/* ═══════════════════════════════════════════════════════════
   src/utils/trajectory_contract.js
   ═══════════════════════════════════════════════════════════
   
   体质曲线四视图 · 数据契约 + Mock 数据
   
   说明：
   - 此文件定义 4 个体质曲线视图的 API 返回数据结构
   - 每个视图暴露一个 mock 生成函数，返回与未来后端 API 完全对齐的数据
   - 后端接口就绪后，只需把 mock 替换成 API 调用，前端组件零改动
   
   四视图：
   1. LIFETIME  — 终身曲线（年粒度 · 大运+流年）
   2. YEAR      — 年视图（24 节气 × 五行属性）
   3. JIEQI     — 节气视图（属性卡片墙 · 暂不做曲线）
   4. ADJUST    — 调节视图（虚线=自然发展 vs 实线=青囊介入实测）
   
   依赖后端 User 模型字段（当前缺失，需补）：
   - birth_location  : string  出生地（如 "上海市"）
   - birth_longitude : float   出生地经度（东经，如 121.47）
   - birth_latitude  : float   出生地纬度（北纬，如 31.23）
   
   ═══════════════════════════════════════════════════════════ */


// ───────────────────────────────────────────────────────────
// 24 节气定义（固定顺序）
// 五行属性基于标准中医定义 + 微调量
// true_solar_offset 由经纬度计算：(birth_longitude - 120°) × 4 分钟/度
// ───────────────────────────────────────────────────────────
export const JIEQI_24 = [
  // name, 公历日期(近似), 主五行, 五行微调{wood,fire,earth,metal,water}
  ['立春', '02-04', 'wood',  { wood: +1.5, fire: +0.3, earth: 0,     metal: 0,     water: -0.3 }],
  ['雨水', '02-19', 'wood',  { wood: +1.2, fire: +0.5, earth: 0,     metal: 0,     water: -0.5 }],
  ['惊蛰', '03-06', 'wood',  { wood: +1.0, fire: +0.8, earth: 0,     metal: 0,     water: -0.8 }],
  ['春分', '03-21', 'wood',  { wood: +0.8, fire: +1.0, earth: 0,     metal: 0,     water: -1.0 }],
  ['清明', '04-05', 'wood',  { wood: +0.5, fire: +1.2, earth: +0.3,  metal: 0,     water: -1.2 }],
  ['谷雨', '04-20', 'earth', { wood: +0.3, fire: +1.3, earth: +1.0,  metal: 0,     water: -0.8 }],
  ['立夏', '05-06', 'fire',  { wood: 0,    fire: +1.5, earth: +0.5,  metal: 0,     water: -1.0 }],
  ['小满', '05-21', 'fire',  { wood: 0,    fire: +1.3, earth: +0.8,  metal: 0,     water: -0.8 }],
  ['芒种', '06-06', 'fire',  { wood: -0.2, fire: +1.2, earth: +1.0,  metal: 0,     water: -0.5 }],
  ['夏至', '06-21', 'fire',  { wood: -0.5, fire: +1.0, earth: +1.2,  metal: 0,     water: -0.3 }],
  ['小暑', '07-07', 'fire',  { wood: -0.8, fire: +0.8, earth: +1.3,  metal: 0,     water: 0 }],
  ['大暑', '07-23', 'earth', { wood: -1.0, fire: +0.5, earth: +1.5,  metal: 0,     water: +0.3 }],
  ['立秋', '08-07', 'metal', { wood: -0.8, fire: +0.3, earth: +1.2,  metal: +1.2,  water: 0 }],
  ['处暑', '08-23', 'metal', { wood: -0.5, fire: 0,    earth: +0.8,  metal: +1.5,  water: +0.3 }],
  ['白露', '09-08', 'metal', { wood: -0.3, fire: -0.2, earth: +0.5,  metal: +1.5,  water: +0.5 }],
  ['秋分', '09-23', 'metal', { wood: 0,    fire: -0.5, earth: +0.3,  metal: +1.3,  water: +0.8 }],
  ['寒露', '10-08', 'metal', { wood: +0.2, fire: -0.8, earth: 0,     metal: +1.0,  water: +1.0 }],
  ['霜降', '10-23', 'earth', { wood: +0.3, fire: -1.0, earth: +0.5,  metal: +0.8,  water: +0.8 }],
  ['立冬', '11-07', 'water', { wood: +0.5, fire: -1.2, earth: 0,     metal: +0.5,  water: +1.0 }],
  ['小雪', '11-22', 'water', { wood: +0.3, fire: -1.3, earth: -0.3,  metal: +0.3,  water: +1.2 }],
  ['大雪', '12-07', 'water', { wood: 0,    fire: -1.5, earth: -0.5,  metal: 0,     water: +1.5 }],
  ['冬至', '12-22', 'water', { wood: -0.3, fire: -1.5, earth: -0.8,  metal: -0.3,  water: +1.3 }],
  ['小寒', '01-06', 'water', { wood: -0.5, fire: -1.3, earth: -1.0,  metal: -0.5,  water: +1.2 }],
  ['大寒', '01-20', 'water', { wood: -0.3, fire: -1.0, earth: -0.8,  metal: -0.3,  water: +1.0 }],
]


