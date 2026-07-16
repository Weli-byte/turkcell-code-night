/**
 * smart-features.js — Smart Frontend ozellikleri (her sayfada yuklenir).
 * Streaming AI (gercek EventSource), Live Reasoning, Optimistic UI,
 * Realtime Updates, Smart Prefetch, Live Notifications, AI Challenge Card,
 * Multi-Leaderboard Tabs, Recommendation Feed.
 */

// ── OZELLIK 1: Streaming AI (EventSource) ─────────
async function askAIStream(question, options = {}) {
  const {
    onIntent    = () => {},
    onEvidence  = () => {},
    onChunk     = () => {},
    onGrounding = () => {},
    onDone      = () => {},
    onError     = () => {},
    targetEl    = null,
  } = options;

  const token = Auth.getToken();
  if (!token) return;

  const url = `/api/ai/stream?question=${encodeURIComponent(question)}&token=${encodeURIComponent(token)}`;
  const es = new EventSource(url);
  let fullAnswer = '';

  es.onmessage = (e) => {
    if (!e.data || e.data === '') return;
    try {
      const payload = JSON.parse(e.data);
      const { event, data } = payload;

      if (event === 'intent') {
        onIntent(data);
      } else if (event === 'evidence') {
        onEvidence(data);
      } else if (event === 'chunk') {
        fullAnswer += data;
        if (targetEl) targetEl.textContent += data;
        onChunk(data, fullAnswer);
      } else if (event === 'grounding') {
        onGrounding(data);
      } else if (event === 'done') {
        es.close();
        onDone(fullAnswer);
      } else if (event === 'error') {
        es.close();
        onError(data);
      }
    } catch (err) {
      console.error('SSE parse hatasi:', err);
    }
  };

  es.onerror = () => {
    es.close();
    onError('Bağlantı hatası');
  };

  return {
    close: () => es.close(),
    getAnswer: () => fullAnswer,
  };
}

// ── OZELLIK 2: Live Reasoning gorunumu ────────────
function showLiveReasoning(containerEl) {
  const steps = [
    { icon: '🔍', text: 'Intent belirleniyor...' },
    { icon: '📊', text: 'Veriler toplanıyor...' },
    { icon: '🤖', text: 'AI analiz yapıyor...' },
    { icon: '✅', text: 'Doğrulama yapılıyor...' },
  ];

  containerEl.innerHTML = '';
  containerEl.style.display = '';

  const items = steps.map((step) => {
    const el = document.createElement('div');
    el.className = 'reasoning-step';
    el.style.cssText =
      'display:flex; align-items:center; gap:8px; padding:6px 0;' +
      'opacity:0; font-size:13px; color:var(--text-2);';
    el.innerHTML = `
      <span>${step.icon}</span>
      <span>${step.text}</span>
      <span class="reasoning-dot" style="margin-left:auto; width:6px; height:6px;
        border-radius:50%; background:var(--accent-1); display:none;"></span>`;
    containerEl.appendChild(el);
    return el;
  });

  let currentStep = 0;

  function activateStep(index) {
    if (index >= items.length) return;
    const el = items[index];
    gsap.to(el, { opacity: 1, x: 0, duration: 0.4, ease: 'power2.out' });
    el.querySelector('.reasoning-dot').style.display = 'block';
    if (index > 0) {
      items[index - 1].querySelector('.reasoning-dot')
        .style.background = 'var(--text-muted)';
    }
    currentStep = index + 1;
  }

  return {
    next: () => activateStep(currentStep),
    complete: () => {
      items.forEach((el) => {
        el.querySelector('.reasoning-dot').style.background = 'var(--accent-1)';
        gsap.to(el, { opacity: 1, duration: 0.2 });
      });
      containerEl.style.display = 'none';
    },
    activate: activateStep,
  };
}

// ── OZELLIK 3: Optimistic UI ──────────────────────
// Tahmini deger hemen gosterilir; NIHAI deger daima backend'den dogrulanir.
function optimisticUpdate(el, predictedValue, realValuePromise) {
  const original = el.textContent;

  gsap.to(el, { opacity: 0.5, duration: 0.2 });
  el.textContent = predictedValue;
  el.setAttribute('data-optimistic', 'true');

  realValuePromise
    .then(realValue => {
      el.textContent = realValue;
      el.removeAttribute('data-optimistic');
      gsap.to(el, { opacity: 1, duration: 0.3 });

      if (String(realValue) !== String(predictedValue)) {
        gsap.fromTo(el,
          { color: 'var(--accent-2)' },
          { color: '', duration: 1 }
        );
      }
    })
    .catch(() => {
      el.textContent = original;
      el.removeAttribute('data-optimistic');
      gsap.to(el, { opacity: 1, duration: 0.3 });
    });
}

