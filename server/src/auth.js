// 登录：手机号 + 验证码。SMS_PROVIDER=dev 时验证码直接回传（仅开发/内测），
// 生产必须接阿里云短信并删除 dev 分支（见规划 P4 前置条件）。
// JWT 为自实现 HS256，零依赖；secret 必须由环境变量注入。
import { createHmac, randomInt, randomUUID, timingSafeEqual } from "node:crypto";

const b64u = buf => Buffer.from(buf).toString("base64url");
const unb64u = s => Buffer.from(s, "base64url").toString("utf-8");

function sign(payload, secret, ttlSec) {
  const head = b64u(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const now = Math.floor(Date.now() / 1000);
  const body = b64u(JSON.stringify(Object.assign({ iat: now, exp: now + ttlSec }, payload)));
  const sig = createHmac("sha256", secret).update(head + "." + body).digest("base64url");
  return head + "." + body + "." + sig;
}

export function verify(token, secret) {
  const parts = String(token || "").split(".");
  if (parts.length !== 3) return null;
  const want = createHmac("sha256", secret).update(parts[0] + "." + parts[1]).digest("base64url");
  const a = Buffer.from(want), b = Buffer.from(parts[2]);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  let payload;
  try { payload = JSON.parse(unb64u(parts[1])); } catch { return null; }
  if (!payload.exp || payload.exp * 1000 < Date.now()) return null;
  return payload;
}

export const ACCESS_TTL = 2 * 3600;
export const REFRESH_TTL = 30 * 86400;

export function issueTokens(store, user, secret) {
  const access = sign({ sub: user.phone, nick: user.nickname }, secret, ACCESS_TTL);
  const rid = randomUUID();
  store.putRefresh(rid, { phone: user.phone, exp: Date.now() + REFRESH_TTL * 1000 });
  return { access, refresh: rid, ttl: ACCESS_TTL };
}

export function newCode() {
  return String(randomInt(0, 1000000)).padStart(6, "0");
}
