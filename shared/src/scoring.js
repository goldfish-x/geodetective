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

// 赛道级参数补丁：只覆盖个别 (赛道, 篇章) 组合，其余一律沿用 MODES 原值。
//
// 历史版·世界篇要单独收紧：历史事件在地理上高度聚集（欧洲尤其密集），
// 沿用地理版 1500 km / k=2.3 的曲线时，随便点一座欧洲城市、误差 700 km 也能拿 4000+，
// 等于不认地方也能过关。把衰减指数从 2.3 收到 1.25 后：
//   4000 分所需误差 约 745 km（原 k=2.3）→ 约 415 km（k=1.25）→ 约 350 km（k=1.1）
//   750 km 处        约 3985 分 → 2898 分 → 2667 分
//   1000 km 处       约 3032 分 → 1988 分 → 1799 分
// 中国篇（300 km 容差本来就紧）与整个地理版完全不动。
export const TRACK_MODE_OVERRIDES = {
  history: {
    world: { decayK: 1.1 }
  }
}

/** 取某赛道某篇章的实际计分参数（含赛道级覆盖） */
export function modeOf(trackKey, modeKey) {
  const base = MODES[modeKey]
  if (!base) return base
  const ov = (TRACK_MODE_OVERRIDES[trackKey] || {})[modeKey]
  return ov ? { ...base, ...ov } : base
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
