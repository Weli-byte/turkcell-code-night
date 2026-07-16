/**
 * Global elementler — her sayfada calisir.
 * Navbar, cursor, grain, scroll progress.
 */

// ── GLOBAL HTML PARCALARI ─────────────────

// Her sayfanin <body> basina eklenecek HTML
const GLOBAL_HTML = `
  <!-- Scroll Progress Bar -->
  <div id="scroll-progress"></div>

  <!-- Noise Grain Overlay -->
  <div id="grain"></div>

  <!-- Ozel Cursor -->
  <div id="cursor-dot"></div>
  <div id="cursor-halo"></div>

  <!-- Toast Bildirimi -->
  <div id="toast" class="toast"></div>
`;

// ── NAVBAR HTML ───────────────────────────
const NAVBAR_HTML = `
  <nav class="navbar" id="main-navbar">

    <!-- Sol: Logo -->
    <a class="nav-logo" href="/catalog.html">DGE</a>

    <!-- Orta: Linkler -->
    <div class="nav-links" id="nav-links">
      <a href="/catalog.html"
         data-page="catalog">Katalog</a>
      <a href="/panel.html"
         data-page="panel">Panelim</a>
      <a href="/leaderboard.html"
         data-page="leaderboard">Liderlik</a>
      <a href="/admin.html"
         data-page="admin"
         id="nav-admin-link"
         style="display:none">Admin</a>
    </div>

    <!-- Sag: Puan + Kullanici + Cikis -->
    <div class="nav-right">
      <div class="nav-points" id="nav-points-wrap">
        ⭐ <span id="nav-pts">–</span>
      </div>
      <span class="nav-user"
            id="nav-username">–</span>
      <button class="btn btn-danger btn-sm"
              onclick="logout()">Çıkış</button>
    </div>
  </nav>
`;

// ── GLOBAL ELEMANLARI OLUSTUR ─────────────
function injectGlobalHTML() {
  // Global HTML'i body'nin basina ekle
  document.body.insertAdjacentHTML(
    'afterbegin', GLOBAL_HTML
  );

  // Navbar'i body'nin en basina ekle
  // (scroll-progress'ten sonra)
  const grain = document.getElementById('grain');
  grain.insertAdjacentHTML('afterend', NAVBAR_HTML);
}

// ── AKTIF SAYFA LINKINI ISARETLE ─────────
function setActiveNavLink() {
  const path = window.location.pathname;
  const page = path.split('/').pop()
                   .replace('.html', '');

  document.querySelectorAll('.nav-links a')
    .forEach(a => {
      a.classList.remove('active');
      if (a.getAttribute('data-page') === page) {
        a.classList.add('active');
      }
    });
}

// ── NAVBAR'I API'DEN DOLDUR ───────────────
async function loadNavbar() {
  if (!Auth.isLoggedIn()) return;

  try {
    const me = await API.getMe();

    // Puan guncelle
    const ptsEl = document.getElementById('nav-pts');
    if (ptsEl) {
      const oldVal = parseInt(
        ptsEl.textContent, 10
      ) || 0;
      ptsEl.textContent = formatPoints(me.total_points);

      // Puan artistiysa pulse animasyonu
      if (me.total_points > oldVal && oldVal > 0) {
        pulsePoints();
      }
    }

    // Kullanici adi
    const userEl = document.getElementById(
      'nav-username'
    );
    if (userEl) userEl.textContent = me.username;

    // Admin linki
    if (me.role === 'admin') {
      const adminLink = document.getElementById(
        'nav-admin-link'
      );
      if (adminLink) {
        adminLink.style.display = '';
      }
    }

    return me;
  } catch (e) {
    console.error('Navbar yüklenemedi:', e);
  }
}

// ── NAVBAR'I PERIYODIK GUNCELLE ──────────
let navbarRefreshInterval = null;

function startNavbarRefresh(intervalMs = 30000) {
  if (navbarRefreshInterval) {
    clearInterval(navbarRefreshInterval);
  }
  navbarRefreshInterval = setInterval(
    loadNavbar,
    intervalMs
  );
}

function stopNavbarRefresh() {
  if (navbarRefreshInterval) {
    clearInterval(navbarRefreshInterval);
    navbarRefreshInterval = null;
  }
}