// ═══════════════════════════════════════════════════════════
// 数据契约：四视图
// ═══════════════════════════════════════════════════════════

/**
 * 视图 1: LIFETIME — 终身曲线（年粒度）
 * 接口: GET /api/v1/cases/trajectories/year-view?end_age=81
 * 结构: 复用 trajectory_algorithm.build_year_view_v2() 返回值
 */

/**
 * 视图 2: YEAR — 年视图（某年 × 24 节气 · 纯五行属性）
 * 接口: GET /api/v1/cases/trajectories/jieqi-view?year_age=30
 * 返回结构（每年固定 24 条）:
 * {
 *   year_age: 30,                     // 该年年龄
 *   calendar_year: 2020,              // 公历年
 *   liunian: { gan:'庚', zhi:'子', name:'庚子' },  // 流年干支
 *   dayun_active: { gan:'己', zhi:'酉', name:'己酉', start:24, end:33 },  // 该年所在大运
 *   user_location: {                  // 用户出生地（用于真太阳时校正）
 *     city: '上海市', longitude: 121.47, latitude: 31.23,
 *     true_solar_offset_min: 6,      // (lon-120)*4 分钟/度
 *   },
 *   v_innate: { wood:17.5, fire:21.2, earth:15, metal:25, water:21.2 },
 *   jieqi: [                          // 固定 24 项
 *     {
 *       idx: 0,                        // 0-23
 *       name: '立春',                  // 节气名
 *       date: '2020-02-04',            // 公历日期
 *       month_day: '02-04',            // 月-日
 *       true_solar_time: '09:27+8',    // 真太阳时（含 offset）
 *       wuxing_main: 'wood',           // 主五行
 *       wuxing_bias: { wood:+1.5, ... }, // 节气五行微调量
 *       liunian_impact: { ... },       // 流年对该节气的五行加成
 *       dayun_impact: { ... },         // 大运对该节气的五行加成
 *     },
 *     ...×24
 *   ]
 * }
 */
export function mockYearView({ year_age = 30, longitude = 120.0, latitude = 30.0, city = '未知' } = {}) {
  const trueSolarOffsetMin = Math.round((longitude - 120.0) * 40) / 10  // 每度 4 分钟，保留 1 位小数
  const calendarYear = 1990 + year_age

  // 简化：用固定流年大运占位（后端 lunar_python 会精确排盘）
  const liunianGanZhi = ['庚午','辛未','壬申','癸酉','甲戌','乙亥','丙子','丁丑','戊寅','己卯','庚辰','辛巳','壬午','癸未','甲申','乙酉','丙戌','丁亥','戊子','己丑','庚寅','辛卯','壬辰','癸巳','甲午','乙未','丙申','丁酉','戊戌','己亥']
  const dayunGanZhi = ['辛巳','庚辰','己卯','戊寅','丁丑','丙子','乙亥','甲戌','癸酉','壬申']
  const liunianIdx = (year_age - 1) % liunianGanZhi.length
  const dayunIdx = Math.min(Math.floor((year_age - 1) / 10), 9)

  const jieqi = JIEQI_24.map(([name, md, wx, bias], i) => {
    // 简化：假设每个节气真太阳时 = 节气平均时间 + offset
    const hour = (6 + Math.floor(i * 20 / 60)) % 24
    const minute = Math.floor((i * 20) % 60)
    const sign = trueSolarOffsetMin >= 0 ? '+' : ''
    return {
      idx: i,
      name,
      date: `${calendarYear}-${md}`,
      month_day: md,
      true_solar_time: `${String(hour).padStart(2,'0')}:${String(minute).padStart(2,'0')}${sign}${trueSolarOffsetMin}`,
      wuxing_main: wx,
      wuxing_bias: { ...bias },
      liunian_impact: _mockLiunianImpact(liunianGanZhi[liunianIdx], wx),
      dayun_impact: _mockDayunImpact(dayunGanZhi[dayunIdx], wx),
    }
  })

  return {
    year_age,
    calendar_year: calendarYear,
    liunian: _splitGanZhi(liunianGanZhi[liunianIdx]),
    dayun_active: { ..._splitGanZhi(dayunGanZhi[dayunIdx]), start: dayunIdx * 10 + 1, end: (dayunIdx + 1) * 10 },
    user_location: {
      city,
      longitude,
      latitude,
      true_solar_offset_min: trueSolarOffsetMin,
    },
    v_innate: { wood: 17.5, fire: 21.2, earth: 15, metal: 25, water: 21.2 },
    jieqi,
  }
}


