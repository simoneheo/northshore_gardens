function applySiteData() {
  if (!window.SITE_DATA) return;

  document.querySelectorAll("[data-edit]").forEach((node) => {
    const key = node.getAttribute("data-edit");
    if (!key) return;
    if (!(key in window.SITE_DATA)) return;
    node.textContent = window.SITE_DATA[key];
  });
}

window.renderHomepage = applySiteData;
