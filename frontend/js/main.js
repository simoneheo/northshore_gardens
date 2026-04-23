if (typeof window.renderHomepage === "function") {
  window.renderHomepage();
}

function initFloatingContactWidget() {
  if (!window.APP_CONFIG || !document.body) return;
  if (document.body.classList.contains('intake-page') || document.body.classList.contains('contact-page')) return;
  if (document.getElementById('floatingContactWidget')) return;

  const mount = document.createElement('aside');
  mount.id = 'floatingContactWidget';
  mount.className = 'floating-contact';
  mount.setAttribute('data-open', 'false');
  mount.innerHTML = `
    <button type="button" class="floating-contact-trigger" id="floatingContactTrigger" aria-expanded="false" aria-controls="floatingContactPanel">
      Talk to a designer
    </button>
    <section class="floating-contact-panel" id="floatingContactPanel" aria-label="Talk to a designer panel">
      <div class="floating-contact-head">
        <h3 id="floatingContactPanelTitle">Talk to a designer</h3>
        <button type="button" class="floating-contact-close" id="floatingContactClose" aria-label="Close contact panel">x</button>
      </div>
      <div class="floating-contact-copy">
        <p id="floatingContactIntro"></p>
        <p id="floatingContactTrust" class="contact-trust"></p>
      </div>
      <form id="floatingContactForm" class="floating-contact-form">
        <label for="floatingContactName"><span id="floatingContactNameLabel"></span>
          <input id="floatingContactName" class="text-input" type="text" name="name" required />
        </label>
        <label for="floatingContactMessage"><span id="floatingContactMessageLabel"></span>
          <textarea id="floatingContactMessage" class="text-area" name="message" required></textarea>
        </label>
        <label for="floatingContactEmail"><span id="floatingContactEmailLabel"></span>
          <input id="floatingContactEmail" class="text-input" type="email" name="email" required />
        </label>
        <label for="floatingContactAttachments"><span id="floatingContactUploadLabel"></span>
          <input id="floatingContactAttachments" class="attachment-input" type="file" name="attachments" accept="image/*" multiple />
          <span class="floating-contact-hint">Up to 5 images.</span>
        </label>
        <button type="submit" class="button" id="floatingContactSubmit">Send Message</button>
        <div class="floating-contact-status" id="floatingContactStatus" aria-live="polite"></div>
      </form>
    </section>
  `;
  document.body.appendChild(mount);

  const trigger = document.getElementById('floatingContactTrigger');
  const closeButton = document.getElementById('floatingContactClose');
  const form = document.getElementById('floatingContactForm');
  const statusNode = document.getElementById('floatingContactStatus');
  const submitButton = document.getElementById('floatingContactSubmit');
  const nameNode = document.getElementById('floatingContactName');
  const messageNode = document.getElementById('floatingContactMessage');
  const emailNode = document.getElementById('floatingContactEmail');
  const attachmentsNode = document.getElementById('floatingContactAttachments');

  const site = window.SITE_DATA || {};
  const panelTitle = document.getElementById('floatingContactPanelTitle');
  if (panelTitle) panelTitle.textContent = site.contactTitle || 'Talk to a designer';
  const introEl = document.getElementById('floatingContactIntro');
  if (introEl) {
    introEl.textContent =
      site.contactIntro ||
      "Send a quick note or a photo of your yard and we'll respond with a few thoughtful ideas.";
  }
  const trustEl = document.getElementById('floatingContactTrust');
  if (trustEl) trustEl.textContent = site.contactTrust || 'No sales pressure. No spam.';
  const nameLbl = document.getElementById('floatingContactNameLabel');
  if (nameLbl) nameLbl.textContent = site.contactNameLabel || 'Name';
  const msgLbl = document.getElementById('floatingContactMessageLabel');
  if (msgLbl) msgLbl.textContent = site.contactMessageLabel || 'Message';
  const emailLbl = document.getElementById('floatingContactEmailLabel');
  if (emailLbl) emailLbl.textContent = site.contactEmailLabel || 'Email';
  const uploadLbl = document.getElementById('floatingContactUploadLabel');
  if (uploadLbl) uploadLbl.textContent = site.contactAttachmentLabel || 'Add a photo (optional)';
  if (submitButton) submitButton.textContent = site.contactSubmitButton || 'Send Message';

  function setOpen(isOpen) {
    mount.setAttribute('data-open', isOpen ? 'true' : 'false');
    if (trigger) trigger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }

  function setStatus(message, kind, detail) {
    if (!statusNode) return;
    statusNode.replaceChildren();
    if (!message && !detail) return;
    const className = kind === 'error' ? 'error-text' : (kind === 'success' ? 'success-text' : '');
    if (kind === 'success' && detail) {
      const p1 = document.createElement('p');
      p1.className = className;
      p1.textContent = message;
      const p2 = document.createElement('p');
      p2.className = className;
      p2.style.marginTop = '6px';
      p2.textContent = detail;
      statusNode.append(p1, p2);
      return;
    }
    if (message) {
      const p = document.createElement('p');
      p.className = className;
      p.textContent = message;
      statusNode.appendChild(p);
    }
  }

  trigger?.addEventListener('click', () => {
    const wasOpen = mount.getAttribute('data-open') === 'true';
    setOpen(!wasOpen);
    if (!wasOpen && typeof window.trackNsgEvent === 'function') {
      window.trackNsgEvent('click_talk_to_designer', { action: 'open_panel' });
    }
  });

  closeButton?.addEventListener('click', () => setOpen(false));

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') setOpen(false);
  });

  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    setStatus('');

    const name = nameNode?.value?.trim() || '';
    const message = messageNode?.value?.trim() || '';
    const email = emailNode?.value?.trim() || '';
    const files = Array.from(attachmentsNode?.files || []).slice(0, 5);

    if (!name || !message || !email) {
      setStatus('Please complete name, message, and email.', 'error');
      return;
    }
    const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    if (!emailValid) {
      setStatus('Please enter a valid email address.', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('name', name);
    formData.append('email', email);
    formData.append('message', message);
    files.forEach((file) => formData.append('attachments', file));

    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = 'Sending...';
    }

    try {
      const response = await fetch(`${window.APP_CONFIG.apiBase}/contact-submit`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        let detail = `Request failed (${response.status})`;
        try {
          const payload = await response.json();
          detail = payload?.detail || detail;
        } catch (_err) {}
        throw new Error(detail);
      }
      const okTitle =
        site.contactSuccessTitle ||
        "Thanks - we'll take a look and respond by email.";
      const okBody =
        typeof site.contactSuccessBody === 'string' && site.contactSuccessBody.trim()
          ? site.contactSuccessBody.trim()
          : '';
      if (okBody) {
        setStatus(okTitle, 'success', okBody);
      } else {
        setStatus(okTitle, 'success');
      }
      form.reset();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unable to send message right now.', 'error');
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = site.contactSubmitButton || 'Send Message';
      }
    }
  });
}

