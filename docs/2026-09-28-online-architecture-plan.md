# 《地理大侦探》线上化整体规划（v0.1 草案）

> 2026-09-28 · 目标：登录账号 + 全网排行榜 + 道具经济 + 付费
> 状态：**规划稿，未动任何代码**。现有 Pages 版继续作为离线试玩与回归测试床。

---

## 0. 现状盘点（规划的出发点）

| 维度 | 现状 | 位置 |
| --- | --- | --- |
| 形态 | 纯前端 SPA：Vite + 原生 ES Modules + hash 路由，无后端 | `src/main.js` |
| 持久化 | 仅 localStorage：`gd_nickname` / `gd_leaderboard`(各模式 Top10) / `gd-muted` | `src/core/storage.js` |
| 出题 | 客户端从打包数据组卷，**题库含答案经纬度** | `src/data/china.json`、`src/data/world.json`、`src/core/quiz.js` |
| 计分 | 客户端 Haversine + 得分公式 | `src/core/scoring.js` |
| 道具 | 已实现且纯客户端：加时 +10s、线索（每局各 1 枚，局内重置） | `src/ui/game.js` |
| 资产 | 600 张 300×300 WebP 随仓库/站点下发，约 10 MB | `public/images/` |
| 部署 | GitHub Pages 静态站，Actions 自动部署 | `.github/workflows/` |
| 回归 | Playwright(Python) 套件 + `window.__gdDebug` 钩子 | `tests/` |

---

## 1. 三个必须先定死的前提

1. **答案坐标不再进浏览器包。**
   现有 Pages 版任何人打开 bundle 就能读到全部 600 个坐标；全网榜一旦上线，旧包就是公开作弊器。
   - 线上题库与 demo 题库**物理分离**：坐标只存服务端数据库；客户端只拿 `name / difficulty / hint`；
     实际坐标在**判分之后**才随结果回传用于揭晓动画。
   - 现有 Pages 版保留为离线试玩，其榜单永远只是本机榜，不与全网榜混算。
2. **计分必须服务端权威。**
   客户端只上报「我点在哪 + 用了什么道具」，距离、得分、超时判定全部由服务端计算。
   得分公式与 Haversine 抽成 `shared/` 包（或服务端单源 + 契约测试），杜绝双端漂移。
3. **付费有资质门槛（中国大陆）。**
   - 收费网络游戏需**版号**；境内托管网站需 **ICP 备案**；微信支付 / 支付宝 / 微信登录均需**企业或个体工商户主体**。
   - 路线 A（海外先行）：Stripe + Google/GitHub OAuth，无版号问题，一周级可上线收费。
   - 路线 B（国内合规）：主体 + 备案 + 版号排队，周期以月计，但才有微信生态流量。
   - 建议：P1–P3 不碰钱，先把账号、全网榜、道具跑通；P4 再按主体资质选路线。

---

## 2. 目标架构

```
浏览器 SPA（现有代码演进）
   │  HTTPS / JSON（后期可加 WebSocket 做实时榜与对战）
   ▼
API 层（BFF）：Node + Fastify（或 Cloudflare Workers）
   ├─ auth      登录 / 会话 / JWT 刷新 / 匿名升级
   ├─ game      开局 / 出题(无坐标) / 收答案判分 / 局结算 / 终局
   ├─ economy   道具库存 / 消耗 / 订单状态机 / 支付回调验签
   └─ board     全网榜读模型（赛季 / 总榜 / 好友榜预留）
   ▼
PostgreSQL（用户 / 对局 / 明细 / 订单 / 库存 / 榜单物化视图）
Redis（可选：会话黑名单、限流、实时榜 ZSET）
对象存储 + CDN（600 张配图与地球贴图迁出仓库）
支付渠道：Stripe（海外）｜微信支付 / 支付宝（国内，需主体）
```

**职责边界一句话**：浏览器负责「呈现与手感」，服务端负责「真相与钱」。

---

## 3. 数据模型（最小可用集）

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `users` | id, nickname, provider, provider_uid, created_at, cheat_flag | 一个用户可多登录方式 |
| `questions` | id, mode, name, lng, lat, difficulty, hint, img_key | 由 `src/data/*.json` 灌库；**只对服务端可见** |
| `runs` | id, user_id, mode, season, seed, started_at, finished_at, total, stage_reached, status, client_fp | 一局一条 |
| `run_answers` | run_id, ord, question_id, guess_lng, guess_lat, distance_km, points, props_used, server_ts | 全量留痕，供复核与防作弊 |
| `items` | key, name, kind, price_cents, currency | 道具与商品目录 |
| `inventories` | user_id, item_key, qty | 服务端库存，唯一真相 |
| `orders` | id, user_id, provider, provider_order_id, amount, status(created/paid/failed/refunded), paid_at | 状态机 + 幂等回调 |
| `ledger` | user_id, delta, reason, ref_order_id | 货币/道具流水，可对账 |
| `leaderboard_mv` | mode, season, user_id, best_score, best_run_id, updated_at | 物化/增量维护的读模型 |

