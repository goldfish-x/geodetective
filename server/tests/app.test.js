import test from "node:test";
import assert from "node:assert/strict";
import { buildApp } from "../src/app.js";
import { MODES, haversine, score } from "@gd/shared";

// 合成题库：每 (桶, 难度) 8 题，坐标互不相同
function bank() {
  const out = { cities: [], scenics: [] };
  for (const bucket of ["cities", "scenics"])
    for (let d = 1; d <= 5; d++)
      for (let i = 0; i < 8; i++)
        out[bucket].push({ name: bucket[0] + d + "-" + i, difficulty: d, hint: "测试区",
          lat: 10 + d * 3 + i * 0.7, lng: 100 + d * 5 + i * 1.3 });
  return out;
}
const BANK = { china: bank(), world: bank() };

function app(clock) {
  return buildApp({ store: undefined, dbFile: null, bankOf: m => BANK[m], secret: "t", smsProvider: "dev", now: clock?.now });
}
async function login(a, phone = "13800000000") {
  const c = await a.inject({ method: "POST", url: "/v1/auth/code", payload: { phone } });
  const dev = JSON.parse(c.payload).devCode;
  const r = await a.inject({ method: "POST", url: "/v1/auth/login", payload: { phone, code: dev, nickname: "测试侦探" } });
  return JSON.parse(r.payload);
}
const H = t => ({ authorization: "Bearer " + t });

test("健康检查与 config 不含坐标", async () => {
  const a = app();
  const h = await a.inject({ method: "GET", url: "/v1/health" });
  assert.equal(JSON.parse(h.payload).ok, true);
  const c = await a.inject({ method: "GET", url: "/v1/config" });
  assert.equal(JSON.stringify(JSON.parse(c.payload)).includes("lat"), false);
});

test("登录：错误验证码被拒，正确验证码发 token", async () => {
  const a = app();
  const bad = await a.inject({ method: "POST", url: "/v1/auth/login", payload: { phone: "13800000000", code: "000000" } });
  assert.equal(bad.statusCode, 401);
  const ok = await login(a);
  assert.ok(ok.access && ok.refresh);
  const me = await a.inject({ method: "GET", url: "/v1/me", headers: H(ok.access) });
  assert.equal(JSON.parse(me.payload).nickname, "测试侦探");
  const noauth = await a.inject({ method: "GET", url: "/v1/me" });
  assert.equal(noauth.statusCode, 401);
});

test("refresh 轮换且旧 token 失效", async () => {
  const a = app();
  const t = await login(a);
  const r1 = await a.inject({ method: "POST", url: "/v1/auth/refresh", payload: { refresh: t.refresh } });
  const n = JSON.parse(r1.payload);
  assert.ok(n.access);
  const r2 = await a.inject({ method: "POST", url: "/v1/auth/refresh", payload: { refresh: t.refresh } });
  assert.equal(r2.statusCode, 401);
});

test("对局全链路：判分与服务端一致、揭晓才给坐标、榜单写入", async () => {
  const a = app();
  const t = await login(a);
  const r = await a.inject({ method: "POST", url: "/v1/runs", headers: H(t.access), payload: { mode: "china" } });
  const run = JSON.parse(r.payload);
  assert.equal(Object.keys(run.question).includes("lat"), false, "题目不得含坐标");
  let token = t.access, rid = run.runId, q = run.question, ord = 0, total = 0;
  for (let i = 0; i < 8; i++) {
    const guess = { lat: 31.2, lng: 121.4 };
    const res = await a.inject({ method: "POST", url: `/v1/runs/${rid}/answers`, headers: H(token),
      payload: Object.assign({ ord }, guess) });
    const b = JSON.parse(res.payload);
    assert.equal(res.statusCode, 200);
    const d = haversine(guess.lat, guess.lng, b.reveal.lat, b.reveal.lng);
    assert.equal(b.points, score(d, MODES.china), "服务端判分必须与 shared 公式一致");
    total += b.points;
    ord++;
    if (b.next) q = b.next;
    if (b.stageSettle) {
      assert.equal(b.stageSettle.index, 1);
      assert.equal(b.runOver, true, "合成题库第 1 局门槛 8000 应未达标而中止");
      break;
    }
  }
  const f = await a.inject({ method: "POST", url: `/v1/runs/${rid}/finish`, headers: H(token) });
  const fb = JSON.parse(f.payload);
  assert.equal(fb.total, total);
  assert.equal(fb.rank, 1);
  const bd = await a.inject({ method: "GET", url: "/v1/boards/china?limit=5" });
  assert.equal(JSON.parse(bd.payload).board[0].nickname, "测试侦探");
});

test("超时由服务端判定：时钟越过时限即 0 分", async () => {
  let T = 1_700_000_000_000;
  const a = app({ now: () => T });
  const t = await login(a, "13900000000");
  const r = JSON.parse((await a.inject({ method: "POST", url: "/v1/runs", headers: H(t.access), payload: { mode: "world" } })).payload);
  T += (MODES.world.timeLimit + 1) * 1000;
  const res = await a.inject({ method: "POST", url: `/v1/runs/${r.runId}/answers`, headers: H(t.access),
    payload: { ord: 0, lat: 48.85, lng: 2.35 } });
  const b = JSON.parse(res.payload);
  assert.equal(b.timedOut, true);
  assert.equal(b.points, 0);
});

test("线索道具每局一次，重放旧题序被拒", async () => {
  const a = app();
  const t = await login(a, "13700000000");
  const r = JSON.parse((await a.inject({ method: "POST", url: "/v1/runs", headers: H(t.access), payload: { mode: "china" } })).payload);
  const p1 = await a.inject({ method: "POST", url: `/v1/runs/${r.runId}/props/hint`, headers: H(t.access) });
  assert.equal(p1.statusCode, 200);
  assert.equal(JSON.parse(p1.payload).hint, "测试区");
  const p2 = await a.inject({ method: "POST", url: `/v1/runs/${r.runId}/props/hint`, headers: H(t.access) });
  assert.equal(p2.statusCode, 409);
  const stale = await a.inject({ method: "POST", url: `/v1/runs/${r.runId}/answers`, headers: H(t.access), payload: { ord: 5, lat: 1, lng: 1 } });
  assert.equal(stale.statusCode, 409);
});

test("他人 run 不可读写", async () => {
  const a = app();
  const t1 = await login(a, "13600000000");
  const t2 = await login(a, "13500000000");
  const r = JSON.parse((await a.inject({ method: "POST", url: "/v1/runs", headers: H(t1.access), payload: { mode: "china" } })).payload);
  const x = await a.inject({ method: "POST", url: `/v1/runs/${r.runId}/answers`, headers: H(t2.access), payload: { ord: 0, lat: 1, lng: 1 } });
  assert.equal(x.statusCode, 404);
});
