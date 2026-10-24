// 契约测试：锁定计分公式与关卡结构的对外行为，浏览器与服务端共用同一实现
import test from 'node:test'
import assert from 'node:assert/strict'
import { MODES, haversine, score, STAGES, STAGE_SIZE, DIFFICULTY_LABELS, PROPS, TIERS, tierCounts, TYPE_LABELS, BUCKET_OF_TYPE } from '../src/index.js'

test('haversine 赤道经度 1 度约 111.19 km', () => {
  assert.ok(Math.abs(haversine(0, 0, 0, 1) - 111.195) < 0.05)
})

test('score 边界与衰减', () => {
  assert.equal(score(0, MODES.china), 5000)
  assert.equal(score(MODES.china.maxDistance, MODES.china), 0)
  assert.equal(score(MODES.china.maxDistance + 1, MODES.china), 0)
  assert.equal(score(150, MODES.china), 3461)
  assert.equal(score(750, MODES.world), 3985)
})

test('关卡结构不变量：15 局、三线循环、难度每三局递增', () => {
  assert.equal(STAGES.length, 15)
  assert.equal(STAGE_SIZE, 8)
  assert.deepEqual(STAGES.map(s => s.difficulty), [1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5])
  assert.deepEqual(STAGES.map(s => s.type), [...Array(5).fill(['city', 'scenic', 'history']).flat()])
  assert.deepEqual(STAGES.map(s => s.minScore),
    [6000, 6500, 7000, 7500, 8000, 8500, 9000, 9500, 10000, 10500, 11000, 11500, 12000, 12500, 13000])
  assert.equal(DIFFICULTY_LABELS.length, 6)
  assert.deepEqual(Object.keys(TYPE_LABELS), ['city', 'scenic', 'history'])
  assert.deepEqual(BUCKET_OF_TYPE, { city: 'cities', scenic: 'scenics', history: 'history' })
})

test('道具与档位不变量', () => {
  assert.deepEqual(Object.keys(PROPS), ['time', 'revive', 'redo', 'area'])
  assert.deepEqual(tierCounts(1), {})
  assert.deepEqual(tierCounts(2), { time: 2, revive: 2 })
  assert.deepEqual(tierCounts(3), { time: 3, revive: 2, redo: 1, area: 1 })
  assert.equal(TIERS[4], undefined)
})
