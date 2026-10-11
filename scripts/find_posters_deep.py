#!/usr/bin/env python3
"""
find_posters_deep.py — deeper Wikimedia Commons poster search.

Tries multiple query strategies per film:
  1. English title + year + "film poster"
  2. English title + "film poster" (no year)
  3. Original/alternate language title + year
  4. Original title alone
  5. Short title (first 3 words) + year

Also loosens year matching for pre-1970 films (public domain) since their
Commons files often omit the year or use slightly different spellings.

Run from the repo root:
    python3 -I scripts/find_posters_deep.py
"""

import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(HERE, "data")
ASSETS_POSTERS = os.path.join(HERE, "assets", "posters")
POSTERS_CSV = os.path.join(DATA_DIR, "posters.csv")
CACHE_FILE = os.path.join(HERE, ".poster-cache-deep.json")

POSTERS_CSV_COLS = ["slug", "original_filename", "imported_date", "width", "height",
                    "low_res", "license", "author", "source_url"]

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = (
    "VelvetOctopusFilms/1.0 (velvetoctopusfilms.com; "
    "licensing@velvetoctopusfilms.com) film-catalog-tool"
)
CACHE_TTL_DAYS = 7

# ---------------------------------------------------------------------------
# Original / alternate titles for international and hard-to-find films
# ---------------------------------------------------------------------------

