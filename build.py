#!/usr/bin/env python3
"""
Velvet Octopus Films — static site generator.

Reads data/*.csv and writes a complete static site to dist/.
Stdlib only; no pip install, no node_modules, no build toolchain.

    python3 build.py

To update the catalog, edit a data CSV and re-run. Nothing else needs to change.
"""

import csv
import html
import json
import os
import re
import shutil
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
DIST = os.path.join(HERE, "dist")

# Absolute origin the site is served from. Set SITE_BASE in the deploy workflow.
SITE_BASE = os.environ.get("SITE_BASE", "").rstrip("/")

SITE_NAME = "Velvet Octopus Films"
SITE_TAGLINE = "Films worth a second look."
SITE_FOOT_TAGLINE = "Eight arms. One big library."
TIKTOK_URL = "https://www.tiktok.com/@thelostfilmfiles"
TIKTOK_HANDLE = "@thelostfilmfiles"

OWN_CATALOG = "best-b-movies"

CATALOGS = [
    {
        "key": "best-b-movies",
        "name": "Best B Movies",
        "display_name": "Best B Movies",
        "file": "catalog.csv",
        "prefix": "",
        "blurb": "Classic Hollywood and international cinema, 1930s to today"
                 " — westerns, noir, Rathbone-era mystery, gothic horror,"
                 " and art-house landmarks.",
    },
    {
        "key": "blue-finch",
        "name": "Blue Finch Film Releasing",
        "display_name": "Blue Finch Film Releasing",
        "file": "blue-finch.csv",
        "prefix": "bf",
        "blurb": "Contemporary independent features, weighted to the 2010s"
                 " and 2020s — led by horror, drama, and thriller.",
    },
    {
        "key": "sc-films",
        "name": "SC Films International",
        "display_name": "SC Films International",
        "file": "sc-films.csv",
        "prefix": "sc",
        "blurb": "Live action and family animation, plus documentary and"
                 " genre titles. Year and runtime data is largely absent.",
    },
]
CATALOG_BY_KEY = {c["key"]: c for c in CATALOGS}

COUNTS = {"total": 0, "best-b-movies": 0, "blue-finch": 0, "sc-films": 0}


LICENSING_TERMS = (
    "Velvet Octopus Films represents a library of %(cfv)d films spanning classic "
    "Hollywood, international cinema, and contemporary art-house titles from "
    "the 1930s to today. Titles are available for non-exclusive licensing across "
    "streaming, broadcast, and digital platforms, with territory and term "
    "negotiated per deal. Some titles currently carry a non-exclusive license "
    "with another platform — this doesn’t prevent additional licensing, and "
    "any existing arrangement will be disclosed during the inquiry process. "
    "Reach out with the titles or volume you’re interested in, and we’ll follow "
    "up with availability, territory, and rate details."
)

CONFIRMATION = (
    "Thanks — we’ve got your inquiry and will follow up within a few "
    "business days with availability and terms. — Velvet Octopus Films"
)

SUBMISSION_CONFIRMATION = (
    "Thanks — we’ve received your submission and will be in touch "
    "if it’s a good fit. — Velvet Octopus Films"
)

USE_OPTIONS = [
    "Streaming platform",
    "Broadcast",
    "Home video or digital sell-through",
    "Educational or institutional",
    "Other",
]
VOLUME_OPTIONS = [
    "Single title",
    "Small package (2–10)",
    "Full or near-full catalog",
]

GENRE_OPTIONS = [
    "Drama",
    "Comedy",
    "Horror",
    "Thriller",
    "Action",
    "Animation",
    "Documentary",
    "Other",
]

DISTRIBUTION_STATUS_OPTIONS = [
    "No distribution",
    "Self-distributed",
    "Festival circuit only",
    "Previously distributed",
    "Currently distributed",
]

HIGHLIGHTS = [
    ("Westerns", ["Western"], "Singing cowboys, cavalry pictures, and late-cycle revisionist entries."),
    ("Mystery & noir", ["Mystery", "Film-Noir", "Crime"], "Rathbone-era Holmes, Fritz Lang thrillers, and hard-boiled studio noir."),
    ("Horror & sci-fi", ["Horror", "Sci-Fi"], "Corman-Poe gothics and drive-in creature features through to contemporary independent horror."),
    ("International", None, "Kurosawa, Ozu, Mizoguchi, Ray, Bu\xf1uel, Tarkovsky, and De Sica."),
]

FEATURED = [
    (
        "best-b-movies",
        "From our own library",
        [
            "Bicycle Thieves",
            "Stagecoach",
            "M",
            "Charade",
            "Foreign Correspondent",
            "Pather Panchali",
        ],
    ),
    (
        "blue-finch",
        "Presented for Blue Finch Film Releasing",
        [
            "A Bronx Tale",
            "Papillon",
            "Dead Man’s Shoes",
            "Frances Ha",
            "The Player",
            "A Bittersweet Life",
        ],
    ),
    (
        "sc-films",
        "Presented for SC Films International",
        [
            "Monster Island (aka Orang Ikan)",
            "Dragonkeeper",
            "Bel Ami",
            "Poupelle of Chimney Town",
            "Marmaduke",
            "Big Fish and Begonia",
        ],
    ),
]


def e(s):
    return html.escape(s or "", quote=True)


def monogram(title):
    t = re.sub(r"^(the|a|an)\s+", "", title.strip(), flags=re.I)
    return (t[:1] or "?").upper()


def poster_art(f, prefix="", w=300, h=450):
    """Real key art when the row has a `poster`; monogram placeholder otherwise.
    alt="" is intentional: the title is always adjacent as real text."""
    name = (f.get("poster") or "").strip()
    if name:
        return (
            '<img src="%sassets/posters/%s" alt="" loading="lazy" '
            'decoding="async" width="%d" height="%d">' % (prefix, e(name), w, h)
        )
    return '<span class="mono" aria-hidden="true">%s</span>' % e(monogram(f["title"]))


