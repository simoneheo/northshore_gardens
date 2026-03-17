(function () {
  const data = window.SITE_DATA;
  if (!data) return;

  function esc(value) {
    return String(value ?? "");
  }

  function hasText(value) {
    return typeof value === "string" && value.trim() !== "";
  }

  function formatPrice(value) {
    return "$" + Number(value).toFixed(2);
  }

  function renderLogo(container) {
    if (!container) return;
    const main = esc(data.company?.logoText?.main || "");
    const accent = esc(data.company?.logoText?.accent || "");
    container.innerHTML = `${main} <span>${accent}</span>`;
  }

  function imageOrPlaceholder(src, alt, kind) {
    if (src) {
      return `<img src="${esc(src)}" alt="${esc(alt)}">`;
    }

    const cls =
      kind === "before"
        ? "gallery-ph gallery-ph--before"
        : "gallery-ph gallery-ph--after";

    const label = kind === "before" ? "Before" : "After";

    return `
      <div class="${cls}">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.5"/>
          <circle cx="9" cy="11" r="2.5" stroke="currentColor" stroke-width="1.5"/>
          <path d="M3 17l5-5 3.5 3.5L15 12l6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>${label}</span>
      </div>
    `;
  }

  function sliderImageOrPlaceholder(src, alt, kind) {
    if (src) {
      return `<img src="${esc(src)}" alt="${esc(alt)}">`;
    }

    const cls =
      kind === "before" ? "slider-ph slider-ph-before" : "slider-ph slider-ph-after";

    const label = kind === "before" ? "Before" : "After — Proposed Design";

    return `<div class="${cls}"><span>${label}</span></div>`;
  }

  function renderBrand() {
    renderLogo(document.getElementById("navLogo"));
    renderLogo(document.getElementById("footerLogo"));

    const footerTagline = document.getElementById("footerTagline");
    const footerEmail = document.getElementById("footerEmail");
    const footerCopy = document.getElementById("footerCopy");

    if (footerTagline) footerTagline.textContent = data.company?.tagline || "";
    if (footerEmail) footerEmail.textContent = data.company?.email || "";
    if (footerCopy) footerCopy.textContent = data.footer?.copyright || "";

    document.title = data.company?.name || "Site";
  }

  function renderHome() {
    const mount = document.getElementById("homeMount");
    if (!mount) return;

    const homeMini =
      data.home?.miniHowItWorks ||
      data.miniHowItWorks ||
      { eyebrow: "", title: "", subtext: "", steps: [] };

    const primaryCta = data.hero?.primaryCta || { label: "View Package", section: "packages" };
    const secondaryCta = data.hero?.secondaryCta || { label: "See Our Work", section: "gallery" };

    const badges = (data.hero?.badges || [])
      .map(
        (badge) => `
          <div class="badge">
            <div class="badge-dot"></div>
            ${esc(badge)}
          </div>
        `
      )
      .join("");

    const steps = (homeMini.steps || [])
      .map(
        (step) => `
          <div class="home-step">
            <div class="home-step-circle">${esc(step.number)}</div>
            <h3>${esc(step.title)}</h3>
            <p>${esc(step.body)}</p>
            ${hasText(step.tag) ? `<div class="home-step-tag">${esc(step.tag)}</div>` : ""}
          </div>
        `
      )
      .join("");

    mount.innerHTML = `
      <div class="hero">
        <div class="hero-content">
          <div class="hero-eyebrow">${esc(data.hero?.eyebrow || "")}</div>
          <h1 class="hero-title">${data.hero?.titleHtml || ""}</h1>
          <p class="hero-sub">${esc(data.hero?.subtext || "")}</p>

          <div class="hero-btns">
            <button class="btn-primary" onclick="showSection('${esc(primaryCta.section || "packages")}')">
              ${esc(primaryCta.label || "View Package")}
            </button>
            <button class="btn-secondary" onclick="showSection('${esc(secondaryCta.section || "gallery")}')">
              ${esc(secondaryCta.label || "See Our Work")}
            </button>
          </div>

          <div class="hero-badges">${badges}</div>
        </div>

        <div class="hero-visual">
          <div class="slider-wrap" id="heroSlider">
            <div class="slider-after">
              ${sliderImageOrPlaceholder(
                data.slider?.afterImage,
                data.slider?.afterAlt || "After",
                "after"
              )}
            </div>

            <div class="slider-before" id="sliderBefore">
              ${sliderImageOrPlaceholder(
                data.slider?.beforeImage,
                data.slider?.beforeAlt || "Before",
                "before"
              )}
            </div>

            <div class="slider-divider" id="sliderDivider"></div>
            <div class="slider-handle" id="sliderHandle">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M5 4L1 8l4 4M11 4l4 4-4 4" stroke="#5A6B4A" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>

            <div class="slider-label label-before">${esc(data.slider?.beforeLabel || "Before")}</div>
            <div class="slider-label label-after">${esc(data.slider?.afterLabel || "After")}</div>
          </div>
        </div>
      </div>

      <section class="mini-hiw mini-hiw--exact">
        <div class="mini-hiw-inner">
          <div class="section-eyebrow">${esc(homeMini.eyebrow || "")}</div>
          <h2 class="section-title mini-hiw-title">${esc(homeMini.title || "")}</h2>
          <p class="section-sub mini-hiw-sub">${esc(homeMini.subtext || "")}</p>

          <div class="home-steps-wrap">
            <div class="home-steps-line" aria-hidden="true"></div>
            <div class="home-steps-grid">
              ${steps}
            </div>
          </div>
        </div>
      </section>
    `;
  }

  function renderPackages() {
    const mount = document.getElementById("packagesMount");
    if (!mount) return;

    const lots = data.packages?.lots || [];
    const defaultLot = lots[0] || null;

    const deliverables = (data.packages?.deliverables || [])
      .map(
        (item) => `
          <div class="pkg-del">
            <span class="check">✓</span>
            ${esc(item)}
          </div>
        `
      )
      .join("");

    const lotButtons = lots
      .map(
        (lot, index) => `
          <div
            class="lot-btn ${index === 0 ? "selected" : ""}"
            id="lot-${esc(lot.id)}"
            onclick="selectLot('${esc(lot.id)}')"
          >
            <span class="lot-btn-size">${esc(lot.label)}</span>
            <span class="lot-btn-desc">${esc(lot.desc)}</span>

            <div class="lot-pricing">
              <span class="lot-price">${formatPrice(lot.price)}</span>
              ${lot.originalPrice != null ? `<span class="lot-orig">${formatPrice(lot.originalPrice)}</span>` : ""}
              ${hasText(lot.badge) ? `<span class="lot-save">${esc(lot.badge)}</span>` : ""}
            </div>
          </div>
        `
      )
      .join("");

    mount.innerHTML = `
      <div class="pkg-section">
        <div class="section-eyebrow">${esc(data.packages?.eyebrow || "")}</div>
        <h2 class="section-title">${esc(data.packages?.title || "")}</h2>

        <div class="pkg-card">
          <div class="pkg-label">${esc(data.packages?.label || "")}</div>
          <div class="pkg-name">${esc(data.packages?.name || "")}</div>
          <p class="pkg-tagline">${esc(data.packages?.tagline || "")}</p>

          <hr class="pkg-divider">

          <div class="pkg-includes-label">${esc(data.packages?.includesLabel || "")}</div>
          <div class="pkg-deliverables">${deliverables}</div>

          <hr class="pkg-divider">

          <div class="lot-label">Select your lot size</div>
          <div class="lot-options">${lotButtons}</div>

          ${hasText(data.packages?.noteHtml) ? `<p class="pkg-note">${data.packages.noteHtml}</p>` : ""}

          <div class="checkout-fields">
            <div class="checkout-row">
              <label for="customerName">Full name</label>
              <input id="customerName" type="text" autocomplete="name" placeholder="Your full name">
            </div>

            <div class="checkout-row">
              <label for="customerEmail">Email</label>
              <input id="customerEmail" type="email" autocomplete="email" placeholder="you@example.com">
            </div>

            <div class="checkout-row">
              <label for="customerPhone">Phone</label>
              <input id="customerPhone" type="tel" autocomplete="tel" placeholder="(555) 555-5555">
            </div>
          </div>

          <button class="add-cart" id="cartBtn" onclick="handleCart()">
            Secure Checkout — ${defaultLot ? formatPrice(defaultLot.price) : "$0.00"}
          </button>

          ${hasText(data.packages?.cartNoteHtml) ? `<p class="cart-note">${data.packages.cartNoteHtml}</p>` : ""}
        </div>
      </div>
    `;

    window.PACKAGE_DATA = Object.fromEntries(
      lots.map((lot) => [lot.id, lot])
    );
  }

  function renderHIW() {
    const mount = document.getElementById("hiwMount");
    if (!mount) return;

    const hiw = data.howItWorks || {
      eyebrow: "The Process",
      title: "How It Works",
      subtext: "",
      steps: []
    };

    const renderChecklistItem = (item) => {
      const mark = item.kind === "optional" ? "○" : "✓";
      const noteHtml = hasText(item.note) ? ` <em>(${esc(item.note)})</em>` : "";

      return `
        <li class="timeline-check-item ${item.kind === "optional" ? "is-optional" : "is-included"}">
          <span class="timeline-check-mark">${mark}</span>
          <span class="timeline-check-copy">${esc(item.text || "")}${noteHtml}</span>
        </li>
      `;
    };

    const stepsHtml = (hiw.steps || [])
      .map((step, index) => {
        const checklistHtml = (step.checklist || []).length
          ? `
            <ul class="timeline-checklist">
              ${(step.checklist || []).map(renderChecklistItem).join("")}
            </ul>
          `
          : "";

        const introHtml = hasText(step.intro)
          ? `<p class="timeline-intro">${esc(step.intro)}</p>`
          : "";

        const bodyHtml = hasText(step.body)
          ? `<p class="timeline-copy">${esc(step.body)}</p>`
          : "";

        const calloutHtml = step.callout
          ? `
            <div class="timeline-callout">
              ${hasText(step.callout.strong) ? `<div class="timeline-callout-strong">${esc(step.callout.strong)}</div>` : ""}
              ${hasText(step.callout.subtext) ? `<div class="timeline-callout-subtext">${esc(step.callout.subtext)}</div>` : ""}
            </div>
          `
          : "";

        const isLast = index === hiw.steps.length - 1;

        return `
          <div class="timeline-item ${isLast ? "timeline-item--last" : ""}">
            <div class="timeline-dot ${isLast ? "timeline-dot--earth" : ""}">
              ${esc(step.number || String(index + 1))}
            </div>

            <div class="timeline-body">
              <h3>${esc(step.title || "")}</h3>
              ${introHtml}
              ${bodyHtml}
              ${checklistHtml}
              ${calloutHtml}
            </div>
          </div>
        `;
      })
      .join("");

    mount.innerHTML = `
      <section class="hiw-section">
        <div class="hiw-header">
          <div class="section-eyebrow">${esc(hiw.eyebrow || "The Process")}</div>
          <h2 class="section-title hiw-title">${esc(hiw.title || "How It Works")}</h2>
          <p class="section-sub hiw-sub">${esc(hiw.subtext || "")}</p>
        </div>

        <div class="hiw-timeline">
          ${stepsHtml}
        </div>
      </section>
    `;
  }

  function renderGallery() {
    const mount = document.getElementById("galleryMount");
    if (!mount) return;

    const items = (data.gallery?.items || [])
      .map(
        (item) => `
          <div class="gallery-card" data-gallery-id="${esc(item.id)}">
            <div class="gallery-imgs">
              <div>
                ${imageOrPlaceholder(item.beforeImage, `${item.location} before`, "before")}
              </div>
              <div>
                ${imageOrPlaceholder(item.afterImage, `${item.location} after`, "after")}
              </div>
            </div>

            <div class="gallery-meta">
              ${hasText(item.style) ? `<div class="gallery-style">${esc(item.style)}</div>` : ""}
              ${hasText(item.location) ? `<div class="gallery-loc">${esc(item.location)}</div>` : ""}
              <div class="gallery-tags">
                ${(item.tags || []).map((tag) => `<span class="tag">${esc(tag)}</span>`).join("")}
              </div>
            </div>
          </div>
        `
      )
      .join("");

    mount.innerHTML = `
      <div class="gallery-section">
        <div class="section-eyebrow">${esc(data.gallery?.eyebrow || "")}</div>
        <h2 class="section-title">${esc(data.gallery?.title || "")}</h2>
        <p class="section-sub">${esc(data.gallery?.subtext || "")}</p>

        <div class="gallery-grid">
          ${items}
        </div>

        ${hasText(data.gallery?.note) ? `<p class="gallery-note">${esc(data.gallery.note)}</p>` : ""}
      </div>
    `;
  }

  function renderAbout() {
    const mount = document.getElementById("aboutMount");
    if (!mount) return;

    const paragraphs = (data.about?.paragraphs || [])
      .map((p) => `<p>${esc(p)}</p>`)
      .join("");

    const pillars = (data.about?.pillars || [])
      .map(
        (pillar) => `
          <div class="pillar">
            <h4>${esc(pillar.title)}</h4>
            <p>${esc(pillar.body)}</p>
          </div>
        `
      )
      .join("");

    mount.innerHTML = `
      <div class="about-section">
        <div class="about-grid">
          <div class="about-text">
            <div class="section-eyebrow" style="text-align:left;">${esc(data.about?.eyebrow || "")}</div>
            <h2 class="about-title">${data.about?.titleHtml || ""}</h2>
            ${paragraphs}
          </div>

          <div class="about-pillars">
            ${pillars}
          </div>
        </div>
      </div>
    `;
  }

  renderBrand();
  renderHome();
  renderPackages();
  renderHIW();
  renderGallery();
  renderAbout();
})();