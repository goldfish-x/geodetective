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

文件名必须与题库中的 `name` 完全一致。当前已就位：**china 120 张、world 120 张**，正好覆盖每篇题库里
一星与二星各 60 个地点（共 120 个带 `img` 的条目）；剩余 180 个三四星地点
运行时回退为确定性占位图。

新增图片后依次运行：

```powershell
# 1. 居中裁方 + 缩到 300px（结算卡片只有 100x100 CSS px，原图 1920px 属于浪费）
#    首次运行会把未压缩原图备份到 assets-src/images-original/（已被 .gitignore 忽略）
.venv\Scripts\python.exe scripts\optimize_images.py 300 82

# 2. 重新生成清单，供 game.js 判断哪些地点有本地图
.venv\Scripts\python.exe scripts\generate_image_manifests.py
```

## 从 Wikimedia Commons 补齐配图

`scripts/fetch_world_images.py` 按 `scripts/world-image-queries.json` 里的检索词
到 Commons 抓图，居中裁方为 300px 后写入 `public/images/world/`，并把文件名、
作者、许可证记到 `scripts/world-image-provenance.json`。

```powershell
# 只补缺失项（已存在同名文件会跳过），可用 scripts/world-image-fixes.json 覆盖检索词
.venv\Scripts\python.exe scripts\fetch_world_images.py
# 抓完必须重建署名表（CC BY / CC BY-SA 要求署名）
.venv\Scripts\python.exe scripts\generate_attribution.py
```

脚本靠 Commons 分类元数据判断图文是否对应，但仍需人工复核：自动检索会选中
构图主体不符的图（例如把 Athena Nike 神庙当成帕特农、把油画当成实景照片）。

## 当前限制

- 成绩保存在浏览器 `localStorage`，不能跨设备同步。
- 没有后端排行榜，不能可靠比较不同玩家的成绩。
- 配图全部来自仓库内静态文件，不依赖外部图片接口。

## 署名

`public/images/world/` 中 83 张来自 Wikimedia Commons（CC BY / CC BY-SA / CC0 / 公有领域），
作者与许可证见 [ATTRIBUTION.md](ATTRIBUTION.md)。