initFloatingContactWidget();

document.addEventListener(
  'click',
  function (e) {
    const a = e.target.closest('a[data-intake-entry-intent]');
    if (!a) return;
    const href = a.getAttribute('href') || '';
    if (!href.includes('intake.html')) return;

    let sourcePage = a.getAttribute('data-intake-source-page') || 'unknown';
    if (sourcePage === 'header') {
      try {
        if (window.matchMedia('(max-width: 820px)').matches) {
          const nav = document.getElementById('siteNav');
          if (nav && nav.classList.contains('is-open')) {
            sourcePage = 'mobile_menu';
          }
        }
      } catch (_err) {
        /* ignore */
      }
    }

    const entryIntent = a.getAttribute('data-intake-entry-intent') || 'unknown';
    const analyticsCta = a.getAttribute('data-analytics-cta') || '';
    if (typeof window.trackNsgEvent === 'function') {
      if (analyticsCta === 'get_consultation') {
        window.trackNsgEvent('click_get_consultation', {
          entry_intent: entryIntent,
          source_page: sourcePage,
        });
      } else {
        window.trackNsgEvent('click_get_started', {
          entry_intent: entryIntent,
          source_page: sourcePage,
        });
      }
    }
    e.preventDefault();
    if (typeof window.openIntakeWithIntent === 'function') {
      window.openIntakeWithIntent(entryIntent, sourcePage, href);
    } else {
      window.location.assign(href);
    }
  },
  true
);