// ── SCROLL PROGRESS ───────────────────────
function initScrollProgressBar() {
  const bar = document.getElementById(
    'scroll-progress'
  );
  if (!bar) return;

  function updateBar() {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement
      .scrollHeight - window.innerHeight;
    const pct = docHeight > 0
      ? (scrollTop / docHeight) * 100
      : 0;
    bar.style.width = pct + '%';
  }

  window.addEventListener('scroll', updateBar,
    { passive: true });
  updateBar();
}

// ── NOISE GRAIN ───────────────────────────
function initGrain() {
  const grain = document.getElementById('grain');
  if (!grain) return;
  // CSS'te zaten tanimli, JS ile ek islem yok
  // Sadece varligini dogrula
}

// ── OZEL CURSOR ───────────────────────────
function initCustomCursor() {
  const dot  = document.getElementById('cursor-dot');
  const halo = document.getElementById('cursor-halo');
  if (!dot || !halo) return;

  // Mobilde kapali
  if (window.innerWidth <= 768) {
    dot.style.display  = 'none';
    halo.style.display = 'none';
    document.body.style.cursor = 'auto';
    return;
  }

  document.body.style.cursor = 'none';

  let mouseX = 0, mouseY = 0;
  let haloX  = 0, haloY  = 0;
  let ticking = false;

  document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;

    if (!ticking) {
      requestAnimationFrame(() => {
        // Nokta: anlik takip
        dot.style.left = mouseX + 'px';
        dot.style.top  = mouseY + 'px';
        ticking = false;
      });
      ticking = true;
    }
  });

  // Halo: lerp ile yavas takip
  function animateHalo() {
    haloX += (mouseX - haloX) * 0.1;
    haloY += (mouseY - haloY) * 0.1;
    halo.style.left = haloX + 'px';
    halo.style.top  = haloY + 'px';
    requestAnimationFrame(animateHalo);
  }
  animateHalo();

  // Hover: link ve buton uzerinde buyu
  function addHoverListeners() {
    document.querySelectorAll(
      'a, button, .btn, .video-card, ' +
      '.ai-chip, .challenge-card, ' +
      '.nav-links a'
    ).forEach(el => {
      el.addEventListener('mouseenter', () => {
        document.body.classList.add('cursor-hover');
      });
      el.addEventListener('mouseleave', () => {
        document.body.classList.remove('cursor-hover');
      });
    });
  }

  addHoverListeners();

  // DOM degisince yeniden listener ekle
  const observer = new MutationObserver(
    addHoverListeners
  );
  observer.observe(document.body, {
    childList: true,
    subtree:   true
  });

  // Sayfa disina cikinca gizle
  document.addEventListener('mouseleave', () => {
    dot.style.opacity  = '0';
    halo.style.opacity = '0';
  });
  document.addEventListener('mouseenter', () => {
    dot.style.opacity  = '1';
    halo.style.opacity = '1';
  });
}

// ── SAYFA KORUMASI ────────────────────────
function requireAuth() {
  if (!Auth.isLoggedIn()) {
    window.location.href = '/index.html';
    return false;
  }
  return true;
}

function requireAdmin() {
  if (Auth.getRole() !== 'admin') {
    window.location.href = '/catalog.html';
    return false;
  }
  return true;
}

// ── ANA INIT ─────────────────────────────
async function initGlobalElements(options = {}) {
  const {
    requireLogin = true,
    requireAdminRole = false,
    navbarRefresh = true,
    refreshInterval = 30000,
  } = options;

  // Auth kontrol
  if (requireLogin && !requireAuth()) return;
  if (requireAdminRole && !requireAdmin()) return;

  // Global HTML enjekte et
  injectGlobalHTML();

  // Aktif link
  setActiveNavLink();

  // Scroll progress (CSS ile destekli)
  initScrollProgressBar();

  // Grain efekti
  initGrain();

  // Ozel cursor
  initCustomCursor();

  // Navbar'i API'den doldur
  const me = await loadNavbar();

  // Periyodik guncelleme
  if (navbarRefresh) {
    startNavbarRefresh(refreshInterval);
  }

  // GSAP varsa baslat
  if (typeof initGSAP === 'function') {
    initGSAP(options.gsap || {});
  }

  return me;
}

// Global'e ac
window.initGlobalElements = initGlobalElements;
window.loadNavbar         = loadNavbar;
window.requireAuth        = requireAuth;
window.requireAdmin       = requireAdmin;
window.startNavbarRefresh = startNavbarRefresh;
window.stopNavbarRefresh  = stopNavbarRefresh;
window.setActiveNavLink   = setActiveNavLink;
