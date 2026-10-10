# Velvet Octopus Rebrand — Site Inventory

Read-only audit of the two existing codebases. Nothing was changed to produce this document.

---

## 1. Best B Movies (the build-on codebase)

### Stack and hosting

| Item | Detail |
|---|---|
| Generator | `build.py` — pure Python 3, stdlib only, no pip install, no Node |
| Output | `dist/` — fully static HTML, JS, CSS, images |
| Hosting | GitHub Pages at `https://boatshareai.github.io/best-b-movies/` |
| Domain | No CNAME file; no custom domain currently wired |
| Deploy | Push to `main` → `.github/workflows/deploy.yml` → `python3 build.py` → upload `dist/` to Pages |
| Form handler | `functions/inquiry.js` — Cloudflare Workers / Pages Functions, uses Resend API; **not currently connected** (ENDPOINT in `assets/config.js` is blank) |

### Routes and pages

All URLs are relative to the site root. Film pages live under `films/`.

| URL | Page | Notes |
|---|---|---|
| `index.html` | Home | Hero, featured carousels, genre tiles, decade chips, how-licensing-works tiles |
| `catalog.html` | Catalogs | One art carousel per catalog with blurb |
| `browse.html` | Browse titles | Client-side search + filters, full payload baked into JSON blob in the page |
| `licensing.html` | Licensing & contact | Terms copy + inquiry form |
| `about.html` | About | Prose description of the three catalogs |
| `films/{slug}.html` | Film detail | 461 published film pages |
| `robots.txt` | Robots | No sitemap when built without SITE_BASE |

**Not present:** `submit.html`, `contact.html`, `privacy.html`, `404.html`

### Catalog data model

Three CSVs in `data/`. The build merges them; each row gets a `catalog` tag.

#### `catalog.csv` — Best B Movies own library (163 published, 2 hidden)

```
slug, title, year, decade, genres, language, runtime, logline,
status, licence_note, territory, credit, publish
```

- `genres` is `"; "`-delimited (e.g. `Drama; Film-Noir`)
- No `youtube_url` field — **adding this field is required for the Watch-on-YouTube filter and embed**
- No `poster` field — placeholder art is a monogram initial

#### `blue-finch.csv` — Blue Finch Film Releasing (209 published)

```
slug, title, year, decade, genres, language, country, runtime, logline,
poster, status, licence_note, territory, credit, director, writer, cast,
source_url, publish, cross_listed
```

#### `sc-films.csv` — SC Films International (89 published)

Same columns as `blue-finch.csv`.

### The three catalogs

| Key | Name | Size | Description (from code) |
|---|---|---|---|
| `best-b-movies` | Best B Movies | 163 | Classic Hollywood and international cinema, 1930s to today — westerns, noir, Rathbone-era mystery, gothic horror, and art-house landmarks |
| `blue-finch` | Blue Finch Film Releasing | 209 | Contemporary independent features, weighted to the 2010s and 2020s — led by horror, drama, and thriller |
| `sc-films` | SC Films International | 89 | Live action and family animation, plus documentary and genre titles. Year and runtime data is largely absent |

### Forms

**Licensing inquiry** (`licensing.html`):
- Fields: name (required), company (required), email (required), titles of interest, intended use (dropdown), estimated volume (dropdown), message
- Sends via `assets/inquiry.js` → POST to `CFV_CONFIG.ENDPOINT` in `assets/config.js`
- Handler: `functions/inquiry.js` — sends two emails via Resend: auto-reply to inquirer, notification to NOTIFY_TO inbox
- Required env vars: `RESEND_API_KEY`, `FROM_EMAIL`, `NOTIFY_TO`
- **Status: not connected** (ENDPOINT is empty string)

**Filmmaker submission:** No page exists in Best B Movies. Cinema Thrift has one (see §2 below).

### YouTube embeds

None. No YouTube URLs in any catalog CSV and no embed code anywhere in the site.

### Analytics

None. No Google Analytics, no Plausible, no script tags for any tracking.

### JSON-LD structured data

None. No schema.org markup anywhere.

