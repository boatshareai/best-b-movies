#!/usr/bin/env python3
"""
Velvet Octopus Films — static site generator.

Reads data/*.csv and writes a complete static site to dist/.
Stdlib only; no pip install, no node_modules, no build toolchain.

    python3 build.py

Env vars:
  SITE_BASE    absolute origin, e.g. https://velvetoctopusfilms.com
               (required for canonical URLs and sitemap; omit for local dev)
  NOINDEX      set to any value to add <meta name="robots" content="noindex">
               (CI sets this for branch/preview deploys)
"""

import csv
import html
import json
import os
import re
import shutil
import subprocess
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
DIST = os.path.join(HERE, "dist")

SITE_BASE = os.environ.get("SITE_BASE", "").rstrip("/")
NOINDEX = bool(os.environ.get("NOINDEX", ""))

SITE_NAME = "Velvet Octopus Films"
SITE_TAGLINE = "Films worth a second look."
SITE_FOOT_TAGLINE = "Films worth a second look."
TIKTOK_URL = "https://www.tiktok.com/@thelostfilmfiles"
TIKTOK_HANDLE = "@thelostfilmfiles"
SITE_CONTACT_EMAIL = "hello@velvetoctopusfilms.com"
LICENSING_EMAIL = "licensing@velvetoctopusfilms.com"

OWN_CATALOG = "best-b-movies"

