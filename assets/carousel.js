/* Featured-titles carousels: arrow buttons over native scroll-snap tracks.
   No autoplay — each track is a plain scroller, so touch swipe and keyboard
   both work even if this script never runs.

   The home page carries one carousel per catalog, so every [data-carousel]
   on the page is wired up independently. */
(function () {
  "use strict";

  function init(root) {
    var track = root.querySelector(".carousel-track");
    var prev = root.querySelector(".carousel-btn.prev");
    var next = root.querySelector(".carousel-btn.next");
    if (!track || !prev || !next) return;

    function page() {
      // scroll by a near-viewport step so cards don't get half-skipped
      return Math.max(track.clientWidth * 0.8, 160);
    }

    // Scroll snapping and sub-pixel rounding mean scrollLeft rarely settles
    // exactly on 0 or on the maximum, so the bounds need a tolerance. Anything
    // well under one scroll step is safe.
    var EPS = 8;

    function sync() {
      var max = track.scrollWidth - track.clientWidth;
      prev.disabled = track.scrollLeft <= EPS;
      // A track that fits entirely on screen has nothing to scroll to, so both
      // arrows stay disabled rather than looking live but doing nothing.
      next.disabled = max <= EPS || track.scrollLeft >= max - EPS;
    }

    prev.addEventListener("click", function () {
      track.scrollBy({ left: -page(), behavior: "smooth" });
    });
    next.addEventListener("click", function () {
      track.scrollBy({ left: page(), behavior: "smooth" });
    });

    track.addEventListener("scroll", function () {
      window.requestAnimationFrame(sync);
    });
    window.addEventListener("resize", sync);

    sync();
  }

  var roots = document.querySelectorAll("[data-carousel]");
  for (var i = 0; i < roots.length; i++) init(roots[i]);
})();
