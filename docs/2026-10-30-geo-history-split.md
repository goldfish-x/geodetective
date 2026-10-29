# 地理版 / 历史版 双线拆分设计（2026-10-30）

## 1. 背景与目标

原版本把「城市 / 景点 / 历史事件」三条线揉进同一条 15 局关卡表，玩家一局里会在三种题型之间来回切换。
本次把它拆成**两条互不干扰的产品线**（历史版可视为地理版的 DLC）：

| | 地理版 geo | 历史版 history（DLC） |
|---|---|---|
| 题库桶 | `cities` + `scenics` | `history` |
| 每篇章题库量 | 200 + 200 = 400 | 240 |
| 难度层数 | 5（简单/普通/进阶/困难/地狱） | 6（初识/通晓/博览/考据/钩沉/绝学） |
| 局数 | 10（每难度 2 局，城市↔景点交替） | 12（每难度 2 局） |
| 每局题数 | 8 | 8 |
| 单题满分 | 5000（与地理版完全相同） | 5000 |
| 门槛 | 6000 → 12500 | 5000 → 9400 |
| 入口 | `index.html` → `/` | `history.html` → `/history.html` |
| 路由 | `#/game/china`、`#/game/world` | `#/history/china`、`#/history/world` |
| 皮肤 | 深夜侦探事务所（不变） | 世界篇=罗马大理石 / 中国篇=红木青砖 |
| 本机榜单键 | `china` / `world` | `china-history` / `world-history` |

计分公式、时限、距离衰减、道具与档位规则**两版完全共用**，没有任何分叉。

## 2. 唯一事实源：`shared/src/quiz.js`

关卡表由 `TRACKS` 声明式生成，前端渲染与服务端判分都从这里取，避免双端漂移：

```js
export const TRACKS = {
  geo:     { types: ['city','scenic'], levels: 5, stagesPerLevel: 2, minBase: 6000, minStep: 500, legacyStride: 3 },
  history: { types: ['history'],       levels: 6, stagesPerLevel: 2, minBase: 5000, minStep: 400 }
}
```

- `stageTable(track)` → 关卡表；`stagesOf(track)`、`levelsOf(track)`、`difficultyLabel(track, lv)` 为对外取值口。
- `buildQuiz(bank, track)` 按赛道从对应桶抽题，整轮不重复。
- 地理版的 `legacyStride: 3` 让门槛沿用合并版（15 局）里城市/景点两线的原始序号
  `6000 + 500 × (3×(level-1) + sub)`，因此**地理版手感与拆分前逐局一致**：
  `6000, 6500, 7500, 8000, 9000, 9500, 10500, 11000, 12000, 12500`。
- 历史版门槛单独试定为 `5000 + 400 × i`（12 局 → 5000…9400），
  占单局满分（40000）的 12.5% → 23.5%，比地理版略宽，因为历史事件定位比城市更难。
- `STAGES` 仍导出并指向地理版关卡表，旧引用不破。

## 3. 前端

- `web/index.html`（`data-entry="geo"`）与 `web/history.html`（`data-entry="history"`）两个 Vite 入口，
  共用 `src/main.js`；`main.js` 读 `data-entry` 决定默认首页，并按 `#/game/*` 与 `#/history/*` 分发路由。
- `renderGame(app, mode, token, track)` / `renderHome(app, track)`：多一个 `track` 参数，
  内部据此选关卡表、难度层数（星标 `★`×n + `☆`×(levels-n)）、难度名、路由与榜单键。
- `core/storage.js`：`boardKey(mode, track)`，历史版写 `china-history` / `world-history`，与地理版互不覆盖。
- `net/online-game.js`：`createOnlineGame(mode, track)`，并把 `track` 传给 `/v1/runs`；
  关卡表优先读 `cfg.tracks[track].stages`，旧服务端回落到 `cfg.stages`。

## 4. 皮肤（`web/src/styles/theme-history.css`）

- 全部材质为**内联 SVG**（`feTurbulence` 生成大理石脉络 / 木纹 / 石材，矢量矩形画青砖错缝），
  不引入任何位图，构建产物体积几乎不增。
- 材质只铺在 `body` 一层，页面容器 `background: transparent`，避免多层背景错位出现拼缝。
- 世界篇为**浅色**主题：正文改深墨色，顶栏/底栏/卡片统一换成磨光大理石板，
  道具、计时条、进度点、徽章全部跟着换色，保证浅底不会出现浅字。
- 中国篇为**深色**主题：青砖墙打底 + 红木面板（内嵌双线金边），沿用浅色正文。
- 历史版首页是中性暗色石材「档案馆」，两张篇章卡底部各有一条材质预告条（大理石 / 红木）。
- 地理版不挂 `trk-history` 类，样式完全不受影响。

## 5. 服务端

- `/v1/config` 新增 `tracks`（各赛道的 label / levels / stages），`stages` 保留为地理版以兼容旧客户端。
- `POST /v1/runs` 接受 `track`，按赛道 `buildQuiz`，并把 `track` 落库到 run。
- 榜单按赛道分库：`boardKey(mode, track)` = `china` / `world` / `china-history` / `world-history`。
  地理版沿用旧键，历史数据不丢。
- `GET /v1/boards/:mode?track=history`、`/v1/me` 的 best 同时给出两个赛道。

## 6. 数据

- 历史题库由 224 / 231 扩到**各 240**，重排为 6 档 × 40 题：
  - 旧 L1 → 新 L1，旧 L5 → 新 L6（各 40 题原样保留）；
  - 旧 L2/L3/L4 按知名度与可定位性人工挑选边界项逐档下沉，新增事件直接指定档位；
  - 降级到 3 档以上的条目同步移除 `desc.img` 生成提示词（校验规则：>2 档不得带 img）。
- 新增 25 条标志性事件（中国 16 / 世界 9），均含 100–200 字简介、坐标、区域提示与配图：
  中国：盘庚迁殷、焚书坑儒、董卓焚烧洛阳、鉴真东渡、交子诞生、北京保卫战、北伐誓师、古田会议、
  中央红军长征出发、抗美援朝出兵、大庆油田会战、十一届三中全会、香港回归、北京奥运会开幕、
  青藏铁路通车、商汤灭夏；
  世界：第一届现代奥运会、九一一事件、庞贝古城覆灭、巴拿马运河通航、以色列建国、
  瓦特改良蒸汽机、意大利王国成立、罗马共和国建立、图尔战役。

## 7. 部署与测试地址

`deploy.yml` 增加 `codex/history-dlc` 触发。一次构建产出两个入口，Pages 上即为两个地址：

- 地理版：<https://goldfish-x.github.io/geodetective/>
- 历史版：<https://goldfish-x.github.io/geodetective/history.html>

本地开发同理：<http://127.0.0.1:5173/> 与 <http://127.0.0.1:5173/history.html>。

## 8. 回归

- `shared/tests/scoring.test.js`：锁定两版关卡表（局数/类型/难度/门槛）、六档难度名、`buildQuiz` 按赛道取桶且不重复。
- `tests/test_levels.py`：题库静态校验（历史线 6 档各 ≥40）+ 地理版 10 局结构 + 历史版 12 局结构与皮肤类名 + 中止路径。
- `tests/full_game.py`：两条赛道各跑完整流程（10 局 / 12 局），校验成绩单行数与进度点数。
- `tests/test_stage_settle.py`、`tests/test_images.py`：档案条数随题库总量动态计算。
