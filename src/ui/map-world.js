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
        // 浅蓝连线：加宽 + 抬到球面上方 2.5 个单位（globeRadius=100），避免贴地时被大地遮挡
        lineStyle: { width: 4.5, color: '#8fd3ff', opacity: 1, curveness: 0.18 },
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
  const faceTo = (lng, lat) => chart.setOption({ globe: { viewControl: { alpha: lat, beta: lng + 90 } } })

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
      const h = 2.5
      if (guess) {
        series.push({
          id: 'link',
          data: [{ coords: [[guess.lng, guess.lat, h], [actual.lng, actual.lat, h]] }]
        })
      }
      chart.setOption({ series })
      // 视角保持不动：只有当答案或落点被转到球背面（离视线中心 >72° 已贴到边缘）时才转向，
      // 转向目标是两点的球面中点；两点近乎对跖时中点无意义，直接面向答案。
      const A = [actual.lng, actual.lat]
      const G = guess ? [guess.lng, guess.lat] : null
      const visible = pt => angBetween(pt, facing()) <= 72
      if (!visible(A) || (G && !visible(G))) {
        const pair = G && angBetween(G, A) < 150 ? midOf(G, A) : A
        faceTo(pair[0], pair[1])
      }
    },
    // 供测试读取：相机正对的经纬度 [lng, lat]
    getView() { return facing() },
    highlightRegion() { /* 世界篇提示以文字呈现（原型简化） */ },
    clearHighlight() { /* no-op */ },
    // 局结算档案：显示红点并将镜头转向该地（保证可见），清除红点
    showSpot(lng, lat) {
      chart.setOption({
        series: [{ id: 'spot', data: [[lng, lat, 0]] }],
        // 同 reveal：用 alpha/beta 转向，不写 targetCoord，避免留下「回位锚点」
        globe: { viewControl: { alpha: lat, beta: lng + 90 } }
      })
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
      ro.disconnect()
      chart.dispose()
      texChart.dispose()
    }
  }
}
