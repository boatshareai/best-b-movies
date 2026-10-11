#!/usr/bin/env python3
"""
find_posters.py — search Wikimedia Commons for missing poster images.

Usage:
    python3 -I scripts/find_posters.py --commons

For each film without an entry in data/posters.csv:
  - Queries the Wikimedia Commons API for a poster image
  - HIGH confidence (exact title+year match): downloads, resizes, records
  - MEDIUM confidence (title matches, year uncertain): adds to
    docs/velvet-octopus/poster-review.html for manual review
  - LOW confidence: skipped, not recorded

Results are cached in .poster-cache.json at the repo root for 7 days.
Rate-limited to 1 request per second.

Run from the repo root or any directory — paths are resolved relative to this
script's parent directory (the repo root).
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(HERE, "data")
ASSETS_POSTERS = os.path.join(HERE, "assets", "posters")
POSTERS_CSV = os.path.join(DATA_DIR, "posters.csv")
CACHE_FILE = os.path.join(HERE, ".poster-cache.json")
REVIEW_HTML = os.path.join(HERE, "docs", "velvet-octopus", "poster-review.html")

POSTERS_CSV_COLS = ["slug", "original_filename", "imported_date", "width", "height",
                    "low_res", "license", "author", "source_url"]

CATALOG_FILES = [
    os.path.join(DATA_DIR, "catalog.csv"),
    os.path.join(DATA_DIR, "blue-finch.csv"),
    os.path.join(DATA_DIR, "sc-films.csv"),
]

# Wikimedia Commons API
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = (
    "VelvetOctopusFilms/1.0 (velvetoctopusfilms.com; "
    "licensing@velvetoctopusfilms.com) film-catalog-tool"
)
CACHE_TTL_DAYS = 7

# ---------------------------------------------------------------------------
# PIL / sips helpers (same as import_posters.py)
# ---------------------------------------------------------------------------

try:
    from PIL import Image as _PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def get_image_dimensions(path):
    if HAS_PIL:
        with _PILImage.open(path) as im:
            return im.size
    import subprocess
    result = subprocess.run(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
        capture_output=True, text=True, check=True,
    )
    w = h = 0
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("pixelWidth:"):
            w = int(line.split(":")[1].strip())
        elif line.startswith("pixelHeight:"):
            h = int(line.split(":")[1].strip())
    return w, h


def resize_image(src, dst, max_side, quality):
    if HAS_PIL:
        with _PILImage.open(src) as im:
            im = im.convert("RGB")
            w, h = im.size
            if w > max_side:
                new_h = int(h * max_side / w)
                im = im.resize((max_side, new_h), _PILImage.LANCZOS)
            elif h > max_side:
                new_w = int(w * max_side / h)
                im = im.resize((new_w, max_side), _PILImage.LANCZOS)
            im.save(dst, "JPEG", quality=quality, optimize=True)
    else:
        import subprocess
        subprocess.run(
            ["sips", "-Z", str(max_side), "--setProperty", "format", "jpeg",
             "--setProperty", "formatOptions", str(quality),
             "--out", dst, src],
            check=True, capture_output=True,
        )


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_all_films():
    """Return list of {slug, title, year} dicts from all catalogs."""
    films = []
    for path in CATALOG_FILES:
        if not os.path.exists(path):
            continue
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                slug = (row.get("slug") or "").strip()
                title = (row.get("title") or "").strip()
                year = (row.get("year") or "").strip()
                publish = (row.get("publish") or "yes").strip().lower()
                if slug and title and publish not in ("no", "false", "0"):
                    films.append({"slug": slug, "title": title, "year": year})
    return films


def load_existing_slugs():
    """Return set of slugs that already have an entry in data/posters.csv."""
    if not os.path.exists(POSTERS_CSV):
        return set()
    with open(POSTERS_CSV, newline="", encoding="utf-8") as fh:
        return {row["slug"].strip() for row in csv.DictReader(fh) if row.get("slug")}


def poster_file_exists(slug):
    """Return True if assets/posters/<slug>.jpg already exists."""
    return os.path.isfile(os.path.join(ASSETS_POSTERS, slug + ".jpg"))


def append_posters_csv(row):
    exists = os.path.exists(POSTERS_CSV)
    with open(POSTERS_CSV, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=POSTERS_CSV_COLS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, indent=2)


def cache_key(title, year):
    return "%s|%s" % (title.lower(), year)


def is_cache_fresh(entry):
    if not entry or "ts" not in entry:
        return False
    age_days = (time.time() - entry["ts"]) / 86400
    return age_days < CACHE_TTL_DAYS


# ---------------------------------------------------------------------------
# Wikimedia Commons API
# ---------------------------------------------------------------------------

def commons_search(title, year):
    """
    Search Wikimedia Commons for a film poster.

    Returns list of dicts: {title, url, thumb_url, description}
    """
    query = "%s (%s) film poster" % (title, year) if year else "%s film poster" % title
    params = urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": "6",
        "srlimit": "5",
        "format": "json",
    })
    url = "%s?%s" % (COMMONS_API, params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError) as exc:
        print("  API error for %r: %s" % (title, exc))
        return []

    results = []
    for hit in data.get("query", {}).get("search", []):
        fn = hit.get("title", "")  # e.g. "File:Black Sabbath 1963 film.jpg"
        results.append({
            "filename": fn,
            "snippet": hit.get("snippet", ""),
        })
    return results


def commons_file_info(filename):
    """
    Get image URL, thumbnail URL, license, and author for a Commons file.

    Returns dict or None.
    """
    bare = filename.replace("File:", "").replace("file:", "")
    params = urllib.parse.urlencode({
        "action": "query",
        "titles": "File:" + bare,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": "1000",
        "format": "json",
    })
    url = "%s?%s" % (COMMONS_API, params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError) as exc:
        print("  File-info error for %r: %s" % (filename, exc))
        return None

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        ii = page.get("imageinfo", [{}])[0]
        meta = ii.get("extmetadata", {})
        license_short = meta.get("LicenseShortName", {}).get("value", "")
        author_raw = meta.get("Artist", {}).get("value", "")
        # Strip HTML tags from author
        author = re.sub(r"<[^>]+>", "", author_raw).strip()
        return {
            "url": ii.get("url", ""),
            "thumb_url": ii.get("thumburl", ""),
            "descurl": ii.get("descriptionurl", ""),
            "license": license_short,
            "author": author,
        }
    return None


# ---------------------------------------------------------------------------
# Confidence classification
# ---------------------------------------------------------------------------

def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def classify_confidence(title, year, filename, snippet):
    """
    Return "high", "medium", or "low".

    HIGH:   exact title + year match in filename or snippet
    MEDIUM: title matches, year uncertain or absent
    LOW:    title doesn't match well enough
    """
    fn_lower = filename.lower()
    snip_lower = snippet.lower()
    title_norm = _norm(title)

    # Check title presence
    title_words = [w for w in re.split(r"\W+", title.lower()) if len(w) > 2]
    fn_title_match = title_norm in _norm(fn_lower) or all(w in fn_lower for w in title_words)
    snip_title_match = title_norm in _norm(snip_lower) or all(w in snip_lower for w in title_words)

    if not fn_title_match and not snip_title_match:
        return "low"

    if year:
        year_in_fn = year in fn_lower
        year_in_snip = year in snip_lower
        if year_in_fn or year_in_snip:
            return "high"
        else:
            return "medium"
    else:
        # No year to check — medium confidence
        return "medium"


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------

def download_file(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        with open(dest, "wb") as fh:
            fh.write(resp.read())


# ---------------------------------------------------------------------------
# Review HTML helper
# ---------------------------------------------------------------------------

def update_review_html(medium_items):
    """
    Write/append medium-confidence candidates to docs/velvet-octopus/poster-review.html.
    medium_items: list of {slug, title, year, thumb_url, filename, descurl}
    """
    os.makedirs(os.path.dirname(REVIEW_HTML), exist_ok=True)

    if os.path.exists(REVIEW_HTML):
        with open(REVIEW_HTML, encoding="utf-8") as fh:
            existing = fh.read()
    else:
        existing = ""

    # Build new entries HTML
    rows_html = ""
    for item in medium_items:
        thumb = item.get("thumb_url", "")
        img_tag = ('<img src="%s" alt="" loading="lazy" style="max-width:120px;border-radius:3px">'
                   % thumb) if thumb else "(no thumbnail)"
        rows_html += """
