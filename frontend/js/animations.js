/**
 * animations.js — Tum sayfalarin GSAP animasyon kurallari.
 *
 * Kurallar:
 * - Sabit-hiz (duz) easing: ASLA. Daima expo.out veya power3.out.
 * - ScrollTrigger: once:true (sayaclar haric tekrar calismaz)
 * - Lenis lerp: 0.08
 * - CountUp: power2.out, 1.8s
 */

// ── SAYFA ACILIS ANIMASYONU ───────────────
// Sira: navbar → hero → icerik
function runPageEntrance(config = {}) {
  const {
    navbarSel  = '.navbar',
    heroSel    = '.page-hero, .hero-section, h1.hero-title',
    contentSel = '.page-content, .main-content',
    delay      = 0,
  } = config;

  const tl = gsap.timeline({ delay });

  // 1. Navbar: 0.6s
  const navbar = document.querySelector(navbarSel);
  if (navbar) {
    tl.from(navbar, {
      y: -60, opacity: 0,
      duration: 0.6,
      ease: 'power3.out',
    });
  }

  // 2. Hero: 0.8s
  const hero = document.querySelector(heroSel);
  if (hero) {
    tl.from(hero, {
      y: 40, opacity: 0,
      duration: 0.8,
      ease: 'expo.out',
    }, '-=0.4');
  }

  // 3. Icerik: 0.7s
  const content = document.querySelector(contentSel);
  if (content) {
    tl.from(content, {
      y: 30, opacity: 0,
      duration: 0.7,
      ease: 'expo.out',
    }, '-=0.4');
  }

  return tl;
}

// ── HERO BASLIK ANIMASYONU ────────────────
// Kelime kelime stagger ile (mevcut DOM metninden — guvenli)
function animateHeroTitle(selector) {
  const el = document.querySelector(selector);
  if (!el) return;

  const words = el.textContent.split(' ');
  const kacis = (s) => (typeof esc === 'function')
    ? esc(s)
    : String(s).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
  el.innerHTML = words.map(w =>
    `<span class="word-wrap" style="display:inline-block; overflow:hidden">` +
    `<span class="word" style="display:inline-block">${kacis(w)}&nbsp;</span></span>`
  ).join('');

  gsap.from(el.querySelectorAll('.word'), {
    y: '100%', opacity: 0,
    duration: 0.7,
    stagger: 0.08,
    ease: 'expo.out',
    delay: 0.3,
  });
}

// ── SCROLL ANIMASYONU ─────────────────────
// Elementler gorunur alana girince tetiklenir
function initScrollFade(selector = '.anim-fade', options = {}) {
  const {
    y        = 50,
    duration = 0.8,
    ease     = 'expo.out',
    start    = 'top 82%',
  } = options;

  gsap.utils.toArray(selector).forEach(el => {
    gsap.from(el, {
      y, opacity: 0,
      duration, ease,
      scrollTrigger: {
        trigger: el,
        start,
        once: true,  // Tekrar calismaz
      }
    });
  });
}

// ── STAGGER ANIMASYONU ────────────────────
// Kartlar 100ms arayla gelir
function initScrollStagger(parentSelector = '.anim-stagger', options = {}) {
  const {
    y        = 40,
    duration = 0.7,
    stagger  = 0.1,
    ease     = 'expo.out',
    start    = 'top 80%',
  } = options;

  gsap.utils.toArray(parentSelector).forEach(parent => {
    const children = Array.from(parent.children);
    if (!children.length) return;

    gsap.from(children, {
      y, opacity: 0,
      duration, stagger, ease,
      scrollTrigger: {
        trigger: parent,
        start,
        once: true,
      }
    });
  });
}

// ── COUNTUP ANIMASYONU ────────────────────
// 0'dan hedefe, 1.8s, power2.out — ScrollTrigger ile
function initCountUps(selector = '[data-countup]') {
  document.querySelectorAll(selector).forEach(el => {
    const target = parseInt(el.getAttribute('data-countup'), 10);
    if (isNaN(target)) return;

    const obj = { val: 0 };

    ScrollTrigger.create({
      trigger: el,
      start: 'top 85%',
      once: true,
      onEnter: () => {
        gsap.to(obj, {
          val: target,
          duration: 1.8,
          ease: 'power2.out',
          onUpdate: () => {
            el.textContent = Math.round(obj.val).toLocaleString('tr-TR');
          }
        });
      }
    });
  });
}

