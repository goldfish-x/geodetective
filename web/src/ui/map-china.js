// 中国篇：ECharts 2D 地图（省级区划 + 着色 + 缩放平移 + 点击取经纬度）
import * as echarts from 'echarts'
import chinaGeo from '../data/china-map.json'

echarts.registerMap('china', chinaGeo)

// 复古地图册色板（哑光大地色系）
const PALETTE = [
  '#77875f', '#8a8161', '#6d7f72', '#94825f',
  '#7b8563', '#87795d', '#6e7a68', '#8d8a66'
]

// 方位 → 省级行政区（名称与 GeoJSON properties.name 对应）
export const REGION_PROVINCES = {
  '华北地区': ['北京市', '天津市', '河北省', '山西省', '内蒙古自治区'],
  '东北地区': ['辽宁省', '吉林省', '黑龙江省'],
  '华东地区': ['上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省', '台湾省'],
  '华中地区': ['河南省', '湖北省', '湖南省'],
  '华南地区': ['广东省', '广西壮族自治区', '海南省', '香港特别行政区', '澳门特别行政区'],
  '西南地区': ['重庆市', '四川省', '贵州省', '云南省', '西藏自治区'],
  '西北地区': ['陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区']
}

// 中国境内大致范围（含南海诸岛）
const CHINA_BBOX = { lngMin: 72, lngMax: 136, latMin: 2, latMax: 56 }

