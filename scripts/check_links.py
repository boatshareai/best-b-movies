#!/usr/bin/env python3 -I
"""
Check internal links in dist/ for broken references.
Also reports external URLs for review.

Usage (from repo root):
    python3 scripts/check_links.py

Exits 0 if no broken internal links, 1 otherwise.
"""

import html.parser
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(HERE, "dist")

ALLOWED_EXTERNAL_HOSTS = {
    "www.youtube-nocookie.com",   # YouTube embeds (only on play)
    "www.youtube.com",            # TikTok strip links
    "www.tiktok.com",
    "resend.com",                 # privacy policy links
    "www.cloudflare.com",
    "sitemaps.org",               # sitemap XML namespace
    "schema.org",                 # JSON-LD
    "bluefinchfilms.com",         # partner catalog source_url links
    "www.bluefinchfilms.com",
    "scfilmsinternational.com",   # partner catalog source_url links
    "www.scfilmsinternational.com",
}


class LinkExtractor(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        href = None
        if tag == "a":
            href = d.get("href")
        elif tag in ("link", "script"):
            href = d.get("href") or d.get("src")
        elif tag == "img":
            href = d.get("src")
        if href:
            self.links.append(href)


def collect_html_files():
    files = []
    for root, _, fnames in os.walk(DIST):
        for f in fnames:
            if f.endswith(".html"):
                files.append(os.path.join(root, f))
    return sorted(files)


def resolve(href, page_path):
    """Return (kind, resolved_path_or_url).
    kind: 'internal', 'external', 'anchor', 'mailto', 'skip'
    """
    href = href.strip()
    if not href or href.startswith("#"):
        return "anchor", href
    if href.startswith("mailto:") or href.startswith("tel:"):
        return "mailto", href
    parsed = urllib.parse.urlparse(href)
    if parsed.scheme in ("http", "https"):
        return "external", href
    if parsed.scheme:
        return "skip", href
    # Relative reference
    page_dir = os.path.dirname(page_path)
    path_part = parsed.path
    if not path_part:
        return "anchor", href
    resolved = os.path.normpath(os.path.join(page_dir, path_part))
    return "internal", resolved


def check_internal(resolved):
    """True if the path exists in dist/."""
    if os.path.isfile(resolved):
        return True
    if os.path.isdir(resolved):
        return os.path.isfile(os.path.join(resolved, "index.html"))
    return False


def main():
    if not os.path.isdir(DIST):
        print("FAIL: dist/ not found — run python3 build.py first")
        sys.exit(1)

    html_files = collect_html_files()
    broken = []
    external_urls = set()
    checked = 0

    for page_path in html_files:
        with open(page_path, encoding="utf-8") as fh:
            content = fh.read()
        parser = LinkExtractor()
        try:
            parser.feed(content)
        except Exception:
            pass
        rel_page = os.path.relpath(page_path, DIST)
        for href in parser.links:
            kind, resolved = resolve(href, page_path)
            if kind == "internal":
                checked += 1
                if not check_internal(resolved):
                    broken.append((rel_page, href, resolved))
            elif kind == "external":
                external_urls.add(href)

    print("Checked %d internal links across %d pages" % (checked, len(html_files)))

    # Warn about external URLs whose host isn't in ALLOWED_EXTERNAL_HOSTS
    unexpected_external = []
    for url in sorted(external_urls):
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower().lstrip("www.")
        if not any(host == h.lstrip("www.") for h in ALLOWED_EXTERNAL_HOSTS):
            unexpected_external.append(url)

    if unexpected_external:
        print("\nWARN: unexpected external URLs (review manually):")
        for u in unexpected_external:
            print("  " + u)
    else:
        print("OK:   external URLs all in allowed-hosts list")

    if broken:
        print("\nFAIL: %d broken internal link(s):" % len(broken))
        for page, href, resolved in sorted(broken):
            print("  [%s] %s" % (page, href))
        sys.exit(1)
    else:
        print("PASS: no broken internal links")


if __name__ == "__main__":
    main()
