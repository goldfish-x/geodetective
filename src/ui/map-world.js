// 世界篇：ECharts GL 3D 地球（国界着色 + 拖拽旋转 + 点击取经纬度）
import * as echarts from 'echarts'
import 'echarts-gl'
import worldGeo from '../data/world-map.json'

echarts.registerMap('world', worldGeo)

// 复古地图册色板
const PALETTE = [
  '#77875f', '#8a8161', '#6d7f72', '#94825f',
  '#7b8563', '#87795d', '#6e7a68', '#8d8a66'
]

export function createWorldMap(container, { onPick, onInvalidPick }) {
  const chart = echarts.init(container)

  // 离屏 2D 地图作为地球贴图（必须直接初始化在 canvas 元素上）
  const texCanvas = document.createElement('canvas')
  const texChart = echarts.init(texCanvas, null, {
    renderer: 'canvas',
    width: 2048,
    height: 1024
  })

  const countryNames = worldGeo.features
    .map(f => f.properties && f.properties.name)
    .filter(Boolean)

  texChart.setOption({
    backgroundColor: '#0a1120',
    series: [{
      type: 'map',
      map: 'world',
      roam: false,
      // 贴图必须精确铺满 [-180,180]×[-90,90]（等距圆柱），否则球面 UV 与地图错位：
      // 默认布局按数据包围盒（纬度仅 -55.8~83.6）居中缩放，且 aspectScale 默认 0.75 横向压缩，
      // 会导致大陆整体偏移十余个纬度、高经度地区偏差 30° 以上
      aspectScale: 1,
      boundingCoords: [[-180, -90], [180, 90]],
      // 未指定尺寸时布局只占容器 80%（layout.js 默认），必须显式铺满整个画布
      left: 0,
      top: 0,
      width: '100%',
      height: '100%',
      label: { show: false },
      emphasis: { label: { show: false } },
      select: { disabled: true },
      itemStyle: { borderColor: 'rgba(236,225,200,.55)', borderWidth: 0.6 },
      data: countryNames.map((name, i) => ({
        name,
        itemStyle: { areaColor: PALETTE[i % PALETTE.length] }
      }))
    }]
  })

  chart.setOption({
    backgroundColor: 'transparent',
    globe: {
      baseTexture: texChart,
      shading: 'lambert',
      // 高度轴是按「数据里的最大 alt」归一化到 [0, globeOuterRadius - globeRadius] 的
      // （见 echarts-gl globeCreator.js），默认 outerRadius=150 会把连线抬到球面上方 50 个单位
      // ——半个球半径，于是大圆弧看着像一根飞出地球的直线。压到 103 后连线只离地 3 个单位，
      // 既贴着球面又不会和地表 z-fighting。
      globeOuterRadius: 103,
      viewControl: {
        autoRotate: false,
        distance: 180,
        minDistance: 110,
        maxDistance: 320,
        rotateSensitivity: 2,
        zoomSensitivity: 1.5,
        panSensitivity: 0,
        // 初始面对东亚，用 alpha/beta 而不是 targetCoord：
        // echarts-gl 每次 setOption 都会按 model 里的 targetCoord 重设相机
        // （GlobeView._updateViewControl），表现为「一题结束地球自动回位」；
        // 而 alpha/beta 会被拖拽实时回写进 model，所以再 setOption 也不会跳。
        alpha: 30,
        beta: 195
      },
      light: {
        main: { intensity: 1.1, shadow: false },
        ambient: { intensity: 0.55 }
      }
    },
    series: [
      {
        id: 'pick',
        type: 'scatter3D',
        coordinateSystem: 'globe',
        symbol: 'circle',
        symbolSize: 12,
        silent: true,
        itemStyle: { color: '#f2c14e' },
        data: []
      },
      {
        id: 'answer',
        type: 'scatter3D',
        coordinateSystem: 'globe',
        symbol: 'circle',
        symbolSize: 14,
        silent: true,
        itemStyle: { color: '#e05d44' },
        label: { show: false },
        data: []
      },
      {
        id: 'link',
        type: 'lines3D',
        coordinateSystem: 'globe',
        silent: true,
        // polyline 必须为 true：echarts-gl 在 globe 上的 lines3D 会忽略 curveness，
        // 一律用三次贝塞尔拟合，两点夹角一大控制点就被甩到球外（连线翘出球的轮廓）。
        // 折线模式改为直接沿我们算好的大圆插值点走线，严格贴球面。
        polyline: true,
        lineStyle: { width: 4.5, color: '#8fd3ff', opacity: 1 },
        data: []
      },
      {
        // 局结算档案：悬停地名时的红点标记
        id: 'spot',
        type: 'scatter3D',
        coordinateSystem: 'globe',
        symbol: 'circle',
        symbolSize: 12,
        silent: true,
        itemStyle: { color: '#ff5f56' },
        data: []
      }
    ]
  })

  // —— 相机朝向 / 球面角度：用于判断答案是否落在可见半球 ——
  const facing = () => {
    try {
      const vc = chart.getModel().getComponent('globe', 0).get('viewControl') || {}
      return [Number(vc.beta) - 90 || 0, Number(vc.alpha) || 0]   // [lng, lat]
    } catch {
      return [105, 30]
    }
  }
  const toVec = ([lng, lat]) => {
    const a = (90 - lat) * Math.PI / 180, b = lng * Math.PI / 180
    return [Math.sin(a) * Math.cos(b), Math.cos(a), Math.sin(a) * Math.sin(b)]
  }
  const angBetween = (p, q) => {
    const u = toVec(p), v = toVec(q)
    const d = Math.max(-1, Math.min(1, u[0] * v[0] + u[1] * v[1] + u[2] * v[2]))
    return Math.acos(d) * 180 / Math.PI
  }
  const midOf = (p, q) => {
    const u = toVec(p), v = toVec(q)
    const m = [u[0] + v[0], u[1] + v[1], u[2] + v[2]]
    const len = Math.hypot(m[0], m[1], m[2])
    if (len < 1e-6) return p
    const lat = 90 - Math.acos(m[1] / len) * 180 / Math.PI
    const lng = Math.atan2(m[2], m[0]) * 180 / Math.PI
    return [lng, lat]
  }
  // ———— 程序转向（结算时把答案转到正面） ————
  // 必须用 viewControl.targetCoord，不能用 alpha/beta：
  // echarts-gl 每帧都会把相机「当前角度」回写进 model.viewControl.alpha/beta
  // （GlobeView._updateViewControl → control.on('update') → globeChangeCamera action → model.setView），
  // 而且该回写是异步 action。玩家刚拖拽过地球时阻尼惯性仍在持续回写，会把我们用 setOption
  // 下发的新 alpha/beta 立刻覆盖回去，表现为「结算时地球不转」（实测 0/6 全灭）。
  // targetCoord 不参与回写，且在 _updateViewControl 里优先于 alpha/beta，每次重渲染都重新指向目标，
  // 所以收敛稳定。代价：它会留在 option 里成为「回位锚点」，到达后必须摘掉，
  // 否则之后任何一次 setOption 重渲染都会把镜头拉回来（就是「一题结束地球自动回位」）。
  let anchor = null           // 正在进行的程序转向目标 [lng, lat]
  let anchorRaf = 0
  const releaseAnchor = () => {
    if (!anchor) return
    anchor = null
    if (anchorRaf) { cancelAnimationFrame(anchorRaf); anchorRaf = 0 }
    try {
      // echarts 的 merge 会跳过 null，所以只能直接改原始 option 摘锚点
      chart.getModel().getComponent('globe', 0).option.viewControl.targetCoord = null
    } catch { /* 图表已销毁 */ }
  }
  // 下发转向目标，并看守到相机到位后自动摘锚点
  const watchAnchor = () => {
    if (!anchor) return
    const t0 = performance.now()
    const tick = () => {
      if (!anchor) return
      const still = angBetween(facing(), anchor)
      if (still < 1.5 || performance.now() - t0 > 1600) { releaseAnchor(); return }
      anchorRaf = requestAnimationFrame(tick)
    }
    anchorRaf = requestAnimationFrame(tick)
  }
  const turnTo = (lng, lat) => {
    anchor = [lng, lat]
    return { targetCoord: [lng, lat] }   // 作为 globe.viewControl 的一部分随 setOption 一起下发
  }
  // 玩家一上手拖拽就让位，避免程序视角和人手抢镜头
  chart.getZr().on('mousedown', releaseAnchor)
  chart.getZr().on('touchstart', releaseAnchor)
  // 沿大圆做球面线性插值(slerp)，返回 h 高度上的 seg+1 个 [lng, lat, h] 点
  const arcPath = (p, q, h, seg = 48) => {
    const u = toVec(p), v = toVec(q)
    const dot = Math.max(-1, Math.min(1, u[0] * v[0] + u[1] * v[1] + u[2] * v[2]))
    const w = Math.acos(dot)
    if (w < 1e-4) return [[p[0], p[1], h], [q[0], q[1], h]]
    const sw = Math.sin(w)
    const pts = []
    for (let i = 0; i <= seg; i++) {
      const t = i / seg
      const k0 = Math.sin((1 - t) * w) / sw, k1 = Math.sin(t * w) / sw
      const x = u[0] * k0 + v[0] * k1, y = u[1] * k0 + v[1] * k1, z = u[2] * k0 + v[2] * k1
      pts.push([Math.atan2(z, x) * 180 / Math.PI,
                90 - Math.acos(y / Math.hypot(x, y, z)) * 180 / Math.PI, h])
    }
    return pts
  }

  // —— 获取 globe 坐标系（首次渲染后可用） ——
  const getCoordSys = () => {
    try {
      const model = chart.getModel().getComponent('globe', 0)
      return (model && model.coordinateSystem) || null
    } catch {
      return null
    }
  }

  // —— 像素 → 经纬度：相机射线与球体求交，再由球面点反算 ——
  const convertPixel = px => {
    const cs = getCoordSys()
    if (!cs || !cs.viewGL || !cs.viewGL.camera) return null
    const camera = cs.viewGL.camera
    const width = chart.getWidth()
    const height = chart.getHeight()
    if (!width || !height) return null

    const ndcX = (px[0] / width) * 2 - 1
    const ndcY = -((px[1] / height) * 2 - 1)

    let ray
    try {
      // claygl castRay 接收 Vector2（读取 .array），数据向量均存于 .array
      ray = camera.castRay({ array: [ndcX, ndcY] })
    } catch {
      return null
    }
    if (!ray || !ray.origin || !ray.direction) return null

    // 射线与球体（圆心在原点，半径 cs.radius）求交
    const o = ray.origin.array, d = ray.direction.array
    const ox = o[0], oy = o[1], oz = o[2]
    let dx = d[0], dy = d[1], dz = d[2]
    const dLen = Math.hypot(dx, dy, dz)
    if (dLen === 0) return null
    dx /= dLen; dy /= dLen; dz /= dLen

    const R = cs.radius
    const b = ox * dx + oy * dy + oz * dz
    const c = ox * ox + oy * oy + oz * oz - R * R
    const disc = b * b - c
    if (disc < 0) return null  // 未命中球面（点到太空）

    const t = -b - Math.sqrt(disc)
    if (t <= 0) return null

    const point = [ox + t * dx, oy + t * dy, oz + t * dz]
    const data = cs.pointToData(point)
    if (!data || !Number.isFinite(data[0]) || !Number.isFinite(data[1])) return null
    return [data[0], data[1]]
  }

  // —— 点击（与拖拽区分） ——
  let down = null
  const onDown = e => { down = [e.offsetX, e.offsetY] }
  const onUp = e => {
    if (!down) return
    const moved = Math.hypot(e.offsetX - down[0], e.offsetY - down[1])
    down = null
    if (moved > 6) return
    const coords = convertPixel([e.offsetX, e.offsetY])
    if (!coords) { onInvalidPick && onInvalidPick(); return }
    onPick && onPick(coords[0], coords[1])
  }
  chart.getZr().on('mousedown', onDown)
  chart.getZr().on('mouseup', onUp)
  chart.getZr().on('touchstart', onDown)
  chart.getZr().on('touchend', onUp)

  const ro = new ResizeObserver(() => chart.resize())
  ro.observe(container)

  return {
    setPick(lng, lat) {
      chart.setOption({ series: [{ id: 'pick', data: [[lng, lat, 0]] }] })
    },
    clearPick() {
      chart.setOption({ series: [{ id: 'pick', data: [] }] })
    },
    reveal(actual, guess) {
      const series = [{ id: 'answer', data: [[actual.lng, actual.lat, 0]] }]
      const h = 1     // 折线整体抬到球面上方 3 个单位（见 globeOuterRadius：最大 alt 映射为 outerRadius-R）
      if (guess) {
        series.push({
          id: 'link',
          data: [{ coords: arcPath([guess.lng, guess.lat], [actual.lng, actual.lat], h) }]
        })
      }
      // 视角保持不动：只有当答案或落点被转到球背面时才转向，转向目标是两点的球面中点；
      // 两点近乎对跖时中点无意义，直接面向答案。
      // 可见半径 = acos(R / (R + distance)) = acos(100 / 280) ≈ 69.5°，超出即被球身挡住。
      const A = [actual.lng, actual.lat]
      const G = guess ? [guess.lng, guess.lat] : null
      const visible = pt => angBetween(pt, facing()) <= 66
      const opt = { series }
      if (!visible(A) || (G && !visible(G))) {
        const pair = G && angBetween(G, A) < 150 ? midOf(G, A) : A
        opt.globe = { viewControl: turnTo(pair[0], pair[1]) }
      }
      chart.setOption(opt)
      watchAnchor()
    },
    // 供测试读取：相机正对的经纬度 [lng, lat]
    getView() { return facing() },
    highlightRegion() { /* 世界篇提示以文字呈现（原型简化） */ },
    clearHighlight() { /* no-op */ },
    // 局结算档案：显示红点并将镜头转向该地（保证可见），清除红点
    showSpot(lng, lat) {
      chart.setOption({
        series: [{ id: 'spot', data: [[lng, lat, 0]] }],
        globe: { viewControl: turnTo(lng, lat) }
      })
      watchAnchor()
    },
    clearSpot() {
      chart.setOption({ series: [{ id: 'spot', data: [] }] })
    },
    // 清除揭晓标记（答案点与连线）
    clearReveal() {
      chart.setOption({ series: [{ id: 'answer', data: [] }, { id: 'link', data: [] }] })
    },
    resetView() { /* 保持当前视角 */ },
    dispose() {
      releaseAnchor()
      ro.disconnect()
      chart.dispose()
      texChart.dispose()
    }
  }
}