export function createChinaMap(container, { onPick, onInvalidPick }) {
  const chart = echarts.init(container)

  const provinceNames = chinaGeo.features
    .map(f => f.properties && f.properties.name)
    .filter(Boolean)

  const baseRegions = provinceNames.map((name, i) => ({
    name,
    itemStyle: { areaColor: PALETTE[i % PALETTE.length] }
  }))

  const option = {
    backgroundColor: 'transparent',
    geo: {
      map: 'china',
      roam: true,
      zoom: 1.2,
      center: [104.5, 36.5],
      scaleLimit: { min: 1, max: 10 },
      label: { show: false },
      itemStyle: {
        borderColor: 'rgba(16,22,34,.9)',
        borderWidth: 1
      },
      emphasis: { label: { show: false } },
      select: { disabled: true },
      regions: baseRegions
    },
    series: [
      {
        id: 'pick',
        type: 'scatter',
        coordinateSystem: 'geo',
        symbol: 'circle',
        symbolSize: 16,
        z: 20,
        itemStyle: { color: '#f2c14e', borderColor: '#101828', borderWidth: 2 },
        data: []
      },
      {
        id: 'answer',
        type: 'scatter',
        coordinateSystem: 'geo',
        symbol: 'circle',
        symbolSize: 18,
        z: 20,
        itemStyle: { color: '#e05d44', borderColor: '#fdf6e3', borderWidth: 2 },
        label: {
          show: true,
          formatter: '{b}',
          position: 'top',
          color: '#fdf6e3',
          fontSize: 13,
          fontWeight: 'bold',
          textBorderColor: '#101828',
          textBorderWidth: 3
        },
        data: []
      },
      {
        id: 'link',
        type: 'lines',
        coordinateSystem: 'geo',
        z: 19,
        silent: true,
        // 浅蓝连线：加粗 + 实线 + 暗色光晕，保证在任何省份底色上都看得清
        lineStyle: {
          color: '#8fd3ff', width: 3.5, type: 'solid', curveness: 0.12, opacity: 1,
          shadowColor: 'rgba(8, 14, 26, 0.9)', shadowBlur: 7
        },
        data: []
      },
      {
        // 局结算档案：悬停地名时的红点标记（涟漪效果）
        id: 'spot',
        type: 'effectScatter',
        coordinateSystem: 'geo',
        symbol: 'circle',
        symbolSize: 11,
        z: 30,
        silent: true,
        rippleEffect: { scale: 3.5, brushType: 'stroke' },
        itemStyle: { color: '#ff5f56', borderColor: '#fdf6e3', borderWidth: 2 },
        data: []
      }
    ]
  }
  chart.setOption(option)

  // —— 点击（与拖拽区分）：按下/抬起位移小于阈值视为点击 ——
  let down = null
  const onDown = e => { down = [e.offsetX, e.offsetY] }
  const onUp = e => {
    if (!down) return
    const moved = Math.hypot(e.offsetX - down[0], e.offsetY - down[1])
    down = null
    if (moved > 6) return
    let coords = null
    try {
      const r = chart.convertFromPixel({ geoIndex: 0 }, [e.offsetX, e.offsetY])
      if (r && Number.isFinite(r[0]) && Number.isFinite(r[1])) coords = r
    } catch { /* ignore */ }
    if (!coords) return
    const [lng, lat] = coords
    const inside = lng >= CHINA_BBOX.lngMin && lng <= CHINA_BBOX.lngMax &&
      lat >= CHINA_BBOX.latMin && lat <= CHINA_BBOX.latMax
    if (inside) onPick && onPick(lng, lat)
    else onInvalidPick && onInvalidPick()
  }
  chart.getZr().on('mousedown', onDown)
  chart.getZr().on('mouseup', onUp)
  chart.getZr().on('touchstart', onDown)
  chart.getZr().on('touchend', onUp)

  const ro = new ResizeObserver(() => chart.resize())
  ro.observe(container)

  return {
    // 玩家落点标记
    setPick(lng, lat) {
      chart.setOption({ series: [{ id: 'pick', data: [{ name: '指认位置', value: [lng, lat] }] }] })
    },
    clearPick() {
      chart.setOption({ series: [{ id: 'pick', data: [] }] })
    },
    // 揭晓实际位置（有猜测时画连线）
    reveal(actual, guess) {
      const series = [{ id: 'answer', data: [{ name: actual.name, value: [actual.lng, actual.lat] }] }]
      if (guess) {
        series.push({
          id: 'link',
          data: [{ coords: [[guess.lng, guess.lat], [actual.lng, actual.lat]] }]
        })
      }
      chart.setOption({ series })
    },
    // 高亮提示方位的省份
    highlightRegion(regionName) {
      const provinces = REGION_PROVINCES[regionName] || []
      const merged = baseRegions.map(r =>
        provinces.includes(r.name)
          ? { name: r.name, itemStyle: { areaColor: '#d9a441', opacity: 1 } }
          : { name: r.name, itemStyle: { ...r.itemStyle, opacity: 0.35 } }
      )
      chart.setOption({ geo: { regions: merged } })
    },
    clearHighlight() {
      chart.setOption({ geo: { regions: baseRegions } })
    },
    // 疆域透镜：高亮答案所在省份，其余压暗
    highlightArea(provinceName) {
      const merged = baseRegions.map(r =>
        r.name === provinceName
          ? { name: r.name, itemStyle: { areaColor: '#e8b64c', opacity: 1 } }
          : { name: r.name, itemStyle: { ...r.itemStyle, opacity: 0.3 } }
      )
      chart.setOption({ geo: { regions: merged } })
    },
    // 局结算档案：显示/清除红点
    showSpot(lng, lat) {
      chart.setOption({ series: [{ id: 'spot', data: [{ value: [lng, lat] }] }] })
    },
    clearSpot() {
      chart.setOption({ series: [{ id: 'spot', data: [] }] })
    },
    // 清除揭晓标记（答案点与连线）
    clearReveal() {
      chart.setOption({ series: [{ id: 'answer', data: [] }, { id: 'link', data: [] }] })
    },
    // 供测试读取：当前挂在图上的标记数量（回归守卫用）
    markerState() {
      const list = chart.getOption().series || []
      const n = id => {
        const hit = list.find(x => x && x.id === id)
        return hit && hit.data ? hit.data.length : 0
      }
      return { pick: n("pick"), answer: n("answer"), link: n("link"), spot: n("spot") }
    },
    // 复位视野
    resetView() {
      chart.setOption({ geo: { zoom: 1.2, center: [104.5, 36.5] } })
    },
    dispose() {
      ro.disconnect()
      chart.dispose()
    }
  }
}