document.addEventListener(
  'click',
  function (e) {
    const a = e.target.closest('a');
    if (!a || a.hash !== '#packages') return;
    let ctaLocation = a.getAttribute('data-packages-analytics') || '';
    if (!ctaLocation) {
      const de = a.getAttribute('data-edit');
      if (de === 'navPackages') ctaLocation = 'nav';
      else if (de === 'heroTertiaryCta') ctaLocation = 'hero';
      else ctaLocation = 'other';
    }
    if (typeof window.trackNsgEvent === 'function') {
      window.trackNsgEvent('click_packages_cta', { cta_location: ctaLocation });
    }
  },
  true
);

const navToggle = document.querySelector('.nav-toggle');
const siteNav = document.querySelector('.site-nav');

if (navToggle && siteNav) {
  navToggle.addEventListener('click', () => {
    const isOpen = siteNav.classList.toggle('is-open');
    navToggle.setAttribute('aria-expanded', String(isOpen));
  });
}

const intakeMount = document.getElementById('intakeApp');

if (intakeMount) {
  const defaultLead =
    window.NSGLeadIntent && typeof window.NSGLeadIntent.getLeadIntent === 'function'
      ? window.NSGLeadIntent.getLeadIntent()
      : { entry_intent: 'unknown', source_page: 'unknown' };

  const defaultSteps = [
    {
      key: 'name',
      type: 'text',
      label: 'Step 1',
      title: 'What is your name?',
      hint: 'We use this in our emails and to organize your photos.',
      required: true,
      placeholder: 'First and last name',
    },
    {
      key: 'yardGoal',
      type: 'textarea',
      label: 'Step 2',
      title: 'What are you hoping to improve?',
      hint: 'A sentence or two is perfect.',
      required: false,
      placeholder: 'Front beds, entry feel, curb appeal...'
    },
    {
      key: 'yardNotes',
      type: 'textarea',
      label: 'Step 3',
      title: 'Tell us a little about your yard or goals.',
      hint: 'Share anything helpful about style, maintenance, or what feels off.',
      required: false,
      placeholder: 'Anything you want us to keep in mind...'
    },
    {
      key: 'photos',
      type: 'upload',
      label: 'Step 4',
      title: 'Upload a photo of your yard (optional).',
      hint: 'You can skip this and reply to a follow-up email with more photos.',
      required: false,
    },
    {
      key: 'address',
      type: 'text',
      label: 'Step 5',
      title: 'What is your address? (optional but helpful)',
      hint: 'If easier, just include city and street.',
      required: false,
      placeholder: 'Optional address',
    },
    {
      key: 'email',
      type: 'email',
      label: 'Step 6',
      title: 'What is your email?',
      hint: "We'll send a thoughtful follow-up. No spam.",
      required: true,
      placeholder: 'you@example.com',
    },
  ];

  function normalizeStep(step) {
    if (!step || typeof step !== 'object') return null;
    const key = typeof step.key === 'string' ? step.key.trim() : '';
    const type = typeof step.type === 'string' ? step.type.trim() : '';
    const label = typeof step.label === 'string' ? step.label.trim() : '';
    const title = typeof step.title === 'string' ? step.title.trim() : '';
    if (!key || !type || !label || !title) return null;
    if (!['textarea', 'upload', 'text', 'email'].includes(type)) return null;
    return {
      key,
      type,
      label,
      title,
      hint: typeof step.hint === 'string' ? step.hint : '',
      required: Boolean(step.required),
      placeholder: typeof step.placeholder === 'string' ? step.placeholder : '',
    };
  }

  function resolveIntakeSteps() {
    const rawSteps = window.QUESTIONNAIRE_CONFIG?.intake?.steps;
    if (!Array.isArray(rawSteps) || !rawSteps.length) return defaultSteps;
    const parsed = rawSteps.map(normalizeStep).filter(Boolean);
    if (!parsed.length) return defaultSteps;
    const hasRequiredEmail = parsed.some((s) => s.type === 'email' && s.required === true);
    const hasRequiredName = parsed.some((s) => s.key === 'name' && s.type === 'text' && s.required === true);
    if (!hasRequiredEmail || !hasRequiredName) return defaultSteps;
    return parsed;
  }

  const steps = resolveIntakeSteps();

  const initialAnswers = {};
  steps.forEach((step) => {
    initialAnswers[step.key] = step.type === 'upload' ? [] : '';
  });

  const state = {
    current: 0,
    answers: initialAnswers,
    error: '',
    submitting: false,
    submitted: false,
    leadIntent: defaultLead,
  };

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function render() {
    if (state.submitted) {
      intakeMount.innerHTML = `
        <div class="success-state">
          <p class="eyebrow">Submitted</p>
          <h2>Thanks - we've got your submission.</h2>
          <p>We'll review your yard and follow up with a few thoughtful ideas shortly. There's no checkout step here. This intake is for personal follow-up first.</p>
          <p>Keep an eye on your email for a response from Northshore Gardens.</p>
          <a class="button" href="./index.html">Back to homepage</a>
        </div>
      `;
      return;
    }

    const step = steps[state.current];
    const progress = ((state.current + 1) / steps.length) * 100;

    intakeMount.innerHTML = `
      <div class="progress-meta">
        <span>${step.label}</span>
        <span>${state.current + 1} of ${steps.length}</span>
      </div>
      <div class="progress-track"><div class="progress-fill" style="width:${progress}%"></div></div>
      <div class="question-wrap">
        <p class="eyebrow">Northshore Gardens Intake</p>
        <h2>${step.title}</h2>
        ${step.hint ? `<p class="question-hint">${escapeHtml(step.hint)}</p>` : ''}
        <div class="question-body">${renderBody(step)}</div>
        ${state.error ? `<p class="error-text">${escapeHtml(state.error)}</p>` : ''}
      </div>
      <div class="intake-actions">
        <button type="button" class="button button-ghost" ${state.current === 0 ? 'disabled' : ''} data-action="back">Back</button>
        <div class="actions-right">
          ${state.current < steps.length - 1 ? `<button type="button" class="button" data-action="next">Next</button>` : `<button type="button" class="button" data-action="submit" ${state.submitting ? 'disabled' : ''}>${state.submitting ? 'Submitting...' : 'Submit'}</button>`}
        </div>
      </div>
    `;

    attachStepEvents(step);
  }

  function renderBody(step) {
    switch (step.type) {
      case 'upload':
        return `
          <div class="upload-box">
            <strong>Add up to 5 photos</strong>
            <p class="question-hint">Photos help our designers give more specific ideas.</p>
            <input id="uploadStepInput" type="file" accept="image/*" multiple />
            <div class="upload-thumbs">
              ${Array.isArray(state.answers[step.key]) && state.answers[step.key].length
                ? state.answers[step.key].map(file => `<span class="upload-thumb">${escapeHtml(file.name)}</span>`).join('')
                : '<span class="upload-thumb">No files selected yet</span>'}
            </div>
          </div>
        `;
      case 'textarea':
        return `
          <div class="inline-fields">
            <textarea id="textStepField" class="text-area" placeholder="${escapeHtml(step.placeholder || '')}">${escapeHtml(state.answers[step.key] || '')}</textarea>
          </div>
        `;
      case 'text':
        return `
          <div class="inline-fields">
            <input id="textStepInput" class="text-input" type="text" value="${escapeHtml(state.answers[step.key] || '')}" placeholder="${escapeHtml(step.placeholder || '')}" />
          </div>
        `;
      case 'email':
        return `
          <div class="inline-fields">
            <input id="emailStepInput" class="text-input" type="email" value="${escapeHtml(state.answers[step.key] || '')}" placeholder="${escapeHtml(step.placeholder || '')}" />
          </div>
        `;
      default:
        return '';
    }
  }

  function attachStepEvents(step) {
    const uploadInput = document.getElementById('uploadStepInput');
    if (uploadInput) {
      uploadInput.addEventListener('change', (event) => {
        const files = Array.from(event.target.files || []).slice(0, 5);
        state.answers[step.key] = files;
        state.error = '';
        render();
      });
    }

    const textStepField = document.getElementById('textStepField');
    if (textStepField) {
      textStepField.addEventListener('input', (event) => {
        state.answers[step.key] = event.target.value;
      });
    }

    const textStepInput = document.getElementById('textStepInput');
    if (textStepInput) {
      textStepInput.addEventListener('input', (event) => {
        state.answers[step.key] = event.target.value;
      });
    }

    const emailStepInput = document.getElementById('emailStepInput');
    if (emailStepInput) {
      emailStepInput.addEventListener('input', (event) => {
        state.answers[step.key] = event.target.value;
      });
    }

    intakeMount.querySelector('[data-action="back"]')?.addEventListener('click', () => {
      if (state.current === 0) return;
      state.current -= 1;
      state.error = '';
      render();
    });

    intakeMount.querySelector('[data-action="next"]')?.addEventListener('click', () => {
      if (!validateStep(step)) return;
      state.current += 1;
      state.error = '';
      render();
    });

    intakeMount.querySelector('[data-action="submit"]')?.addEventListener('click', async () => {
      if (!validateStep(step)) return;
      state.error = '';
      state.submitting = true;
      render();

      try {
        await submitIntake();
        if (window.NSGLeadIntent && typeof window.NSGLeadIntent.clearLeadIntent === 'function') {
          window.NSGLeadIntent.clearLeadIntent();
        }
        window.location.href = './intake_success.html';
      } catch (error) {
        state.error = error instanceof Error ? error.message : 'Submission failed. Please try again.';
      } finally {
        state.submitting = false;
        render();
      }
    });
  }

  async function submitIntake() {
    const endpoint = `${window.APP_CONFIG.apiBase}/intake-submit`;
    const formData = new FormData();
    steps.forEach((step) => {
      const value = state.answers[step.key];
      if (step.type === 'upload') {
        (Array.isArray(value) ? value : []).forEach((file) => formData.append(step.key, file));
      } else {
        formData.append(step.key, String(value || '').trim());
      }
    });
    // Legacy aliases for old backend/reporting paths.
    const emailValue = String(state.answers.email || '').trim();
    const yardGoalValue = String(state.answers.yardGoal || '').trim();
    const yardNotesValue = String(state.answers.yardNotes || '').trim();
    if (emailValue) formData.append('client_email', emailValue);
    if (yardGoalValue) formData.append('improve', yardGoalValue);
    if (yardNotesValue) formData.append('notes', yardNotesValue);
    formData.append('entry_intent', state.leadIntent.entry_intent);
    formData.append('source_page', state.leadIntent.source_page);

    const response = await fetch(endpoint, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let message = `Submission failed (${response.status})`;
      try {
        const payload = await response.json();
        if (payload?.detail) {
          message = payload.detail;
        }
      } catch (_error) {
        // no-op
      }
      throw new Error(message);
    }
  }

  function validateStep(step) {
    if (!step.required) return true;
    if (step.type === 'text') {
      const textVal = String(state.answers[step.key] || '').trim();
      if (!textVal) {
        state.error = step.key === 'name' ? 'Please add your name.' : 'Please fill in this field.';
        render();
        return false;
      }
    }
    if (step.type === 'email') {
      const emailVal = String(state.answers[step.key] || '').trim();
      if (!emailVal) {
        state.error = 'Please add your email so we can follow up.';
        render();
        return false;
      }
      const emailOkay = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailVal);
      if (!emailOkay) {
        state.error = 'Please enter a valid email address.';
        render();
        return false;
      }
    }

    return true;
  }

  render();
}

