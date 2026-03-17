const API_BASE = (window.APP_CONFIG && window.APP_CONFIG.apiBase) || 'https://YOUR-BACKEND.onrender.com';

/* ---------- Section Navigation ---------- */
function showSection(id) {
  document.querySelectorAll('.section').forEach(function (s) {
    s.classList.remove('active');
  });

  document.querySelectorAll('.nav-links a').forEach(function (a) {
    a.classList.remove('active');
  });

  var el = document.getElementById('section-' + id);
  if (el) el.classList.add('active');

  var nav = document.getElementById('nav-' + id);
  if (nav) nav.classList.add('active');

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ---------- Package — Lot Size Selector ---------- */
var selectedLot = 'standard';

function formatPrice(value) {
  return '$' + Number(value).toFixed(2);
}

function selectLot(lot) {
  selectedLot = lot;

  var std = document.getElementById('lot-standard');
  var large = document.getElementById('lot-large');
  var btn = document.getElementById('cartBtn');

  if (std) std.classList.toggle('selected', lot === 'standard');
  if (large) large.classList.toggle('selected', lot === 'large');

  var pkg = window.PACKAGE_DATA && window.PACKAGE_DATA[lot];
  if (pkg && btn) {
    btn.textContent = 'Secure Checkout — ' + formatPrice(pkg.price);
  }
}

function validateCheckoutForm() {
  var name = document.getElementById('customerName')?.value.trim();
  var email = document.getElementById('customerEmail')?.value.trim();
  var phone = document.getElementById('customerPhone')?.value.trim();

  if (!name || !email || !phone) {
    throw new Error('Please enter your name, email, and phone number.');
  }

  return { name: name, email: email, phone: phone };
}

/* ---------- Package — Stripe Checkout ---------- */
async function handleCart() {
  var btn = document.getElementById('cartBtn');
  if (!btn) return;

  var pkg = window.PACKAGE_DATA && window.PACKAGE_DATA[selectedLot];
  if (!pkg) {
    alert('Please select a package.');
    return;
  }

  var customer;
  try {
    customer = validateCheckoutForm();
  } catch (err) {
    alert(err.message || 'Please complete the form.');
    return;
  }

  var originalText = 'Secure Checkout — ' + formatPrice(pkg.price);
  btn.textContent = 'Redirecting to secure checkout...';
  btn.disabled = true;

  try {
    var res = await fetch(API_BASE + '/create-checkout-session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        package_id: pkg.id,
        package_name: pkg.label,
        package_price: pkg.price,
        customer_name: customer.name,
        customer_email: customer.email,
        customer_phone: customer.phone
      })
    });

    var data = await res.json();
    if (!res.ok || !data.checkout_url) {
      throw new Error(data.detail || 'Unable to start checkout.');
    }

    window.location.href = data.checkout_url;
  } catch (err) {
    alert(err.message || 'Something went wrong starting checkout.');
    btn.textContent = originalText;
    btn.disabled = false;
  }
}

/* ---------- Before/After Slider ---------- */
(function () {
  function initSlider() {
    var slider = document.getElementById('heroSlider');
    var before = document.getElementById('sliderBefore');
    var divider = document.getElementById('sliderDivider');
    var handle = document.getElementById('sliderHandle');
    var dragging = false;

    if (!slider || !before || !divider || !handle) return;

    function setSlider(clientX) {
      var rect = slider.getBoundingClientRect();
      var pct = ((clientX - rect.left) / rect.width) * 100;
      pct = Math.max(5, Math.min(95, pct));

      before.style.width = pct + '%';
      divider.style.left = pct + '%';
      handle.style.left = pct + '%';
    }

    slider.addEventListener('mousedown', function (e) {
      dragging = true;
      setSlider(e.clientX);
      e.preventDefault();
    });

    document.addEventListener('mousemove', function (e) {
      if (dragging) setSlider(e.clientX);
    });

    document.addEventListener('mouseup', function () {
      dragging = false;
    });

    slider.addEventListener('touchstart', function (e) {
      dragging = true;
      setSlider(e.touches[0].clientX);
    }, { passive: true });

    document.addEventListener('touchmove', function (e) {
      if (dragging) setSlider(e.touches[0].clientX);
    }, { passive: true });

    document.addEventListener('touchend', function () {
      dragging = false;
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSlider);
  } else {
    initSlider();
  }
})();