ORIGINAL_TITLES = {
    "bicycle thieves":                        ["Ladri di biciclette"],
    "black sabbath":                          ["I tre volti della paura", "Black Sabbath 1963"],
    "a woman without love":                   ["Una mujer sin amor"],
    "i vitelloni":                            ["I vitelloni 1953", "vitelloni Fellini"],
    "throne of blood":                        ["Kumonosu-jo", "Kumonosujo Kurosawa"],
    "woman in the dunes":                     ["Suna no onna", "Woman in the Dunes 1964"],
    "the exterminating angel":               ["El ángel exterminador", "Bunuel exterminating"],
    "the trial":                              ["Orson Welles The Trial 1962", "Le procès 1962"],
    "teorema":                                ["Teorema Pasolini 1968"],
    "ivan the terrible, part i":             ["Ivan Groznyy", "Ivan the Terrible Eisenstein"],
    "ivan's childhood":                       ["Ivanovo detstvo", "Ivan childhood Tarkovsky"],
    "the story of the last chrysanthemum":   ["Zangiku monogatari", "Mizoguchi chrysanthemum"],
    "cairo station":                          ["Bab el hadid", "Cairo Station 1958"],
    "the only son":                           ["Hitori musuko", "Ozu Only Son"],
    "goopy gyne bagha byne":                 ["Gupi Gayen Bagha Bayen", "Satyajit Ray Goopy"],
    "the music room":                         ["Jalsaghar", "Satyajit Ray music room"],
    "dona flor and her two husbands":        ["Dona Flor e Seus Dois Maridos"],
    "the given word":                         ["O Pagador de Promessas"],
    "the story of qiu ju":                   ["Qiu Ju da Guan Si", "Zhang Yimou Qiu Ju"],
    "women on the verge of a nervous breakdown": ["Mujeres al borde", "Almodovar mujeres"],
    "the castle of purity":                   ["El castillo de la pureza"],
    "four nights of a dreamer":              ["Quatre nuits rêveur", "Bresson dreamer"],
    "come drink with me":                     ["Da zui xia", "King Hu drink"],
    "dragon inn":                             ["Long men ke zhan", "King Hu dragon inn"],
    "flame of my love":                       ["Waga koi wa moenu", "Mizoguchi flame"],
    "the love of sumako the actress":        ["Joyu Sumako", "Mizoguchi sumako"],
    "there was a father":                     ["Chichi ariki", "Ozu father"],
    "the flavor of green tea over rice":     ["Ochazuke no aji", "Ozu green tea"],
    "women of the night":                     ["Yoru no onnatachi", "Mizoguchi women night"],
    "black girl":                             ["La noire de", "Sembene black girl"],
    "caravaggio":                             ["Caravaggio Derek Jarman 1986"],
    "matador":                                ["Matador Almodovar 1986"],
    "venom and eternity":                     ["Traité de bave éternité", "Isou venom"],
    "the great madcap":                       ["El gran calavera", "Bunuel calavera"],
    "the chess players":                      ["Shatranj Ke Khilari", "Satyajit Ray chess"],
    "lisa and the devil":                     ["Lisa e il diavolo", "Mario Bava lisa"],
    "rabid dogs":                             ["Cani arrabbiati", "Bava rabid dogs"],
    "the pizza triangle":                     ["Dramma della gelosia", "pizza triangle"],
    "der leone have sept cabeças":            ["Der Leone Rocha 1970"],
    "anni difficili":                         ["Anni difficili 1948"],
    "edward ii":                              ["Edward II Jarman 1991"],
    "in the year 2889":                       ["In the Year 2889 1967 film"],
    "voyage to the planet of prehistoric women": ["Voyage prehistoric women 1968"],
    "pather panchali":                        ["Pather Panchali 1955", "Satyajit Ray pather"],
    "foreign correspondent":                 ["Foreign Correspondent Hitchcock 1940"],
    "m":                                      ["M Fritz Lang 1931", "Fritz Lang M Lorre"],
    "hondo":                                  ["Hondo 1953 John Wayne"],
    "bedazzled":                              ["Bedazzled 1967 Peter Cook Dudley Moore"],
    "father of the bride":                    ["Father of the Bride 1950 Spencer Tracy"],
    "oliver twist":                           ["Oliver Twist 1948 David Lean"],
    "hellzapoppin":                           ["Hellzapoppin 1941"],
    "a double life":                          ["A Double Life 1947 Ronald Colman"],
    "arch of triumph":                        ["Arch of Triumph 1948"],
    "berlin express":                         ["Berlin Express 1948 film"],
    "blowing wild":                           ["Blowing Wild 1953"],
    "knock on wood":                          ["Knock on Wood 1954 Danny Kaye"],
    "man hunt":                               ["Man Hunt 1941 Fritz Lang"],
    "machine-gun kelly":                      ["Machine-Gun Kelly 1958 Corman"],
    "obsession":                              ["Obsession 1943 film"],
    "queen of outer space":                   ["Queen of Outer Space 1958"],
    "reign of terror":                        ["Reign of Terror 1949 film"],
    "summer of fear":                         ["Summer of Fear 1978 Wes Craven"],
    "teenage zombies":                        ["Teenage Zombies 1959 film"],
    "the addiction":                          ["The Addiction 1995 Abel Ferrara"],
    "the hound of the baskervilles":         ["Hound of the Baskervilles 1939 Rathbone"],
    "the incredible petrified world":        ["Incredible Petrified World 1959"],
    "the snows of kilimanjaro":              ["Snows of Kilimanjaro 1952"],
    "cloak and dagger":                       ["Cloak and Dagger 1946 Lang"],
    "bon voyage":                             ["Bon Voyage 1944 Hitchcock"],
    "sherlock holmes and the spider woman":  ["Spider Woman 1944 Rathbone Holmes"],
    "grizzly":                                ["Grizzly 1976 film horror"],
    "widows peak":                            ["Widows Peak 1994 film"],
    "baran":                                  ["Baran 2001 Majidi film"],
    "the river":                              ["The River 1997 Tsai film"],
    "moloch":                                 ["Moloch 1999 Sokurov film"],
}

# ---------------------------------------------------------------------------
# PIL / sips
# ---------------------------------------------------------------------------

try:
    from PIL import Image as _PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def resize_image(src, dst, max_side, quality):
    if HAS_PIL:
        with _PILImage.open(src) as im:
            im = im.convert("RGB")
            w, h = im.size
            if w > max_side:
                new_h = int(h * max_side / w)
                im = im.resize((max_side, new_h), _PILImage.LANCZOS)
            elif h > max_side:
                new_w = int(w * max_side / h)
                im = im.resize((new_w, max_side), _PILImage.LANCZOS)
            im.save(dst, "JPEG", quality=quality, optimize=True)
    else:
        import subprocess
        subprocess.run(
            ["sips", "-Z", str(max_side), "--setProperty", "format", "jpeg",
             "--setProperty", "formatOptions", str(quality),
             "--out", dst, src],
            check=True, capture_output=True,
        )


