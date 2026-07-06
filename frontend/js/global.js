/**
 * global.js — Shared runtime: cursor, lenis, scroll progress,
 * toast system, navbar helpers, GSAP reveal animations.
 * Plain script (no ES module) — loaded after api.js on every page.
 */

/* ============================================================
   LENIS SMOOTH SCROLL
   ============================================================ */
function initLenis() {
  if (typeof Lenis === 'undefined') return;

  const lenis = new Lenis({
    duration:  1.2,
    easing:    (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
    smooth:    true,
    direction: 'vertical',
  });

  if (window.gsap && window.ScrollTrigger) {
    lenis.on('scroll', ScrollTrigger.update);
    gsap.ticker.add((time) => lenis.raf(time * 1000));
    gsap.ticker.lagSmoothing(0);
  } else {
    (function raf(time) { lenis.raf(time); requestAnimationFrame(raf); })(0);
  }
}

/* ============================================================
   SCROLL PROGRESS BAR
   ============================================================ */
function initScrollProgress() {
  const bar = document.getElementById('scroll-progress');
  if (!bar) return;
  window.addEventListener('scroll', () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.transform = `scaleX(${max > 0 ? window.scrollY / max : 0})`;
  }, { passive: true });
}

/* ============================================================
   CUSTOM CURSOR
   ============================================================ */
function initCursor() {
  const dot  = document.querySelector('.cursor-dot');
  const halo = document.querySelector('.cursor-halo');
  if (!dot || !halo || window.matchMedia('(max-width: 768px)').matches) return;

  let mx = 0, my = 0, hx = 0, hy = 0;

  document.addEventListener('mousemove', (e) => {
    mx = e.clientX; my = e.clientY;
    dot.style.transform = `translate(${mx - 4}px, ${my - 4}px)`;
  });

  (function loop() {
    hx += (mx - hx - 24) * 0.12;
    hy += (my - hy - 24) * 0.12;
    halo.style.transform = `translate(${hx}px, ${hy}px)`;
    requestAnimationFrame(loop);
  })();

  document.querySelectorAll('a, button, .video-card, .challenge-card, .lb-row, .quick-chip, .card-hover')
    .forEach((el) => {
      el.addEventListener('mouseenter', () => halo.classList.add('hovered'));
      el.addEventListener('mouseleave', () => halo.classList.remove('hovered'));
    });
}

/* ============================================================
   GSAP ENTRANCE ANIMATIONS
   ============================================================ */
function initAnimations() {
  if (!window.gsap) return;

  gsap.utils.toArray('.will-animate').forEach((el) => {
    gsap.from(el, {
      opacity: 0, y: 30, duration: 0.7, ease: 'power3.out',
      scrollTrigger: window.ScrollTrigger
        ? { trigger: el, start: 'top 88%', once: true }
        : null,
    });
  });

  gsap.utils.toArray('[data-stagger]').forEach((parent) => {
    const children = parent.querySelectorAll('[data-stagger-child]');
    if (!children.length) return;
    gsap.from(children, {
      opacity: 0, y: 24, duration: 0.5, ease: 'power2.out', stagger: 0.07,
      scrollTrigger: window.ScrollTrigger
        ? { trigger: parent, start: 'top 88%', once: true }
        : null,
    });
  });
}

/* ============================================================
   TOAST SYSTEM
   ============================================================ */
function showToast({ title, msg = '', points = null, icon = '🎯', duration = 4000 }) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = `
    <div class="toast-icon">${icon}</div>
    <div class="toast-body">
      <div class="toast-title">${title}</div>
      ${msg ? `<div class="toast-msg">${msg}</div>` : ''}
    </div>
    ${points !== null ? `<div class="toast-points">+${points} puan</div>` : ''}
  `;
  container.appendChild(el);

  if (window.gsap) {
    gsap.from(el, { opacity: 0, x: 60, duration: 0.4, ease: 'power3.out' });
    setTimeout(() => gsap.to(el, {
      opacity: 0, x: 60, duration: 0.35, ease: 'power2.in',
      onComplete: () => el.remove(),
    }), duration);
  } else {
    setTimeout(() => el.remove(), duration);
  }
}

/* ============================================================
   NAVBAR
   ============================================================ */
