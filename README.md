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

## 当前限制

- 成绩保存在浏览器 `localStorage`，不能跨设备同步。
- 没有后端排行榜，不能可靠比较不同玩家的成绩。
- 地名配图依赖外部远程图片接口。
