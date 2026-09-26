"""Regenerate ATTRIBUTION.md from every provenance file (name-search + geo passes).

顺带做一致性清理：provenance 里若登记名对应的 jpg 已不在磁盘上（人工复核后删除的劣质图），
就把这条记录一并删掉，保证 ATTRIBUTION.md / provenance / 磁盘三者始终吻合
（tests/test_images.py 会检查这一点）。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOURCES = [
    ("world", "scripts/world-image-provenance.json"),
    ("world", "scripts/world-image-geo-provenance.json"),
    ("china", "scripts/china-image-geo-provenance.json"),
    ("world", "scripts/world-image-alias-provenance.json"),
    ("china", "scripts/china-image-alias-provenance.json"),
]


def main():
    prov = {}
    for mode, rel in SOURCES:
        f = ROOT / rel
        if not f.exists():
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        keep = {n: r for n, r in data.items()
                if (ROOT / "public" / "images" / mode / (n + ".webp")).exists()}
        dropped = sorted(set(data) - set(keep))
        if dropped:
            f.write_text(json.dumps(keep, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")
            print("pruned %s: %d stale -> %d kept" % (rel, len(dropped), len(keep)))
        for name, rec in keep.items():
            rec = dict(rec)
            rec["mode"] = mode
            # 中国篇与世界篇存在同名地点（稻城亚丁/冈仁波齐），必须按 (mode, name) 记账
            prov[(mode, name)] = rec

    lines = [
        "# 图片素材署名 / Attribution",
        "",
        "`public/images/` 中来自 Wikimedia Commons 的地名配图，共 %d 张。" % len(prov),
        "这些图片多为 CC BY / CC BY-SA 授权，按许可证要求在此列出作者与许可证；",
        "部分为 CC0 或公有领域。每条链接均指向 Commons 文件页（含原始分辨率与完整授权信息）。",
        "",
        "| 篇目 · 游戏地名 | Commons 文件 | 作者 | 许可证 |",
        "| --- | --- | --- | --- |",
    ]
    for mode_key, name in sorted(prov, key=lambda k: (k[0], k[1])):
        r = prov[(mode_key, name)]
        title = r["title"]
        link = "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_")
        artist = (r.get("artist") or "见文件页").replace("|", "\\|")[:90] or "见文件页"
        lic = " ".join(str(r.get("license", "?")).split())
        label = "世界篇" if r["mode"] == "world" else "中国篇"
        lines.append("| %s · %s | [%s](%s) | %s | %s |" % (
            label, name, title[5:], link, artist, lic))

    lines += [
        "",
        "其余图片来自项目自备素材，不由 Wikimedia Commons 提供：其中 157 张为 AI 生成图"
        "（中国篇一二星 120 张、世界篇 37 张），29 张为 scripts/generate_illustrations.py 按地名意象绘制的插画"
        "（中国篇 28 张、世界篇 1 张），均未登记在本表中。",
        "",
        "说明：配图只在答题结束后的结算面板出现，且全部是仓库内的静态文件（`public/images/`），",
        "游戏运行时不请求任何外部图片地址；因此本署名表用于素材来源合规，而不是运行依赖。",
        "若将来出现未覆盖的地点，运行时由 `src/core/placeholder.js` 按地名确定性渲染占位图。",
        "",
    ]
    out = ROOT / "ATTRIBUTION.md"
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("attribution rows: %d -> %s" % (len(prov), out.name))


if __name__ == "__main__":
    raise SystemExit(main())
