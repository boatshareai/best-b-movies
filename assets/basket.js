/* Velvet Octopus Films — inquiry basket.
   Stores selected film slugs/titles in localStorage.
   Exposes window.VOF_BASKET and renders a floating chip when ≥1 title is queued. */

(function () {
  "use strict";

  var KEY = "vof_basket";

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || "[]"); }
    catch (e) { return []; }
  }

  function save(items) {
    try { localStorage.setItem(KEY, JSON.stringify(items)); }
    catch (e) {}
  }

  function emit() {
    document.dispatchEvent(new CustomEvent("vof:basket"));
  }

  function sync() {
    var items = load();
    var chip = document.getElementById("vof-basket-chip");
    if (!chip) return;
    if (items.length === 0) { chip.hidden = true; return; }
    chip.hidden = false;
    var countEl = chip.querySelector(".basket-count");
    var nEl     = chip.querySelector(".basket-n");
    if (countEl) countEl.textContent = items.length;
    if (nEl)     nEl.textContent = items.length === 1 ? "title" : "titles";
  }

  var api = {
    getAll: load,

    has: function (slug) {
      return load().some(function (i) { return i.slug === slug; });
    },

    toggle: function (slug, title, year) {
      var items = load(), idx = -1;
      items.forEach(function (i, n) { if (i.slug === slug) idx = n; });
      if (idx === -1) items.push({ slug: slug, title: title, year: year || "" });
      else items.splice(idx, 1);
      save(items);
      sync();
      emit();
    },

    addAll: function (newItems) {
      var items = load();
      newItems.forEach(function (ni) {
        if (!items.some(function (i) { return i.slug === ni.slug; })) {
          items.push({ slug: ni.slug, title: ni.title, year: ni.year || "" });
        }
      });
      save(items);
      sync();
      emit();
    },

    clear: function () {
      save([]);
      sync();
      emit();
    },
  };

  // ── Build floating chip ──────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", function () {
    // Don't show the chip on the licensing page itself — you're already there
    var p = location.pathname;
    if (p === "/licensing" || p === "/licensing.html" || p.endsWith("/licensing")) return;

    // Use root-relative URL so this works from any depth
    var licUrl = "/licensing.html";

    var chip = document.createElement("div");
    chip.id        = "vof-basket-chip";
    chip.className = "basket-chip";
    chip.hidden    = true;
    chip.innerHTML =
      '<a class="basket-chip-link" href="' + licUrl + '">' +
        '<svg class="basket-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">' +
          '<path d="M2 4h12l-1.5 7H3.5L2 4Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>' +
          '<circle cx="5.5" cy="13" r="1" fill="currentColor"/>' +
          '<circle cx="10.5" cy="13" r="1" fill="currentColor"/>' +
        '</svg>' +
        '<span class="basket-count">0</span> ' +
        '<span class="basket-n">titles</span> &mdash; Inquire &rsaquo;' +
      '</a>' +
      '<button type="button" class="basket-chip-clear" aria-label="Clear selection">&times;</button>';
    document.body.appendChild(chip);

    chip.querySelector(".basket-chip-clear").addEventListener("click", function () {
      api.clear();
      // Reset any in-basket card toggles visible on this page
      document.querySelectorAll(".basket-toggle.in-basket").forEach(function (b) {
        b.classList.remove("in-basket");
        b.setAttribute("aria-label", "Add to inquiry");
        b.title = "Add to inquiry";
      });
      // Reset film-page button if present
      var fb = document.getElementById("basket-btn");
      if (fb) { fb.classList.remove("in-basket"); fb.textContent = "+ Add to inquiry"; }
    });

    // ── Film-detail page basket button ────────────────────────────────────
    var filmBtn = document.getElementById("basket-btn");
    if (filmBtn) {
      var slug  = filmBtn.dataset.slug;
      var title = filmBtn.dataset.title;
      var year  = filmBtn.dataset.year || "";

      function updateFilmBtn() {
        if (api.has(slug)) {
          filmBtn.classList.add("in-basket");
          filmBtn.textContent = "✓ In your inquiry";
        } else {
          filmBtn.classList.remove("in-basket");
          filmBtn.textContent = "+ Add to inquiry";
        }
      }

      updateFilmBtn();
      filmBtn.addEventListener("click", function () {
        api.toggle(slug, title, year);
        updateFilmBtn();
      });
    }

    sync();
  });

  window.VOF_BASKET = api;
})();
