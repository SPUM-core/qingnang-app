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

// ═══════════════════════════════════════════════════════════
// v0.2 三曲线 Mock 数据 — 体质调理曲线信任锚点
// ★ 基于胡运涛病历真实 PPG 观测数据（12 个时间点）
// ───────────────────────────────────────────────────────────
// 数据来源：青囊/病历/胡运涛/数据/脉象/ 目录下 12 份 PPG 报告
// 转换公式：v_obs = 50 + ΔF * 40（ΔF ∈ [-1,1]，仪器读数 → [10,90] 量纲）
// 健康综合得分：health_score = 100 - sqrt(Σ(v_i - 50)² / 5)
// 健康区带 H（分量值）：40-60
// ═══════════════════════════════════════════════════════════

function healthScore (v) {
  const dims = ['wood', 'fire', 'earth', 'metal', 'water']
  const sumSq = dims.reduce((s, k) => s + ((v[k] ?? 50) - 50) ** 2, 0)
  return Math.round((100 - Math.sqrt(sumSq / 5)) * 10) / 10
}

// ═══ 先天基底 S_0^0（病历 v5.4 出生事件校核版）═══
// 八字：丁卯 己酉 甲子 丙寅（寅时确定）
// 量化：木↑↑↑→60  火↑↑(郁)→58  土↓→35  金↔→50  水↔(伤)→48
const HU_V_INNATE = { wood: 60, fire: 58, earth: 35, metal: 50, water: 48 }
const HU_V_BASELINE = { wood: 60, fire: 58, earth: 35, metal: 50, water: 48 }

// ═══ 12 个真实 PPG 观测点 ═══
// ΔF 原始读数 → v_obs = 50 + ΔF * 40
// 包含同日多次采集（07-18×2, 08-02×4, 09-08×2）
const PPG_RECORDS = [
  // day=1  07-18 首次采集（假性充盈：土+0.60→74 但临床为 S_土↓↓↓）
  { day: 1,  t: '07-18', hhmm: '18:00', wood: 35.6, fire: 74.8, earth: 74.0, metal: 38.8, water: 26.0,
    paradoxFlags: ['earth_false_fullness', 'fire_empty_float'],
    syndromeHint: '脾虚湿困+上热下寒（假性充盈）' },
  // day=2  07-18 重复采集
  { day: 2,  t: '07-18', hhmm: '18:01', wood: 36.0, fire: 76.8, earth: 74.0, metal: 38.8, water: 26.0,
    syndromeHint: '脾虚湿困+上热下寒' },
  // day=3  07-21 湿热化火（火从+0.62→+0.75 心率84.8）
  { day: 3,  t: '07-21', hhmm: '18:17', wood: 37.6, fire: 80.0, earth: 74.0, metal: 40.0, water: 26.0,
    syndromeHint: '湿热化火·舌厚黄苔·肝俞痛' },
  // day=4  08-02 气滞血瘀（服药前？）
  { day: 4,  t: '08-02', hhmm: '15:57', wood: 70.0, fire: 40.0, earth: 36.0, metal: 66.0, water: 26.0,
    syndromeHint: '气滞血瘀（置信度88%）' },
  // day=5  08-02 火衰
  { day: 5,  t: '08-02', hhmm: '16:06', wood: 62.8, fire: 29.6, earth: 32.4, metal: 60.4, water: 26.0,
    syndromeHint: '火衰（温差趋零）' },
  // day=6  08-02 收敛正常（服方后？）
  { day: 6,  t: '08-02', hhmm: '16:17', wood: 54.4, fire: 47.2, earth: 44.8, metal: 53.6, water: 54.4,
    syndromeHint: '五形趋于正常（肝气郁结44%）' },
  // day=7  08-02 收敛正常
  { day: 7,  t: '08-02', hhmm: '16:23', wood: 56.0, fire: 49.2, earth: 45.2, metal: 54.8, water: 57.6,
    syndromeHint: '五形趋于正常（肝气郁结53%）' },
  // day=8  09-08 服方 on（v5.7 最小试探方·桂枝汤）
  { day: 8,  t: '09-08', hhmm: '12:50', wood: 52.8, fire: 56.0, earth: 47.2, metal: 52.4, water: 54.0,
    syndromeHint: '正常脉象（服方on·透火郁主频效验）' },
  // day=9  09-08 服方 on
  { day: 9,  t: '09-08', hhmm: '12:51', wood: 51.6, fire: 57.2, earth: 49.6, metal: 51.2, water: 57.2,
    syndromeHint: '正常脉象（服方on）' },
  // day=10 09-10 停药 off（on-off 验证：肝郁87% 水亏-0.31）
  { day: 10, t: '09-10', hhmm: '16:08', wood: 55.2, fire: 44.8, earth: 41.2, metal: 54.0, water: 38.4,
    syndromeHint: '停药复发·肝郁87%·水亏' },
  // day=11 09-12 爬山后气阴两虚（木-0.27 金-0.22）
  { day: 11, t: '09-12', hhmm: '18:35', wood: 42.4, fire: 41.2, earth: 40.4, metal: 44.0, water: 41.6,
    syndromeHint: '气阴两虚·清阳不升' },
  // day=12 09-15 湿遏火衰（舌胖齿痕·中根部厚白苔）
  { day: 12, t: '09-15', hhmm: '11:25', wood: 51.2, fire: 32.4, earth: 39.2, metal: 50.8, water: 26.0,
    syndromeHint: '湿遏·火衰-0.41·水滞-0.62' },
]

