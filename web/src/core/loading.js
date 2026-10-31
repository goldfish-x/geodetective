// 加载进度条：进入对局时立刻在页面底部出现，导入地图/题库/档案/配图清单时分段前进。
// 只在「进入对局」这条路径上用，首页与结算页都不受影响。
let el = null
let fillEl = null
let textEl = null
let timer = 0
let cur = 0

function paint() {
  if (fillEl) fillEl.style.width = cur + '%'
  if (textEl && !textEl.textContent) textEl.textContent = '正在加载…'
}

export function showLoadBar(text = '正在加载地图与题库…') {
  hideLoadBar()
  cur = 0
  el = document.createElement('div')
  el.className = 'gd-load'
  el.id = 'gd-load'
  el.innerHTML = '<div class="gd-load-title">正在调取档案</div>'
    + '<div class="gd-load-track"><i id="gd-load-fill"></i></div>'
    + '<div class="gd-load-text" id="gd-load-text"></div>'
  document.body.appendChild(el)
  fillEl = el.querySelector('#gd-load-fill')
  textEl = el.querySelector('#gd-load-text')
  bump(6, text)
  // 真实进度回调之间间隔可能较长，这里做一个缓动蠕升（最高 90%），避免看起来卡住
  timer = setInterval(() => {
    if (cur >= 90) return
    cur = Math.min(90, cur + Math.max(0.6, (90 - cur) * 0.07))
    paint()
  }, 180)
}

export function bump(pct, text) {
  if (!el) return
  cur = Math.max(cur, Math.max(0, Math.min(100, pct)))
  if (text && textEl) textEl.textContent = text
  paint()
}

export function hideLoadBar() {
  if (timer) { clearInterval(timer); timer = 0 }
  if (el && el.parentNode) el.parentNode.removeChild(el)
  el = fillEl = textEl = null
  cur = 0
}