### Every place the old names appear

This is the complete list of strings that need to change.

#### In `build.py` (source of truth — all generated output inherits these)

| Variable / location | Current value | Change to |
|---|---|---|
| `SITE_NAME` (line 33) | `"Best B Movies"` | `"Velvet Octopus Films"` |
| `OWN_CATALOG` (line 35) | `"best-b-movies"` | keep key; display name changes below |
| `CATALOGS[0]["name"]` | `"Best B Movies"` | `"Best B Movies"` ← **keep as collection name** |
| `TAGLINE` (line 82) | `"B-movie licensing"` | `"Films worth a second look."` |
| `LICENSING_TERMS` copy | mentions "Best B Movies" (×2) | update brand name |
| `CONFIRMATION` | "we've got your inquiry…" — unsigned | add "— Velvet Octopus Films" |
| `page()` template — footer | `© 2026 Best B Movies. Licensing inquiries only…` | `© 2026 Velvet Octopus Films…` |
| `page()` template — footer text | `Licensing inquiries only — this site does not stream or sell films.` | update or keep (still accurate) |
| `page()` template — header logo `alt` | `"Best B Movies"` | `"Velvet Octopus Films"` |
| `page()` template — header `<span class="mark">` | `Licensing & distribution` | `Films worth a second look.` or remove |
| `page()` template — `og:site_name` | `"Best B Movies"` | `"Velvet Octopus Films"` |
| `page()` template — default meta description | mentions all three catalog names | update |
| `build_home()` — hero headline | `Better Movies. Brought To You.` | new copy per brief |
| `build_home()` — hero pitch | references "Blue Finch Film Releasing and SC Films International" | keep; only brand changes |
| `build_home()` — `description=` kwarg | "An independent film distributor…Best B Movies…" | update |
| `build_home()` — "How licensing works" tile | "163 titles in the Best B Movies library…" | update count + brand |
| `build_home()` — "Nothing hidden" tile | "69 Best B Movies titles currently carry…" | update brand |
| `build_licensing()` — `LICENSING_TERMS` | "Best B Movies represents a library of…" | update brand |
| `build_licensing()` — second paragraph | "the Classic Films Vault library specifically" | ← **old name; fix now** |
| `build_about()` — text | "Best B Movies is an independent distribution outfit…" | update brand |
| `build_about()` — h2 | `<h2>Best B Movies</h2>` | `<h2>Best B Movies</h2>` ← **keep as collection name** |

#### In `assets/site.css`

- Comment on line 1: `/* Best B Movies — licensing portfolio */`
- Entire palette: red/yellow/black (Anton display font) → replace with Velvet Octopus palette (Velvet/Deep/Cream/Lilac/Gold, Poppins)

#### In `assets/config.js`

- Comment references "Best B Movies" — update

#### In `functions/inquiry.js`

| Location | Current | Change to |
|---|---|---|
| `from:` field in sendEmail | `Best B Movies <${env.FROM_EMAIL}>` | `Velvet Octopus Films <${env.FROM_EMAIL}>` |
| auto-reply sign-off | `— Best B Movies` | `— Velvet Octopus Films` |
| auto-reply subject | `"We received your Best B Movies inquiry"` | `"We received your Velvet Octopus Films inquiry"` |
| notification subject | `New licensing inquiry — ${company}` | keep (no brand name in it) |

#### In `assets/og-image.jpg`

Replace with `og-image.png` from brand kit.

#### In `assets/logo-lockup.png` and `assets/brand-logo` reference

Replace with SVG logos from brand kit (see §3 below for which files go where).

#### In `assets/favicon-16.png`, `favicon-32.png`, `favicon-180.png`

Replace with `favicon.ico`, `favicon.svg`, `apple-touch-icon.png` from brand kit.

#### In `assets/fonts/`

Replace Anton woff2 files with Poppins woff2 files from brand kit.

#### In generated `dist/`

All of the above, baked in — regenerated from source on each build.

#### In sitemap.xml (generated)

No brand names; URLs only. No change needed.

