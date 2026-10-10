# Velvet Octopus Films — Build Report

Branch: `velvet-octopus`  
Build: `python3 build.py` → 470 pages in `dist/`  
Date: 2026-10-10

---

## Final pass — PASS / FIXED table

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Security headers (`_headers`) | **FIXED** | `_headers` created at repo root; copied into `dist/` by `build.py`. CSP: `default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; frame-src https://www.youtube-nocookie.com; connect-src 'self' https://*.workers.dev; form-action 'self'; base-uri 'self'; frame-ancestors 'none'`. No `unsafe-inline` anywhere. All inline `style=""` attributes replaced with CSS utility classes. |
| 2 | SEO (canonical, JSON-LD, noindex, OG) | **FIXED** | `page()` in `build.py` now emits canonical `<link>`, JSON-LD Organization sitewide, JSON-LD Movie on film pages, og:image (poster on film pages, `og-image.png` on others), noindex when `NOINDEX` env var is set. `SITE_BASE=https://velvetoctopusfilms.com python3 build.py` generates `sitemap.xml` and correct canonicals. |
| 3 | Redirects (`catalog.html` → `browse.html`) | **FIXED** | `build_catalog_redirect()` now points to `browse.html` (was `collections.html`). `scripts/check_redirects.py` passes: `dist/catalog.html` has `<meta http-equiv="refresh" content="0;url=browse.html">` + noindex. `scripts/redirect_map.csv` lists 2 entries for `/catalog.html` and `/catalog`. |
| 4 | Search (`intl=1` filter) | **FIXED** | `catalog.js` now has a dedicated `intlCb` checkbox. `intlOnly` filter shows films where `f.l && f.l.toLowerCase() !== "english"`. Previously `intl=1` incorrectly set `langSel.value = "__none"` (meaning "language not specified"). All 6 browse filters (q, catalog, genre, decade, lang, runtime, status, yt, intl, sort) are persisted in URL params. |
| 5 | About page | **FIXED** | `build_about()` rewritten with real content. Contains `<!-- TODO confirm wording with former owners -->` in HTML source (not visible), followed by: "Velvet Octopus began as a film distributor. Its owners later rebranded it as SC Films International and Blue Finch Film Releasing. We're bringing the name back, with their blessing." |
| 6 | Privacy page | **FIXED** | `build_privacy()` rewritten: covers no-analytics, no-cookies-set, YouTube via youtube-nocookie.com on click only, forms via Resend (transactional only, data deleted when no longer useful), links to Resend and Cloudflare privacy policies, contact email `hello@velvetoctopusfilms.com`. No placeholders. |
| 7 | Reference update (why_watch, catalog ID, carousels) | **FIXED** | `why_watch` column added to all 3 CSVs (blank; shown on film pages when filled). Film pages show catalog ID badge (`.catalog-id`) and "Represented by" link. Licensing form URL prefilled with `?title=…&catalog=…`. Criterion-pattern carousels: each collection shows a one-line `cat["reason"]` under the heading. |
| 8 | Screenshots | **DONE** | 6 images in `docs/velvet-octopus/screenshots/`: `home-375.jpg`, `home-1280.jpg`, `browse-375.jpg`, `browse-1280.jpg`, `film-375.jpg`, `film-1280.jpg`. Preview server: `python3 -m http.server -d dist 8000` → http://localhost:8000 |
| 9 | Final checks | **PASS** | `python3 build.py` → clean, 470 pages. `python3 scripts/check_links.py` → PASS (15,957 internal links, 0 broken, all external hosts in allowed list). `python3 scripts/check_redirects.py` → PASS. `git log -S RESEND` → only `.env.example` placeholder and Worker env-var references, no real key. `.env.example` present. No external requests except `youtube-nocookie.com` on click (enforced by CSP `frame-src` + JS deferred load). |

---

## What was built

### Brand & assets

- **Poppins woff2 fonts** (Bold/Medium/Regular/Light) copied from brand kit into `assets/fonts/` — self-hosted, no external font requests.
- **Logo SVGs** (wordmark, stacked, icon, icon-simple, all in cream and velvet variants) in `assets/brand/`.
- **Favicons**: `favicon.ico`, `favicon.svg`, `apple-touch-icon.png`, `og-image.png` — replacing the old PNG set.

### CSS — `assets/site.css` (complete rewrite)

