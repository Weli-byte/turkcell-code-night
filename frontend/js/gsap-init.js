/**
 * GSAP + Lenis + ScrollTrigger kurulumu
 * Referans siteler:
 *   lusion.co      — mouse reaktif elementler
 *   zentry.com     — sinematik scroll gecisler
 *   linear.app     — mukemmel tipografi + hiz
 *   bruno-simon.com — ozel cursor, immersive
 */

// ── LENIS SMOOTH SCROLL ───────────────────
let lenis;

function initLenis() {
  lenis = new Lenis({
    lerp:     0.08,
    duration: 1.2,
    smoothWheel: true,
    syncTouch: false,
  });

  gsap.ticker.add((time) => {
    lenis.raf(time * 1000);
  });

  gsap.ticker.lagSmoothing(0);

  lenis.on('scroll', ScrollTrigger.update);
  ScrollTrigger.scrollerProxy(document.body, {
    scrollTop(value) {
      return arguments.length
        ? lenis.scrollTo(value, {immediate: true})
        : window.scrollY;
    },
    getBoundingClientRect() {
      return {
        top: 0, left: 0,
        width: window.innerWidth,
        height: window.innerHeight
      };
    }
  });
}

// ── SCROLL PROGRESS BAR ───────────────────
function initScrollProgress() {
  const bar = document.getElementById(
    'scroll-progress'
  );
  if (!bar) return;

  gsap.to(bar, {
    width: '100%',
    ease: 'none',
    scrollTrigger: {
      start:  'top top',
      end:    'bottom bottom',
      scrub:  0.3,
    }
  });
}

// ── OZEL CURSOR ───────────────────────────
function initCursor() {
  const dot  = document.getElementById('cursor-dot');
  const halo = document.getElementById('cursor-halo');
  if (!dot || !halo) return;

  // Mobilde cursor kapali
  if (window.innerWidth <= 768) {
    if (dot)  dot.style.display  = 'none';
    if (halo) halo.style.display = 'none';
    return;
  }

  let mouseX = 0, mouseY = 0;
  let haloX  = 0, haloY  = 0;

  document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;

    // Nokta: direkt takip
    gsap.set(dot, { x: mouseX, y: mouseY });
  });

  // Halo: lerp ile yavas takip
  function animateHalo() {
    haloX += (mouseX - haloX) * 0.1;
    haloY += (mouseY - haloY) * 0.1;
    gsap.set(halo, { x: haloX, y: haloY });
    requestAnimationFrame(animateHalo);
  }
  animateHalo();

  // Hover efektleri
  const interactives = document.querySelectorAll(
    'a, button, .btn, .video-card, .ai-chip, .nav-links a'
  );

  interactives.forEach(el => {
    el.addEventListener('mouseenter', () => {
      document.body.classList.add('cursor-hover');
    });
    el.addEventListener('mouseleave', () => {
      document.body.classList.remove('cursor-hover');
    });
  });
}

// ── SAYFA ACILIS ANIMASYONU ───────────────
function initPageEntrance(options = {}) {
  const {
    navbar   = '.navbar',
    hero     = '.hero, .page-hero, h1',
    content  = '.page > .container > *',
    delay    = 0,
  } = options;

  const tl = gsap.timeline({ delay });

  if (document.querySelector(navbar)) {
    tl.from(navbar, {
      y: -60, opacity: 0,
      duration: 0.6,
      ease: 'power3.out'
    });
  }

  if (document.querySelector(hero)) {
    tl.from(hero, {
      y: 40, opacity: 0,
      duration: 0.8,
      ease: 'expo.out'
    }, '-=0.3');
  }

  return tl;
}

