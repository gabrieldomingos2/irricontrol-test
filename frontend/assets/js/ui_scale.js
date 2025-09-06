// assets/js/ui_scale.js
(function () {
  let last = null;

  function getUiScale() {
    const v = getComputedStyle(document.documentElement)
      .getPropertyValue('--ui-scale')
      .trim();
    const n = parseFloat(v || '1');
    return Number.isFinite(n) ? n : 1;
  }

  function px(n) {
    return Math.max(1, Math.round(n * getUiScale()));
  }

  function debounce(fn, ms) {
    let t;
    return (...a) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...a), ms);
    };
  }

  function onScaleChange(cb) {
    const check = () => {
      const s = getUiScale();
      if (s !== last) {
        last = s;
        try { cb(s); } catch {}
      }
    };
    window.addEventListener('resize', debounce(check, 120));
    document.addEventListener('DOMContentLoaded', check);
    check(); // primeira chamada
  }

  window.UI_SCALE = { getUiScale, px, onScaleChange };
})();
