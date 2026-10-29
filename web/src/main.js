import './styles/main.css'
import './styles/theme-history.css'
import { renderHome } from './ui/home.js'
import { renderGame } from './ui/game.js'

const app = document.getElementById('app')

// 入口决定默认产品线：index.html → 地理版；history.html → 历史版
// 两条线共用同一套渲染逻辑，靠 track 参数区分关卡表、题库桶、皮肤与榜单。
const ENTRY = app.dataset.entry === 'history' ? 'history' : 'geo'

function route() {
  // 清理上一屏（游戏页注册的地图/计时器等）
  if (typeof window.__gdCleanup === 'function') {
    window.__gdCleanup()
    window.__gdCleanup = null
  }

  // 异步加载游戏资源时，用 token 防止用户快速切换路由后旧请求覆盖新页面。
  const routeToken = Symbol('gd-route')
  window.__gdRouteToken = routeToken

  const match = location.hash.match(/^#\/(game|history)\/(china|world)$/)
  if (match) renderGame(app, match[2], routeToken, match[1] === 'history' ? 'history' : 'geo')
  else renderHome(app, ENTRY)
}

window.addEventListener('hashchange', route)
route()
