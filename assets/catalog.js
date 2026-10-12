/* Velvet Octopus Films — browse page: client-side card grid.
   Reads JSON from #catalog-data, renders poster cards, handles filters. */

(function () {
  "use strict";

  var data = JSON.parse(document.getElementById("catalog-data").textContent);
  var grid = document.getElementById("rows");
  var empty = document.getElementById("empty");
  var countEl = document.getElementById("count");
  var addAllBtn = document.getElementById("add-all");

  var q = document.getElementById("q");
  var peopleSel = document.getElementById("people");
  var catSel = document.getElementById("catalog");
  var genreSel = document.getElementById("genre");
  var decadeSel = document.getElementById("decade");
  var yrFrom = document.getElementById("yr_from");
  var yrTo = document.getElementById("yr_to");
  var langSel = document.getElementById("lang");
  var runtimeSel = document.getElementById("runtime");
  var statusSel = document.getElementById("status");
  var ytCb = document.getElementById("yt");
  var intlCb = document.getElementById("intl");
  var sortSel = document.getElementById("sort");
  var resetBtn = document.getElementById("reset");

  var BADGE = {
    Available: "badge-available",
    Licensed: "badge-licensed",
    Represented: "badge-represented",
  };

  function monogram(title) {
    return (title.replace(/^(the|a|an)\s+/i, "").trim()[0] || "?").toUpperCase();
  }

  function posterHTML(f) {
    if (f.p) {
      return '<img src="assets/posters/' + esc(f.p) + '" alt="" loading="lazy" decoding="async" width="300" height="450">';
    }
    return '<span class="card-typo-title" aria-hidden="true">' + esc(f.t) + "</span>";
  }

  function esc(s) {
    return (s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function card(f) {
    var bcls = BADGE[f.st] || "badge-available";
    var btxt = f.st || "Available";
    var ytDot = f.yt ? '<span class="status-dot badge-yt">YouTube</span>' : "";
    var inBasket = window.VOF_BASKET && window.VOF_BASKET.has(f.s);
    var toggleLabel = inBasket ? "Remove from inquiry" : "Add to inquiry";
    var basketBtn =
      '<button class="basket-toggle' + (inBasket ? " in-basket" : "") + '" ' +
      'type="button" data-slug="' + esc(f.s) + '" data-title="' + esc(f.t) + '" ' +
      'aria-label="' + toggleLabel + '" title="' + toggleLabel + '">' +
      (inBasket ? "✓" : "+") +
      "</button>";
    return (
      '<a class="film-card" href="films/' + esc(f.s) + '.html" title="' + esc(f.t) + '">' +
        '<span class="poster">' +
          posterHTML(f) +
          '<span class="status-dot ' + bcls + '">' + esc(btxt) + "</span>" +
          ytDot +
          basketBtn +
        "</span>" +
        '<span class="cap">' +
          "<b>" + esc(f.t) + "</b>" +
          '<span class="cap-sub">' + esc(f.y || "Year not listed") + "</span>" +
        "</span>" +
      "</a>"
    );
  }

  function matchRuntime(f, val) {
    if (!val) return true;
    if (val === "__none") return f.r === null || f.r === undefined;
    var parts = val.split("-").map(Number);
    return f.r !== null && f.r !== undefined && f.r >= parts[0] && f.r <= parts[1];
  }

  function filter(films) {
    var qv = (q.value || "").trim().toLowerCase();
    var pv = peopleSel ? (peopleSel.value || "").trim().toLowerCase() : "";
    var cat = catSel.value;
    var genre = genreSel.value;
    var decade = decadeSel.value;
    var lang = langSel.value;
    var rt = runtimeSel.value;
    var status = statusSel.value;
    var ytOnly = ytCb && ytCb.checked;
    var intlOnly = intlCb && intlCb.checked;
    var yfrom = yrFrom ? parseInt(yrFrom.value, 10) : NaN;
    var yto = yrTo ? parseInt(yrTo.value, 10) : NaN;

    return films.filter(function (f) {
      if (qv && f.t.toLowerCase().indexOf(qv) === -1 && (f.o || "").toLowerCase().indexOf(qv) === -1) return false;
      if (pv) {
        var dr = (f.dr || "").toLowerCase();
        var ca = (f.ca || "").toLowerCase();
        var pr = (f.pr || "").toLowerCase();
        if (dr.indexOf(pv) === -1 && ca.indexOf(pv) === -1 && pr.indexOf(pv) === -1) return false;
      }
      if (cat && f.c !== cat) return false;
      if (genre && f.g.indexOf(genre) === -1) return false;
      if (decade) {
        if (decade === "__none" && f.d) return false;
        if (decade !== "__none" && f.d !== decade) return false;
      }
      if (lang) {
        if (lang === "__none" && f.l) return false;
        if (lang !== "__none" && f.l !== lang) return false;
      }
      /* intlOnly: show non-English only (language set, and not English) */
      if (intlOnly && (!f.l || f.l.toLowerCase() === "english")) return false;
      if (!matchRuntime(f, rt)) return false;
      if (status && f.st !== status) return false;
      if (ytOnly && !f.yt) return false;
      if (!isNaN(yfrom) && (f.yn === null || f.yn === undefined || f.yn < yfrom)) return false;
      if (!isNaN(yto) && (f.yn === null || f.yn === undefined || f.yn > yto)) return false;
      return true;
    });
  }

  function sort(films) {
    var s = sortSel ? sortSel.value : "t";
    var copy = films.slice();
    if (s === "y_desc") {
      copy.sort(function (a, b) { return (parseInt(b.y) || 0) - (parseInt(a.y) || 0); });
    } else if (s === "y_asc") {
      copy.sort(function (a, b) { return (parseInt(a.y) || 0) - (parseInt(b.y) || 0); });
    } else {
      copy.sort(function (a, b) { return a.t.toLowerCase() < b.t.toLowerCase() ? -1 : 1; });
    }
    return copy;
  }

  var _lastResults = [];

  function render() {
    _lastResults = sort(filter(data));
    grid.innerHTML = _lastResults.map(card).join("");
    empty.hidden = _lastResults.length > 0;
    if (countEl) {
      countEl.textContent = "";
      var b = document.createElement("b");
      b.textContent = _lastResults.length;
      countEl.appendChild(b);
      countEl.appendChild(document.createTextNode(" of " + data.length + " titles"));
    }
    if (addAllBtn) {
      var filtered = _lastResults.length < data.length;
      addAllBtn.hidden = !filtered;
      addAllBtn.textContent = "Add all " + _lastResults.length + " to inquiry";
    }
  }

  function readUrl() {
    var params = new URLSearchParams(location.search);
    if (params.get("q")) q.value = params.get("q");
    if (params.get("people") && peopleSel) peopleSel.value = params.get("people");
    if (params.get("catalog")) catSel.value = params.get("catalog");
    if (params.get("genre")) genreSel.value = params.get("genre");
    if (params.get("decade")) decadeSel.value = params.get("decade");
    if (params.get("lang")) langSel.value = params.get("lang");
    if (params.get("runtime")) runtimeSel.value = params.get("runtime");
    if (params.get("status")) statusSel.value = params.get("status");
    if (params.get("yr_from") && yrFrom) yrFrom.value = params.get("yr_from");
    if (params.get("yr_to") && yrTo) yrTo.value = params.get("yr_to");
    if (params.get("yt") === "1" && ytCb) ytCb.checked = true;
    if (params.get("intl") === "1" && intlCb) intlCb.checked = true;
  }

  function pushUrl() {
    var p = new URLSearchParams();
    if (q.value) p.set("q", q.value);
    if (peopleSel && peopleSel.value) p.set("people", peopleSel.value);
    if (catSel.value) p.set("catalog", catSel.value);
    if (genreSel.value) p.set("genre", genreSel.value);
    if (decadeSel.value) p.set("decade", decadeSel.value);
    if (langSel.value) p.set("lang", langSel.value);
    if (runtimeSel.value) p.set("runtime", runtimeSel.value);
    if (statusSel.value) p.set("status", statusSel.value);
    if (yrFrom && yrFrom.value) p.set("yr_from", yrFrom.value);
    if (yrTo && yrTo.value) p.set("yr_to", yrTo.value);
    if (ytCb && ytCb.checked) p.set("yt", "1");
    if (intlCb && intlCb.checked) p.set("intl", "1");
    var s = p.toString();
    history.replaceState(null, "", s ? "?" + s : location.pathname);
  }

  function syncPillState() {
    [catSel, genreSel, decadeSel, langSel, runtimeSel, statusSel, sortSel, yrFrom, yrTo].forEach(function (el) {
      if (!el) return;
      if (el.tagName === "SELECT") {
        if (el.value && el.value !== el.options[0].value) {
          el.dataset.active = "1";
        } else {
          delete el.dataset.active;
        }
      }
    });
    if (q) q.dataset.active = q.value ? "1" : "";
    if (peopleSel) peopleSel.dataset.active = peopleSel.value ? "1" : "";
  }

  function onChange() { pushUrl(); syncPillState(); render(); }

  [catSel, genreSel, decadeSel, langSel, runtimeSel, statusSel, sortSel, yrFrom, yrTo].forEach(function (el) {
    if (el) el.addEventListener("change", onChange);
  });
  if (ytCb) ytCb.addEventListener("change", onChange);
  if (intlCb) intlCb.addEventListener("change", onChange);
  q.addEventListener("input", onChange);
  if (peopleSel) peopleSel.addEventListener("input", onChange);

  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      q.value = "";
      if (peopleSel) peopleSel.value = "";
      [catSel, genreSel, decadeSel, langSel, runtimeSel, statusSel].forEach(function (el) {
        if (el) el.value = "";
      });
      if (yrFrom) yrFrom.value = "";
      if (yrTo) yrTo.value = "";
      if (ytCb) ytCb.checked = false;
      if (intlCb) intlCb.checked = false;
      if (sortSel) sortSel.value = "t";
      pushUrl();
      syncPillState();
      render();
    });
  }

  if (addAllBtn) {
    addAllBtn.addEventListener("click", function () {
      if (!window.VOF_BASKET) return;
      window.VOF_BASKET.addAll(_lastResults.map(function (f) {
        return { slug: f.s, title: f.t };
      }));
      addAllBtn.textContent = "✓ " + _lastResults.length + " titles added";
      addAllBtn.disabled = true;
      setTimeout(function () {
        addAllBtn.disabled = false;
        addAllBtn.textContent = "Add all " + _lastResults.length + " to inquiry";
      }, 2000);
    });
  }

  // Re-render when basket changes so toggle states stay current.
  document.addEventListener("vof:basket", render);

  // Delegate basket-toggle clicks so they work on dynamically rendered cards.
  if (grid) {
    grid.addEventListener("click", function (evt) {
      var btn = evt.target.closest(".basket-toggle");
      if (!btn || !window.VOF_BASKET) return;
      evt.preventDefault();
      evt.stopPropagation();
      window.VOF_BASKET.toggle(btn.dataset.slug, btn.dataset.title);
    });
  }

  readUrl();
  syncPillState();
  render();
})();