function initNavbar() {
  const path = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a').forEach((a) => {
    const href = (a.getAttribute('href') || '').replace('./', '');
    if (href === path || (path === '' && href === 'index.html')) {
      a.classList.add('active');
    }
  });

  const pill     = document.getElementById('nav-points');
  const userEl   = document.getElementById('nav-username');
  const logoutEl = document.getElementById('nav-logout');

  if (userEl && Auth.getUsername()) {
    userEl.textContent = Auth.getUsername();
  }

  if (pill && Auth.isLoggedIn()) {
    API.getMe()
      .then((d) => {
        if (pill) pill.textContent = `⚡ ${d.total_points} puan`;
        // Seviye rozeti — gerçek toplam puandan deterministik hesap
        if (d.level && !document.getElementById('nav-level')) {
          const lv = document.createElement('span');
          lv.id = 'nav-level';
          lv.className = 'nav-level-chip';
          lv.title = `${d.level.title} — sonraki seviyeye ${d.level.xp_needed} puan`;
          lv.textContent = `Lv ${d.level.level}`;
          pill.parentNode.insertBefore(lv, pill);
        }
      })
      .catch(() => {});
  }

  if (logoutEl) {
    logoutEl.addEventListener('click', () => {
      Auth.clear();
      window.location.href = 'index.html';
    });
  }

  initBurgerMenu();
}

/* ============================================================
   MOBILE BURGER MENU (Sprint 22)
   JS injection — HTML dosyalarına dokunmadan tüm sayfalarda çalışır
   ============================================================ */
function initBurgerMenu() {
  const navbar = document.querySelector('.navbar');
  const links  = navbar ? navbar.querySelector('.nav-links') : null;
  if (!navbar || !links || document.getElementById('nav-burger')) return;

  const burger = document.createElement('button');
  burger.id = 'nav-burger';
  burger.className = 'nav-burger';
  burger.setAttribute('aria-label', 'Menü');
  burger.textContent = '☰';

  const right = navbar.querySelector('.nav-right');
  if (right) right.appendChild(burger);
  else navbar.appendChild(burger);

  const close = () => {
    navbar.classList.remove('nav-open');
    burger.textContent = '☰';
  };

  burger.addEventListener('click', (e) => {
    e.stopPropagation();
    navbar.classList.toggle('nav-open');
    burger.textContent = navbar.classList.contains('nav-open') ? '✕' : '☰';
  });
  links.addEventListener('click', close);
  document.addEventListener('click', (e) => {
    if (navbar.classList.contains('nav-open') && !navbar.contains(e.target)) close();
  });
}

/* ============================================================
   GLOBAL ARAMA — Ctrl+K KOMUT PALETİ (Sprint 23)
   JS injection — tüm sayfalarda çalışır, sonuçlar gerçek API'den
   ============================================================ */