def load():
    films = []
    skipped = 0
    seen_slugs = {}
    for cat in CATALOGS:
        path = os.path.join(HERE, "data", cat["file"])
        if not os.path.exists(path):
            raise SystemExit("missing catalog file: %s" % path)
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        for r in rows:
            r = {k: (v or "").strip() for k, v in r.items() if k}
            if r.get("publish", "yes").lower() in ("no", "false", "0"):
                skipped += 1
                continue
            r["genre_list"] = [g for g in r["genres"].split("; ") if g]
            r["runtime_n"] = int(r["runtime"]) if r.get("runtime", "").isdigit() else None
            r["catalog"] = cat["key"]
            r["catalog_name"] = cat["name"]
            # youtube_id: bare 11-char ID stored in the column
            r["youtube_id"] = (r.get("youtube_id") or "").strip()
            if r["slug"] in seen_slugs:
                raise SystemExit(
                    "duplicate slug %r in %s and %s"
                    % (r["slug"], seen_slugs[r["slug"]], cat["file"])
                )
            seen_slugs[r["slug"]] = cat["file"]
            films.append(r)
    films.sort(key=lambda f: f["title"].lower())
    if skipped:
        print("skipping %d title(s) marked publish=no" % skipped)
    return films


def in_catalog(films, key):
    return [f for f in films if f["catalog"] == key]


# --------------------------------------------------------------------------
# layout
# --------------------------------------------------------------------------

NAV = [
    ("Home", "index.html"),
    ("Collections", "collections.html"),
    ("Browse", "browse.html"),
    ("Licensing", "licensing.html"),
    ("Submit a film", "submit.html"),
    ("About", "about.html"),
]


def page(title, body, current, depth=0, description=""):
    up = "../" * depth
    nav = []
    for label, href in NAV:
        cur = ' aria-current="page"' if href == current else ""
        cls_parts = []
        if href == "index.html":
            cls_parts.append("nav-home")
        if cls_parts:
            cls = ' class="%s"' % " ".join(cls_parts)
        else:
            cls = ""
        nav.append('<a href="%s%s"%s%s>%s</a>' % (up, href, cls, cur, label))
    nav.append(
        '<a class="cta" href="%slicensing.html">'
        '<span class="cta-long">Licensing inquiry</span>'
        '<span class="cta-short">Inquire</span></a>' % up
    )
    desc = description or (
        "%d films across three collections — classic Hollywood, international "
        "cinema, and contemporary independent features — available for "
        "licensing across streaming, broadcast, and digital platforms."
        % COUNTS["total"]
    )
    ogimg = ""
    if SITE_BASE:
        ogimg = (
            '<meta property="og:image" content="%s/assets/og-image.png">\n'
            '<meta property="og:image:width" content="1200">\n'
            '<meta property="og:image:height" content="630">\n'
            '<meta name="twitter:card" content="summary_large_image">\n' % SITE_BASE
        )
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<meta name="robots" content="index, follow">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:site_name" content="%(site)s">
<meta property="og:type" content="website">
%(ogimg)s<link rel="icon" type="image/svg+xml" href="%(up)sassets/favicon.svg">
<link rel="icon" type="image/x-icon" href="%(up)sassets/favicon.ico">
<link rel="apple-touch-icon" href="%(up)sassets/apple-touch-icon.png">
<meta name="theme-color" content="#5B2A86">
<link rel="stylesheet" href="%(up)sassets/site.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <div class="wrap">
    <a class="brand" href="%(up)sindex.html" aria-label="Velvet Octopus Films — home">
      <img class="brand-logo" src="%(up)sassets/brand/logo-wordmark.svg"
           alt="Velvet Octopus Films" width="220" height="40" decoding="async">
    </a>
    <nav class="nav" aria-label="Main">%(nav)s</nav>
  </div>
</header>
<main id="main">
%(body)s
</main>
<footer class="site-foot">
  <div class="wrap">
    <div class="foot-brand">
      <img class="foot-logo" src="%(up)sassets/brand/logo-wordmark.svg"
           alt="Velvet Octopus Films" width="160" height="29" decoding="async" loading="lazy">
      <p class="foot-tag">%(foot_tagline)s</p>
      <p class="foot-copy">&copy; %(year)d Velvet Octopus Films.
        Licensing inquiries only — this site does not stream or sell films.</p>
    </div>
    <nav class="fnav" aria-label="Footer">
      <a href="%(up)sbrowse.html">Browse titles</a>
      <a href="%(up)scollections.html">Collections</a>
      <a href="%(up)slicensing.html">Licensing</a>
      <a href="%(up)ssubmit.html">Submit a film</a>
      <a href="%(up)sabout.html">About</a>
      <a href="%(up)scontact.html">Contact</a>
      <a href="%(up)sprivacy.html">Privacy &amp; terms</a>
    </nav>
  </div>
</footer>
</body>
</html>
""" % {
        "title": e(title),
        "desc": e(desc),
        "nav": "\n      ".join(nav),
        "body": body,
        "up": up,
        "site": e(SITE_NAME),
        "foot_tagline": e(SITE_FOOT_TAGLINE),
        "ogimg": ogimg,
        "year": 2026,
    }


# --------------------------------------------------------------------------
# home
# --------------------------------------------------------------------------


def featured_card(f, prefix=""):
    art = poster_art(f, prefix=prefix)
    bcls = badge(f["status"])[0]
    btxt = f["status"] or "Available"
    yt_dot = ""
    if f.get("youtube_id"):
        yt_dot = '<span class="status-dot badge-yt">YouTube</span>'
    return """        <a class="film-card" href="%(prefix)sfilms/%(slug)s.html" title="%(title)s">
          <span class="poster">
            %(art)s
            <span class="status-dot %(bcls)s">%(btxt)s</span>%(yt_dot)s
          </span>
          <span class="cap">
            <b>%(title)s</b>
            <span class="cap-sub">%(year)s</span>
          </span>
        </a>""" % {
        "prefix": prefix,
        "slug": e(f["slug"]),
        "art": art,
        "bcls": e(bcls),
        "btxt": e(btxt),
        "yt_dot": ("\n            " + yt_dot) if yt_dot else "",
        "title": e(f["title"]),
        "year": e(f["year"]) or "Year not listed",
    }


def band_shade(i):
    return "section-cream" if i % 2 == 0 else "section-white"


def build_featured(films, keys=None, start=0, as_index=False):
    by_key = {(f["title"].strip().lower(), f["catalog"]): f for f in films}
    sections = []
    for cat_key, heading, titles in FEATURED:
        if keys is not None and cat_key not in keys:
            continue
        cards = []
        for want in titles:
            # "Dead Man's Shoes" vs "Dead Man’s Shoes" — normalise apostrophes
            want_norm = want.strip().lower().replace("’", "'").replace("‘", "'")
            f = None
            for (title_lower, ckey), film in by_key.items():
                if ckey == cat_key and title_lower.replace("’", "'").replace("‘", "'") == want_norm:
                    f = film
                    break
            if f is None:
                raise SystemExit(
                    "featured title %r is not in the %s catalog (renamed, "
                    "removed, or publish=no). Fix FEATURED in build.py or the "
                    "catalog CSV." % (want, cat_key)
                )
            cards.append(featured_card(f))
        n = len(in_catalog(films, cat_key))
        if as_index:
            cat = CATALOG_BY_KEY[cat_key]
            heading = cat["name"]
            kicker = (
                "Our own library"
                if cat_key == OWN_CATALOG
                else "Presented on behalf of the rights holder"
            )
            eyebrow = '    <p class="eyebrow">%s</p>\n' % e(kicker)
            line = '    <p class="cat-line">%d titles. %s</p>\n' % (n, e(cat["blurb"]))
            link = "Browse this collection &rsaquo;"
        else:
            eyebrow = ""
            line = ""
            link = "View all %d titles &rsaquo;" % n
        sections.append(
            """