<tr>
  <td>%s</td>
  <td><b>%s</b> (%s)</td>
  <td>%s</td>
  <td><a href="%s" target="_blank">View on Commons</a></td>
  <td>Review before importing</td>
</tr>""" % (
            img_tag,
            item["title"],
            item["year"] or "?",
            item["filename"].replace("File:", ""),
            item.get("descurl", "#"),
        )

    if existing and "</tbody>" in existing:
        # Insert before </tbody>
        updated = existing.replace("</tbody>", rows_html + "\n</tbody>")
        with open(REVIEW_HTML, "w", encoding="utf-8") as fh:
            fh.write(updated)
    else:
        # Create fresh
        html = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Poster Review — Velvet Octopus Films</title>
<style>
  body { font-family: system-ui, sans-serif; padding: 24px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ddd; padding: 8px 12px; vertical-align: top; }
  th { background: #f4f4f4; }
  img { display: block; }
</style>
</head>
<body>
<h1>Poster Review Queue</h1>
<p>Medium-confidence poster candidates from Wikimedia Commons.
Review each before importing with import_posters.py.</p>
<table>
<thead>
<tr>
  <th>Thumbnail</th>
  <th>Film</th>
  <th>Commons filename</th>
  <th>Link</th>
  <th>Status</th>
</tr>
</thead>
<tbody>%s
</tbody>
</table>
</body>
</html>
""" % rows_html
        with open(REVIEW_HTML, "w", encoding="utf-8") as fh:
            fh.write(html)

    print("  Review HTML updated: %s" % REVIEW_HTML)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Find poster images on Wikimedia Commons")
    parser.add_argument("--commons", action="store_true", required=True,
                        help="Query Wikimedia Commons for missing posters")
    args = parser.parse_args()

    films = load_all_films()
    existing_slugs = load_existing_slugs()

    # Films with no poster image and no posters.csv entry
    missing = [
        f for f in films
        if f["slug"] not in existing_slugs and not poster_file_exists(f["slug"])
    ]

    if not missing:
        print("All films have posters or posters.csv entries.")
        return

    print("Searching for posters for %d films…" % len(missing))

    cache = load_cache()
    os.makedirs(ASSETS_POSTERS, exist_ok=True)

    stats = {"high": 0, "medium": 0, "low": 0, "errors": 0}
    medium_items = []

    for film in missing:
        slug = film["slug"]
        title = film["title"]
        year = film["year"]

        ck = cache_key(title, year)
        cached = cache.get(ck)
        if is_cache_fresh(cached):
            results = cached.get("results", [])
        else:
            time.sleep(1)
            results = commons_search(title, year)
            cache[ck] = {"ts": time.time(), "results": results}
            save_cache(cache)

        if not results:
            stats["low"] += 1
            continue

        best = None
        best_conf = "low"

        for hit in results:
            conf = classify_confidence(title, year, hit["filename"], hit.get("snippet", ""))
            if conf == "high":
                best = hit
                best_conf = "high"
                break
            if conf == "medium" and best_conf != "high":
                best = hit
                best_conf = "medium"

        if best_conf == "low" or best is None:
            stats["low"] += 1
            continue

        # Get file info (may need another API call — rate-limit)
        fi_key = "fi:" + best["filename"]
        fi_cached = cache.get(fi_key)
        if is_cache_fresh(fi_cached):
            file_info = fi_cached.get("info")
        else:
            time.sleep(1)
            file_info = commons_file_info(best["filename"])
            cache[fi_key] = {"ts": time.time(), "info": file_info}
            save_cache(cache)

        if not file_info or not file_info.get("url"):
            stats["errors"] += 1
            continue

        if best_conf == "high":
            # Download, resize, record
            tmp = os.path.join(ASSETS_POSTERS, slug + "_tmp_download")
            try:
                print("  HIGH: downloading %s for %s…" % (best["filename"], slug))
                download_file(file_info["url"], tmp)

                out_full = os.path.join(ASSETS_POSTERS, slug + ".jpg")
                out_480 = os.path.join(ASSETS_POSTERS, slug + "-480.jpg")
                resize_image(tmp, out_full, 1000, 88)
                resize_image(tmp, out_480, 480, 82)
                os.remove(tmp)

                try:
                    w, h = get_image_dimensions(out_full)
                except Exception:
                    w = h = 0

                today = time.strftime("%Y-%m-%d")
                append_posters_csv({
                    "slug": slug,
                    "original_filename": best["filename"],
                    "imported_date": today,
                    "width": str(w),
                    "height": str(h),
                    "low_res": "yes" if (w > 0 and w < 800) else "no",
                    "license": file_info.get("license", ""),
                    "author": file_info.get("author", ""),
                    "source_url": file_info.get("descurl", ""),
                })
                stats["high"] += 1
            except Exception as exc:
                print("  ERROR downloading %s: %s" % (slug, exc))
                if os.path.exists(tmp):
                    os.remove(tmp)
                stats["errors"] += 1

        elif best_conf == "medium":
            medium_items.append({
                "slug": slug,
                "title": title,
                "year": year,
                "filename": best["filename"],
                "thumb_url": file_info.get("thumb_url", ""),
                "descurl": file_info.get("descurl", ""),
            })
            stats["medium"] += 1

    if medium_items:
        update_review_html(medium_items)

    print()
    print("Summary: high %d downloaded, medium %d queued for review, low %d skipped"
          % (stats["high"], stats["medium"], stats["low"]))
    if stats["errors"]:
        print("  %d errors (see output above)" % stats["errors"])


if __name__ == "__main__":
    main()
