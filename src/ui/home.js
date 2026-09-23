// 首页：昵称、模式选择、排行榜、玩法说明
import { getNickname, setNickname, getTop10 } from '../core/storage.js'
import { MODES } from '../core/scoring.js'

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

      <div class="board">
        <div class="board-head">
          <span class="board-title">侦探荣誉榜</span>
          <div class="board-tabs">
            <button class="board-tab active" data-mode="china">中国篇</button>
            <button class="board-tab" data-mode="world">世界篇</button>
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
          <li>每局设有最低通关得分，局末未达标即任务中止；每局重置两枚道具：加时 +10 秒、提示大致方位（世界篇提示大洲）。</li>
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
  function renderBoard(mode) {
    const top = getTop10(mode)
    boardList.innerHTML = top.length
      ? top.map((r, i) => `
          <li>
            <span class="bl-idx">${i + 1}</span>
            <span class="bl-date">${r.date}</span>
            <span class="bl-score">${r.score.toLocaleString('zh-CN')}</span>
          </li>`).join('')
      : '<li class="empty">暂无记录 · 等待第一位侦探</li>'
  }

  app.querySelectorAll('.board-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      app.querySelectorAll('.board-tab').forEach(t => t.classList.remove('active'))
      tab.classList.add('active')
      renderBoard(tab.dataset.mode)
    })
  })

  // 未设昵称直接开局时，兜底保存输入框内容
  app.querySelectorAll('.mode-card').forEach(card => {
    card.addEventListener('click', () => {
      const v = input.value.trim()
      if (v) setNickname(v)
    })
  })

  renderBoard('china')
}