CATALOGS = [
    {
        "key": "best-b-movies",
        "name": "Velvet Octopus",
        "file": "catalog.csv",
        "prefix": "",
        "blurb": "Classic Hollywood and international cinema, 1930s to today"
                 " — westerns, noir, Rathbone-era mystery, gothic horror,"
                 " and art-house landmarks.",
        # one-line curatorial reason shown under carousel heading (Criterion pattern)
        "reason": "Our own library: films we represent directly for non-exclusive licensing.",
    },
    {
        "key": "blue-finch",
        "name": "Blue Finch Film Releasing",
        "file": "blue-finch.csv",
        "prefix": "bf",
        "blurb": "Contemporary independent features, weighted to the 2010s"
                 " and 2020s — led by horror, drama, and thriller.",
        "reason": "Presented on behalf of Blue Finch Film Releasing. Inquiries go to them.",
    },
    {
        "key": "sc-films",
        "name": "SC Films International",
        "file": "sc-films.csv",
        "prefix": "sc",
        "blurb": "Live action and family animation, plus documentary and"
                 " genre titles. Year and runtime data is largely absent.",
        "reason": "Presented on behalf of SC Films International. Inquiries go to them.",
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
    "with another platform — this doesn't prevent additional licensing, and "
    "any existing arrangement will be disclosed during the inquiry process. "
    "Reach out with the titles or volume you're interested in, and we'll follow "
    "up with availability, territory, and rate details."
)

CONFIRMATION = (
    "Thanks — we've got your inquiry and will follow up within a few "
    "business days with availability and terms. — Velvet Octopus Films"
)

SUBMISSION_CONFIRMATION = (
    "Thanks — we've received your submission and will be in touch "
    "if it's a good fit. — Velvet Octopus Films"
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
    "Drama", "Comedy", "Horror", "Thriller", "Action",
    "Animation", "Documentary", "Other",
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
            "Dead Man's Shoes",
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
    """Real key art when the row has a poster; title-text placeholder otherwise.
    alt="" is intentional: the title is always adjacent as real text."""
    name = (f.get("poster") or "").strip()
    if name:
        return (
            '<img src="%sassets/posters/%s" alt="" loading="lazy" '
            'decoding="async" width="%d" height="%d">' % (prefix, e(name), w, h)
        )
    return '<span class="card-typo-title" aria-hidden="true">%s</span>' % e(f["title"])


def poster_url(f, prefix=""):
    """Absolute URL for og:image when poster exists."""
    name = (f.get("poster") or "").strip()
    if name and SITE_BASE:
        return "%s/%sassets/posters/%s" % (SITE_BASE, prefix, urllib.parse.quote(name))
    return ""


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
            r["youtube_id"] = (r.get("youtube_id") or "").strip()
            r["why_watch"] = (r.get("why_watch") or "").strip()
            if r["slug"] in seen_slugs:
                raise SystemExit(
                    "duplicate slug %r in %s and %s"
                    % (r["slug"], seen_slugs[r["slug"]], cat["file"])
                )
            seen_slugs[r["slug"]] = cat["file"]
            # Auto-detect poster file if not set in CSV
            if not r.get("poster"):
                poster_path = os.path.join(ASSETS, "posters", r["slug"] + ".jpg")
                if os.path.isfile(poster_path):
                    r["poster"] = r["slug"] + ".jpg"
            films.append(r)
    films.sort(key=lambda f: f["title"].lower())
    if skipped:
        print("skipping %d title(s) marked publish=no" % skipped)
    return films


def in_catalog(films, key):
    return [f for f in films if f["catalog"] == key]


# --------------------------------------------------------------------------
# Organization JSON-LD (sitewide)
# --------------------------------------------------------------------------

ORG_JSONLD = json.dumps({
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Velvet Octopus Films",
    "url": "https://velvetoctopusfilms.com",
    "description": "An independent film library for licensing — classic Hollywood, international cinema, and contemporary independent features.",
    "sameAs": [TIKTOK_URL],
    "contactPoint": {
        "@type": "ContactPoint",
        "contactType": "licensing",
        "email": LICENSING_EMAIL,
    },
}, separators=(",", ":"))


def movie_jsonld(f):
    data = {
        "@context": "https://schema.org",
        "@type": "Movie",
        "name": f["title"],
    }
    if f["year"]:
        data["dateCreated"] = f["year"]
    if f["logline"]:
        data["description"] = f["logline"]
    if f["genre_list"]:
        data["genre"] = f["genre_list"]
    if f["language"]:
        data["inLanguage"] = f["language"]
    if f["runtime_n"]:
        data["duration"] = "PT%dM" % f["runtime_n"]
    dir_val = (f.get("director") or "").strip()
    if dir_val:
        data["director"] = [
            {"@type": "Person", "name": n.strip()}
            for n in dir_val.split(",")
            if n.strip()
        ]
    if SITE_BASE:
        data["url"] = "%s/films/%s.html" % (SITE_BASE, f["slug"])
    p = (f.get("poster") or "").strip()
    if p and SITE_BASE:
        data["image"] = "%s/assets/posters/%s" % (SITE_BASE, urllib.parse.quote(p))
    if f["youtube_id"]:
        data["trailer"] = {
            "@type": "VideoObject",
            "embedUrl": "https://www.youtube-nocookie.com/embed/%s" % f["youtube_id"],
        }
    return json.dumps(data, separators=(",", ":"))


# --------------------------------------------------------------------------
# layout
# --------------------------------------------------------------------------

NAV = [
    ("Films", "browse.html"),
    ("Collections", "collections.html"),
    ("Watch", "watch.html"),
    ("License", "licensing.html"),
    ("About", "about.html"),
]

# No CTA button, no "Submit a film" in nav — only the links above.


def page(title, body, current, depth=0, description="",
         canonical_path="", ogimg_override="", extra_jsonld="",
         is_home=False):
    up = "../" * depth
    nav_links = []
    for label, href in NAV:
        cur = ' aria-current="page"' if href == current else ""
        nav_links.append('<a href="%s%s"%s>%s</a>' % (up, href, cur, label))
    nav_str = "\n    ".join(nav_links)

    desc = description or (
        "%d films across three collections — classic Hollywood, international "
        "cinema, and contemporary independent features — available for "
        "licensing across streaming, broadcast, and digital platforms."
        % COUNTS["total"]
    )

    # Canonical URL
    canon_path = canonical_path or current
    canonical_tag = ""
    if SITE_BASE and canon_path:
        canonical_tag = '<link rel="canonical" href="%s/%s">\n' % (SITE_BASE, canon_path)

    # robots
    robots = "noindex, nofollow" if NOINDEX else "index, follow"

    # og:image — use provided override, else site-level og-image
    ogimg_url = ogimg_override
    if not ogimg_url and SITE_BASE:
        ogimg_url = "%s/assets/og-image.png" % SITE_BASE
    ogimg_tags = ""
    if ogimg_url:
        ogimg_tags = (
            '<meta property="og:image" content="%s">\n'
            '<meta property="og:image:width" content="1200">\n'
            '<meta property="og:image:height" content="630">\n'
            '<meta name="twitter:card" content="summary_large_image">\n' % e(ogimg_url)
        )

    # JSON-LD: always include org; include extra (Movie) when provided
    jsonld_blocks = (
        '<script type="application/ld+json">%s</script>\n' % ORG_JSONLD
    )
    if extra_jsonld:
        jsonld_blocks += '<script type="application/ld+json">%s</script>\n' % extra_jsonld

    # Body class: page-home enables absolute header overlay on hero
    body_class = ' class="page-home"' if is_home else ""

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<meta name="robots" content="%(robots)s">
%(canonical)s<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:site_name" content="%(site)s">
<meta property="og:type" content="website">
%(ogimg)s%(jsonld)s<link rel="icon" type="image/svg+xml" href="%(up)sassets/favicon.svg">
<link rel="icon" type="image/x-icon" href="%(up)sassets/favicon.ico">
<link rel="apple-touch-icon" href="%(up)sassets/apple-touch-icon.png">
<meta name="theme-color" content="#5B2A86">
<link rel="preload" href="%(up)sassets/fonts/InstrumentSerif-Regular.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="%(up)sassets/fonts/Inter-Variable.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="%(up)sassets/site.css">
</head>
<body%(body_class)s>
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <a class="logo" href="%(up)sindex.html" aria-label="Velvet Octopus Films, home">
    <img src="%(up)sassets/brand/logo-wordmark-films.svg" alt="Velvet Octopus Films" width="160" height="44">
  </a>
  <nav class="nav" aria-label="Main">
    %(nav)s
    <a class="icon-btn" href="%(up)sbrowse.html" aria-label="Search films">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l5 5"/></svg>
    </a>
  </nav>
  <button class="nav-mobile-btn" aria-label="Menu" aria-expanded="false" aria-controls="mobile-nav">
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M3 8h18M3 16h18"/></svg>
  </button>
</header>
<main id="main">
%(body)s
</main>
<footer class="site-footer">
  <div class="foot-top">
    <div>
      <img src="%(up)sassets/brand/logo-wordmark-films.svg" alt="Velvet Octopus Films" width="140" height="34" loading="lazy">
      <p class="tagline">Films worth a second look.</p>
    </div>
    <nav class="foot-links" aria-label="Footer">
      <a href="%(up)sbrowse.html">Films</a>
      <a href="%(up)scollections.html">Collections</a>
      <a href="%(up)swatch.html">Watch</a>
      <a href="%(up)slicensing.html">License</a>
      <a href="%(up)ssubmit.html">Submit a film</a>
      <a href="%(up)sabout.html">About</a>
      <a href="%(up)scontact.html">Contact</a>
      <a href="%(up)sprivacy.html">Privacy and terms</a>
    </nav>
  </div>
  <p class="copy">&copy; %(year)d Velvet Octopus Films</p>
</footer>
</body>
</html>
""" % {
        "title": e(title),
        "desc": e(desc),
        "nav": nav_str,
        "body": body,
        "up": up,
        "site": e(SITE_NAME),
        "robots": robots,
        "canonical": canonical_tag,
        "ogimg": ogimg_tags,
        "jsonld": jsonld_blocks,
        "year": 2026,
        "body_class": body_class,
    }


# --------------------------------------------------------------------------
# stills helpers
# --------------------------------------------------------------------------


def still_exists(slug):
    """Return True if assets/stills/<slug>.webp is present."""
    return os.path.isfile(os.path.join(ASSETS, "stills", slug + ".webp"))


def still_width(slug):
    """Return pixel width of assets/stills/<slug>.webp using sips, or 0 on error."""
    path = os.path.join(ASSETS, "stills", slug + ".webp")
    if not os.path.isfile(path):
        return 0
    try:
        result = subprocess.run(
            ["sips", "-g", "pixelWidth", path],
            capture_output=True, text=True, check=True,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("pixelWidth:"):
                return int(line.split(":")[1].strip())
    except Exception:
        pass
    return 0


def load_posters_csv():
    """Return dict keyed by slug from data/posters.csv, or {} if file absent."""
    path = os.path.join(HERE, "data", "posters.csv")
    if not os.path.exists(path):
        return {}
    result = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            slug = (row.get("slug") or "").strip()
            if slug:
                result[slug] = {k: v.strip() for k, v in row.items()}
    return result


def poster_file_exists(slug):
    """Return True if assets/posters/<slug>.jpg was imported (exists on disk)."""
    return os.path.isfile(os.path.join(ASSETS, "posters", slug + ".jpg"))


def shelf_card_html(f, up=""):
    """Poster card > still card > typographic fallback for a shelf."""
    slug = f["slug"]
    title = f["title"]
    year = f.get("year", "")
    genres = f.get("genre_list", [])
    genre_part = (" · " + genres[0]) if genres else ""
    film_url = "%sfilms/%s.html" % (up, e(slug))

    if f.get("poster"):
        return """<a class="card card-poster" href="%(film_url)s">
  <div class="thumb">
    <img src="%(up)sassets/posters/%(poster)s"
         srcset="%(up)sassets/posters/%(poster_480)s 480w, %(up)sassets/posters/%(poster)s 960w"
         sizes="(max-width:599px) 72vw, (max-width:899px) 42vw, 25vw"
         loading="lazy" decoding="async"
         alt="Poster for %(title_e)s (%(year_e)s)">
  </div>
  <h3>%(title_e)s</h3>
  <p>%(year_e)s%(genre_part)s</p>
</a>""" % {
            "film_url": film_url,
            "up": up,
            "poster": e(f["poster"]),
            "poster_480": e(f["poster"].replace(".jpg", "-480.jpg")),
            "title_e": e(title),
            "year_e": e(year),
            "genre_part": e(genre_part),
        }
    elif still_exists(slug):
        return """<a class="card" href="%(film_url)s">
  <div class="thumb">
    <img src="%(up)sassets/stills/%(slug)s.webp"
         srcset="%(up)sassets/stills/%(slug)s-480.webp 480w, %(up)sassets/stills/%(slug)s.webp 960w"
         sizes="(max-width:599px) 72vw, (max-width:899px) 42vw, 25vw"
         width="960" height="540" loading="lazy" decoding="async"
         alt="Still from %(title_e)s (%(year_e)s)">
  </div>
  <h3>%(title_e)s</h3>
  <p>%(year_e)s%(genre_part)s</p>
</a>""" % {
            "film_url": film_url,
            "up": up,
            "slug": e(slug),
            "title_e": e(title),
            "year_e": e(year),
            "genre_part": e(genre_part),
        }
    else:
        return """<a class="card card-typo" href="%(film_url)s">
  <div class="thumb thumb-typo">
    <span class="typo-title">%(title_e)s</span>
    <span class="typo-year">%(year_e)s</span>
  </div>
  <h3>%(title_e)s</h3>
  <p>%(year_e)s%(genre_part)s</p>
</a>""" % {
            "film_url": film_url,
            "title_e": e(title),
            "year_e": e(year),
            "genre_part": e(genre_part),
        }


def filter_films_for_shelf(films, filter_spec):
    """Filter films according to a shelf filter spec string."""
    if filter_spec == "has_still":
        return [f for f in films if still_exists(f["slug"])]
    if filter_spec.startswith("genre:"):
        genres = filter_spec[6:].split(",")
        return [f for f in films if any(g in f["genre_list"] for g in genres)]
    if filter_spec == "lang:non-english":
        return [f for f in films if f.get("language") and f["language"] != "English"]
    return films


def build_shelves_html(films):
    """Build all shelf sections from shelves.json. Returns (html, hidden_shelf_ids)."""
    shelf_config_path = os.path.join(HERE, "shelves.json")
    if not os.path.isfile(shelf_config_path):
        return "", []
    with open(shelf_config_path, encoding="utf-8") as fh:
        shelf_configs = json.load(fh)

    hidden = []
    shelf_sections = []

    for cfg in shelf_configs:
        raw = filter_films_for_shelf(films, cfg["filter"])
        # Sort genre and lang shelves by year ascending so classic films appear first
        if cfg["filter"] != "has_still":
            raw = sorted(raw, key=lambda f: f.get("year") or "9999")
        filtered = raw[:cfg["max"]]
        if len(filtered) < 6:
            hidden.append(cfg["id"])
            continue

        cards_html = "\n".join(shelf_card_html(f) for f in filtered)

        # Build "see all" link
        filt = cfg["filter"]
        if filt == "has_still":
            see_href = "browse.html?yt=1"
        elif filt.startswith("genre:"):
            primary_genre = filt[6:].split(",")[0]
            see_href = "browse.html?genre=%s" % urllib.parse.quote(primary_genre)
        elif filt == "lang:non-english":
            see_href = "browse.html?intl=1"
        else:
            see_href = "browse.html"

        shelf_id = "shelf-%s" % cfg["id"]
        reason_p = ('<p>%s</p>' % e(cfg["reason"])) if cfg.get("reason") else ""
        shelf_sections.append("""<section class="shelf" aria-labelledby="%(shelf_id)s">
  <div class="shelf-head">
    <div>
      <h2 id="%(shelf_id)s">%(title)s</h2>
      %(reason_p)s
    </div>
    <a class="link-all" href="%(see_href)s">See all</a>
  </div>
  <div class="row">%(cards)s</div>
</section>""" % {
            "shelf_id": shelf_id,
            "title": e(cfg["title"]),
            "see_href": see_href,
            "reason_p": reason_p,
            "cards": cards_html,
        })

    html_out = ""
    if shelf_sections:
        html_out = "\n".join(shelf_sections)

    return html_out, hidden


# --------------------------------------------------------------------------
# home
# --------------------------------------------------------------------------


def featured_card(f, prefix=""):
    art = poster_art(f, prefix=prefix)
    bcls = badge(f["status"])[0]
    btxt = f["status"] or "Available"
    yt_dot = ""
    if f.get("youtube_id"):
        yt_dot = '\n            <span class="status-dot badge-yt">YouTube</span>'
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
        "yt_dot": yt_dot,
        "title": e(f["title"]),
        "year": e(f["year"]) or "Year not listed",
    }


def band_shade(i):
    return "section-cream" if i % 2 == 0 else "section-white"


def build_featured(films, keys=None, start=0, as_index=False):
    """Criterion-pattern carousels: heading + one-line reason + poster row."""
    by_key = {(f["title"].strip().lower(), f["catalog"]): f for f in films}
    sections = []
    for cat_key, heading, titles in FEATURED:
        if keys is not None and cat_key not in keys:
            continue
        cards = []
        for want in titles:
            want_norm = want.strip().lower().replace("'", "'").replace("'", "'")
            f = None
            for (title_lower, ckey), film in by_key.items():
                if ckey == cat_key and title_lower.replace("'", "'").replace("'", "'") == want_norm:
                    f = film
                    break
            if f is None:
                raise SystemExit(
                    "featured title %r not in %s catalog (renamed, removed, or publish=no). "
                    "Fix FEATURED in build.py." % (want, cat_key)
                )
            cards.append(featured_card(f))
        n = len(in_catalog(films, cat_key))
        cat = CATALOG_BY_KEY[cat_key]
        if as_index:
            heading = cat["name"]
            kicker = (
                "Our own library"
                if cat_key == OWN_CATALOG
                else "Represented collection"
            )
            eyebrow = '    <p class="cat-eyebrow">%s</p>\n' % e(kicker)
            # blurb = full description; reason = one-line curation note
            line = '    <p class="cat-line">%d titles. %s</p>\n' % (
                n, e(cat["blurb"])
            )
            link = "Browse this collection &rsaquo;"
        else:
            eyebrow = ""
            # On home page: one-line reason under the heading (Criterion pattern)
            line = '    <p class="cat-reason muted">%s</p>\n' % e(cat["reason"])
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
    cfv = in_catalog(films, "best-b-movies")

    # --- Check for hero.json override ---
    hero_json_path = os.path.join(ASSETS, "hero", "hero.json")
    hero_webp_path = os.path.join(ASSETS, "hero", "hero.webp")
    use_hero_json = os.path.isfile(hero_json_path) and os.path.isfile(hero_webp_path)

    # Collect all stills for the slideshow, putting hero.json film first
    hero_slug_first = ""
    if use_hero_json:
        with open(hero_json_path, encoding="utf-8") as fh:
            hj = json.load(fh)
        hero_slug_first = (hj.get("slug") or "").strip()

    slide_films = []
    # Pin hero.json film first if it has a still
    if hero_slug_first:
        for f in cfv:
            if f["slug"] == hero_slug_first and still_exists(f["slug"]):
                slide_films.append(f)
                break
    # Add remaining stills in catalog order
    for f in cfv:
        if still_exists(f["slug"]) and f not in slide_films:
            slide_films.append(f)

    if len(slide_films) >= 2:
        # Build crossfading slideshow
        slides_html_parts = []
        for i, sf in enumerate(slide_films):
            active_cls = " active" if i == 0 else ""
            priority = 'fetchpriority="high"' if i == 0 else 'loading="lazy"'
            # Use hero.webp (higher res) for the first/pinned slide when available
            if i == 0 and use_hero_json and os.path.isfile(hero_webp_path):
                src = "assets/hero/hero.webp"
                srcset = "assets/hero/hero-1280.webp 1280w, assets/hero/hero.webp 1920w"
            else:
                src = "assets/stills/%s.webp" % sf["slug"]
                srcset = "assets/stills/%(s)s-480.webp 480w, assets/stills/%(s)s.webp 1280w" % {"s": sf["slug"]}
            slides_html_parts.append(
                '  <img class="hero-img hero-slide%(active)s" %(priority)s decoding="async"\n'
                '       src="%(src)s" srcset="%(srcset)s" sizes="100vw"\n'
                '       data-title="%(title)s" data-year="%(year)s" data-slug="%(slug)s"\n'
                '       alt="Still from %(title)s (%(year)s)">' % {
                    "active": active_cls,
                    "priority": priority,
                    "src": src,
                    "srcset": srcset,
                    "title": e(sf["title"]),
                    "year": e(sf.get("year", "")),
                    "slug": e(sf["slug"]),
                }
            )
        slides_html = "\n".join(slides_html_parts)

        first = slide_films[0]
        featured_credit = (
            '<p class="featured"><span class="tag">Featured</span> '
            '<a class="hero-film-link" href="films/%(slug)s.html">'
            '<b class="hero-film-name">%(title)s (%(year)s)</b></a></p>'
        ) % {"slug": e(first["slug"]), "title": e(first["title"]), "year": e(first.get("year", ""))}

        hero_section = """<section class="hero">
%(slides)s
  <div class="hero-inner">
    <p class="eyebrow">Velvet Octopus Films</p>
    <h1>A library of<br>classic films.</h1>
    <p class="sub">%(total)d films, from 1930s Hollywood noir and B-westerns to landmark world cinema. Watch on YouTube, or license a film for your platform.</p>
    <div class="actions">
      <a class="btn btn-gold" href="browse.html">Browse the films</a>
      <a class="btn btn-line" href="licensing.html">License a film</a>
    </div>
    %(featured_credit)s
  </div>
  <script>
(function(){
  var slides=Array.from(document.querySelectorAll('.hero .hero-slide'));
  if(slides.length<2)return;
  var cur=0,nameEl=document.querySelector('.hero-film-name'),linkEl=document.querySelector('.hero-film-link');
  setInterval(function(){
    slides[cur].classList.remove('active');
    cur=(cur+1)%%slides.length;
    var s=slides[cur];
    s.classList.add('active');
    if(nameEl)nameEl.textContent=s.dataset.title+' ('+s.dataset.year+')';
    if(linkEl)linkEl.href='films/'+s.dataset.slug+'.html';
  },6000);
})();
  </script>
</section>""" % {
            "slides": slides_html,
            "total": total,
            "featured_credit": featured_credit,
        }

    elif len(slide_films) == 1:
        sf = slide_films[0]
        src = "assets/hero/hero.webp" if (use_hero_json and os.path.isfile(hero_webp_path)) else "assets/stills/%s.webp" % sf["slug"]
        srcset = ("assets/hero/hero-1280.webp 1280w, assets/hero/hero.webp 1920w"
                  if (use_hero_json and os.path.isfile(hero_webp_path))
                  else "assets/stills/%(s)s-480.webp 480w, assets/stills/%(s)s.webp 1280w" % {"s": sf["slug"]})
        featured_credit = (
            '<p class="featured"><span class="tag">Featured</span> '
            '<a href="films/%(slug)s.html"><b>%(title)s (%(year)s)</b></a></p>'
        ) % {"slug": e(sf["slug"]), "title": e(sf["title"]), "year": e(sf.get("year", ""))}
        hero_section = """<section class="hero">
  <img class="hero-img" src="%(src)s" srcset="%(srcset)s" sizes="100vw"
       fetchpriority="high" decoding="async" alt="Still from %(title)s (%(year)s)">
  <div class="hero-inner">
    <p class="eyebrow">Velvet Octopus Films</p>
    <h1>A library of<br>classic films.</h1>
    <p class="sub">%(total)d films, from 1930s Hollywood noir and B-westerns to landmark world cinema. Watch on YouTube, or license a film for your platform.</p>
    <div class="actions">
      <a class="btn btn-gold" href="browse.html">Browse the films</a>
      <a class="btn btn-line" href="licensing.html">License a film</a>
    </div>
    %(featured_credit)s
  </div>
</section>""" % {"src": src, "srcset": srcset, "title": e(sf["title"]), "year": e(sf.get("year", "")),
                  "total": total, "featured_credit": featured_credit}
    else:
        # No stills at all
        hero_section = """<section class="hero hero-no-still">
  <div class="hero-inner">
    <img class="hero-logo-bg" src="assets/brand/logo-icon-simple.svg" alt="" aria-hidden="true" width="320" height="320">
    <p class="eyebrow">Velvet Octopus Films</p>
    <h1>A library of<br>classic films.</h1>
    <p class="sub">%(total)d films, from 1930s Hollywood noir and B-westerns to landmark world cinema. Watch on YouTube, or license a film for your platform.</p>
    <div class="actions">
      <a class="btn btn-gold" href="browse.html">Browse the films</a>
      <a class="btn btn-line" href="licensing.html">License a film</a>
    </div>
  </div>
</section>""" % {"total": total}

    # Shelves
    shelves_html, hidden_shelves = build_shelves_html(films)

    # Browse by decade grid — only decades with >= 1 film
    decades = sorted({f["decade"] for f in films if f["decade"]})
    decade_links = "\n    ".join(
        '<a href="browse.html?decade=%(d)s"><span>%(d)s</span><i aria-hidden="true">→</i></a>' % {"d": e(d)}
        for d in decades
    )

    body = """%(hero)s

%(shelves)s

<section class="shelf decades" aria-labelledby="decades-head">
  <div class="shelf-head" style="padding-inline:0">
    <h2 id="decades-head">Browse by decade</h2>
  </div>
  <div class="decade-grid">
    %(decade_links)s
  </div>
</section>

<section class="band">
  <div class="band-inner">
    <div>
      <h2>Looking to license?</h2>
      <p>We license our library for streaming, broadcast and digital platforms. Territory and term are set per deal.</p>
    </div>
    <a class="btn btn-line" href="licensing.html">Start an inquiry</a>
  </div>
</section>
""" % {
        "hero": hero_section,
        "shelves": shelves_html,
        "decade_links": decade_links,
    }

    return page(
        "Velvet Octopus Films — a library of classic films",
        body,
        "index.html",
        canonical_path="index.html",
        description="An independent film library for licensing. %d titles across "
        "classic Hollywood, international cinema, and contemporary "
        "independent features." % total,
        is_home=True,
    )


# --------------------------------------------------------------------------
# collections
# --------------------------------------------------------------------------


COLLECTION_DESCRIPTIONS = {
    "best-b-movies": "Classic Hollywood westerns, noir, mystery and horror alongside landmark international cinema from Japan, Italy, France, India and beyond.",
    "blue-finch": "Contemporary independent features from the 2010s and 2020s, led by horror, drama and thriller.",
    "sc-films": "Live action, family animation, documentary and genre titles from an international rights catalog.",
}


def build_collections(films):
    # Build collection summary rows
    collection_rows = []
    for cat in CATALOGS:
        n = len(in_catalog(films, cat["key"]))
        desc = COLLECTION_DESCRIPTIONS.get(cat["key"], cat["blurb"])
        collection_rows.append(
            '<div class="collection-row"><h3>%s</h3><p class="label-caps">%d titles</p>'
            '<p class="lede">%s</p>'
            '<a class="btn btn-line" href="browse.html?catalog=%s">Browse</a></div>'
            % (e(cat["name"]), n, e(desc), urllib.parse.quote(cat["key"]))
        )

    # Poster strip — pick genre-diverse images we have on disk
    _strip_candidates = [
        ("stagecoach-1939.jpg",             "Stagecoach (1939)"),
        ("house-of-usher-1960.jpg",         "House of Usher (1960)"),
        ("ikiru-1952.jpg",                  "Ikiru (1952)"),
        ("charade-1963.jpg",                "Charade (1963)"),
        ("the-rules-of-the-game-1939.jpg",  "The Rules of the Game (1939)"),
        ("the-quiet-man-1952.jpg",          "The Quiet Man (1952)"),
        ("drunken-angel-1948.jpg",          "Drunken Angel (1948)"),
        ("mirror-1975.jpg",                 "Mirror (1975)"),
        ("shock-corridor-1963.jpg",         "Shock Corridor (1963)"),
        ("sansho-the-bailiff-1954.jpg",     "Sansho the Bailiff (1954)"),
    ]
    _strip_imgs = []
    for fname, alt in _strip_candidates:
        if os.path.isfile(os.path.join(ASSETS, "posters", fname)):
            _strip_imgs.append(
                '<img src="assets/posters/%s" alt="%s" loading="lazy" decoding="async">'
                % (e(fname), e(alt))
            )
    poster_strip = "\n    ".join(_strip_imgs)

    body = """
<div class="coll-hero">
  <div class="coll-poster-strip" aria-hidden="true">
    %(poster_strip)s
  </div>
  <div class="coll-hero-text">
    <h1>Collections</h1>
    <p>%(total)d titles across three collections — our own library,
      plus two we present on behalf of their rights holders.</p>
    <a class="btn btn-gold" href="browse.html">Search all titles</a>
  </div>
</div>
%(rows)s
""" % {
        "total": len(films),
        "rows": build_featured(films, as_index=True, start=1),
        "poster_strip": poster_strip,
    }

    return page(
        "Collections — %s" % SITE_NAME,
        body,
        "collections.html",
        canonical_path="collections.html",
        description="Three collections totalling %d titles: Velvet Octopus, "
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
      <a href="collections.html">Browse by collection</a> instead, or filter below.</p>
  </div>
</section>

<form class="filters" id="filters" role="search" aria-label="Filter titles">
  <div class="wrap">
    <div class="filter-row">
      <label class="vh" for="q">Search</label>
      <input type="search" id="q" name="q" class="filter-search"
             placeholder="Search titles and loglines&hellip;" autocomplete="off">
      <label class="vh" for="catalog">Collection</label>
      <select id="catalog" class="filter-pill">
        <option value="">All collections</option>%(cats)s
      </select>
      <label class="vh" for="genre">Genre</label>
      <select id="genre" class="filter-pill">
        <option value="">All genres</option>%(genres)s
      </select>
      <label class="vh" for="decade">Decade</label>
      <select id="decade" class="filter-pill">
        <option value="">All decades</option>%(decades)s
        <option value="__none">Not listed</option>
      </select>
      <label class="vh" for="lang">Language</label>
      <select id="lang" class="filter-pill">
        <option value="">All languages</option>%(langs)s
        <option value="__none">Not specified</option>
      </select>
      <label class="vh" for="runtime">Runtime</label>
      <select id="runtime" class="filter-pill">
        <option value="">Any runtime</option>
        <option value="0-79">Under 80 min</option>
        <option value="80-99">80&ndash;99 min</option>
        <option value="100-119">100&ndash;119 min</option>
        <option value="120-999">120 min+</option>
        <option value="__none">Not listed</option>
      </select>
      <label class="vh" for="status">Status</label>
      <select id="status" class="filter-pill">
        <option value="">Any status</option>%(statuses)s
      </select>
      <label class="filter-check">
        <input type="checkbox" id="yt" name="yt" value="1">
        YouTube
      </label>
      <label class="filter-check">
        <input type="checkbox" id="intl" name="intl" value="1">
        Non-English
      </label>
      <label class="vh" for="sort">Sort</label>
      <select id="sort" class="filter-pill">
        <option value="t">A &ndash; Z</option>
        <option value="y_desc">Newest first</option>
        <option value="y_asc">Oldest first</option>
      </select>
    </div>
    <div class="filter-foot">
      <span class="result-count" id="count" role="status" aria-live="polite"></span>
      <button type="button" class="link-btn" id="reset">Clear</button>
    </div>
  </div>
</form>

<section class="section">
  <div class="wrap">
    <div class="card-grid" id="rows" aria-live="polite" aria-label="Search results"></div>
    <div class="empty" id="empty" hidden>
      <strong>No titles match those filters.</strong>
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
        canonical_path="browse.html",
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
    """Click-to-play embed. Iframe loads from yt-embed.js on user click only."""
    vid = e(youtube_id)
    return """
    <div class="yt-wrap">
      <button class="yt-trigger" type="button" data-yt-id="%(vid)s"
        aria-label="Watch on YouTube — opens player">
        <span class="yt-play-icon" aria-hidden="true">&#9654;</span>
        <span>Watch on YouTube</span>
      </button>
    </div>""" % {"vid": vid}


def build_film(f, films, posters_dict=None):
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

    # Catalog attribution strip (Kino Lorber pattern: clear catalog credit)
    rep = (
        '<a class="rep-tag" href="../browse.html?catalog=%s">'
        '<span>Represented by</span> %s</a>'
        % (urllib.parse.quote(f["catalog"]), e(f["catalog_name"]))
    )
    catalog_id_tag = '<span class="catalog-id">%s</span>' % e(f["catalog_name"])

    spec = [("Collection", f["catalog_name"])]
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
            f["decade"], e(f["decade"]),
        )

    synopsis = (
        '<p class="synopsis">%s</p>' % e(f["logline"])
        if f["logline"]
        else '<p class="synopsis muted">No synopsis on file. We can supply one on request.</p>'
    )

    # why_watch (curator note, shown only when filled)
    why_block = ""
    if f.get("why_watch"):
        why_block = """
      <div class="why-watch">
        <span class="why-label">Why watch</span>
        %s
      </div>""" % e(f["why_watch"])

    # Poster beside facts (imported via import_posters.py / find_posters.py)
    slug = f["slug"]
    if posters_dict is None:
        posters_dict = {}
    facts_poster_html = ""
    if poster_file_exists(slug):
        poster_row = posters_dict.get(slug, {})
        poster_credit = ""
        author = (poster_row.get("author") or "").strip()
        license_txt = (poster_row.get("license") or "").strip()
        if author or license_txt:
            parts = [p for p in [author, license_txt] if p]
            poster_credit = " / ".join(parts)
        poster_credit_html = (
            '<p class="poster-credit">%s</p>' % e(poster_credit)
            if poster_credit else ""
        )
        facts_poster_html = (
            '<div class="film-facts-poster">'
            '<img src="../assets/posters/%(slug)s.jpg"'
            ' srcset="../assets/posters/%(slug)s-480.jpg 480w,'
            ' ../assets/posters/%(slug)s.jpg 1000w"'
            ' sizes="(max-width:767px) 140px, 180px"'
            ' width="180" height="270" loading="lazy" decoding="async"'
            ' alt="Poster for %(title)s">'
            '%(credit)s'
            '</div>'
        ) % {
            "slug": e(slug),
            "title": e(f["title"]),
            "credit": poster_credit_html,
        }

    # Blurred backdrop (CSS-only, CSP-safe: img-src 'self')
    poster_name = (f.get("poster") or "").strip()
    if poster_name:
        backdrop_html = (
            '<div class="film-backdrop">'
            '<img class="backdrop-img" src="../assets/posters/%s" alt="" aria-hidden="true">'
            '</div>' % e(poster_name)
        )
    else:
        backdrop_html = ""

    # Full-width still hero (above main content)
    slug = f["slug"]
    if still_exists(slug):
        film_hero_html = (
            '<div class="film-hero">'
            '<img src="../assets/stills/%(slug)s.webp" '
            'srcset="../assets/stills/%(slug)s-480.webp 480w, ../assets/stills/%(slug)s.webp 960w" '
            'sizes="100vw" width="960" height="540" '
            'alt="Still from %(title)s (%(year)s)" '
            'loading="eager" decoding="async">'
            '<div class="film-hero-fade"></div>'
            '</div>' % {
                "slug": e(slug),
                "title": e(f["title"]),
                "year": e(f["year"]),
            }
        )
        # Use still as og:image if no poster
    else:
        film_hero_html = ""

    # CTAs: Watch (yt-trigger) + License side by side in film-head
    yt_id = f.get("youtube_id", "")
    inquire_qs = urllib.parse.urlencode({
        "title": f["title"],
        "catalog": f["catalog_name"],
    })
    inquire = "../licensing.html?" + inquire_qs
    source_url = (f.get("source_url") or "").strip()

    if yt_id:
        watch_btn = (
            '<button class="btn btn-gold yt-trigger" type="button" '
            'data-yt-id="%(vid)s" aria-label="Watch on YouTube — opens player">'
            '<span class="yt-play-icon" aria-hidden="true">&#9654;</span> Watch'
            '</button>' % {"vid": e(yt_id)}
        )
        watch_script = '\n<script src="../assets/yt-embed.js"></script>'
    else:
        watch_btn = ""
        watch_script = ""

    if f["catalog"] != "best-b-movies" and source_url:
        license_btn = (
            '<a class="btn btn-line btn-ext" href="%(url)s" '
            'target="_blank" rel="noopener noreferrer">License via %(name)s'
            '<span class="vh"> (opens in a new tab)</span></a>'
            % {"name": e(f["catalog_name"]), "url": e(source_url)}
        )
        cta = (
            "<p>Territory and term are negotiated per deal. %(name)s handles "
            "enquiries for this title — their page carries the current details.</p>\n"
            '      <a class="btn btn-line btn-ext" href="%(url)s" '
            'target="_blank" rel="noopener noreferrer">View on %(name)s'
            '<span class="vh"> (opens in a new tab)</span></a>'
            % {"name": e(f["catalog_name"]), "url": e(source_url)}
        )
    else:
        license_btn = '<a class="btn btn-line" href="%s">License this film</a>' % e(inquire)
        cta = (
            "<p>Territory and term are negotiated per deal. "
            "Send us this title and we'll come back with availability and rates.</p>\n"
            '      <a class="btn btn-line" href="%s">License this film</a>' % e(inquire)
        )

    ctas_html = ""
    if watch_btn or license_btn:
        ctas_html = '<div class="film-ctas">%s%s</div>' % (watch_btn, license_btn)

    # Related films: same genre, same catalog, up to 5
    related_genres = f["genre_list"][:1]
    related = [
        r for r in films
        if r["slug"] != f["slug"]
        and r["catalog"] == f["catalog"]
        and any(g in r["genre_list"] for g in related_genres)
    ][:5]
    related_html = ""
    if related:
        rcards = "\n".join(featured_card(r, prefix="../") for r in related)
        related_html = """
<section class="section section-white">
  <div class="wrap">
    <div class="rule-head"><h2>More from this collection</h2></div>
    <div class="related-grid">
%s
    </div>
  </div>
</section>""" % rcards

    body = """
%(backdrop)s%(film_hero)s
<section class="film-head">
  <div class="wrap">
    <p class="crumbs"><a href="../index.html">Home</a> &rsaquo;
      <a href="../browse.html">Browse</a> &rsaquo; %(title)s</p>
    <div class="film-head-grid">
      <span class="poster film-poster">%(art)s</span>
      <div>
        <div class="catalog-strip">%(catalog_id)s</div>
        <h1>%(title)s</h1>
        <div class="film-meta">%(meta)s</div>
        <span class="badge %(bcls)s badge-lg">%(btxt)s</span>
        %(rep)s
        %(ctas)s
      </div>
    </div>
  </div>
</section>

<div class="wrap">
  <div class="film-body">
    <div>
      %(why_block)s
      <h2>Synopsis</h2>
      %(synopsis)s

      <h2>Details</h2>
      <div class="film-facts-row">
        <dl class="spec">
    %(spec)s
        </dl>
        %(facts_poster)s
      </div>

      <h2 class="browse-similar-head">Browse similar</h2>
      <div class="tag-row">%(tags)s</div>
    </div>

    <aside class="aside-card">
      <h2>License this film</h2>
      <p>%(licence_note)s</p>
      %(cta)s
    </aside>
  </div>
</div>
%(related)s%(watch_script)s
""" % {
        "title": e(f["title"]),
        "meta": meta_html,
        "art": poster_art(f, prefix="../"),
        "bcls": badge_cls,
        "btxt": e(badge_txt),
        "synopsis": synopsis,
        "rep": rep,
        "catalog_id": catalog_id_tag,
        "spec": spec_html,
        "tags": tags,
        "licence_note": e(f["licence_note"]),
        "cta": cta,
        "ctas": ctas_html,
        "backdrop": backdrop_html,
        "film_hero": film_hero_html,
        "why_block": why_block,
        "related": related_html,
        "watch_script": watch_script,
        "facts_poster": facts_poster_html,
    }

    year = " (%s)" % f["year"] if f["year"] else ""
    slug_path = "films/%s.html" % f["slug"]
    # og:image: prefer still, then poster, then site default
    og_img = ""
    if still_exists(f["slug"]) and SITE_BASE:
        og_img = "%s/assets/stills/%s.webp" % (SITE_BASE, urllib.parse.quote(f["slug"]))
    if not og_img:
        og_img = poster_url(f)
    return page(
        "%s%s — %s" % (f["title"], year, SITE_NAME),
        body,
        "",
        depth=1,
        description="%s%s — %sRepresented by %s. Contact us to confirm "
        "licensing availability."
        % (f["title"], year, meta_logline(f["logline"]), f["catalog_name"]),
        canonical_path=slug_path,
        ogimg_override=og_img,
        extra_jsonld=movie_jsonld(f),
    )


# --------------------------------------------------------------------------
# licensing
# --------------------------------------------------------------------------


def build_licensing(films):
    def opts(values):
        return "".join('<option value="%s">%s</option>' % (e(v), e(v)) for v in values)

    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>Licensing &amp; contact</h1></div>

    <div class="prose">
      <p>We offer non-exclusive licensing for individual titles, themed packages,
        or full-catalog deals. Territory, term and platform are set per deal.
        Use the form below to tell us what you&rsquo;re looking for.</p>
      <p>Our own library has %(cfv)d titles. Alongside that we represent
        %(bf)d titles for Blue Finch Film Releasing and %(sc)d for
        SC Films International — %(total)d in all. For agency-represented
        titles, availability and terms are confirmed per inquiry. Every title page
        states which collection it comes from.</p>
    </div>

    <h2 class="section-h2">Send an inquiry</h2>

    <div class="form-card">
      <div class="notice notice-ok" id="ok" hidden role="status">%(confirm)s</div>
      <div class="notice notice-err" id="err" hidden role="alert"></div>
      <div class="notice notice-warn" id="unconfigured" hidden>
        <strong>Form not connected.</strong>
        Email us at <a href="mailto:%(lic_email)s">%(lic_email)s</a> to discuss licensing.
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
              placeholder="e.g. Stagecoach, A Bittersweet Life, or &lsquo;browsing the full catalog&rsquo;">
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

    <div class="prose mt-prose">
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
        "cfv": len(in_catalog(films, "best-b-movies")),
        "total": len(films),
        "bf": len(in_catalog(films, "blue-finch")),
        "sc": len(in_catalog(films, "sc-films")),
        "confirm": e(CONFIRMATION),
        "uses": opts(USE_OPTIONS),
        "vols": opts(VOLUME_OPTIONS),
        "lic_email": LICENSING_EMAIL,
    }
    return page(
        "Licensing & contact — %s" % SITE_NAME,
        body,
        "licensing.html",
        canonical_path="licensing.html",
        description="Licensing terms and inquiry form for %d titles across the "
        "Velvet Octopus, Blue Finch, and SC Films International collections."
        % len(films),
    )


# --------------------------------------------------------------------------
# submit
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
        finished films only — no development, no treatments.</p>
      <p>Fill in the form below. We&rsquo;ll read every submission and reply
        if it&rsquo;s a good fit. We can&rsquo;t guarantee a response to every
        inquiry, but we do look at all of them.</p>
    </div>

    <div class="submit-note">
      <strong>We don&rsquo;t just list your film &mdash; we cut it.</strong>
      <p>Every title we represent is eligible for short-form promotional
        material: trailers, social cuts, genre reels across the channels we
        operate. If a project has been sitting, the right clip in the right
        feed can open a new door.</p>
    </div>

    <div class="form-card mt-form-card">
      <div class="notice notice-ok" id="ok" hidden role="status">%(confirm)s</div>
      <div class="notice notice-err" id="err" hidden role="alert"></div>
      <div class="notice notice-warn" id="unconfigured" hidden>
        <strong>Form not connected.</strong>
        Email your submission to <a href="mailto:%(submit_email)s">%(submit_email)s</a>.
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
            <p class="hint">Password-protected links are fine. No file uploads.</p>
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
        "submit_email": SITE_CONTACT_EMAIL,
    }
    return page(
        "Submit a film — %s" % SITE_NAME,
        body,
        "submit.html",
        canonical_path="submit.html",
        description="Submit your independent film to Velvet Octopus Films for "
        "distribution consideration. Finished films only.",
    )


# --------------------------------------------------------------------------
# about  (item 5: real content, specific line with HTML comment)
# --------------------------------------------------------------------------


def build_about(films):
    cfv = in_catalog(films, "best-b-movies")
    langs = sorted(
        {f["language"] for f in cfv if f["language"] and f["language"] != "English"}
    )
    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>About Velvet Octopus Films</h1></div>
    <div class="prose">
      <p>Velvet Octopus Films is an independent film library. We represent classic
        and contemporary titles for licensing, and distribute them to YouTube and
        AVOD platforms. This site is the catalog and the contact form. It does not
        stream or sell films directly.</p>

      <p>Velvet Octopus has been in film distribution since 2005.
        <!-- lineage: associated through management with SC Films International and Blue Finch Films [TODO: confirm current relationship before publishing] --></p>

      <h2>Our own library</h2>
      <p>%(cfv)d titles of classic Hollywood and international cinema. The core
        runs from the 1930s through the 1970s, with a smaller set reaching into
        the 2000s and 2010s. The American side goes deep on genre pictures:
        B-westerns and singing-cowboy series, studio film noir, the Rathbone-era
        Sherlock Holmes mysteries, gothic horror and drive-in science fiction.
        The international side gathers landmark work from Japan, Italy, France,
        India, China, Russia, and Spain &mdash; films by Kurosawa, Ozu, Mizoguchi,
        Satyajit Ray, De Sica, Bu&ntilde;uel, and Tarkovsky among them, across
        %(nlang)d languages beyond English.</p>
      <p>These titles are offered for non-exclusive licensing across streaming,
        broadcast, and digital platforms, with territory and term negotiated
        per deal. Many are also on the
        <a href="%(tiktok)s" target="_blank" rel="noopener noreferrer">%(handle)s TikTok</a>
        as short clips and on YouTube as full films.</p>

      <h2>How to watch</h2>
      <p>Many titles from our own library are on YouTube.
        <a href="watch.html">Browse the watch list</a> to find them in one place,
        or visit a film&rsquo;s page for the Watch button when it&rsquo;s available.
        For short clips, follow
        <a href="%(tiktok)s" target="_blank" rel="noopener noreferrer">%(handle)s</a>
        on TikTok.</p>

      <h2>How to license</h2>
      <p>Use the <a href="licensing.html">licensing inquiry form</a>. Tell us
        which titles or what volume you&rsquo;re after and we&rsquo;ll
        come back with availability, territory options, and rates within a few
        business days.</p>

      <p><a class="btn btn-line" href="collections.html">Browse the collections</a></p>
    </div>
  </div>
</section>
""" % {
        "total": len(films),
        "cfv": len(cfv),
        "nlang": len(langs),
        "tiktok": e(TIKTOK_URL),
        "handle": e(TIKTOK_HANDLE),
    }
    return page(
        "About — %s" % SITE_NAME,
        body,
        "about.html",
        canonical_path="about.html",
        description="About Velvet Octopus Films — an independent film library "
        "for licensing. What we do, how to watch, how to license.",
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
      <p>To discuss a specific title or a package, use the
        <a href="licensing.html">licensing inquiry form</a> — it asks the
        right questions up front and speeds up our reply.</p>

      <h2>Film submissions</h2>
      <p>If you have a finished film you&rsquo;d like us to consider, use the
        <a href="submit.html">film submission form</a>.</p>

      <h2>Everything else</h2>
      <p>Email <a href="mailto:%(contact)s">%(contact)s</a>. We read every
        message and reply when we can.</p>

      <h2>TikTok</h2>
      <p>Short clips and rare footage: follow
        <a href="%(tiktok)s" target="_blank" rel="noopener noreferrer">%(handle)s</a>.</p>
    </div>
  </div>
</section>
""" % {
        "contact": SITE_CONTACT_EMAIL,
        "tiktok": e(TIKTOK_URL),
        "handle": e(TIKTOK_HANDLE),
    }
    return page(
        "Contact — %s" % SITE_NAME,
        body,
        "contact.html",
        canonical_path="contact.html",
        description="Contact Velvet Octopus Films for licensing inquiries, "
        "film submissions, or general questions.",
    )


# --------------------------------------------------------------------------
# privacy  (item 6: real text, no placeholders)
# --------------------------------------------------------------------------


def build_privacy():
    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>Privacy &amp; terms</h1></div>
    <div class="prose">

      <h2>What this site does</h2>
      <p>This is a static film catalog and contact form. No accounts, no
        subscriptions, no purchases. The only action you can take is submitting
        an inquiry or a film for consideration.</p>

      <h2>Analytics</h2>
      <p>None. This site loads no analytics scripts, sets no tracking cookies,
        and makes no third-party analytics requests. Every page is plain HTML,
        CSS, and self-hosted JavaScript. You can verify this by inspecting the
        network tab in any browser.</p>

      <h2>Cookies</h2>
      <p>We set no cookies. The site has no login, no shopping cart, and no
        persistent session. Your browser may set session storage for filter
        state on the Browse page; that data never leaves your browser.</p>

      <h2>YouTube embeds</h2>
      <p>Film pages that have a YouTube link show a click-to-play button.
        <strong>No YouTube request is made until you click it.</strong> When you
        do click, the video loads from
        <code>www.youtube-nocookie.com</code>, which is YouTube&rsquo;s
        privacy-enhanced embed domain. That means YouTube does not receive your
        identity from the embed unless you are signed into Google and have
        consented to that tracking in your Google account.</p>

      <h2>Forms and email</h2>
      <p>When you submit a licensing inquiry or film submission, the data you
        enter is sent to a Cloudflare Worker, which passes it to
        <a href="https://resend.com" target="_blank" rel="noopener noreferrer">Resend</a>
        to deliver the email. We receive that email in our inbox.</p>
      <p>We use the information you send (name, email, company, message) only
        to reply to you. We do not sell it, share it with third parties for
        marketing, or add it to any mailing list. We retain it as long as
        the email thread is useful, then delete it.</p>
      <p>Resend is a transactional email provider. They receive your email
        address and the message content as part of delivery. See
        <a href="https://resend.com/legal/privacy-policy" target="_blank"
           rel="noopener noreferrer">Resend&rsquo;s privacy policy</a>
        for how they handle it.</p>
      <p>Cloudflare processes the network request. See
        <a href="https://www.cloudflare.com/privacypolicy/" target="_blank"
           rel="noopener noreferrer">Cloudflare&rsquo;s privacy policy</a>.</p>

      <h2>External links</h2>
      <p>Links to TikTok, YouTube, and partner company pages leave this site.
        Those services have their own privacy policies.</p>

      <h2>Contact</h2>
      <p>Privacy questions: <a href="mailto:%(contact)s">%(contact)s</a>.</p>

    </div>
  </div>
</section>
""" % {"contact": SITE_CONTACT_EMAIL}
    return page(
        "Privacy & terms — %s" % SITE_NAME,
        body,
        "privacy.html",
        canonical_path="privacy.html",
        description="Privacy policy for Velvet Octopus Films: no analytics, "
        "no cookies, YouTube embeds load on click only.",
    )


# --------------------------------------------------------------------------
# 404
# --------------------------------------------------------------------------


def build_watch(films):
    watchable = [f for f in films if (f.get("youtube_id") or "").strip()]

    if watchable:
        cards = []
        for f in watchable:
            vid = e(f["youtube_id"].strip())
            art = poster_art(f, w=240, h=360)
            year = " (%s)" % f["year"] if f["year"] else ""
            cards.append("""
    <div class="film-card watch-card">
      <a href="films/%(slug)s.html" class="poster">%(art)s</a>
      <div class="card-info">
        <a class="card-title" href="films/%(slug)s.html">%(title)s%(year)s</a>
        <button class="btn btn-gold yt-trigger" type="button"
                data-yt-id="%(vid)s" aria-label="Watch %(title)s on YouTube">
          &#9654; Watch
        </button>
      </div>
      <div class="yt-embed-slot"></div>
    </div>""" % {
                "slug": e(f["slug"]),
                "art": art,
                "title": e(f["title"]),
                "year": e(year),
                "vid": vid,
            })
        grid_html = '<div class="card-grid watch-grid">%s</div>' % "".join(cards)
        count_note = '<p class="lede">%d titles available to watch now.</p>' % len(watchable)
        script_tag = '\n<script src="assets/yt-embed.js"></script>'
    else:
        grid_html = """
<div class="empty-watch">
  <p>Watch links are being added to the catalog. Check back soon, or
    <a href="about.html#how-to-watch">learn how to find films</a> on YouTube now.</p>
  <a class="btn btn-gold" href="browse.html">Browse all titles</a>
</div>"""
        count_note = ""
        script_tag = ""

    body = """
<section class="section section-cream">
  <div class="wrap">
    <div class="rule-head"><h1>Watch</h1></div>
    %(count_note)s
    %(grid_html)s
  </div>
</section>%(script_tag)s
""" % {
        "count_note": count_note,
        "grid_html": grid_html,
        "script_tag": script_tag,
    }
    return page(
        "Watch — %s" % SITE_NAME,
        body,
        "watch.html",
        canonical_path="watch.html",
        description="Watch films from the Velvet Octopus catalog on YouTube — "
        "click to play directly on the page.",
    )


def build_404():
    body = """
<section class="section section-cream">
  <div class="wrap not-found">
    <h1>404</h1>
    <p>That page doesn&rsquo;t exist &mdash; or it moved.</p>
    <a class="btn btn-line" href="index.html">Back to the home page</a>
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
# catalog.html redirect  (item 3: old Catalog URL → Browse, not Collections)
# --------------------------------------------------------------------------


def build_catalog_redirect():
    dest = "browse.html"
    if SITE_BASE:
        dest_abs = "%s/browse.html" % SITE_BASE
    else:
        dest_abs = dest
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0;url=%s">
<link rel="canonical" href="%s">
<meta name="robots" content="noindex">
<title>Redirecting…</title>
</head>
<body>
<p><a href="%s">Browse titles</a></p>
</body>
</html>
""" % (dest, dest_abs, dest)


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

    # Copy _headers into dist so Cloudflare Pages picks it up
    headers_src = os.path.join(HERE, "_headers")
    if os.path.isfile(headers_src):
        shutil.copy2(headers_src, os.path.join(DIST, "_headers"))

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
    write("catalog.html", build_catalog_redirect())   # old URL → browse.html
    write("browse.html", build_browse(films))
    write("licensing.html", build_licensing(films))
    write("submit.html", build_submit())
    write("watch.html", build_watch(films))
    write("about.html", build_about(films))
    write("contact.html", build_contact())
    write("privacy.html", build_privacy())
    write("404.html", build_404())

    posters_dict = load_posters_csv()
    for f in films:
        write(os.path.join("films", f["slug"] + ".html"), build_film(f, films, posters_dict))

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
    # Stills summary
    own_films = in_catalog(films, "best-b-movies")
    n_stills = sum(1 for f in films if still_exists(f["slug"]))
    _, hidden_shelves = build_shelves_html(films)
    print("built %d pages into dist/" % total_pages)
    if not SITE_BASE:
        print("  no SITE_BASE set — sitemap.xml skipped; set SITE_BASE=https://velvetoctopusfilms.com for production")
    if NOINDEX:
        print("  NOINDEX=1 — all pages carry noindex,nofollow")
    print("  %d film pages" % len(films))
    print("  stills: %d films have stills, %d use typographic fallback" % (n_stills, len(films) - n_stills))
    if hidden_shelves:
        print("  shelves hidden (< 6 films): %s" % ", ".join(hidden_shelves))
    print("  preview:  python3 -m http.server -d dist 8000")


if __name__ == "__main__":
    main()
