# Public-information sourcing pass — loglines and posters

Run 16 September 2026. Scope was loglines for the Blue Finch and SC Films
catalogs, and poster art for all three. Territory data, the genre-label
rollup, *Run To The High Country* and the *Awaydays* year conflict were
explicitly out of scope and were not touched.

## Result

| Catalog | Titles | Loglines before | Loglines after | Posters |
|---|---|---|---|---|
| Classic Films Vault | 165 | 165 | 165 *(already complete)* | 0 — see below |
| Blue Finch Film Releasing | 209 | 0 | **208** | **208** |
| SC Films International | 89 | 0 | **88** | **89** |
| **Total** | **463** | **165** | **461** | **297** |

296 loglines and 297 poster images were added, and one wrong logline/poster pair
was corrected. Two gaps remain, listed below.

Run in two passes. The first resolved 279 titles by slug-matching against the
agency sitemaps and category indexes, leaving 19 unmatched. The second was a
multi-agent sweep over those 19 — one searcher per title, then two independent
adversarial verifiers per hit, both required to clear it — which resolved 18 of
them and, in passing, caught an error the first pass had introduced.

## Correction to the brief

The brief put the outstanding loglines at 197 (Blue Finch) and 73 (SC Films).
Neither the local CSVs nor the live repo had *any* agency loglines — the true
starting figures were 209 and 89, all 298 empty. The brief's 298 total was
right; the per-catalog split was not.

## Method

**Loglines.** Each title page on `bluefinchfilms.com` or
`scfilmsinternational.com` was fetched and its synopsis block parsed out.
Loglines were then written from scratch in the catalog's existing plain,
factual house style — marketing framing ("a gripping neo-noir horror"),
comparison titles ("*Ex Machina* meets *2001*"), star billing and festival
laurels were dropped. No site copy is reproduced verbatim. Where a page's
synopsis stopped short, the logline says only what the page actually
asserts rather than filling the gap from elsewhere.

**Posters.** Key art was taken from the same pages, identified by portrait
aspect ratio plus filename, which separates one-sheets from the production
stills and cast headshots that also sit on those pages. `og:image` is the
site logo on both sites and was not used. Images are saved as
`assets/posters/<slug>.jpg`, downscaled to 600px wide (the card renders at
300×450) and re-encoded as progressive JPEG: 111 MB of source art became
26 MB across 297 files. Verified by eye against the slug on a labelled
contact sheet — a 24-title random sample from the first pass (24/24 correct)
and all 18 from the second (18/18 correct).

## Gaps — no confident match found

Two titles remain unresolved out of 463.

- **Head Count** (Blue Finch, 2018) — no page found on `bluefinchfilms.com`
  under any slug variant, via the site's own WordPress search, via `site:`
  queries, or in the sitemap. No logline, no poster.
- **The Boxcar Children** (SC Films) — the page exists and the poster was
  obtained, but the page carries only voice-cast and director credits with no
  plot text at all. Re-checked directly against every `<p>` in the page body
  after a verifier claimed a synopsis was present; there isn't one. Logline
  left blank.

The other 17 of the original 19 gaps were closed in the second pass. They had
been missed because the first pass only probed `/library/`, `/coming-soon/`
and `/new-releases/`. Blue Finch also publishes titles under
**`/international-sales/<slug>/`**, and several titles sit at non-obvious
slugs: `library/beast/` (Beast Beast), `library/ghtg/` (God Help the Girl),
`library/yckda/` (You Cannot Kill David Arquette), `library/good-boy-uk/` and
`library/next-exit-uk/` (a `-uk` territory suffix), `marmaduke-3d`, and
`current-films-live-action-titles/dusk/` for **Deathkeeper**, whose page slug
and `<title>` still carry its former working title *Dusk*.

## Errors found in the agencies' own material

Three separate defects on the source sites, all of which would corrupt a
naive scrape:

1. **`library/the-east/` serves the wrong film.** That URL's page is headed
   *Beast Beast* and carries Danny Madden's credits, runtime and synopsis.
   The first pass matched the catalog's *The East* to it and filed Beast
   Beast's plot and key art against that row. **This was caught and
   corrected in the second pass**: the genuine page is
   `library/the-east-2/` (WordPress appended `-2` because the slug was
   taken), and it is Jim Taihuttu's Dutch/Indonesian war film — Netherlands,
   Dutch language, 137 minutes. The row now carries that film's logline and
   poster. Every one of the 271 first-pass pages was then re-checked by
   comparing its on-page heading against the catalog title; this was the only
   genuine mismatch.

2. **`library/fivefingersformarseilles/` has *Lords of Anarchy*'s copy**
   pasted below its own one-line description. The correct line was used.

3. **Every Blue Finch page carries stale Open Graph / schema.org metadata**
   describing an unrelated animated film ("a brave city mouse joins a ship
   full of pirates"), and `og:image` is the site header logo rather than the
   key art. Both verifier lenses flagged this independently on nearly every
   page they checked. Nothing here was sourced from `og:` tags — synopses
   come from the rendered body and posters from in-body `<img>` elements —
   but anything built against this site later should know.

## Two things worth knowing

**The `poster` column is only read by `build_featured()`.** Film detail pages
and the browse table render no poster art at all, so only the 6 Blue Finch /
SC Films titles among the 12 `FEATURED` entries display art today. The other
274 images are data in place, waiting on a template change that was not part
of this pass.

**Classic Films Vault posters (165) were not sourced.** There is no
rights-holder site for that catalog. IMDb's conditions of use prohibit
scraping, and TMDB's image API needs a key that does not exist anywhere in
the project. `data/catalog.csv` therefore still has no `poster` column.
Supply a TMDB API key and this becomes a single re-run.

## Also repaired in passing

This local copy of `site/` was a partial export and could not build: it was
missing `data/catalog.csv` entirely, `data/sc-films.csv` was 0 bytes, and
`assets/` held none of the CSS, JS or logo files. All were restored from
`github.com/boatshareai/classic-films-vault` (the live source of truth, whose
`blue-finch.csv` was byte-identical to the local one). `python3 build.py`
now produces all 463 film pages with no missing asset references.
