# 地理大侦探 · Geo Detective

一个纯前端地理竞猜游戏：中国 2D 地图 + 世界 3D 地球，支持本地成绩存档。

自 `codex/history-dlc` 起拆成**两条独立产品线**（历史版可视为地理版的 DLC），
计分公式、时限、道具规则完全共用，只是关卡表、题库桶、皮肤与榜单分开
（唯一例外：历史版·世界篇的距离衰减单独收严，`decayK` 2.3 → 1.25，
避免在欧洲这类事件密集区靠蒙得分；地理版不受影响）：

| | 地理版 | 历史版（DLC） |
|---|---|---|
| 内容 | 城市 + 景点 | 历史事件发生地 |
| 局数 / 难度 | 10 局 / 5 档 | 6 局 / 6 档 |
| 每篇章题库 | 400（200+200） | 240 |
| 门槛 | 6000 → 15000（+1000/局） | 6000 → 12000（+1200/局） |
| 皮肤 | 深夜侦探事务所 | 世界篇罗马大理石 / 中国篇红木青砖 |
| 线上地址 | <https://goldfish-x.github.io/geodetective/> | <https://goldfish-x.github.io/geodetective/history.html> |
| 本地地址 | <http://127.0.0.1:5173/> | <http://127.0.0.1:5173/history.html> |

设计细节见 [`docs/2026-10-30-geo-history-split.md`](docs/2026-10-30-geo-history-split.md)。

## 本地开发

```bash
npm install
npm run dev
```

打开 <http://127.0.0.1:5173>。

## 生产构建与本地预览

```bash
npm run build
npm run preview -- --host 127.0.0.1 --port 4173
```

构建产物在 `dist/`。这是一个纯静态站点，不需要 Node 服务器运行时，只需要任意静态文件服务器。

## 分享给别人测试

### 方式一：直接挂网（推荐）

不需要发送整个项目，也不需要发送 `node_modules`。把项目推到 GitHub 后，启用 GitHub Pages 即可得到一个测试地址。

本仓库已包含 GitHub Actions 部署配置：

```text
.github/workflows/deploy.yml
```

首次使用：

1. 打开 GitHub 仓库。
2. 进入 `Settings -> Pages`。
3. `Source` 选择 `GitHub Actions`。
4. 推送 `main` 分支，或手动运行 `Deploy to GitHub Pages` workflow。

部署成功后，地址通常是：

```text
https://<用户名>.github.io/geodetective/
```

也可以使用 Vercel、Netlify、Cloudflare Pages 等静态托管服务，构建命令填：

```bash
npm run build
```

输出目录填：

```text
dist
```

### 方式二：临时局域网测试

在本机启动：

```bash
npm run dev -- --host
```

Vite 会显示局域网地址，同一 Wi-Fi / 局域网内的测试者可以访问。

### 方式三：发送静态包

如果测试者无法访问外网，只需要压缩 `dist/` 目录发送。对方用任意静态服务器打开即可，不需要源码、`node_modules` 或 Python 测试环境。

PowerShell 示例：

```powershell
npm run build
Compress-Archive -Path dist/* -DestinationPath geo-detective-dist.zip
```

接收方解压后可预览：

```bash
npx serve .
```

## 回归测试

Python Playwright 测试默认访问 <http://127.0.0.1:5173>。

```powershell
npm run dev
```

