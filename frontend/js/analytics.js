/**
 * GA4 (gtag) + Meta Pixel. Loads only when APP_CONFIG.analytics.enabled (not on localhost).
 * Exposes window.trackNsgEvent(name, params) for custom events (always defined; no-op when disabled).
 */
(function () {
  function noop() {}

  window.trackNsgEvent = noop;

  var cfg = window.APP_CONFIG && window.APP_CONFIG.analytics;
  if (!cfg || !cfg.enabled || !cfg.ga4MeasurementId || !cfg.metaPixelId) {
    return;
  }

  var gaId = cfg.ga4MeasurementId;
  var pixelId = cfg.metaPixelId;

  window.dataLayer = window.dataLayer || [];
  function gtag() {
    window.dataLayer.push(arguments);
  }
  window.gtag = gtag;
  gtag("js", new Date());
  gtag("config", gaId);

  var gaScript = document.createElement("script");
  gaScript.async = true;
  gaScript.src =
    "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(gaId);
  document.head.appendChild(gaScript);

  !(function (f, b, e, v, n, t, s) {
    if (f.fbq) return;
    n = f.fbq = function () {
      n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
    };
    if (!f._fbq) f._fbq = n;
    n.push = n;
    n.loaded = !0;
    n.version = "2.0";
    n.queue = [];
    t = b.createElement(e);
    t.async = !0;
    t.src = v;
    s = b.getElementsByTagName(e)[0];
    s.parentNode.insertBefore(t, s);
  })(
    window,
    document,
    "script",
    "https://connect.facebook.net/en_US/fbevents.js"
  );
  window.fbq("init", pixelId);
  window.fbq("track", "PageView");

  window.trackNsgEvent = function (eventName, params) {
    if (!eventName) return;
    var p = params && typeof params === "object" ? params : {};
    gtag("event", eventName, p);
    window.fbq("trackCustom", eventName, p);
  };

  function initHomepageScroll() {
    if (!document.body || !document.body.classList.contains("homepage")) return;
    var done = false;
    function onScroll() {
      if (done) return;
      if (window.scrollY >= 100) {
        done = true;
        window.trackNsgEvent("homepage_scroll", { threshold_px: 100 });
        window.removeEventListener("scroll", onScroll);
      }
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initHomepageScroll);
  } else {
    initHomepageScroll();
  }
})();
