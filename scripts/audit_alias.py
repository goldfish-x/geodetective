"""离线复核别名轮抓到的图：用与抓取时相同的规则 + 人工否决表，重新检查每条 provenance。
不调用任何网络接口，只读 scripts/*-image-alias-provenance.json 里记录的标题与分类。

用法: python scripts/audit_alias.py <mode|all> [apply]
"""
import json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
mode = sys.argv[1] if len(sys.argv) > 1 else "all"
APPLY = len(sys.argv) > 2 and sys.argv[2] == "apply"

src = (ROOT / "scripts/fetch_alias.py").read_text(encoding="utf-8")
head = src[:src.index("REJ_PATH =")]
ns = {"__file__": str(ROOT / "scripts" / "fetch_alias.py"), "__name__": "helpers",
      "sys": type(sys)("a"), "argv": ["x", mode if mode != "all" else "china"]}
ns["sys"].argv = ns["argv"]
exec(compile(head, "helpers", "exec"), ns)
norm, sig_words, hit, hit_phrase = ns["norm"], ns["sig_words"], ns["hit"], ns["hit_phrase"]
JUNK, VIEW = ns["JUNK"], ns["VIEW"]
ALIAS = json.loads((ROOT / "scripts/place-aliases.json").read_text(encoding="utf-8"))
REGION = json.loads((ROOT / "scripts/place-region.json").read_text(encoding="utf-8"))
REJECT = json.loads((ROOT / "scripts/alias-reject.json").read_text(encoding="utf-8")) if (ROOT / "scripts/alias-reject.json").exists() else {}
GENERIC_WORDS = {"China", "PRC", "People's Republic"}

for m in (["china", "world"] if mode == "all" else [mode]):
    pf = ROOT / ("scripts/%s-image-alias-provenance.json" % m)
    if not pf.exists():
        continue
    prov = json.loads(pf.read_text(encoding="utf-8"))
    bad = {}
    for name, rec in sorted(prov.items()):
        title, cats = rec["title"], rec.get("cats") or []
        hay = norm(title + " " + " ".join(cats))
        why = []
        if JUNK.search(title):
            why.append("junk-title")
        rule = REJECT.get(m, {}).get(name, {})
        for pat in rule.get("not", []):
            if re.search(pat, hay):
                why.append("manual-reject-not:%s" % pat[:20])
        for pat in rule.get("must", []):
            if not re.search(pat, hay):
                why.append("manual-reject-must:%s" % pat[:20])
        reg = [r for r in REGION.get(name, []) if r not in GENERIC_WORDS] if m == "china" else REGION.get(name, [])
        if reg and not any(hit_phrase(r, hay) for r in reg):
            why.append("region?%s" % "/".join(reg[:2]))
        need = None
        for a in ALIAS.get(name, []):
            if norm(a) and all(hit(w, hay) for w in (sig_words(a)[0] or [norm(a)])):
                need = a
                break
        if need is None:
            why.append("no-alias-in-cats")
        if why:
            bad[name] = (why, title, cats[:3])
    print("\n===== %s: %d 张别名轮图，%d 张待复核 =====" % (m, len(prov), len(bad)))
    for name, (why, title, cats) in bad.items():
        print("  %-12s %-22s %s" % (name, ",".join(why)[:22], title[:58]))
        print("      %s" % " | ".join(cats)[:100])
    if APPLY:
        for name in bad:
            f = ROOT / "public" / "images" / m / (name + ".jpg")
            if f.exists():
                f.unlink()
            prov.pop(name)
        pf.write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("  applied: removed %d" % len(bad))
