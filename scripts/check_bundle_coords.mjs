// 坐标哨兵：确认在线产物不含答案坐标、demo 产物含坐标。
// 用法: node scripts/check_bundle_coords.mjs online|demo
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const kind = process.argv[2] || "online";
const coords = JSON.parse(readFileSync(HERE + "../web/src/data/china-coords.json", "utf-8"));
const sentinels = ["墨脱", "塔什库尔干", "霍林郭勒"].map(n => coords[n].slice(0, 2).join(","));
const files = readdirSync(HERE + "../web/dist/assets").filter(f => f.endsWith(".js"));
const blob = files.map(f => readFileSync(HERE + "../web/dist/assets/" + f, "utf-8")).join("\n");
const hits = sentinels.filter(s => blob.includes(s));
if (kind === "online" && hits.length) {
  console.error("x 在线产物泄漏坐标哨兵:", hits);
  process.exit(1);
}
if (kind === "demo" && hits.length !== sentinels.length) {
  console.error("x demo 产物缺少坐标哨兵:", hits);
  process.exit(1);
}
console.log(`ok 坐标哨兵校验通过（${kind}，扫描 ${files.length} 个 js chunk）`);
