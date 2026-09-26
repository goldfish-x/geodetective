"""把 public/images 下的地名配图从 JPEG 迁到 WebP（同尺寸 300x300，体积再降约 30%）。

原 JPEG 会先备份到 assets-src/images-original-jpg/（.gitignore 已忽略），确认无误后
本地保留即可，仓库里只留 .webp。

用法: python scripts/convert_to_webp.py [quality=80] [--dry]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE_ROOT = ROOT / "public" / "images"
BACKUP_ROOT = ROOT / "assets-src" / "images-original-jpg"
QUALITY = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 80
DRY = "--dry" in sys.argv
EDGE = 300


def main():
    from PIL import Image
    import shutil

    before = after = 0
    n = skipped = 0
    for mode in ("china", "world"):
        d = IMAGE_ROOT / mode
        if not d.is_dir():
            continue
        bak = BACKUP_ROOT / mode
        bak.mkdir(parents=True, exist_ok=True)
        for src in sorted(d.glob("*.jpg")):
            dst = src.with_suffix(".webp")
            with Image.open(src) as im:
                im = im.convert("RGB")
                if im.size != (EDGE, EDGE):
                    side = min(im.size)
                    im = im.crop(((im.size[0] - side) // 2, (im.size[1] - side) // 2,
                                  (im.size[0] + side) // 2, (im.size[1] + side) // 2))
                    im = im.resize((EDGE, EDGE), Image.LANCZOS)
                b = src.stat().st_size
                if DRY:
                    est = int(b * 0.62)
                    print("  %-14s %5dB -> ~%dB" % (src.name, b, est))
                    before += b
                    after += est
                    n += 1
                    continue
                if not (bak / src.name).exists():
                    shutil.copy2(src, bak / src.name)
                q = QUALITY
                while True:
                    im.save(dst, "WEBP", quality=q, method=6)
                    a = dst.stat().st_size
                    if a <= 80 * 1024 or q <= 40:
                        break
                    q -= 8
                if a < 3 * 1024:
                    im.save(dst, "WEBP", quality=min(95, q + 20), method=6)
                    a = dst.stat().st_size
                if a >= b:
                    dst.unlink()
                    skipped += 1
                    continue
                src.unlink()
                before += b
                after += a
                n += 1
    print("converted %d images (%d kept as jpg because webp was not smaller)" % (n, skipped))
    print("  before: %.2f MB" % (before / 1048576))
    print("  after : %.2f MB" % (after / 1048576))
    print("  saved : %.2f MB (%.0f%%)" % ((before - after) / 1048576,
                                          100.0 * (before - after) / max(before, 1)))
    print("  originals backed up to %s" % BACKUP_ROOT.relative_to(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
