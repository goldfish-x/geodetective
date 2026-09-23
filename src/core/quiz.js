// 关卡设计：共 10 局，每局 8 题，局内类型与难度相同，逐局递增
// 城市局与景点局交替：1 简单城市 → 2 简单景点 → 3 普通城市 → … → 10 地狱景点
// 每局满分 40000（8 × 5000），minScore 为通关门槛，低于即中止
export const STAGE_SIZE = 8

export const STAGES = [
  { type: 'city',   difficulty: 1, minScore: 8000 },
  { type: 'scenic', difficulty: 1, minScore: 9000 },
  { type: 'city',   difficulty: 2, minScore: 10000 },
  { type: 'scenic', difficulty: 2, minScore: 11000 },
  { type: 'city',   difficulty: 3, minScore: 12000 },
  { type: 'scenic', difficulty: 3, minScore: 13000 },
  { type: 'city',   difficulty: 4, minScore: 14000 },
  { type: 'scenic', difficulty: 4, minScore: 15000 },
  { type: 'city',   difficulty: 5, minScore: 16000 },
  { type: 'scenic', difficulty: 5, minScore: 17000 }
]

// 难度等级名称（用于界面展示）
export const DIFFICULTY_LABELS = ['', '简单', '普通', '进阶', '困难', '地狱']

function pick(list) {
  return list[Math.floor(Math.random() * list.length)]
}

/**
 * 从题库生成整局关卡（10 局 × 8 题，全程不重复）
 * @param {{cities: Array, scenics: Array}} bank 题库
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
    const pool = type === 'city' ? bank.cities : bank.scenics
    const questions = []
    for (let i = 0; i < STAGE_SIZE; i++) {
      questions.push({ ...draw(pool, difficulty), type })
    }
    return { type, difficulty, minScore, questions }
  })
}