// ── OZELLIK 4: Realtime Updates ───────────────────
let realtimeIntervals = {};

function startRealtimeUpdate(key, fetchFn, renderFn, intervalMs = 30000) {
  stopRealtimeUpdate(key);

  async function update() {
    try {
      const data = await fetchFn();
      renderFn(data);
    } catch (e) {
      console.error(`Realtime [${key}] hata:`, e);
    }
  }

  update();
  realtimeIntervals[key] = setInterval(update, intervalMs);
}

function stopRealtimeUpdate(key) {
  if (realtimeIntervals[key]) {
    clearInterval(realtimeIntervals[key]);
    delete realtimeIntervals[key];
  }
}

function stopAllRealtimeUpdates() {
  Object.keys(realtimeIntervals).forEach(stopRealtimeUpdate);
}

window.addEventListener('beforeunload', stopAllRealtimeUpdates);

// ── OZELLIK 5: Smart Prefetch ─────────────────────
const prefetchCache = {};

async function prefetchContent(contentId) {
  if (prefetchCache[contentId]) return;
  try {
    const data = await API.getContent(contentId);
    prefetchCache[contentId] = data;

    if (data.stream_url) {
      const link = document.createElement('link');
      link.rel  = 'prefetch';
      link.href = data.stream_url;
      document.head.appendChild(link);
    }
  } catch (e) { /* prefetch hatasi sessizce yutulur */ }
}

function initSmartPrefetch() {
  const videoCards = document.querySelectorAll('.video-card[data-content-id]');

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.getAttribute('data-content-id');
          if (id) {
            // Gorunur olduktan kisa sure sonra on-yukle
            gsap.delayedCall(0.5, () => prefetchContent(id));
          }
          observer.unobserve(entry.target);
        }
      });
    },
    { rootMargin: '200px' }
  );

  videoCards.forEach(card => observer.observe(card));
}

// ── OZELLIK 6: Live Notifications ─────────────────
const notifQueue = [];
let notifShowing = false;

function showLiveNotif(message, type = 'success', duration = 5000) {
  notifQueue.push({ message, type, duration });
  if (!notifShowing) processNotifQueue();
}

function processNotifQueue() {
  if (!notifQueue.length) {
    notifShowing = false;
    return;
  }
  notifShowing = true;
  const { message, type, duration } = notifQueue.shift();

  let notif = document.getElementById('live-notif');
  if (!notif) {
    notif = document.createElement('div');
    notif.id = 'live-notif';
    notif.style.cssText =
      'position:fixed; top:80px; right:24px; z-index:9990;' +
      'background:var(--bg-card-2); border:1px solid var(--border-acc);' +
      'border-radius:var(--radius); padding:16px 20px;' +
      'min-width:260px; max-width:380px; backdrop-filter:blur(12px);' +
      'font-size:14px; color:var(--text-1); display:none;';
    document.body.appendChild(notif);
  }

  if (type === 'reward')      notif.style.borderColor = 'var(--accent-1)';
  else if (type === 'badge')  notif.style.borderColor = 'var(--gold)';
  else if (type === 'error')  notif.style.borderColor = 'var(--danger)';
  else                        notif.style.borderColor = 'var(--border-acc)';

  notif.innerHTML = message;
  notif.style.display = 'block';

  gsap.fromTo(notif,
    { x: 60, opacity: 0 },
    { x: 0, opacity: 1, duration: 0.4, ease: 'expo.out' }
  );

  gsap.delayedCall(duration / 1000, () => {
    gsap.to(notif, {
      x: 60, opacity: 0,
      duration: 0.3, ease: 'power2.in',
      onComplete: () => {
        notif.style.display = 'none';
        processNotifQueue();
      }
    });
  });
}

function notifyReward(points, challengeName) {
  showLiveNotif(`
    <div style="font-weight:600; margin-bottom:4px">
      ⭐ +${formatPoints(points)} Puan!
    </div>
    <div style="font-size:12px; color:var(--text-2)">
      ${esc(challengeName)} tamamlandı
    </div>
  `, 'reward', 6000);
}

function notifyBadge(tier) {
  const icons = { BRONZE: '🥉', SILVER: '🥈', GOLD: '🥇', PLATINUM: '💎' };
  showLiveNotif(`
    <div style="font-weight:600; margin-bottom:4px">
      ${icons[tier] || '🏆'} ${esc(tier)} Rozeti!
    </div>
    <div style="font-size:12px; color:var(--text-2)">
      Tebrikler, yeni rozet kazandın!
    </div>
  `, 'badge', 7000);
}

