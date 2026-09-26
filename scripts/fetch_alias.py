"""Pass 3 (final): 用「地名英文/拼音/中文别名」在 Wikimedia Commons 精确检索，补齐 3~5 星配图。

顺序: 别名1 检索 -> 坐标邻近检索 -> 别名2 -> 别名3/中文名，每地点 <=4 次 API 调用。
硬约束: 候选必须命中「本次检索词的全部实义词」，再用 JUNK 黑名单 + VIEW/QUAL 打分，
        分数不达标就跳过（运行时保留占位图），宁缺毋滥。
可续跑: public/images/<mode>/<name>.webp 已存在即跳过。

用法: python scripts/fetch_alias.py <mode> [limit] [start]
"""
import json, math, os, re, sys, time, unicodedata, urllib.parse, urllib.request, urllib.error
from collections import Counter
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MODE = sys.argv[1] if len(sys.argv) > 1 else "china"
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 0
START = int(sys.argv[3]) if len(sys.argv) > 3 else 0
SLEEP = float(os.environ.get("GD_SLEEP", "2.4"))
DEBUG = os.environ.get("GD_DEBUG") == "1"
EDGE, THUMB_W = 300, 900
MIN_SEARCH, MIN_GEO = 30, 24
COOL = [0.0]
RADIUS = int(os.environ.get("GD_RADIUS", "25000"))
NOGEO = os.environ.get("GD_NO_GEO") == "1"   # 只走地名检索，跳过坐标邻近（易命中政府/学校/机场）
# prop=categories 与 generator 同用会被 API 静默丢弃，分类必须从 extmetadata 取
GENERIC_LOC = {"China", "PRC", "People's Republic"}
EMDA = "Categories|LicenseShortName|Artist|GPSLatitude|GPSLongitude|ImageDescription"

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "GeoDetective/1.0 (one representative photo per place)"}
DEST = ROOT / "public" / "images" / MODE
PROV = ROOT / ("scripts/%s-image-alias-provenance.json" % MODE)

NOISE_CAT = re.compile(r"(?i)^(category:)?(?:jpg files|png files|uploads? by|photos imported"
    r"|images? from|files reviewed|cc-|creative commons|self-published|photographs of"
    r"|wikipedia|flickr|panoramio|geograph|images? uploaded|videos?)")
JUNK = re.compile(r"(?i)(\bmap\b|locator|carte|\bflag\b|coat of arms|\blogo\b|diagram|chart"
    r"|\bsign\b|signage|plaque|poster|banner|brochure|\bscan\b|photocop|\bsvg\b|icon"
    r"|screenshot|book cover|\bdrawing\b|engrav|\bsketch\b|\bpainting\b|cartoon|emblem"
    r"|\bseal\b|mural|billboard|\binterior\b|lobby|platform|\bstation\b|subway|\btunnel\b"
    r"|parking|\bdoor\b|\bhotel\b|\bbank\b|\boffice\b|\bschool\b|hospital|cemetery"
    r"|\bgrave\b|\btomb\b|\bwreck\b|\bISS\d|view of earth|satellite|\bfood\b|\bmeal\b"
    r"|noodle|hotpot|restaurant|menu|\bfair\b|exhibition|conference|summit|portrait"
    r"|group of people|wedding|committee|\bcompany\b|烟草|管委会|合影|塑像|纪念碑"
    r"|\baircraft\b|\bplane\b|\btrain\b|\bship\b|\bferry\b|\bbus\b|locomotive"
    r"|draft|placeholder|nocat|postage|stamp|coin|\bsculpture\b|\bstatue\b|\blogo\b"
r"|\bairport\b|terminal|\broad\b|\brd\b|boulevard|avenue|\bave\b|\bway\b|\blane\b"
r"|highway|expressway|\buniversity\b|\bcollege\b|\bcampus\b|concert|festival|\bgala\b|performance"
r"|marathon|ceremony|graduation|competition|\bmatch\b|football|basketball|\bexpo\b|expos?|market"
r"|crowd|protest|parade|advertisement|notice|\bticket\b|\breceipt\b|\bmedal\b|\bbadge\b|\bmenu\b"
    r"|railway|railroad|\btracks?\b|\bairplane\b|\bheliport\b|hangar|tarmac|\bfleet\b"
    r"|\bwoman\b|\bman\b|\bgirl\b|\bboy\b|\bchild\b|\brooster\b|\bpoultry\b|\bvendor\b"
    r"|cruise|\byacht\b|\bboat\b|\bbarge\b|\bschooner\b|\bcanoe\b|\bpontoon|\bpedestrian"
    r"|人物|特写|船舶|航运|飞机|航空|铁路|铁轨|轨道|航班|航站楼|售票|游船|邮轮|博物馆|图书馆|学校|委员会|开发区|站|brt|小学|中学|大学|师专|医院|汽车站|火车站|高铁|机场|政府|教育局|体育场|体育馆|广告|文保碑|海事|码头|互通|标识牌|路口|大楼|会所|商务中心|度假区大门|\bmuseum\b|\bgallery\b|\blibrary\b|\bmunicipal\b|government|\binterchange\b|\bcourthouse\b|\bbureau\b|\bdam\b|\bconvention\b|\bchamber\b"
    r"|\bmonument to\b|\bmemorial to\b|\bpresident\b|\bsinger\b|\bmusician\b"
    r"|\bprofes\w*\b|\bportrait of\b|\bfarmers?\b|\bvillagers?\b|\bpower plant\b|power station|\bthermal\b|\brefinery\b|\bfactory\b|industrial|\bg\d{2}\b|direction|\btruck\b|\bvehicle\b|\baustin\b|\bcooperation\b|signing|\bopenstreetmap\b|\bwar\b|\bbattle\b|\bfuneral\b|\bsrtm\b|\blandsat\b|\bmodis\b|\baster\b|\bsentinel\b|\bDEM\b|\bmodel\b|\brender\b)")
