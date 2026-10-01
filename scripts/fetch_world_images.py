import json, re, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image

ROOT = Path(".")
Q = json.load(open("scripts/world-image-queries.json", encoding="utf-8"))
_fx = Path("scripts/world-image-fixes.json")
if _fx.exists():
    Q.update(json.loads(_fx.read_text(encoding="utf-8")))
todo = json.load(open("scripts/world-image-todo.json", encoding="utf-8"))
DEST = ROOT / "web" / "public" / "images" / "world"
PROV = ROOT / "scripts" / "world-image-provenance.json"
UA = {"User-Agent": "GeoDetective/1.0 (localizing game assets; one-off batch)"}
API = "https://commons.wikimedia.org/w/api.php"
THUMB_W = 600
BAD = re.compile(r"(map|locator|flag|coat of arms|logo|diagram|chart|svg|location|carte|karte|"
                 r"panorama de|sign post|wikivoyage|banner|poster|illustration|engrave|drawing|"
                 r"sketch|clipart|stamp|banknote|coin|sculpture of logo)", re.I)

prov = json.loads(PROV.read_text(encoding="utf-8")) if PROV.exists() else {}
used = {v.get("title") for v in prov.values() if v.get("title")}


def api(params):
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=25).read())
        except urllib.error.HTTPError as e:
            err = e
            wait = 2.0 * (attempt + 1)
            if e.code == 429:
                ra = e.headers.get("Retry-After")
                wait = float(ra) + 1 if ra and ra.isdigit() else 6.0 * (attempt + 1)
            print("      API %s, retry in %.0fs" % (e.code, wait))
            time.sleep(wait)
        except Exception as e:
            err = e
            time.sleep(2.0 * (attempt + 1))
    print("      API fail:", str(err)[:80])
    return None


def words(term):
    stop = {"of", "the", "and", "a", "an", "from", "en", "de", "la", "view", "views",
            "city", "skyline", "night", "sunset", "panorama", "closeup", "aerial",
            "detail", "full", "classic", "photo", "image", "steep", "red", "white"}
    return [w for w in re.findall(r"[A-Za-z\u00c0-\u017f]{3,}|[\u4e00-\u9fff]{2,}", term)
            if w.lower() not in stop]


def candidates(term):
    time.sleep(0.35)
    j = api({"action": "query", "format": "json", "generator": "search",
             "gsrsearch": "filetype:bitmap " + term, "gsrnamespace": "6",
             "gsrlimit": "10", "prop": "imageinfo",
             "iiprop": "url|size|extmetadata|mime", "iiurlwidth": str(THUMB_W)})
    if not j or "query" not in j:
        return []
    out = []
    for page in j["query"].get("pages", {}).values():
        ii = (page.get("imageinfo") or [{}])[0]
        title = page.get("title", "")
        url = ii.get("thumburl") or ii.get("url")
        mime = ii.get("mime", "")
        if not url or "jpeg" not in mime and "png" not in mime:
            continue
        meta = ii.get("extmetadata", {})
        lic = re.sub(r"<[^>]+>", "", (meta.get("LicenseShortName", {}) or {}).get("value", "")) or "?"
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist", {}) or {}).get("value", ""))
        artist = re.sub(r"\s+", " ", artist).strip()[:120]
        w, h = ii.get("width") or 0, ii.get("height") or 0
        out.append({"title": title, "url": url, "lic": lic, "artist": artist, "w": w, "h": h})
    return out


def score(c, ws, alt_words):
    t = c["title"]
    if BAD.search(t):
        return -999
    s = 0
    low = t.lower()
    hits = sum(1 for w in ws if w.lower() in low)
    s += 6 * hits
    s += 2 * sum(1 for w in alt_words if w.lower() in low)
    if min(c["w"], c["h"]) < 500:
        s -= 6
    if c["w"] >= 1200 and c["h"] >= 800:
        s += 2
    if any(k in t.lower() for k in ("jpg", "jpeg")):
        s += 1
    return s


def save(img_url, dest, size=300):
    body = None
    for _ in range(3):
        try:
            body = urllib.request.urlopen(urllib.request.Request(img_url, headers=UA), timeout=30).read()
            break
        except Exception:
            time.sleep(2)
    if not body:
        return None
    p = dest.with_suffix(".part")
    p.write_bytes(body)
    try:
        with Image.open(p) as im:
            im = im.convert("RGB")
            w, h = im.size
            side = min(w, h)
            im = im.crop(((w - side) // 2, (h - side) // 2, (w - side) // 2 + side, (h - side) // 2 + side))
            im = im.resize((size, size), Image.LANCZOS)
            im.save(dest, "WEBP", quality=80, method=6)
        p.unlink()
        return dest.stat().st_size
    except Exception as e:
        print("      decode fail", str(e)[:60])
        p.unlink(missing_ok=True)
        return None


done = skipped = failed = 0
for rec in todo:
    name = rec["name"]
    dest = DEST / (name + ".webp")
    if dest.exists():
        skipped += 1
        continue
    picked = None
    for term in Q[name]:
        ws = words(term)
        alt = []
        for t2 in Q[name]:
            if t2 != term:
                alt += words(t2)
        cands = candidates(term)
        cands = [c for c in cands if c["title"] not in used]
        cands.sort(key=lambda c: -score(c, ws, alt))
        if cands:
            top = cands[0]
            if score(top, ws, alt) > 0:
                picked = (term, top)
                break
    if not picked:
        print("[FAIL] %s  no candidate" % name)
        failed += 1
        continue
    term, c = picked
    kb = save(c["url"], dest)
    if not kb:
        print("[FAIL] %s  download failed" % name)
        failed += 1
        continue
    used.add(c["title"])
    prov[name] = {"title": c["title"], "term": term, "license": c["lic"],
                  "artist": c["artist"], "source": c["url"].split("?")[0]}
    print("[OK]   %-12s %4dKB  <- %s" % (name, kb // 1024, c["title"][:70]))
    done += 1
    time.sleep(0.8)

PROV.write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print("\nnew=%d already=%d failed=%d" % (done, skipped, failed))
