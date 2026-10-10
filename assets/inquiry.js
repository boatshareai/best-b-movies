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

  // Pre-fill titles from ?title= query param (linked from film pages).
  var titleInput = document.getElementById("titles");
  if (titleInput) {
    var params = new URLSearchParams(location.search);
    var preTitle = params.get("title");
    if (preTitle && !titleInput.value) titleInput.value = preTitle;
  }

  if (!cfg.ENDPOINT) {
    if (unconfiguredEl) {
      unconfiguredEl.hidden = false;
      // Update mailto link with configured email
      var email = cfg.LICENSING_EMAIL || cfg.SITE_CONTACT_EMAIL || "";
      if (email) {
        unconfiguredEl.innerHTML =
          "<strong>Form not connected.</strong> " +
          'Email us at <a href="mailto:' + email + '">' + email + "</a> to discuss licensing.";
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

    // Honeypot check
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
