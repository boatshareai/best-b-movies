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

  // Pre-fill titles from ?title= query param or inquiry basket.
  // When coming from the basket, render removable chip tags so individual
  // titles can be deleted before submitting.
  var titleInput = document.getElementById("titles");

  function escHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function renderChips(items) {
    var group = titleInput.parentNode;
    var wrap = document.createElement("div");
    wrap.className = "basket-chips-edit";
    wrap.id = "basket-chips-edit";
    items.forEach(function (item) {
      var tag = document.createElement("span");
      tag.className = "basket-chip-tag";
      tag.dataset.slug = item.slug;
      tag.innerHTML = escHtml(item.title) +
        '<button type="button" class="chip-remove" aria-label="Remove ' + escHtml(item.title) + '">×</button>';
      wrap.appendChild(tag);
    });
    group.insertBefore(wrap, titleInput);
    titleInput.type = "hidden";
    updateHidden(wrap);

    wrap.addEventListener("click", function (e) {
      var btn = e.target.closest ? e.target.closest(".chip-remove") :
        (e.target.className === "chip-remove" ? e.target : null);
      if (!btn) return;
      var tag = btn.parentNode;
      var slug = tag.dataset.slug;
      if (window.VOF_BASKET) window.VOF_BASKET.toggle(slug, tag.childNodes[0].textContent.trim());
      tag.remove();
      updateHidden(wrap);
      if (!wrap.querySelector(".basket-chip-tag")) {
        wrap.remove();
        titleInput.type = "text";
        titleInput.value = "";
      }
    });
  }

  function updateHidden(wrap) {
    var titles = [];
    wrap.querySelectorAll(".basket-chip-tag").forEach(function (t) {
      titles.push(t.childNodes[0].textContent.trim());
    });
    titleInput.value = titles.join(", ");
  }

  if (titleInput) {
    var params = new URLSearchParams(location.search);
    var preTitle = params.get("title");
    if (preTitle && !titleInput.value) {
      titleInput.value = preTitle;
    } else if (!titleInput.value && window.VOF_BASKET) {
      var basketItems = window.VOF_BASKET.getAll();
      if (basketItems.length) {
        renderChips(basketItems);
      }
    }
  }

  if (!cfg.ENDPOINT) {
    if (unconfiguredEl) {
      unconfiguredEl.hidden = false;
      // Update mailto link with configured email
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