/**
 * 视图 3: JIEQI — 节气视图（纯属性卡片墙）
 * 与 YEAR 视图共用同一份数据，只是展示形式不同
 * 此视图暂不做体质曲线，只看五行属性
 */

/**
 * 视图 4: ADJUST — 调节视图（虚线 vs 实线）
 * 接口: GET /api/v1/cases/trajectories/adjustment-view
 * 返回结构:
 * {
 *   projected: {                // 自然发展（虚线 · 无青囊介入的反事实曲线）
 *     elems: [...],             // n 点
 *     driftData: [...],
 *     stateFlags: [...],
 *     yangBot: [...], yinTop: [...],
 *   },
 *   actual: {                   // 实际观测（实线 · 青囊介入后的真实走势）
 *     elems: [...],
 *     driftData: [...],
 *     stateFlags: [...],
 *     yangBot: [...], yinTop: [...],
 *   },
 *   interventions: [            // 青囊介入事件（markPoint）
 *     {
 *       idx: 45,                // 在 actual 数组中的索引
 *       day: 45,                // 天数
 *       type: 'acupuncture',    // 介入类型
 *       label: '针灸·曲池',     // 描述
 *       impact: +3.2,           // 预期改善量（相对于 projected）
 *     },
 *     ...
 *   ],
 *   plan: {                     // 当前青囊方案
 *     name: '健脾益气方案',
 *     start_date: '2024-06-01',
 *     end_date: null,
 *     expected_improvement: 12,   // 方案目标改善量
 *     actual_improvement: 8.7,    // 已实现改善量（actual - projected 在最新点的值）
 *     status: 'ongoing',          // ongoing / completed / paused
 *   },
 *   comparison: {               // 两条曲线的量化对比
 *     total_shift: +8.7,          // 实际改善总量
 *     disease_days_projected: 12, // 自然发展下的改善周期
 *     disease_days_actual: 3,     // 实际改善周期（介入后减少了）
 *     peak_reduction: 5.4,        // 尖峰高度降低
 *   }
 * }
 */
export function mockAdjustView() {
  // 生成自然发展（虚线）：向下漂移，偶尔穿出阴界
  const n = 60
  const elems = Array.from({ length: n }, (_, i) => ({
    day: i * 5,
    t: `第 ${i * 5} 天`,
    age: 30 + Math.floor(i * 5 / 365),
    wood: 45 + Math.sin(i * 0.2) * 3,
    fire: 42 + Math.cos(i * 0.15) * 3,
    earth: 52 + (i / n) * 6,   // 自然趋势：土逐渐旺
    metal: 50 + Math.sin(i * 0.3) * 2,
    water: 48 - (i / n) * 4,   // 自然趋势：水逐渐衰
  }))

  const driftD = elems.map(e =>
    Math.round((-(e.fire - 50) * 0.35 - (e.wood - 50) * 0.15
              + (e.water - 50) * 0.35 + (e.earth - 50) * 0.15) * 10) / 10
  )
  const yangBot = Array(n).fill(-8)
  const yinTop = Array(n).fill(+12)

  const stateFlags = driftD.map((d, i) => {
    if (d > yinTop[i] + 2) return 'disease'
    if (d > yinTop[i] - 3) return 'subhealthy'
    return 'healthy'
  })

  // 青囊介入（实线）：在 day=150 处开始上拉
  const startIdx = 30
  const improvedDrift = driftD.map((d, i) => {
    if (i < startIdx) return d
    const pull = Math.min(8, (i - startIdx) * 0.25)  // 渐进上拉
    return Math.max(-12, d - pull)
  })
  const improvedFlags = improvedDrift.map((d, i) => {
    if (d > yinTop[i] + 2) return 'disease'
    if (d > yinTop[i] - 3) return 'subhealthy'
    return 'healthy'
  })

  return {
    projected: {
      elems,
      driftData: driftD,
      stateFlags,
      yangBot, yinTop,
    },
    actual: {
      elems,   // 同一组观测点
      driftData: improvedDrift,
      stateFlags: improvedFlags,
      yangBot, yinTop,
    },
    interventions: [
      { idx: 30, day: 150, type: 'acupuncture', label: '针灸·足三里+曲池', impact: +3.2 },
      { idx: 40, day: 200, type: 'herb',        label: '四君子汤·7剂',      impact: +2.8 },
      { idx: 50, day: 250, type: 'diet',       label: '饮食调理·忌生冷',    impact: +2.7 },
    ],
    plan: {
      name: '健脾益气方案',
      start_date: '2024-06-01',
      end_date: null,
      expected_improvement: 12,
      actual_improvement: Math.round((driftD[startIdx] - improvedDrift[n-1]) * 10) / 10,
      status: 'ongoing',
    },
    comparison: {
      total_shift: Math.round((driftD[n-1] - improvedDrift[n-1]) * 10) / 10,
      disease_days_projected: stateFlags.filter(s => s === 'disease').length,
      disease_days_actual: improvedFlags.filter(s => s === 'disease').length,
      peak_reduction: Math.round((Math.max(...driftD) - Math.max(...improvedDrift)) * 10) / 10,
    },
  }
}


