// 确定性视觉占位图生成器：用名称做种子，避免所有地点显示同一张远程默认图。
// 当没有可用的图片服务时，返回 DataURL 作为唯一标识。

const PALETTE = [
  ['#3b2f4f', '#8a4b7c'],
  ['#1c3a4e', '#3a6d8c'],
  ['#2b4a3d', '#5a8a6d'],
  ['#4a3b2a', '#8f6d4b'],
  ['#4c2c2c', '#8f4b4b'],
  ['#2a2e4a', '#565a8f'],
]

function hash(str) {
  let h = 0
  for (let i = 0; i < str.length; i++) {
    h = (h << 5) - h + str.charCodeAt(i)
    h |= 0
  }
  return Math.abs(h)
}

function pickColor(name, idx) {
  const colors = PALETTE[hash(name) % PALETTE.length]
  return colors[idx % colors.length]
}

export function placeholderFor(name, width = 120, height = 120) {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) return ''

  const h = hash(name)
  const c1 = pickColor(name, 0)
  const c2 = pickColor(name, 1)

  const grad = ctx.createLinearGradient(0, 0, width, height)
  grad.addColorStop(0, c1)
  grad.addColorStop(1, c2)
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, width, height)

  // 装饰圆
  const cx = width * (0.25 + (h % 100) / 200)
  const cy = height * (0.2 + ((h >> 4) % 100) / 200)
  const r = 20 + (h % 30)
  ctx.beginPath()
  ctx.arc(cx, cy, r, 0, Math.PI * 2)
  ctx.fillStyle = 'rgba(255,255,255,0.12)'
  ctx.fill()

  // 地点首字/首字母
  const char = name.trim().charAt(0)
  ctx.fillStyle = 'rgba(255,255,255,0.92)'
  ctx.font = 'bold 48px "Noto Serif SC", serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.shadowColor = 'rgba(0,0,0,0.35)'
  ctx.shadowBlur = 6
  ctx.shadowOffsetX = 1
  ctx.shadowOffsetY = 1
  ctx.fillText(char, width / 2, height / 2)

  // 底部细线铭牌
  ctx.shadowColor = 'transparent'
  ctx.fillStyle = 'rgba(0,0,0,0.18)'
  ctx.fillRect(0, height - 24, width, 24)
  ctx.fillStyle = 'rgba(255,255,255,0.85)'
  ctx.font = '12px "Noto Serif SC", sans-serif'
  ctx.fillText(name.slice(0, 8), width / 2, height - 9)

  return canvas.toDataURL('image/jpeg', 0.92)
}