| Old | New |
|---|---|
| Anton display font | Poppins (Bold headings, Light/Regular body) |
| Red `#fa0a14` primary | Velvet `#5B2A86` primary |
| Light white header | Dark velvet header |
| Light white hero | Dark velvet hero with faint icon watermark |
| White footer | Deep `#2B1342` footer |
| Gold `--blue: #0063a6` buttons | Gold `#F2B84B` primary action buttons (text: --deep) |
| Table layout for browse | Poster card grid (2:3 `aspect-ratio`) |
| Inline `style=""` attributes | CSS utility classes (CSP-compliant: no `unsafe-inline`) |

Full palette: `--velvet: #5B2A86`, `--deep: #2B1342`, `--cream: #F4EBDD`, `--lilac: #CDB4E6`, `--gold: #F2B84B`.  
WCAG contrast (from brand kit): cream on velvet 8.4:1, cream on deep 13.9:1, deep on gold 9.2:1 — all AA or better.

### Generator — `build.py` (complete rewrite)

| Page | URL | Notes |
|---|---|---|
| Home | `index.html` | Hero copy, stacked logo, TikTok strip, three-collection links |
| Collections | `collections.html` | Criterion-pattern carousels with one-line curation reason per collection |
| Catalog redirect | `catalog.html` | meta-refresh + noindex → `browse.html` |
| Browse | `browse.html` | Card grid, 9 filters, URL param persistence |
| Licensing | `licensing.html` | Updated copy, honeypot, mailto fallback when ENDPOINT blank |
| Submit a film | `submit.html` | Film submission form with rights confirmation |
| About | `about.html` | Real content, includes founder note with HTML comment |
| Contact | `contact.html` | Email links, TikTok link |
| Privacy & terms | `privacy.html` | Real text — no analytics, no cookies, YouTube click-only, Resend disclosure |
| 404 | `404.html` | Friendly page |
| Film pages | `films/{slug}.html` | JSON-LD Movie, og:image from poster, why_watch block, catalog ID badge, related films strip, licensing URL prefilled |

Every page:
- `<title>` and unique `<meta name="description">`
- `<link rel="canonical">` (when `SITE_BASE` set)
- JSON-LD Organization (sitewide)
- `<meta name="robots" content="noindex, nofollow">` when `NOINDEX=1`

### Security headers — `_headers`

```
/*
  Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; frame-src https://www.youtube-nocookie.com; connect-src 'self' https://*.workers.dev; form-action 'self'; base-uri 'self'; frame-ancestors 'none'
  Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()
  X-Frame-Options: DENY
```

No `unsafe-inline` in `style-src` or `script-src`. All inline `style=""` attributes are replaced by CSS utility classes (`.section-h2`, `.mt-action`, `.mt-prose`, `.mt-form-card`, `.browse-similar-head`, `.why-watch`, `.catalog-strip`, `.catalog-id`).

### Data — `youtube_id` and `why_watch` columns

Both columns added (all blank) to all three catalog CSVs:
- `data/catalog.csv` (163 rows, 2 marked publish=no)
- `data/blue-finch.csv` (209 rows)
- `data/sc-films.csv` (89 rows)

To set YouTube IDs: `python3 scripts/set_youtube_url.py your-ids.csv`  
To set a curator note: edit `why_watch` column in the relevant CSV and rebuild.

### JavaScript

| File | Purpose |
|---|---|
| `assets/config.js` | `window.VOF_CONFIG` — ENDPOINT, SUBMISSION_ENDPOINT, email addresses |
| `assets/catalog.js` | Browse card grid: render, filter, sort, URL param persistence. Fixed `intl=1` to filter non-English (not "language not specified"). |
| `assets/inquiry.js` | Licensing form handler — VOF_CONFIG, mailto fallback when ENDPOINT blank, honeypot |
| `assets/submit.js` | Film submission form handler — same pattern |
| `assets/yt-embed.js` | Click-to-play YouTube-nocookie embed (no network request until click) |
| `assets/carousel.js` | Collection carousels — unchanged from original |

### Cloudflare Worker handlers

| File | Route | Env vars needed |
|---|---|---|
| `functions/inquiry.js` | POST `/inquiry` | RESEND_API_KEY, FROM_EMAIL, NOTIFY_TO, ALLOW_ORIGIN |
| `functions/submission.js` | POST `/submission` | RESEND_API_KEY, FROM_EMAIL, SUBMISSION_NOTIFY_TO, ALLOW_ORIGIN |

Both workers:
- Validate and sanitize all input (max lengths, allowlists for dropdowns)
- Check `Origin` header against `ALLOW_ORIGIN` env var
- Server-side honeypot check (silent success for bots)
- Basic in-memory rate limiting (5 req/IP/60s for inquiry; 3/IP/60s for submission)
- Send via Resend API — key never touches the browser

