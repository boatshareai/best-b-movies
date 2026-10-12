"""
Populate director, cast, and producer fields in data/catalog.csv using TMDB.

Usage:
    TMDB_KEY=your_key python3 scripts/fetch_people.py

Get a free API key at https://www.themoviedb.org/settings/api

- Skips rows that already have a director filled in (re-run safe).
- Writes progress to stdout and saves after every 10 films.
- Stores raw TMDB movie IDs in .tmdb-cache.json to avoid repeat searches.
"""

import csv, json, os, sys, time, urllib.request, urllib.parse

API_KEY = os.environ.get("TMDB_KEY", "")
if not API_KEY:
    sys.exit("Set TMDB_KEY=your_key before running.")

BASE = "https://api.themoviedb.org/3"
CACHE_FILE = ".tmdb-cache.json"
CSV_FILE = "data/catalog.csv"
CAST_LIMIT = 6  # top-billed actors to store


def tmdb_get(path, params=None):
    params = params or {}
    params["api_key"] = API_KEY
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def search_movie(title, year):
    data = tmdb_get("/search/movie", {"query": title, "year": year, "language": "en-US"})
    results = data.get("results", [])
    if not results:
        # retry without year constraint
        data = tmdb_get("/search/movie", {"query": title, "language": "en-US"})
        results = data.get("results", [])
    return results[0]["id"] if results else None


def get_credits(tmdb_id):
    data = tmdb_get(f"/movie/{tmdb_id}/credits")
    crew = data.get("crew", [])
    cast = data.get("cast", [])

    director = ", ".join(
        p["name"] for p in crew if p.get("job") == "Director"
    )
    producer = ", ".join(
        p["name"] for p in crew
        if p.get("job") in ("Producer", "Executive Producer")
        and p.get("department") == "Production"
    )[:200]  # cap length
    actors = ", ".join(p["name"] for p in cast[:CAST_LIMIT])

    return director, actors, producer


def main():
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    fieldnames = list(rows[0].keys())
    changed = 0

    for i, row in enumerate(rows):
        slug = row["slug"]
        title = row["title"]
        year = row.get("year", "").strip()

        # skip if already populated
        if row.get("director", "").strip():
            continue

        print(f"[{i+1}/{len(rows)}] {title} ({year}) ...", end=" ", flush=True)

        try:
            tmdb_id = cache.get(slug)
            if not tmdb_id:
                tmdb_id = search_movie(title, year)
                if tmdb_id:
                    cache[slug] = tmdb_id

            if not tmdb_id:
                print("NOT FOUND")
                row["director"] = ""
                row["cast"] = ""
                row["producer"] = ""
                continue

            director, actors, producer = get_credits(tmdb_id)
            row["director"] = director
            row["cast"] = actors
            row["producer"] = producer
            changed += 1
            print(f"dir={director or '—'}  cast={actors[:40] or '—'}")

        except Exception as e:
            print(f"ERROR: {e}")

        # rate-limit: TMDB allows ~40 req/s, be gentle
        time.sleep(0.26)

        # save progress every 10 films
        if (i + 1) % 10 == 0:
            _save(rows, fieldnames)
            with open(CACHE_FILE, "w") as f:
                json.dump(cache, f, indent=2)
            print(f"  — saved progress ({changed} updated so far)")

    _save(rows, fieldnames)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

    print(f"\nDone. {changed} films updated.")


def _save(rows, fieldnames):
    import io
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=fieldnames)
    w.writeheader()
    for row in rows:
        w.writerow(row)
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        f.write(out.getvalue())


if __name__ == "__main__":
    main()