另开终端：

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe tests\full_game.py
```

如需改变端口：

```powershell
$env:GD_BASE="http://127.0.0.1:5173"
.venv\Scripts\python.exe tests\full_game.py
```

## 部署路径说明

`vite.config.js` 支持通过 `VITE_BASE` 设置资源基础路径：

- 根域名 / 自定义域名：`/`
- GitHub Pages 项目页：`/<仓库名>/`

GitHub Actions 会自动根据仓库名设置该值。

## 本地地名配图

配图放在（WebP，300×300，quality 80）：

```text
public/images/china/地点名.webp
public/images/world/地点名.webp
```

文件名必须与题库中的 `name` 完全一致（中文原名，无需转写）。当前覆盖情况：

| 篇目 | 题库条目 | 已配图 | 待补图 | 构成 |
| --- | --- | --- | --- | --- |
| 中国篇 | 640 | 640 | 0 | 城市 200 / 景点 200 / 历史 240 |
| 世界篇 | 640 | 640 | 0 | 城市 200 / 景点 200 / 历史 240 |

合计 1280 张 300×300 WebP，全部条目均有图（`tests/test_images.py` 校验磁盘 ↔ 清单 ↔ 题库三方一致）。
图片来源逐条登记在 `scripts/<篇>-image-*-provenance.json` 与 [ATTRIBUTION.md](ATTRIBUTION.md)：
Wikimedia Commons 授权图与网络检索真拍算「已登记来源」，其余为项目自备素材
（按提示词生成的意象图 + 代码插画）。待出图清单见 [`docs/历史事件待出图清单.md`](docs/历史事件待出图清单.md)（由
`scripts/history-image-recheck-prompts.json` 生成，目前已清空）；没有合格图的条目走
`src/core/placeholder.js` 的确定性占位图，`desc` 里也不保留 `img` 提示词
（维持「有 img 必有图」这条不变量）。

- 配图只出现在**答题结束后的结算面板**，答题过程中不展示，因此不影响难度曲线与信息量。
- 磁盘上没有对应 webp 的地点，由 `src/core/placeholder.js` 按地名渲染确定性占位图（同一名
  字每次生成的图案一致），不会出现破图，也不需要任何网络请求。
- 图片是 `public/` 下的静态文件，不进 bundle：`src/data/{mode}-images.json` 只是一份地名清单
  （异步 chunk，1.6 / 2.1 kB），运行时按 `images/<mode>/<地名>.webp` 懒加载单张图。

### 为什么是 WebP

`scripts/convert_to_webp.py` 是一次性迁移脚本：把 `public/images/**/*.jpg` 逐张重编码为
300×300 的 WebP（quality 80、method 6），并把原 jpg 移到 `assets-src/images-original-jpg/`
（已被 `.gitignore` 忽略）。现在重跑它会打印「没有待转换的 jpg」，属正常。
引用扩展名的地方都已同步：`src/ui/game.js`、`tests/test_images.py`、`scripts/` 下全部
清单/署名/审计/抓取脚本（抓图脚本现在直接落盘 WebP）。
注意 WebP 对雾景、大平面水面压得极狠，个别真拍只有 2.3 KB，所以 `test_images.py` 的
体积下限从 3 KB 降到 1.5 KB，这个阈值只用于剔除明显损坏的文件。

### 历史线配图与提示词资产

历史事件（每篇 240 条，六档难度）的配图取向是**事件本身的图优先**：1840 年后用当年黑白/泛黄档案老照片或历史海报，
更早的用中西方教科书与百科常见的历史油画、国画、版画、壁画、人物肖像或半身塑像；只有遗址保存完整的
才用遗址实景，纪念馆/纪念碑次选。地图、政区图、战役形势图、文字展板、复制园景、车站厂房一律不收。

三份可复用资产全部入库，清单文档由它们生成，不要手改文档：

| 文件 | 作用 |
| --- | --- |
| `scripts/history-image-queries.json` | 事件 → Commons 检索词（英文事件名 + 中文名 + 期望图型） |
| `scripts/history-image-todo.json` | 待生成清单条目（A 无图 / B 只有城市风貌照） |
| `scripts/history-image-prompts.json` | 待生成条目的生图提示词（近代=档案老照片，古代=历史画/版画/肖像） |
| `scripts/<篇>-image-user-provenance.json` | 人工搜集并复核的事件图来源登记（含用户提供图与网络检索图） |

两条硬性口径（`check_image_prompts.py` 会在 CI 里拦）：

- **中国古代没有塑像习俗**：提示词里不得出现铜像、石像、半身塑像、雕塑，人物一律用历代传世肖像画、
  工笔重彩人物像或水墨写意画像；
- **人物出生地不画幼年**：有成年传世画像/照片的直接用成年像（曾国藩像、王阳明像、忽必烈像那一类），
  不编「神童场景」。

清单文档由 `python scripts/gen_image_todo_doc.py` 生成，四档统计（A 无图 / B 仅城市风貌 /
C 遗址达标 / D 事件图达标）全部来自上面几份 JSON 与磁盘实际文件，不手写。

```powershell
python scripts\check_image_prompts.py     # 校验提示词：不得串到其他事件、长度合规、必须能对上本事件
```

> 批量生成提示词时**必须让模型回显事件名并按事件名回填**，不能按序号回填：模型偶发换行、合并或漏条，
> 序号映射会整批错位（上一版清单就出现过「巫蛊之祸拿到参合陂的提示词」）。CI 里的
> `check_image_prompts.py` 就是拦这个的。

### 29 张代码插画

三四五星里仍有 29 个地点在 Commons 上抓不到「图文对应」的真拍（如 株洲、贺兰山岩画、
冷湖黑独山、阿什哈巴德）。这些不用占位图、也不硬凑同名异地照片，而是用
`scripts/generate_illustrations.py` 按地名意象绘制旅行海报式插画：

- `scripts/illustration-scenes.json`：逐条人工指定 `{recipe, pal, sun, star, clouds, args, note}`，
  `note` 写明意象依据（例：株洲 = 湘江 + 铁路大桥 + 电力机车）。
- 17 个 recipe（喀斯特峰林/梯田/雅丹/岩画/徽派马头墙/侗族鼓楼/峡谷大拐弯…）+ 10 套配色，
  统一在 900px 上绘制再缩到 300px，最后套同一层胶片颗粒与暗角，保证成套观感一致。
- 确定性：随机种子取自地名 md5，同一地名每次重绘像素一致，因此不需要把生成参数入库。
- 插画属于自备素材，**不写入 provenance / ATTRIBUTION.md**（署名表只登记 Commons 真拍）。

```powershell
.venv\Scripts\python.exe scripts\generate_illustrations.py            # 只补缺失
.venv\Scripts\python.exe scripts\generate_illustrations.py --force     # 全部重绘
.venv\Scripts\python.exe scripts\generate_illustrations.py --only 怀化,屏山峡谷   # 局部重绘
```

新增图片后依次运行：

```powershell
# 1. 居中裁方 + 缩到 300px 并输出 WebP（结算卡片只有 100x100 CSS px，原图 1920px 属于浪费）
#    首次运行会把未压缩原图备份到 assets-src/images-original/（已被 .gitignore 忽略）
.venv\Scripts\python.exe scripts\optimize_images.py 300 82