VIEW = re.compile(r"(?i)(views? of|cityscape|skyline|panorama|aerial|overlook|\bview\b"
    r"|landscape|streetscape|view over|\bcoast\b|\bcanyon\b|\bglacier\b|waterfall"
    r"|夜景|全景|鸟瞰|远眺|风光|街景|天际线|全貌|俯瞰|景色)")
GENERIC = re.compile(r"(?i)^(category:)?(views?|panoramas?|skylines?|cityscapes?|aerial views?"
    r"|landscapes?|streetscapes?|night scener?|sights) of (.+)$")
QUAL = re.compile(r"(?i)(quality images|featured pictures|valuable images|picture of the day)")
STOP = set("""mount mountains mt national park ancient city cities town village villages island
islands lake lakes river river valley valleys falls desert great little old new san santa the
view views panorama panoramas landscape landscapes range peak peaks rock rocks cave caves ruin
ruins district province county global geopark canyon gorges gorge crater lagoons lagoon spring
springs well forest trees tree bay bays bridge bridges tower towers square gates gate fort forts
beach harbour harbor port sands dune dunes pass basin delta terraces terrace temple temples
mosque monastery palaces palace garden gardens reservoir wetland creek strait channel road trail
stone first second grand upper lower north south east west central inner outer main port site
archaeological natural scenic reserve protected area bay head land lands water green blue white
""".split())


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def sig_words(alias):
    ws = [w for w in re.split(r"[ ,\-_/'()\.]+", norm(alias)) if len(w) >= 3]
    return [w for w in ws if w not in STOP and len(w) >= 4], ws


def hit(key, text):
    return bool(re.search(r"(?<![a-z0-9\u4e00-\u9fff])%s(?![a-z0-9])" % re.escape(key), norm(text)))


def hit_phrase(p, text):
    return bool(re.search(r"(?<![a-z0-9\u4e00-\u9fff])%s(?![a-z0-9])" % re.escape(norm(p)), norm(text)))


