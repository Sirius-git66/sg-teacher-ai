/* Shared site behaviors — mobile nav, mascot mounting, scroll. */
(function () {
  'use strict';

  function init() {
    initNav();
    initMascot();
  }

  /* --- Mobile navigation toggle ----------------------------------------- */
  function initNav() {
    var toggle = document.querySelector('.nav-toggle');
    var nav = document.querySelector('.site-nav');
    if (!toggle || !nav) return;

    toggle.addEventListener('click', function () {
      nav.classList.toggle('open');
    });

    // Close nav when clicking outside
    document.addEventListener('click', function (e) {
      if (!nav.contains(e.target) && !toggle.contains(e.target)) {
        nav.classList.remove('open');
      }
    });
  }

  /* --- Mascot rendering -------------------------------------------------- */
  function initMascot() {
    var canvas = document.getElementById('mascot-canvas');
    if (!canvas || !window.TeacherDither) return;

    var instance = window.TeacherDither.mount(canvas);
    if (!instance) return;

    // Speech bubble — cycle through messages
    var bubble = document.getElementById('mascot-speech');
    if (!bubble) return;

    var messages = [
      'Every claim here is sourced.',
      'Click a citation to verify it.',
      'Build fails when facts go stale.',
      'Not affiliated with MOE.',
      'Check before you assign.'
    ];

    var idx = 0;
    var reduced = window.matchMedia
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false;

    if (!reduced) {
      setInterval(function () {
        idx = (idx + 1) % messages.length;
        bubble.textContent = messages[idx];
      }, 5000);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