// ───────────────────────────────────────────────────────────
// 内部工具
// ───────────────────────────────────────────────────────────

function _splitGanZhi(name) {
  // '辛巳' → { gan:'辛', zhi:'巳', name:'辛巳' }
  return { gan: name[0], zhi: name[1], name }
}

function _mockLiunianImpact(liunianGanZhi, wx) {
  // 简化占位：流年干支主气给一个 ±0.5 的影响
  const map = {
    木: 'wood', 火: 'fire', 土: 'earth', 金: 'metal', 水: 'water',
  }
  const result = { wood: 0, fire: 0, earth: 0, metal: 0, water: 0 }
  // 简化：假设阳干年该五行+，阴干年-（占位，后端 lunar_python 精确计算）
  const gan = liunianGanZhi[0]
  const yangGans = ['甲','丙','戊','庚','壬']
  const yinGans  = ['乙','丁','己','辛','癸']
  const zhiWxMap = { '子':'water','丑':'earth','寅':'wood','卯':'wood','辰':'earth',
                     '巳':'fire','午':'fire','未':'earth','申':'metal','酉':'metal',
                     '戌':'earth','亥':'water' }
  const zhi = liunianGanZhi[1]
  const mainWx = zhiWxMap[zhi] || wx
  if (yangGans.includes(gan)) result[mainWx] = +0.5
  else if (yinGans.includes(gan)) result[mainWx] = -0.3
  return result
}

function _mockDayunImpact(dayunGanZhi, wx) {
  // 简化占位：大运主气给 ±0.8 的影响
  const result = { wood: 0, fire: 0, earth: 0, metal: 0, water: 0 }
  const zhiWxMap = { '子':'water','丑':'earth','寅':'wood','卯':'wood','辰':'earth',
                     '巳':'fire','午':'fire','未':'earth','申':'metal','酉':'metal',
                     '戌':'earth','亥':'water' }
  const zhi = dayunGanZhi[1]
  const mainWx = zhiWxMap[zhi] || wx
  result[mainWx] = +0.8
  return result
}


// ═══════════════════════════════════════════════════════════
// 五行色（给节气卡片 / 标签 用）
// ═══════════════════════════════════════════════════════════
export const WUXING_COLORS = {
  wood:  { hex: '#4DB6AC', light: '#B2DFDB', label: '木' },
  fire:  { hex: '#E57373', light: '#FFCDD2', label: '火' },
  earth: { hex: '#BCAAA4', light: '#EFEBE9', label: '土' },
  metal: { hex: '#90A4AE', light: '#CFD8DC', label: '金' },
  water: { hex: '#42A5F5', light: '#BBDEFB', label: '水' },
}


// ═══════════════════════════════════════════════════════════
// 五行维度常量（与后端 trajectory_algorithm/_constants.py 单一信源对齐）
// ═══════════════════════════════════════════════════════════

// 五维 key 顺序（与后端 DIMS 一致）
export const WUXING_DIMS = ['wood', 'fire', 'earth', 'metal', 'water']

// 中文标签映射
export const WUXING_LABELS = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }

// 健康凸多面体 H — 与后端 HEALTH_POLYTOPE 一致（单一信源：_constants.py）
export const HEALTH_POLYTOPE = {
  wood:  [35, 65],
  fire:  [30, 70],
  earth: [40, 60],
  metal: [38, 62],
  water: [35, 65],
}

// 健康中心（与后端 HEALTH_CENTROID 一致）
export const HEALTH_CENTROID = {
  wood: 50, fire: 50, earth: 50, metal: 50, water: 50,
}

// 阴阳投影权重（与后端 YY_W_YANG / YY_W_YIN 一致）
export const YY_W_YANG = { fire: 0.55, wood: 0.45 }
export const YY_W_YIN = { earth: 0.55, water: 0.45 }
