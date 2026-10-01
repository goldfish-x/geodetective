import test from 'node:test'
import assert from 'node:assert/strict'
import { buildApp } from '../src/app.js'

test('GET /v1/health 返回 ok', async () => {
  const app = buildApp()
  const res = await app.inject({ method: 'GET', url: '/v1/health' })
  assert.equal(res.statusCode, 200)
  assert.equal(res.json().ok, true)
})

test('GET /v1/config 下发规则且不含坐标', async () => {
  const app = buildApp()
  const res = await app.inject({ method: 'GET', url: '/v1/config' })
  const body = res.json()
  assert.equal(res.statusCode, 200)
  assert.equal(body.stages.length, 10)
  assert.equal(body.stageSize, 8)
  assert.equal(body.modes.china.maxDistance, 300)
  assert.equal(JSON.stringify(body).includes('lat'), false, 'config 不得泄漏坐标字段')
})
