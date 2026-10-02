import { defineConfig } from 'vite'

// 坐标剥离开关：只有 demo（Pages 离线试玩）与 development（本地联调/离线回归）保留坐标；
// 生产构建（npm run build）把坐标 json 别名成空对象，产物中不含任何答案坐标。
export default defineConfig(({ mode }) => {
  const stripCoords = mode !== 'demo' && mode !== 'development'
  return {
    resolve: stripCoords ? {
      alias: [
        { find: /^\.\.\/data\/china-coords\.json$/, replacement: new URL('./src/data/_no_coords.json', import.meta.url).pathname },
        { find: /^\.\.\/data\/world-coords\.json$/, replacement: new URL('./src/data/_no_coords.json', import.meta.url).pathname }
      ]
    } : undefined,
    // 本地/自定义域名用 '/'；GitHub Pages 项目页用 '/geodetective/'。
    // CI 会通过 VITE_BASE 动态传入仓库名，避免仓库改名后资源路径失效。
    base: process.env.VITE_BASE || '/',
    server: {
      port: 5173,
      host: true
    }
  }
})
