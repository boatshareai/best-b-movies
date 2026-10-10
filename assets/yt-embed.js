/* Velvet Octopus Films — YouTube click-to-play embed.
   Replaces the trigger button with a youtube-nocookie.com iframe on click.
   Privacy-preserving: no YouTube request until the user clicks. */

(function () {
  "use strict";

  document.addEventListener("click", function (evt) {
    var btn = evt.target.closest("[data-yt-id]");
    if (!btn) return;
    var id = btn.getAttribute("data-yt-id");
    if (!id) return;

    var wrap = btn.closest(".yt-wrap");
    if (!wrap) return;

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

    wrap.innerHTML = "";
    wrap.appendChild(iframe);
    iframe.focus();
  });
})();
