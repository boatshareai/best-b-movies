(function () {
  var slides = Array.from(document.querySelectorAll('.hero .hero-slide'));
  if (slides.length < 2) return;

  var cur = 0;
  var nameEl = document.querySelector('.hero-film-name');
  var linkEl = document.querySelector('.hero-film-link');

  function goTo(idx) {
    slides[cur].classList.remove('active');
    cur = idx % slides.length;
    slides[cur].classList.add('active');
    var s = slides[cur];
    if (nameEl) nameEl.textContent = s.dataset.title + ' (' + s.dataset.year + ')';
    var href = 'films/' + s.dataset.slug + '.html';
    if (linkEl) linkEl.href = href;
  }

  setInterval(function () { goTo(cur + 1); }, 6000);
})();
