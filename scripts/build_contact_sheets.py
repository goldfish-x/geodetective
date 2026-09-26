import json, re, time, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "public" / "images" / "world"
TILE = 220
COLS = 6


def font(size):
    for cand in ("msyh.ttc", "C:/Windows/Fonts/msyh.ttc", "arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue
    return ImageFont.load_default()


def build(mode, names, out_path):
    f_tile = font(20)
    f_lbl = font(20)
    rows = (len(names) + COLS - 1) // COLS
    pad_t, pad_b, gap = 30, 8, 6
    W = COLS * (TILE + gap) + gap
    H = rows * (TILE + pad_t + pad_b + gap) + gap
    sheet = Image.new("RGB", (W, H), (18, 24, 38))
    d = ImageDraw.Draw(sheet)
    miss = 0
    for i, name in enumerate(names):
        r, c = divmod(i, COLS)
        x = gap + c * (TILE + gap)
        y = gap + r * (TILE + pad_t + pad_b + gap)
        d.text((x + 4, y + 2), "%d %s" % (i + 1, name), fill=(255, 235, 150), font=f_lbl)
        p = DEST / (name + ".jpg")
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
    world = json.loads((ROOT / "src/data/world-images.json").read_text(encoding="utf-8"))
    china = json.loads((ROOT / "src/data/china-images.json").read_text(encoding="utf-8"))
    out = ROOT / "tests/_contact"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.jpg"):
        old.unlink()
    for part, i in ((world[j:j + 60], 1) for j in range(0, len(world), 60)):
        build("world", part, out / "world-%02d.jpg" % i)
    build("china", china[:60], out / "china-01.jpg")
    build("china", china[60:], out / "china-02.jpg")


if __name__ == "__main__":
    raise SystemExit(main())