function initCommandPalette() {
  if (!Auth.isLoggedIn() || document.getElementById('cmdk-overlay')) return;

  const PAGES = [
    { icon: '🎬', title: 'Katalog',    href: 'catalog.html' },
    { icon: '📊', title: 'Panelim',    href: 'panel.html' },
    { icon: '🏆', title: 'Sıralama',   href: 'leaderboard.html' },
    { icon: '👤', title: 'Profil',     href: 'profile.html' },
    { icon: '📡', title: 'Sosyal',     href: 'social.html' },
  ];
  if (Auth.getRole() === 'admin') {
    PAGES.push({ icon: '🛠', title: 'Admin Paneli', href: 'admin.html' });
  }

  const overlay = document.createElement('div');
  overlay.id = 'cmdk-overlay';
  overlay.className = 'cmdk-overlay';
  overlay.innerHTML = `
    <div class="cmdk-box">
      <div class="cmdk-input-row">
        <span>🔍</span>
        <input id="cmdk-input" placeholder="Video, kullanıcı veya sayfa ara…"
               autocomplete="off" spellcheck="false" />
        <kbd class="cmdk-kbd">ESC</kbd>
      </div>
      <div class="cmdk-results" id="cmdk-results"></div>
      <div class="cmdk-footer">
        <span><kbd class="cmdk-kbd">↑↓</kbd> gezin</span>
        <span><kbd class="cmdk-kbd">↵</kbd> aç</span>
        <span><kbd class="cmdk-kbd">Ctrl K</kbd> aç/kapa</span>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  const input     = overlay.querySelector('#cmdk-input');
  const resultsEl = overlay.querySelector('#cmdk-results');
  let items       = [];   // düz liste: {href, el}
  let selected    = 0;
  let debounceT   = null;
  let reqSeq      = 0;

  function open() {
    overlay.classList.add('open');
    input.value = '';
    renderResults(null, '');
    setTimeout(() => input.focus(), 30);
  }
  function close() { overlay.classList.remove('open'); }
  function toggle() { overlay.classList.contains('open') ? close() : open(); }

  function setSelected(i) {
    if (!items.length) return;
    selected = (i + items.length) % items.length;
    items.forEach((it, idx) => it.el.classList.toggle('selected', idx === selected));
    items[selected].el.scrollIntoView({ block: 'nearest' });
  }

  function renderResults(data, q) {
    const ql = q.trim().toLowerCase();
    const pages = PAGES.filter(p => !ql || p.title.toLowerCase().includes(ql));
    let html = '';

    if (pages.length) {
      html += `<div class="cmdk-section">Sayfalar</div>` + pages.map(p => `
        <div class="cmdk-item" data-href="${p.href}">
          <span class="cmdk-item-icon">${p.icon}</span>
          <span class="cmdk-item-title">${p.title}</span>
        </div>`).join('');
    }
    if (data?.videos?.length) {
      html += `<div class="cmdk-section">Videolar</div>` + data.videos.map(v => `
        <div class="cmdk-item" data-href="content.html?id=${encodeURIComponent(v.id)}">
          <span class="cmdk-item-icon" style="color:${v.thumbnail_color}">🎬</span>
          <span class="cmdk-item-title">${v.title}</span>
          <span class="cmdk-item-meta">${v.genre} · ${Math.round(v.duration_minutes)} dk
            ${v.avg_rating > 0 ? '· ⭐ ' + v.avg_rating : ''} · 👁 ${v.watches}</span>
        </div>`).join('');
    }
    if (data?.users?.length) {
      html += `<div class="cmdk-section">Kullanıcılar</div>` + data.users.map(u => `
        <div class="cmdk-item" data-href="profile.html?u=${encodeURIComponent(u.username)}">
          <span class="cmdk-item-icon">👤</span>
          <span class="cmdk-item-title">${u.username}${u.is_me ? ' (sen)' : ''}</span>
          <span class="cmdk-item-meta">Lv ${u.level} · ⚡ ${u.total_points}</span>
        </div>`).join('');
    }
    if (!html) {
      html = `<div class="cmdk-empty">“${q}” için sonuç yok</div>`;
    }

    resultsEl.innerHTML = html;
    items = [...resultsEl.querySelectorAll('.cmdk-item')].map(el => ({
      href: el.dataset.href, el,
    }));
    items.forEach((it, idx) => {
      it.el.addEventListener('click', () => { window.location.href = it.href; });
      it.el.addEventListener('mousemove', () => setSelected(idx));
    });
    selected = 0;
    if (items.length) items[0].el.classList.add('selected');
  }

  input.addEventListener('input', () => {
    const q = input.value;
    clearTimeout(debounceT);
    if (q.trim().length < 1) { renderResults(null, ''); return; }
    debounceT = setTimeout(async () => {
      const seq = ++reqSeq;
      try {
        const data = await API.search(q.trim());
        if (seq === reqSeq) renderResults(data, q);   // bayat yanıtı atla
      } catch (_) {
        if (seq === reqSeq) renderResults(null, q);
      }
    }, 250);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(selected + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSelected(selected - 1); }
    else if (e.key === 'Enter' && items[selected]) {
      window.location.href = items[selected].href;
    }
  });

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      toggle();
    } else if (e.key === 'Escape' && overlay.classList.contains('open')) {
      close();
    }
  });
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });

  // Navbar'a arama butonu
  const right = document.querySelector('.nav-right');
  if (right && !document.getElementById('nav-search-btn')) {
    const btn = document.createElement('button');
    btn.id = 'nav-search-btn';
    btn.className = 'nav-search-btn';
    btn.title = 'Ara (Ctrl+K)';
    btn.innerHTML = '🔍';
    btn.addEventListener('click', open);
    right.insertBefore(btn, right.firstChild);
  }
}

/* ============================================================
   PWA (Sprint 22) — manifest + service worker
   ============================================================ */
function initPWA() {
  if (!document.querySelector('link[rel="manifest"]')) {
    const l = document.createElement('link');
    l.rel = 'manifest';
    l.href = '/manifest.json';
    document.head.appendChild(l);
  }
  if (!document.querySelector('meta[name="theme-color"]')) {
    const m = document.createElement('meta');
    m.name = 'theme-color';
    m.content = '#050508';
    document.head.appendChild(m);
  }
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
}

/* ============================================================
   PAGE INIT
   ============================================================ */
function initPage({ auth = true } = {}) {
  if (auth && !Auth.isLoggedIn()) {
    window.location.href = 'index.html';
    return;
  }

  initLenis();
  initScrollProgress();
  initCursor();
  initNavbar();
  initCommandPalette();
  initPWA();

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAnimations);
  } else {
    initAnimations();
  }
}

/* ============================================================
   STAT NUMBER COUNTER ANIMATION
   ============================================================ */
function animateNumber(el, target, duration = 1200) {
  if (!el) return;
  const start = parseInt(el.textContent) || 0;
  const step  = (ts) => {
    if (!animateNumber._start) animateNumber._start = ts;
    const progress = Math.min((ts - animateNumber._start) / duration, 1);
    el.textContent = Math.round(start + (target - start) * progress);
    if (progress < 1) requestAnimationFrame(step);
    else { delete animateNumber._start; }
  };
  requestAnimationFrame(step);
}

/* ============================================================
   BADGE LABEL HELPER
   ============================================================ */
function badgeClass(tier) {
  const map = { bronze: 'badge-bronze', silver: 'badge-silver', gold: 'badge-gold', platinum: 'badge-platinum' };
  return map[tier?.toLowerCase()] || 'badge-bronze';
}

function badgeEmoji(tier) {
  const map = { bronze: '🥉', silver: '🥈', gold: '🥇', platinum: '💎' };
  return map[tier?.toLowerCase()] || '🏅';
}

/* ============================================================
   FORMAT HELPERS
   ============================================================ */
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', year: 'numeric' });
}

function fmtNum(n) {
  return Number(n || 0).toLocaleString('tr-TR');
}

/* ============================================================
   CELEBRATE — GSAP konfeti patlaması
   ============================================================ */
function celebratePoints(points, { x = window.innerWidth / 2, y = window.innerHeight / 2 } = {}) {
  if (!window.gsap) {
    showToast({ title: `+${points} puan!`, icon: '🎉', duration: 3000 });
    return;
  }

  const COLORS  = ['#00FF87', '#00D4FF', '#FFB800', '#6C00FF', '#FF4D4D', '#fff'];
  const COUNT   = 40;
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:9995;overflow:hidden';
  document.body.appendChild(overlay);

  for (let i = 0; i < COUNT; i++) {
    const p   = document.createElement('div');
    const clr = COLORS[Math.floor(Math.random() * COLORS.length)];
    const sz  = 6 + Math.random() * 8;
    p.style.cssText = `position:absolute;width:${sz}px;height:${sz}px;
      background:${clr};border-radius:${Math.random() > 0.5 ? '50%' : '2px'};
      left:${x}px;top:${y}px;opacity:1`;
    overlay.appendChild(p);

    const angle  = (Math.random() * Math.PI * 2);
    const dist   = 120 + Math.random() * 200;
    const tx     = Math.cos(angle) * dist;
    const ty     = Math.sin(angle) * dist - 60;

    gsap.to(p, {
      x: tx, y: ty,
      rotation:  Math.random() * 720 - 360,
      opacity:   0,
      duration:  0.9 + Math.random() * 0.6,
      ease:      'power2.out',
      delay:     Math.random() * 0.15,
      onComplete: () => p.remove(),
    });
  }

  // Büyük puan metni
  const label = document.createElement('div');
  label.textContent = `+${points}`;
  label.style.cssText = `position:fixed;left:${x}px;top:${y - 40}px;
    font-family:'JetBrains Mono',monospace;font-size:32px;font-weight:700;
    color:#00FF87;text-shadow:0 0 20px rgba(0,255,135,0.6);
    pointer-events:none;z-index:9996;transform:translate(-50%,-50%);opacity:0`;
  document.body.appendChild(label);

  gsap.timeline()
    .to(label, { opacity: 1, y: -20, duration: 0.3, ease: 'back.out(1.7)' })
    .to(label, { opacity: 0, y: -60, duration: 0.5, ease: 'power2.in', delay: 0.8,
      onComplete: () => { label.remove(); overlay.remove(); } });
}

/* ============================================================
   WEEKLY ACTIVITY CHART — pure CSS bar chart
   ============================================================ */
function renderWeeklyChart(containerId, days) {
  const el = document.getElementById(containerId);
  if (!el || !days?.length) return;

  const maxMin = Math.max(...days.map(d => d.minutes), 1);
  const dayNames = ['Pzt','Sal','Çar','Per','Cum','Cmt','Paz'];

  el.innerHTML = days.map((d) => {
    const pct   = Math.round((d.minutes / maxMin) * 100);
    const dt    = new Date(d.date);
    const label = dayNames[dt.getDay() === 0 ? 6 : dt.getDay() - 1];
    const isToday = d.date === new Date().toISOString().slice(0, 10);

    return `
      <div class="chart-bar-wrap ${isToday ? 'today' : ''}">
        <div class="chart-bar-val">${d.minutes > 0 ? Math.round(d.minutes) + 'dk' : ''}</div>
        <div class="chart-bar-track">
          <div class="chart-bar-fill" data-pct="${pct}" style="height:0%"></div>
        </div>
        <div class="chart-bar-label">${label}</div>
        ${d.points > 0 ? `<div class="chart-bar-pts">+${d.points}</div>` : ''}
      </div>`;
  }).join('');

  // Animate bars with GSAP or CSS
  setTimeout(() => {
    el.querySelectorAll('.chart-bar-fill').forEach((bar) => {
      const pct = bar.dataset.pct;
      if (window.gsap) {
        gsap.to(bar, { height: pct + '%', duration: 0.8, ease: 'power2.out',
          delay: 0.05 * Array.from(el.querySelectorAll('.chart-bar-fill')).indexOf(bar) });
      } else {
        bar.style.height = pct + '%';
      }
    });
  }, 100);
}
