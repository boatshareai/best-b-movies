# Velvet Octopus Films — Build Report

Branch: `velvet-octopus`  
Build: `python3 build.py` → 470 pages in `dist/`  
Date: 2026-10-10

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

Full palette: `--velvet: #5B2A86`, `--deep: #2B1342`, `--cream: #F4EBDD`, `--lilac: #CDB4E6`, `--gold: #F2B84B`.  
WCAG contrast (from brand kit): cream on velvet 8.4:1, cream on deep 13.9:1, deep on gold 9.2:1 — all AA or better.

### Generator — `build.py` (complete rewrite)

| Page | URL | Notes |
|---|---|---|
| Home | `index.html` | New hero copy, stacked logo, TikTok strip, VO branding |
| Collections | `collections.html` | Renamed from Catalogs; same carousel layout |
| Catalog redirect | `catalog.html` | HTTP-refresh redirect → `collections.html` |
| Browse | `browse.html` | Card grid, YouTube filter checkbox, sort dropdown |
| Licensing | `licensing.html` | Updated brand copy, honeypot field |
| Submit a film | `submit.html` | New — Cinema Thrift fields ported |
| About | `about.html` | Updated branding + TODO flag for VO history |
| Contact | `contact.html` | New — email links, TikTok link |
| Privacy & terms | `privacy.html` | New — placeholder, no-analytics note |
| 404 | `404.html` | New — friendly page |
| Film pages | `films/{slug}.html` | YouTube embed when `youtube_id` set; gold "License this film" CTA when blank; related films strip |

### Data — `youtube_id` column

Added `youtube_id` column (all blank) to all three catalog CSVs:
- `data/catalog.csv`
- `data/blue-finch.csv`
- `data/sc-films.csv`

To populate: `python3 scripts/set_youtube_url.py your-ids.csv`

Input CSV format (header optional):
```
slug,url
stagecoach-1939,https://www.youtube.com/watch?v=XXXXXXXXXXX
```

The script validates only `youtube.com` and `youtu.be` URLs and stores the bare 11-char video ID.

### JavaScript

| File | Purpose |
|---|---|
| `assets/config.js` | `window.VOF_CONFIG` — ENDPOINT, SUBMISSION_ENDPOINT, email addresses |
| `assets/catalog.js` | Browse card grid: render, filter, sort, URL param persistence |
| `assets/inquiry.js` | Licensing form handler — VOF_CONFIG, mailto fallback, honeypot |
| `assets/submit.js` | Filmmaker submission form handler — same pattern |
| `assets/yt-embed.js` | Click-to-play YouTube-nocookie embed |
| `assets/carousel.js` | Unchanged from original |

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

---

## Redirect map (old URL → new URL)

| Old | New | Method |
|---|---|---|
| `catalog.html` | `collections.html` | `<meta http-equiv="refresh">` + `<link rel="canonical">` |
| All `films/{slug}.html` | Same — slugs unchanged | n/a |
| `licensing.html` | Same | n/a |
| `about.html` | Same | n/a |
| `browse.html` | Same | n/a |

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

---

## Analytics

None added. No Google Analytics, no Plausible, no script tags for any tracking.  
The site shipped without analytics and remains that way.

---

## Open TODOs

| Item | File | Notes |
|---|---|---|
| VO history copy | `build.py` → `build_about()` | Placeholder with TODO flag; Josh fills in |
| Privacy policy detail | `build.py` → `build_privacy()` | Placeholder; legal team fills in |
| `ENDPOINT` in config.js | `assets/config.js` | Set once Workers are deployed |
| `YOUTUBE_CHANNEL_URL` | `assets/config.js` | Set once channel handle is confirmed |
| YouTube IDs | `data/catalog.csv` | Use `scripts/set_youtube_url.py` to bulk-add |
| DNS / domain | — | Not done. Hard rule: no DNS changes in this session |
| Deploy | — | Not done. Hard rule: no deploy in this session |
