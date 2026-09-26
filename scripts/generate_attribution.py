import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
prov = json.loads((ROOT / "scripts/world-image-provenance.json").read_text(encoding="utf-8"))
todo = [r["name"] for r in json.loads((ROOT / "scripts/world-image-todo.json").read_text(encoding="utf-8"))]

lines = [
    "# 图片素材署名 / Attribution",
    "",
    "`public/images/world/` 中由 Wikimedia Commons 提供的 83 张地名配图。",
    "这些图片多为 CC BY / CC BY-SA 授权，按许可证要求在此列出作者与许可证；",
    "部分为 CC0 或公有领域。每条链接均指向 Commons 文件页（含原始分辨率与完整授权信息）。",
    "",
    "| 游戏地名 | Commons 文件 | 作者 | 许可证 |",
    "| --- | --- | --- | --- |",
]
for name in todo:
    r = prov.get(name)
    if not r:
        continue
    title = r["title"]
    link = "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_")
    artist = (r["artist"] or "见文件页").replace("|", "\\|")
    lic = " ".join(r["license"].split())
    lines.append("| %s | [%s](%s) | %s | %s |" % (name, title[5:], link, artist, lic))

lines += [
    "",
    "其余配图（中国篇 120 张与世界篇已有 37 张）为项目内自制的确定性渲染图，",
    "生成逻辑见 `src/core/placeholder.js` 与 `scripts/`，不涉及第三方版权素材。",
    "",
]
out = ROOT / "ATTRIBUTION.md"
out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
print("rows:", len(todo), "->", out.relative_to(ROOT), out.stat().st_size, "bytes")
print("\n".join(lines[:9]))
