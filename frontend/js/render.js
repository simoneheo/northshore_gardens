function applySiteData() {
  if (!window.SITE_DATA) return;

  document.querySelectorAll("[data-edit]").forEach((node) => {
    const key = node.getAttribute("data-edit");
    if (!key) return;
    if (!(key in window.SITE_DATA)) return;
    node.textContent = window.SITE_DATA[key];
  });

  renderGalleryFromSiteData();
}

const GALLERY_VISIBLE_COUNT = 3;

function createGalleryArticle(item, delayIdx) {
  const article = document.createElement("article");
  let revealClass = "gallery-card reveal";
  if (delayIdx === 1) revealClass += " reveal-delay-1";
  else if (delayIdx >= 2) revealClass += " reveal-delay-2";
  article.className = revealClass;

  const images = document.createElement("div");
  images.className = "gallery-images split-2";

  const figBefore = document.createElement("figure");
  const imgBefore = document.createElement("img");
  imgBefore.src = item.beforeSrc || "";
  imgBefore.alt = typeof item.beforeAlt === "string" ? item.beforeAlt : "Before";
  imgBefore.decoding = "async";
  const capBefore = document.createElement("figcaption");
  capBefore.textContent =
    typeof item.beforeLabel === "string" ? item.beforeLabel : "Before";
  figBefore.append(imgBefore, capBefore);

  const figAfter = document.createElement("figure");
  const imgAfter = document.createElement("img");
  imgAfter.src = item.afterSrc || "";
  imgAfter.alt = typeof item.afterAlt === "string" ? item.afterAlt : "After";
  imgAfter.decoding = "async";
  const capAfter = document.createElement("figcaption");
  capAfter.textContent = typeof item.afterLabel === "string" ? item.afterLabel : "After";
  figAfter.append(imgAfter, capAfter);

  images.append(figBefore, figAfter);

  const copy = document.createElement("div");
  copy.className = "gallery-copy";
  const tagsWrap = document.createElement("div");
  tagsWrap.className = "gallery-tags";
  tagsWrap.setAttribute("aria-label", "Project tags");
  const tagList = Array.isArray(item.tags) ? item.tags : [];
  tagList.forEach((t) => {
    if (typeof t !== "string" || !t.trim()) return;
    const span = document.createElement("span");
    span.className = "gallery-tag";
    span.textContent = t.trim();
    tagsWrap.appendChild(span);
  });
  copy.appendChild(tagsWrap);

  article.append(copy, images);
  return article;
}

function wireGalleryMoreToggle() {
  const wrap = document.getElementById("galleryMore");
  const btn = document.getElementById("galleryMoreToggle");
  const moreGrid = document.getElementById("galleryGridMore");
  if (!wrap || !btn || !moreGrid) return;

  function setExpanded(expanded) {
    btn.setAttribute("aria-expanded", expanded ? "true" : "false");
    moreGrid.hidden = !expanded;
    btn.textContent = expanded ? "Show less" : "Show more";
  }

  setExpanded(false);
  btn.onclick = () => {
    const nextExpanded = btn.getAttribute("aria-expanded") !== "true";
    setExpanded(nextExpanded);
    if (
      nextExpanded &&
      typeof window.trackNsgEvent === "function"
    ) {
      window.trackNsgEvent("gallery_show_more", { section: "gallery" });
    }
  };
}

function renderGalleryFromSiteData() {
  const grid = document.getElementById("galleryGrid");
  const moreWrap = document.getElementById("galleryMore");
  const moreGrid = document.getElementById("galleryGridMore");
  if (!grid || !window.SITE_DATA) return;
  const items = window.SITE_DATA.galleryItems;
  if (!Array.isArray(items) || items.length === 0) {
    grid.replaceChildren();
    if (moreGrid) moreGrid.replaceChildren();
    if (moreWrap) moreWrap.hidden = true;
    return;
  }

  grid.replaceChildren();
  if (moreGrid) moreGrid.replaceChildren();

  const first = items.slice(0, GALLERY_VISIBLE_COUNT);
  const rest = items.slice(GALLERY_VISIBLE_COUNT);

  first.forEach((item, idx) => {
    grid.appendChild(createGalleryArticle(item, idx));
  });

  if (moreWrap && moreGrid) {
    if (rest.length === 0) {
      moreWrap.hidden = true;
    } else {
      moreWrap.hidden = false;
      rest.forEach((item, idx) => {
        moreGrid.appendChild(createGalleryArticle(item, idx));
      });
      wireGalleryMoreToggle();
    }
  }
}

window.renderHomepage = applySiteData;