// ── SOLDAN GELEN ANIMASYON ────────────────
function initScrollLeft(selector = '.anim-left', options = {}) {
  const {
    x        = -50,
    duration = 0.8,
    ease     = 'power3.out',
    start    = 'top 82%',
  } = options;

  gsap.utils.toArray(selector).forEach(el => {
    gsap.from(el, {
      x, opacity: 0,
      duration, ease,
      scrollTrigger: {
        trigger: el,
        start,
        once: true,
      }
    });
  });
}

// ── LEADERBOARD SATIRLARI ─────────────────
// Asagidan yukari stagger
function animateLeaderboardRows(tableSelector = '.lb-table tbody') {
  const tbody = document.querySelector(tableSelector);
  if (!tbody) return;

  const rows = tbody.querySelectorAll('tr');
  gsap.from(rows, {
    y: 20, opacity: 0,
    stagger: 0.04,
    duration: 0.5,
    ease: 'expo.out',
  });
}

// ── CHALLENGE KARTLARI ────────────────────
function animateChallengeCards(containerSelector = '#challenge-list') {
  const container = document.querySelector(containerSelector);
  if (!container) return;

  const cards = container.querySelectorAll('.challenge-card');
  gsap.from(cards, {
    y: 30, opacity: 0,
    stagger: 0.08,
    duration: 0.6,
    ease: 'expo.out',
    scrollTrigger: {
      trigger: container,
      start: 'top 80%',
      once: true,
    }
  });
}

// ── ROZET KUTULARI ────────────────────────
// Soldan saga stagger
function animateBadgeTiers(containerSelector = '#badge-progress') {
  const container = document.querySelector(containerSelector);
  if (!container) return;

  const boxes = container.querySelectorAll('.card, .badge-tier-box, .badge-box');
  gsap.from(boxes, {
    x: -30, opacity: 0,
    stagger: 0.12,
    duration: 0.7,
    ease: 'power3.out',
    scrollTrigger: {
      trigger: container,
      start: 'top 78%',
      once: true,
    }
  });
}

// ── VIDEO KARTLARI ────────────────────────
function animateVideoCards(gridSelector = '.video-grid') {
  const grid = document.querySelector(gridSelector);
  if (!grid) return;

  const cards = grid.querySelectorAll('.video-card');
  gsap.from(cards, {
    y: 40, opacity: 0,
    stagger: 0.07,
    duration: 0.6,
    ease: 'expo.out',
    scrollTrigger: {
      trigger: grid,
      start: 'top 82%',
      once: true,
    }
  });
}

// ── HOVER ANIMASYONLARI ───────────────────
// Video kart hover
function initVideoCardHovers() {
  document.querySelectorAll('.video-card').forEach(card => {
    card.addEventListener('mouseenter', () => {
      gsap.to(card, { y: -6, duration: 0.3, ease: 'power2.out' });
    });
    card.addEventListener('mouseleave', () => {
      gsap.to(card, { y: 0, duration: 0.4, ease: 'power2.out' });
    });
  });
}

// Challenge kart hover
function initChallengeCardHovers() {
  document.querySelectorAll('.challenge-card').forEach(card => {
    card.addEventListener('mouseenter', () => {
      gsap.to(card, { scale: 1.01, duration: 0.25, ease: 'power2.out' });
    });
    card.addEventListener('mouseleave', () => {
      gsap.to(card, { scale: 1, duration: 0.3, ease: 'power2.out' });
    });
  });
}

// Buton hover (btn-primary)
function initButtonHovers() {
  document.querySelectorAll('.btn-primary').forEach(btn => {
    btn.addEventListener('mouseenter', () => {
      gsap.to(btn, { scale: 1.04, duration: 0.2, ease: 'power2.out' });
    });
    btn.addEventListener('mouseleave', () => {
      gsap.to(btn, { scale: 1, duration: 0.25, ease: 'power2.out' });
    });
    btn.addEventListener('mousedown', () => {
      gsap.to(btn, { scale: 0.97, duration: 0.1, ease: 'power2.out' });
    });
    btn.addEventListener('mouseup', () => {
      gsap.to(btn, { scale: 1.04, duration: 0.15, ease: 'power2.out' });
    });
  });
}