要点：`run_answers` 不删不改，是防作弊与客诉复核的唯一依据；榜单只存「每用户每赛季每模式最佳」。

---

## 4. API 设计（v1）

```
POST /v1/auth/login            {provider, code|credential}      → {access, refresh, user}
POST /v1/auth/refresh          {refresh}                        → {access}
GET  /v1/me                                                       → 昵称/库存/货币/本赛季最佳
POST /v1/runs                  {mode}                           → {run_id, stage1, question(无坐标)}
POST /v1/runs/:id/answers      {lng, lat, props?: [key]}        → {distance_km, points, reveal{lng,lat},
                                                                   stage{score, passed}, next?|settle}
POST /v1/runs/:id/props/:key                                    → 消耗 1 枚并返回效果（加时/线索文本）
POST /v1/runs/:id/finish                                          → {total, rank_delta, board_position}
GET  /v1/boards/:mode?season=&limit=                              → 全网榜
GET  /v1/boards/:mode/me                                            → 我的名次与差距
POST /v1/orders                {item_key}                       → {order_id, pay_params}
POST /v1/pay/:provider/callback                                   → 验签 → 改单 → 发货(ledger+inventory)
```

约定：所有对局接口带 `Idempotency-Key`；答案接口服务端校验「提交间隔 ≥ 下限、单题超时以服务端时钟为准」；
未登录可玩但 `runs.user_id = null`，成绩只进本机榜，登录后一次性合并（可选）。

---

## 5. 前端改造清单（按现有文件）

| 文件 | 改动 |
| --- | --- |
| 新增 `src/net/api.js`、`src/net/session.js` | 统一 fetch 封装、token 刷新、离线降级 |
| `src/core/storage.js` | 改为**适配器**：`LocalAdapter`（现状）/ `RemoteAdapter`（API）；`getTop10/addScore` 双实现 |
| `src/core/quiz.js` | 不再本地组卷；改为消费服务端下发的题目流；门槛/局数配置改服务端下发 |
| `src/data/*.json` | 迁到 `server/seed/` 灌库；客户端包**不再含坐标**（档案文案与 `img` 提示词可留） |
| `src/ui/game.js` | 点击→上报→等服务端判分再揭晓；道具消耗走 API；删除本地 `score()` 调用 |
| `src/ui/home.js` | 荣誉榜加「本机 / 全网 / 赛季」tab；登录入口；商店入口 |
| `src/ui/map-*.js` | 基本不动：几何与贴图不含答案；reveal 坐标改由响应提供 |
| 构建 | 图片迁 CDN 后 `public/images` 只留清单；包体进一步下降 |

保留离线模式：无会话或断网时自动回落到 `LocalAdapter`，Pages 版行为不变（也是回归测试的默认路径）。

---

## 6. 全网排行榜设计

- 维度：`mode × season`（赛季=自然月或 8 周一季）× 总榜；每用户取最佳一局。
- 读模型：Postgres 部分索引 `(mode, season, best_score DESC)` 取 Top N 足够（N≤1000）；
  需要「我的名次」时用 `COUNT(*) WHERE best_score > mine` 或维护 rank 列。
- 实时感：结算响应里直接回 `board_position` 与「距上一名差几分」，无需 WebSocket 也能有反馈。
- 展示：前三名沿用现有 1st/2nd/3rd 奖牌与金银铜背景板；加「已校验」角标与赛季倒计时。
- 反灌榜：单账号每日计入榜的对局数上限 + 新号冷却期 + 异常分数进 shadow 队列（上榜但仅自己可见，复核后放出）。

---

## 7. 道具与经济

- 现状道具（加时 / 线索）**服务端化**：库存在服务端，对局内消耗写 `run_answers.props_used`，判分时校验合法性。
- 获取途径三层：每日登录赠送 → 对局/任务产出（货币）→ 充值购买（货币或直接道具包）。
- 货币单轨起步（一种代币），避免双币带来的合规与对账复杂度；流水全进 `ledger`。
- 新增道具建议（低成本高感知）：排除两个错误省份/大洲、一次「重指」、结算保护（本局门槛 -10%）。
  全部做成服务端开关位，客户端只渲染效果。

---

## 8. 付费与订单

- 订单状态机：`created → paying → paid → delivered` / `failed` / `refunded`；回调**验签 + 幂等**（provider_order_id 唯一）。
- 发货只认回调与对账任务，不认客户端回执；每日对账脚本拉渠道账单比对 `orders`。
- 商品形态建议：月卡/赛季通行证（持续收入）> 道具包（冲动消费）> 买断去广告（一次性）。
- 合规：国内收费前置条件见第 1 节；未拿版号前，国内侧只做免费+广告位预留或干脆不开放收费开关。