def get_dims(path):
    if HAS_PIL:
        with _PILImage.open(path) as im:
            return im.size
    import subprocess
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
                         capture_output=True, text=True).stdout
    w = h = 0
    for line in out.splitlines():
        if "pixelWidth" in line:  w = int(line.split()[-1])
        if "pixelHeight" in line: h = int(line.split()[-1])
    return w, h

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(c):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2)

def cache_fresh(entry):
    if not entry or "ts" not in entry:
        return False
    return (time.time() - entry["ts"]) / 86400 < CACHE_TTL_DAYS

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_missing():
    """Return films from classic catalog that have no poster on disk."""
    films = []
    for path in [os.path.join(DATA_DIR, "catalog.csv")]:
        if not os.path.exists(path): continue
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                slug = (row.get("slug") or "").strip()
                title = (row.get("title") or "").strip()
                year  = (row.get("year") or "").strip()
                pub   = (row.get("publish") or "yes").strip().lower()
                if not slug or not title: continue
                if pub in ("no", "false", "0"): continue
                poster = os.path.join(ASSETS_POSTERS, slug + ".jpg")
                if not os.path.isfile(poster):
                    films.append({"slug": slug, "title": title, "year": year})
    return films


def append_csv(row):
    exists = os.path.exists(POSTERS_CSV)
    with open(POSTERS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=POSTERS_CSV_COLS, extrasaction="ignore")
        if not exists: w.writeheader()
        w.writerow(row)

# ---------------------------------------------------------------------------
# Commons API
# ---------------------------------------------------------------------------

def api_get(params):
    url = COMMONS_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print("    API error: %s" % exc)
        return {}


def search_commons(query):
    data = api_get({
        "action": "query", "list": "search",
        "srsearch": query, "srnamespace": "6",
        "srlimit": "5", "format": "json",
    })
    return data.get("query", {}).get("search", [])


