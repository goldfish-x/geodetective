import './styles/main.css'
import './styles/theme-history.css'
import { renderHome } from './ui/home.js'
import { renderGame } from './ui/game.js'
import { showLoadBar, hideLoadBar } from './core/loading.js'

const app = document.getElementById('app')

// 入口决定默认产品线：index.html → 地理版；history.html → 历史版
// 两条线共用同一套渲染逻辑，靠 track 参数区分关卡表、题库桶、皮肤与榜单。
const ENTRY = app.dataset.entry === 'history' ? 'history' : 'geo'

function route() {
  // 清理上一屏（游戏页注册的地图/计时器等）
  hideLoadBar()
  if (typeof window.__gdCleanup === 'function') {
    window.__gdCleanup()
    window.__gdCleanup = null
  }

  // 异步加载游戏资源时，用 token 防止用户快速切换路由后旧请求覆盖新页面。
  const routeToken = Symbol('gd-route')
  window.__gdRouteToken = routeToken

  const match = location.hash.match(/^#\/(game|history)\/(china|world)$/)
  if (match) {
    // 地图 + 题库 + 档案都是懒加载的，大屏也要 1–3 秒；先在底部挂一条进度条，
    // 免得点了篇章之后像没反应。renderGame 结束时（无论成功失败）都会摘掉。
    showLoadBar()
    renderGame(app, match[2], routeToken, match[1] === 'history' ? 'history' : 'geo')
      .catch(err => { console.error(err) })
      .finally(hideLoadBar)
  } else {
    hideLoadBar()
    renderHome(app, ENTRY)
  }
}

window.addEventListener('hashchange', route)
route()
