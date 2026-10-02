// 道具与付费档位的双端唯一定义：服务端按此校验次数，前端按此渲染图标与说明。
export const PROP_ORDER = ['time', 'revive', 'redo', 'area']

export const PROPS = {
  time:   { key: 'time',   name: '加时沙漏', effect: '本题倒计时 +12 秒' },
  revive: { key: 'revive', name: '复活罗盘', effect: '本局未达标时复活一次，继续下一局；该局在结算与终局中标黄' },
  redo:   { key: 'redo',   name: '回溯怀表', effect: '回退并重做本局最近两题，重做得分替换原得分' },
  area:   { key: 'area',   name: '疆域透镜', effect: '高亮答案所在的省份 / 国家；无对应地图区域时改为文字提示大洲' }
}

// 付费档位：1 档无道具；2 档 2 次加时 + 2 次复活；3 档再加 1 次回溯 + 1 次透镜
export const TIERS = {
  1: { label: '一档', counts: {} },
  2: { label: '二档', counts: { time: 2, revive: 2 } },
  3: { label: '三档', counts: { time: 3, revive: 2, redo: 1, area: 1 } }
}

export const tierCounts = tier => Object.assign({}, (TIERS[tier] || TIERS[3]).counts)