def file_info(filename):
    bare = filename.replace("File:", "").replace("file:", "")
    data = api_get({
        "action": "query", "titles": "File:" + bare,
        "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiurlwidth": "1000", "format": "json",
    })
    for page in data.get("query", {}).get("pages", {}).values():
        ii = (page.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        author_raw = meta.get("Artist", {}).get("value", "")
        author = re.sub(r"<[^>]+>", "", author_raw).strip()
        return {
            "url": ii.get("url", ""),
            "thumb_url": ii.get("thumburl", ""),
            "descurl": ii.get("descriptionurl", ""),
            "license": lic,
            "author": author,
        }
    return None

# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

# Extensions that are never film posters
_BAD_EXTS = {".pdf", ".webm", ".ogv", ".djvu", ".ogg", ".wav", ".mp3",
             ".mp4", ".avi", ".mov", ".flac", ".djv", ".epub"}

def _file_ext(filename):
    return os.path.splitext(filename.lower())[1]

def is_image_file(filename):
    return _file_ext(filename) in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff"}

def _norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()

def title_in_filename(title, filename):
    """All significant title words must appear in the filename itself."""
    tn = _norm(title)
    fn = _norm(filename.lower())
    words = [w for w in tn.split() if len(w) > 2]
    return bool(words) and all(w in fn for w in words)

def year_in_filename(year, filename):
    if not year:
        return False
    return year in filename.lower()

def poster_signal(filename):
    """Filename contains 'poster', 'film', or 'movie'."""
    fn = filename.lower()
    return any(w in fn for w in ("poster", "film", "movie"))

def confidence(title, year, filename, snippet, pre1970=False):
    # Hard reject: non-image formats are never posters
    if not is_image_file(filename):
        return "low"

    # Title must be in the filename itself (not just the search snippet)
    if not title_in_filename(title, filename):
        return "low"

    # Year in filename + poster/film signal = high confidence
    if year_in_filename(year, filename) and poster_signal(filename):
        return "high"

    # Year in filename alone = high (pre-1970 public domain files often skip "poster")
    if year_in_filename(year, filename):
        return "high"

    # Pre-1970 + title match + poster signal in filename = high
    if pre1970 and poster_signal(filename):
        return "high"

    return "low"  # title-only match without year is too risky

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        with open(dest, "wb") as f:
            f.write(resp.read())

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    films = load_missing()
    if not films:
        print("No missing posters — done.")
        return

    print("Deep-searching %d films on Wikimedia Commons…" % len(films))
    os.makedirs(ASSETS_POSTERS, exist_ok=True)
    cache = load_cache()
    stats = {"found": 0, "skipped": 0, "error": 0}

    for film in films:
        slug  = film["slug"]
        title = film["title"]
        year  = film["year"]
        pre1970 = year.isdigit() and int(year) < 1970

        title_key = _norm(title)
        alt_titles = ORIGINAL_TITLES.get(title_key, [])
        # also try key without articles
        bare = re.sub(r"^(the|a|an|le|la|les|il|i|un|una|der|die|das)\s+", "",
                      title_key).strip()

        # Build ordered query list (most specific first)
        queries = []
        if year:
            queries.append("%s %s film poster" % (title, year))
        queries.append("%s film poster" % title)
        if year:
            queries.append("%s %s" % (title, year))
        for alt in alt_titles:
            if year:
                queries.append("%s %s" % (alt, year))
            queries.append(alt)
        if bare and bare != title_key:
            if year:
                queries.append("%s %s film" % (bare, year))
            queries.append("%s film poster" % bare)

        best_hit = None
        best_conf = "low"

        for query in queries:
            ck = "deep|" + query.lower()
            cached = cache.get(ck)
            if cache_fresh(cached):
                results = cached.get("results", [])
            else:
                time.sleep(1)
                results = search_commons(query)
                cache[ck] = {"ts": time.time(), "results": results}
                save_cache(cache)

            for hit in results:
                fn  = hit.get("title", "")
                snip = hit.get("snippet", "")
                conf = confidence(title, year, fn, snip, pre1970=pre1970)
                if conf == "high":
                    best_hit = hit
                    best_conf = "high"
                    break

            if best_conf == "high":
                break  # don't try more queries

        if best_hit is None or best_conf != "high":
            print("  SKIP  %s (%s)" % (title, year))
            stats["skipped"] += 1
            continue

        # Get file info
        fi_ck = "fi:" + best_hit["title"]
        fi_cached = cache.get(fi_ck)
        if cache_fresh(fi_cached):
            fi = fi_cached.get("info")
        else:
            time.sleep(1)
            fi = file_info(best_hit["title"])
            cache[fi_ck] = {"ts": time.time(), "info": fi}
            save_cache(cache)

        if not fi or not fi.get("url"):
            print("  ERR   %s — no file info" % title)
            stats["error"] += 1
            continue

        img_url = fi["url"]
        tmp = os.path.join("/tmp", slug + "_src.jpg")
        try:
            print("  [%s] %s — %s" % (best_conf.upper(), title, best_hit["title"]))
            download(img_url, tmp)
            w, h = get_dims(tmp)
            dst      = os.path.join(ASSETS_POSTERS, slug + ".jpg")
            dst_480  = os.path.join(ASSETS_POSTERS, slug + "-480.jpg")
            resize_image(tmp, dst,     1000, 88)
            resize_image(tmp, dst_480,  480, 82)
            os.remove(tmp)
            append_csv({
                "slug": slug,
                "original_filename": best_hit["title"],
                "imported_date": time.strftime("%Y-%m-%d"),
                "width": w, "height": h, "low_res": "yes" if w < 600 else "",
                "license": fi.get("license", ""),
                "author": fi.get("author", ""),
                "source_url": fi.get("descurl", ""),
            })
            stats["found"] += 1
        except Exception as exc:
            print("    download error: %s" % exc)
            stats["error"] += 1

    print()
    print("Done. Found: %(found)d  Skipped: %(skipped)d  Errors: %(error)d" % stats)
    save_cache(cache)


if __name__ == "__main__":
    main()
