#!/usr/bin/env python3 -I
"""
WCAG AA contrast checker for Velvet Octopus Films color tokens.

Usage (from repo root):
    python3 scripts/check_contrast.py

Checks every text/background pair defined in the design against WCAG AA:
  - Normal text: contrast ratio >= 4.5:1
  - Large text (18pt+ or 14pt+ bold): contrast ratio >= 3:1

Exits 0 if all pairs pass, 1 if any fail.
"""

import math
import sys


# ── Color tokens ──────────────────────────────────────────────────────────────
COLORS = {
    "ground":   "#0E0915",
    "surface":  "#181022",
    "line":     "#2C2139",
    "line_form":"#5A4A70",
    "cream":    "#F4EBDD",
    "muted":    "#B8A9CC",
    "velvet":   "#5B2A86",
    "gold":     "#F2B84B",
    "white":    "#FFFFFF",
    "black":    "#000000",
}


# ── Pairs to check: (text_token, bg_token, description, large_text) ──────────
PAIRS = [
    # Body text on main backgrounds
    ("cream",    "ground",   "body text on page background",        False),
    ("cream",    "surface",  "body text on card surface",            False),
    ("muted",    "ground",   "muted text on page background",        False),
    ("muted",    "surface",  "muted text on card surface",           False),

    # Navigation / header
    ("cream",    "ground",   "nav links on header",                  False),

    # Buttons
    ("ground",   "gold",     "primary button text on gold",          False),
    ("cream",    "surface",  "outline button text on surface",       False),
    ("cream",    "velvet",   "active pill text on velvet",           False),

    # Active filter pills
    ("cream",    "velvet",   "filter pill text (active)",            False),

    # Badges
    ("cream",    "ground",   "badge text on ground",                 False),

    # Large display headings (bold, 48px+)
    ("cream",    "ground",   "hero heading on page background (large)", True),
    ("cream",    "surface",  "section heading on surface (large)",   True),

    # Footer
    ("muted",    "ground",   "footer text on ground",                False),
    ("cream",    "ground",   "footer links on ground",               False),

    # Tags / chips
    ("muted",    "surface",  "tag text on surface",                  False),
]


def hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def linearize(c):
    s = c / 255.0
    if s <= 0.04045:
        return s / 12.92
    return ((s + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color):
    r, g, b = hex_to_rgb(hex_color)
    rl = linearize(r)
    gl = linearize(g)
    bl = linearize(b)
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl


def contrast_ratio(hex1, hex2):
    l1 = relative_luminance(hex1)
    l2 = relative_luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def main():
    failures = []
    rows = []

    for text_tok, bg_tok, desc, large in PAIRS:
        text_hex = COLORS[text_tok]
        bg_hex = COLORS[bg_tok]
        ratio = contrast_ratio(text_hex, bg_hex)
        threshold = 3.0 if large else 4.5
        passed = ratio >= threshold
        rows.append((desc, text_tok, bg_tok, ratio, threshold, passed))
        if not passed:
            failures.append((desc, text_tok, bg_tok, ratio, threshold))

    col_w = max(len(r[0]) for r in rows) + 2
    header = "%-*s  %-10s  %-10s  %8s  %9s  %s" % (
        col_w, "Pair", "Text", "Bg", "Ratio", "Required", "Result"
    )
    print(header)
    print("-" * len(header))
    for desc, tt, bt, ratio, threshold, passed in rows:
        status = "PASS" if passed else "FAIL"
        print("%-*s  %-10s  %-10s  %8.2f  %9.1f  %s" % (
            col_w, desc, tt, bt, ratio, threshold, status
        ))

    print()
    if failures:
        print("FAIL: %d pair(s) below WCAG AA:" % len(failures))
        for desc, tt, bt, ratio, threshold in failures:
            print("  [%s on %s] %s — %.2f:1 (need %.1f:1)" % (
                tt, bt, desc, ratio, threshold
            ))
        sys.exit(1)
    else:
        print("PASS: all %d pairs meet WCAG AA" % len(rows))


if __name__ == "__main__":
    main()
