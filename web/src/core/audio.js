// 音效模块：Web Audio 程序化合成，无需音频素材
// 首次用户交互时解锁 AudioContext（浏览器自动播放策略）
let ctx = null
let muted = false

// 恢复静音偏好
try { muted = localStorage.getItem('gd-muted') === '1' } catch { /* ignore */ }

export function isMuted() { return muted }

export function toggleMute() {
  muted = !muted
  try { localStorage.setItem('gd-muted', muted ? '1' : '0') } catch { /* ignore */ }
  return muted
}

function ac() {
  if (muted) return null
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext
    if (!AC) return null
    ctx = new AC()
  }
  if (ctx.state === 'suspended') ctx.resume()
  return ctx
}

/**
 * 单音：oscillator + 包络
 * @param {object} a AudioContext
 * @param {object} o { type, from, to, dur, delay, vol }
 */
function tone(a, { type = 'sine', from, to, dur = 0.15, delay = 0, vol = 0.18 }) {
  const t0 = a.currentTime + delay
  const osc = a.createOscillator()
  const gain = a.createGain()
  osc.type = type
  osc.frequency.setValueAtTime(from, t0)
  if (to && to !== from) osc.frequency.exponentialRampToValueAtTime(to, t0 + dur)
  gain.gain.setValueAtTime(0, t0)
  gain.gain.linearRampToValueAtTime(vol, t0 + 0.012)
  gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)
  osc.connect(gain).connect(a.destination)
  osc.start(t0)
  osc.stop(t0 + dur + 0.02)
}

// —— 事件音效 ——

// 点击地图落点（轻快短音）
export const sfxPick = () => {
  const a = ac(); if (!a) return
  tone(a, { type: 'triangle', from: 660, to: 880, dur: 0.09, vol: 0.12 })
}

// 确认指认（双音上行）
export const sfxConfirm = () => {
  const a = ac(); if (!a) return
  tone(a, { type: 'triangle', from: 523, dur: 0.09, vol: 0.14 })
  tone(a, { type: 'triangle', from: 784, dur: 0.12, delay: 0.09, vol: 0.14 })
}

/**
 * 单题判定：按得分比例播放不同音效
 * @param {number} ratio 得分 / 满分（0~1）
 */
export function sfxJudge(ratio) {
  const a = ac(); if (!a) return
  if (ratio >= 0.8) {
    // 精准：明亮琶音（C-E-G-C）
    ;[523, 659, 784, 1047].forEach((f, i) =>
      tone(a, { type: 'triangle', from: f, dur: 0.14, delay: i * 0.07, vol: 0.15 }))
  } else if (ratio >= 0.4) {
    // 尚可：双音
    tone(a, { type: 'triangle', from: 523, dur: 0.1, vol: 0.14 })
    tone(a, { type: 'triangle', from: 659, dur: 0.14, delay: 0.08, vol: 0.14 })
  } else if (ratio > 0) {
    // 勉强：低音单音
    tone(a, { type: 'sine', from: 330, to: 262, dur: 0.22, vol: 0.14 })
  } else {
    // 失手：下行三连
    ;[392, 311, 262].forEach((f, i) =>
      tone(a, { type: 'sawtooth', from: f, dur: 0.12, delay: i * 0.09, vol: 0.07 }))
  }
}

// 超时（蜂鸣）
export const sfxTimeout = () => {
  const a = ac(); if (!a) return
  tone(a, { type: 'square', from: 440, to: 220, dur: 0.35, vol: 0.1 })
}

// 倒计时告急（最后 3 秒滴答，n = 剩余整秒数）
export const sfxTick = () => {
  const a = ac(); if (!a) return
  tone(a, { type: 'square', from: 990, dur: 0.05, vol: 0.07 })
}

// 使用道具（闪亮上滑音）
export const sfxProp = () => {
  const a = ac(); if (!a) return
  tone(a, { type: 'sine', from: 660, to: 1320, dur: 0.18, vol: 0.13 })
}

// 局过关（小号式胜利音型）
export const sfxStageClear = () => {
  const a = ac(); if (!a) return
  ;[523, 523, 523, 698].forEach((f, i) =>
    tone(a, { type: 'sawtooth', from: f, dur: i === 3 ? 0.3 : 0.1, delay: i * 0.11, vol: 0.08 }))
}

// 局失败 / 游戏中止（下行挽歌）
export const sfxGameOver = () => {
  const a = ac(); if (!a) return
  ;[392, 349, 311, 262].forEach((f, i) =>
    tone(a, { type: 'triangle', from: f, dur: 0.28, delay: i * 0.18, vol: 0.12 }))
}

// 全通关（终章凯歌）
export const sfxVictory = () => {
  const a = ac(); if (!a) return
  ;[523, 659, 784, 1047, 784, 1047].forEach((f, i) =>
    tone(a, { type: 'triangle', from: f, dur: i >= 4 ? 0.35 : 0.13, delay: i * 0.12, vol: 0.13 }))
}

// 独占榜首（登顶庆典：五音上行 + 尾部长音 + 金粉式高音闪烁）
export const sfxChampion = () => {
  const a = ac(); if (!a) return
  ;[523, 659, 784, 1047, 1319].forEach((f, i) =>
    tone(a, { type: 'triangle', from: f, dur: i === 4 ? 0.55 : 0.12, delay: i * 0.1, vol: 0.14 }))
  ;[1568, 2093, 2637].forEach((f, i) =>
    tone(a, { type: 'sine', from: f, dur: 0.09, delay: 0.52 + i * 0.12, vol: 0.07 }))
}