#### In `dist/robots.txt`

No brand names. No change needed.

---

## 2. Cinema Thrift (retired — reuse submit page only)

### Stack and hosting

Plain static HTML in a zip (`/Users/joshuajoynes/Downloads/cinema-thrift.zip`). Art Deco look. No build process. Not currently deployed anywhere.

### Pages

| File | Page |
|---|---|
| `index.html` | Home |
| `catalog.html` | Catalog |
| `browse.html` | Browse |
| `licensing.html` | Licensing |
| `submit.html` | Drop Off a Film (filmmaker submission) |
| `about.html` | About |
| `films/bicycle-thieves-1948.html` | Sample film page |
| `films/stagecoach-1939.html` | Sample film page |

### Filmmaker submission form (`submit.html`) — worth porting

Fields: name, email, film title, year, genre, runtime, synopsis, trailer/screener link, current distribution status, rights confirmation.

The form is a mockup (`onsubmit="alert(...)"`) — not wired to any endpoint. It covers all the right fields. The new "Submit a film" page should use these fields and wire them to the same inquiry handler pattern as the licensing form.

---

## 3. Brand kit location

Unzipped at `/Users/joshuajoynes/Desktop/velvet-octopus-brand/`. Contents needed by the site:

| Kit path | Copy to |
|---|---|
| `public-brand/favicon.ico` | `assets/favicon.ico` |
| `public-brand/favicon.svg` | `assets/favicon.svg` |
| `public-brand/apple-touch-icon.png` | `assets/apple-touch-icon.png` |
| `public-brand/og-image.png` | `assets/og-image.png` |
| `public-brand/logo-wordmark.svg` | `assets/brand/logo-wordmark.svg` |
| `public-brand/logo-wordmark-velvet.svg` | `assets/brand/logo-wordmark-velvet.svg` |
| `public-brand/logo-stacked.svg` | `assets/brand/logo-stacked.svg` |
| `public-brand/logo-stacked-velvet.svg` | `assets/brand/logo-stacked-velvet.svg` |
| `public-brand/logo-icon.svg` | `assets/brand/logo-icon.svg` |
| `public-brand/logo-icon-simple.svg` | `assets/brand/logo-icon-simple.svg` |
| `public-fonts/Poppins-Bold.woff2` | `assets/fonts/Poppins-Bold.woff2` |
| `public-fonts/Poppins-Light.woff2` | `assets/fonts/Poppins-Light.woff2` |
| `public-fonts/Poppins-Regular.woff2` | `assets/fonts/Poppins-Regular.woff2` |
| `public-fonts/Poppins-Medium.woff2` | `assets/fonts/Poppins-Medium.woff2` |
| `public-fonts/FONT-LICENSE.txt` | `assets/fonts/FONT-LICENSE.txt` |

The `brand-kit/` folder must not be committed. The files above are copied into the tracked `assets/` tree.

---

## 4. Gaps and new pages needed

| Item | Status | Notes |
|---|---|---|
| `youtube_url` field in catalog.csv | Missing | Add column; blank for all existing rows. Film page shows embed when populated; browse "Watch on YouTube" filter hides rows with blank value |
| `submit.html` (filmmaker submission) | Missing from Best B Movies | Port from Cinema Thrift; wire to a new `functions/submission.js` or reuse inquiry handler with a `type` field |
| `contact.html` | Doesn't exist | Contact copy + email links from config; no separate form needed if licensing form stays the inquiry channel |
| `privacy.html` / `terms.html` | Doesn't exist | Placeholder copy; Josh fills in detail |
| `404.html` | Doesn't exist | Friendly static page |
| Analytics | None | No change required unless Josh requests it |
| JSON-LD | None | Worth adding `Movie` schema to film pages; not blocking |

---

## 5. Recommendation: proceed as planned

None of the above discoveries change the plan. The `youtube_url` gap is expected — the brief already calls for it. The missing pages (submit, privacy, 404) are all on the build list. The form being unconnected is an existing condition, not a regression. Build on `velvet-octopus` branch; no DNS, no deploy, no merge.
