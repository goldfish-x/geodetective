// 游戏页：出题 → 作答 → 单题结算 → 局结算（最低分门槛） → 终局结算
import { MODES, haversine, score } from '../core/scoring.js'
import { buildQuiz, STAGE_SIZE, STAGES, DIFFICULTY_LABELS } from '../core/quiz.js'
import { getNickname, addScore } from '../core/storage.js'
import {
  isMuted, toggleMute, sfxPick, sfxConfirm, sfxJudge, sfxTimeout,
  sfxTick, sfxProp, sfxStageClear, sfxGameOver, sfxVictory
} from '../core/audio.js'

const ICON_SND_ON = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5L6 9H3v6h3l5 4V5z" fill="currentColor" stroke="none"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.5 6a9 9 0 0 1 0 12"/></svg>`
const ICON_SND_OFF = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5L6 9H3v6h3l5 4V5z" fill="currentColor" stroke="none"/><path d="M16 9l6 6M22 9l-6 6"/></svg>`

const ICON_CLOCK = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>`
const ICON_COMPASS = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z" fill="currentColor" stroke="none"/></svg>`

const fmt = n => n.toLocaleString('zh-CN')
const pad2 = n => String(n).padStart(2, '0')

// 地名简介与配图：优先加载 public/images 中的真实图片；
// 没有本地图片的地点回退到确定性视觉占位图，避免远程服务不可用时出现空白。
import { placeholderFor } from '../core/placeholder.js'
const imgURL = (name, modeKey, availableImages) => {
  if (availableImages.has(name)) {
    return `${import.meta.env.BASE_URL}images/${modeKey}/${encodeURIComponent(name)}.jpg`
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
  const stages = buildQuiz(bank)

  const state = {
    stageIndex: 0,      // 当前局（0 起）
    qInStage: 0,        // 局内题目序号（0 起）
    total: 0,           // 总分
    stageScore: 0,      // 当前局得分
    records: [],
    guess: null,
    phase: 'answering', // answering | settle | done
    props: { time: true, hint: true },
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

    <div class="map-wrap">
      <div class="map-holder" id="map-holder"></div>

      <div class="confirm-pop hidden" id="confirm-pop">
        <span class="confirm-text">就是这里？</span>
        <button class="btn btn-ghost" id="btn-rechoose">重选</button>
        <button class="btn btn-primary" id="btn-confirm">确认指认</button>
      </div>

      <div class="settle-pop hidden" id="settle-pop">
        <div class="settle-title" id="settle-title"></div>
        <div class="settle-meter" aria-hidden="true"><i id="settle-meter-fill"></i></div>
        <div class="settle-detail" id="settle-detail"></div>
        <button class="btn btn-primary" id="btn-next">下一题</button>
      </div>

      <div class="toast hidden" id="toast"></div>
    </div>

    <footer class="game-bottom">
      <div class="props">
        <button class="prop" id="prop-time" title="当前题加时 10 秒">${ICON_CLOCK}<span>加时 +10s</span></button>
        <button class="prop" id="prop-hint" title="提示大致方位">${ICON_COMPASS}<span>线索</span></button>
      </div>
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

  // ————— 流程 —————
  function startQuestion() {
    state.phase = 'answering'
    state.guess = null
    state.timerTotal = mode.timeLimit
    state.timerRemain = mode.timeLimit
    state.lastTickSec = 99
    map.clearPick()
    map.clearHighlight()
    elHint.classList.add('hidden')
    elConfirm.classList.add('hidden')
    elSettle.classList.add('hidden')

    const stage = stages[state.stageIndex]
    const q = stage.questions[state.qInStage]

    // 新一局：重置道具与本局计分
    if (state.qInStage === 0) {
      state.props = { time: true, hint: true }
      $('prop-time').classList.remove('used')
      $('prop-hint').classList.remove('used')
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

  function settle(timedOut) {
    state.phase = 'settle'
    elConfirm.classList.add('hidden')

    const q = stages[state.stageIndex].questions[state.qInStage]
    let dist = null, pts = 0
    if (state.guess) {
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

    // 2.5 秒后自动进入下一题
    state.autoNext = setTimeout(next, 2500)
  }

  function next() {
    clearTimeout(state.autoNext)
    if (state.phase === 'done' || state.phase === 'stageSettle') return
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
    elSettle.classList.add('hidden')
    elConfirm.classList.add('hidden')
    elHint.classList.add('hidden')
    map.clearPick()
    map.clearHighlight()
    map.clearReveal()

    const stage = stages[state.stageIndex]
    const passed = state.stageScore >= stage.minScore
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
        <button class="btn btn-primary" id="btn-stage-next">${passed ? (isLast ? '查看最终结算' : `进入第${state.stageIndex + 2}局`) : '结束本局任务'}</button>
      </div>`
    elMap.parentElement.appendChild(panel)

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

  $('btn-next').addEventListener('click', next)

  // ————— 道具 —————
  $('prop-time').addEventListener('click', () => {
    if (!state.props.time || state.phase !== 'answering') return
    state.props.time = false
    $('prop-time').classList.add('used')
    state.timerTotal += 10
    state.timerRemain += 10
    state.lastTickSec = 99
    startTimer()
    sfxProp()
    showToast('已加时 10 秒')
  })

  $('prop-hint').addEventListener('click', () => {
    if (!state.props.hint || state.phase !== 'answering') return
    state.props.hint = false
    $('prop-hint').classList.add('used')
    sfxProp()
    const q = stages[state.stageIndex].questions[state.qInStage]
    const label = modeKey === 'china' ? '大致方位' : '所在大洲'
    elHint.innerHTML = `<b>${label}</b>：${q.hint}`
    elHint.classList.remove('hidden')
    map.highlightRegion(q.hint)
  })

  // ————— 终局 —————
  function endGame(victory) {
    state.phase = 'done'
    stopTimer()
    map.dispose()
    if (victory) sfxVictory()
    else sfxGameOver()

    const nickname = getNickname() || '无名侦探'
    const rankInfo = addScore(modeKey, state.total)
    const reached = Math.min(state.stageIndex + 1, STAGES.length)

    app.innerHTML = `
    <div class="result-page">
      <div class="result-card">
        <div class="result-stamp">${victory ? '完美结案' : '任务中止'}</div>
        <p class="result-sub">${nickname} · ${mode.title} · ${victory ? '十局全部通关' : `止步第${reached}局`}</p>
        <div class="result-score"><em>${fmt(state.total)}</em><span>总分</span></div>
        ${rankInfo ? `<div class="result-rank">进入个人榜单 · 第 ${rankInfo.rank} 名</div>` : '<div class="result-rank dim">未能进入个人 Top 10</div>'}
        <div class="result-stagebar">
          ${STAGES.map((s, i) => {
            const cleared = victory || i < state.stageIndex
            return `<span class="stage-dot${cleared ? ' cleared' : ''}" title="第${i + 1}局 · ${DIFFICULTY_LABELS[s.difficulty]}${s.type === 'city' ? '城市' : '景点'} · 门槛 ${fmt(s.minScore)}">${i + 1}</span>`
          }).join('<i class="stage-sep"></i>')}
        </div>
        <ol class="result-list">
          ${state.records.map(r => `
            <li>
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
    </div>`

    app.querySelector('#btn-again').addEventListener('click', () => {
      location.hash = '#/game/' + modeKey
      if (location.hash === '#/game/' + modeKey) window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
    app.querySelector('#btn-home').addEventListener('click', () => { location.hash = '#/' })

    // 终局总分滚动 + 印章盖戳动画
    countUp(app.querySelector('.result-score em'), 0, state.total, 1200)
  }

  $('btn-back').addEventListener('click', () => { location.hash = '#/' })

  let toastTimer = 0
  function showToast(msg) {
    elToast.textContent = msg
    elToast.classList.remove('hidden')
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => elToast.classList.add('hidden'), 1600)
  }

  startQuestion()

  // 测试钩子（仅供自动化测试读取内部状态）
  window.__gdDebug = { state, stages }

  // 注册清理（路由切换时）
  window.__gdCleanup = () => {
    stopTimer()
    clearTimeout(state.autoNext)
    clearTimeout(toastTimer)
    stopCountUps()
    map.dispose()
    window.__gdDebug = null
  }
}
