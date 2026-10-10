/* Velvet Octopus Films — film submission form handler.
   Reads window.VOF_CONFIG set by assets/config.js. */

(function () {
  "use strict";

  var cfg = window.VOF_CONFIG || {};
  var form = document.getElementById("submission");
  var okEl = document.getElementById("ok");
  var errEl = document.getElementById("err");
  var unconfiguredEl = document.getElementById("unconfigured");
  var submitBtn = document.getElementById("submit");
  var statusLine = document.getElementById("status-line");

  if (!cfg.SUBMISSION_ENDPOINT) {
    if (unconfiguredEl) {
      unconfiguredEl.hidden = false;
      var email = cfg.SITE_CONTACT_EMAIL || "";
      if (email) {
        unconfiguredEl.innerHTML =
          "<strong>Form not connected.</strong> " +
          'Email your submission to <a href="mailto:' + email + '">' + email + "</a>.";
      }
    }
    if (form) form.style.display = "none";
    return;
  }

  if (!form) return;

  function validate() {
    var ok = true;
    var required = ["name", "email", "film_title", "year", "synopsis"];
    required.forEach(function (id) {
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
    var rights = document.getElementById("rights_confirmation");
    var rightsErr = form.querySelector('[data-err="rights_confirmation"]');
    if (rights && !rights.checked) {
      if (rightsErr) rightsErr.hidden = false;
      ok = false;
    } else if (rightsErr) {
      rightsErr.hidden = true;
    }
    return ok;
  }

  form.addEventListener("submit", function (evt) {
    evt.preventDefault();
    if (!validate()) return;

    var hp = form.querySelector('[name="website"]');
    if (hp && hp.value) return;

    var body = {
      name: (form.querySelector("#name") || {}).value || "",
      email: (form.querySelector("#email") || {}).value || "",
      film_title: (form.querySelector("#film_title") || {}).value || "",
      year: (form.querySelector("#year") || {}).value || "",
      genre: (form.querySelector("#genre") || {}).value || "",
      runtime: (form.querySelector("#runtime") || {}).value || "",
      synopsis: (form.querySelector("#synopsis") || {}).value || "",
      screener_link: (form.querySelector("#screener_link") || {}).value || "",
      distribution_status: (form.querySelector("#distribution_status") || {}).value || "",
      rights_confirmation: true,
    };

    submitBtn.disabled = true;
    if (statusLine) statusLine.textContent = "Sending…";
    if (errEl) errEl.hidden = true;

    fetch(cfg.SUBMISSION_ENDPOINT, {
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
        console.error("submission error:", err);
      });
  });
})();
