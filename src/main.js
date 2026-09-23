import './styles/main.css'
import { renderHome } from './ui/home.js'
import { renderGame } from './ui/game.js'

const app = document.getElementById('app')

function route() {
  // 清理上一屏（游戏页注册的地图/计时器等）
  if (typeof window.__gdCleanup === 'function') {
    window.__gdCleanup()
    window.__gdCleanup = null
  }

  // 异步加载游戏资源时，用 token 防止用户快速切换路由后旧请求覆盖新页面。
  const routeToken = Symbol('gd-route')
  window.__gdRouteToken = routeToken

  const match = location.hash.match(/^#\/game\/(china|world)$/)
  if (match) renderGame(app, match[1], routeToken)
  else renderHome(app)
}

window.addEventListener('hashchange', route)
route()
