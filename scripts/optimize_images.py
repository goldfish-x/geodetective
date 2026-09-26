from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE_ROOT = ROOT / "public" / "images"
BACKUP_ROOT = ROOT / "assets-src" / "images-original"

MAX_EDGE = int(__import__("sys").argv[1]) if len(__import__("sys").argv) > 1 else 300
QUALITY = int(__import__("sys").argv[2]) if len(__import__("sys").argv) > 2 else 82


def main():
    from PIL import Image

    total_before = total_after = 0
    count = 0
    for mode in ("china", "world"):
        src_dir = IMAGE_ROOT / mode
        if not src_dir.is_dir():
            continue
        bak_dir = BACKUP_ROOT / mode
        bak_dir.mkdir(parents=True, exist_ok=True)
        for p in sorted(src_dir.glob("*.jpg")):
            before = p.stat().st_size
            bak = bak_dir / p.name
            if not bak.exists():
                shutil_copy2(p, bak)
            with Image.open(p) as im:
                im = im.convert("RGB")
                w, h = im.size
                side = min(w, h)
                left = (w - side) // 2
                top = (h - side) // 2
                im = im.crop((left, top, left + side, top + side))
                if side > MAX_EDGE:
                    im = im.resize((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
                im.save(p, "JPEG", quality=QUALITY, optimize=True, progressive=True)
            after = p.stat().st_size
            total_before += before
            total_after += after
            count += 1
    print("optimized %d images" % count)
    print("  before: %.1f MB" % (total_before / 1048576))
    print("  after : %.1f MB" % (total_after / 1048576))
    print("  saved : %.1f MB (%.0f%%)" % (
        (total_before - total_after) / 1048576,
        100.0 * (total_before - total_after) / max(total_before, 1)))
    print("  target: %dpx square, quality %d" % (MAX_EDGE, QUALITY))
    print("  originals backed up to %s" % BACKUP_ROOT.relative_to(ROOT))


def shutil_copy2(a, b):
    import shutil
    shutil.copy2(a, b)


if __name__ == "__main__":
    raise SystemExit(main())