// ── OZELLIK 7: AI Challenge Card ──────────────────
async function renderAIChallengeCard(containerEl) {
  if (!containerEl) return;

  containerEl.innerHTML = `
    <div class="card card-accent">
      <div class="flex-between" style="margin-bottom:12px">
        <span style="font-weight:600">🤖 AI Önerisi</span>
        <span class="spinner spinner-sm"></span>
      </div>
      <p class="text-muted" style="font-size:13px">
        Kişisel challenge'lar yükleniyor...
      </p>
    </div>`;

  try {
    const res = await apiFetch('/api/ai/challenge/generate', {
      method: 'POST',
      body: JSON.stringify({}),
    });

    const challenges = res.challenges || [];

    if (!challenges.length) {
      containerEl.innerHTML = '';
      return;
    }

    containerEl.innerHTML = `
      <div class="card card-accent anim-fade">
        <div class="flex-between" style="margin-bottom:16px">
          <span style="font-weight:600; font-size:15px">🤖 AI Kişisel Önerileri</span>
          <span class="badge-chip badge-none" style="font-size:10px">GPT-4o</span>
        </div>
        ${challenges.map(ch => `
          <div class="challenge-card" style="margin-bottom:8px">
            <div class="flex-between">
              <span class="challenge-name">${esc(ch.name)}</span>
              <span class="challenge-pts">+${ch.reward_points}p</span>
            </div>
            <div class="challenge-condition">${esc(ch.condition)}</div>
            ${ch.reason ? `
              <div style="font-size:12px; color:var(--text-muted); margin-top:4px">
                💡 ${esc(ch.reason)}
              </div>` : ''}
          </div>`).join('')}
      </div>`;

    gsap.from(containerEl.querySelector('.card'), {
      y: 30, opacity: 0, duration: 0.6, ease: 'expo.out'
    });

  } catch (e) {
    containerEl.innerHTML = `
      <div class="card" style="opacity:0.5">
        <p class="text-muted" style="font-size:13px">
          AI önerileri şu an yüklenemiyor.
        </p>
      </div>`;
    console.error('AI Challenge Card:', e);
  }
}

// ── OZELLIK 8: Multi-Leaderboard Tabs ─────────────
function initLeaderboardTabs(containerEl, tabsEl) {
  if (!containerEl || !tabsEl) return;

  const tabs = [
    { key: 'genel',     label: 'Genel',     fetch: () => API.getLeaderboard() },
    { key: 'haftalik',  label: 'Bu Hafta',  fetch: () => apiFetch('/api/leaderboard/weekly') },
    { key: 'en_aktif',  label: 'En Aktif',  fetch: () => apiFetch('/api/ai/leaderboard/en_aktif') },
    { key: 'en_sosyal', label: 'En Sosyal', fetch: () => apiFetch('/api/ai/leaderboard/en_sosyal') },
    { key: 'ai_score',  label: 'AI Score',  fetch: () => apiFetch('/api/ai/leaderboard/ai_score') },
  ];

  let activeTab = 'genel';

  tabsEl.innerHTML = tabs.map(t => `
    <button
      class="btn btn-sm ${t.key === 'genel' ? 'btn-primary' : 'btn-ghost'}"
      data-tab="${t.key}"
      onclick="switchLeaderboardTab('${t.key}')">${t.label}</button>`).join('');

  async function loadTab(key) {
    const tab = tabs.find(t => t.key === key);
    if (!tab) return;

    containerEl.style.opacity = '0.5';
    try {
      const data = await tab.fetch();
      renderLeaderboard(containerEl, data);
      gsap.to(containerEl, { opacity: 1, duration: 0.3 });
    } catch (e) {
      containerEl.style.opacity = '1';
    }
  }

  window.switchLeaderboardTab = (key) => {
    activeTab = key;
    tabsEl.querySelectorAll('button').forEach(btn => {
      const isActive = btn.dataset.tab === key;
      btn.className = `btn btn-sm ${isActive ? 'btn-primary' : 'btn-ghost'}`;
    });
    loadTab(key);
  };

  loadTab('genel');

  // 30 sn'de bir aktif sekmeyi gercek API'den tazele
  startRealtimeUpdate(
    'leaderboard',
    () => tabs.find(t => t.key === activeTab).fetch(),
    (data) => renderLeaderboard(containerEl, data),
    30000
  );
}