def dist_km(a, b, c, d):
    if None in (a, b, c, d):
        return None
    r = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, (a, b, c, d))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def api(params):
    wait = COOL[0] - time.time()
    if wait > 0:
        print("     cooldown %.0fs" % wait, flush=True); time.sleep(wait)
    url = API + "?" + urllib.parse.urlencode(params)
    for i in range(5):
        try:
            j = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45).read())
            return None if "error" in j else j
        except urllib.error.HTTPError as e:
            ra = (e.headers or {}).get("Retry-After")
            w = (float(ra) + 3) if (e.code in (429, 403) and ra and str(ra).isdigit()) else 25.0 * (i + 1)
            if e.code in (429, 403):
                COOL[0] = max(COOL[0], time.time() + w + 45)
            print("     HTTP %s -> %.0fs" % (e.code, w), flush=True); time.sleep(w)
        except Exception as e:
            print("     %s -> %.0fs" % (type(e).__name__, 10.0 * (i + 1)), flush=True); time.sleep(10.0 * (i + 1))
    return None


def pages(j):
    out = []
    for pg in sorted((j or {}).get("query", {}).get("pages", {}).values(), key=lambda x: x.get("index", 99)):
        ii = (pg.get("imageinfo") or [{}])[0]
        url = ii.get("thumburl") or ii.get("url")
        if not url or "jpeg" not in (ii.get("mime") or ""):
            continue
        meta = ii.get("extmetadata", {})
        def gps(key):
            v = strip((meta.get(key, {}) or {}).get("value", "")).replace("°", "").replace("'", " ")
            try:
                return float(v.split()[0])
            except Exception:
                return None
        raw = (meta.get("Categories", {}) or {}).get("value", "") or ""
        out.append({"title": pg.get("title", ""), "url": url, "lat": gps("GPSLatitude"),
                    "lng": gps("GPSLongitude"),
                    "w": ii.get("width") or 0, "h": ii.get("height") or 0,
                    "cats": [c.strip() for c in raw.split("|") if c.strip()],
                    "lic": strip((meta.get("LicenseShortName", {}) or {}).get("value", "")) or "?",
                    "artist": strip((meta.get("Artist", {}) or {}).get("value", ""))[:160]})
    return out


def geo_cands(lat, lng):
    return pages(api({"action": "query", "format": "json", "generator": "geosearch",
        "ggscoord": "%s|%s" % (lat, lng), "ggsradius": str(RADIUS), "ggslimit": "14",
        "ggsnamespace": "6", "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        "iiextmetadatafilter": EMDA, "iiextmetadatalanguage": "en",
        "iiurlwidth": str(THUMB_W), "maxlag": "8"}))


def search_cands(q):
    return pages(api({"action": "query", "format": "json", "generator": "search",
        "gsrsearch": q, "gsrlimit": "10", "gsrnamespace": "6", "prop": "imageinfo|categories",
        "iiprop": "url|size|mime|extmetadata", "iiextmetadatafilter": EMDA,
        "iiextmetadatalanguage": "en", "iiurlwidth": str(THUMB_W), "maxlag": "8"}))


