// 契约测试：锁定计分公式与两条赛道（地理版/历史版）关卡结构的对外行为
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  MODES, haversine, score, STAGES, GEO_STAGES, HISTORY_STAGES, STAGE_SIZE,
  DIFFICULTY_LABELS, difficultyLabel, levelsOf, stagesOf, TRACKS, TRACK_KEYS,
  PROPS, TIERS, FREE_TIER, tierCounts, TYPE_LABELS, BUCKET_OF_TYPE, buildQuiz
} from '../src/index.js'

test('haversine 赤道经度 1 度约 111.19 km', () => {
  assert.ok(Math.abs(haversine(0, 0, 0, 1) - 111.195) < 0.05)
})

test('score 边界与衰减（两版共用同一公式）', () => {
  assert.equal(score(0, MODES.china), 5000)
  assert.equal(score(MODES.china.maxDistance, MODES.china), 0)
  assert.equal(score(MODES.china.maxDistance + 1, MODES.china), 0)
  assert.equal(score(150, MODES.china), 3461)
  assert.equal(score(750, MODES.world), 3985)
})

test('地理版：10 局、城市/景点两线、5 难度、门槛沿用合并版原值', () => {
  assert.equal(GEO_STAGES.length, 10)
  assert.equal(STAGE_SIZE, 8)
  assert.deepEqual(GEO_STAGES.map(s => s.difficulty), [1, 1, 2, 2, 3, 3, 4, 4, 5, 5])
  assert.deepEqual(GEO_STAGES.map(s => s.type), ['city', 'scenic', 'city', 'scenic', 'city', 'scenic', 'city', 'scenic', 'city', 'scenic'])
  assert.deepEqual(GEO_STAGES.map(s => s.minScore),
    [6000, 6500, 7500, 8000, 9000, 9500, 10500, 11000, 12000, 12500])
  // STAGES 仍指向地理版，旧引用不破
  assert.equal(STAGES, GEO_STAGES)
})

test('历史版：12 局、单线、6 难度、门槛 5000 起每局 +400', () => {
  assert.equal(HISTORY_STAGES.length, 12)
  assert.deepEqual(HISTORY_STAGES.map(s => s.difficulty), [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6])
  assert.ok(HISTORY_STAGES.every(s => s.type === 'history'))
  assert.deepEqual(HISTORY_STAGES.map(s => s.minScore),
    [5000, 5400, 5800, 6200, 6600, 7000, 7400, 7800, 8200, 8600, 9000, 9400])
  assert.deepEqual(HISTORY_STAGES, stagesOf('history'))
  assert.equal(levelsOf('history'), 6)
  assert.equal(levelsOf('geo'), 5)
})

test('难度名分赛道：地理版 5 级旧称，历史版 6 级史感称', () => {
  assert.deepEqual(Object.keys(DIFFICULTY_LABELS), ['geo', 'history'])
  assert.equal(DIFFICULTY_LABELS.geo.length, 6)
  assert.equal(DIFFICULTY_LABELS.history.length, 7)
  assert.equal(difficultyLabel('geo', 5), '地狱')
  assert.equal(difficultyLabel('history', 6), '绝学')
  assert.equal(difficultyLabel('history', 99), '')
  assert.deepEqual(Object.keys(TYPE_LABELS), ['city', 'scenic', 'history'])
  assert.deepEqual(BUCKET_OF_TYPE, { city: 'cities', scenic: 'scenics', history: 'history' })
  assert.deepEqual(TRACK_KEYS, ['geo', 'history'])
})

test('buildQuiz 按赛道取对应题库且不重复', () => {
  const bank = {
    cities: Array.from({ length: 60 }, (_, i) => ({ name: 'c' + i, difficulty: (i % 5) + 1 })),
    scenics: Array.from({ length: 60 }, (_, i) => ({ name: 's' + i, difficulty: (i % 5) + 1 })),
    // 历史版题库按 6 难度 × 40 题构造（与真实数据规模一致）
    history: Array.from({ length: 240 }, (_, i) => ({ name: 'h' + i, difficulty: (i % 6) + 1 }))
  }
  const geo = buildQuiz(bank, 'geo')
  assert.equal(geo.length, 10)
  assert.ok(geo.every(s => s.questions.length === STAGE_SIZE))
  const geoNames = geo.flatMap(s => s.questions.map(q => q.name))
  assert.equal(new Set(geoNames).size, geoNames.length)
  assert.ok(geoNames.every(n => n[0] !== 'h'))

  const his = buildQuiz(bank, 'history')
  assert.equal(his.length, 12)
  const hisNames = his.flatMap(s => s.questions.map(q => q.name))
  assert.equal(new Set(hisNames).size, hisNames.length)
  assert.ok(hisNames.every(n => n[0] === 'h'))
  // 历史版每难度两局共 16 题，都能从 40 题的池子里抽满
  for (let lv = 1; lv <= 6; lv++) {
    const n = his.filter(s => s.difficulty === lv).flatMap(s => s.questions).filter(q => q.difficulty === lv).length
    assert.equal(n, 16)
  }
  assert.deepEqual(TRACKS.geo.types, ['city', 'scenic'])
  assert.deepEqual(TRACKS.history.types, ['history'])
})

test('道具与档位不变量', () => {
  assert.deepEqual(Object.keys(PROPS), ['time', 'revive', 'redo', 'area'])
  assert.deepEqual(tierCounts(0), { revive: 1, redo: 1, area: 2 })
  assert.equal(tierCounts(0).time, undefined)
  assert.deepEqual(tierCounts(1), {})
  assert.deepEqual(tierCounts(2), { time: 2, revive: 2 })
  assert.deepEqual(tierCounts(3), { time: 3, revive: 2, redo: 1, area: 1 })
  assert.equal(TIERS[4], undefined)
  assert.equal(FREE_TIER, 0)
  assert.equal(TIERS[0].label, '免费版')
})