<section class="section %(shade)s">
  <div class="wrap">
%(eyebrow)s    <div class="featured-head">
      <h2>%(heading)s</h2>
      <a class="all-link" href="browse.html?catalog=%(key)s">%(link)s</a>
    </div>
%(line)s
    <div class="carousel" data-carousel>
      <button type="button" class="carousel-btn prev" aria-label="Scroll %(label)s left">&lsaquo;</button>
      <div class="carousel-track" tabindex="0" role="group" aria-label="%(label)s">
%(cards)s
      </div>
      <button type="button" class="carousel-btn next" aria-label="Scroll %(label)s right">&rsaquo;</button>
    </div>
  </div>
</section>"""
            % {
                "shade": band_shade(start + len(sections)),
                "heading": e(heading),
                "eyebrow": eyebrow,
                "line": line,
                "link": link,
                "key": urllib.parse.quote(cat_key),
                "label": e(heading),
                "cards": "\n".join(cards),
            }
        )
    if not sections:
        return ""
    return "\n".join(sections) + '\n<script src="assets/carousel.js"></script>'


def build_home(films):
    total = len(films)
    intl = sum(1 for f in films if f["language"] and f["language"] != "English")

    tiles = []
    for label, genres, sub in HIGHLIGHTS:
        if genres is None:
            count = intl
            href = "browse.html?intl=1"
        else:
            count = sum(1 for f in films if any(g in f["genre_list"] for g in genres))
            href = "browse.html?genre=" + urllib.parse.quote(genres[0])
        tiles.append(
            """      <a class="tile" href="%s">
        <span class="count">%d</span>
        <span class="label">%s</span>
        <span class="sub">%s</span>
      </a>"""
            % (href, count, e(label), e(sub))
        )

    decades = {}
    for f in films:
        if f["decade"]:
            decades[f["decade"]] = decades.get(f["decade"], 0) + 1
    chips = "".join(
        '<a class="decade-chip" href="browse.html?decade=%s"><b>%d</b> from the %s</a>'
        % (d, decades[d], d)
        for d in sorted(decades)
    )

    licensed = sum(1 for f in films if f["status"] == "Licensed")

    split = "\n".join(
        '      <li><a href="browse.html?catalog=%s"><b>%d</b> %s</a></li>'
        % (urllib.parse.quote(c["key"]), len(in_catalog(films, c["key"])), e(c["name"]))
        for c in CATALOGS
    )

    body = """
<section class="hero">
  <div class="wrap">
    <img class="hero-logo" src="assets/brand/logo-stacked.svg"
         alt="Velvet Octopus Films" width="200" height="140" decoding="async">
    <h1>Films worth a second look.</h1>
    <p class="pitch">An independent film library available for licensing. Our own
      collection runs from the 1930s to today. We also present select catalogs for
      Blue Finch Film Releasing and SC Films International.</p>
    <ul class="hero-split">
%(split)s
    </ul>
    <div class="hero-actions">
      <a class="btn btn-gold" href="browse.html">Browse all %(total)d titles</a>
      <a class="btn btn-ghost" href="licensing.html">Licensing inquiry</a>
    </div>
  </div>
</section>
%(featured)s
<section class="section %(lib_shade)s">
  <div class="wrap">
    <div class="rule-head"><h2>Across all three collections</h2></div>
    <div class="tiles">
%(tiles)s
    </div>
    <div class="decades">%(chips)s</div>
  </div>
</section>

<div class="tiktok-strip">
  <div class="wrap">
    <h2>Short clips on TikTok</h2>
    <p>Rare footage, forgotten performances, scenes that hold up. Follow %(handle)s for a daily cut.</p>
    <a class="btn btn-gold btn-ext" href="%(tiktok)s" target="_blank" rel="noopener noreferrer">
      Follow on TikTok<span class="vh"> (opens in a new tab)</span></a>
  </div>
</div>

<section class="section %(how_shade)s">
  <div class="wrap">
    <div class="rule-head"><h2>How licensing works</h2></div>
    <div class="tiles">
      <div class="tile">
        <span class="label">Three collections, one inquiry</span>
        <span class="sub">%(cfv)d titles in the Best B Movies library, plus
          %(bf)d for Blue Finch Film Releasing and %(sc)d for SC Films
          International. Every title page says which.</span>
      </div>
      <div class="tile">
        <span class="label">Terms stated, not implied</span>
        <span class="sub">Best B Movies titles are offered non-exclusively,
          territory and term per deal. Agency-represented titles carry no assumed
          position &mdash; availability is confirmed per inquiry.</span>
      </div>
      <div class="tile">
        <span class="label">Nothing hidden</span>
        <span class="sub">%(licensed)d Best B Movies titles currently carry a
          non-exclusive licence with another platform. They are flagged in the
          catalog and remain available to license.</span>
      </div>
      <div class="tile">
        <span class="label">Single titles to full catalog</span>
        <span class="sub">Package one title, a themed bundle, or explore any of our
          three collections. Tell us the volume and we&rsquo;ll confirm terms per
          title.</span>
      </div>
    </div>
    <p style="margin-top:32px">
      <a class="btn btn-solid" href="licensing.html">Start a licensing inquiry</a>
    </p>
  </div>
