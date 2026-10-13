// ═══════════════════════════════════════════════════════════
// almanac.js — 历法显示层共享工具
//
// 单一真源：时辰判定只在此实现一次。
// 原先 HeroDailyTipsCard.nowPeriod 与 AnchorTimelineCard.isNow
// 各写一遍 getHours()+range 匹配，且 fallback 一个取 tl[8]、一个取 tl[7]，
// 导致同一屏显示两个不同的"当令时辰"。现在统一。
// ═══════════════════════════════════════════════════════════

/**
 * 判断某个时辰是否为当前时辰。
 *
 * ⚠️ 已知局限：使用设备本地钟表时。本项目八字链路用真太阳时
 * （NOAA 均时差 + 经度修正），两者在经度偏离时可能相差 40 分钟以上。
 * 若要严谨，需由后端下发真太阳时当令时辰，此处只做本地兜底。
 *
 * @param {Object} period 时辰对象，需含 range（如 "23-1"）
 * @param {number} [hour] 传入小时可避免重复取时钟（便于测试）
 * @returns {boolean}
 */
export function isNowPeriod(period, hour) {
  if (!period || typeof period.range !== 'string') return false
  const h = typeof hour === 'number' ? hour : new Date().getHours()
  const [s, e] = period.range.split('-').map(Number)
  if (Number.isNaN(s) || Number.isNaN(e)) return false
  // 子时跨午夜（23-1）：s >= e
  if (s >= e) return h >= s || h < e
  return h >= s && h < e
}

/**
 * 找出当前时辰。
 * 无匹配时返回 null —— 不猜测、不 fallback 到固定时辰，
 * 避免在数据未就绪时把任意时辰显示成"当令"。
 */
export function findNowPeriod(timeline, hour) {
  const tl = Array.isArray(timeline) ? timeline : []
  return tl.find((item) => isNowPeriod(item, hour)) || null
}

/**
 * 时辰色类 → 中文标签。
 * 后端 personal_type 为主，降级到旧 type 字段。
 */
export function periodColorClass(period) {
  if (!period) return 'n'
  const pt = period.personal_type
  if (pt === 'good') return 'g'
  if (pt === 'bad') return 'b'
  if (pt === 'neutral') return 'w'
  const t = period.type
  if (t === 'good') return 'g'
  if (t === 'critical') return 'b'
  if (t === 'warn') return 'w'
  return 'n'
}

/** 五行 → 生我者。用于把"弱形"翻译成建议中该补的颜色/方位。 */
const SHENG = { wood: 'water', fire: 'wood', earth: 'fire', metal: 'earth', water: 'metal' }
const KE = { wood: 'metal', fire: 'water', earth: 'wood', metal: 'fire', water: 'earth' }
const WX_CN = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }

export function shengOf(elem) { return SHENG[elem] || '' }
export function keOf(elem) { return KE[elem] || '' }
export function wxName(elem) { return WX_CN[elem] || '' }

/**
 * 按飞星五行生成方位宜避话术。
 * 后端 reason 里写死了"九星叠位火气重，易上火"，与实际飞星无关
 * （飞星为水时也这么说），本函数按真实元素生成。
 */
export function buildDirAdvice({ feixingElem, dir, isGood, weakElem, strongElem }) {
  const fe = wxName(feixingElem) || '该'
  const wk = wxName(weakElem)
  const st = wxName(strongElem)
  if (!dir) return ''
  if (isGood) {
    if (weakElem && feixingElem === SHENG[weakElem]) {
      return `${fe}生${wk}形，此方气场有助。今日${dir}向为取气位，睡床可偏向此方。`
    }
    if (weakElem && feixingElem === weakElem) {
      return `${fe}与${wk}形同气，此方最宜。${dir}向可久坐、可安床。`
    }
    if (strongElem && feixingElem === SHENG[strongElem]) {
      return `${fe}生${st}形，而你${st}形已偏旺。此方气性偏助，仍可用${dir}向纳气，但不宜久居。`
    }
    return `${fe}气平和，${dir}向为宜居之方，可作为今日主要活动方位。`
  }
  if (strongElem && feixingElem === KE[strongElem]) {
    return `${fe}克${st}形，易助长你已偏旺的${st}气。${dir}向宜少停留。`
  }
  if (strongElem && feixingElem === strongElem) {
    return `${fe}与${st}形同气，叠加易过旺。${dir}向避免久坐或久居。`
  }
  return `此方与你的弱形无补益关系，${dir}向可作临时停留，不宜久处。`
}