/**
 * Lead intent / source tracking for intake (silent; not shown in UI).
 * Persists via query string + sessionStorage for resilience across navigation.
 */

(function () {
  const STORAGE_ENTRY = "nsg_lead_entry_intent";
  const STORAGE_SOURCE = "nsg_lead_source_page";

  const ALLOWED_ENTRY_INTENTS = new Set(["quick_ideas", "get_started", "unknown"]);
  const ALLOWED_SOURCE_PAGES = new Set([
    "hero",
    "gallery",
    "how_it_works",
    "packages",
    "final_cta",
    "header",
    "mobile_menu",
    "plans_page",
    "unknown",
  ]);

  function normalizeEntryIntent(value) {
    const v = String(value || "")
      .trim()
      .toLowerCase();
    if (ALLOWED_ENTRY_INTENTS.has(v)) return v;
    return "unknown";
  }

  function normalizeSourcePage(value) {
    const v = String(value || "")
      .trim()
      .toLowerCase();
    if (ALLOWED_SOURCE_PAGES.has(v)) return v;
    return "unknown";
  }

  /**
   * Validate and persist lead intent + source to sessionStorage.
   * @param {string} entryIntent
   * @param {string} sourcePage
   */
  function setLeadIntent(entryIntent, sourcePage) {
    const ei = normalizeEntryIntent(entryIntent);
    const sp = normalizeSourcePage(sourcePage);
    try {
      sessionStorage.setItem(STORAGE_ENTRY, ei);
      sessionStorage.setItem(STORAGE_SOURCE, sp);
    } catch (_e) {
      /* ignore quota / private mode */
    }
  }

  /**
   * Read lead intent: URL query params first, then sessionStorage, else unknown.
   * When URL provides either param, missing side falls back to stored value or unknown.
   * @returns {{ entry_intent: string, source_page: string }}
   */
  function getLeadIntent() {
    let params;
    try {
      params = new URLSearchParams(window.location.search || "");
    } catch (_e) {
      params = new URLSearchParams();
    }

    const rawEi = params.get("entry_intent");
    const rawSp = params.get("source_page");
    let fromUrl = false;
    if (rawEi !== null || rawSp !== null) {
      fromUrl = true;
    }

    let sessionEi = "unknown";
    let sessionSp = "unknown";
    try {
      sessionEi = sessionStorage.getItem(STORAGE_ENTRY) || "unknown";
      sessionSp = sessionStorage.getItem(STORAGE_SOURCE) || "unknown";
    } catch (_e) {
      /* ignore */
    }

    if (fromUrl) {
      const entryIntent = normalizeEntryIntent(
        rawEi !== null && rawEi !== "" ? rawEi : sessionEi
      );
      const sourcePage = normalizeSourcePage(
        rawSp !== null && rawSp !== "" ? rawSp : sessionSp
      );
      setLeadIntent(entryIntent, sourcePage);
      return { entry_intent: entryIntent, source_page: sourcePage };
    }

    if (sessionEi !== "unknown" || sessionSp !== "unknown") {
      return {
        entry_intent: normalizeEntryIntent(sessionEi),
        source_page: normalizeSourcePage(sessionSp),
      };
    }

    return { entry_intent: "unknown", source_page: "unknown" };
  }

  function clearLeadIntent() {
    try {
      sessionStorage.removeItem(STORAGE_ENTRY);
      sessionStorage.removeItem(STORAGE_SOURCE);
    } catch (_e) {
      /* ignore */
    }
  }

  /**
   * Store intent, build intake URL with query params, navigate.
   * For a future modal intake on the homepage: call setLeadIntent() then open the modal instead of assign().
   * @param {string} entryIntent
   * @param {string} sourcePage
   * @param {string} [href] — default ./intake.html (relative to current page)
   */
  function openIntakeWithIntent(entryIntent, sourcePage, href) {
    const ei = normalizeEntryIntent(entryIntent);
    const sp = normalizeSourcePage(sourcePage);
    setLeadIntent(ei, sp);
    const base = href && href.trim() ? href.trim() : "./intake.html";
    const u = new URL(base, window.location.href);
    u.searchParams.set("entry_intent", ei);
    u.searchParams.set("source_page", sp);
    window.location.assign(u.toString());
  }

  window.NSGLeadIntent = {
    normalizeEntryIntent,
    normalizeSourcePage,
    setLeadIntent,
    getLeadIntent,
    clearLeadIntent,
    openIntakeWithIntent,
  };
  window.openIntakeWithIntent = openIntakeWithIntent;
})();