// ── SCROLL ANIMASYONLARI ──────────────────
function initScrollAnimations() {
  // Fade-in up: her .anim-fade elementi
  gsap.utils.toArray('.anim-fade').forEach(el => {
    gsap.from(el, {
      y: 50, opacity: 0,
      duration: 0.8,
      ease: 'expo.out',
      scrollTrigger: {
        trigger: el,
        start:   'top 82%',
        once:    true,
      }
    });
  });

  // Stagger: .anim-stagger parent icindeki cocuklar
  gsap.utils.toArray('.anim-stagger').forEach(parent => {
    const children = parent.children;
    gsap.from(children, {
      y: 40, opacity: 0,
      duration: 0.7,
      stagger:  0.1,
      ease: 'expo.out',
      scrollTrigger: {
        trigger: parent,
        start:   'top 80%',
        once:    true,
      }
    });
  });

  // Soldan gelen: .anim-left
  gsap.utils.toArray('.anim-left').forEach(el => {
    gsap.from(el, {
      x: -50, opacity: 0,
      duration: 0.8,
      ease: 'power3.out',
      scrollTrigger: {
        trigger: el,
        start:   'top 82%',
        once:    true,
      }
    });
  });
}

// ── COUNTUP ANIMASYONU ────────────────────
function animateCountUp(el, target, duration = 1.8) {
  const obj = { value: 0 };
  gsap.to(obj, {
    value: target,
    duration: duration,
    ease: 'power2.out',
    onUpdate: () => {
      el.textContent = Math.round(obj.value)
        .toLocaleString('tr-TR');
    },
    scrollTrigger: el ? {
      trigger: el,
      start:   'top 85%',
      once:    true,
    } : undefined,
  });
}

function initCountUps() {
  document.querySelectorAll('[data-countup]')
    .forEach(el => {
      const target = parseInt(
        el.getAttribute('data-countup'), 10
      );
      if (!isNaN(target)) {
        animateCountUp(el, target);
      }
    });
}

// ── MAGNETIK BUTON EFEKTI ────────────────
function initMagneticButtons() {
  if (window.innerWidth <= 768) return;

  document.querySelectorAll('.btn-magnetic')
    .forEach(btn => {
      btn.addEventListener('mousemove', (e) => {
        const rect = btn.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;
        gsap.to(btn, {
          x: x * 0.3, y: y * 0.3,
          duration: 0.3,
          ease: 'power2.out'
        });
      });
      btn.addEventListener('mouseleave', () => {
        gsap.to(btn, {
          x: 0, y: 0,
          duration: 0.5,
          ease: 'elastic.out(1, 0.5)'
        });
      });
    });
}

// ── NAVBAR SCROLL EFEKTI ─────────────────
function initNavbarScroll() {
  const navbar = document.querySelector('.navbar');
  if (!navbar) return;

  ScrollTrigger.create({
    start: 'top -80px',
    onEnter: () => {
      navbar.style.background =
        'rgba(5,5,8,0.95)';
    },
    onLeaveBack: () => {
      navbar.style.background =
        'rgba(5,5,8,0.85)';
    }
  });
}

// ── PUAN GUNCELLENINCE PULSE ──────────────
function pulsePoints() {
  const el = document.getElementById('nav-pts');
  if (!el) return;
  const wrap = el.closest('.nav-points');
  if (!wrap) return;
  wrap.classList.remove('pulse');
  void wrap.offsetWidth; // reflow
  wrap.classList.add('pulse');
  gsap.delayedCall(0.6, () => {
    wrap.classList.remove('pulse');
  });
}

// ── ANA INIT ─────────────────────────────
function initGSAP(pageOptions = {}) {
  gsap.registerPlugin(ScrollTrigger);
  initLenis();
  initScrollProgress();
  initCursor();
  initNavbarScroll();
  initScrollAnimations();
  initCountUps();
  initMagneticButtons();
  initPageEntrance(pageOptions);

  // ScrollTrigger refresh
  window.addEventListener('load', () => {
    ScrollTrigger.refresh();
  });
}

// Global'e ac
window.initGSAP       = initGSAP;
window.animateCountUp = animateCountUp;
window.pulsePoints    = pulsePoints;
window.lenis          = () => lenis;
