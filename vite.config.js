import { defineConfig } from 'vite'

export default defineConfig({
  // 本地/自定义域名用 '/'；GitHub Pages 项目页用 '/geodetective/'。
  // CI 会通过 VITE_BASE 动态传入仓库名，避免仓库改名后资源路径失效。
  base: process.env.VITE_BASE || '/',
  server: {
    port: 5173,
    host: true
  }
})
