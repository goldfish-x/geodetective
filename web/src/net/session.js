// 会话令牌存放：localStorage。access 过期时用 refresh 轮换。
const K = { access: "gd_access", refresh: "gd_refresh", phone: "gd_phone", nick: "gd_nick" }

export const getSession = () => ({
  access: localStorage.getItem(K.access) || "",
  refresh: localStorage.getItem(K.refresh) || "",
  phone: localStorage.getItem(K.phone) || "",
  nickname: localStorage.getItem(K.nick) || ""
})

export function setSession(s) {
  for (const [k, v] of Object.entries({ [K.access]: s.access, [K.refresh]: s.refresh, [K.phone]: s.phone, [K.nick]: s.nickname }))
    v ? localStorage.setItem(k, v) : localStorage.removeItem(k)
}

export const clearSession = () => setSession({})
