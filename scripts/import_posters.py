#!/usr/bin/env python3
"""
import_posters.py — import poster images from ~/Desktop/velvet-octopus-posters-inbox/

Usage:
    python3 -I scripts/import_posters.py

For each image in the inbox:
  - Matches the filename to a film slug from the three catalog CSVs
  - Resizes to assets/posters/<slug>.jpg (max 1000px wide, quality 88)
  - Resizes to assets/posters/<slug>-480.jpg (max 480px wide, quality 82)
  - Flags source images under 800px wide as LOW-RES
  - Appends a row to data/posters.csv
  - Moves the original to ~/Desktop/velvet-octopus-posters-inbox/_done/
  - Leaves unmatched files in place and reports them

Run from the repo root or any directory — paths are resolved relative to this
script's parent directory (the repo root).
"""

import csv
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX = os.path.expanduser("~/Desktop/velvet-octopus-posters-inbox")
DONE_DIR = os.path.join(INBOX, "_done")
ASSETS_POSTERS = os.path.join(HERE, "assets", "posters")
DATA_DIR = os.path.join(HERE, "data")
POSTERS_CSV = os.path.join(DATA_DIR, "posters.csv")
POSTERS_CSV_COLS = ["slug", "original_filename", "imported_date", "width", "height",
                    "low_res", "license", "author", "source_url"]

