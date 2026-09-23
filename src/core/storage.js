// 本地存档：昵称 + 各模式历史最高 10 次得分（localStorage）
const KEY_NICKNAME = 'gd_nickname'
const KEY_BOARD = 'gd_leaderboard'

export function getNickname() {
  return localStorage.getItem(KEY_NICKNAME) || ''
}

export function setNickname(name) {
  localStorage.setItem(KEY_NICKNAME, name.trim())
}

function loadBoard() {
  try {
    return JSON.parse(localStorage.getItem(KEY_BOARD)) || {}
  } catch {
    return {}
  }
}

/**
 * 获取某模式 Top 10（分数降序）
 * @returns {Array<{score:number, date:string}>}
 */
export function getTop10(mode) {
  const board = loadBoard()
  return (board[mode] || []).slice().sort((a, b) => b.score - a.score).slice(0, 10)
}

/**
 * 记录一局得分，返回是否进入 Top 10 及排名（1 起）
 * @returns {{rank:number}|null} 未上榜返回 null
 */
export function addScore(mode, scoreVal) {
  const board = loadBoard()
  const list = board[mode] || []
  const d = new Date()
  const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const entry = { score: scoreVal, date }
  list.push(entry)
  list.sort((a, b) => b.score - a.score)
  board[mode] = list.slice(0, 10)
  localStorage.setItem(KEY_BOARD, JSON.stringify(board))
  const rank = board[mode].indexOf(entry)
  return rank >= 0 ? { rank: rank + 1 } : null
}