// ═══ 关键临床事件 ═══
const CLINICAL_EVENTS = [
  { day: 1, type: '初诊',   label: '首次服药（v5.2）',     direction: '收敛', scoreDelta: +0.0 },
  { day: 1, type: '悖论态', label: 'PPG土+0.60=假性充盈',  direction: '注意',  scoreDelta: 0, isParadox: true },
  { day: 3, type: '干预',   label: 'v5.5方：薏苡仁+竹茹清湿热', direction: '收敛', scoreDelta: +3.5 },
  { day: 5, type: '排病',   label: '湿泻+阳虚寒象暴露',    direction: '短期发散', scoreDelta: -5.8, isSideEffect: true },
  { day: 6, type: '排病',   label: '同日内火衰→收敛（服药后）', direction: '收敛', scoreDelta: +12.4 },
  { day: 8, type: '干预',   label: 'v5.7最小试探方·桂枝汤透火郁', direction: '收敛', scoreDelta: +8.2 },
  { day: 9, type: '收敛',   label: '五形回归正常区间',      direction: '收敛', scoreDelta: +2.1 },
  { day: 10,type: '偏离',   label: '停药on-off验证复发',    direction: '发散', scoreDelta: -6.3 },
  { day: 11,type: '偏离',   label: '爬山耗气·气阴两虚',    direction: '发散', scoreDelta: -4.0, isSideEffect: true },
  { day: 12,type: '排病',   label: '湿遏·火衰-0.41·重建v7.0苓桂术甘', direction: '短期发散', scoreDelta: -8.0, isSideEffect: true },
]

// ═══ 构建 trajectory ═══
function buildTrajectory () {
  const actual = []
  const actual_elements = []
  const DIMS = ['wood', 'fire', 'earth', 'metal', 'water']

  for (const rec of PPG_RECORDS) {
    const v = { wood: rec.wood, fire: rec.fire, earth: rec.earth, metal: rec.metal, water: rec.water }
    const hs = healthScore(v)
    actual.push({ day: rec.day, t: rec.t, score: hs, syndromeHint: rec.syndromeHint })
    actual_elements.push({
      day: rec.day, t: rec.t,
      wood: rec.wood, fire: rec.fire, earth: rec.earth, metal: rec.metal, water: rec.water,
      hhmm: rec.hhmm, age: 39,       // 胡运涛 1987生 → 2026 年 39 岁
      syndromeHint: rec.syndromeHint,
      paradoxFlags: rec.paradoxFlags || [],
    })
  }

  // 目标收敛曲线：从第一个观测 → 健康区带中心 72
  const startScore = actual[0].score
  const target = []
  const tau = Math.max(actual.length / 2.5, 3)
  for (let i = 0; i < actual.length; i++) {
    const progress = 1 - Math.exp(-i / tau)
    const score = startScore + (72.0 - startScore) * progress
    target.push({ day: i + 1, t: actual[i].t, score: Math.round(score * 10) / 10 })
  }

  return {
    target,
    actual,
    actual_elements,
    events: CLINICAL_EVENTS,
    innate_elements: HU_V_INNATE,
    v_innate: HU_V_INNATE,
    v_baseline: HU_V_BASELINE,
  }
}

export const MOCK_TRAJECTORY = buildTrajectory()

// 健康区带 H（分量值）：40-60
export const HEALTH_ZONE = { min: 40, max: 60, label: '健康区带 H' }

// v_innate / v_baseline（综合雷达图用）
export const MOCK_V_INNATE = HU_V_INNATE
export const MOCK_V_BASELINE_NEW = HU_V_BASELINE

// PPG 个体基线（后端 09-10 报告的"近采中位数"）
export const PPG_INDIVIDUAL_BASELINE = { wood: 53.2, fire: 48.8, earth: 45.2, metal: 52.8, water: 50.8 }

// ═══════════════════════════════════════════════════════════
// 曾银鸾 · 终身体质曲线模拟（参考案例）
// 八字：丁酉 戊申 癸亥 甲寅
// 先天基底：水↑↑↑ 金↑↑ 木↑ 火↓↓ 土↔
// 量化：wood=55, fire=40, earth=50, metal=60, water=65
// 病史：2011右乳癌+化放疗→2021左乳癌→2025尿道上皮癌
// ═══════════════════════════════════════════════════════════
export const ZY_V_INNATE = { wood: 55, fire: 40, earth: 50, metal: 60, water: 65 }

