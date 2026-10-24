// 关卡设计：共 15 局，每局 8 题；三条线（城市 → 景点 → 历史事件）循环，难度每三局抬一档
// 1 城市·简单 → 2 景点·简单 → 3 历史·简单 → 4 城市·普通 → … → 15 历史·地狱
// 每局满分 40000（8 × 5000），minScore 为通关门槛，低于即中止；
// 局数由 10 增到 15 时把每局门槛涨幅从 1000 降到 500，避免总局数变多后通关难度陡增
export const STAGE_SIZE = 8

const MIN_BASE = 6000
const MIN_STEP = 500

export const STAGES = Array.from({ length: 15 }, (_, i) => ({
  type: ['city', 'scenic', 'history'][i % 3],
  difficulty: Math.floor(i / 3) + 1,
  minScore: MIN_BASE + MIN_STEP * i
}))

// 三条线的中文名（徽章、局档案标题、终局进度点共用）
export const TYPE_LABELS = { city: '城市', scenic: '景点', history: '历史' }

// 难度等级名称（用于界面展示）
export const DIFFICULTY_LABELS = ['', '简单', '普通', '进阶', '困难', '地狱']

// 题库桶名与关卡类型的对应关系
export const BUCKET_OF_TYPE = { city: 'cities', scenic: 'scenics', history: 'history' }

function pick(list) {
  return list[Math.floor(Math.random() * list.length)]
}

/**
 * 从题库生成整局关卡（15 局 × 8 题，全程不重复）
 * @param {{cities: Array, scenics: Array, history: Array}} bank 题库
 * @returns {Array} 关卡数组，每项 { type, difficulty, minScore, questions }
 */
export function buildQuiz(bank) {
  const used = new Set()

  const draw = (pool, difficulty) => {
    const candidates = pool.filter(q => q.difficulty === difficulty && !used.has(q.name))
    if (candidates.length === 0) {
      // 该难度已抽干，退化为任意未使用题目
      const fallback = pool.filter(q => !used.has(q.name))
      const item = fallback.length > 0 ? pick(fallback) : pick(pool)
      used.add(item.name)
      return item
    }
    const item = pick(candidates)
    used.add(item.name)
    return item
  }

  return STAGES.map(({ type, difficulty, minScore }) => {
    const pool = bank[BUCKET_OF_TYPE[type]]
    const questions = []
    for (let i = 0; i < STAGE_SIZE; i++) {
      questions.push({ ...draw(pool, difficulty), type })
    }
    return { type, difficulty, minScore, questions }
  })
}