---

## 9. 防作弊清单（按性价比排序）

1. 坐标不下发、判分在服务端（根因，必做）。
2. 服务端时钟判超时 + 提交间隔下限（挡脚本秒答）。
3. `run_answers` 全量留痕 + Top 榜抽样人工/自动复核（答题节奏、落点分布是否像人）。
4. 设备指纹 + 限流 + 新号冷却；同 IP 多号互刷检测。
5. 分数异常检测：单局满分率、距离分布偏离人类基线 → shadow 队列。
6. 旧 Pages 包隔离：线上服换独立题库 id 空间，demo 坐标对线上无效（题库 id 加盐或换坐标微扰无意义，直接换发题序列即可）。

---

## 10. 分期路线与验收

| 期 | 内容 | 验收标准 | 预估 |
| --- | --- | --- | --- |
| P0 准备 | 选型定稿、monorepo 拆分（`web/ server/ shared/`）、CI 加服务端单测、域名/备案/主体启动 | CI 绿；server hello-world 部署成功 | 1 周 |
| ↳ 进度 | **已完成**：分支 `codex/online-p0`；monorepo 拆分、`@gd/shared` 契约测试、Fastify BFF 骨架（`/v1/health` `/v1/config`）、`ci.yml`；**待办**：server 部署目标待定（依赖选型/主体），域名与备案未启动 | | |
| P1 账号+权威对局 | auth、runs/answers/finish、storage 适配器、离线回落、mock API 测试模式 | 线上完整玩一局且 bundle 无坐标；E2E 全绿 | 2–3 周 |
| P2 全网榜 | boards API + 首页 tab + 结算名次反馈 | 两设备互见成绩；赛季切换正确 | 1 周 |
| P3 道具经济 | 库存/消耗/每日赠送/货币流水 | 断网重连不丢道具；消耗与判分一致 | 1–2 周 |
| P4 支付 | 订单状态机、回调验签、对账、商店 UI | 沙箱全链路；对账零差异 | 2–4 周（含资质） |
| P5 加固运营 | shadow 队列、实时榜、好友榜、赛季结算奖励 | 抽样复核流程跑通 | 持续 |

---

## 11. 选型三档

| 档 | 组合 | 适合 | 月成本量级 |
| --- | --- | --- | --- |
| 极简 | Cloudflare Workers + D1/KV + Stripe | 海外试水、单人维护 | < $10 |
| 均衡 | 腾讯云/阿里云 轻量 + Fastify + Postgres + CDN | 国内合规主线 | ¥100–300 |
| 省事 | Supabase（auth+PG+RLS）+ Vercel | 快速验证，但国内访问与支付受限 | $0–25 |

建议：P1 用「均衡」档的最小集（一台轻量机 + 托管 PG），Workers 作为海外边缘读榜的后续优化。

---

## 12. 运维与成本

- 图片与贴图迁对象存储 + CDN（现约 10 MB，CDN 后首屏与流量都降）。
- 备份：PG 每日快照 + `ledger/orders` 异地留存；密钥进托管 Secret。
- 监控：接口 P95、判分耗时、支付回调成功率、shadow 队列长度。
- 灰度：`online` 模式 feature flag，先 5% 流量，观察判分与榜单一致性后放量。

---

## 13. 风险登记

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 版号/备案周期不可控 | 国内收费无限期推迟 | 海外路线先行；国内先免费运营攒用户 |
| 旧 Pages 包坐标泄露 | 全网榜被刷 | 线上题库独立发题序列 + shadow 队列 + 榜单校验标 |
| 微信登录/支付需企业主体 | 个人开发者卡死 | 尽早注册个体工商户/公司；过渡用手机号验证码登录 |
| 服务端判分引入延迟感 | 手感变差 | 揭晓动画本地先播占位、结果回填；判分目标 < 80ms |
| 双端公式漂移 | 榜不公 | shared 包 + 契约测试（同一输入双端同输出） |
| **剩余 149 张扩池配图仍为网络检索图，授权未核验** | 付费上线即构成侵权风险 | 已换掉 48 张；收费前按 `scripts/<mode>-image-web-provenance.json` 逐条替换：开代理跑 `GD_REPLACE=1 GD_STAGE=_ccstage python scripts/fetch_geo_images.py <mode> 9000` 取候选，Qwen-VL 核验后再提升，或改自有拍摄 |

---

## 14. 测试策略（复用现有资产）

- 现有 Playwright 套件继续跑离线模式（Pages / dev server），零改动保底。
- 新增 `GD_API=mock`：本地起一个内存版 API（Fastify in-memory），E2E 覆盖登录→对局→上榜→商店。
- 服务端单测：判分边界（0 km / 判定线 / 超时）、订单状态机、回调幂等。
- 契约测试：`shared/scoring` 在 Node 与浏览器各跑同一组用例比对输出。
