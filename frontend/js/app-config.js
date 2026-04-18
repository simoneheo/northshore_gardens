const isLocal =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1";

window.APP_CONFIG = {
  apiBase: isLocal
    ? "http://localhost:8001"
    : "https://northshore-gardens.onrender.com",
};
