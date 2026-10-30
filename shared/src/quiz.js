// 关卡设计：拆成两条独立赛道（地理版 / 历史版），互不影响
//
// 地理版 geo    ：城市 + 景点两条线，5 个难度 × 每难度 2 局 = 10 局
//                 门槛沿用合并版里城市/景点两局的原始数值（6000 起，按原 15 局序号折算），
//                 保证「跟以前一样」。
// 历史版 history：历史事件单线，6 个难度 × 每难度 2 局 = 12 局
//                 门槛：6000 起、每局 +600（满分 40000/局，约 15% → 31.5%）
//
// 每局 8 题、单题满分 5000、计分公式（scoring.js）两版完全一致。
export const STAGE_SIZE = 8

// 每局满分 = STAGE_SIZE × MODES[*].maxScore = 8 × 5000 = 40000
export const STAGE_MAX = STAGE_SIZE * 5000

// 赛道定义：唯一事实源，前端渲染与服务端判分都读这里
export const TRACKS = {
  geo: {
    key: 'geo',
    label: '地理版',
    sub: '城市 · 景点',
    types: ['city', 'scenic'],
    levels: 5,
    stagesPerLevel: 2,
    minBase: 6000,
    minStep: 500,
    // 地理版沿用合并版（15 局）中城市/景点两线的门槛序号：3*(level-1)+sub
    legacyStride: 3
  },
  history: {
    key: 'history',
    label: '历史版',
    sub: '历史事件',
    types: ['history'],
    levels: 6,
    stagesPerLevel: 2,
    // 历史版门槛：6000 起、每局 +600（12 局 → 6000…12600，占单局满分 15% → 31.5%），
    // 与地理版的 6000…12500（15% → 31.25%）基本对齐
    minBase: 6000,
    minStep: 600,
    legacyStride: 0
  }
}

export const TRACK_KEYS = Object.keys(TRACKS)

/** 生成某条赛道的关卡表 */
export function stageTable(trackKey) {
  const t = TRACKS[trackKey] || TRACKS.geo
  const out = []
  for (let lv = 1; lv <= t.levels; lv++) {
    for (let sub = 0; sub < t.stagesPerLevel; sub++) {
      const i = out.length
      const type = t.types.length > 1 ? t.types[i % t.types.length] : t.types[0]
      const minScore = t.legacyStride
        ? t.minBase + t.minStep * (t.legacyStride * (lv - 1) + sub)
        : t.minBase + t.minStep * i
      out.push({ type, difficulty: lv, minScore })
    }
  }
  return out
}

export const GEO_STAGES = stageTable('geo')
export const HISTORY_STAGES = stageTable('history')

/** @deprecated 兼容旧引用：等同地理版关卡表 */
export const STAGES = GEO_STAGES

export const stagesOf = trackKey => (trackKey === 'history' ? HISTORY_STAGES : GEO_STAGES)

// 三条线的中文名（徽章、局档案标题、终局进度点共用）
export const TYPE_LABELS = { city: '城市', scenic: '景点', history: '历史' }

// 难度等级名称：地理版 5 级沿用旧称；历史版 6 级用一套更有史感的叫法
export const DIFFICULTY_LABELS = {
  geo: ['', '简单', '普通', '进阶', '困难', '地狱'],
  history: ['', '初识', '通晓', '博览', '考据', '钩沉', '绝学']
}

/** 取某赛道的难度名（越界返回空串） */
export function difficultyLabel(trackKey, lv) {
  const arr = DIFFICULTY_LABELS[trackKey] || DIFFICULTY_LABELS.geo
  return arr[lv] || ''
}

export const levelsOf = trackKey => (TRACKS[trackKey] || TRACKS.geo).levels

// 题库桶名与关卡类型的对应关系
export const BUCKET_OF_TYPE = { city: 'cities', scenic: 'scenics', history: 'history' }

function pick(list) {
  return list[Math.floor(Math.random() * list.length)]
}

/**
 * 从题库生成整局关卡（全程不重复）
 * @param {{cities?: Array, scenics?: Array, history?: Array}} bank 题库
 * @param {'geo'|'history'} [trackKey='geo'] 赛道
 * @returns {Array} 关卡数组，每项 { type, difficulty, minScore, questions }
 */
export function buildQuiz(bank, trackKey = 'geo') {
  const used = new Set()

  const draw = (pool, difficulty) => {
    const candidates = pool.filter(q => q.difficulty === difficulty && !used.has(q.name))
    if (candidates.length === 0) {
      const fallback = pool.filter(q => !used.has(q.name))
      const item = fallback.length > 0 ? pick(fallback) : pick(pool)
      used.add(item.name)
      return item
    }
    const item = pick(candidates)
    used.add(item.name)
    return item
  }

  return stageTable(trackKey).map(({ type, difficulty, minScore }) => {
    const pool = bank[BUCKET_OF_TYPE[type]] || []
    const questions = []
    for (let i = 0; i < STAGE_SIZE; i++) {
      questions.push({ ...draw(pool, difficulty), type })
    }
    return { type, difficulty, minScore, questions }
  })
}