# 2. 重新生成清单，供 game.js 判断哪些地点有本地图
.venv\Scripts\python.exe scripts\generate_image_manifests.py

# 3. 重新生成署名表
.venv\Scripts\python.exe scripts\generate_attribution.py
```

## 从 Wikimedia Commons 补齐三四五星配图

主脚本 `scripts/fetch_alias.py`，对每个缺图地点按「别名1 → 坐标邻近(25km) → 别名2 →
中文原名 → `Views of <别名1>`」的顺序检索，最多 5 次 API 调用，宁缺毋滥：

- `scripts/place-aliases.json`：地名 → 英文/拼音/别名（缺别名基本抓不到，先补这张表）
- `scripts/place-region.json`：地名 → 所属省/国，用于同名异地判定（中国篇会剔除 "China" 这类
  到处都命中的泛词）
- `scripts/alias-reject.json`：人工否决表 `{"<mode>": {"<地名>": {"not": [正则], "must": [正则]}}}`，
  用来永久拉黑「城市名命中同名街道 / 学校 / 界碑 / 龙卷风」这类误图
- 硬过滤：检索词的每个实义词都必须出现在文件名或分类里；候选自带 GPS 距答案 >400km 丢弃；
  行政区不一致丢弃；地图/标识牌/车站/机场/学校/政府/人物/船舶等 JUNK 词直接淘汰
- 打分：`Views of X` 景观分类、Quality/Featured 分类、分辨率、横构图加分，低于阈值
  （检索 30 / 邻近 24）就跳过，保留占位图
- 结果写入 `scripts/{mode}-image-alias-provenance.json`（文件名、作者、许可证、分类、分数、来源）

```powershell
# 只补缺失项（磁盘已有同名文件自动跳过）；429 限流明显，GD_SLEEP 建议 >=2.2
$env:PYTHONIOENCODING='utf-8'; $env:GD_SLEEP='2.2'
.venv\Scripts\python.exe scripts\fetch_alias.py china
.venv\Scripts\python.exe scripts\fetch_alias.py world

