from pathlib import Path
import hashlib
import json
import os

# 地名配图资产校验：文件集 == 配图条目集，尺寸/体积/去重/署名齐全
# 不调浏览器，纯离线，可直接 python tests/test_images.py 或在 pytest 下运行

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 80 * 1024
MIN_BYTES = 3 * 1024
EDGE = 300

try:
    from PIL import Image
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False


def img_prompt_names(mode):
    desc = json.loads((ROOT / "src" / "data" / f"{mode}-desc.json").read_text(encoding="utf-8"))
    return {n for n, e in desc.items() if e.get("img")}


def on_disk(mode):
    d = ROOT / "public" / "images" / mode
    return {p.stem for p in d.glob("*.jpg")} if d.is_dir() else set()


fail = []
for mode in ("china", "world"):
    want, have = img_prompt_names(mode), on_disk(mode)
    if want != have:
        fail.append(f"{mode}: 缺图 {sorted(want - have)[:5]} / 多余 {sorted(have - want)[:5]}")
    manifest = set(json.loads((ROOT / "src" / "data" / f"{mode}-images.json").read_text(encoding="utf-8")))
    if manifest != have:
        fail.append(f"{mode}: {mode}-images.json 与磁盘不一致，请重跑 generate_image_manifests.py")
    print(f"[{mode}] 配图条目 {len(want)} · 磁盘 {len(have)} · 清单 {len(manifest)}")

    hashes = {}
    for p in sorted((ROOT / "public" / "images" / mode).glob("*.jpg")):
        b = p.read_bytes()
        h = hashlib.md5(b).hexdigest()
        if h in hashes:
            fail.append(f"{mode}: {p.name} 与 {hashes[h]} 内容完全相同")
        hashes[h] = p.name
        if not (MIN_BYTES <= len(b) <= MAX_BYTES):
            fail.append(f"{mode}: {p.name} 体积异常 {len(b)}B")
        if HAVE_PIL:
            with Image.open(p) as im:
                if im.size != (EDGE, EDGE):
                    fail.append(f"{mode}: {p.name} 尺寸 {im.size} != {(EDGE, EDGE)}")

prov_path = ROOT / "scripts" / "world-image-provenance.json"
if prov_path.exists():
    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    attr = (ROOT / "ATTRIBUTION.md").read_text(encoding="utf-8")
    for name in prov:
        if name not in attr:
            fail.append(f"署名缺失: {name}")
        if not (ROOT / "public" / "images" / "world" / f"{name}.jpg").exists():
            fail.append(f"provenance 指向不存在的图: {name}")
    print(f"[署名] Commons 来源 {len(prov)} 条已全部登记 ATTRIBUTION.md")

if fail:
    for m in fail:
        print("  ✗", m)
    raise SystemExit(1)
print("全部通过 ✅")