// 每年的体质模拟点（1957出生 → 2038丙辰运末）
// 基于八字大运+病史推演的趋势线，非真实观测
function buildZengLifetime () {
  const DIMS = ['wood', 'fire', 'earth', 'metal', 'water']
  const elems = []
  const events = []

  // 大运起止（岁）
  const DAYUN = [
    { name: '己酉', start: 1,  end: 11,  w: '土金',   drift: +2 },   // 少年土金运，火稍长
    { name: '庚戌', start: 11, end: 21,  w: '金土',   drift: 0 },    // 官印相生，稳定
    { name: '辛亥', start: 21, end: 31,  w: '金水',   drift: -2 },   // 金水运，水势增
    { name: '壬子', start: 31, end: 41,  w: '水水',   drift: -5 },   // 双水运，水极旺→身体透支
    { name: '癸丑', start: 41, end: 51,  w: '水土',   drift: -3 },   // 土制水，但更年期火衰
    { name: '甲寅', start: 51, end: 61,  w: '木木',   drift: -2 },   // 木泄水，压力开始显现
    { name: '乙卯', start: 61, end: 71,  w: '木木',   drift: -8 },   // 双木极泄，最危重10年
    { name: '丙辰', start: 71, end: 81,  w: '火土',   drift: +5 },    // 补火制水，晚年修复
  ]

  const events_raw = [
    { age: 54, year: 2011, type: '手术', surgery: true, damage: 0.4, recoveryDays: 1095,
      label: '右乳腺癌手术+化放疗', isMedical: true },
    { age: 55, year: 2012, type: '药物', isMedical: true,
      label: '阿那曲唑5年（芳香化酶抑制剂→进一步压制火形）' },
    { age: 64, year: 2021, type: '手术', surgery: true, damage: 0.35, recoveryDays: 730,
      label: '左乳腺癌手术（对侧复发）', isMedical: true },
    { age: 68, year: 2025, type: '手术', surgery: true, damage: 0.3, recoveryDays: 540,
      label: '尿道上皮癌手术（水系统癌变）', isMedical: true },
    { age: 69, year: 2026, type: '窗口期', label: '丙午年双火·18年来最佳补火窗口' },
  ]

  // 2011 化放疗直接损伤量
  const chemo_damage = { fire: -12, metal: -10, water: -3 }   // 火形大伤、金形损伤、水链受损
  const arimidex_damage = { fire: -8 }                        // 阿那曲唑压火
  const surgery_2021 = { metal: -5, water: -3, fire: -3 }
  const surgery_2025 = { water: -8, metal: -4 }

  for (let age = 0; age <= 81; age++) {
    const year = 1957 + age
    const day = age * 365

    // 大运基准偏移
    const dy = DAYUN.find(d => age >= d.start && age < d.end) || DAYUN[DAYUN.length - 1]

    // 先天基底 + 大运偏移（水旺→fire↓、metal↓随年龄）
    let v = { ...ZY_V_INNATE }
    // 随年龄自然衰老（20岁后每10年各分量 -1，除了已经偏离的方向继续偏）
    const decay = age > 20 ? (age - 20) / 10 : 0
    v.fire -= decay * 0.8     // 火随年龄衰减最快
    v.metal -= decay * 0.3    // 金（肺）次之
    v.water -= decay * 0.2    // 水（肾）缓慢衰减

    // 大运对火的影响
    v.fire += dy.drift * 0.6

    // 2011 化放疗（age 54，持续约1年）
    if (age >= 54 && age <= 56) {
      v.fire += chemo_damage.fire
      v.metal += chemo_damage.metal
      v.water += chemo_damage.water
    }
    // 阿那曲唑 2011-2016（age 54-59）
    if (age >= 54 && age <= 59) {
      v.fire += arimidex_damage.fire
    }
    // 2021 左乳手术（age 64）
    if (age >= 64 && age <= 65) {
      v.metal += surgery_2021.metal
      v.water += surgery_2021.water
      v.fire += surgery_2021.fire
    }
    // 2025 尿道上皮癌（age 68）
    if (age >= 68) {
      v.water += surgery_2025.water
      v.metal += surgery_2025.metal
    }
    // 2026 丙午年补火窗口（age 69）
    if (age >= 69 && age <= 70) {
      v.fire += 6   // 双火年，命局最需要的调候力量
    }
    // 2028 起丙辰大运（age 71+）
    if (age >= 71) {
      v.fire += 3   // 丙火正财照命
      v.earth += 2  // 辰土制水
      v.water -= 3  // 土制水 → 水势回归
    }

    // 钳制到 [5, 95]
    for (const k of DIMS) v[k] = Math.max(5, Math.min(95, Math.round(v[k] * 10) / 10))

    elems.push({
      day,
      t: `${year}·${age}岁`,
      age,
      ...v,
    })
  }

  // 事件 day 对齐到 age 对应的 day
  for (const ev of events_raw) {
    ev.day = ev.age * 365
    delete ev.age
    delete ev.year
    events.push(ev)
  }

  return {
    actual_elements: elems,
    events,
    innate_elements: ZY_V_INNATE,
    v_innate: ZY_V_INNATE,
    label: '曾银鸾 · 终身体质曲线（1957-2038）',
    birthYear: 1957,
    target: elems.map(e => ({ day: e.day, t: e.t, score: 50 })),
    actual: elems.map(e => ({ day: e.day, t: e.t, score: 50 })),
  }
}