</section>
""" % {
        "total": total,
        "split": split,
        "cfv": len(in_catalog(films, "best-b-movies")),
        "bf": len(in_catalog(films, "blue-finch")),
        "sc": len(in_catalog(films, "sc-films")),
        "featured": build_featured(films, keys=["best-b-movies"]),
        "lib_shade": band_shade(1),
        "how_shade": band_shade(2),
        "tiles": "\n".join(tiles),
        "chips": chips,
        "licensed": licensed,
        "tiktok": e(TIKTOK_URL),
        "handle": e(TIKTOK_HANDLE),
    }
    return page(
        "Velvet Octopus Films — films worth a second look",
        body,
        "index.html",
        description="An independent film library for licensing. %d titles across "
        "classic Hollywood, international cinema, and contemporary "
        "independent features." % total,
    )


# --------------------------------------------------------------------------
# collections  (was: catalog)
# --------------------------------------------------------------------------


def build_collections(films):
    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>Collections</h1></div>
    <p class="lede">%(total)d titles across three collections &mdash; our own library,
      plus two we present on behalf of their rights holders. Take them one at a
      time below, or <a href="browse.html">search all three at once</a>.</p>
  </div>
</section>
%(rows)s
""" % {
        "total": len(films),
        "rows": build_featured(films, as_index=True, start=1),
    }

    return page(
        "Collections — %s" % SITE_NAME,
        body,
        "collections.html",
        description="Three collections totalling %d titles: Best B Movies, "
        "Blue Finch Film Releasing, and SC Films International."
        % len(films),
    )


# --------------------------------------------------------------------------
# browse
# --------------------------------------------------------------------------


def build_browse(films):
    genres = sorted({g for f in films for g in f["genre_list"]})
    decades = sorted({f["decade"] for f in films if f["decade"]})
    langs = sorted({f["language"] for f in films if f["language"]})
    statuses = sorted({f["status"] for f in films if f["status"]})

    def opts(values):
        return "".join('<option value="%s">%s</option>' % (e(v), e(v)) for v in values)

    cat_opts = "".join(
        '<option value="%s">%s (%d)</option>'
        % (e(c["key"]), e(c["name"]), len(in_catalog(films, c["key"])))
        for c in CATALOGS
    )

    payload = [
        {
            "s": f["slug"],
            "t": f["title"],
            "y": f["year"],
            "d": f["decade"],
            "g": f["genre_list"],
            "l": f["language"],
            "r": f["runtime_n"],
            "o": f["logline"],
            "p": (f.get("poster") or "").strip(),
            "st": f["status"],
            "c": f["catalog"],
            "cn": f["catalog_name"],
            "yt": f.get("youtube_id", ""),
        }
        for f in films
    ]

    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>Browse titles</h1></div>
    <p class="lede">%(total)d titles across all three collections.
      <a href="collections.html">Browse by collection</a> instead, or filter below.
      Every card shows which collection represents the title.</p>

    <form class="filters" id="filters" role="search" aria-label="Filter titles">
      <div class="filter-grid">
        <div class="field search-field">
          <label for="q">Search title or logline</label>
          <input type="search" id="q" name="q" placeholder="e.g. Stagecoach, A Bronx Tale, Dragonkeeper" autocomplete="off">
        </div>
        <div class="field">
          <label for="catalog">Collection</label>
          <select id="catalog"><option value="">All collections</option>%(cats)s</select>
        </div>
        <div class="field">
          <label for="genre">Genre</label>
          <select id="genre"><option value="">All genres</option>%(genres)s</select>
        </div>
        <div class="field">
          <label for="decade">Decade</label>
          <select id="decade">
            <option value="">All decades</option>%(decades)s
            <option value="__none">Not listed</option>
          </select>
        </div>
        <div class="field">
          <label for="lang">Language</label>
          <select id="lang">
            <option value="">All languages</option>%(langs)s
            <option value="__none">Not specified</option>
          </select>
        </div>
        <div class="field">
          <label for="runtime">Runtime</label>
          <select id="runtime">
            <option value="">Any runtime</option>
            <option value="0-79">Under 80 min</option>
            <option value="80-99">80&ndash;99 min</option>
            <option value="100-119">100&ndash;119 min</option>
            <option value="120-999">120 min and over</option>
            <option value="__none">Not listed</option>
          </select>
        </div>
        <div class="field">
          <label for="status">Licensing status</label>
          <select id="status"><option value="">Any status</option>%(statuses)s</select>
        </div>
        <div class="field">
          <label for="yt">
            <input type="checkbox" id="yt" name="yt" value="1">
            Watch on YouTube only
          </label>
        </div>
        <div class="field">
          <label for="sort">Sort by</label>
          <select id="sort">
            <option value="t">Title A&ndash;Z</option>
            <option value="y_desc">Year (newest first)</option>
            <option value="y_asc">Year (oldest first)</option>
          </select>
        </div>
      </div>
      <div class="filter-foot">
        <p class="result-count" id="count" role="status" aria-live="polite"></p>
        <button type="button" class="link-btn" id="reset">Clear all filters</button>
      </div>
    </form>

    <div class="card-grid" id="rows" aria-live="polite" aria-label="Search results"></div>
    <div class="empty" id="empty" hidden>
      <p><strong>No titles match those filters.</strong></p>
      <p>Try clearing a filter, or <a href="licensing.html">ask us about the full catalog</a>.</p>
    </div>
  </div>