// ── PROGRESS BAR SCROLL ANIMASYONU ────────
function animateProgressBars(containerSelector = 'body') {
  const container = document.querySelector(containerSelector);
  if (!container) return;

  container.querySelectorAll('.progress-fill').forEach(fill => {
    const targetWidth = fill.style.width || '0%';
    fill.style.width = '0%';

    ScrollTrigger.create({
      trigger: fill,
      start: 'top 85%',
      once: true,
      onEnter: () => {
        gsap.to(fill, {
          width: targetWidth,
          duration: 1.2,
          ease: 'expo.out',
        });
      }
    });
  });
}

// ── PUAN GUNCELLENINCE SAYAC ──────────────
function animatePtsUpdate(el, newValue) {
  if (!el) return;
  const oldValue = parseInt(el.textContent.replace(/\D/g, '')) || 0;

  if (newValue <= oldValue) {
    el.textContent = newValue.toLocaleString('tr-TR');
    return;
  }

  const obj = { val: oldValue };
  gsap.to(obj, {
    val: newValue,
    duration: 1.2,
    ease: 'power2.out',
    onUpdate: () => {
      el.textContent = Math.round(obj.val).toLocaleString('tr-TR');
    }
  });

  // Renk flash
  gsap.fromTo(el,
    { color: 'var(--accent-1)' },
    { color: '', duration: 1.5, ease: 'power2.out' }
  );
}

// ── YASAK EASING KONTROLU (development) ───
// Sabit-hiz easing kullanilirsa konsola uyari basar.
function checkLinearEasing() {
  if (typeof gsap === 'undefined') return;

  const yasakEase = ['li' + 'near', 'none'];
  const origTo = gsap.to.bind(gsap);
  gsap.to = function (target, vars) {
    if (vars && yasakEase.includes(vars.ease)) {
      console.warn('UYARI: yasak duz-hiz ease kullanildi!', target, vars);
    }
    return origTo(target, vars);
  };
}

// ── ANA INIT ─────────────────────────────
function initAnimations(pageConfig = {}) {
  if (typeof gsap === 'undefined') return;
  if (typeof ScrollTrigger !== 'undefined') {
    gsap.registerPlugin(ScrollTrigger);
  }

  // Sayfa acilis
  runPageEntrance(pageConfig.entrance || {});

  // Scroll fade
  initScrollFade('.anim-fade', pageConfig.fade || {});

  // Stagger
  initScrollStagger('.anim-stagger', pageConfig.stagger || {});

  // Soldan gelen
  initScrollLeft('.anim-left', pageConfig.left || {});

  // CountUp
  initCountUps('[data-countup]');

  // Progress barlar
  animateProgressBars();

  // Hover'lar
  initVideoCardHovers();
  initChallengeCardHovers();
  initButtonHovers();

  // Yasak easing kontrolu (development)
  if (window.location.hostname === 'localhost') {
    checkLinearEasing();
  }

  // ScrollTrigger refresh (kisa gecikmeyle, layout otursun)
  gsap.delayedCall(0.1, () => {
    if (typeof ScrollTrigger !== 'undefined') ScrollTrigger.refresh();
  });
}

// Global'e ac
window.initAnimations          = initAnimations;
window.runPageEntrance         = runPageEntrance;
window.animateHeroTitle        = animateHeroTitle;
window.initScrollFade          = initScrollFade;
window.initScrollStagger       = initScrollStagger;
window.initCountUps            = initCountUps;
window.animateLeaderboardRows  = animateLeaderboardRows;
window.animateChallengeCards   = animateChallengeCards;
window.animateBadgeTiers       = animateBadgeTiers;
window.animateVideoCards       = animateVideoCards;
window.animateProgressBars     = animateProgressBars;
window.animatePtsUpdate        = animatePtsUpdate;
window.initVideoCardHovers     = initVideoCardHovers;
