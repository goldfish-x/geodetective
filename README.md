# 地理大侦探 · Geo Detective

一个纯前端地理竞猜游戏：中国 2D 地图 + 世界 3D 地球，支持本地成绩存档。

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

配图放在：

```text
public/images/china/地点名.jpg
public/images/world/地点名.jpg
```

文件名必须与题库中的 `name` 完全一致（中文原名，无需转写）。当前覆盖情况：

| 篇目 | 已配图 | 占位图 | 其中自备生成图 | 其中 Commons 真拍 | 体积 |
| --- | --- | --- | --- | --- | --- |
| 中国篇 | 272 张 / 300 | 28 | 120（一二星全部） | 152（三四五星） | 5683 KB |
| 世界篇 | 299 张 / 300 | 1 | 37（一二星的一部分） | 262 | 6603 KB |

- 配图只出现在**答题结束后的结算面板**，答题过程中不展示，因此不影响难度曲线与信息量。
- 磁盘上没有对应 jpg 的地点，由 `src/core/placeholder.js` 按地名渲染确定性占位图（同一名
  字每次生成的图案一致），不会出现破图，也不需要任何网络请求。
- 图片是 `public/` 下的静态文件，不进 bundle：`src/data/{mode}-images.json` 只是一份地名清单
  （异步 chunk），运行时按 `images/<mode>/<地名>.jpg` 懒加载单张图。

新增图片后依次运行：

```powershell
# 1. 居中裁方 + 缩到 300px（结算卡片只有 100x100 CSS px，原图 1920px 属于浪费）
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

不合格的处理方式固定是三步：删 `public/images/<mode>/<地名>.jpg`、从
`scripts/<mode>-image-*-provenance.json` 删该条、往 `alias-reject.json` 加否决正则。
`tests/test_images.py` 会校验 provenance ↔ 磁盘 ↔ ATTRIBUTION.md 三者一致，漏一步就红。

历史脚本 `scripts/fetch_world_images.py`（关键词抓世界篇）、`scripts/fetch_geo_images.py`
（坐标抓中国篇）保留备查，它们的 provenance 文件仍参与署名生成。

## 当前限制

- 成绩保存在浏览器 `localStorage`，不能跨设备同步。
- 没有后端排行榜，不能可靠比较不同玩家的成绩。
- 地名配图覆盖 中国篇 272/300、世界篇 299/300，其余地点显示确定性占位图。
- 配图全部来自仓库内静态文件，不依赖外部图片接口，离线可用。

## 署名

`public/images/` 中 414 张来自 Wikimedia Commons（CC BY / CC BY-SA / CC0 / 公有领域），
作者与许可证逐条见 [ATTRIBUTION.md](ATTRIBUTION.md)。

