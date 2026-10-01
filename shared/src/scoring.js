// 模式配置与计分核心
export const MODES = {
  china: {
    key: 'china',
    title: '中国篇',
    timeLimit: 15,      // 每题秒数
    maxDistance: 300,   // 距离上限（公里），超出 0 分
    decayK: 1.7,        // 衰减指数：值越大前段越宽容
    maxScore: 5000
  },
  world: {
    key: 'world',
    title: '世界篇',
    timeLimit: 20,
    maxDistance: 1500,
    decayK: 2.3,
    maxScore: 5000
  }
}

// 地球半径（公里）
const EARTH_R = 6371

/**
 * Haversine 球面距离（公里）
 */
export function haversine(lat1, lng1, lat2, lng2) {
  const rad = Math.PI / 180
  const dLat = (lat2 - lat1) * rad
  const dLng = (lng2 - lng1) * rad
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLng / 2) ** 2
  return 2 * EARTH_R * Math.asin(Math.sqrt(a))
}

/**
 * 得分 = 5000 × (1 − (d/D)^k)，d ≥ D 时为 0
 */
export function score(distance, mode) {
  const { maxDistance: D, decayK: k, maxScore } = mode
  if (distance >= D) return 0
  return Math.round(maxScore * (1 - (distance / D) ** k))
}
