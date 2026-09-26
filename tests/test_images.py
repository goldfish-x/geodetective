from pathlib import Path
import hashlib
import json

# 地名配图资产校验（离线，无需浏览器）
#   1. 一二星地点必须有图          2. 磁盘上不得出现陌生地名（孤儿图）
#   3. 清单 JSON 必须与磁盘一致    4. 统一 300x300 WebP、体积在合理区间
#   5. 全库不得有字节相同的重复图  6. 每张 Commons 图都必须已登记署名

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 80 * 1024
# WebP 比 JPEG 小得多：雾景/大平面这类低细节真拍可以压到 2KB 左右仍然正常，
# 所以下限按 WebP 重新取值（1.5KB 足以筛掉纯色/空白/半写入文件）。
MIN_BYTES = 1500
EDGE = 300

try:
    from PIL import Image
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

PROV_SOURCES = [
    ("world", "scripts/world-image-provenance.json"),
    ("world", "scripts/world-image-geo-provenance.json"),
    ("china", "scripts/china-image-geo-provenance.json"),
    ("world", "scripts/world-image-alias-provenance.json"),
    ("china", "scripts/china-image-alias-provenance.json"),
]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def img_prompt_names(mode):
    desc = load("src/data/%s-desc.json" % mode)
    return {n for n, e in desc.items() if e.get("img")}


def bank_names(mode):
    bank = load("src/data/%s.json" % mode)
    return {it["name"] for bucket in bank.values() for it in bucket}


def on_disk(mode):
    d = ROOT / "public" / "images" / mode
    return {p.stem for p in d.glob("*.webp")} if d.is_dir() else set()


fail = []
for mode in ("china", "world"):
    want, have = img_prompt_names(mode), on_disk(mode)
    if want - have:
        fail.append("%s: 一二星缺图 %s" % (mode, sorted(want - have)[:6]))
    orphan = have - bank_names(mode)
    if orphan:
        fail.append("%s: 图片名不在题库中 %s" % (mode, sorted(orphan)[:6]))
    manifest = set(load("src/data/%s-images.json" % mode))
    if manifest != have:
        fail.append("%s: %s-images.json 与磁盘不一致，请重跑 generate_image_manifests.py" % (mode, mode))
    print("[%-5s] 一二星必配图 %3d · 磁盘实有 %3d · 清单 %3d" % (mode, len(want), len(have), len(manifest)))

hashes = {}
for mode in ("china", "world"):
    for p in sorted((ROOT / "public" / "images" / mode).glob("*.webp")):
        b = p.read_bytes()
        h = hashlib.md5(b).hexdigest()
        tag = "%s/%s" % (mode, p.name)
        if h in hashes:
            fail.append("重复图片: %s == %s" % (tag, hashes[h]))
        hashes[h] = tag
        if not (MIN_BYTES <= len(b) <= MAX_BYTES):
            fail.append("%s 体积异常 %dB" % (tag, len(b)))
        if HAVE_PIL:
            with Image.open(p) as im:
                if im.size != (EDGE, EDGE):
                    fail.append("%s 尺寸 %s != %s" % (tag, im.size, (EDGE, EDGE)))

attr_path = ROOT / "ATTRIBUTION.md"
attr = attr_path.read_text(encoding="utf-8") if attr_path.exists() else ""
total_prov = 0
for mode, rel in PROV_SOURCES:
    f = ROOT / rel
    if not f.exists():
        continue
    prov = json.loads(f.read_text(encoding="utf-8"))
    total_prov += len(prov)
    for name in prov:
        if not (ROOT / "public" / "images" / mode / (name + ".webp")).exists():
            fail.append("provenance 指向不存在的图: %s/%s" % (mode, name))
        label = "世界篇" if mode == "world" else "中国篇"
        if "%s · %s" % (label, name) not in attr:
            fail.append("署名缺失: %s/%s（跑 generate_attribution.py）" % (mode, name))
print("[署名 ] Commons 来源 %d 张" % total_prov)

if fail:
    for m in fail:
        print("  ✗", m)
    raise SystemExit(1)
print("全部通过 ✅")
