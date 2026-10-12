"""
Replace all catalog poster images with correct ones from TMDB.

Usage:
    TMDB_KEY=your_key python3 scripts/fetch_posters.py

- Reads TMDB IDs from .tmdb-cache.json (must exist — run fetch_people.py first)
- Downloads the highest-voted English or language-neutral poster for each film
- Falls back to any poster if no English one exists
- Writes to assets/posters/{slug}.jpg (overwrites existing wrong images)
- Skips films with no TMDB ID
"""

import csv, json, os, sys, time, urllib.request, urllib.parse

API_KEY = os.environ.get("TMDB_KEY", "")
if not API_KEY:
    sys.exit("Set TMDB_KEY=your_key before running.")

BASE = "https://api.themoviedb.org/3"
CACHE_FILE = ".tmdb-cache.json"
CSV_FILE = "data/catalog.csv"
POSTER_DIR = os.path.join("assets", "posters")
POSTER_BASE = "https://image.tmdb.org/t/p/w500"


def tmdb_get(path, params=None):
    params = params or {}
    params["api_key"] = API_KEY
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())


def best_poster(tmdb_id):
    """Return the best poster file_path for this TMDB ID, or None."""
    data = tmdb_get(f"/movie/{tmdb_id}/images")
    posters = data.get("posters", [])
    if not posters:
        return None
    # Prefer English or no-language posters, sorted by vote_average desc
    en_posters = [p for p in posters if p.get("iso_639_1") in ("en", None, "")]
    ranked = sorted(en_posters or posters, key=lambda p: p.get("vote_average", 0), reverse=True)
    return ranked[0]["file_path"]


def download_poster(file_path, dest):
    url = POSTER_BASE + file_path
    with urllib.request.urlopen(url, timeout=30) as r:
        data = r.read()
    with open(dest, "wb") as f:
        f.write(data)
    return len(data)


def main():
    with open(CACHE_FILE) as f:
        cache = json.load(f)

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    os.makedirs(POSTER_DIR, exist_ok=True)

    ok = 0
    skipped = 0
    errors = []

    for i, row in enumerate(rows):
        slug = row["slug"]
        title = row["title"]
        year = row.get("year", "")
        tmdb_id = cache.get(slug)

        if not tmdb_id:
            print(f"[{i+1}/{len(rows)}] SKIP (no TMDB ID): {title} ({year})")
            skipped += 1
            continue

        dest = os.path.join(POSTER_DIR, slug + ".jpg")
        print(f"[{i+1}/{len(rows)}] {title} ({year}) ...", end=" ", flush=True)

        try:
            file_path = best_poster(tmdb_id)
            if not file_path:
                print("NO POSTER on TMDB")
                errors.append((slug, "no poster on TMDB"))
                continue

            size = download_poster(file_path, dest)
            print(f"OK ({size // 1024}KB) → {slug}.jpg")
            ok += 1

        except Exception as e:
            print(f"ERROR: {e}")
            errors.append((slug, str(e)))

        time.sleep(0.3)

    print(f"\nDone. {ok} downloaded, {skipped} skipped (no TMDB ID), {len(errors)} errors.")
    if errors:
        print("\nFailed:")
        for slug, reason in errors:
            print(f"  {slug}: {reason}")


if __name__ == "__main__":
    main()