const contactForm = document.getElementById('contactForm');
if (contactForm) {
  const statusNode = document.getElementById('contactStatus');
  const submitButton = document.getElementById('contactSubmit');

  function setContactStatus(message, isError = false, isSuccess = false) {
    if (!statusNode) return;
    statusNode.className = isSuccess ? 'contact-success' : '';
    statusNode.innerHTML = `<p class="${isError ? 'error-text' : ''}">${message}</p>`;
  }

  contactForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    setContactStatus('');

    const name = document.getElementById('contactName')?.value?.trim() || '';
    const email = document.getElementById('contactEmail')?.value?.trim() || '';
    const message = document.getElementById('contactMessage')?.value?.trim() || '';
    const attachmentInput = document.getElementById('contactAttachments');
    const files = Array.from(attachmentInput?.files || []).slice(0, 5);

    if (!name || !email || !message) {
      setContactStatus('Please complete name, email, and message.', true);
      return;
    }

    const formData = new FormData();
    formData.append('name', name);
    formData.append('email', email);
    formData.append('message', message);
    files.forEach((file) => formData.append('attachments', file));

    submitButton.disabled = true;
    submitButton.textContent = 'Sending...';

    try {
      const response = await fetch(`${window.APP_CONFIG.apiBase}/contact-submit`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        let detail = `Request failed (${response.status})`;
        try {
          const payload = await response.json();
          detail = payload?.detail || detail;
        } catch (_error) {
          // no-op
        }
        throw new Error(detail);
      }

      const successTitle = window.SITE_DATA?.contactSuccessTitle || 'Thanks, your message was sent.';
      const rawBody = window.SITE_DATA?.contactSuccessBody;
      const successBody =
        typeof rawBody === 'string' && rawBody.trim() ? rawBody.trim() : '';
      const html = successBody
        ? `<strong>${successTitle}</strong><br>${successBody}`
        : `<strong>${successTitle}</strong>`;
      setContactStatus(html, false, true);
      contactForm.reset();
    } catch (error) {
      setContactStatus(error instanceof Error ? error.message : 'Unable to send message right now.', true);
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = window.SITE_DATA?.contactSubmitButton || 'Send Message';
    }
  });
}