</section>
<script id="catalog-data" type="application/json">%(json)s</script>
<script src="assets/catalog.js"></script>
""" % {
        "total": len(films),
        "cats": cat_opts,
        "genres": opts(genres),
        "decades": opts(decades),
        "langs": opts(langs),
        "statuses": opts(statuses),
        "json": json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c"),
    }
    return page(
        "Browse titles — %s" % SITE_NAME,
        body,
        "browse.html",
        description="Search and filter all %d titles by collection, "
        "genre, decade, language, and licensing status." % len(films),
    )


# --------------------------------------------------------------------------
# film detail
# --------------------------------------------------------------------------


BADGES = {
    "Available": ("badge-available", "Available"),
    "Licensed": ("badge-licensed", "Licensed — non-exclusive"),
    "Represented": ("badge-represented", "Represented"),
}


def badge(status):
    return BADGES.get(status, ("badge-available", status or "Available"))


def meta_logline(logline):
    if not logline:
        return ""
    if len(logline) <= 150:
        return logline + " "
    cut = logline[:150]
    sp = cut.rfind(" ")
    if sp > 100:
        cut = cut[:sp]
    return cut.rstrip(" .,;:—-") + "… "


def youtube_embed(youtube_id):
    """Click-to-play YouTube embed using youtube-nocookie.com."""
    vid = e(youtube_id)
    return """    <div class="yt-wrap">
      <button class="yt-trigger" type="button" data-yt-id="%(vid)s" aria-label="Watch %(vid)s on YouTube (opens player)">
        <span class="yt-play-icon" aria-hidden="true">&#9654;</span>
        <span>Watch on YouTube</span>
      </button>
    </div>
    <script src="../../assets/yt-embed.js"></script>""" % {"vid": vid}


def build_film(f, films):
    badge_cls, badge_txt = badge(f["status"])

    meta = []
    if f["year"]:
        meta.append(e(f["year"]))
    if f["genre_list"]:
        meta.append(e(", ".join(f["genre_list"])))
    if f["runtime_n"]:
        meta.append("%d min" % f["runtime_n"])
    if f["language"]:
        meta.append(e(f["language"]))
    meta_html = '<span class="sep" aria-hidden="true">/</span>'.join(
        "<span>%s</span>" % m for m in meta
    )

    rep = (
        '<a class="rep-tag" href="../browse.html?catalog=%s">'
        '<span>Represented by</span> %s</a>'
        % (urllib.parse.quote(f["catalog"]), e(f["catalog_name"]))
    )

    spec = [("Represented by", f["catalog_name"])]
    spec.append(("Year", f["year"] or "Not listed"))
    spec.append(("Genre", ", ".join(f["genre_list"]) or "Not listed"))
    for label in ("Director", "Writer", "Cast"):
        val = (f.get(label.lower()) or "").strip()
        if val:
            spec.append((label, val))
    spec.append(("Language", f["language"] or "Not specified"))
    if (f.get("country") or "").strip():
        spec.append(("Country", f["country"].strip()))
    spec.append(
        ("Runtime", "%d minutes" % f["runtime_n"] if f["runtime_n"] else "Not listed")
    )
    if f["credit"]:
        spec.append(("Note", f["credit"]))
    spec.append(("Licensing status", badge_txt))
    if f["territory"]:
        spec.append(("Existing licence territory", f["territory"]))
    spec_html = "\n    ".join(
        "<div><dt>%s</dt><dd>%s</dd></div>" % (e(k), e(v)) for k, v in spec
    )

    tags = "".join(
        '<a class="tag" href="../browse.html?genre=%s">%s</a>'
        % (urllib.parse.quote(g), e(g))
        for g in f["genre_list"]
    )
    if f["decade"]:
        tags += '<a class="tag" href="../browse.html?decade=%s">%s</a>' % (
            f["decade"],
            e(f["decade"]),
        )

    synopsis = (
        '<p class="synopsis">%s</p>' % e(f["logline"])
        if f["logline"]
        else '<p class="synopsis muted">No synopsis on file for this title. '
        'We can supply one on request.</p>'
    )

    # YouTube embed OR "License this film" CTA
    yt_id = f.get("youtube_id", "")
    if yt_id:
        watch_block = youtube_embed(yt_id)
    else:
        watch_block = ""

    inquire = "../licensing.html?title=" + urllib.parse.quote(f["title"])
    source_url = (f.get("source_url") or "").strip()
    if f["catalog"] != "best-b-movies" and source_url:
        cta = (
            "<p>Territory and term are negotiated per deal. %(name)s handles "
            "enquiries for this title — their own page for it carries the "
            "current details.</p>\n"
            '      <a class="btn btn-solid btn-ext" href="%(url)s" '
            'target="_blank" rel="noopener noreferrer">View on %(name)s'
            '<span class="vh"> (opens in a new tab)</span></a>'
            % {"name": e(f["catalog_name"]), "url": e(source_url)}
        )
    else:
        cta = (
            "<p>Territory and term are negotiated per deal. Send us this title "
            "and we’ll come back with availability and rates.</p>\n"
            '      <a class="btn btn-gold" href="%s">License this film</a>' % e(inquire)
        )

    # Related films: same genre, same catalog, different title, up to 5
    related_genre = f["genre_list"][:1]
    related = [
        r for r in films
        if r["slug"] != f["slug"]
        and r["catalog"] == f["catalog"]
        and any(g in r["genre_list"] for g in related_genre)
    ][:5]
    related_html = ""
    if related:
        cards = "\n".join(featured_card(r, prefix="../") for r in related)
        related_html = """
<section class="section section-white">
  <div class="wrap">
    <div class="rule-head"><h2>More from this collection</h2></div>
    <div class="related-grid">
%s
    </div>
  </div>
</section>""" % cards

    body = """
<section class="film-head">
  <div class="wrap">
    <p class="crumbs"><a href="../index.html">Home</a> &rsaquo;
      <a href="../browse.html">Browse</a> &rsaquo; %(title)s</p>
    <div class="film-head-grid">
      <span class="poster film-poster">%(art)s</span>
      <div>
        <h1>%(title)s</h1>
        <div class="film-meta">%(meta)s</div>
        <span class="badge %(bcls)s badge-lg">%(btxt)s</span>
        %(rep)s
      </div>
    </div>
  </div>
</section>

