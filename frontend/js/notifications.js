/**
 * notifications.js — SSE client + kalıcı bildirim merkezi (Sprint 16).
 * global.js ve api.js'den SONRA yüklenir.
 * initNotifications() çağrısıyla başlatılır.
 *
 * Okunmamış sayacı DB'den gelir (sayfa yenilense de korunur);
 * çan ikonuna tıklayınca kalıcı bildirim geçmişi paneli açılır.
 */

(function () {
  'use strict';

  let es         = null;   // EventSource
  let unread     = 0;
  let bellEl     = null;
  let badgeEl    = null;
  let panelEl    = null;
  let panelOpen  = false;
  let pointsPill = null;

  /* ── Çan + panel oluştur ───────────────────────────────── */
  function createBell() {
    const right = document.querySelector('.nav-right');
    if (!right || document.getElementById('notif-bell')) return;

    const wrap = document.createElement('div');
    wrap.className = 'notif-wrap';
    wrap.innerHTML = `
      <button id="notif-bell" class="notif-bell">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
        <span class="notif-badge" id="notif-badge" style="display:none">0</span>
      </button>
      <div class="notif-panel" id="notif-panel">
        <div class="notif-panel-header">
          <span>🔔 Bildirimler</span>
          <button class="notif-mark-all" id="notif-mark-all">Tümünü okundu yap</button>
        </div>
        <div class="notif-panel-list" id="notif-panel-list">
          <div class="notif-empty">Yükleniyor…</div>
        </div>
      </div>`;
    right.insertBefore(wrap, right.firstChild);

    bellEl  = document.getElementById('notif-bell');
    badgeEl = document.getElementById('notif-badge');
    panelEl = document.getElementById('notif-panel');

    bellEl.addEventListener('click', (e) => {
      e.stopPropagation();
      panelOpen ? closePanel() : openPanel();
    });

    document.getElementById('notif-mark-all').addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        await API.markNotifsRead(true);
        unread = 0;
        updateBadge();
        loadPanelList();
      } catch (_) {}
    });

    // Dışarı tıklayınca kapat
    document.addEventListener('click', (e) => {
      if (panelOpen && !wrap.contains(e.target)) closePanel();
    });

    bellEl.addEventListener('mouseenter', () =>
      document.querySelector('.cursor-halo')?.classList.add('hovered'));
    bellEl.addEventListener('mouseleave', () =>
      document.querySelector('.cursor-halo')?.classList.remove('hovered'));
  }

  function openPanel() {
    panelOpen = true;
    panelEl.classList.add('open');
    loadPanelList();
  }

  function closePanel() {
    panelOpen = false;
    panelEl.classList.remove('open');
  }

  const TYPE_ICONS = {
    points: '⚡', badge: '🏅', challenge: '🎯',
    party: '🎉', level: '⬆️', info: '🔔',
  };

  function relTime(ts) {
    if (!ts) return '';
    const diff = (Date.now() - new Date(ts)) / 1000;
    if (diff < 60)    return `${Math.round(diff)}s önce`;
    if (diff < 3600)  return `${Math.round(diff / 60)}dk önce`;
    if (diff < 86400) return `${Math.round(diff / 3600)}sa önce`;
    return `${Math.round(diff / 86400)}g önce`;
  }

  async function loadPanelList() {
    const list = document.getElementById('notif-panel-list');
    try {
      const d = await API.getNotifications();
      const items = d.notifications || [];
      if (!items.length) {
        list.innerHTML = '<div class="notif-empty">Henüz bildirim yok.</div>';
        return;
      }
      list.innerHTML = items.map(n => `
        <div class="notif-item ${n.is_read ? '' : 'unread'}" data-id="${n.id}">
          <span class="notif-item-icon">${TYPE_ICONS[n.type] || '🔔'}</span>
          <div class="notif-item-body">
            <div class="notif-item-title">${n.title}</div>
            ${n.message ? `<div class="notif-item-msg">${n.message}</div>` : ''}
            <div class="notif-item-time">${relTime(n.created_at)}</div>
          </div>
          ${n.is_read ? '' : '<span class="notif-dot"></span>'}
        </div>`).join('');

      // Tek bildirime tıkla → okundu
      list.querySelectorAll('.notif-item.unread').forEach(el => {
        el.addEventListener('click', async () => {
          const id = parseInt(el.dataset.id);
          try {
            await API.markNotifsRead([id]);
            el.classList.remove('unread');
            el.querySelector('.notif-dot')?.remove();
            unread = Math.max(0, unread - 1);
            updateBadge();
          } catch (_) {}
        });
      });
    } catch (e) {
      list.innerHTML = `<div class="notif-empty">${e.message}</div>`;
    }
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

  async function initUnreadCount() {
    try {
      const d = await API.getUnreadCount();
      unread = d.count || 0;
      updateBadge();
    } catch (_) {}
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
      setTimeout(connect, 3000);
      return;
    }

    unread++;
    updateBadge();
    if (panelOpen) loadPanelList();

    if (data.type === 'points') {
      showToast({
        title: '🎯 Puan Kazandın!',
        msg:   data.reason || 'Görev tamamlandı',
        points: data.points,
        icon:  '⚡',
      });
      refreshPointsPill(data.total_points);
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
    } else if (data.type === 'party') {
      showToast({
        title: '🎉 Watch Party',
        msg:   data.message || '',
        icon:  '🎉',
        duration: 5000,
      });
      window.dispatchEvent(new CustomEvent('sse-party', { detail: data }));
    } else if (data.type === 'level') {
      showToast({
        title: `⬆️ Seviye Atladın! Lv ${data.level}`,
        msg:   data.message || '',
        icon:  '🌟',
        duration: 6500,
      });
      if (typeof celebratePoints === 'function') celebratePoints(data.level);
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
      setTimeout(connect, 5000);
    };
  }

  /* ── Public API ────────────────────────────────────────── */
  window.initNotifications = function () {
    if (!Auth.isLoggedIn()) return;
    createBell();
    pointsPill = document.getElementById('nav-points');
    initUnreadCount();
    connect();
  };

  window.pushLocalNotification = handleNotification;

})();
