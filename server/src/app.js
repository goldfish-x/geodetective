// BFF 骨架（P0）：只暴露健康检查与共享配置，证明服务端能复用 @gd/shared。
// P1 起在此挂 auth / runs / answers / boards / economy 五组路由。
import Fastify from 'fastify'
import { MODES, STAGES, STAGE_SIZE } from '@gd/shared'

export function buildApp(opts = {}) {
  const app = Fastify(opts)

  app.get('/v1/health', async () => ({ ok: true, service: 'geo-detective-api', version: '0.3.0' }))

  // 不含任何坐标：模式参数与关卡门槛是公开规则，坐标必须留在服务端题库（见规划第 1 节）
  app.get('/v1/config', async () => ({
    modes: Object.fromEntries(Object.entries(MODES).map(([k, m]) =>
      [k, { title: m.title, timeLimit: m.timeLimit, maxDistance: m.maxDistance, maxScore: m.maxScore }])),
    stages: STAGES.map(s => ({ type: s.type, difficulty: s.difficulty, minScore: s.minScore })),
    stageSize: STAGE_SIZE
  }))

  return app
}