def place_tokens(cands, name):
    cnt = Counter()
    for c in cands:
        for cat in c["cats"]:
            g = GENERIC.match(cat)
            key = (g.group(3) if g else cat).replace("Category:", "").strip()
            if NOISE_CAT.match(cat) or len(key) < 2:
                continue
            cnt[key] += 1
    toks = {norm(name)}
    for key, n in cnt.most_common(5):
        if n >= max(2, len(cands) // 4):
            toks |= {p.lower() for p in re.split(r"[ ,/、\-()]+", key) if len(p) >= 2}
            toks.add(norm(key))
    return toks, cnt


def common(c, name):
    t = c["title"]
    if JUNK.search(t):
        return None
    rule = REJECT.get(MODE, {}).get(name)
    if rule:
        hay = norm(t + " " + " ".join(c["cats"]))
        for pat in rule.get("not", []):
            if re.search(pat, hay):
                if DEBUG:
                    print("      dbg veto       %s" % c["title"][:56], flush=True)
                return None
        for pat in rule.get("must", []):
            if not re.search(pat, hay):
                if DEBUG:
                    print("      dbg must-miss  %s" % c["title"][:56], flush=True)
                return None
    catstr = " ".join(c["cats"])
    s = 0
    if VIEW.search(t):
        s += 14
    if any(VIEW.search(x) for x in c["cats"]):
        s += 18
    if QUAL.search(catstr):
        s += 22
    if name in t:
        s += 12
    m = min(c["w"], c["h"])
    s += 10 if m >= 1200 else 6 if m >= 800 else 0 if m >= 520 else -45
    if c["w"] >= c["h"]:
        s += 5
    if len(c["cats"]) >= 3:
        s += 3
    return s, t, catstr


def rank_search(cands, name, q, pool, rec):
    need_all, _ = sig_words(q)
    full = norm(q)
    scored = []
    for c in cands:
        base = common(c, name)
        if base is None:
            if DEBUG:
                print("      dbg junk/size  %-52s" % c["title"][:52], flush=True)
            continue
        s, t, catstr = base
        hay = norm(t + " " + catstr)
        if need_all:
            if not all(hit(w, hay) for w in need_all):
                if DEBUG:
                    print("      dbg word %s  %-50s" % (need_all, c["title"][:50]), flush=True)
                continue
        elif not hit(full, hay):
            continue
        # 地理一致性: 候选必须落在该地名所属行政区，或本身就挂在含地名核心词的
        # 主题分类下（如 Category:Views of Yading）。两者都不满足 => 判为同名异地，丢弃。
        cat_hay = norm(catstr)
        reg = REGION.get(name) or []
        if MODE == "china":
            # 中国篇里 "China" 到处都有，等于没过滤 —— 必须靠省/市名把关
            reg = [r for r in reg if r not in GENERIC_LOC]
        ok_geo = any(hit_phrase(rg, cat_hay) for rg in reg) or any(hit_phrase(rg, t) for rg in reg)
        ok_cat = (all(hit(w, cat_hay) for w in need_all) if need_all else hit(full, cat_hay))
        if not (ok_geo or ok_cat):
            if DEBUG:
                print("      dbg region     %-50s | %s" % (c["title"][:50], catstr[:70]), flush=True)
            continue
        d = dist_km(c["lat"], c["lng"], rec["lat"], rec["lng"])
        if d is not None and d > 400:
            if DEBUG:
                print("      dbg far %.0fkm   %s" % (d, c["title"][:50]), flush=True)
            continue
        s += 12
        if hit(full, t):
            s += 10
        elif hit(full, catstr):
            s += 6
        for other in pool:
            if other == q:
                continue
            ow, _ = sig_words(other)
            if ow and all(hit(w, hay) for w in ow):
                s += 6
                break
        scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    return scored


def rank_geo(cands, name, pool, geo_tokens):
    scored = []
    for c in cands:
        base = common(c, name)
        if base is None:
            continue
        s, t, catstr = base
        hay = norm(t + " " + catstr)
        ok = any(hit(k, hay) for k in geo_tokens if k)
        if not ok:
            for a in pool:
                aw, _ = sig_words(a)
                if aw and all(hit(w, hay) for w in aw):
                    ok = True
                    s += 10
                    break
        if not ok:
            continue
        s += 10
        scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    return scored


def save(url, dest):
    body = None
    for _ in range(3):
        try:
            body = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
            break
        except Exception:
            time.sleep(5)
    if not body:
        return None
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(body)
    try:
        with Image.open(tmp) as im:
            im = im.convert("RGB")
            w, h = im.size
            if min(w, h) < 300:
                return None
            side = min(w, h)
            im = im.crop(((w - side) // 2, (h - side) // 2, (w - side) // 2 + side,
                          (h - side) // 2 + side)).resize((EDGE, EDGE), Image.LANCZOS)
        for q in (80, 72, 64):        # WebP：比 JPEG 再省约 25%，卡片只有 100 CSS px
            im.save(dest, "WEBP", quality=q, method=6)
            if dest.stat().st_size <= 78 * 1024:
                break
        return dest.stat().st_size
    except Exception:
        return None
    finally:
        tmp.unlink(missing_ok=True)


REJ_PATH = ROOT / "scripts/alias-reject.json"
REJECT = json.loads(REJ_PATH.read_text(encoding="utf-8")) if REJ_PATH.exists() else {}
ALIAS = json.loads((ROOT / "scripts/place-aliases.json").read_text(encoding="utf-8"))
REGION = json.loads((ROOT / "scripts/place-region.json").read_text(encoding="utf-8"))
BANK = json.loads((ROOT / ("src/data/%s.json" % MODE)).read_text(encoding="utf-8"))
todo = [{"name": it["name"], "lat": it["lat"], "lng": it["lng"], "diff": it["difficulty"],
         "bucket": k} for k in ("cities", "scenics") for it in BANK[k]
        if it["difficulty"] >= 3 and not (DEST / (it["name"] + ".webp")).exists()]
only = [x for x in os.environ.get("GD_ONLY", "").split(",") if x.strip()]
if only:
    todo = [r for r in todo if r["name"] in only]
todo.sort(key=lambda r: r["diff"])
todo = todo[START:][:LIMIT or None]
prov = json.loads(PROV.read_text(encoding="utf-8")) if PROV.exists() else {}
used = set()
for rel in ("scripts/world-image-provenance.json", "scripts/world-image-geo-provenance.json",
            "scripts/china-image-geo-provenance.json", "scripts/world-image-alias-provenance.json",
            "scripts/china-image-alias-provenance.json"):
    f = ROOT / rel
    if f.exists():
        used |= {v["title"] for v in json.loads(f.read_text(encoding="utf-8")).values()}

done = skip = 0
failed = []
print("%s: %d places to try (used titles=%d)" % (MODE, len(todo), len(used)), flush=True)
for rec in todo:
    name = rec["name"]
    if (DEST / (name + ".webp")).exists():
        skip += 1
        continue
    pool = list(dict.fromkeys(ALIAS.get(name, []) + [name]))
    # 顺序：别名1 → 坐标邻近 → 别名2 → 中文原名（中文文件名/分类偶尔是唯一命中路径）
    first = pool[:1] + ([] if NOGEO else [None]) + pool[1:2] + (
        [name] if name not in pool[:2] else [])
    # Commons 的 "Views of X" 分类命名约定：直搜地名命不中时，用视图分类词兜底
    if pool[0] != name:
        first = first + ["Views of %s" % pool[0]]
    seq = list(dict.fromkeys(first))
    picked = gtoks = ranked = None
    thr = MIN_SEARCH
    for q in seq:
        if q is None:
            cands = [c for c in geo_cands(rec["lat"], rec["lng"]) if c["title"] not in used]
            gtoks, _cnt = place_tokens(cands, name)
            ranked = rank_geo(cands, name, pool, gtoks)
            thr, src = MIN_GEO, "geo"
        else:
            cands = [c for c in search_cands(q) if c["title"] not in used]
            ranked = rank_search(cands, name, q, pool, rec)
            thr, src = MIN_SEARCH, q[:18]
        if ranked and ranked[0][0] >= thr:
            picked = ranked[:4]
            break
        time.sleep(SLEEP)
    if not picked:
        failed.append(name)
        print("[--] %-12s d%d best=%s" % (name, rec["diff"], str(ranked[0][0]) if ranked else "-"), flush=True)
        time.sleep(SLEEP)
        continue
    got = None
    for sc, best in picked:
        kb = save(best["url"], DEST / (name + ".webp"))
        if kb:
            got = (sc, best, kb)
            break
        time.sleep(1.0)
    if not got:
        failed.append(name)
        print("[--] %-12s save-failed (%d cand)" % (name, len(picked)), flush=True)
        time.sleep(SLEEP)
        continue
    sc, best, kb = got
    used.add(best["title"])
    prov[name] = {"title": best["title"], "license": best["lic"], "artist": best["artist"],
                  "score": sc, "via": src, "orig": "%dx%d" % (best["w"], best["h"]),
                  "cats": best["cats"][:12]}
    if done % 20 == 0:
        PROV.write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("[OK] %-12s d%d sc=%-3d %4dkB %-18s %s" % (name, rec["diff"], sc, kb // 1024, src, best["title"][:46]), flush=True)
    done += 1
    time.sleep(SLEEP)

PROV.write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print("\n%s done=%d skip=%d kept-placeholder=%d" % (MODE, done, skip, len(failed)))
if failed:
    print("kept:", "、".join(failed))
