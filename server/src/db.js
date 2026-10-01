// P1 存储：单节点文件型驱动（JSON 快照），接口与未来 Postgres 驱动一致。
// 重启不丢数据；万局/日量级单机足够，换 PG 时只替换本模块的实现。
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

const EMPTY = { users: {}, codes: {}, refresh: {}, runs: {}, answers: {}, boards: {} };

export function openStore(file) {
  let data = structuredClone(EMPTY);
  if (file && existsSync(file)) {
    try {
      data = Object.assign(structuredClone(EMPTY), JSON.parse(readFileSync(file, "utf-8")));
    } catch {
      data = structuredClone(EMPTY);
    }
  }
  const api = {
    data,
    save() {
      if (!file) return;
      mkdirSync(dirname(file), { recursive: true });
      writeFileSync(file, JSON.stringify(data));
    },
    userByPhone(phone) { return data.users[phone] || null; },
    putUser(u) { data.users[u.phone] = u; api.save(); return u; },
    putCode(phone, code, exp) { data.codes[phone] = { code, exp }; api.save(); },
    takeCode(phone) {
      const c = data.codes[phone];
      delete data.codes[phone];
      api.save();
      return c || null;
    },
    putRefresh(id, rec) { data.refresh[id] = rec; api.save(); },
    takeRefresh(id) { const r = data.refresh[id] || null; delete data.refresh[id]; api.save(); return r; },
    putRun(r) { data.runs[r.id] = r; api.save(); return r; },
    run(id) { return data.runs[id] || null; },
    addAnswer(a) { (data.answers[a.runId] = data.answers[a.runId] || []).push(a); api.save(); },
    answers(runId) { return data.answers[runId] || []; },
    boardUpset(mode, season, entry) {
      const key = mode + "/" + season;
      const list = (data.boards[key] = data.boards[key] || []).filter(e => e.phone !== entry.phone);
      list.push(entry);
      list.sort((a, b) => b.score - a.score);
      data.boards[key] = list.slice(0, 500);
      api.save();
      return data.boards[key];
    },
    board(mode, season, limit) {
      return (data.boards[mode + "/" + season] || []).slice(0, limit || 100);
    },
    bestOf(mode, season, phone) {
      return (data.boards[mode + "/" + season] || []).find(e => e.phone === phone) || null;
    }
  };
  return api;
}

export function seasonOf(d) {
  return d.getUTCFullYear() + "-" + String(d.getUTCMonth() + 1).padStart(2, "0");
}
