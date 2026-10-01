import json, re, time, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TILE = 220
COLS = 6


def font(size):
    for cand in ("msyh.ttc", "C:/Windows/Fonts/msyh.ttc", "arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue
    return ImageFont.load_default()


PROV = {}
for _rel in ("scripts/world-image-provenance.json", "scripts/world-image-geo-provenance.json",
             "scripts/china-image-geo-provenance.json", "scripts/world-image-alias-provenance.json",
             "scripts/china-image-alias-provenance.json"):
    _f = ROOT / _rel
    if _f.exists():
        for _n, _r in json.loads(_f.read_text(encoding="utf-8")).items():
            PROV[(_rel.split("/")[1].split("-")[0], _n)] = _r.get("title", "")[5:]


def build(mode, names, out_path):
    dest = ROOT / "web" / "public" / "images" / mode
    f_tile = font(20)
    f_lbl = font(20)
    rows = (len(names) + COLS - 1) // COLS
    pad_t, pad_b, gap = 30, 26, 6
    W = COLS * (TILE + gap) + gap
    H = rows * (TILE + pad_t + pad_b + gap) + gap
    sheet = Image.new("RGB", (W, H), (18, 24, 38))
    d = ImageDraw.Draw(sheet)
    miss = 0
    for i, name in enumerate(names):
        r, c = divmod(i, COLS)
        x = gap + c * (TILE + gap)
        y = gap + r * (TILE + pad_t + pad_b + gap)
        src = PROV.get((mode, name), "")
        d.text((x + 4, y + 2), "%d %s" % (i + 1, name), fill=(255, 235, 150), font=f_lbl)
        if src:
            d.text((x + 4, y + TILE + 8), src[:34], fill=(150, 200, 255), font=f_lbl)
        p = dest / (name + ".webp")
        box = (x, y + pad_t, x + TILE, y + pad_t + TILE)
        if p.exists():
            with Image.open(p) as im:
                im = im.convert("RGB")
                im.thumbnail((TILE, TILE), Image.LANCZOS)
                canvas = Image.new("RGB", (TILE, TILE), (10, 14, 24))
                canvas.paste(im, ((TILE - im.size[0]) // 2, (TILE - im.size[1]) // 2))
                sheet.paste(canvas, box)
        else:
            d.rectangle(box, outline=(90, 90, 110), width=2)
            d.text((box[0] + 30, box[1] + 90), "MISSING", fill=(255, 120, 120), font=f_tile)
            miss += 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, "JPEG", quality=80, optimize=True)
    print("%s: %d tiles (%d missing) %dx%d -> %s" % (
        mode, len(names), miss, W, H, out_path.relative_to(ROOT)))


def main():
    world = json.loads((ROOT / "web/src/data/world-images.json").read_text(encoding="utf-8"))
    china = json.loads((ROOT / "web/src/data/china-images.json").read_text(encoding="utf-8"))
    out = ROOT / "tests/_contact"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.jpg"):
        old.unlink()
    for mode, names in (("world", world), ("china", china)):
        for i in range(0, len(names), 60):
            build(mode, names[i:i + 60], out / ("%s-%02d.jpg" % (mode, i // 60 + 1)))


if __name__ == "__main__":
    raise SystemExit(main())
