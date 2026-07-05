/**
 * notifications.js — SSE client + bildirim çanı UI.
 * global.js ve api.js'den SONRA yüklenir.
 * initNotifications() çağrısıyla başlatılır.
 */

(function () {
  'use strict';

  let es         = null;   // EventSource
  let unread     = 0;
  let bellEl     = null;
  let badgeEl    = null;
  let pointsPill = null;

  /* ── Çan oluştur / güncelle ────────────────────────────── */
  function createBell() {
    const right = document.querySelector('.nav-right');
    if (!right || document.getElementById('notif-bell')) return;

    const bell = document.createElement('button');
    bell.id        = 'notif-bell';
    bell.className = 'notif-bell';
    bell.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
        <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
      </svg>
      <span class="notif-badge" id="notif-badge" style="display:none">0</span>`;
    right.insertBefore(bell, right.firstChild);

    bellEl  = bell;
    badgeEl = document.getElementById('notif-badge');

    // Tıklayınca okundu say
    bell.addEventListener('click', () => {
      unread = 0;
      updateBadge();
    });

    // Hover cursor
    bell.addEventListener('mouseenter', () =>
      document.querySelector('.cursor-halo')?.classList.add('hovered'));
    bell.addEventListener('mouseleave', () =>
      document.querySelector('.cursor-halo')?.classList.remove('hovered'));
  }

  function updateBadge() {
    if (!badgeEl) return;
    if (unread > 0) {
      badgeEl.textContent = unread > 9 ? '9+' : String(unread);
      badgeEl.style.display = '';
    } else {
      badgeEl.style.display = 'none';
    }
    if (bellEl) {
      bellEl.classList.toggle('has-notif', unread > 0);
    }
  }

  /* ── Points pill güncelle ──────────────────────────────── */
  function refreshPointsPill(totalPoints) {
    if (!pointsPill) pointsPill = document.getElementById('nav-points');
    if (pointsPill && totalPoints != null) {
      pointsPill.textContent = `⚡ ${totalPoints} puan`;
      pointsPill.classList.add('pulse');
      setTimeout(() => pointsPill.classList.remove('pulse'), 700);
    }
  }

  /* ── Bildirim işle ─────────────────────────────────────── */
  function handleNotification(data) {
    if (data.type === 'connected') return;
    if (data.type === 'reconnect') {
      // Kısa bekleme sonra yeniden bağlan
      setTimeout(connect, 3000);
      return;
    }

    unread++;
    updateBadge();

    if (data.type === 'points') {
      showToast({
        title: '🎯 Puan Kazandın!',
        msg:   data.reason || 'Görev tamamlandı',
        points: data.points,
        icon:  '⚡',
      });
      refreshPointsPill(data.total_points);
      // Leaderboard sayfası dinliyorsa otomatik yenile
      window.dispatchEvent(new CustomEvent('sse-points', { detail: data }));
    } else if (data.type === 'badge') {
      showToast({
        title: '🏅 Yeni Rozet!',
        msg:   data.badge,
        icon:  '🏆',
        duration: 6000,
      });
    } else if (data.type === 'challenge') {
      showToast({
        title: '🎯 ' + (data.challenge_name || 'Görev tamamlandı'),
        msg:   data.message || '',
        icon:  '⚡',
      });
    }
  }

  /* ── SSE bağlantısı ────────────────────────────────────── */
  function connect() {
    if (!Auth.isLoggedIn()) return;
    if (es) { es.close(); es = null; }

    const token = Auth.getToken();
    es = new EventSource(`/api/notifications/stream?token=${token}`);

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        handleNotification(data);
      } catch (_) {}
    };

    es.onerror = () => {
      es.close();
      es = null;
      // 5s sonra yeniden bağlan
      setTimeout(connect, 5000);
    };
  }

  /* ── Public API ────────────────────────────────────────── */
  window.initNotifications = function () {
    if (!Auth.isLoggedIn()) return;
    createBell();
    pointsPill = document.getElementById('nav-points');
    connect();
  };

  window.pushLocalNotification = handleNotification;

})();
