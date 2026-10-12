/* Velvet Octopus Films — licensing inquiry form handler.
   Reads window.VOF_CONFIG set by assets/config.js. */

(function () {
  "use strict";

  var cfg = window.VOF_CONFIG || {};
  var form = document.getElementById("inquiry");
  var okEl = document.getElementById("ok");
  var errEl = document.getElementById("err");
  var unconfiguredEl = document.getElementById("unconfigured");
  var submitBtn = document.getElementById("submit");
  var statusLine = document.getElementById("status-line");

  // ── Titles field: pre-fill from basket or ?title= param ──────────────────
  var titleInput = document.getElementById("titles");
  var banner = document.getElementById("titles-banner");

  function escHtml(s) {
    return (s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  function syncTitlesField(items) {
    if (titleInput) titleInput.value = items.map(function (i) { return i.title; }).join("\n");
  }

  function renderBanner(items) {
    if (!banner) return;
    if (!items || !items.length) { banner.hidden = true; return; }
    banner.hidden = false;
    var chips = items.map(function (item) {
      return '<span class="basket-tag">' + escHtml(item.title) +
        '<button type="button" class="basket-tag-remove" data-slug="' + escHtml(item.slug) +
        '" aria-label="Remove ' + escHtml(item.title) + '">&times;</button></span>';
    }).join("");
    banner.innerHTML =
      '<div class="basket-chips">' + chips + '</div>' +
      '<span class="titles-banner-actions">' +
        '<a href="/browse.html" class="titles-action">Browse catalog</a>' +
        '<button type="button" class="titles-action titles-clear" id="titles-clear-btn">Clear all</button>' +
      '</span>';
    if (titleInput) titleInput.style.display = "none";
    syncTitlesField(items);

    // Use event delegation so listeners survive innerHTML replacement
    banner.addEventListener("click", function (e) {
      var removeBtn = e.target.closest(".basket-tag-remove");
      if (removeBtn) {
        var slug = removeBtn.dataset.slug;
        if (window.VOF_BASKET) window.VOF_BASKET.toggle(slug, "");
        var remaining = window.VOF_BASKET ? window.VOF_BASKET.getAll() : [];
        syncTitlesField(remaining);
        renderBanner(remaining);
        if (!remaining.length && titleInput) titleInput.style.display = "";
        return;
      }
      if (e.target.classList.contains("titles-clear")) {
        if (window.VOF_BASKET) window.VOF_BASKET.clear();
        syncTitlesField([]);
        banner.hidden = true;
        if (titleInput) { titleInput.style.display = ""; titleInput.value = ""; }
      }
    });
  }

  function initBasket() {
    if (!titleInput || !window.VOF_BASKET) return;
    var basketItems = window.VOF_BASKET.getAll();
    if (basketItems.length) {
      renderBanner(basketItems);
    } else {
      var params = new URLSearchParams(location.search);
      var preTitle = params.get("title");
      if (preTitle && !titleInput.value) titleInput.value = preTitle;
    }
  }

  initBasket();

  // Re-init when browser restores page from bfcache (back/forward navigation)
  window.addEventListener("pageshow", function (e) {
    if (e.persisted) initBasket();
  });

  // ── Unconfigured fallback ─────────────────────────────────────────────────
  if (!cfg.ENDPOINT) {
    if (unconfiguredEl) {
      unconfiguredEl.hidden = false;
      var email = cfg.LICENSING_EMAIL || cfg.SITE_CONTACT_EMAIL || "";
      if (email) {
        unconfiguredEl.textContent = "";
        var msg = document.createElement("strong");
        msg.textContent = "Form not connected.";
        var link = document.createElement("a");
        link.href = "mailto:" + email;
        link.textContent = email;
        unconfiguredEl.appendChild(msg);
        unconfiguredEl.appendChild(document.createTextNode(" Email us at "));
        unconfiguredEl.appendChild(link);
        unconfiguredEl.appendChild(document.createTextNode(" to discuss licensing."));
      }
    }
    if (form) form.style.display = "none";
    return;
  }

  if (!form) return;

  function validate() {
    var ok = true;
    ["name", "company", "email"].forEach(function (id) {
      var input = document.getElementById(id);
      var errP = form.querySelector('[data-err="' + id + '"]');
      var valid = input && input.value.trim();
      if (id === "email" && valid) {
        valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.value.trim());
      }
      if (input) input.setAttribute("aria-invalid", valid ? "false" : "true");
      if (errP) errP.hidden = !!valid;
      if (!valid) ok = false;
    });
    return ok;
  }

  form.addEventListener("submit", function (evt) {
    evt.preventDefault();
    if (!validate()) return;

    var hp = form.querySelector('[name="website"]');
    if (hp && hp.value) return;

    var body = {
      name: (form.querySelector("#name") || {}).value || "",
      company: (form.querySelector("#company") || {}).value || "",
      email: (form.querySelector("#email") || {}).value || "",
      titles: (form.querySelector("#titles") || {}).value || "",
      use: (form.querySelector("#use") || {}).value || "",
      volume: (form.querySelector("#volume") || {}).value || "",
      message: (form.querySelector("#message") || {}).value || "",
    };

    submitBtn.disabled = true;
    if (statusLine) statusLine.textContent = "Sending…";
    if (errEl) errEl.hidden = true;

    fetch(cfg.ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
      .then(function (res) {
        if (!res.ok) return res.text().then(function (t) { throw new Error(t || res.status); });
        return res.json();
      })
      .then(function () {
        form.hidden = true;
        if (okEl) okEl.hidden = false;
        if (window.VOF_BASKET) window.VOF_BASKET.clear();
      })
      .catch(function (err) {
        submitBtn.disabled = false;
        if (statusLine) statusLine.textContent = "";
        if (errEl) {
          errEl.textContent = "Something went wrong. Please try again or email us directly.";
          errEl.hidden = false;
        }
        console.error("inquiry error:", err);
      });
  });
})();
