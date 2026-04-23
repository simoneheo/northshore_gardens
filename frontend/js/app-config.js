const isLocal =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1";

/** Public client-side IDs (same property as northshoregardens.studio). */
const GA4_MEASUREMENT_ID = "G-53J5YXQ6WL";
const META_PIXEL_ID = "1473776911057697";

window.APP_CONFIG = {
  apiBase: isLocal
    ? "http://localhost:8001"
    : "https://northshore-gardens.onrender.com",
  analytics: {
    enabled: !isLocal,
    ga4MeasurementId: GA4_MEASUREMENT_ID,
    metaPixelId: META_PIXEL_ID,
  },
};
