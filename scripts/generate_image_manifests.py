from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
IMAGE_ROOT = ROOT / "public" / "images"
DATA_ROOT = ROOT / "src" / "data"


def main():
    for mode in ("china", "world"):
        mode_dir = IMAGE_ROOT / mode
        names = sorted(p.stem for p in mode_dir.glob("*.jpg")) if mode_dir.exists() else []
        out = DATA_ROOT / (mode + "-images.json")
        out.write_text(
            json.dumps(names, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print("%s: %d images -> %s" % (mode, len(names), out.relative_to(ROOT)))

        data = json.loads((DATA_ROOT / (mode + ".json")).read_text(encoding="utf-8"))
        entries = [item["name"] for bucket in data.values() for item in bucket]
        have = set(names)
        missing = [n for n in entries if n not in have]
        extra = [n for n in names if n not in set(entries)]
        print("   entries=%d matched=%d missing=%d unmatched_files=%d" % (
            len(entries), len(entries) - len(missing), len(missing), len(extra)))
        if extra:
            print("   files with no entry: %s" % ", ".join(extra))
        if missing:
            print("   first missing: %s" % ", ".join(missing[:10]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
