/**
 * Serves ./frontend as static assets, and proxies /admin* to the FastAPI backend on Render
 * so the admin UI can live at https://northshoregardens.studio/admin
 *
 * Set API_ORIGIN in wrangler.jsonc `vars` or in the Cloudflare dashboard if the API URL changes.
 */
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === "/admin" || path.startsWith("/admin/")) {
      const api = String(env.API_ORIGIN || "https://northshore-gardens.onrender.com").replace(
        /\/$/,
        ""
      );
      const target = api + path + url.search;
      return fetch(new Request(target, request));
    }

    return env.ASSETS.fetch(request);
  },
};
