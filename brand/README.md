# Brand masters

Source art. **Not published** — `build.py` only copies `assets/`.

| File | What it is |
|---|---|
| `bestbmovies-master.png` | **Current.** 8000×8000 RGBA, real alpha. Artwork occupies 7380×5414 of that canvas (1.363:1); the rest is transparent padding. Master for everything on the site. |
| `logo-master.png` | Superseded. Flat vault mark from the Classic Films Vault identity. |
| `logo-3d-master.jpg` | Superseded. Glossy 3D render of the same vault mark. |

The two vault files are kept only as history of the previous identity. Nothing
on the site references them.

## Published assets, and why each is cut the way it is

| Asset | Size | Cut from |
|---|---|---|
| `assets/logo-lockup.png` | 440×323, 15 KB | Whole lockup, trimmed to the alpha bounding box. Shown at 148px wide (116px under 620px). |
| `assets/favicon-16.png` | 16×16 | B glyph only |
| `assets/favicon-32.png` | 32×32 | B glyph only |
| `assets/favicon-180.png` | 180×180 | B glyph only (apple-touch) |
| `assets/og-image.jpg` | 1200×630, 88 KB | Lockup centred on `--steel-dk`, flattened |

**The favicons are not the lockup shrunk down.** At 32px the full lockup is an
unreadable smear — the banner text goes first. They are a square crop centred on
the red B, which still reads at 16px. The crop is centred on the glyph itself,
not on the artwork, because the B sits ~275px left of the artwork's centre.

**The lockup is palette-quantised to 64 colours.** The halftone dots are
high-frequency detail that full-colour PNG compresses badly: the same image as
RGBA is 385 KB against 15 KB quantised, and at 148px the two are
indistinguishable.

**The social card is flattened on purpose.** A transparent PNG renders on
whatever backdrop the feed decides — usually white, sometimes black — so it is
composited on the brand dark and saved as JPEG, which needs no alpha.

`og:image` must be an absolute URL or scrapers ignore it, so the tag is only
emitted when `SITE_BASE` is set. CI sets it; a local `python3 build.py` does
not, and omits the tag rather than emitting a broken relative one.

## Regenerating

The published assets are derived; see the `PIL` steps in the rebrand commit, or
re-cut from `bestbmovies-master.png`: trim to the alpha bbox for the lockup, and
crop a 2000px square centred on the B glyph for the icons.
