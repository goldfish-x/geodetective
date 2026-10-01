import json, os, re, sys, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MODE = sys.argv[1] if len(sys.argv) > 1 else "china"
RADIUS = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else 0
DRY = os.environ.get("GD_DRY") == "1"
# GD_REPLACE=1  对已有配图的地点也重新取 CC 图（用于把网络检索图换成可署名真拍）
# GD_STAGE=DIR  结果只写进暂存目录与 <mode>-provenance.json，核验通过后再提升为正式资源
REPLACE = os.environ.get("GD_REPLACE") == "1"
STAGE = Path(os.environ["GD_STAGE"]) if os.environ.get("GD_STAGE") else None
SLEEP = float(os.environ.get("GD_SLEEP", "2.5"))
EDGE = 300

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "GeoDetective/1.0 (one representative photo per place; low rate)"}
DEST = ROOT / "public" / "images" / MODE
PROV = ROOT / ("scripts/%s-image-geo-provenance.json" % MODE)

todo = json.loads((ROOT / ("scripts/%s-image-todo.json" % MODE)).read_text(encoding="utf-8"))
if LIMIT:
    todo = todo[:LIMIT]
prov = json.loads(PROV.read_text(encoding="utf-8")) if PROV.exists() else {}
PROV_OUT = (STAGE / ("%s-provenance.json" % MODE)) if STAGE else PROV
if STAGE:
    (STAGE / MODE).mkdir(parents=True, exist_ok=True)
    if PROV_OUT.exists():
        prov.update(json.loads(PROV_OUT.read_text(encoding="utf-8")))

BAD = re.compile(r"(?i)(\bmap\b|locator|carte|karte|\bflag\b|coat of arms|\bcrest\b|\blogo\b|"
  r"diagram|\bchart\b|\bsign\b|signage|plaque|\bstamp\b|banknote|\bcoin\b|poster|banner|"
  r"brochure|\bscan\b|photocop|\bsvg\b|\bicon\b|screenshot|book cover|\bdrawing\b|engrav|"
  r"\bsketch\b|\bpainting\b|cartoon|emblem|\bseal\b|graffiti|\bmural\b|billboard|\binterior\b|"
  r"\binside\b|lobby|platform|\bstation\b|subway|\bmetro\b|tunnel|parking|notice|\bdoor\b|"
  r"street name|house number|\bhotel\b|\bbank\b|\boffice\b|\bschool\b|hospital|cemetery|"
  r"\bgrave\b|\btomb\b|\bwreck\b|\bdraft\b|\btest\b|nocat|\bpanoramio \(\d+\)\.jpg$|"
  r"ISS\d{3}|View of Earth|Lynk|\bvehicle\b|\baircraft\b|\bsatellite image\b)")

GOOD = re.compile(r"(?i)(view of|views of|panorama|skyline|cityscape|landscape|overlook|"
  r"aerial|sunset|sunrise|dusk|night view|old town|\bcity\b|\btown\b|valley|mountain|lake|"
  r"river|bay|coast|cliff|canyon|desert|glacier|waterfall|bridge|temple|palace|fortress|"
  r"castle|\bpark\b|\bsquare\b|tower|\bpeak\b|gorge|island|harbor|harbour|monastery|"
  r"夜景|全景|鸟瞰|远眺|风光|景色|街景|老城|古城|天际线|雪山|峡谷|瀑布|群岛|半岛|火山|草原|沙漠|运河|梯田)")

QUAL = re.compile(r"(?i)(quality images|featured pictures|valuable images|picture of the day)")
VIEWS = re.compile(r"(?i)^category:views? of |category:skylines|category:panoramas|category:aerial views")


def api(params):
    url = API + "?" + urllib.parse.urlencode(params)
    for i in range(4):
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=45).read())
        except urllib.error.HTTPError as e:
            w = (float(e.headers.get("Retry-After")) + 2) if (e.code == 429 and e.headers.get("Retry-After", "").isdigit()) else 15.0 * (i + 1)
            print("     HTTP %s -> %.0fs" % (e.code, w)); time.sleep(w)
        except Exception as e:
            print("     %s -> %.0fs" % (type(e).__name__, 10.0 * (i + 1))); time.sleep(10.0 * (i + 1))
    return None


