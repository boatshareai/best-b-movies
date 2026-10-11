(function () {
  var slides = Array.from(document.querySelectorAll('.hero .hero-slide'));
  if (slides.length < 2) return;

  var cur = 0;
  var nameEl = document.querySelector('.hero-film-name');
  var linkEl = document.querySelector('.hero-film-link');
  var overlayEl = document.querySelector('.hero-slide-overlay');

  function goTo(idx) {
    slides[cur].classList.remove('active');
    cur = idx % slides.length;
    slides[cur].classList.add('active');
    var s = slides[cur];
    if (nameEl) nameEl.textContent = s.dataset.title + ' (' + s.dataset.year + ')';
    var href = 'films/' + s.dataset.slug + '.html';
    if (linkEl) linkEl.href = href;
    if (overlayEl) overlayEl.href = href;
  }

  // Auto-advance every 6 seconds
  var timer = setInterval(function () { goTo(cur + 1); }, 6000);

  // Manual dots
  var dotsEl = document.querySelector('.hero-dots');
  if (dotsEl) {
    slides.forEach(function (s, i) {
      var dot = document.createElement('button');
      dot.className = 'hero-dot' + (i === 0 ? ' active' : '');
      dot.setAttribute('aria-label', s.dataset.title);
      dot.addEventListener('click', function () {
        clearInterval(timer);
        dotsEl.querySelectorAll('.hero-dot').forEach(function (d) { d.classList.remove('active'); });
        dot.classList.add('active');
        goTo(i);
        timer = setInterval(function () {
          var nextDot = dotsEl.querySelectorAll('.hero-dot')[cur + 1 < slides.length ? cur + 1 : 0];
          dotsEl.querySelectorAll('.hero-dot').forEach(function (d) { d.classList.remove('active'); });
          if (nextDot) nextDot.classList.add('active');
          goTo(cur + 1);
        }, 6000);
      });
      dotsEl.appendChild(dot);
    });

    // Keep dot in sync with auto-advance
    var origGoTo = goTo;
    goTo = function (idx) {
      origGoTo(idx);
      dotsEl.querySelectorAll('.hero-dot').forEach(function (d, i) {
        d.classList.toggle('active', i === cur);
      });
    };
  }
})();
