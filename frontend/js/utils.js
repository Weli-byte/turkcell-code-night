/**
 * utils.js — Tum sayfalarda kullanilan yardimci fonksiyonlar.
 */

function showToast(message, type = 'success',
                   duration = 4000) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.className = `toast show ${
    type === 'error' ? 'error' : ''
  }`;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.classList.remove('show');
  }, duration);
}

function formatPoints(n) {
  return Number(n).toLocaleString('tr-TR');
}

function formatMinutes(min) {
  const m = Math.round(min);
  if (m < 60) return `${m} dk`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r > 0 ? `${h} sa ${r} dk` : `${h} sa`;
}

function timeAgo(isoString) {
  const diff = Date.now() -
    new Date(isoString).getTime();
  const min  = Math.floor(diff / 60000);
  if (min < 1)  return 'az önce';
  if (min < 60) return `${min} dk önce`;
  const h = Math.floor(min / 60);
  if (h < 24)   return `${h} sa önce`;
  const d = Math.floor(h / 24);
  return `${d} gün önce`;
}

function esc(s) {
  // Kullanici kaynakli metin icin HTML kacisi (XSS onlemi).
  return String(s ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function getBadgeClass(tier) {
  if (!tier) return 'badge-none';
  return `badge-${tier}`;
}

function getRankIcon(rank) {
  if (rank === 1) return '🥇';
  if (rank === 2) return '🥈';
  if (rank === 3) return '🥉';
  return `#${rank}`;
}

function logout() {
  Auth.clear();
  window.location.href = '/index.html';
}

// Global'e ac
window.esc           = esc;
window.showToast     = showToast;
window.formatPoints  = formatPoints;
window.formatMinutes = formatMinutes;
window.timeAgo       = timeAgo;
window.getBadgeClass = getBadgeClass;
window.getRankIcon   = getRankIcon;
window.logout        = logout;