function renderLeaderboard(containerEl, data) {
  const myId = Auth.getUserId();
  const rows = Array.isArray(data) ? data : [];

  containerEl.innerHTML = `
    <table class="lb-table">
      <thead><tr>
        <th style="width:60px">#</th>
        <th>Kullanıcı</th>
        <th>Rozetler</th>
        <th style="text-align:right">Puan</th>
      </tr></thead>
      <tbody>
        ${rows.map(e => `
          <tr class="${(e.user_id === myId || e.is_current_user) ? 'me' : ''}">
            <td>
              <span class="lb-rank ${
                e.rank === 1 ? 'gold' :
                e.rank === 2 ? 'silver' :
                e.rank === 3 ? 'bronze' : ''}">${getRankIcon(e.rank)}</span>
            </td>
            <td>
              <span style="font-weight:${e.is_current_user ? '600' : '400'}">${esc(e.username)}</span>
              ${e.is_current_user
                ? '<span class="badge-chip badge-none" style="margin-left:6px; font-size:10px">Sen</span>'
                : ''}
            </td>
            <td>
              ${(e.badges || []).map(b =>
                `<span class="badge-chip ${getBadgeClass(b)}" style="font-size:10px">${esc(b)}</span>`
              ).join(' ') || '<span class="text-muted">—</span>'}
            </td>
            <td style="text-align:right">
              <span class="lb-pts">${formatPoints(
                e.total_points ?? e.weekly_points ?? e.score ?? e.ai_score ?? 0
              )}</span>
            </td>
          </tr>`).join('')}
      </tbody>
    </table>`;

  const trows = containerEl.querySelectorAll('tbody tr');
  if (trows.length && typeof gsap !== 'undefined') {
    gsap.from(trows, {
      y: 20, opacity: 0, stagger: 0.04, duration: 0.5, ease: 'expo.out'
    });
  }
}

// ── OZELLIK 9: Recommendation Feed ────────────────
async function renderRecommendationFeed(containerEl) {
  if (!containerEl) return;

  containerEl.innerHTML = '<div class="spinner"></div>';

  try {
    const res = await apiFetch('/api/ai/recommendations');
    const recs = res.recommendations || {};

    const allRecs = [
      ...(recs.video     || []).slice(0, 3).map(r => ({ ...r, type: 'video' })),
      ...(recs.challenge || []).slice(0, 2).map(r => ({ ...r, type: 'challenge' })),
      ...(recs.badge     || []).slice(0, 1).map(r => ({ ...r, type: 'badge' })),
    ];

    if (!allRecs.length) {
      containerEl.innerHTML = '<p class="text-muted">Öneri yok.</p>';
      return;
    }

    containerEl.innerHTML = `
      <div class="anim-stagger">
        ${allRecs.map(rec => `
          <div class="card" style="margin-bottom:10px; padding:14px 18px">
            <div class="flex-center gap-12">
              <span style="font-size:20px">${
                rec.type === 'video' ? '🎬' :
                rec.type === 'challenge' ? '🎯' : '🏆'}</span>
              <div style="flex:1">
                <div style="font-weight:500; font-size:14px">
                  ${esc(rec.title || rec.name || rec.badge || '—')}
                </div>
                <div style="font-size:12px; color:var(--text-muted)">
                  ${esc(rec.reason || rec.type || '—')}
                </div>
              </div>
              ${rec.type === 'video' ? `
                <button class="btn btn-ghost btn-sm js-watch"
                        data-id="${esc(rec.id)}">İzle</button>` : ''}
            </div>
          </div>`).join('')}
      </div>`;

    // Inline onclick yerine programatik listener (XSS yuzeyini kucultur)
    containerEl.querySelectorAll('.js-watch').forEach(b => {
      b.addEventListener('click', () => goWatch(b.dataset.id));
    });

    if (typeof gsap !== 'undefined') {
      const cards = containerEl.querySelectorAll('.card');
      gsap.from(cards, {
        y: 20, opacity: 0, stagger: 0.08, duration: 0.5, ease: 'expo.out'
      });
    }

  } catch (e) {
    containerEl.innerHTML = '<p class="text-muted">Öneri yüklenemedi.</p>';
  }
}

// ── Global'e ac ───────────────────────────────────
window.askAIStream              = askAIStream;
window.showLiveReasoning        = showLiveReasoning;
window.optimisticUpdate         = optimisticUpdate;
window.startRealtimeUpdate      = startRealtimeUpdate;
window.stopRealtimeUpdate       = stopRealtimeUpdate;
window.initSmartPrefetch        = initSmartPrefetch;
window.showLiveNotif            = showLiveNotif;
window.notifyReward             = notifyReward;
window.notifyBadge              = notifyBadge;
window.renderAIChallengeCard    = renderAIChallengeCard;
window.initLeaderboardTabs      = initLeaderboardTabs;
window.renderLeaderboard        = renderLeaderboard;
window.renderRecommendationFeed = renderRecommendationFeed;
window.prefetchContent          = prefetchContent;
