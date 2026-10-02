// BFF（P1）：登录 / 服务端权威对局 / 全网榜。
// 坐标只存在于服务端题库；下发给浏览器的题目不含 lat/lng，揭晓坐标在判分后才回传。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";
import Fastify from "fastify";
import cors from "@fastify/cors";
import { MODES, haversine, score, buildQuiz, STAGES, STAGE_SIZE, PROPS, TIERS, tierCounts } from "@gd/shared";
import { openStore, seasonOf } from "./db.js";
import { verify, issueTokens, newCode, REFRESH_TTL } from "./auth.js";

const HERE = fileURLToPath(new URL(".", import.meta.url));

export function loadBank(mode) {
  // meta 与坐标分文件存放：坐标只在服务端合并使用，永不下发给浏览器
  const meta = JSON.parse(readFileSync(HERE + "../../web/src/data/" + mode + ".json", "utf-8"));
  const coords = JSON.parse(readFileSync(HERE + "../../web/src/data/" + mode + "-coords.json", "utf-8"));
  for (const bucket of ["cities", "scenics"])
    for (const it of meta[bucket]) {
      const c = coords[it.name];
      if (c) { it.lat = c[0]; it.lng = c[1]; it.area = c[2] || ""; }
    }
  return meta;
}

// 下发题目：只含展示与判级所需字段，绝不含坐标
const pubQ = q => ({ name: q.name, difficulty: q.difficulty, type: q.type });