<div class="wrap">
  <div class="film-body">
    <div>
      %(watch_block)s
      <h2>Synopsis</h2>
      %(synopsis)s

      <h2>Details</h2>
      <dl class="spec">
    %(spec)s
      </dl>

      <h2 style="margin-top:34px">Browse similar</h2>
      <div class="tag-row">%(tags)s</div>
    </div>

    <aside class="aside-card">
      <h2>Licensing</h2>
      <p>%(licence_note)s</p>
      %(cta)s
    </aside>
  </div>
</div>
%(related)s
""" % {
        "title": e(f["title"]),
        "meta": meta_html,
        "art": poster_art(f, prefix="../"),
        "bcls": badge_cls,
        "btxt": e(badge_txt),
        "synopsis": synopsis,
        "rep": rep,
        "spec": spec_html,
        "tags": tags,
        "licence_note": e(f["licence_note"]),
        "cta": cta,
        "watch_block": watch_block,
        "related": related_html,
    }

    year = " (%s)" % f["year"] if f["year"] else ""
    return page(
        "%s%s — %s" % (f["title"], year, SITE_NAME),
        body,
        "",
        depth=1,
        description="%s%s — %sRepresented by %s. Contact us to confirm "
        "licensing availability."
        % (f["title"], year, meta_logline(f["logline"]), f["catalog_name"]),
    )


# --------------------------------------------------------------------------
# licensing / contact
# --------------------------------------------------------------------------


def build_licensing(films):
    def opts(values):
        return "".join('<option value="%s">%s</option>' % (e(v), e(v)) for v in values)

    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>Licensing &amp; contact</h1></div>

    <div class="prose">
      <p>%(terms)s</p>
      <p>Alongside that library we represent %(bf)d titles for Blue Finch Film
        Releasing and %(sc)d for SC Films International &mdash; %(total)d titles
        in all. The paragraph above sets out the terms for the Best B Movies
        library specifically; for agency-represented titles we hold no
        assumed rights position, and availability, territory, and terms are
        confirmed per inquiry. Every title page states which collection the film
        comes from.</p>
    </div>

    <h2 style="font-size:24px;margin:44px 0 18px">Send an inquiry</h2>

    <div class="form-card">
      <div class="notice notice-ok" id="ok" hidden role="status">%(confirm)s</div>
      <div class="notice notice-err" id="err" hidden role="alert"></div>
      <div class="notice notice-warn" id="unconfigured" hidden>
        <strong>Form not connected.</strong>
        Email us at <a href="mailto:%(contact_email_attr)s">%(contact_email)s</a> to discuss licensing.
      </div>

      <form id="inquiry" novalidate>
        <div class="form-grid">
          <div class="field">
            <label for="name">Name <span class="req">*</span></label>
            <input type="text" id="name" name="name" required autocomplete="name">
            <p class="err-text" data-err="name" hidden>Please enter your name.</p>
          </div>
          <div class="field">
            <label for="company">Company <span class="req">*</span></label>
            <input type="text" id="company" name="company" required autocomplete="organization">
            <p class="err-text" data-err="company" hidden>Please enter your company.</p>
          </div>
          <div class="field full">
            <label for="email">Email <span class="req">*</span></label>
            <input type="email" id="email" name="email" required autocomplete="email">
            <p class="err-text" data-err="email" hidden>Please enter a valid email address.</p>
          </div>
          <div class="field full">
            <label for="titles">Titles of interest</label>
            <input type="text" id="titles" name="titles"
              placeholder="e.g. Stagecoach, M, or &lsquo;browsing the full catalog&rsquo;">
            <p class="hint">Coming from a film page? We&rsquo;ll fill this in for you.</p>
          </div>
          <div class="field">
            <label for="use">Intended use</label>
            <select id="use" name="use">
              <option value="">Select&hellip;</option>%(uses)s
            </select>
          </div>
          <div class="field">
            <label for="volume">Estimated volume</label>
            <select id="volume" name="volume">
              <option value="">Select&hellip;</option>%(vols)s
            </select>
          </div>
          <div class="field full">
            <label for="message">Message</label>
            <textarea id="message" name="message" placeholder="Anything else we should know?"></textarea>
          </div>
          <!-- honeypot: bots fill this, humans don't -->
          <div class="field field-hp" aria-hidden="true">
            <label for="website">Website</label>
            <input type="text" id="website" name="website" tabindex="-1" autocomplete="off">
          </div>
        </div>
        <div class="form-foot">
          <button type="submit" class="btn btn-solid" id="submit">Send inquiry</button>
          <span class="hint" id="status-line"></span>
        </div>
      </form>
    </div>

    <div class="prose" style="margin-top:44px">
      <h2>What happens next</h2>
      <p>We review every inquiry and reply within a few business days with
        availability, territory options, and rates. You&rsquo;ll get an
        acknowledgement by email as soon as you submit. Inquiries are handled by
        email only &mdash; there&rsquo;s no live chat or booking calendar.</p>
    </div>
  </div>
</section>
<script src="assets/config.js"></script>
<script src="assets/inquiry.js"></script>
""" % {
        "terms": e(LICENSING_TERMS % {"cfv": len(in_catalog(films, "best-b-movies"))}),
        "total": len(films),
        "bf": len(in_catalog(films, "blue-finch")),
        "sc": len(in_catalog(films, "sc-films")),
        "confirm": e(CONFIRMATION),
        "uses": opts(USE_OPTIONS),
        "vols": opts(VOLUME_OPTIONS),
        "contact_email": "licensing@velvetoctopusfilms.com",
        "contact_email_attr": "licensing@velvetoctopusfilms.com",
    }
    return page(
        "Licensing & contact — %s" % SITE_NAME,
        body,
        "licensing.html",
        description="Licensing terms and inquiry form for %d titles across the "
        "Best B Movies, Blue Finch, and SC Films International collections."
        % len(films),
    )


# --------------------------------------------------------------------------
# submit a film
# --------------------------------------------------------------------------


