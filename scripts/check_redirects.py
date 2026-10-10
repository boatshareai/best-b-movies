#!/usr/bin/env python3 -I
"""
Validate the redirect map and verify catalog.html redirects correctly.

Usage (from repo root):
    python3 scripts/check_redirects.py

Checks:
  1. scripts/redirect_map.csv exists and is parseable.
  2. dist/catalog.html exists and contains a meta-refresh pointing to browse.html.
  3. Reports redirect counts per old-domain path.

Exits 0 on success, 1 on failure.
"""

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP_FILE = os.path.join(HERE, "scripts", "redirect_map.csv")
DIST = os.path.join(HERE, "dist")


def check_map():
    if not os.path.isfile(MAP_FILE):
        print("FAIL: redirect_map.csv not found at %s" % MAP_FILE)
        return None
    with open(MAP_FILE, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    print("OK:   redirect_map.csv found — %d entries" % len(rows))
    return rows


def check_catalog_html(rows):
    catalog_path = os.path.join(DIST, "catalog.html")
    if not os.path.isfile(catalog_path):
        print("FAIL: dist/catalog.html not found (run python3 build.py first)")
        return False
    with open(catalog_path, encoding="utf-8") as fh:
        content = fh.read()
    # Check meta-refresh pointing to browse.html
    pattern = re.compile(r'content=["\']0;url=([^"\']+)["\']', re.IGNORECASE)
    match = pattern.search(content)
    if not match:
        print("FAIL: dist/catalog.html has no meta-refresh redirect")
        return False
    dest = match.group(1)
    if "browse.html" not in dest:
        print("FAIL: dist/catalog.html redirects to %r, expected browse.html" % dest)
        return False
    print("OK:   dist/catalog.html → %s (meta-refresh)" % dest)

    # Check robots noindex
    if 'content="noindex"' not in content.lower() and "noindex" not in content.lower():
        print("WARN: dist/catalog.html missing noindex (bots could index the redirect page)")
    else:
        print("OK:   dist/catalog.html has noindex")

    return True


def report_counts(rows):
    if not rows:
        return
    by_path = {}
    for r in rows:
        by_path[r["old_path"]] = r["new_path"]
    print("\nRedirect map (%d entries):" % len(rows))
    for old, new in sorted(by_path.items()):
        print("  %-40s -> %s" % (old, new))


def main():
    errors = []

    rows = check_map()
    if rows is None:
        errors.append("redirect_map.csv missing")

    ok = check_catalog_html(rows)
    if not ok:
        errors.append("catalog.html redirect failed")

    report_counts(rows)

    if errors:
        print("\nFAILED: %d error(s)" % len(errors))
        sys.exit(1)
    else:
        print("\nPASS: all redirect checks passed")


if __name__ == "__main__":
    main()