export function buildApp(opts = {}) {
  const secret = opts.secret || process.env.GD_JWT_SECRET || "dev-secret-change-me";
  const sms = opts.smsProvider || process.env.SMS_PROVIDER || "dev";
  const store = opts.store || openStore(opts.dbFile || null);
  const bankOf = opts.bankOf || loadBank;
  const now = opts.now || (() => Date.now());

  const app = Fastify(opts.fastify || {});

  // 开发期浏览器从 Vite 端口跨域调用；生产为同源部署，此配置无副作用
  app.register(cors, { origin: true, maxAge: 600 })

  app.addHook("onRequest", async req => {
    const t = (req.headers.authorization || "").replace(/^Bearer\s+/i, "");
    req.user = t ? verify(t, secret) : null;
  });
  const needAuth = async (req, rep) => {
    if (!req.user) return rep.code(401).send({ error: "unauthorized" });
    return null;
  };

  app.get("/v1/health", async () => ({ ok: true, service: "geo-detective-api", version: "0.3.0" }));
  app.get("/v1/config", async () => ({
    modes: Object.fromEntries(Object.entries(MODES).map(([k, m]) =>
      [k, { title: m.title, timeLimit: m.timeLimit, maxDistance: m.maxDistance, maxScore: m.maxScore }])),
    stages: STAGES.map(s => ({ type: s.type, difficulty: s.difficulty, minScore: s.minScore })),
    stageSize: STAGE_SIZE,
    season: seasonOf(new Date(now())),
    props: PROPS,
    tiers: TIERS
  }));

  // —— 登录 ——
  app.post("/v1/auth/code", async (req, rep) => {
    const phone = String(req.body?.phone || "").trim();
    if (!/^1\d{10}$/.test(phone)) return rep.code(400).send({ error: "bad_phone" });
    const code = newCode();
    store.putCode(phone, code, now() + 5 * 60 * 1000);
    if (sms === "dev") return { ok: true, devCode: code };
    return rep.code(501).send({ error: "sms_provider_not_configured" });
  });

  app.post("/v1/auth/login", async (req, rep) => {
    const { phone, code, nickname } = req.body || {};
    const rec = store.takeCode(String(phone || ""));
    if (!rec || rec.exp < now() || rec.code !== String(code || ""))
      return rep.code(401).send({ error: "bad_code" });
    let user = store.userByPhone(phone) ||
      store.putUser({ phone, nickname: String(nickname || "").slice(0, 12) || "无名侦探", createdAt: now() });
    if (nickname) { user.nickname = String(nickname).slice(0, 12); store.putUser(user); }
    return Object.assign({ user: { phone: phone.slice(0, 3) + "****" + phone.slice(7), nickname: user.nickname } },
      issueTokens(store, user, secret));
  });

  app.post("/v1/auth/refresh", async (req, rep) => {
    const rec = store.takeRefresh(String(req.body?.refresh || ""));
    if (!rec || rec.exp < now()) return rep.code(401).send({ error: "bad_refresh" });
    const user = store.userByPhone(rec.phone);
    return issueTokens(store, user, secret);
  });

  app.get("/v1/me", async (req, rep) => {
    if (await needAuth(req, rep)) return;
    const season = seasonOf(new Date(now()));
    const user = store.userByPhone(req.user.sub);
    const best = {};
    for (const m of Object.keys(MODES)) {
      const e = store.bestOf(m, season, req.user.sub);
      best[m] = e ? { score: e.score, rank: store.board(m, season, 500).findIndex(x => x.phone === req.user.sub) + 1 } : null;
    }
    return { phone: req.user.sub.slice(0, 3) + "****" + req.user.sub.slice(7), nickname: user?.nickname || req.user.nick, season, best };
  });

  // —— 对局 ——
  app.post("/v1/runs", async (req, rep) => {
    if (await needAuth(req, rep)) return;
    const mode = req.body?.mode;
    if (!MODES[mode]) return rep.code(400).send({ error: "bad_mode" });
    const stages = buildQuiz(bankOf(mode));
    const tier = [1, 2, 3].includes(Number(req.body?.tier)) ? Number(req.body.tier) : 3;
    const run = {
      id: randomUUID(), phone: req.user.sub, mode, stages, tier,
      s: 0, q: 0, stageScore: 0, total: 0, props: tierCounts(tier),
      revived: [], awaitRevive: false,
      issuedAt: now(), over: false, createdAt: now()
    };
    store.putRun(run);
    return { runId: run.id, mode, stage: 1, tier: run.tier, props: Object.assign({}, run.props),
             question: pubQ(stages[0].questions[0]), timeLimit: MODES[mode].timeLimit };
  });

  const cur = run => run.stages[run.s].questions[run.q];

  const useProp = (run, key) => {
    if (!run.props[key]) return false;
    run.props[key] -= 1;
    return true;
  };

  app.post("/v1/runs/:id/props/time", async (req, rep) => {
    if (await needAuth(req, rep)) return;
    const run = store.run(req.params.id);
    if (!run || run.phone !== req.user.sub || run.over) return rep.code(404).send({ error: "no_run" });
    if (!useProp(run, "time")) return rep.code(409).send({ error: "prop_exhausted" });
    run.issuedAt += 12000;
    store.putRun(run);
    return { add: 12, left: run.props.time };
  });

  app.post("/v1/runs/:id/props/area", async (req, rep) => {
    if (await needAuth(req, rep)) return;
    const run = store.run(req.params.id);
    if (!run || run.phone !== req.user.sub || run.over) return rep.code(404).send({ error: "no_run" });
    if (!useProp(run, "area")) return rep.code(409).send({ error: "prop_exhausted" });
    const q = cur(run);
    store.putRun(run);
    return { area: q.area || "", hint: q.hint, left: run.props.area };
  });

  app.post("/v1/runs/:id/props/redo", async (req, rep) => {
    if (await needAuth(req, rep)) return;
    const run = store.run(req.params.id);
    if (!run || run.phone !== req.user.sub || run.over) return rep.code(404).send({ error: "no_run" });
    if (run.q < 1) return rep.code(409).send({ error: "nothing_to_redo" });
    if (!useProp(run, "redo")) return rep.code(409).send({ error: "prop_exhausted" });
    const n = Math.min(2, run.q);
    const from = run.s * STAGE_SIZE + run.q - n;
    for (const a of store.answers(run.id).filter(a => a.ord >= from)) {
      run.total -= a.pts;
      run.stageScore -= a.pts;
    }
    store.data.answers[run.id] = store.answers(run.id).filter(a => a.ord < from);
    run.q -= n;
    run.issuedAt = now();
    store.putRun(run);
    store.save();
    return { rewound: n, ord: run.s * STAGE_SIZE + run.q, question: pubQ(cur(run)), left: run.props.redo };
  });

  app.post("/v1/runs/:id/props/revive", async (req, rep) => {
    if (await needAuth(req, rep)) return;
    const run = store.run(req.params.id);
    if (!run || run.phone !== req.user.sub) return rep.code(404).send({ error: "no_run" });
    if (!run.awaitRevive) return rep.code(409).send({ error: "not_dead" });
    if (run.s + 1 >= run.stages.length) return rep.code(409).send({ error: "last_stage" });
    if (!useProp(run, "revive")) return rep.code(409).send({ error: "prop_exhausted" });
    run.revived.push(run.s + 1);
    run.awaitRevive = false;
    run.over = false;
    run.s += 1; run.q = 0; run.stageScore = 0;
    run.issuedAt = now();
    store.putRun(run);
    return { revived: run.revived.slice(), nextStage: run.s + 1, question: pubQ(cur(run)), left: run.props.revive };
  });

  app.post("/v1/runs/:id/answers", async (req, rep) => {
    if (await needAuth(req, rep)) return;
    const run = store.run(req.params.id);
    if (!run || run.phone !== req.user.sub || run.over) return rep.code(404).send({ error: "no_run" });
    const ord = Number(req.body?.ord);
    if (ord !== run.s * STAGE_SIZE + run.q) return rep.code(409).send({ error: "stale_answer" });
    const q = cur(run);
    const mode = MODES[run.mode];
    const elapsed = (now() - run.issuedAt) / 1000;
    const timedOut = elapsed > mode.timeLimit;
    const lat = Number(req.body?.lat), lng = Number(req.body?.lng);
    const bad = !Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180;
    const dist = timedOut || bad ? null : haversine(lat, lng, q.lat, q.lng);
    const pts = dist == null ? 0 : score(dist, mode);
    run.total += pts;
    run.stageScore += pts;
    store.addAnswer({ runId: run.id, ord, name: q.name, lat, lng, dist, pts, timedOut, at: now() });

    const stage = run.stages[run.s];
    const lastQ = run.q + 1 >= STAGE_SIZE;
    const lastStage = run.s + 1 >= run.stages.length;
    const out = {
      ord, points: pts, distanceKm: dist == null ? null : Math.round(dist), timedOut,
      reveal: { name: q.name, lat: q.lat, lng: q.lng },
      stage: { index: run.s + 1, score: run.stageScore, minScore: stage.minScore }
    };
    if (!lastQ) {
      run.q += 1;
      run.issuedAt = now();
      store.putRun(run);
      out.next = pubQ(cur(run));
      return out;
    }
    const passed = run.stageScore >= stage.minScore;
    out.stageSettle = { index: run.s + 1, passed, score: run.stageScore, minScore: stage.minScore };
    if (!passed || lastStage) {
      run.over = true;
      run.awaitRevive = !passed && !lastStage && run.props.revive > 0;
      out.canRevive = run.awaitRevive;
      store.putRun(run);
      out.runOver = true;
      return out;
    }
    run.s += 1; run.q = 0; run.stageScore = 0; run.issuedAt = now();
    store.putRun(run);
    out.nextStage = run.s + 1;
    out.next = pubQ(cur(run));
    return out;
  });

  app.post("/v1/runs/:id/finish", async (req, rep) => {
    if (await needAuth(req, rep)) return;
    const run = store.run(req.params.id);
    if (!run || run.phone !== req.user.sub) return rep.code(404).send({ error: "no_run" });
    run.over = true;
    store.putRun(run);
    const season = seasonOf(new Date(now()));
    const user = store.userByPhone(run.phone);
    const prev = store.bestOf(run.mode, season, run.phone);
    if (!prev || run.total > prev.score)
      store.boardUpset(run.mode, season, { phone: run.phone, nickname: user?.nickname || "无名侦探", score: run.total, date: new Date(now()).toISOString().slice(0, 10) });
    const board = store.board(run.mode, season, 10);
    const rank = board.findIndex(e => e.phone === run.phone) + 1;
    return { total: run.total, season, rank: rank || null, revived: run.revived.slice(),
             board: board.map((e, i) => ({ rank: i + 1, nickname: e.nickname, score: e.score, date: e.date })) };
  });

  app.get("/v1/boards/:mode", async (req, rep) => {
    const mode = req.params.mode;
    if (!MODES[mode]) return rep.code(404).send({ error: "bad_mode" });
    const season = req.query.season || seasonOf(new Date(now()));
    const limit = Math.min(100, Math.max(1, Number(req.query.limit) || 20));
    return { season, board: store.board(mode, season, limit)
      .map((e, i) => ({ rank: i + 1, nickname: e.nickname, score: e.score, date: e.date })) };
  });

  return app;
}
