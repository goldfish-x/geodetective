// BFF 客户端：统一 fetch、Bearer 注入、401 自动刷新一次。
// 基址优先级：?api= URL 参数 > localStorage.gd_api > 构建期 VITE_API > 同源 /
import { getSession, setSession, clearSession } from "./session.js"

function base() {
  const q = new URLSearchParams(location.search).get("api")
  if (q) { localStorage.setItem("gd_api", q); return q.replace(/\/$/, "") }
  const ls = localStorage.getItem("gd_api")
  if (ls) return ls.replace(/\/$/, "")
  return (import.meta.env.VITE_API || "").replace(/\/$/, "")
}

export const apiBase = base
export const onlineEnabled = () =>
  new URLSearchParams(location.search).has("online") || localStorage.getItem("gd_online") === "1"

async function raw(path, opts = {}) {
  const s = getSession()
  const headers = Object.assign({}, opts.headers || {})
  if (opts.body) headers["content-type"] = "application/json"
  if (s.access && !headers.authorization) headers.authorization = "Bearer " + s.access
  const res = await fetch(base() + path, Object.assign({}, opts, { headers, body: opts.body ? JSON.stringify(opts.body) : undefined }))
  let body = null
  try { body = await res.json() } catch { /* 204 等 */ }
  return { status: res.status, body }
}

export async function api(path, opts = {}) {
  let r = await raw(path, opts)
  if (r.status === 401 && getSession().refresh && !opts.noRetry) {
    const rt = await raw("/v1/auth/refresh", { method: "POST", body: { refresh: getSession().refresh }, noRetry: true })
    if (rt.status === 200) {
      const s = getSession()
      setSession(Object.assign({}, s, { access: rt.body.access, refresh: rt.body.refresh }))
      r = await raw(path, opts)
    } else clearSession()
  }
  if (r.status >= 400) throw Object.assign(new Error((r.body && r.body.error) || ("http_" + r.status)), { status: r.status, body: r.body })
  return r.body
}
