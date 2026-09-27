// Mock 演示数据 — 后端不可达时前端自动降级到此
// 所有数据仅供演示，不对应真实用户或真实计算结果

export const MOCK_V_BASE = {
  wood: 58.2,
  fire: 72.5,
  earth: 63.1,
  metal: 48.8,
  water: 55.4
}

export const MOCK_V_OBS_LIST = [
  { t: '2026-08-01', values: { wood: 56.1, fire: 73.8, earth: 62.0, metal: 49.2, water: 56.0 } },
  { t: '2026-08-15', values: { wood: 54.5, fire: 75.2, earth: 60.8, metal: 50.1, water: 56.8 } },
  { t: '2026-09-01', values: { wood: 53.0, fire: 76.5, earth: 59.5, metal: 51.0, water: 57.5 } },
  { t: '2026-09-15', values: { wood: 51.2, fire: 78.0, earth: 58.1, metal: 52.3, water: 58.2 } },
  { t: '2026-09-25', values: { wood: 49.8, fire: 79.3, earth: 56.7, metal: 53.5, water: 59.0 } }
]

export const MOCK_DRIFT_SERIES = MOCK_V_OBS_LIST.map((obs) => ({
  t: obs.t,
  delta: {
    wood: +(obs.values.wood - MOCK_V_BASE.wood).toFixed(1),
    fire: +(obs.values.fire - MOCK_V_BASE.fire).toFixed(1),
    earth: +(obs.values.earth - MOCK_V_BASE.earth).toFixed(1),
    metal: +(obs.values.metal - MOCK_V_BASE.metal).toFixed(1),
    water: +(obs.values.water - MOCK_V_BASE.water).toFixed(1)
  }
}))

export const MOCK_TREND_STATE = 'slow_drift'

export const MOCK_REPORTS = [
  {
    id: 'rpt-001',
    title: '九夏末 · 漂移趋势观察（第 4 次）',
    created_at: '2026-09-25 09:14',
    scope: 'V_base → V_obs（30 天窗）',
    notice: '观察到火形分量缓慢上升 +6.8，木形分量同步下降 -8.4，差值 Δ≈15.2 处于正常波动区间；金形分量稳步上升 +4.7，提示近期修剪效应增强，建议继续保持规律作息以减少漂移加速。'
  },
  {
    id: 'rpt-002',
    title: '处暑 · 漂移趋势观察（第 3 次）',
    created_at: '2026-09-10 08:32',
    scope: 'V_base → V_obs（30 天窗）',
    notice: '土形分量小幅回落 -4.4，未触发土虚警戒；水形缓慢上升 +3.1，差值 Δ 未见突变；整体趋势稳定。'
  },
  {
    id: 'rpt-003',
    title: '立秋 · 漂移趋势观察（第 2 次）',
    created_at: '2026-08-22 07:55',
    scope: 'V_base → V_obs（30 天窗）',
    notice: '金形分量进入上升通道，+2.3 → +3.8，修剪效应渐显；火形上升 +4.0 与金形上升呈耦合关系，符合秋季收敛季节节律。'
  }
]

export const MOCK_NOTIFICATIONS = [
  {
    id: 'ntf-001',
    title: '白露时令养生提示',
    scheduled_at: '2026-09-25 06:00',
    type: '时辰提醒',
    body: '白露后昼夜温差加大，建议早间饮水 200ml 温水润木，晚间 21:00 前入眠以助金形收敛。'
  },
  {
    id: 'ntf-002',
    title: '药茶方案推送：木形偏弱',
    scheduled_at: '2026-09-24 12:00',
    type: '药膳提醒',
    body: '木形分量近 30 天累计下降 -8.4，建议饮用陈皮+炒麦芽代茶饮（陈皮 ΔS 木 +3.2，麦芽 ΔS 木 +2.1），每日 200ml。'
  },
  {
    id: 'ntf-003',
    title: '趋势观察提示：火形上升',
    scheduled_at: '2026-09-20 18:00',
    type: '漂移提示',
    body: '火形分量近 30 天上升 +6.8，建议减少辛辣刺激饮食，晚间避免剧烈运动以降低火形积聚速度。'
  },
  {
    id: 'ntf-004',
    title: '数据采集提醒：建议补充语音样本采样',
    scheduled_at: '2026-09-15 09:00',
    type: '数据采集提醒',
    body: '距上次语音样本采集已 45 天，建议今日录制 30 秒自然说话样本，用于漂移拟合更新。'
  }
]

export const MOCK_KB_ITEMS = [
  { id: 101, category: '药膳', title: '陈皮茶 — 木形偏弱时饮用', compliant: true },
  { id: 102, category: '药膳', title: '炒麦芽汤 — 木形 +2.1 / 土形 +1.5', compliant: true },
  { id: 103, category: '导引', title: '八段锦 · 第一式两手托天理三焦', compliant: true },
  { id: 104, category: '衣物', title: '白色 / 金色系 — 金形 +1.2', compliant: true },
  { id: 105, category: '时辰', title: '戌时（19-21点）— 心包经当值，适宜静坐', compliant: true },
  { id: 106, category: '药膳', title: '百合银耳羹 — 火形 +1.8 / 水形 +2.0', compliant: true },
  { id: 107, category: '衣物', title: '黑色系 — 水形 +1.5', compliant: true },
  { id: 108, category: '导引', title: '站桩 — 土形 +2.0 / 木形 -0.5', compliant: true }
]

export const MOCK_USER = {
  id: 1,
  name: '演示用户',
  birth_date: '1992-06-15',
  birth_ganzhi: '壬申 丙午 庚寅',
  timezone: 'Asia/Shanghai'
}

export function isMockMode (health) {
  if (!health) return true
  return !health.ok
}
