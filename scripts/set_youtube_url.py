#!/usr/bin/env python3 -I
"""
Set youtube_id values in data/catalog.csv from a CSV of slug,url pairs.

Usage:
    python3 scripts/set_youtube_url.py input.csv

input.csv format (with or without a header row):
    slug,url
    stagecoach,https://www.youtube.com/watch?v=dQw4w9WgXcQ
    bicycle-thieves-1948,https://youtu.be/dQw4w9WgXcQ

Only youtube.com and youtu.be URLs are accepted.
The script stores the bare 11-character video ID, not the full URL.
Only data/catalog.csv is written; the partner catalogs are not touched.

Run from the repo root:
    python3 scripts/set_youtube_url.py your-ids.csv
"""

import csv
import io
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(HERE, "data", "catalog.csv")

YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(url):
    """Return the 11-char YouTube video ID or raise ValueError."""
    url = url.strip()
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        raise ValueError("could not parse URL: %r" % url)

    host = parsed.netloc.lower().lstrip("www.")

    if host == "youtu.be":
        vid = parsed.path.lstrip("/").split("/")[0].split("?")[0]
    elif host in ("youtube.com", "m.youtube.com"):
        qs = urllib.parse.parse_qs(parsed.query)
        vids = qs.get("v", [])
        if not vids:
            # Handle /shorts/<id> and /embed/<id> paths
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in ("shorts", "embed", "v"):
                vid = parts[1]
            else:
                raise ValueError("no video ID found in URL: %r" % url)
        else:
            vid = vids[0]
    else:
        raise ValueError(
            "only youtube.com and youtu.be URLs are accepted, got: %r" % url
        )

    vid = vid.strip()
    if not YT_ID_RE.match(vid):
        raise ValueError("extracted ID %r doesn't look like a YouTube video ID" % vid)
    return vid


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/set_youtube_url.py input.csv", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.isfile(input_path):
        print("error: input file not found: %s" % input_path, file=sys.stderr)
        sys.exit(1)

    # Parse the input CSV.
    updates = {}
    errors = []
    with open(input_path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for i, row in enumerate(reader):
            if not row or not row[0].strip():
                continue
            if i == 0 and row[0].strip().lower() == "slug":
                continue  # skip header
            if len(row) < 2:
                errors.append("row %d: expected slug,url — got %r" % (i + 1, row))
                continue
            slug = row[0].strip()
            url = row[1].strip()
            if not url:
                errors.append("row %d: empty URL for slug %r" % (i + 1, slug))
                continue
            try:
                vid = extract_video_id(url)
            except ValueError as exc:
                errors.append("row %d (%s): %s" % (i + 1, slug, exc))
                continue
            if slug in updates and updates[slug] != vid:
                errors.append(
                    "row %d: duplicate slug %r with conflicting IDs" % (i + 1, slug)
                )
                continue
            updates[slug] = vid

    if errors:
        print("Input errors (nothing written):", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        sys.exit(1)

    if not updates:
        print("No valid updates found in input. Nothing written.")
        sys.exit(0)

    # Read the catalog.
    with open(CATALOG, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
        fh.seek(0)
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames

    if not fieldnames:
        print("error: could not read fieldnames from %s" % CATALOG, file=sys.stderr)
        sys.exit(1)

    if "youtube_id" not in fieldnames:
        print("error: youtube_id column not found in %s" % CATALOG, file=sys.stderr)
        print("Run build.py once to add the column, or add it manually.", file=sys.stderr)
        sys.exit(1)

    slug_index = {r["slug"]: i for i, r in enumerate(rows)}

    applied = []
    not_found = []
    for slug, vid in updates.items():
        if slug not in slug_index:
            not_found.append(slug)
            continue
        rows[slug_index[slug]]["youtube_id"] = vid
        applied.append((slug, vid))

    if not_found:
        print("Warning: these slugs were not found in catalog.csv (skipped):")
        for s in not_found:
            print("  " + s)

    if not applied:
        print("No matching slugs found. Nothing written.")
        sys.exit(0)

    # Write back.
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    with open(CATALOG, "w", encoding="utf-8", newline="") as fh:
        fh.write(buf.getvalue())

    print("Updated %d title(s) in %s:" % (len(applied), CATALOG))
    for slug, vid in applied:
        print("  %s → %s" % (slug, vid))


if __name__ == "__main__":
    main()
