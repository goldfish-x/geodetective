// 游戏页：出题 → 作答 → 单题结算 → 局结算（最低分门槛） → 终局结算
import { MODES, haversine, score, buildQuiz, STAGE_SIZE, STAGES, DIFFICULTY_LABELS, PROPS, PROP_ORDER, tierCounts } from '@gd/shared'
import { getNickname, addScore } from '../core/storage.js'
import { onlineEnabled } from '../net/api.js'
import { getSession } from '../net/session.js'
import { createOnlineGame } from '../net/online-game.js'
import {
  isMuted, toggleMute, sfxPick, sfxConfirm, sfxJudge, sfxTimeout,
  sfxTick, sfxProp, sfxStageClear, sfxGameOver, sfxVictory, sfxChampion
} from '../core/audio.js'

const ICON_SND_ON = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5L6 9H3v6h3l5 4V5z" fill="currentColor" stroke="none"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.5 6a9 9 0 0 1 0 12"/></svg>`
const ICON_SND_OFF = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5L6 9H3v6h3l5 4V5z" fill="currentColor" stroke="none"/><path d="M16 9l6 6M22 9l-6 6"/></svg>`

const ICON_CLOCK = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>`
const ICON_COMPASS = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z" fill="currentColor" stroke="none"/></svg>`

const fmt = n => n.toLocaleString('zh-CN')
const pad2 = n => String(n).padStart(2, '0')

// 榜首庆祝用的金粉雨：种子固定 → 每次呈现完全一致（自动化测试可断言片数与位置）
const CONFETTI_N = 36
function confettiHtml() {
  const COLORS = ['#e8b64c', '#d9a441', '#ece1c8', '#f2d489', '#d0563f']
  let seed = 20260928
  const rnd = () => (seed = (seed * 48271) % 2147483647) / 2147483647
  const bits = Array.from({ length: CONFETTI_N }, () => {
    const c = COLORS[Math.floor(rnd() * COLORS.length)]
    return `<i style="--l:${(rnd() * 100).toFixed(2)}%;--w:${(4 + rnd() * 5).toFixed(1)}px;` +
      `--h:${(7 + rnd() * 8).toFixed(1)}px;--d:${(2.2 + rnd() * 2.4).toFixed(2)}s;` +
      `--dl:${(rnd() * 1.2).toFixed(2)}s;--r:${Math.floor(rnd() * 720 - 360)}deg;` +
      `--o:${(0.55 + rnd() * 0.45).toFixed(2)};background:${c}"></i>`
  }).join('')
  return `<div class="confetti" aria-hidden="true">${bits}</div>`
}

// 地名简介与配图：优先加载 public/images 中的真实图片；
// 没有本地图片的地点回退到确定性视觉占位图，避免远程服务不可用时出现空白。
import { placeholderFor } from '../core/placeholder.js'
const imgURL = (name, modeKey, availableImages) => {
  if (availableImages.has(name)) {
    return `${import.meta.env.BASE_URL}images/${modeKey}/${encodeURIComponent(name)}.webp`
  }
  return placeholderFor(name, 120, 120)
}

