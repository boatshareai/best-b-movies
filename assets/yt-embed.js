/* Velvet Octopus Films — YouTube click-to-play embed.
   Privacy-preserving: no YouTube request until the user clicks.
   Two modes:
     - Inside .yt-wrap  → replaces the wrap with the iframe (film page)
     - Inside .watch-card → inserts into .yt-embed-slot, hides the button */

(function () {
  "use strict";

  function makeIframe(id) {
    var iframe = document.createElement("iframe");
    iframe.src =
      "https://www.youtube-nocookie.com/embed/" +
      encodeURIComponent(id) +
      "?autoplay=1&rel=0";
    iframe.allow =
      "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
    iframe.allowFullscreen = true;
    iframe.title = "YouTube video player";
    iframe.setAttribute("loading", "lazy");
    return iframe;
  }

  document.addEventListener("click", function (evt) {
    var btn = evt.target.closest("[data-yt-id]");
    if (!btn) return;
    var id = btn.getAttribute("data-yt-id");
    if (!id) return;

    // Watch-card mode: insert iframe into slot, hide button
    var card = btn.closest(".watch-card");
    if (card) {
      var slot = card.querySelector(".yt-embed-slot");
      if (slot) {
        slot.appendChild(makeIframe(id));
        btn.hidden = true;
        return;
      }
    }

    // Film-page mode: replace .yt-wrap
    var wrap = btn.closest(".yt-wrap");
    if (!wrap) return;
    wrap.innerHTML = "";
    var iframe = makeIframe(id);
    wrap.appendChild(iframe);
    iframe.focus();
  });
})();
