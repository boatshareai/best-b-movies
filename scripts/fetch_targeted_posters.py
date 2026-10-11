#!/usr/bin/env python3
"""
fetch_targeted_posters.py — direct-lookup for films whose Commons filenames are known.

Uses the imageinfo API rather than search, so no false-positives.
Run from the repo root:
    python3 -I scripts/fetch_targeted_posters.py
"""

import csv
import json
import os
import re
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(HERE, "data")
ASSETS_POSTERS = os.path.join(HERE, "assets", "posters")
POSTERS_CSV = os.path.join(DATA_DIR, "posters.csv")

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = (
    "VelvetOctopusFilms/1.0 (velvetoctopusfilms.com; "
    "licensing@velvetoctopusfilms.com) film-catalog-tool"
)
POSTERS_CSV_COLS = ["slug", "original_filename", "imported_date", "width", "height",
                    "low_res", "license", "author", "source_url"]

# ---------------------------------------------------------------------------
# slug → ordered list of candidate Commons filenames to try (first hit wins)
# ---------------------------------------------------------------------------

TARGETS = {
    # ── Horror / Cult ────────────────────────────────────────────────────────
    "m-1931":                   ["M 1931 film poster.jpg",
                                 "Fritz Lang M 1931 poster.jpg",
                                 "M (1931) poster.jpg",
                                 "M-Plakat-1931.jpg"],
    "hellzapoppin-1941":        ["Hellzapoppin' (1941 film poster).jpg",
                                 "Hellzapoppin poster 1941.jpg",
                                 "Hellzapoppin (1941).jpg"],
    "lisa-and-the-devil-1973":  ["Lisa e il diavolo poster.jpg",
                                 "Lisa and the Devil (1973 film).jpg"],
    "the-10th-victim-1965":     ["The 10th Victim poster.jpg",
                                 "La decima vittima poster.jpg",
                                 "Decima vittima 1965.jpg"],
    "queen-of-blood-1966":      ["Queen of Blood (1966 film).jpg",
                                 "Queen of Blood 1966 poster.jpg"],
    "rabid-dogs-1974":          ["Cani arrabbiati 1974 poster.jpg",
                                 "Rabid Dogs 1974 poster.jpg"],

    # ── Hitchcock / Noir ─────────────────────────────────────────────────────
    "foreign-correspondent-1940": ["Foreign Correspondent 1940 poster.jpg",
                                   "Foreign Correspondent poster.jpg",
                                   "Foreign Correspondent (film).jpg"],
    "man-hunt-1941":            ["Man Hunt (1941 film) poster.jpg",
                                 "Man Hunt Fritz Lang 1941.jpg"],
    "cloak-and-dagger-1946":    ["Cloak and Dagger (1946 film) poster.jpg",
                                 "Cloak and dagger 1946 poster.jpg"],
    "a-double-life-1947":       ["A Double Life (1947 film) poster.jpg",
                                 "A Double Life 1947 poster.jpg"],
    "berlin-express-1948":      ["Berlin Express (1948 film) poster.jpg",
                                 "Berlin Express 1948 poster.jpg"],
    "reign-of-terror-1949":     ["Reign of Terror (1949 film) poster.jpg",
                                 "Black Book 1949 Mann poster.jpg"],
    "arch-of-triumph-1948":     ["Arch of Triumph (1948) poster.jpg",
                                 "Arch of Triumph 1948 film.jpg"],
    "the-stranger-1946":        ["The Stranger 1946 film poster.jpg",
                                 "The Stranger (1946 film).jpg",
                                 "Orson Welles The Stranger 1946.jpg"],
    "obsession-1943":           ["Obsession 1943 film poster.jpg",
                                 "Ossessione poster 1943.jpg",
                                 "Ossessione (1943).jpg"],
    "it-happened-tomorrow-1944": ["It Happened Tomorrow (1944 film).jpg",
                                  "It Happened Tomorrow poster.jpg"],

    # ── Italian / European art cinema ────────────────────────────────────────
    "bicycle-thieves-1948":     ["Bicycle Thieves (1948 film).jpg",
                                 "Ladri di biciclette poster.jpg",
                                 "Bicycle Thieves poster.jpg",
                                 "Ladri di biciclette (1948).jpg"],
    "i-vitelloni-1953":         ["I vitelloni (1953 film) poster.jpg",
                                 "I Vitelloni 1953 poster.jpg",
                                 "I vitelloni poster.jpg"],
    "teorema-1968":             ["Teorema (1968 film) poster.jpg",
                                 "Teorema Pasolini poster.jpg",
                                 "Teorema (film).jpg"],
    "the-exterminating-angel-1962": ["The Exterminating Angel poster.jpg",
                                     "El ángel exterminador poster.jpg",
                                     "El angel exterminador 1962.jpg"],
    "the-trial-1962":           ["The Trial (1962 film) poster.jpg",
                                 "Orson Welles The Trial poster.jpg",
                                 "Le procès 1962 poster.jpg"],
    "a-woman-without-love-1952": ["Una mujer sin amor poster.jpg",
                                  "A Woman Without Love 1952 poster.jpg"],
    "anni-difficili-1948":      ["Anni difficili 1948 poster.jpg",
                                 "Anni difficili film 1948.jpg"],
    "venom-and-eternity-1951":  ["Traité de bave et d'éternité poster.jpg",
                                 "Venom and Eternity 1951.jpg"],
    "four-nights-of-a-dreamer-1971": ["Four Nights of a Dreamer poster.jpg",
                                      "Quatre nuits d'un rêveur poster.jpg",
                                      "Bresson Four Nights 1971.jpg"],
    "the-castle-of-purity-1973": ["El castillo de la pureza poster.jpg",
                                  "Castle of Purity 1973 poster.jpg"],
    "the-great-madcap-1949":    ["El gran calavera poster.jpg",
                                 "El gran calavera 1949.jpg",
                                 "The Great Madcap 1949 poster.jpg"],
    "women-on-the-verge-of-a-nervous-breakdown-1988": [
                                 "Mujeres al borde de un ataque de nervios poster.jpg",
                                 "Women on the Verge poster.jpg",
                                 "Almodovar Women on the Verge 1988.jpg"],
    "the-given-word-1962":      ["O Pagador de Promessas poster.jpg",
                                 "The Given Word 1962 poster.jpg"],
    "dona-flor-and-her-two-husbands-1976": [
                                 "Dona Flor e Seus Dois Maridos poster.jpg",
                                 "Dona Flor and Her Two Husbands poster.jpg"],
    "matador-1986":             ["Matador (1986 film) poster.jpg",
                                 "Matador Almodovar poster.jpg",
                                 "Matador (Almodóvar) poster.jpg"],
    "caravaggio-1986":          ["Caravaggio (1986 film) poster.jpg",
                                 "Caravaggio Derek Jarman poster.jpg"],
    "edward-ii-1991":           ["Edward II (1991 film) poster.jpg",
                                 "Edward II Jarman poster.jpg"],
    "der-leone-have-sept-cabeças-1970": ["Der Leone Have Sept Cabeças poster.jpg",
                                         "Der Leone Rocha poster.jpg"],
    "the-pizza-triangle-1970":  ["Dramma della gelosia poster.jpg",
                                 "The Pizza Triangle poster.jpg"],

    # ── Japanese / Asian cinema ──────────────────────────────────────────────
    "ivan's-childhood-1962":    ["Ivanovo detstvo poster.jpg",
                                 "Ivan's Childhood poster.jpg",
                                 "Ivan's Childhood 1962.jpg"],
    "woman-in-the-dunes-1964":  ["Woman in the Dunes poster.jpg",
                                 "Suna no onna poster.jpg",
                                 "Woman in the Dunes (1964 film).jpg"],
    "cairo-station-1958":       ["Bab el hadid poster.jpg",
                                 "Cairo Station 1958 poster.jpg",
                                 "Cairo Station (film).jpg"],
    "come-drink-with-me-1966":  ["Come Drink with Me 1966 poster.jpg",
                                 "Da zui xia poster.jpg",
                                 "Come Drink with Me poster.jpg"],
    "dragon-inn-1967":          ["Dragon Inn (1967 film) poster.jpg",
                                 "Long men ke zhan poster.jpg",
                                 "Dragon Inn poster.jpg"],
    "the-music-room-1958":      ["Jalsaghar poster.jpg",
                                 "The Music Room 1958 poster.jpg",
                                 "The Music Room (film).jpg"],
    "pather-panchali-1955":     ["Pather Panchali poster.jpg",
                                 "Pather Panchali (1955 film).jpg"],
    "goopy-gyne-bagha-byne-1969": ["Goopy Gyne Bagha Byne poster.jpg",
                                   "Gupi Gayen Bagha Bayen poster.jpg"],
    "the-chess-players-1977":   ["Shatranj Ke Khilari poster.jpg",
                                 "The Chess Players 1977 poster.jpg",
                                 "Chess Players Satyajit Ray poster.jpg"],
    "throne-of-blood-1957":     ["Throne of Blood (1957 film) poster.jpg",
                                 "Kumonosu-jō poster.jpg",
                                 "Throne of Blood poster.jpg"],
    "flame-of-my-love-1949":    ["Waga koi wa moenu poster.jpg",
                                 "Flame of My Love Mizoguchi poster.jpg"],
    "the-love-of-sumako-the-actress-1947": ["Joyu Sumako no koi poster.jpg",
                                             "Sumako the actress poster.jpg"],
    "there-was-a-father-1942":  ["There Was a Father poster.jpg",
                                 "Chichi ariki poster.jpg",
                                 "There Was a Father (1942).jpg"],
    "the-only-son-1936":        ["The Only Son (1936 film) poster.jpg",
                                 "Hitori musuko poster.jpg"],
    "the-flavor-of-green-tea-over-rice-1952": [
                                 "Ochazuke no aji poster.jpg",
                                 "The Flavor of Green Tea Over Rice poster.jpg"],
    "the-story-of-the-last-chrysanthemum-1939": [
                                 "Zangiku monogatari poster.jpg",
                                 "Story of Last Chrysanthemum poster.jpg"],
    "women-of-the-night-1948":  ["Women of the Night poster.jpg",
                                 "Yoru no onnatachi poster.jpg"],
    "ivan-the-terrible-part-i-1944": ["Ivan the Terrible Part I poster.jpg",
                                       "Ivan Groznyy 1944 poster.jpg",
                                       "Eisenstein Ivan the Terrible poster.jpg"],
    "ivan's-childhood-1962":    ["Ivan's Childhood poster.jpg",
                                 "Ivanovo detstvo 1962.jpg"],
    "baran-2001":               ["Baran (2001 film) poster.jpg",
                                 "Baran Majidi poster.jpg"],
    "the-river-1997":           ["The River (1997 film) poster.jpg",
                                 "He liu 1997 poster.jpg",
                                 "Tsai Ming-liang River poster.jpg"],
    "moloch-1999":              ["Moloch (1999 film) poster.jpg",
                                 "Moloch Sokurov 1999 poster.jpg"],
    "the-story-of-qiu-ju-1992": ["The Story of Qiu Ju poster.jpg",
                                 "Qiu Ju da Guan Si poster.jpg"],
    "dream-2008":               ["Dream (2008 film) poster.jpg",
                                 "Kim Ki-duk Dream 2008 poster.jpg"],

    # ── African / World cinema ───────────────────────────────────────────────
    "black-girl-1966":          ["La Noire de... poster.jpg",
                                 "Black Girl Sembene poster.jpg",
                                 "La Noire de film poster.jpg"],

    # ── Westerns ────────────────────────────────────────────────────────────
    "idaho-1943":               ["Idaho (1943 film) poster.jpg",
                                 "Idaho 1943 Roy Rogers poster.jpg"],
    "hands-across-the-border-1944": ["Hands Across the Border (1944 film).jpg",
                                      "Hands Across the Border 1944 poster.jpg"],
    "lone-ranger-1956":         ["The Lone Ranger (1956 film) poster.jpg",
                                 "Lone Ranger 1956 poster.jpg"],
    "hellzapoppin-1941":        ["Hellzapoppin poster.jpg",
                                 "Hellzapoppin' (film).jpg"],

    # ── Sci-fi / B-movie ─────────────────────────────────────────────────────
    "big-time-operators-1957":  ["Big Time Operators poster.jpg",
                                 "Big Time Operators 1957.jpg"],
    "the-incredible-petrified-world-1959": [
                                 "The Incredible Petrified World poster.jpg"],
    "in-the-year-2889-1967":    ["In the Year 2889 (film) poster.jpg",
                                 "In the Year 2889 1967.jpg"],
    "voyage-to-the-planet-of-prehistoric-women-1968": [
                                 "Voyage to the Planet of Prehistoric Women poster.jpg"],

    # ── Comedy / Drama ───────────────────────────────────────────────────────
    "bedazzled-1967":           ["Bedazzled (1967 film) poster.jpg",
                                 "Bedazzled 1967 poster.jpg",
                                 "Peter Cook Dudley Moore Bedazzled poster.jpg"],
    "father-of-the-bride-1950": ["Father of the Bride (1950 film) poster.jpg",
                                 "Father of the Bride 1950 poster.jpg"],
    "knock-on-wood-1954":       ["Knock on Wood (1954 film) poster.jpg",
                                 "Knock on Wood Danny Kaye poster.jpg"],
    "boeing-boeing-1965":       ["Boeing, Boeing (film) poster.jpg",
                                 "Boeing Boeing 1965 poster.jpg"],
    "widows-peak-1994":         ["Widow's Peak (1994 film) poster.jpg",
                                 "Widows Peak 1994 poster.jpg"],
    "blowing-wild-1953":        ["Blowing Wild (1953 film) poster.jpg",
                                 "Blowing Wild poster 1953.jpg"],
    "hondo-1953":               ["Hondo (1953 film) poster.jpg",
                                 "Hondo 1953 poster.jpg",
                                 "John Wayne Hondo poster.jpg"],
    "hurry-sundown-1967":       ["Hurry Sundown (1967 film) poster.jpg",
                                 "Hurry Sundown poster.jpg"],
    "no-blade-of-grass-1970":   ["No Blade of Grass (film) poster.jpg",
                                 "No Blade of Grass 1970 poster.jpg"],
    "the-snows-of-kilimanjaro-1952": ["The Snows of Kilimanjaro (1952 film) poster.jpg",
                                      "Snows of Kilimanjaro 1952 poster.jpg"],

    # ── Sherlock Holmes series ───────────────────────────────────────────────
    "sherlock-holmes-and-a-study-in-scarlet-1933": [
                                 "A Study in Scarlet (1933 film) poster.jpg",
                                 "Sherlock Holmes Study in Scarlet 1933.jpg"],
    "sherlock-holmes-and-the-pearl-of-death-1944": [
                                 "The Pearl of Death (film) poster.jpg",
                                 "Pearl of Death 1944 poster.jpg",
                                 "Sherlock Holmes Pearl of Death poster.jpg"],
    "sherlock-holmes-and-the-scarlet-claw-1944": [
                                 "The Scarlet Claw (1944 film) poster.jpg",
                                 "Scarlet Claw 1944 poster.jpg",
                                 "Sherlock Holmes Scarlet Claw poster.jpg"],
    "sherlock-holmes-and-the-spider-woman-1943": [
                                 "Spider Woman (film) poster.jpg",
                                 "Sherlock Holmes Spider Woman poster.jpg",
                                 "Spider Woman 1944 poster.jpg"],
    "sherlock-holmes-faces-death-1943": [
                                 "Sherlock Holmes Faces Death poster.jpg",
                                 "Holmes Faces Death 1943 poster.jpg"],
    "sherlock-holmes-in-washington-1943": [
                                 "Sherlock Holmes in Washington (film) poster.jpg",
                                 "Sherlock Holmes Washington 1943 poster.jpg"],
    "sherlock-holmes-pursuit-to-algiers-1945": [
                                 "Pursuit to Algiers (film) poster.jpg",
                                 "Pursuit to Algiers 1945 poster.jpg"],

    # ── Other missing ────────────────────────────────────────────────────────
    "annI-difficili-1948":      ["Anni difficili 1948 film poster.jpg"],
    "poor-little-rich-girl-1936": ["Poor Little Rich Girl (1936 film) poster.jpg",
                                   "Poor Little Rich Girl Shirley Temple poster.jpg"],
    "storm-in-a-teacup-1937":   ["Storm in a Teacup (1937 film) poster.jpg",
                                 "Storm in a Teacup poster.jpg"],
    "grizzly-1976":             ["Grizzly (film) poster.jpg",
                                 "Grizzly 1976 horror poster.jpg"],
    "summer-of-fear-1978":      ["Summer of Fear (film) poster.jpg",
                                 "Summer of Fear Wes Craven poster.jpg"],
    "the-addiction-1995":       ["The Addiction (1995 film) poster.jpg",
                                 "Abel Ferrara The Addiction poster.jpg"],
    "escape-from-sobibor-1987": ["Escape from Sobibor (film) poster.jpg",
                                 "Escape from Sobibor 1987 poster.jpg"],
    "we-dont-live-here-anymore-2004": [
                                 "We Don't Live Here Anymore poster.jpg",
                                 "We Don't Live Here Anymore (film).jpg"],
    "my-winter-journey-2003":   ["My Winter Journey (2003 film) poster.jpg"],
    "krug-vtoroy-1990":         ["Krug vtoroy poster.jpg",
                                 "Krug vtoroy 1990.jpg"],
    "glamour-1931":             ["Glamour (1931 film) poster.jpg",
                                 "Glamour 1931 poster.jpg"],
    "sing-cowboy-sing-1937":    ["Sing, Cowboy, Sing poster.jpg",
                                 "Sing Cowboy Sing 1937.jpg"],
    "it-happened-tomorrow-1944": ["It Happened Tomorrow 1944 poster.jpg"],
    "rough-riders-round-up-1939": ["Rough Riders Round Up 1939.jpg",
                                   "Rough Riders Roundup poster.jpg"],
    "el-mural-2010":            ["El mural (2010 film) poster.jpg"],
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
            if w > max_side or h > max_side:
                scale = min(max_side / w, max_side / h)
                im = im.resize((int(w * scale), int(h * scale)), _PILImage.LANCZOS)
            im.save(dst, "JPEG", quality=quality, optimize=True)
    else:
        import subprocess
        subprocess.run(
            ["sips", "-Z", str(max_side), "--setProperty", "format", "jpeg",
             "--setProperty", "formatOptions", str(quality), "--out", dst, src],
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


def get_file_info(filename):
    """Return (url, license, author, descurl) or None if not found."""
    data = api_get({
        "action": "query",
        "titles": "File:" + filename,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": "1000",
        "format": "json",
    })
    for pid, page in data.get("query", {}).get("pages", {}).items():
        if pid == "-1":
            return None  # file doesn't exist
        ii_list = page.get("imageinfo") or []
        if not ii_list:
            return None
        ii = ii_list[0]
        url = ii.get("url", "")
        if not url:
            return None
        meta   = ii.get("extmetadata", {})
        lic    = meta.get("LicenseShortName", {}).get("value", "")
        author = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
        descurl = ii.get("descriptionurl", "")
        # Skip non-image types (video, PDF, etc.)
        if url.lower().split("?")[0].endswith((".webm", ".ogv", ".pdf", ".djvu")):
            return None
        return {"url": url, "license": lic, "author": author, "descurl": descurl,
                "filename": filename}
    return None


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        with open(dest, "wb") as f:
            f.write(resp.read())


def append_csv(row):
    exists = os.path.exists(POSTERS_CSV)
    with open(POSTERS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=POSTERS_CSV_COLS, extrasaction="ignore")
        if not exists:
            w.writeheader()
        w.writerow(row)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(ASSETS_POSTERS, exist_ok=True)
    stats = {"found": 0, "skip_exists": 0, "not_found": 0, "error": 0}

    slugs_to_try = sorted(TARGETS.keys())

    for slug in slugs_to_try:
        dst = os.path.join(ASSETS_POSTERS, slug + ".jpg")
        if os.path.isfile(dst):
            print("  EXISTS %s" % slug)
            stats["skip_exists"] += 1
            continue

        candidates = TARGETS[slug]
        hit = None
        for fname in candidates:
            time.sleep(0.6)
            fi = get_file_info(fname)
            if fi:
                hit = fi
                break

        if hit is None:
            print("  MISS   %s" % slug)
            stats["not_found"] += 1
            continue

        tmp = "/tmp/%s_src.jpg" % slug
        try:
            download(hit["url"], tmp)
            w, h = get_dims(tmp)
            dst_480 = os.path.join(ASSETS_POSTERS, slug + "-480.jpg")
            resize_image(tmp, dst,     1000, 88)
            resize_image(tmp, dst_480,  480, 82)
            os.remove(tmp)
            append_csv({
                "slug": slug,
                "original_filename": hit["filename"],
                "imported_date": time.strftime("%Y-%m-%d"),
                "width": w, "height": h,
                "low_res": "yes" if w < 600 else "",
                "license": hit["license"],
                "author": hit["author"],
                "source_url": hit["descurl"],
            })
            print("  FOUND  %s — %s" % (slug, hit["filename"]))
            stats["found"] += 1
        except Exception as exc:
            print("  ERROR  %s — %s" % (slug, exc))
            stats["error"] += 1

    print()
    print("Done. Found: %(found)d  Already exists: %(skip_exists)d  "
          "Not found: %(not_found)d  Errors: %(error)d" % stats)


if __name__ == "__main__":
    main()