def build_submit():
    def opts(values):
        return "".join('<option value="%s">%s</option>' % (e(v), e(v)) for v in values)

    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>Submit a film</h1></div>
    <div class="prose">
      <p>We&rsquo;re interested in independent features, documentaries, and
        genre films with a clear audience and clean rights. We consider
        finished films only &mdash; no development, no treatments.</p>
      <p>Fill in the form below. We&rsquo;ll read every submission and reply
        if it&rsquo;s a good fit. We can&rsquo;t guarantee a response to every
        inquiry, but we do look at all of them.</p>
    </div>

    <div class="form-card" style="margin-top:32px">
      <div class="notice notice-ok" id="ok" hidden role="status">%(confirm)s</div>
      <div class="notice notice-err" id="err" hidden role="alert"></div>
      <div class="notice notice-warn" id="unconfigured" hidden>
        <strong>Form not connected.</strong>
        Email your submission to <a href="mailto:%(submit_email_attr)s">%(submit_email)s</a>.
      </div>

      <form id="submission" novalidate>
        <div class="form-grid">
          <div class="field">
            <label for="name">Your name <span class="req">*</span></label>
            <input type="text" id="name" name="name" required autocomplete="name">
            <p class="err-text" data-err="name" hidden>Please enter your name.</p>
          </div>
          <div class="field">
            <label for="email">Email <span class="req">*</span></label>
            <input type="email" id="email" name="email" required autocomplete="email">
            <p class="err-text" data-err="email" hidden>Please enter a valid email address.</p>
          </div>
          <div class="field">
            <label for="film_title">Film title <span class="req">*</span></label>
            <input type="text" id="film_title" name="film_title" required>
            <p class="err-text" data-err="film_title" hidden>Please enter the film title.</p>
          </div>
          <div class="field">
            <label for="year">Year completed <span class="req">*</span></label>
            <input type="text" id="year" name="year" required placeholder="e.g. 2023" inputmode="numeric">
            <p class="err-text" data-err="year" hidden>Please enter the year.</p>
          </div>
          <div class="field">
            <label for="genre">Genre</label>
            <select id="genre" name="genre">
              <option value="">Select&hellip;</option>%(genres)s
            </select>
          </div>
          <div class="field">
            <label for="runtime">Runtime (minutes)</label>
            <input type="text" id="runtime" name="runtime" placeholder="e.g. 92" inputmode="numeric">
          </div>
          <div class="field full">
            <label for="synopsis">Synopsis <span class="req">*</span></label>
            <textarea id="synopsis" name="synopsis" required
              placeholder="One or two paragraphs is fine."></textarea>
            <p class="err-text" data-err="synopsis" hidden>Please add a synopsis.</p>
          </div>
          <div class="field full">
            <label for="screener_link">Link to your screener</label>
            <input type="url" id="screener_link" name="screener_link"
              placeholder="Vimeo, YouTube, Google Drive&hellip;">
            <p class="hint">A password-protected Vimeo link is fine. No file uploads.</p>
          </div>
          <div class="field full">
            <label for="distribution_status">Current distribution status</label>
            <select id="distribution_status" name="distribution_status">
              <option value="">Select&hellip;</option>%(dist_statuses)s
            </select>
          </div>
          <div class="field full">
            <label>
              <input type="checkbox" id="rights_confirmation" name="rights_confirmation" required>
              I confirm that I own or control the rights to submit this film
              <span class="req">*</span>
            </label>
            <p class="err-text" data-err="rights_confirmation" hidden>Please confirm rights.</p>
          </div>
          <!-- honeypot -->
          <div class="field field-hp" aria-hidden="true">
            <label for="website">Website</label>
            <input type="text" id="website" name="website" tabindex="-1" autocomplete="off">
          </div>
        </div>
        <div class="form-foot">
          <button type="submit" class="btn btn-solid" id="submit">Submit your film</button>
          <span class="hint" id="status-line"></span>
        </div>
      </form>
    </div>
  </div>
</section>
<script src="assets/config.js"></script>
<script src="assets/submit.js"></script>
""" % {
        "confirm": e(SUBMISSION_CONFIRMATION),
        "genres": opts(GENRE_OPTIONS),
        "dist_statuses": opts(DISTRIBUTION_STATUS_OPTIONS),
        "submit_email": "submit@velvetoctopusfilms.com",
        "submit_email_attr": "submit@velvetoctopusfilms.com",
    }
    return page(
        "Submit a film — %s" % SITE_NAME,
        body,
        "submit.html",
        description="Submit your independent film to Velvet Octopus Films for "
        "distribution consideration. Finished films only.",
    )


# --------------------------------------------------------------------------
# about
# --------------------------------------------------------------------------


def build_about(films):
    cfv = in_catalog(films, "best-b-movies")
    langs = sorted(
        {f["language"] for f in cfv if f["language"] and f["language"] != "English"}
    )
    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>About</h1></div>
    <div class="prose">
      <div class="todo-flag">
        <strong>TODO:</strong> Replace this placeholder with Velvet Octopus Films history and background.
      </div>

      <p>Velvet Octopus Films is an independent film library and distribution
        operation. We look after a collection of classic and contemporary films,
        put them in front of buyers, and stream them on YouTube and AVOD platforms.</p>

      <p>Every title page states which collection it comes from.</p>

      <h2>Best B Movies</h2>
      <p>%(cfv)d titles of classic Hollywood and international cinema, with the
        core concentrated in the 1930s through the 1970s. The American side runs
        deep on genre pictures: B-westerns and singing-cowboy series, studio film
        noir, the Rathbone-era Sherlock Holmes mysteries, and gothic horror and
        drive-in science fiction. The international side gathers landmark work
        from Japan, Italy, France, India, China, Russia, and Spain &mdash; films
        by Kurosawa, Ozu, Mizoguchi, Satyajit Ray, De Sica, Bu&ntilde;uel, and
        Tarkovsky among them, across %(nlang)d languages beyond English. These titles
        are offered for non-exclusive licensing across streaming, broadcast, and
        digital platforms.</p>

      <h2>Partner Collections</h2>
      <p>%(bf)d titles from Blue Finch Film Releasing and %(sc)d from SC Films
        International. Independent features, horror, thriller, family titles.
        We present them on their behalf &mdash; availability, territory, and terms
        confirmed direct with each company, per inquiry.</p>

      <p>We are a licensing and distribution operation only &mdash; this site is
        a catalog and a contact form, not a streaming service.</p>

      <p><a class="btn btn-solid" href="collections.html">Browse the collections</a></p>
    </div>
  </div>
</section>
""" % {
        "total": len(films),
        "cfv": len(cfv),
        "bf": len(in_catalog(films, "blue-finch")),
        "sc": len(in_catalog(films, "sc-films")),
        "nlang": len(langs),
    }
    return page(
        "About — %s" % SITE_NAME,
        body,
        "about.html",
    )


