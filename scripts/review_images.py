"""离线列出每张 Commons 配图的来源元数据，供人工复核（不联网）。

用法:
  python scripts/review_images.py <mode>            # 全部，按分数升序
  python scripts/review_images.py <mode> --risky    # 只列命中可疑关键词的
  python scripts/review_images.py <mode> --names 大理,洛阳

可疑词表用 (?![a-z]) 收尾，避免 "Library19" 这类数字后缀漏检。
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["scripts/%s-image-provenance.json", "scripts/%s-image-geo-provenance.json",
           "scripts/%s-image-alias-provenance.json"]
RISK = re.compile(r"(?i)(library| Museums? |museum|gallery|station|terminal|airport|aerodrome|"
    r"school|universit|college|hospital|clinic|office|government|committee|bureau|courthouse|"
    r"tower|chimney|wind farm|windmill|turbine|substation|power plant|factory|plant|"
    r"memorial|monument|statue|bust|plaque|sign|signage|stele|map|locator|flag|logo|emblem|seal|"
    r"port|harbour|harbor|ship|boat|ferry|crane|bridge|road|highway|expressway|tunnel|"
    r"railway|rail |tracks|train|bus |locomotive|aircraft|plane|jet|helicopter|"
    r"poster|advertisement|brochure|ticket|receipt|menu|cover|book|scan|copy|"
    r"ceremony|conference|summit|graduation|concert|festival|performance|match|football|"
    r"grave|tomb|cemetery|funeral|wreck|ruins of|interior|lobby|corridor|room|"
    r"人物|雕像|纪念碑|图书馆|博物馆|车站|机场|学校|医院|政府|大楼|仪式|会议|列车|飞机|船舶|码头|大桥|公路)")


def load(mode):
    prov = {}
    for rel in SOURCES:
        f = ROOT / (rel % mode)
        if not f.exists():
            continue
        for k, v in json.loads(f.read_text(encoding="utf-8")).items():
            prov[k] = v
    return prov


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "china"
    args = sys.argv[2:]
    risky_only = "--risky" in args
    want = None
    if "--names" in args:
        want = set(args[args.index("--names") + 1].split(","))
    prov = load(mode)
    have = {p.stem for p in (ROOT / "public/images" / mode).glob("*.jpg")}
    rows = []
    for name, rec in prov.items():
        if name not in have:
            continue
        if want and name not in want:
            continue
        title = rec.get("title", "")
        cats = " | ".join(rec.get("cats") or [])
        hay = title + " " + cats
        hits = sorted({m.group(0).strip().lower() for m in RISK.finditer(hay)})
        if risky_only and not hits:
            continue
        rows.append((rec.get("score", -1), name, rec.get("via", "?"), title, cats, hits,
                     rec.get("orig", ""), rec.get("license", "?")))
    rows.sort()
    print("%s: %d 条待看" % (mode, len(rows)))
    for sc, name, via, title, cats, hits, orig, lic in rows:
        print("%-3s %-12s %-18s %-8s %s" % (sc, name, via[:18], orig[:8], title[:60]))
        if hits:
            print("       ⚠ %s" % ",".join(hits[:8]))
        if cats:
            print("       %s" % cats[:130])


if __name__ == "__main__":
    main()
