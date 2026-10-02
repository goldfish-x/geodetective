// 首页：昵称、模式选择、排行榜、玩法说明
import { getNickname, setNickname, getTop10 } from '../core/storage.js'
import { MODES } from '@gd/shared'
import { api, onlineEnabled } from '../net/api.js'
import { getSession, setSession, clearSession } from '../net/session.js'

export function renderHome(app) {
  window.__gdCleanup = null
  const nickname = getNickname()

  app.innerHTML = `
  <div class="home-page">
    <div class="home-inner">
      <div class="home-file-tag">卷宗编号 · No.1893-Geo</div>
      <h1 class="home-title">地理大侦探</h1>
      <p class="home-tagline">一份加密地名档案 · 一枚放大镜 · 十次指认机会</p>

      <div class="nick-row">
        <label for="nick-input">侦探代号</label>
        <input id="nick-input" type="text" maxlength="12" placeholder="无名侦探" value="${nickname}">
      </div>

      <div class="mode-cards">
        <a class="mode-card china" href="#/game/china">
          <span class="mc-name">中国篇</span>
          <span class="mc-desc">省级区划地图 · 15 秒/题 · 300 km 判定</span>
          <span class="mc-cta">开始侦查 →</span>
        </a>
        <a class="mode-card world" href="#/game/world">
          <span class="mc-name">世界篇</span>
          <span class="mc-desc">立体地球 · 20 秒/题 · 1500 km 判定</span>
          <span class="mc-cta">开始侦查 →</span>
        </a>
      </div>

      <div class="online-row" id="online-row"></div>

      <div class="board">
        <div class="board-head">
          <span class="board-title">侦探荣誉榜</span>
          <div class="board-tabs">
            <button class="board-tab active" data-mode="china">中国篇</button>
            <button class="board-tab" data-mode="world">世界篇</button>
            <button class="board-tab scope active" id="scope-local">本机</button>
            <button class="board-tab scope" id="scope-global">全网</button>
          </div>
        </div>
        <ol class="board-list" id="board-list"></ol>
      </div>

      <details class="rules">
        <summary>玩法说明</summary>
        <ul>
          <li>共 10 局，每局 8 题：城市局与景点局交替，难度由简单逐局升至地狱。</li>
          <li>在地图上点击你认为的地理位置，越接近实际位置得分越高，单题最高 ${MODES.china.maxScore} 分。</li>
          <li>中国篇超过 300 km、世界篇超过 1500 km 即 0 分；超时亦 0 分。</li>
          <li>每局设有最低通关得分，局末未达标即任务中止。</li>
          <li>道具按付费档位发放（内测默认三档）：一档无道具；二档 2 枚加时沙漏 + 2 枚复活罗盘；三档再加 1 枚回溯怀表与 1 枚疆域透镜。</li>
          <li>加时沙漏：本题倒计时 +12 秒。复活罗盘：本局未达标时复活一次并进入下一局，该局在结算中以黄色标识。回溯怀表：回退并重做本局最近两题，重做得分替换原得分。疆域透镜：高亮答案所在的省份或国家，地图无该区域时改为文字提示。</li>
          <li>局末结算展示本局「地名档案」：悬停地名可阅读简介与配图，实际位置以红点标注在地图上。</li>
          <li>成绩自动记录到本机，各模式保留历史最高 10 次。</li>
        </ul>
      </details>

      <footer class="home-foot">地理大侦探 · 原型 v0.2 · 纯前端本地存档</footer>
    </div>
  </div>`

  const input = app.querySelector('#nick-input')
  input.addEventListener('change', () => {
    const v = input.value.trim()
    if (v) setNickname(v)
  })

  const boardList = app.querySelector('#board-list')
  // 前三名：1st/2nd/3rd 奖牌前缀 + 金/银/铜半透明背景板（配色见 main.css 的 li.topN）
  const MEDAL = { 1: '1st', 2: '2nd', 3: '3rd' }
  const online = onlineEnabled()
  let curMode = 'china', curScope = 'local'

  function rowsHtml(top) {
    return top.length
      ? top.map((r, i) => `
          <li${i < 3 ? ` class="top${i + 1}"` : ''}>
            <span class="bl-idx">${i < 3 ? `<em class="bl-medal">${MEDAL[i + 1]}</em>` : i + 1}</span>
            <span class="bl-date">${r.who ? r.who + ' · ' : ''}${r.date}</span>
            <span class="bl-score">${r.score.toLocaleString('zh-CN')}</span>
          </li>`).join('')
      : '<li class="empty">暂无记录 · 等待第一位侦探</li>'
  }

  async function renderBoard() {
    if (curScope === 'local' || !online) {
      boardList.innerHTML = rowsHtml(getTop10(curMode).map(r => ({ score: r.score, date: r.date })))
      return
    }
    try {
      const d = await api('/v1/boards/' + curMode + '?limit=10')
      boardList.innerHTML = rowsHtml(d.board.map(r => ({ score: r.score, date: r.date, who: r.nickname })))
    } catch {
      boardList.innerHTML = '<li class="empty">全网榜暂不可用 · 已回落到本机榜</li>'
    }
  }

  // —— 登录行：在线模式才出现；离线试玩保持原样 ——
  const row = app.querySelector('#online-row')
  function renderRow() {
    if (!online) {
      row.innerHTML = '<span class="or-off">离线试玩模式 · 成绩只记本机</span>'
      app.querySelector('#scope-global').classList.add('hidden')
      return
    }
    const s = getSession()
    row.innerHTML = s.access
      ? `<span class="or-on">已登录 ${s.phone} · ${s.nickname || '无名侦探'}</span><button class="or-btn" id="btn-logout">退出</button>`
      : `<input id="login-phone" inputmode="numeric" maxlength="11" placeholder="手机号">
         <button class="or-btn" id="btn-code">获取验证码</button>
         <input id="login-code" inputmode="numeric" maxlength="6" placeholder="验证码">
         <button class="or-btn primary" id="btn-login">登录</button>
         <span class="or-tip" id="login-tip"></span>`
    const tip = msg => { const t = app.querySelector('#login-tip'); if (t) t.textContent = msg }
    app.querySelector('#btn-logout')?.addEventListener('click', () => { clearSession(); renderRow(); renderBoard() })
    app.querySelector('#btn-code')?.addEventListener('click', async () => {
      const phone = app.querySelector('#login-phone').value.trim()
      try {
        const d = await api('/v1/auth/code', { method: 'POST', body: { phone } })
        tip(d.devCode ? '开发环境验证码：' + d.devCode : '验证码已发送')
      } catch (e) { tip(e.message) }
    })
    app.querySelector('#btn-login')?.addEventListener('click', async () => {
      const phone = app.querySelector('#login-phone').value.trim()
      const code = app.querySelector('#login-code').value.trim()
      try {
        const d = await api('/v1/auth/login', { method: 'POST', body: { phone, code, nickname: getNickname() } })
        setSession({ access: d.access, refresh: d.refresh, phone: d.user.phone, nickname: d.user.nickname })
        renderRow(); renderBoard()
      } catch (e) { tip(e.message) }
    })
  }

  app.querySelectorAll('.board-tab[data-mode]').forEach(tab => {
    tab.addEventListener('click', () => {
      app.querySelectorAll('.board-tab[data-mode]').forEach(t => t.classList.remove('active'))
      tab.classList.add('active')
      curMode = tab.dataset.mode
      renderBoard()
    })
  })
  for (const [id, scope] of [['scope-local', 'local'], ['scope-global', 'global']]) {
    app.querySelector('#' + id).addEventListener('click', e => {
      curScope = scope
      app.querySelector('#scope-local').classList.toggle('active', scope === 'local')
      app.querySelector('#scope-global').classList.toggle('active', scope === 'global')
      renderBoard()
    })
  }
  renderRow()
  renderBoard()

  // 未设昵称直接开局时，兜底保存输入框内容
  app.querySelectorAll('.mode-card').forEach(card => {
    card.addEventListener('click', () => {
      const v = input.value.trim()
      if (v) setNickname(v)
    })
  })

}