export async function renderGame(app, modeKey, routeToken) {
  const mode = MODES[modeKey]
  if (!mode) return

  // 按模式懒加载地图、题库与档案，避免 ECharts/ECharts GL 与两套大 GeoJSON 全部进入首屏。
  const [mapModule, bankModule, descModule, imagesModule] = await Promise.all([
    modeKey === 'china' ? import('./map-china.js') : import('./map-world.js'),
    modeKey === 'china' ? import('../data/china.json') : import('../data/world.json'),
    modeKey === 'china' ? import('../data/china-desc.json') : import('../data/world-desc.json'),
    modeKey === 'china' ? import('../data/china-images.json') : import('../data/world-images.json')
  ])
  if (window.__gdRouteToken !== routeToken || !app.isConnected) return

  const bank = bankModule.default
  const descBank = descModule.default
  const availableImages = new Set(imagesModule.default)
  const descOf = name => descBank[name] || {}

  // 在线模式：未登录则回首页提示登录；已登录则整局由服务端驱动
  const wantOnline = onlineEnabled()
  if (wantOnline && !getSession().access) {
    app.innerHTML = `<div class="result-page"><div class="result-card">
      <div class="result-stamp">需登录</div>
      <p class="result-sub">在线对局的成绩计入全网榜，请先在首页登录</p>
      <div class="result-actions"><button class="btn btn-primary" id="btn-home">返回首页</button></div>
    </div></div>`
    app.querySelector('#btn-home').addEventListener('click', () => { location.hash = '#/' })
    return
  }
  const online = wantOnline ? await createOnlineGame(modeKey) : null

  // 离线玩法需要坐标做本地判分；在线模式坐标一律来自服务端揭晓，构建期也不进产物
  if (!online) {
    const { loadCoords, mergeCoords } = await import('../core/coords.js')
    mergeCoords(bank, (await loadCoords(modeKey)).default)
  }
  const stages = online ? online.stages : buildQuiz(bank)

  const state = {
    stageIndex: 0,      // 当前局（0 起）
    qInStage: 0,        // 局内题目序号（0 起）
    total: 0,           // 总分
    stageScore: 0,      // 当前局得分
    records: [],
    guess: null,
    phase: 'answering', // answering | settle | done
    props: {},            // 道具剩余次数（按付费档位发放，整局共享）
    revived: [],          // 被复活罗盘救回的局号（结算标黄）
    tier: 3,
    timerTotal: mode.timeLimit,
    timerRemain: mode.timeLimit,
    timerEnd: 0,
    rafId: 0
  }

  app.innerHTML = `
  <div class="game-page">
    <header class="game-top">
      <button class="btn-back" id="btn-back" title="返回首页">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>
      </button>
      <div class="q-meta">
        <span class="q-badge" id="q-badge">城市</span>
        <span class="q-name" id="q-name">——</span>
        <span class="q-diff" id="q-diff" title="难度等级"></span>
      </div>
      <div class="q-stats">
        <span class="q-index" id="q-index">第1局 · 01/08</span>
        <span class="q-stage" id="q-stage-wrap">本局 <em id="q-stage-score">0</em>/<span id="q-target">8,000</span></span>
        <span class="q-score">总分 <em id="q-score">0</em></span>
      </div>
      <button class="btn-snd" id="btn-snd" title="音效开关"></button>
    </header>

    <div class="hint-banner hidden" id="hint-banner"></div>

    <div class="map-stage">
      <div class="map-wrap">
        <div class="map-holder" id="map-holder"></div>

        <div class="confirm-pop hidden" id="confirm-pop">
          <span class="confirm-text">就是这里？</span>
          <button class="btn btn-ghost" id="btn-rechoose">重选</button>
          <button class="btn btn-primary" id="btn-confirm">确认指认</button>
        </div>

        <div class="toast hidden" id="toast"></div>
      </div>

      <aside class="card-slot" id="card-slot">
        <div class="settle-pop hidden" id="settle-pop">
          <div class="settle-title" id="settle-title"></div>
          <div class="settle-meter" aria-hidden="true"><i id="settle-meter-fill"></i></div>
          <div class="settle-detail" id="settle-detail"></div>
          <button class="btn btn-primary" id="btn-next">下一题</button>
          <div class="settle-tip">点击「下一题」继续 · 也可按回车</div>
        </div>
      </aside>
    </div>

    <footer class="game-bottom">
      <div class="props" id="props-bar"></div>
      <div class="timer">
        <div class="timer-fill" id="timer-fill"></div>
        <span class="timer-text" id="timer-text"></span>
      </div>
    </footer>
  </div>`

  const $ = id => app.querySelector('#' + id)
  const elMap = $('map-holder')
  const elName = $('q-name'), elBadge = $('q-badge'), elIndex = $('q-index'), elScore = $('q-score'), elDiff = $('q-diff')
  const elStageScore = $('q-stage-score'), elTarget = $('q-target')
  const elFill = $('timer-fill'), elTimerText = $('timer-text')
  const elConfirm = $('confirm-pop'), elSettle = $('settle-pop'), elMeterFill = $('settle-meter-fill'), elToast = $('toast'), elHint = $('hint-banner')
  const btnNext = $('btn-next'), elTimer = app.querySelector('.timer')
  const elSlot = $('card-slot')
  // 结算卡/局档案不浮在地图上，而是占一条独立栏位：出现时地图收缩让位，红点绝不被遮
  const setSlot = on => elSlot.classList.toggle('active', on)

  const createMap = modeKey === 'china' ? mapModule.createChinaMap : mapModule.createWorldMap
  const map = createMap(elMap, {
    onPick: handlePick,
    onInvalidPick: () => showToast(modeKey === 'china' ? '请点击地图区域内' : '请点击地球表面')
  })

  // ————— 音效开关 —————
  const elSnd = $('btn-snd')
  const syncSndIcon = () => { elSnd.innerHTML = isMuted() ? ICON_SND_OFF : ICON_SND_ON }
  syncSndIcon()
  elSnd.addEventListener('click', () => { toggleMute(); syncSndIcon() })

  // ————— 数字滚动动画 —————
  const animEls = new Set()
  function countUp(el, from, to, dur = 600) {
    if (el.__raf) cancelAnimationFrame(el.__raf)
    animEls.add(el)
    const t0 = performance.now()
    const step = now => {
      const k = Math.min(1, (now - t0) / dur)
      const eased = 1 - (1 - k) ** 3 // easeOutCubic
      el.textContent = fmt(Math.round(from + (to - from) * eased))
      el.__raf = k < 1 ? requestAnimationFrame(step) : null
    }
    el.__raf = requestAnimationFrame(step)
  }
  const stopCountUps = () => {
    animEls.forEach(el => { if (el.__raf) { cancelAnimationFrame(el.__raf); el.__raf = null } })
    animEls.clear()
  }

  // ————— 倒计时 —————
  function tick() {
    // 只在答题态推进：单题结算、局档案面板、终局停留时绝不允许计时条继续走动
    if (state.phase !== 'answering') { state.rafId = 0; return }
    state.timerRemain = Math.max(0, (state.timerEnd - performance.now()) / 1000)
    const ratio = state.timerRemain / state.timerTotal
    elFill.style.width = (ratio * 100) + '%'
    elFill.classList.toggle('warn', ratio <= 0.5 && ratio > 0.2)
    elFill.classList.toggle('danger', ratio <= 0.2)
    elTimerText.textContent = state.timerRemain.toFixed(1) + 's'
    // 最后 3 秒：滴答音 + 文本脉冲
    const secLeft = Math.ceil(state.timerRemain)
    if (state.timerRemain > 0 && secLeft <= 3 && secLeft !== state.lastTickSec) {
      state.lastTickSec = secLeft
      sfxTick()
      elTimerText.classList.remove('pulse')
      void elTimerText.offsetWidth // 重触发动画
      elTimerText.classList.add('pulse')
    }
    if (state.timerRemain <= 0) { onTimeout(); return }
    state.rafId = requestAnimationFrame(tick)
  }

  function startTimer() {
    cancelAnimationFrame(state.rafId)
    state.timerEnd = performance.now() + state.timerRemain * 1000
    state.rafId = requestAnimationFrame(tick)
  }

  function stopTimer() {
    cancelAnimationFrame(state.rafId)
  }

  // ————— 道具栏：图标 + 剩余次数 + 悬停说明 —————
  const PROP_ICON = {
    time: '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 2h12M6 22h12M8 2c0 5 3 6 4 8 1-2 4-3 4-8M8 22c0-5 3-6 4-8 1 2 4 3 4 8"/></svg>',
    revive: '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20 3v5h-5"/><circle cx="12" cy="12" r="2.4"/></svg>',
    redo: '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/></svg>',
    area: '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 2 3 7v10l9 5 9-5V7z"/><path d="M12 22V12M3 7l9 5 9-5"/></svg>'
  }

  function renderProps() {
    const bar = $('props-bar')
    if (!bar) return
    const locked = state.phase !== 'answering'
    bar.innerHTML = PROP_ORDER.map(k => {
      const left = state.props[k] || 0
      return `<button class="prop${left > 0 ? '' : ' used'}${locked ? ' locked' : ''}" data-prop="${k}" aria-label="${PROPS[k].name}">
        ${PROP_ICON[k]}<em class="prop-n">${left}</em></button>`
    }).join('') + '<span class="prop-tip" id="prop-tip" role="tooltip"></span>'
    bar.querySelectorAll('[data-prop]').forEach(btn => {
      const k = btn.dataset.prop
      btn.addEventListener('click', () => useProp(k))
      const show = () => {
        const tip = $('prop-tip')
        tip.innerHTML = `<b>${PROPS[k].name}</b> · 剩 ${state.props[k] || 0} 次<br>${PROPS[k].effect}`
        const p = bar.getBoundingClientRect(), r = btn.getBoundingClientRect()
        tip.style.left = Math.max(4, Math.min(r.left - p.left + r.width / 2 - 92, p.width - 188)) + 'px'
        tip.classList.add('show')
      }
      const hide = () => $('prop-tip').classList.remove('show')
      btn.addEventListener('mouseenter', show)
      btn.addEventListener('focus', show)
      btn.addEventListener('mouseleave', hide)
      btn.addEventListener('blur', hide)
    })
  }

  function showArea(area, hint) {
    if (area) {
      elHint.innerHTML = `<b>答案所在</b>：${area}`
      elHint.classList.remove('hidden')
      if (modeKey === 'china') map.highlightArea(area)
      else map.highlightCountry(area)
    } else {
      const label = modeKey === 'china' ? '大致方位' : '所在大洲'
      elHint.innerHTML = `<b>${label}</b>：${hint}`
      elHint.classList.remove('hidden')
      map.highlightRegion(hint)
    }
  }

  function rewindLocal(n) {
    for (let i = 0; i < n; i++) {
      const rec = state.records.pop()
      if (!rec) break
      state.total -= rec.points
      state.stageScore -= rec.points
    }
    state.qInStage = Math.max(0, state.qInStage - n)
    elScore.textContent = fmt(state.total)
    elStageScore.textContent = fmt(state.stageScore)
    startQuestion()
  }

  async function useProp(k) {
    if (k === 'revive') return            // 复活只在局结算面板触发
    if (state.phase !== 'answering' || !(state.props[k] > 0)) return
    if (k === 'redo' && state.qInStage < 1) { showToast('本局还没有可回退的题目'); return }
    sfxProp()
    if (online) {
      try {
        if (k === 'time') {
          const d = await online.prop('time')
          state.timerTotal += d.add; state.timerRemain += d.add
          state.lastTickSec = 99; startTimer(); showToast('已加时 12 秒')
        } else if (k === 'area') {
          const d = await online.prop('area'); showArea(d.area, d.hint)
        } else if (k === 'redo') {
          const d = await online.prop('redo'); online.ord = d.ord; rewindLocal(d.rewound)
        }
        state.props[k] -= 1
        renderProps()
      } catch (e) { showToast(e.message) }
      return
    }
    const q = stages[state.stageIndex].questions[state.qInStage]
    if (k === 'time') {
      state.timerTotal += 12; state.timerRemain += 12
      state.lastTickSec = 99; startTimer(); showToast('已加时 12 秒')
    } else if (k === 'area') showArea(q.area || '', q.hint)
    else if (k === 'redo') rewindLocal(Math.min(2, state.qInStage))
    state.props[k] -= 1
    renderProps()
  }

  // 把计时条彻底停住：不留上一题的残条，也不让它看起来还在倒计时
  function parkTimer(text) {
    elFill.style.width = '0%'
    elFill.classList.remove('warn', 'danger')
    elTimerText.textContent = text
    elTimerText.classList.remove('pulse')
    elTimer.classList.add('settled')
    renderProps()
  }

  // ————— 流程 —————
  function startQuestion() {
    state.phase = 'answering'
    state.guess = null
    state.timerTotal = mode.timeLimit
    state.timerRemain = mode.timeLimit
    state.lastTickSec = 99
    map.clearPick()
    map.clearHighlight()
    // 清掉上一题的揭晓物：答案红点（带地名标签）与浅蓝连线，
    // 否则新一题开始时屏幕上还挂着上一题的正确答案位置与名称
    map.clearReveal()
    map.clearSpot()
    elHint.classList.add('hidden')
    elConfirm.classList.add('hidden')
    elSettle.classList.add('hidden')
    renderProps()
    elTimer.classList.remove('settled')
    setSlot(false)

    const stage = stages[state.stageIndex]
    const q = stage.questions[state.qInStage]

    // 新一局：重置道具与本局计分
    if (state.qInStage === 0) {
      elTarget.textContent = fmt(stage.minScore)
      elStageScore.textContent = '0'
      $('q-stage-wrap').classList.remove('danger')
    }

    elBadge.textContent = q.type === 'city' ? '城市' : '景点'
    elBadge.classList.toggle('scenic', q.type === 'scenic')
    elName.textContent = q.name
    const lv = Math.min(5, Math.max(1, q.difficulty || 1))
    elDiff.className = 'q-diff lv' + lv
    elDiff.title = `难度 ${lv}/5 · ${DIFFICULTY_LABELS[lv]}`
    elDiff.textContent = '★'.repeat(lv) + '☆'.repeat(5 - lv)
    elIndex.textContent = `第${state.stageIndex + 1}局 · ${pad2(state.qInStage + 1)}/${pad2(STAGE_SIZE)}`
    // 题目名入场动画（重触发）
    elName.classList.remove('enter')
    void elName.offsetWidth
    elName.classList.add('enter')
    startTimer()
  }

  function handlePick(lng, lat) {
    if (state.phase !== 'answering') return
    state.guess = { lng, lat }
    map.setPick(lng, lat)
    sfxPick()
    elConfirm.classList.remove('hidden')
  }

  $('btn-rechoose').addEventListener('click', () => {
    state.guess = null
    map.clearPick()
    elConfirm.classList.add('hidden')
  })

  $('btn-confirm').addEventListener('click', () => {
    if (!state.guess) return
    stopTimer()
    sfxConfirm()
    settle(false)
  })

  function onTimeout() {
    stopTimer()
    if (state.phase !== 'answering') return
    state.guess = null
    settle(true)
  }

  async function settle(timedOut) {
    state.phase = 'settle'
    elConfirm.classList.add('hidden')

    const q = stages[state.stageIndex].questions[state.qInStage]
    let dist = null, pts = 0
    if (online) {
      // 服务端判分：本地不算距离与得分，超时/未指认由服务端一并裁定
      const r = await online.answer(timedOut ? null : state.guess, state.stageIndex)
      pts = r.points
      dist = r.distanceKm
      timedOut = r.timedOut
      Object.assign(q, { lat: r.reveal.lat, lng: r.reveal.lng })
    } else if (state.guess) {
      dist = haversine(state.guess.lat, state.guess.lng, q.lat, q.lng)
      pts = score(dist, mode)
    }
    const prevTotal = state.total, prevStage = state.stageScore
    state.total += pts
    state.stageScore += pts
    state.records.push({
      name: q.name, distance: dist, points: pts, timedOut,
      difficulty: q.difficulty || 1,
      stage: state.stageIndex + 1, q: state.qInStage + 1
    })
    // 得分滚动动画
    countUp(elScore, prevTotal, state.total)
    countUp(elStageScore, prevStage, state.stageScore)
    $('q-stage-wrap').classList.toggle('danger', state.stageScore < stages[state.stageIndex].minScore)

    // 先让出卡片栏位（地图同帧收缩），再揭晓答案，避免红点位置事后跳一下
    setSlot(true)
    map.reveal(q, state.guess)

    // 音效 + 判级文案
    const ratio = pts / mode.maxScore
    elMeterFill.style.width = `${Math.max(4, ratio * 100)}%`
    elMeterFill.className = timedOut || ratio <= 0 ? 'bad'
      : ratio >= 0.8 ? 'great'
      : ratio >= 0.4 ? 'good'
      : 'ok'
    if (timedOut) sfxTimeout()
    else sfxJudge(ratio)
    const grade = timedOut ? '<span class="grade bad">超 时</span>'
      : ratio >= 0.8 ? '<span class="grade great">精 准</span>'
      : ratio >= 0.4 ? '<span class="grade good">接 近</span>'
      : pts > 0 ? '<span class="grade ok">偏 远</span>'
      : '<span class="grade bad">失 手</span>'
    $('settle-title').innerHTML = `${grade}<b>${fmt(pts)}</b><small>分</small>`
    const distText = dist != null ? `距离实际位置 <b>${fmt(Math.round(dist))}</b> 公里` : '未能完成指认'
    const lv = Math.min(5, Math.max(1, q.difficulty || 1))
    $('settle-detail').innerHTML = `${q.name} · <span class="diff-tag lv${lv}">${DIFFICULTY_LABELS[lv]}</span> · ${distText}`
    elSettle.classList.remove('hidden')
    // 结算弹层重触发入场动画
    elSettle.classList.remove('pop')
    void elSettle.offsetWidth
    elSettle.classList.add('pop')

    // 节奏交给玩家：不再自动跳题，必须点击「下一题」（或按回车/空格）才进入下一题
    btnNext.textContent = state.qInStage + 1 >= STAGE_SIZE ? '查看本局档案' : '下一题'
    elTimer.classList.add('settled')
    elTimerText.textContent = '已结算'
    btnNext.focus({ preventScroll: true })
  }

  function next() {
    // 只有「单题结算」态能推进，天然防止回车+点击重复触发导致连跳两题
    if (state.phase !== 'settle') return
    if (online) {
      if (online.last && online.last.stageSettle) { showStageSettle(); return }
      state.qInStage++
      startQuestion()
      return
    }
    state.qInStage++

    if (state.qInStage < STAGE_SIZE) {
      startQuestion()
      return
    }

    // —— 局结算：展示本局地名档案面板，由面板按钮驱动后续流程 ——
    showStageSettle()
  }

  // ————— 局结算：地名档案面板 —————
  function showStageSettle() {
    state.phase = 'stageSettle'
    stopTimer()
    parkTimer('本局小结')
    elSettle.classList.add('hidden')
    elConfirm.classList.add('hidden')
    elHint.classList.add('hidden')
    setSlot(true)
    map.clearPick()
    map.clearHighlight()
    map.clearReveal()

    const stage = stages[state.stageIndex]
    const passed = online ? online.last.stageSettle.passed : state.stageScore >= stage.minScore
    const isLast = state.stageIndex === stages.length - 1
    if (passed) sfxStageClear()

    // 预加载本局著名地点配图，悬停时即可快速显示
    stage.questions.forEach(q => {
      const e = descOf(q.name)
      if (availableImages.has(q.name)) { const im = new Image(); im.src = imgURL(q.name, modeKey, availableImages) }
    })

    const panel = document.createElement('div')
    panel.className = 'stage-settle'
    panel.innerHTML = `
      <div class="ss-head">
        <span class="ss-title">第${state.stageIndex + 1}局 · ${stage.type === 'city' ? '城市' : '景点'}档案</span>
        <span class="ss-result ${passed ? 'pass' : 'fail'}">${passed ? '通 关' : '未达标'}</span>
      </div>
      <div class="ss-score-line">本局得分 <b>${fmt(state.stageScore)}</b> / 通关门槛 ${fmt(stage.minScore)} · 单题最高 ${fmt(mode.maxScore)}</div>
      <div class="ss-body">
        <div class="ss-list">
          ${stage.questions.map((q, i) => `
            <button class="ss-chip" data-i="${i}" title="${q.name}"><i>${pad2(i + 1)}</i>${q.name}</button>`).join('')}
        </div>
        <div class="ss-detail" id="ss-detail">
          <div class="ss-empty">悬停左侧地名<br>查看档案与实际位置</div>
        </div>
      </div>
      <div class="ss-foot">
        <span class="ss-hint">悬停地名 · 地图红点即实际位置${modeKey === 'world' ? ' · 地球自动转向' : ''}</span>
        ${!passed && (state.props.revive || 0) > 0 && !isLast ? `<button class="btn btn-ghost revive" id="btn-revive">复活罗盘 · 剩 ${state.props.revive}</button>` : ''}
        <button class="btn btn-primary" id="btn-stage-next">${passed ? (isLast ? '查看最终结算' : `进入第${state.stageIndex + 2}局`) : '结束本局任务'}</button>
      </div>`
    elSlot.appendChild(panel)

    const detail = panel.querySelector('#ss-detail')
    const showDetail = q => {
      const e = descOf(q.name)
      const lv = Math.min(5, Math.max(1, q.difficulty || 1))
      detail.innerHTML = `
        ${availableImages.has(q.name) || e.img ? `<img class="ss-img" src="${imgURL(q.name, modeKey, availableImages)}" alt="${q.name}" onerror="this.remove()">` : ''}
        <div class="ss-text">
          <div class="ss-name">${q.name}<em class="diff-tag lv${lv}">${DIFFICULTY_LABELS[lv]}</em></div>
          <p class="ss-desc">${e.desc || ''}</p>
          <div class="ss-geo">${q.hint} · ${Math.abs(q.lat).toFixed(2)}°${q.lat >= 0 ? 'N' : 'S'} ${Math.abs(q.lng).toFixed(2)}°${q.lng >= 0 ? 'E' : 'W'}</div>
        </div>`
      const img = detail.querySelector('.ss-img')
      if (img) img.addEventListener('load', () => img.classList.add('ok'))
      map.showSpot(q.lng, q.lat)
    }

    panel.querySelectorAll('.ss-chip').forEach(chip => {
      const q = stage.questions[+chip.dataset.i]
      const activate = () => {
        panel.querySelectorAll('.ss-chip').forEach(c => c.classList.remove('active'))
        chip.classList.add('active')
        showDetail(q)
      }
      chip.addEventListener('mouseenter', activate)
      chip.addEventListener('mouseleave', () => map.clearSpot())
      chip.addEventListener('click', activate) // 触屏设备支持
    })

    panel.querySelector('#btn-revive')?.addEventListener('click', async () => {
      state.props.revive -= 1
      state.revived.push(state.stageIndex + 1)
      panel.remove()
      map.clearSpot()
      if (online) {
        const d = await online.prop('revive')
        state.stageIndex = d.nextStage - 1
      } else {
        state.stageIndex++
      }
      state.qInStage = 0
      state.stageScore = 0
      const flash = document.createElement('div')
      flash.className = 'stage-flash'
      flash.innerHTML = `<span>第${state.stageIndex + 1}局 复活</span>`
      elMap.parentElement.appendChild(flash)
      setTimeout(() => flash.remove(), 1100)
      renderProps()
      startQuestion()
    })

    panel.querySelector('#btn-stage-next').addEventListener('click', () => {
      panel.remove()
      map.clearSpot()
      if (!passed) { endGame(false); return }
      if (isLast) { endGame(true); return }

      state.stageIndex++
      state.qInStage = 0
      state.stageScore = 0
      // 局过关：全屏闪过动效
      const flash = document.createElement('div')
      flash.className = 'stage-flash'
      flash.innerHTML = `<span>第${state.stageIndex}局 通过</span>`
      elMap.parentElement.appendChild(flash)
      setTimeout(() => flash.remove(), 1100)
      showToast(`通过第${state.stageIndex}局 · 挑战第${state.stageIndex + 1}局`)
      startQuestion()
    })
  }

  btnNext.addEventListener('click', next)
  // 键盘推进：焦点已在按钮上时交给浏览器原生 click，避免同一次按键触发两次跳题
  const onKey = e => {
    if (state.phase !== 'settle') return
    if (e.key !== 'Enter' && e.key !== ' ') return
    if (document.activeElement === btnNext) return
    e.preventDefault()
    next()
  }
  window.addEventListener('keydown', onKey)

  // ————— 终局 —————
  async function endGame(victory) {
    state.phase = 'done'
    stopTimer()
    map.dispose()
    if (victory) sfxVictory()
    else sfxGameOver()

    const nickname = getNickname() || '无名侦探'
    const rankInfo = online
      ? await online.finish().then(fb => { state.total = fb.total; return { rank: fb.rank, board: fb.board } })
      : addScore(modeKey, state.total)
    const champion = !!rankInfo && rankInfo.rank === 1   // 本次成绩登顶 → 播放庆祝画面
    const reached = Math.min(state.stageIndex + 1, STAGES.length)

    app.innerHTML = `
    <div class="result-page">
      <div class="result-card${champion ? ' champion' : ''}">
        <div class="result-stamp">${victory ? '完美结案' : '任务中止'}</div>
        ${champion ? '<div class="result-crown">★ 独占榜首 · 新纪录 ★</div>' : ''}
        <p class="result-sub">${nickname} · ${mode.title} · ${victory ? '十局全部通关' : `止步第${reached}局`}</p>
        <div class="result-score"><em>${fmt(state.total)}</em><span>总分</span></div>
        ${champion
          ? `<div class="result-rank first">第 1 名 · ${online ? '全网榜首' : '本机历史最高'}</div>`
          : rankInfo
            ? `<div class="result-rank">进入个人榜单 · 第 ${rankInfo.rank} 名</div>`
            : '<div class="result-rank dim">未能进入个人 Top 10</div>'}
        <div class="result-stagebar">
          ${STAGES.map((s, i) => {
            const cleared = victory || i < state.stageIndex
            return `<span class="stage-dot${cleared ? ' cleared' : ''}${state.revived.includes(i + 1) ? ' revived' : ''}" title="第${i + 1}局 · ${DIFFICULTY_LABELS[s.difficulty]}${s.type === 'city' ? '城市' : '景点'} · 门槛 ${fmt(s.minScore)}">${i + 1}</span>`
          }).join('<i class="stage-sep"></i>')}
        </div>
        ${state.revived.length ? `<p class="result-revived-note">黄色局为复活罗盘救回：第 ${state.revived.join('、')} 局</p>` : ''}
        <ol class="result-list">
          ${state.records.map(r => `
            <li${state.revived.includes(r.stage) ? ' class="revived"' : ''}>
              <span class="rl-idx">${r.stage}-${pad2(r.q)}</span>
              <span class="rl-name">${r.name}<em class="diff-tag lv${Math.min(5, r.difficulty)}">${DIFFICULTY_LABELS[Math.min(5, r.difficulty)]}</em></span>
              <span class="rl-dist">${r.distance != null ? fmt(Math.round(r.distance)) + ' km' : '未指认'}</span>
              <span class="rl-pts">${fmt(r.points)}</span>
            </li>`).join('')}
        </ol>
        <div class="result-actions">
          <button class="btn btn-primary" id="btn-again">再来一局</button>
          <button class="btn btn-ghost" id="btn-home">返回首页</button>
        </div>
      </div>
      ${champion ? confettiHtml() : ''}
    </div>`

    app.querySelector('#btn-again').addEventListener('click', () => {
      location.hash = '#/game/' + modeKey
      if (location.hash === '#/game/' + modeKey) window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
    app.querySelector('#btn-home').addEventListener('click', () => { location.hash = '#/' })

    // 终局总分滚动 + 印章盖戳动画
    countUp(app.querySelector('.result-score em'), 0, state.total, 1200)
    // 登顶：等印章落稳（0.35s 延迟 + 0.45s 动画）后补一段凯歌
    if (champion) championTimer = setTimeout(sfxChampion, 820)
  }

  $('btn-back').addEventListener('click', () => { location.hash = '#/' })

  let toastTimer = 0
  let championTimer = 0   // 登顶凯歌的延时，路由切换时必须清掉
  function showToast(msg) {
    elToast.textContent = msg
    elToast.classList.remove('hidden')
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => elToast.classList.add('hidden'), 1600)
  }

  // 道具按档位发放：在线由服务端下发，离线读本地档位（内测默认三档）
  state.tier = online ? online.tier : Number(localStorage.getItem('gd_tier') || 3)
  state.props = online ? Object.assign({}, online.props) : tierCounts(state.tier)

  startQuestion()

  // 测试钩子（仅供自动化测试读取内部状态）
  window.__gdDebug = { state, stages, map }

  // 注册清理（路由切换时）
  window.__gdCleanup = () => {
    stopTimer()
    window.removeEventListener('keydown', onKey)
    clearTimeout(toastTimer)
    clearTimeout(championTimer)
    stopCountUps()
    map.dispose()
    window.__gdDebug = null
  }
}