### Scripts

| File | Purpose |
|---|---|
| `scripts/set_youtube_url.py` | Bulk-set `youtube_id` in `data/catalog.csv` from a slug,url CSV |
| `scripts/check_redirects.py` | Validates `redirect_map.csv` and that `dist/catalog.html` → `browse.html` |
| `scripts/check_links.py` | Checks all internal links in `dist/` for broken references; reports external URLs |
| `scripts/redirect_map.csv` | Old-path → new-path mapping for documentation |

---

## Redirect map

| Old path | New path | Method |
|---|---|---|
| `/catalog.html` | `/browse.html` | `<meta http-equiv="refresh">` + `<link rel="canonical">` + noindex |
| `/catalog` | `/browse.html` | Same (documented in redirect_map.csv) |
| All `films/{slug}.html` | Same — slugs unchanged | n/a |
| `/licensing.html`, `/about.html`, `/browse.html` | Same | n/a |

Old film page slugs are untouched — no 301s needed for existing links.

---

## Form setup steps

### 1. Create a Resend account and verify your domain

1. Sign up at [resend.com](https://resend.com).
2. Add `velvetoctopusfilms.com` under **Domains** and add the DNS records it gives you.
3. Create an API key under **API Keys**. Copy it — you won't see it again.

### 2. Deploy the Workers to Cloudflare

The Workers live in `functions/`. Deploy with Cloudflare Pages (easiest) or Wrangler CLI.

**With Cloudflare Pages:**
1. Connect your GitHub repo to a new Cloudflare Pages project.
2. Leave the build command blank (this repo builds locally, not on CF).
3. Set the Functions directory to `functions/`.
4. Under **Settings → Environment Variables**, add:

| Variable | Value |
|---|---|
| `RESEND_API_KEY` | your key from step 1 |
| `FROM_EMAIL` | `licensing@velvetoctopusfilms.com` (must be verified in Resend) |
| `NOTIFY_TO` | inbox for licensing inquiry notifications |
| `SUBMISSION_NOTIFY_TO` | inbox for film submissions |
| `ALLOW_ORIGIN` | `https://velvetoctopusfilms.com` (exact origin, no trailing slash) |

**With Wrangler:**
```bash
cd functions
npx wrangler deploy inquiry.js --name vof-inquiry
npx wrangler deploy submission.js --name vof-submission
```
Set secrets: `npx wrangler secret put RESEND_API_KEY --name vof-inquiry` (repeat for each var).

### 3. Wire up config.js

Once the Workers are deployed, copy their URLs into `assets/config.js`:

```js
window.VOF_CONFIG = {
  ENDPOINT: "https://vof-inquiry.your-account.workers.dev",
  SUBMISSION_ENDPOINT: "https://vof-submission.your-account.workers.dev",
  SITE_CONTACT_EMAIL: "hello@velvetoctopusfilms.com",
  LICENSING_EMAIL: "licensing@velvetoctopusfilms.com",
  YOUTUBE_CHANNEL_URL: "",  // fill in once the channel handle is confirmed
};
```

Then rebuild: `python3 build.py` and deploy `dist/`.

**Until ENDPOINT is set:** both forms show a visible "Email us at …" fallback with a mailto link. Neither form fails silently.

### 4. Production build

```bash
SITE_BASE=https://velvetoctopusfilms.com python3 build.py
```

This generates `sitemap.xml`, correct canonical URLs, and `robots.txt` with the sitemap reference.

For CI/preview deploys:

```bash
SITE_BASE=https://preview.velvetoctopusfilms.com NOINDEX=1 python3 build.py
```

---

## Analytics

None added. No Google Analytics, no Plausible, no script tags for any tracking.  
The site shipped without analytics and remains that way. Confirmed by CSP: `connect-src 'self' https://*.workers.dev` — no analytics endpoints permitted.

---

## Open TODOs

| Item | File | Notes |
|---|---|---|
| Confirm wording with former owners | `build.py` → `build_about()` | HTML comment already in source; just remove it when confirmed |
| `ENDPOINT` in config.js | `assets/config.js` | Set once Workers are deployed |
| `YOUTUBE_CHANNEL_URL` | `assets/config.js` | Set once channel handle is confirmed |
| YouTube IDs | `data/catalog.csv` | Use `scripts/set_youtube_url.py` to bulk-add |
| Curator notes | All 3 CSVs `why_watch` column | Fill in when curated text is ready; shown on film pages only when set |
| DNS / domain | — | Not done. Hard rule: no DNS changes in this session |
| Deploy | — | Not done. Hard rule: no deploy in this session |