export const ZY_LIFETIME_TRAJECTORY = buildZengLifetime()
// 曾银鸾 SPUM 三曲线 mock 数据（由 tizhi-curve 算法生成）
// 算法: spum_computeHealthBounds_v1 — Y/X 浓度 + EMA 滞后 + 金属弹性解耦
// 坐标系: Y正=阴偏(向上) > yinTop, Y负=阳偏(向下) < yangBot
export const ZY_SPUM_FULL_82 = {
    algorithm: 'spum_computeHealthBounds_v2',
  theory_source: 'SPUM2611 + 青囊中医总纲',
  // ── v2 新增字段 ──
  sigma_trend: [0.53, 0.48, 0.48, 0.48, 0.48, 0.48, 0.48, 0.48, 0.48, 0.48, 0.48, 0.48, 0.486, 0.495, 0.502, 0.509, 0.511, 0.511, 0.511, 0.511, 0.511, 0.511, 0.506, 0.492, 0.476, 0.457, 0.432, 0.431, 0.431, 0.431, 0.43, 0.43, 0.423, 0.406, 0.385, 0.367, 0.359, 0.358, 0.359, 0.359, 0.358, 0.358, 0.365, 0.385, 0.407, 0.426, 0.435, 0.435, 0.435, 0.434, 0.434, 0.434, 0.457, 0.514, 0.592, 0.57, 0.594, 0.606, 0.616, 0.622, 0.634, 0.635, 0.621, 0.59, 0.594, 0.538, 0.51, 0.51, 0.606, 0.535, 0.51, 0.509, 0.537, 0.602, 0.613, 0.606, 0.603, 0.603, 0.603, 0.602, 0.602, 0.602],
  health_score: [0.236, 0.234, 0.256, 0.272, 0.272, 0.272, 0.272, 0.272, 0.272, 0.272, 0.272, 0.272, 0.279, 0.275, 0.294, 0.315, 0.325, 0.328, 0.328, 0.328, 0.328, 0.328, 0.334, 0.382, 0.357, 0.352, 0.33, 0.32, 0.321, 0.319, 0.319, 0.318, 0.316, 0.281, 0.228, 0.178, 0.165, 0.161, 0.162, 0.162, 0.162, 0.162, 0.179, 0.224, 0.307, 0.312, 0.326, 0.322, 0.322, 0.322, 0.323, 0.321, 0.316, 0.355, 0.193, 0.438, 0.32, 0.337, 0.465, 0.477, 0.47, 0.499, 0.476, 0.416, 0.284, 0.224, 0.224, 0.252, 0.219, 0.2, 0.239, 0.252, 0.31, 0.372, 0.391, 0.427, 0.443, 0.432, 0.432, 0.432, 0.431, 0.434],
  polytope_statuses: ['IN', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'ON', 'IN', 'IN', 'ON', 'ON', 'ON', 'ON', 'ON', 'ON', 'ON', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'IN', 'ON', 'ON', 'ON', 'ON', 'ON', 'ON', 'ON', 'ON', 'IN', 'IN', 'ON', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'IN', 'ON', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT', 'OUT'],
  violation_depths: [0.0, 4.0, 6.4, 6.4, 6.4, 6.4, 6.4, 6.4, 6.4, 6.4, 6.4, 6.4, 6.0, 5.1, 4.1, 3.2, 2.8, 2.8, 2.8, 2.8, 2.8, 2.8, 1.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.4, 3.8, 5.8, 6.7, 6.7, 6.6, 6.6, 6.6, 6.6, 5.0, 1.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 1.5, 3.0, 4.8, 6.4, 7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 5.3, 1.1, 0.0, 0.0, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6],
  frame_residues: [0.64, 0.479, 0.328, 0.331, 0.331, 0.331, 0.331, 0.331, 0.331, 0.331, 0.331, 0.331, 0.358, 0.506, 0.521, 0.521, 0.516, 0.509, 0.509, 0.509, 0.509, 0.509, 0.529, 0.444, 0.492, 0.453, 0.469, 0.512, 0.51, 0.513, 0.512, 0.513, 0.5, 0.507, 0.529, 0.624, 0.621, 0.648, 0.65, 0.649, 0.648, 0.649, 0.689, 0.753, 0.486, 0.526, 0.498, 0.512, 0.512, 0.511, 0.51, 0.512, 0.619, 0.611, 0.693, 0.429, 0.559, 0.541, 0.386, 0.374, 0.396, 0.356, 0.343, 0.334, 0.251, 0.517, 0.504, 0.474, 0.413, 0.533, 0.444, 0.474, 0.425, 0.684, 0.724, 0.583, 0.484, 0.517, 0.517, 0.516, 0.516, 0.514],

  v_innate: {"wood":55,"fire":40,"earth":50,"metal":60,"water":65},
  view_mode: 'year',
  dayun: [{"gan":"己","zhi":"酉","start":1,"end":11,"name":"己酉"},{"gan":"庚","zhi":"戌","start":11,"end":21,"name":"庚戌"},{"gan":"辛","zhi":"亥","start":21,"end":31,"name":"辛亥"},{"gan":"壬","zhi":"子","start":31,"end":41,"name":"壬子"},{"gan":"癸","zhi":"丑","start":41,"end":51,"name":"癸丑"},{"gan":"甲","zhi":"寅","start":51,"end":61,"name":"甲寅"},{"gan":"乙","zhi":"卯","start":61,"end":71,"name":"乙卯"},{"gan":"丙","zhi":"辰","start":71,"end":81,"name":"丙辰"}],
  dayunMarkArea: [{"start_age":1,"end_age":11,"name":"己酉","gan":"己","zhi":"酉"},{"start_age":11,"end_age":21,"name":"庚戌","gan":"庚","zhi":"戌"},{"start_age":21,"end_age":31,"name":"辛亥","gan":"辛","zhi":"亥"},{"start_age":31,"end_age":41,"name":"壬子","gan":"壬","zhi":"子"},{"start_age":41,"end_age":51,"name":"癸丑","gan":"癸","zhi":"丑"},{"start_age":51,"end_age":61,"name":"甲寅","gan":"甲","zhi":"寅"},{"start_age":61,"end_age":71,"name":"乙卯","gan":"乙","zhi":"卯"},{"start_age":71,"end_age":81,"name":"丙辰","gan":"丙","zhi":"辰"}],
  elems: [{"age":0,"day":0,"t":"1957·0岁·丙辰","dayun":"丙辰","wood":49.6,"fire":40,"earth":56.6,"metal":78.4,"water":69.6},{"age":1,"day":365,"t":"1958·1岁·己酉","dayun":"己酉","wood":49.6,"fire":40,"earth":56.6,"metal":78.4,"water":69.6},{"age":2,"day":730,"t":"1959·2岁·己酉","dayun":"己酉","wood":49.6,"fire":40,"earth":56.6,"metal":78.4,"water":69.6},{"age":3,"day":1095,"t":"1960·3岁·己酉","dayun":"己酉","wood":49.6,"fire":40,"earth":56.6,"metal":78.4,"water":69.6},{"age":4,"day":1460,"t":"1961·4岁·己酉","dayun":"己酉","wood":49.6,"fire":40,"earth":56.6,"metal":78.4,"water":69.6},{"age":5,"day":1825,"t":"1962·5岁·己酉","dayun":"己酉","wood":49.6,"fire":40,"earth":56.6,"metal":78.4,"water":69.6},{"age":6,"day":2190,"t":"1963·6岁·己酉","dayun":"己酉","wood":49.6,"fire":40,"earth":56.6,"metal":78.4,"water":69.6},{"age":7,"day":2555,"t":"1964·7岁·己酉","dayun":"己酉","wood":49.6,"fire":40,"earth":56.6,"metal":78.4,"water":69.6},{"age":8,"day":2920,"t":"1965·8岁·己酉","dayun":"己酉","wood":49.6,"fire":40,"earth":56.6,"metal":78.4,"water":69.6},{"age":9,"day":3285,"t":"1966·9岁·己酉","dayun":"己酉","wood":49.6,"fire":40,"earth":56.6,"metal":78.4,"water":69.6},{"age":10,"day":3650,"t":"1967·10岁·己酉","dayun":"己酉","wood":49.6,"fire":40,"earth":56.6,"metal":78.4,"water":69.6},{"age":11,"day":4015,"t":"1968·11岁·庚戌","dayun":"庚戌","wood":49.6,"fire":40,"earth":56.6,"metal":78.4,"water":69.6},{"age":12,"day":4380,"t":"1969·12岁·庚戌","dayun":"庚戌","wood":49.8,"fire":40.2,"earth":56.9,"metal":78,"water":69.3},{"age":13,"day":4745,"t":"1970·13岁·庚戌","dayun":"庚戌","wood":50.1,"fire":40.5,"earth":57.8,"metal":77.1,"water":68.6},{"age":14,"day":5110,"t":"1971·14岁·庚戌","dayun":"庚戌","wood":50.6,"fire":41,"earth":58.8,"metal":76.1,"water":67.8},{"age":15,"day":5475,"t":"1972·15岁·庚戌","dayun":"庚戌","wood":50.9,"fire":41.4,"earth":59.6,"metal":75.2,"water":67.1},{"age":16,"day":5840,"t":"1973·16岁·庚戌","dayun":"庚戌","wood":51.1,"fire":41.5,"earth":59.9,"metal":74.8,"water":66.8},{"age":17,"day":6205,"t":"1974·17岁·庚戌","dayun":"庚戌","wood":51.1,"fire":41.5,"earth":59.9,"metal":74.8,"water":66.8},{"age":18,"day":6570,"t":"1975·18岁·庚戌","dayun":"庚戌","wood":51.1,"fire":41.5,"earth":59.9,"metal":74.8,"water":66.8},{"age":19,"day":6935,"t":"1976·19岁·庚戌","dayun":"庚戌","wood":51.1,"fire":41.5,"earth":59.9,"metal":74.8,"water":66.8},{"age":20,"day":7300,"t":"1977·20岁·庚戌","dayun":"庚戌","wood":51.1,"fire":41.5,"earth":59.9,"metal":74.8,"water":66.8},{"age":21,"day":7665,"t":"1978·21岁·辛亥","dayun":"辛亥","wood":51.1,"fire":41.5,"earth":59.9,"metal":74.8,"water":66.8},{"age":22,"day":8030,"t":"1979·22岁·辛亥","dayun":"辛亥","wood":52.2,"fire":41,"earth":58.7,"metal":73.9,"water":68},{"age":23,"day":8395,"t":"1980·23岁·辛亥","dayun":"辛亥","wood":55,"fire":40.2,"earth":55.9,"metal":71.8,"water":71},{"age":24,"day":8760,"t":"1981·24岁·辛亥","dayun":"辛亥","wood":58.3,"fire":39.1,"earth":52.4,"metal":69.4,"water":74.5},{"age":25,"day":9125,"t":"1982·25岁·辛亥","dayun":"辛亥","wood":61,"fire":38.2,"earth":49.6,"metal":67.3,"water":77.4},{"age":26,"day":9490,"t":"1983·26岁·辛亥","dayun":"辛亥","wood":62.2,"fire":37.8,"earth":48.4,"metal":66.4,"water":78.6},{"age":27,"day":9855,"t":"1984·27岁·辛亥","dayun":"辛亥","wood":62.2,"fire":37.7,"earth":48.4,"metal":66.4,"water":78.6},{"age":28,"day":10220,"t":"1985·28岁·辛亥","dayun":"辛亥","wood":62.2,"fire":37.7,"earth":48.4,"metal":66.4,"water":78.6},{"age":29,"day":10585,"t":"1986·29岁·辛亥","dayun":"辛亥","wood":62.2,"fire":37.6,"earth":48.4,"metal":66.3,"water":78.6},{"age":30,"day":10950,"t":"1987·30岁·辛亥","dayun":"辛亥","wood":62.2,"fire":37.5,"earth":48.4,"metal":66.3,"water":78.6},{"age":31,"day":11315,"t":"1988·31岁·壬子","dayun":"壬子","wood":62.2,"fire":37.4,"earth":48.4,"metal":66.3,"water":78.5},{"age":32,"day":11680,"t":"1989·32岁·壬子","dayun":"壬子","wood":62.4,"fire":36.7,"earth":48.6,"metal":65.6,"water":79.4},{"age":33,"day":12045,"t":"1990·33岁·壬子","dayun":"壬子","wood":63.1,"fire":35.2,"earth":49,"metal":63.9,"water":81.4},{"age":34,"day":12410,"t":"1991·34岁·壬子","dayun":"壬子","wood":63.9,"fire":33.3,"earth":49.4,"metal":61.9,"water":83.8},{"age":35,"day":12775,"t":"1992·35岁·壬子","dayun":"壬子","wood":64.6,"fire":31.7,"earth":49.8,"metal":60.2,"water":85.8},{"age":36,"day":13140,"t":"1993·36岁·壬子","dayun":"壬子","wood":64.9,"fire":31,"earth":50,"metal":59.5,"water":86.7},{"age":37,"day":13505,"t":"1994·37岁·壬子","dayun":"壬子","wood":64.9,"fire":30.9,"earth":50,"metal":59.5,"water":86.7},{"age":38,"day":13870,"t":"1995·38岁·壬子","dayun":"壬子","wood":64.9,"fire":30.9,"earth":50,"metal":59.5,"water":86.6},{"age":39,"day":14235,"t":"1996·39岁·壬子","dayun":"壬子","wood":64.9,"fire":30.8,"earth":50,"metal":59.4,"water":86.6},{"age":40,"day":14600,"t":"1997·40岁·壬子","dayun":"壬子","wood":64.9,"fire":30.7,"earth":50,"metal":59.4,"water":86.6},{"age":41,"day":14965,"t":"1998·41岁·癸丑","dayun":"癸丑","wood":64.9,"fire":30.6,"earth":50,"metal":59.4,"water":86.6},{"age":42,"day":15330,"t":"1999·42岁·癸丑","dayun":"癸丑","wood":64.1,"fire":31,"earth":51,"metal":60.3,"water":85},{"age":43,"day":15695,"t":"2000·43岁·癸丑","dayun":"癸丑","wood":62.1,"fire":32.2,"earth":53.3,"metal":62.4,"water":81.3},{"age":44,"day":16060,"t":"2001·44岁·癸丑","dayun":"癸丑","wood":59.8,"fire":33.5,"earth":56,"metal":65,"water":76.8},{"age":45,"day":16425,"t":"2002·45岁·癸丑","dayun":"癸丑","wood":57.9,"fire":34.6,"earth":58.3,"metal":67.1,"water":73},{"age":46,"day":16790,"t":"2003·46岁·癸丑","dayun":"癸丑","wood":57,"fire":35.1,"earth":59.2,"metal":68,"water":71.5},{"age":47,"day":17155,"t":"2004·47岁·癸丑","dayun":"癸丑","wood":57,"fire":35,"earth":59.2,"metal":68,"water":71.4},{"age":48,"day":17520,"t":"2005·48岁·癸丑","dayun":"癸丑","wood":57,"fire":34.9,"earth":59.2,"metal":67.9,"water":71.4},{"age":49,"day":17885,"t":"2006·49岁·癸丑","dayun":"癸丑","wood":57,"fire":34.8,"earth":59.2,"metal":67.9,"water":71.4},{"age":50,"day":18250,"t":"2007·50岁·癸丑","dayun":"癸丑","wood":57,"fire":34.8,"earth":59.2,"metal":67.9,"water":71.4},{"age":51,"day":18615,"t":"2008·51岁·甲寅","dayun":"甲寅","wood":57,"fire":34.7,"earth":59.2,"metal":67.8,"water":71.4},{"age":52,"day":18980,"t":"2009·52岁·甲寅","dayun":"甲寅","wood":58.5,"fire":36.1,"earth":58.1,"metal":66.8,"water":70.6},{"age":53,"day":19345,"t":"2010·53岁·甲寅","dayun":"甲寅","wood":61.9,"fire":39.6,"earth":55.3,"metal":64.4,"water":68.7},{"age":54,"day":19710,"t":"2011·54岁·甲寅","dayun":"甲寅","wood":66,"fire":31.9,"earth":52,"metal":51.5,"water":63.4},{"age":55,"day":20075,"t":"2012·55岁·甲寅","dayun":"甲寅","wood":69.4,"fire":33.3,"earth":49.2,"metal":53.9,"water":63},{"age":56,"day":20440,"t":"2013·56岁·甲寅","dayun":"甲寅","wood":70.8,"fire":40.3,"earth":48.1,"metal":55.4,"water":63},{"age":57,"day":20805,"t":"2014·57岁·甲寅","dayun":"甲寅","wood":70.8,"fire":45.2,"earth":48.1,"metal":58,"water":63.7},{"age":58,"day":21170,"t":"2015·58岁·甲寅","dayun":"甲寅","wood":70.8,"fire":46.3,"earth":48.1,"metal":57.9,"water":63.7},{"age":59,"day":21535,"t":"2016·59岁·甲寅","dayun":"甲寅","wood":70.8,"fire":47,"earth":48.1,"metal":57.9,"water":63.7},{"age":60,"day":21900,"t":"2017·60岁·甲寅","dayun":"甲寅","wood":70.8,"fire":48.5,"earth":48.1,"metal":57.9,"water":63.7},{"age":61,"day":22265,"t":"2018·61岁·乙卯","dayun":"乙卯","wood":70.8,"fire":48.5,"earth":48.1,"metal":57.8,"water":63.6},{"age":62,"day":22630,"t":"2019·62岁·乙卯","dayun":"乙卯","wood":71.5,"fire":48.2,"earth":47.5,"metal":57.9,"water":63.7},{"age":63,"day":22995,"t":"2020·63岁·乙卯","dayun":"乙卯","wood":73,"fire":47.7,"earth":46,"metal":58.1,"water":63.8},{"age":64,"day":23360,"t":"2021·64岁·乙卯","dayun":"乙卯","wood":74.8,"fire":44,"earth":44.3,"metal":53.4,"water":60.9},{"age":65,"day":23725,"t":"2022·65岁·乙卯","dayun":"乙卯","wood":76.4,"fire":45.4,"earth":42.9,"metal":56.7,"water":62.9},{"age":66,"day":24090,"t":"2023·66岁·乙卯","dayun":"乙卯","wood":77,"fire":46.2,"earth":42.3,"metal":58.6,"water":64.1},{"age":67,"day":24455,"t":"2024·67岁·乙卯","dayun":"乙卯","wood":77,"fire":46.1,"earth":42.3,"metal":58.6,"water":64.1},{"age":68,"day":24820,"t":"2025·68岁·乙卯","dayun":"乙卯","wood":77,"fire":46.1,"earth":42.3,"metal":54.6,"water":56},{"age":69,"day":25185,"t":"2026·69岁·乙卯","dayun":"乙卯","wood":77,"fire":46,"earth":42.3,"metal":57.5,"water":61.9},{"age":70,"day":25550,"t":"2027·70岁·乙卯","dayun":"乙卯","wood":77,"fire":45.9,"earth":42.3,"metal":58.5,"water":64},{"age":71,"day":25915,"t":"2028·71岁·丙辰","dayun":"丙辰","wood":77,"fire":45.8,"earth":42.3,"metal":58.5,"water":64},{"age":72,"day":26280,"t":"2029·72岁·丙辰","dayun":"丙辰","wood":75.3,"fire":45.6,"earth":44.2,"metal":58.6,"water":63.8},{"age":73,"day":26645,"t":"2030·73岁·丙辰","dayun":"丙辰","wood":71.1,"fire":45,"earth":48.7,"metal":59.1,"water":63.3},{"age":74,"day":27010,"t":"2031·74岁·丙辰","dayun":"丙辰","wood":66.2,"fire":44.4,"earth":54.2,"metal":59.6,"water":62.8},{"age":75,"day":27375,"t":"2032·75岁·丙辰","dayun":"丙辰","wood":62,"fire":43.9,"earth":58.7,"metal":60,"water":62.4},{"age":76,"day":27740,"t":"2033·76岁·丙辰","dayun":"丙辰","wood":60.3,"fire":43.7,"earth":60.6,"metal":60.2,"water":62.2},{"age":77,"day":28105,"t":"2034·77岁·丙辰","dayun":"丙辰","wood":60.3,"fire":43.6,"earth":60.6,"metal":60.1,"water":62.2},{"age":78,"day":28470,"t":"2035·78岁·丙辰","dayun":"丙辰","wood":60.3,"fire":43.5,"earth":60.6,"metal":60.1,"water":62.1},{"age":79,"day":28835,"t":"2036·79岁·丙辰","dayun":"丙辰","wood":60.3,"fire":43.4,"earth":60.6,"metal":60.1,"water":62.1},{"age":80,"day":29200,"t":"2037·80岁·丙辰","dayun":"丙辰","wood":60.3,"fire":43.3,"earth":60.6,"metal":60,"water":62.1},{"age":81,"day":29565,"t":"2038·81岁·丙辰","dayun":"丙辰","wood":60.3,"fire":43.3,"earth":60.6,"metal":60,"water":62.1}],
  // 核心三曲线
  driftData: [-0.8,-0.8,-0.8,-0.8,-0.8,-0.8,-0.8,-0.8,-0.8,-0.8,-0.8,-0.8,-0.7,-0.5,0,0.4,0.4,0.4,0.4,0.4,0.4,0.4,0.2,0,-0.5,-0.6,-0.4,-0.5,-0.5,-0.5,-0.5,-0.5,-0.6,-0.7,-0.8,-1,-1.1,-1.1,-1.1,-1.1,-1.1,-1.1,-1,-0.6,-0.2,0.1,0.2,0.2,0.2,0.2,0.2,0.1,0.5,1.1,-0.4,-0.6,0.5,1.3,1.4,1.6,1.8,1.8,1.8,1.7,1.1,1.3,1.4,1.4,1.4,1.4,1.4,1.4,1.3,1.3,2.2,2.5,2.5,2.5,2.5,2.4,2.4,2.4],
  yinTop: [5.2,5.2,5.2,5.2,5.2,5.2,5.2,5.2,5.2,5.2,5.2,5.2,5.1,5.1,5,4.8,4.7,4.7,4.6,4.6,4.5,4.5,4.6,4.7,5.1,5.5,5.7,6,6.1,6.2,6.3,6.4,6.4,6.5,6.5,6.5,6.6,6.6,6.6,6.6,6.6,6.6,6.5,6.4,6.1,5.8,5.5,5.2,5.1,4.9,4.8,4.8,4.8,4.9,5.2,5.6,5.8,6,6.2,6.3,6.4,6.4,6.5,6.5,6.5,6.5,6.6,6.6,6.6,6.6,6.6,6.6,6.6,6.6,6.4,5.9,5.5,5.2,5,4.8,4.7,4.6],
  yangBot: [-4.3,-4.3,-4.3,-4.3,-4.3,-4.3,-4.3,-4.3,-4.3,-4.3,-4.3,-4.3,-4.3,-4.4,-4.4,-4.5,-4.6,-4.6,-4.7,-4.7,-4.7,-4.8,-4.8,-4.9,-5.1,-5.3,-5.6,-5.7,-5.8,-5.9,-5.9,-6,-6,-6,-5.9,-5.8,-5.8,-5.7,-5.7,-5.6,-5.6,-5.6,-5.5,-5.5,-5.4,-5.3,-5.1,-5.1,-5,-4.9,-4.9,-4.9,-5,-5.3,-5.4,-5.6,-6,-6.4,-6.8,-7.2,-7.5,-7.7,-7.9,-8,-7.9,-7.9,-7.9,-8,-8,-8,-8,-8,-8,-8,-7.9,-7.7,-7.5,-7.4,-7.2,-7.1,-7,-6.9],
  diseaseModes: [null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null],
  elArr: [0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.315,0.352,0.369,0.352,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.3,0.303,0.403,0.446,0.483,0.514,0.539,0.561,0.577,0.588,0.661,0.676,0.664,0.654,0.697,0.696,0.682,0.67,0.659,0.643,0.623,0.6,0.578,0.561,0.546,0.534,0.525,0.518],
  // 事件
  events: [{"day":19710,"age":54,"type":"手术","label":"右乳腺癌手术+化放疗","direction":"发散","isMedical":true,"damage":{"fire":12,"metal":10,"water":3}},{"day":20075,"age":55,"type":"药物","label":"阿那曲唑5年","direction":"发散","isMedical":true,"damage":{"fire":8}},{"day":23360,"age":64,"type":"手术","label":"左乳腺癌手术","direction":"发散","isMedical":true,"damage":{"metal":5,"water":3,"fire":3}},{"day":24820,"age":68,"type":"手术","label":"尿道上皮癌手术","direction":"发散","isMedical":true,"damage":{"water":8,"metal":4}},{"day":25185,"age":69,"type":"窗口期","label":"丙午年双火·补火窗口","direction":"收敛"},{"day":25915,"age":71,"type":"转大运","label":"转入丙辰大运·火土补火","direction":"收敛"}],
  healthyZone: { min: -10, max: +10, label: 'SPUM 健康区间 (动态)' },
};