# --------------------------------------------------------------------------
# contact
# --------------------------------------------------------------------------


def build_contact():
    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>Contact</h1></div>
    <div class="prose">
      <p>We handle all inquiries by email. There&rsquo;s no live chat or
        booking calendar.</p>

      <h2>Licensing inquiries</h2>
      <p>To discuss a specific title or a package of titles, use the
        <a href="licensing.html">licensing inquiry form</a> &mdash; it asks the
        right questions up front and speeds up our reply.</p>

      <h2>Film submissions</h2>
      <p>If you have a film you&rsquo;d like us to consider, use the
        <a href="submit.html">film submission form</a>.</p>

      <h2>Everything else</h2>
      <p>Email us at
        <a href="mailto:hello@velvetoctopusfilms.com">hello@velvetoctopusfilms.com</a>.
        We read every message and reply when we can.</p>

      <h2>On TikTok</h2>
      <p>Short clips, rare footage, and scenes that hold up: follow
        <a href="%(tiktok)s" target="_blank" rel="noopener noreferrer">%(handle)s</a>.</p>
    </div>
  </div>
</section>
""" % {
        "tiktok": e(TIKTOK_URL),
        "handle": e(TIKTOK_HANDLE),
    }
    return page(
        "Contact — %s" % SITE_NAME,
        body,
        "contact.html",
        description="Contact Velvet Octopus Films for licensing inquiries, "
        "film submissions, or general questions.",
    )


# --------------------------------------------------------------------------
# privacy & terms
# --------------------------------------------------------------------------


def build_privacy():
    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>Privacy &amp; terms</h1></div>
    <div class="prose">
      <div class="todo-flag">
        <strong>TODO:</strong> Add your full privacy policy and terms of service here.
        The placeholder below covers the basics.
      </div>

      <h2>What we collect</h2>
      <p>When you submit a licensing inquiry or film submission, we collect
        the information you enter in the form (name, email, company, and the
        content of your message). We use it to reply to you and for nothing else.</p>

      <h2>Analytics</h2>
      <p>This site does not use analytics tracking. No cookies are set by this site.
        No third-party scripts load on any page.</p>

      <h2>Email</h2>
      <p>We use <a href="https://resend.com" target="_blank" rel="noopener noreferrer">Resend</a>
        to send transactional email (form acknowledgements). Resend receives the
        email address you provide when submitting a form. See
        <a href="https://resend.com/legal/privacy-policy" target="_blank" rel="noopener noreferrer">Resend&rsquo;s
        privacy policy</a> for how they handle that data.</p>

      <h2>Contact</h2>
      <p>Questions about this policy: <a href="mailto:hello@velvetoctopusfilms.com">hello@velvetoctopusfilms.com</a>.</p>
    </div>
  </div>
</section>
"""
    return page(
        "Privacy & terms — %s" % SITE_NAME,
        body,
        "privacy.html",
        description="Privacy policy and terms of service for Velvet Octopus Films.",
    )


# --------------------------------------------------------------------------
# 404
# --------------------------------------------------------------------------


def build_404():
    body = """
<section class="section section-cream">
  <div class="wrap not-found">
    <h1>404</h1>
    <p>That page doesn&rsquo;t exist &mdash; or it moved.</p>
    <a class="btn btn-solid" href="index.html">Back to the home page</a>
  </div>
</section>
"""
    return page(
        "Page not found — %s" % SITE_NAME,
        body,
        "",
        description="The page you were looking for doesn't exist.",
    )


# --------------------------------------------------------------------------
# catalog.html redirect (old URL → collections.html)
# --------------------------------------------------------------------------


def build_catalog_redirect():
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0;url=collections.html">
<link rel="canonical" href="collections.html">
<title>Redirecting…</title>
</head>
<body>
<p><a href="collections.html">Collections</a></p>
</body>
</html>
"""


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main():
    films = load()
    COUNTS["total"] = len(films)
    for c in CATALOGS:
        COUNTS[c["key"]] = len(in_catalog(films, c["key"]))

    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(os.path.join(DIST, "films"))
    shutil.copytree(ASSETS, os.path.join(DIST, "assets"))

    cname = os.path.join(HERE, "CNAME")
    if os.path.isfile(cname):
        shutil.copy2(cname, os.path.join(DIST, "CNAME"))

    def write(rel, content):
        path = os.path.join(DIST, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)

    write("index.html", build_home(films))
    write("collections.html", build_collections(films))
    write("catalog.html", build_catalog_redirect())  # old URL redirect
    write("browse.html", build_browse(films))
    write("licensing.html", build_licensing(films))
    write("submit.html", build_submit())
    write("about.html", build_about(films))
    write("contact.html", build_contact())
    write("privacy.html", build_privacy())
    write("404.html", build_404())

    for f in films:
        write(os.path.join("films", f["slug"] + ".html"), build_film(f, films))

    urls = [
        "index.html", "collections.html", "browse.html", "licensing.html",
        "submit.html", "about.html", "contact.html", "privacy.html",
    ]
    urls += ["films/%s.html" % f["slug"] for f in films]

    if SITE_BASE:
        write(
            "sitemap.xml",
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(
                "  <url><loc>%s/%s</loc></url>\n" % (SITE_BASE, u) for u in urls
            )
            + "</urlset>\n",
        )
        write(
            "robots.txt",
            "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % SITE_BASE,
        )
    else:
        write("robots.txt", "User-agent: *\nAllow: /\n")

    total_pages = len(urls) + (2 if SITE_BASE else 1)
    print("built %d pages into dist/" % total_pages)
    if not SITE_BASE:
        print("  no SITE_BASE set — sitemap.xml skipped")
    print("  %d film pages" % len(films))
    print("  preview:  python3 -m http.server -d dist 8000")


if __name__ == "__main__":
    main()