# 常用开关
#   GD_ONLY=地名1,地名2   只重抓指定地点
#   GD_DEBUG=1            打印每条候选被淘汰的原因
#   GD_NO_GEO=1           关闭坐标邻近轮（该轮最容易抓到政府/学校/机场）
#   GD_RADIUS=25000       邻近检索半径（米）
```

**每轮抓完必须人工复核**（自动检索无法判断构图主体），再跑：

```powershell
.venv\Scripts\python.exe scripts\review_images.py china      # 列出标题+分类+可疑词
.venv\Scripts\python.exe scripts\audit_alias.py china        # 用同一套规则复查别名轮
.venv\Scripts\python.exe scripts\audit_alias.py china apply  # 判定不合格的：删图 + 删 provenance
.venv\Scripts\python.exe scripts\generate_attribution.py     # 重建署名（顺带清理失效 provenance）
.venv\Scripts\python.exe scripts\generate_image_manifests.py # 重建清单 + 打印缺口
.venv\Scripts\python.exe tests\test_images.py               # 尺寸/体积/去重/署名一致性
.venv\Scripts\python.exe scripts\build_contact_sheets.py     # 拼版总览图，肉眼扫一遍最快
```

不合格的处理方式固定是三步：删 `public/images/<mode>/<地名>.webp`、从
`scripts/<mode>-image-*-provenance.json` 删该条、往 `alias-reject.json` 加否决正则。
`tests/test_images.py` 会校验 provenance ↔ 磁盘 ↔ ATTRIBUTION.md 三者一致，漏一步就红。

历史脚本 `scripts/fetch_world_images.py`（关键词抓世界篇）、`scripts/fetch_geo_images.py`
（坐标抓中国篇）保留备查，它们的 provenance 文件仍参与署名生成。

## 历史事件线的定档与素材规范

每篇 `history` 桶 200 条、五档各 40 条，与城市/景点同星级同屏轮换（15 局 = 三线 × 五星）。
定档只看一件事：**玩家能不能在地图上把这个点猜准**，所以难度由「事件知名度 × 发生地知名度」共同决定。

| 星级 | 取材 | 例 |
| --- | --- | --- |
| 一星 | 家喻户晓的事件，且发生地是直辖市/省会/名城 | 开国大典（北京）、赤壁之战、孔子出生（曲阜）、雅尔塔会议 |
| 二星 | 课本常见事件，发生地多为地区级城市 | 土木堡之变（张家口）、葛底斯堡战役、林则徐出生（福州） |
| 三星 | 事件有名但发生地是县城，或地点分散的长线战争 | 长平之战（高平）、马哈赞河战役（凯比尔堡） |
| 四五星 | 冷门战役、政变、边疆叛乱、二流人物出生地 | 硖石之战、王辅臣平凉叛乱、关汉卿出生（解州） |

- **著名战役发生地 + 历史名人出生地**是压低一二星难度的主要手段：战役名即地名（赤壁、垓下、
  官渡）或发生地本身是名城时才可进一星；「牧野之战→淇县」「城濮之战→鄄城」这类事件熟、
  地点生的组合一律降到二三星。
- **译名一律用中国大陆通用译名**：黑斯廷斯战役（不是哈斯丁斯）、沙隆战役、克雷西会战、
  帕维亚战役、马哈茂德二世废除近卫军、萨拉热窝事件、胡志明战役。事件名同时是图片文件名、
  coords/desc 的键，改名必须四处同步（`_rename` 那类映射表就是为此存在）。
- **同一事件只留一条**：攻占巴士底狱、开罗宣言、布拉格之春、柏林空运、马恩河战役、
  特拉法尔加海战、凡尔赛条约签署、十月革命此前都有 2-4 个异名重复条目，已合并；
  史实错误的条目（拿破仑在凡尔赛宫加冕）删除，正确写法是「拿破仑加冕 · 巴黎圣母院」。
- **坐标必须人工核定**。中文事件名里大量地名会在地理编码库里先命中美国同名地点
  （色当 / 托莱多 / 阿拉曼 / 哈丁 / 凡尔赛 / 亚历山大 / 中途岛 / 萨拉热窝），自动重定位还会
  退化成国家质心（`46.0, 2.0` 这种整数）。因此题库表里逐条写明「事件 → 今地名」，
  再用 `china-map.json` / `world-map.json` 做点在多边形反查得到 `area`，
  `hint` 由省→大区、国→大洲映射推导；地图里没有的区域（中途岛）留空 `area` 并给文字提示。
- **配图宁缺毋滥**：一律取发生地实景照片，插画/地图/拼图/多宫格/车站厂房/灾后废景全部剔除；
  抓不到就留占位图并写进 [`docs/历史事件待出图清单.md`](docs/历史事件待出图清单.md)，
  绝不用别的地点凑数。全库不允许出现字节相同的两张图（`test_images.py` 会拦）。

## 当前限制

- 演示版（`?mode=demo` / Pages 静态站）成绩只存在浏览器 `localStorage`，不能跨设备同步，
  也没有全网排行榜；在线版（`?online=1`，需部署 `server/` BFF）由服务端权威记分并提供登录与
  全网榜，坐标已从浏览器包里剥离，只有 BFF 持有。
- 题库共 600 条/篇（城市 200 + 景点 200 + 历史事件 200），15 局 × 8 题按
  城市→景点→历史、一二星→五星循环；历史事件配图仍有 15 个条目待补（见
  [`docs/历史事件待出图清单.md`](docs/历史事件待出图清单.md)），缺图时回落确定性占位图。
- 配图全部来自仓库内静态文件，不依赖外部图片接口，离线可用；1185 张共 20.9 MB，
  不进 bundle，按地名懒加载。

## 署名

`public/images/` 中已登记来源的配图共 650 条（Wikimedia Commons 授权图：CC BY / CC BY-SA / CC0 / 公有领域；另有网络检索图标注为「未核验授权」，商用前需替换为 CC 或自拍），作者与许可证逐条见 [ATTRIBUTION.md](ATTRIBUTION.md)；其余为项目自备素材（按 `desc.img` 提示词生成的意象图 + 代码插画），不属于第三方授权作品。