def strip(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()


def fetch(lat, lng):
    """generator=geosearch is required: prop= is ignored by list=geosearch."""
    j = api({"action": "query", "format": "json", "generator": "geosearch",
             "ggscoord": "%s|%s" % (lat, lng), "ggsradius": str(RADIUS), "ggslimit": "20",
             "ggsnamespace": "6", "prop": "imageinfo|categories",
             "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "1200", "cllimit": "5"})
    # A throttled MediaWiki reply returns pages WITHOUT the requested props, which
    # looks identical to "this place has no files". Retry so we can tell them apart.
    for attempt in range(3):
        out = _parse(j)
        if out or attempt == 2:
            return out
        time.sleep(7 * (attempt + 1))
        j = api({"action": "query", "format": "json", "generator": "geosearch",
                 "ggscoord": "%s|%s" % (lat, lng), "ggsradius": str(RADIUS), "ggslimit": "20",
                 "ggsnamespace": "6", "prop": "imageinfo|categories",
                 "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "1200", "cllimit": "5"})
        if j is None:
            return []
    return out


def _parse(j):
    out = []
    if not j or "query" not in j:
        return out
    pages = j["query"].get("pages", {})
    for pg in sorted(pages.values(), key=lambda x: x.get("index", 999)):
        ii = (pg.get("imageinfo") or [{}])[0]
        url = ii.get("thumburl") or ii.get("url")
        mime = ii.get("mime") or ""
        if not url or ("jpeg" not in mime and "png" not in mime):
            continue
        cats = [c.get("*", "") if isinstance(c, dict) else str(c)
                for c in pg.get("categories", [])]
        meta = ii.get("extmetadata", {})
        out.append({"title": pg.get("title", ""), "url": url,
                    "w": ii.get("width") or 0, "h": ii.get("height") or 0, "cats": cats,
                    "dist": 0,
                    "lic": strip((meta.get("LicenseShortName", {}) or {}).get("value", "")) or "?",
                    "artist": strip((meta.get("Artist", {}) or {}).get("value", ""))[:150]})
    return out


def score(c, name):
    t = c["title"]
    if BAD.search(t):
        return -999
    catstr = " ".join(c["cats"])
    s = 0
    if VIEWS.search(catstr):
        s += 22
    if QUAL.search(catstr):
        s += 26
    if GOOD.search(t):
        s += 12
    if name in t:
        s += 16
    if any(name in x for x in c["cats"]):
        s += 12
    w, h = c["w"], c["h"]
    if min(w, h) >= 1400:
        s += 10
    elif min(w, h) >= 900:
        s += 6
    elif min(w, h) >= 600:
        s += 1
    elif min(w, h) > 0:
        s -= 30
    if w and w >= h:
        s += 5
    if len(c["cats"]) >= 3:
        s += 3
    return s


def _noop():
    pass


def save(url, dest):
    body = None
    for _ in range(3):
        try:
            body = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
            break
        except Exception:
            time.sleep(6)
    if not body:
        return None
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(body)
    try:
        with Image.open(tmp) as im:
            im = im.convert("RGB")
            w, h = im.size
            if min(w, h) < 340:
                return None
            side = min(w, h)
            im = im.crop(((w - side) // 2, (h - side) // 2, (w - side) // 2 + side,
                          (h - side) // 2 + side)).resize((EDGE, EDGE), Image.LANCZOS)
            im.save(dest, "WEBP", quality=80, method=6)
        return dest.stat().st_size
    except Exception:
        return None
    finally:
        tmp.unlink(missing_ok=True)


used = {v["title"] for v in prov.values()}
done = skip = 0
failed = []
for rec in todo:
    name = rec["name"]
    if (DEST / (name + ".webp")).exists() and not REPLACE:
        skip += 1
        continue
    cands = [c for c in fetch(rec["lat"], rec["lng"]) if c["title"] not in used]
    for c in cands:
        c["sc"] = score(c, name)
    cands.sort(key=lambda c: -c["sc"])
    if not cands or cands[0]["sc"] < 14:
        failed.append(name)
        print("[--]  %-10s best=%s n=%d" % (
            name, ("%d" % cands[0]["sc"]) if cands else "none", len(cands)))
        if cands:
            for c in cands[:3]:
                print("       %4d %-46s %s" % (c["sc"], c["title"][:46], " | ".join(c["cats"])[:90]))
        time.sleep(SLEEP)
        continue
    best = cands[0]
    out = (STAGE / MODE / (name + ".webp")) if STAGE else (DEST / (name + ".webp"))
    kb = 1 if DRY else save(best["url"], out)
    if not kb:
        failed.append(name)
        print("[--]  %-10s save rejected" % name)
        time.sleep(SLEEP)
        continue
    if not DRY:
        used.add(best["title"])
        prov[name] = {"title": best["title"], "license": best["lic"], "artist": best["artist"],
                      "score": best["sc"], "dist_m": best["dist"],
                      "orig": "%dx%d" % (best["w"], best["h"]), "cats": best["cats"][:8]}
    print("[OK]  %-10s sc=%-4d %5.1fkm %-9s %s" % (
        name, best["sc"], best["dist"] / 1000.0, "%dx%d" % (best["w"], best["h"]), best["title"][:58]))
    done += 1
    if not DRY and (done + skip) % 25 == 0:
        PROV_OUT.write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("     ..saved provenance at %d" % (done + skip))
    time.sleep(SLEEP)

if not DRY:
    PROV_OUT.write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print("\n%s: new=%d skip=%d failed=%d" % (MODE, done, skip, len(failed)))
if failed:
    print("failed:", "、".join(failed[:50]))
