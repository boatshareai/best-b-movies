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

  function renderBanner(items) {
    if (!banner || !items.length) return;
    var n = items.length;
    banner.hidden = false;
    banner.innerHTML =
      '<span class="titles-count">' + n + ' title' + (n === 1 ? '' : 's') + ' from your selection</span>' +
      '<span class="titles-banner-actions">' +
        '<a href="films.html" class="titles-action">Browse catalog</a>' +
        '<button type="button" class="titles-action titles-clear" id="titles-clear-btn">Clear all</button>' +
      '</span>';
    document.getElementById("titles-clear-btn").addEventListener("click", function () {
      if (window.VOF_BASKET) window.VOF_BASKET.clear();
      if (titleInput) titleInput.value = "";
      banner.hidden = true;
    });
  }

  if (titleInput) {
    var params = new URLSearchParams(location.search);
    var preTitle = params.get("title");
    if (preTitle && !titleInput.value) {
      titleInput.value = preTitle;
    } else if (!titleInput.value && window.VOF_BASKET) {
      var basketItems = window.VOF_BASKET.getAll();
      if (basketItems.length) {
        titleInput.value = basketItems.map(function (i) { return i.title; }).join("\n");
        renderBanner(basketItems);
      }
    }
  }

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
