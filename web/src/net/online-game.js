// 在线对局适配器：题目、判分、超时、道具、榜单全部以服务端为准。
// 本地只保留展示状态；服务端下发的题目不含坐标，坐标在判分后才回填用于揭晓。
import { api } from './api.js'

export async function createOnlineGame(modeKey) {
  const cfg = await api('/v1/config')
  const run = await api('/v1/runs', { method: 'POST', body: { mode: modeKey } })
  const stages = cfg.stages.map(s => ({ type: s.type, difficulty: s.difficulty, minScore: s.minScore, questions: [] }))
  stages[0].questions.push({ ...run.question })

  const g = {
    mode: modeKey,
    runId: run.runId,
    stages,
    last: null,
    ord: 0,
    timeLimit: run.timeLimit,
    season: cfg.season,

    async answer(guess, stageIndex) {
      const r = await api(`/v1/runs/${g.runId}/answers`, {
        method: 'POST',
        body: { ord: g.ord, lat: guess ? guess.lat : null, lng: guess ? guess.lng : null }
      })
      g.ord += 1
      g.last = r
      // 揭晓坐标回填到对应题目，供红点、连线与局档案使用
      const st = stages[stageIndex]
      const q = st && st.questions.find(x => x.name === r.reveal.name)
      if (q) { q.lat = r.reveal.lat; q.lng = r.reveal.lng }
      if (r.next) {
        const target = r.nextStage ? stages[r.nextStage - 1] : st
        if (target && !target.questions.some(x => x.name === r.next.name)) target.questions.push({ ...r.next })
      }
      return r
    },

    async prop(key) {
      const r = await api(`/v1/runs/${g.runId}/props/${key}`, { method: 'POST' })
      if (key === 'revive' && r.question) {
        const target = stages[r.nextStage - 1]
        if (target && !target.questions.some(x => x.name === r.question.name)) target.questions.push({ ...r.question })
      }
      if (key === 'redo') g.ord = r.ord
      return r
    },
    finish: () => api(`/v1/runs/${g.runId}/finish`, { method: 'POST' })
  }
  return g
}