CATALOG_FILES = [
    os.path.join(DATA_DIR, "catalog.csv"),
    os.path.join(DATA_DIR, "blue-finch.csv"),
    os.path.join(DATA_DIR, "sc-films.csv"),
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

# ---------------------------------------------------------------------------
# PIL / sips helpers
# ---------------------------------------------------------------------------

try:
    from PIL import Image as _PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def get_image_dimensions(path):
    """Return (width, height) for an image file."""
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
    """Resize src → dst, max max_side pixels on the long axis, JPEG output."""
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
# Slug helpers
# ---------------------------------------------------------------------------

def _strip_article(s):
    return re.sub(r"^(the|a|an)[-\s]", "", s, flags=re.I)


def _normalise_title(s):
    """Lowercase, strip punctuation, collapse whitespace/hyphens."""
    s = s.lower()
    s = re.sub(r"[''`]", "", s)         # apostrophes
    s = re.sub(r"[,:.!?;]", "", s)      # punctuation
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _to_slug_fragment(title):
    """Turn a title string into a hyphenated slug fragment (no year)."""
    s = _normalise_title(title)
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def load_slugs():
    """Return a list of (slug, norm_title, year) from all three CSVs."""
    slugs = []
    for path in CATALOG_FILES:
        if not os.path.exists(path):
            continue
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                slug = (row.get("slug") or "").strip()
                title = (row.get("title") or "").strip()
                year = (row.get("year") or "").strip()
                if slug and title:
                    slugs.append((slug, title, year))
    return slugs


def parse_filename(name):
    """
    Return (title, year_str) from a filename stem.

    Handles:
      black-sabbath-1963           → ("black-sabbath", "1963")
      Black Sabbath (1963)         → ("Black Sabbath", "1963")
      Black.Sabbath.1963           → ("Black.Sabbath", "1963")  (dots treated as spaces)
      Black Sabbath                → ("Black Sabbath", "")
    """
    stem = os.path.splitext(name)[0]

    # "Title (Year)" pattern
    m = re.match(r"^(.+?)\s*\((\d{4})\)\s*$", stem)
    if m:
        return m.group(1).strip(), m.group(2)

    # Slug-like: ends with -YYYY
    m = re.match(r"^(.+)-(\d{4})$", stem)
    if m:
        return m.group(1), m.group(2)

    # Plain stem, no year
    return stem, ""


def match_filename_to_slug(filename, slugs):
    """
    Try to match a filename to a slug.

    Returns (slug, title, year) on success, or None on failure.

    Strategy:
    1. If the stem IS a known slug exactly — use it.
    2. Parse title + year from the filename, then compare normalised title
       (stripping "the-" prefix, apostrophes, commas, colons, lowercase).
       Require year to match when present in filename.
    """
    stem = os.path.splitext(filename)[0]

    # Pass 1: exact slug match
    for slug, title, year in slugs:
        if stem.lower() == slug.lower():
            return slug, title, year

    # Pass 2: parse title+year from filename, compare to catalogue
    fn_title_raw, fn_year = parse_filename(filename)
    fn_title_norm = _normalise_title(_strip_article(fn_title_raw))
    fn_title_slug = _to_slug_fragment(fn_title_raw)

    for slug, title, year in slugs:
        cat_norm = _normalise_title(_strip_article(title))

        if fn_title_norm != cat_norm:
            # Also try slug-fragment comparison
            cat_slug_frag = _to_slug_fragment(title)
            if fn_title_slug != cat_slug_frag:
                continue

        # Title matches — now check year
        if fn_year:
            if year and fn_year != year:
                continue

        return slug, title, year

    return None


# ---------------------------------------------------------------------------
# posters.csv helpers
# ---------------------------------------------------------------------------

def load_existing_posters():
    """Return set of slugs already in data/posters.csv."""
    if not os.path.exists(POSTERS_CSV):
        return set()
    with open(POSTERS_CSV, newline="", encoding="utf-8") as fh:
        return {row["slug"].strip() for row in csv.DictReader(fh) if row.get("slug")}


def append_posters_csv(rows):
    """Append rows (list of dicts) to data/posters.csv, creating if needed."""
    exists = os.path.exists(POSTERS_CSV)
    with open(POSTERS_CSV, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=POSTERS_CSV_COLS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(DONE_DIR, exist_ok=True)
    os.makedirs(ASSETS_POSTERS, exist_ok=True)

    # Collect image files in inbox (non-recursive)
    inbox_files = [
        f for f in os.listdir(INBOX)
        if os.path.isfile(os.path.join(INBOX, f))
        and os.path.splitext(f.lower())[1] in IMAGE_EXTS
    ]

    if not inbox_files:
        print("No files found in inbox: %s" % INBOX)
        return

    slugs = load_slugs()
    existing = load_existing_posters()

    matched = 0
    unmatched = []
    low_res_count = 0
    new_rows = []

    for filename in sorted(inbox_files):
        src = os.path.join(INBOX, filename)
        result = match_filename_to_slug(filename, slugs)

        if result is None:
            unmatched.append(filename)
            continue

        slug, title, year = result
        matched += 1

        # Get source dimensions
        try:
            w, h = get_image_dimensions(src)
        except Exception as exc:
            print("  WARN: cannot read dimensions for %s: %s" % (filename, exc))
            w = h = 0

        low_res = w > 0 and w < 800
        if low_res:
            low_res_count += 1
            print("  LOW-RES: %s → %s (%dpx wide)" % (filename, slug, w))

        # Output paths
        out_full = os.path.join(ASSETS_POSTERS, slug + ".jpg")
        out_480 = os.path.join(ASSETS_POSTERS, slug + "-480.jpg")

        # Resize
        try:
            resize_image(src, out_full, 1000, 88)
            resize_image(src, out_480, 480, 82)
        except Exception as exc:
            print("  ERROR resizing %s: %s" % (filename, exc))
            continue

        # Record
        today = time.strftime("%Y-%m-%d")
        new_rows.append({
            "slug": slug,
            "original_filename": filename,
            "imported_date": today,
            "width": str(w),
            "height": str(h),
            "low_res": "yes" if low_res else "no",
            "license": "",
            "author": "",
            "source_url": "",
        })

        # Move to _done
        done_path = os.path.join(DONE_DIR, filename)
        if os.path.exists(done_path):
            base, ext = os.path.splitext(filename)
            done_path = os.path.join(DONE_DIR, "%s_%s%s" % (base, today, ext))
        shutil.move(src, done_path)
        print("  OK: %s → %s" % (filename, slug))

    if new_rows:
        append_posters_csv(new_rows)

    # Summary
    print()
    print("Summary: matched %d, unmatched %d, low-res %d"
          % (matched, len(unmatched), low_res_count))

    if unmatched:
        print()
        print("Unmatched files (left in inbox):")
        for f in unmatched:
            print("  %s" % f)


if __name__ == "__main__":
    main()