const plansGrid = document.getElementById('plansGrid');
if (plansGrid) {
  const plansError = document.getElementById('plansError');

  function getLeadToken() {
    try {
      const params = new URLSearchParams(window.location.search || '');
      return (params.get('lead') || '').trim();
    } catch (_error) {
      return '';
    }
  }

  function setPlansMessage(message, isError = true) {
    if (!plansError) return;
    plansError.innerHTML = message ? `<p class="${isError ? 'error-text' : ''}">${message}</p>` : '';
  }

  const leadToken = getLeadToken();
  if (!leadToken) {
    plansGrid.style.display = 'none';
    setPlansMessage('This link is invalid or expired.');
  } else {
    plansGrid.querySelectorAll('[data-plan-checkout]').forEach((button) => {
      button.addEventListener('click', async () => {
        const packageId = button.getAttribute('data-plan-checkout') || '';
        if (!packageId) return;

        setPlansMessage('');
        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = 'Redirecting...';

        try {
          const response = await fetch(`${window.APP_CONFIG.apiBase}/create-checkout-session`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              public_token: leadToken,
              package_id: packageId,
            }),
          });

          if (!response.ok) {
            let detail = `Request failed (${response.status})`;
            try {
              const payload = await response.json();
              detail = payload?.detail || detail;
            } catch (_error) {
              // no-op
            }
            throw new Error(detail);
          }

          const payload = await response.json();
          if (!payload?.checkout_url) {
            throw new Error('Checkout could not be started. Please try again.');
          }
          window.location.href = payload.checkout_url;
        } catch (_error) {
          setPlansMessage('We could not start checkout right now. Please try again in a moment.');
          button.disabled = false;
          button.textContent = originalText;
        }
      });
    });
  }
}
