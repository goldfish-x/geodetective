// 坐标只服务于离线玩法；在线对局的坐标由服务端在判分后下发。
// 在线构建（vite build，非 demo/development 模式）时坐标 json 被别名成空对象，坐标不进入产物。
export function loadCoords(mode) {
  return mode === 'china' ? import('../data/china-coords.json') : import('../data/world-coords.json')
}

export function mergeCoords(bank, coords) {
  for (const bucket of ['cities', 'scenics', 'history'])
    for (const it of bank[bucket]) {
      const c = coords[it.name]
      if (c) { it.lat = c[0]; it.lng = c[1]; it.area = c[2] || '' }
    }
  return bank
}
