<template>
  <div ref="el" class="drift-chart" :style="bgStyle"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, onActivated, watch, nextTick, computed } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  trajectory: { type: Object, default: null },
  series: { type: Array, default: () => [] },
  height: { type: String, default: '320px' }
})

const el = ref(null)
let chart = null
let ro = null

// ═══════════════════════════════════════════════════════════
// 主题
// ═══════════════════════════════════════════════════════════
const C = {
  wood:  { label: '木', color: '#43A047' },
  fire:  { label: '火', color: '#E53935' },
  earth: { label: '土', color: '#F9A825' },
  metal: { label: '金', color: '#90A4AE' },
  water: { label: '水', color: '#1E88E5' },
}
const DIMS = ['wood', 'fire', 'earth', 'metal', 'water']
const NURBS = '#1A4D45'
const GRID = '#EAEAE4'
const AXIS = '#9AA0A5'
const TEXT = '#6B7277'

// ═══════════════════════════════════════════════════════════
// 坐标系约定
// ────────────────────────────────────────────────────────────
//   Y = 0 为中轴（完美阴阳平衡）
//   Y 正 (+) = 向下 = 阴偏（虚寒、收敛、下坠）
//   Y 负 (−) = 向上 = 阳偏（亢热、发散、上浮）
//
// 阴阳交合区间 = Y ∈ [ -yangMax, +yinMax ]
//   yangMax = 阳半带上限（负值的绝对值，向上延伸的极限）
//   yinMax  = 阴半带下限（正值，向下延伸的极限）
//
// 健康区间就是阴阳交合的"重叠带"——体质偏移曲线在里面游走
// 超出带 = 生病（急性/慢性）
// ═══════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════
// 阴阳分解的体质偏移（有符号）
//
// 每个五行向量 → 一个有符号的体质偏移标量：
//   负 = 阳偏（fire↑, wood↑ 发散）
//   正 = 阴偏（water↑, earth↑ 收敛）
//   0  = 完美中庸
//
// 权重：火 35% / 水 35% / 木 15% / 土 15% / 金 0%（中立）
// ═══════════════════════════════════════════════════════════
function signedDrift (elems) {
  if (!elems?.length) return []
  return elems.map(pt => {
    const d = {
      fire:  pt.fire  !== undefined ? pt.fire  - 50 : 0,
      wood:  pt.wood  !== undefined ? pt.wood  - 50 : 0,
      water: pt.water !== undefined ? pt.water - 50 : 0,
      earth: pt.earth !== undefined ? pt.earth - 50 : 0,
      metal: pt.metal !== undefined ? pt.metal - 50 : 0,
    }
    const yangContrib = -(d.fire * 0.35 + d.wood * 0.15)
    const yinContrib  =  (d.water * 0.35 + d.earth * 0.15)
    return Math.round((yangContrib + yinContrib) * 10) / 10
  })
}

// ═══════════════════════════════════════════════════════════
// 阴阳两轨健康区间（生命周期包络 + 先天偏斜 + 医疗冲击）
//
// 返回 yangLine[] / yinLine[] —— 两条独立轨迹
//   yangLine[i] = −yangMax_i  (负值，向上延伸的上限)
//   yinLine[i]  = +yinMax_i   (正值，向下延伸的下限)
//
// 健康区间就是这两条线之间的区域（围绕 Y=0）
//
// 生命周期：
//   0~16岁 成长期：阳半带 sigmoid 快速扩张 → 阳气充盛可到 -80
//                  阴半带缓慢扩张 → 阴基本不动
//   16~35岁 壮年期：阴阳都宽
//   35岁+ 衰老期：两线渐进向 0 收窄
//
// 先天偏斜（核心！）：
//   fire↓↓ → rawYangMax 极小 → 阳线收窄 = 虚火（阳不足却被迫上浮）
//   water↑↑ → rawYinMax 极大 = 阴过盛
//   先天越平衡 → 阴阳两线越对称
// ═══════════════════════════════════════════════════════════
function computeYinYangModel (elems, innate, events) {
  const n = elems.length
  if (n === 0) return { yangLine: [], yinLine: [], driftData: [], diseaseModes: [] }

  const baseFire = innate.fire ?? 50
  const baseWater = innate.water ?? 50
  const baseWood = innate.wood ?? 50
  const baseEarth = innate.earth ?? 50

  // ═══ 先天基础阴阳带宽（绝对值，单位 = Y 轴刻度）═══
  // 火=阳之源：fire 越高 → 先天阳气足 → yangMax 越大
  // fire↓↓ 严重 → rawYangMax 极小 → 阳线窄 = 虚火（真阳不足）
  // fire↑↑ 充足 → rawYangMax 大 → 阳线宽 = 真阳
  const rawYangMax = Math.max(4,
    (baseFire - 30) * 0.9 + (baseWood - 40) * 0.4)
  // water=阴之源：water 越高 → 先天阴液足 → yinMax 越大
  const rawYinMax = Math.max(4,
    (baseWater - 30) * 0.9 + (baseEarth - 40) * 0.4)

  // ═══ 成长期特殊（0-16岁阳气充盛）═══
  function growthFactor (age) {
    if (!age || age <= 0) return 0.05
    // 0→16 sigmoid 快速增长，16 岁封顶
    return Math.min(1, 1 - Math.exp(-age / 5))
  }
  // 阳的成长期更强（0→16 sigmoid 快速充盛，16岁可达 -80）
  function yangGrowth (age) {
    if (!age || age <= 0) return 0.05
    const g = 1 - Math.exp(-age / 5)
    if (age <= 16) return g * 2.5
    if (age <= 35) return 2.5 - (age - 16) * (0.7 / 19)   // 16岁 2.5 → 35岁 1.8
    const decay = Math.exp(-((age - 35) ** 2) / (2 * 28 * 28))
    return Math.max(0.15, 1.8 * decay)
  }
  // 阴的成长期温和（阴基本不动）
  function yinGrowth (age) {
    if (!age || age <= 0) return 0.1
    if (age <= 16) return 0.1 + (age / 16) * 0.6
    if (age <= 35) return 0.7 + (age - 16) * (0.3 / 19)
    const decay = Math.exp(-((age - 35) ** 2) / (2 * 28 * 28))
    return Math.max(0.15, 1.0 * decay)
  }

  // ═══ 医疗事件冲击（压缩阴阳两线）═══
  const damage = {}
  const recovery = {}
  for (const ev of events || []) {
    if (ev.surgery || ev.isMedical) {
      damage[ev.day] = ev.damage ?? 0.5
      recovery[ev.day] = ev.recoveryDays ?? 540
    }
  }

  // 逐点计算两条线
  const yangLine = []
  const yinLine = []

  for (let i = 0; i < n; i++) {
    const pt = elems[i]
    const age = pt.age ?? 30
    const day = pt.day ?? i

    // 生命周期包络
    const yg = yangGrowth(age)
    const yng = yinGrowth(age)

    // 带宽 = raw × 生命周期 × 先天偏斜
    let yangMax = rawYangMax * yg
    let yinMax  = rawYinMax  * yng

    // 事件冲击
    let shock = 1
    for (const [eday, dmg] of Object.entries(damage)) {
      const ed = parseInt(eday)
      const dur = recovery[eday]
      if (day >= ed && day < ed + dur) {
        const elapsed = day - ed
        const d = Math.exp(-elapsed / (dur / 3))
        shock = Math.min(shock, dmg + (1 - dmg) * (1 - d))
      }
    }
    yangMax = Math.max(yangMax * shock, 2)
    yinMax  = Math.max(yinMax  * shock, 2)

    // yangLine 是负值（向上延伸），yinLine 是正值（向下延伸）
    yangLine.push(-Math.round(yangMax * 10) / 10)
    yinLine.push( Math.round(yinMax  * 10) / 10)
  }

  // 体质偏移（有符号）
  const driftData = signedDrift(elems)

  // ═══ 疾病模式检测 ═══
  const diseaseModes = new Array(n).fill(null)
  for (let i = 0; i < n; i++) {
    const h = driftData[i]
    const yu = yangLine[i]   // 负值
    const yl = yinLine[i]    // 正值

    // 急性：单点超出区间
    if (h < yu - 2 || h > yl + 2) {
      diseaseModes[i] = 'acuteDeviation'
      continue
    }

    // 慢性：连续 3+ 点贴边
    let bc = 0
    for (let j = Math.max(0, i - 2); j <= Math.min(n - 1, i + 2); j++) {
      const hj = driftData[j]
      if ((hj >= yangLine[j] - 3 && hj <= yangLine[j] + 3) ||
          (hj >= yinLine[j] - 3 && hj <= yinLine[j] + 3)) bc++
    }
    if (bc >= 3) diseaseModes[i] = 'chronicBoundary'
  }

  // ═══ 先天主色（偏离 50 最远的那个五行的颜色）═══
  const dims = ['wood', 'fire', 'earth', 'metal', 'water']
  let dominant = 'wood', maxDev = 0
  for (const k of dims) {
    const dev = Math.abs((innate[k] ?? 50) - 50)
    if (dev > maxDev) { maxDev = dev; dominant = k }
  }
  const dominantColor = C[dominant].color
  const dominantLabel = C[dominant].label

  return { yangLine, yinLine, driftData, diseaseModes, rawYangMax, rawYinMax,
    dominantColor, dominantLabel, dominant }
}

const useNewMode = computed(() => !!props.trajectory)

// ═══ 动态背景（顶端先天五行色 → 中轴白 → 底端黑）═══
const dominantBg = ref('#1A4D45')   // 默认深绿
const bgStyle = computed(() => ({
  height: props.height,
  background: `linear-gradient(to bottom,
    ${dominantBg.value}33 0%,
    rgba(255,255,255,0) 50%,
    rgba(20,20,20,40%) 100%)`,
  borderRadius: 6,
}))

// ═══════════════════════════════════════════════════════════
// 渲染入口
// ═══════════════════════════════════════════════════════════
const render = () => {
  if (!chart) return
  useNewMode.value ? renderYinYang() : renderLegacy()
}

const PARADOX_LABELS = {
  earth_false_fullness: '土假性充盈（PPG+0.60≠真旺）',
  fire_empty_float: '火虚浮（PPG+0.62≠真亢）',
}

function renderYinYang () {
  const traj = props.trajectory
  // ═══ 版本检测: v1 或 v2 都走新算法路径（v2 后端仍返回 v1 兼容字段）═══
  const isSpumNew = (traj.algorithm === 'spum_computeHealthBounds_v1' ||
                     traj.algorithm === 'spum_computeHealthBounds_v2')
  const isSpumV2 = traj.algorithm === 'spum_computeHealthBounds_v2'

  // 新算法优先用 traj.elems，老算法用 traj.actual_elements
  const elems = isSpumNew ? (traj.elems || traj.actual_elements || [])
                          : (traj.actual_elements || [])
  const innate = isSpumNew ? (traj.v_innate || traj.innate_elements || {})
                           : (traj.innate_elements || {})
  const times = elems.map(p => {
    if (p.hhmm) return `${p.t}\n${p.hhmm}`
    return p.t || `D${p.day}`
  })
  const n = elems.length

  let yangLine, yinLine, driftData, diseaseModes, rawYangMax, rawYinMax,
    dominantColor, dominantLabel, dominant

  // ═══ v2 新增字段加载（后端并行返回）═══
  const slice = arr => (arr || []).slice(0, n)
  const sigmaTrend       = slice(traj.sigma_trend)        // [0, 1] 密度
  const healthScore      = slice(traj.health_score)       // [0, 1] 综合健康度
  const polytopeStatuses = slice(traj.polytope_statuses)  // IN/ON/OUT
  const violationDepths  = slice(traj.violation_depths)   // 越界深度
  const frameResidues    = slice(traj.frame_residues)     // 不完美残留

  if (isSpumNew) {
    // ═══════════════════════════════════════════════════════════
    // 新算法路径（v1 或 v2 后端都走这里）
    // 坐标系对齐：
    //   沙盒: driftData 正=阳偏(火↑), 老系统: driftData 正=阴偏(水↑)
    //   → driftData 翻转符号
    //   沙盒 yangBot ≤0, 老 yangLine ≤0; 沙盒 yinTop ≥0, 老 yinLine ≥0
    //   → 边界线符号一致，直接用
    // ═══════════════════════════════════════════════════════════
    driftData   = slice(traj.driftData).map(d => -d)   // 翻转！
    yangLine    = slice(traj.yangBot)                   // 直接用（负值）
    yinLine     = slice(traj.yinTop)                    // 直接用（正值）
    diseaseModes = slice(traj.diseaseModes)

    // 先天主色：偏离 50 最远的那个五行
    dominant = 'wood'; let maxDev = 0
    for (const k of DIMS) {
      const dev = Math.abs((innate[k] ?? 50) - 50)
      if (dev > maxDev) { maxDev = dev; dominant = k }
    }
    dominantColor = C[dominant].color
    dominantLabel = C[dominant].label
    rawYangMax = Math.abs(Math.min(...yangLine, 0))
    rawYinMax  = Math.max(...yinLine, 0)
  } else {
    // ═══ 老算法路径（不变）═══
    const r = computeYinYangModel(elems, innate, traj.events)
    yangLine = r.yangLine; yinLine = r.yinLine; driftData = r.driftData
    diseaseModes = r.diseaseModes; rawYangMax = r.rawYangMax; rawYinMax = r.rawYinMax
    dominantColor = r.dominantColor; dominantLabel = r.dominantLabel; dominant = r.dominant
  }

  // 颜色约定
  const AXIS_COLOR = '#1A4D45'

  // ═══ 注入先天主色到背景 ═══
  dominantBg.value = dominantColor

  // ═══ 固定边界（基于先天极值，中医调理的目标区间）═══
  const innateTop = -Math.round(rawYangMax * 10) / 10   // 上边界（阳极限，负值）
  const innateBot =  Math.round(rawYinMax  * 10) / 10   // 下边界（阴极限，正值）
  const innateWidth = innateBot - innateTop             // 中医调理的可用宽度

  // 事件 markLine（医疗事件 = 压缩带的冲击点）
  const medMarkLines = (traj.events || []).filter(ev => ev.surgery || ev.isMedical).map(ev => {
    const idx = elems.findIndex(p => p.day === ev.day)
    if (idx < 0) return null
    return {
      xAxis: idx,
      lineStyle: { color: '#C62828', type: 'dashed', width: 1.5, opacity: 0.7 },
      symbol: 'none',
      label: { show: true, position: 'start', color: '#C62828', fontSize: 9,
        fontWeight: 600, formatter: ev.label || ev.type },
    }
  }).filter(Boolean)

  // 体质偏移曲线上的事件 markPoint
  const evMarkPts = (traj.events || []).map(ev => {
    const idx = elems.findIndex(p => p.day === ev.day)
    if (idx < 0) return null
    let color
    if (ev.isParadox) color = '#FF6F00'
    else if (ev.surgery || ev.isMedical) color = '#C62828'
    else if (ev.isSideEffect) color = '#E65100'
    else color = '#546E7A'
    return {
      coord: [idx, driftData[idx] ?? 0],
      symbol: ev.surgery || ev.isMedical ? 'rect' : (ev.isParadox ? 'triangle' : 'pin'),
      symbolSize: ev.surgery || ev.isMedical ? 24 : (ev.isParadox ? 22 : 22),
      itemStyle: { color, borderColor: '#fff', borderWidth: 2 },
      label: { show: false }
    }
  }).filter(Boolean)

  const hasMedical = (traj.events || []).some(ev => ev.surgery || ev.isMedical)
  const bottomPad = 48 + (hasMedical ? 24 : 0)

  // 先天体质特征描述（tooltip 顶部）
  const innateTag = () => {
    const f = innate.fire ?? 50, w = innate.water ?? 50
    if (f < 45 && w > 55) return '先天火衰水旺（虚火/阴盛质）'
    if (f > 55 && w < 45) return '先天火旺水弱（实火/阳亢质）'
    if (f >= 48 && f <= 52 && w >= 48 && w <= 52) return '先天水火既济（和平质）'
    return '先天偏质'
  }

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(26, 77, 69, 0.95)',
      borderColor: '#1A4D45',
      textStyle: { color: '#fff', fontSize: 12 },
      axisPointer: { type: 'cross', lineStyle: { color: NURBS, opacity: 0.3 } },
      formatter: (params) => {
        const idx = params[0].dataIndex
        const pt = elems[idx]
        if (!pt) return ''
        let h = `<div style="font-weight:600;margin-bottom:6px;">第 ${pt.day} 天 · ${pt.t}`
        if (pt.hhmm) h += ` <span style="opacity:0.6;font-weight:400;font-size:11px;">${pt.hhmm}</span>`
        h += `</div>`
        if (pt.age) h += `<div style="font-size:11px;opacity:0.7;margin-bottom:2px;">年龄 ${pt.age} 岁 · ${innateTag()}</div>`
        if (pt.syndromeHint) h += `<div style="font-size:11px;opacity:0.8;margin-bottom:4px;font-style:italic;">${pt.syndromeHint}</div>`

        h += `<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:3px 10px;margin-bottom:6px;">`
        for (const k of DIMS) {
          const v = pt[k] ?? 50, dev = Math.round((v - 50) * 10) / 10
          const devC = dev > 0 ? '#F9A825' : dev < 0 ? '#1E88E5' : TEXT
          h += `<div><span style="color:${C[k].color};font-weight:700;">${C[k].label}</span> ${v.toFixed(1)} <span style="color:${devC};font-size:10px;">(${dev >= 0 ? '+' : ''}${dev})</span></div>`
        }
        h += `</div>`

        const hs = driftData[idx]
        const yu = yangLine[idx]   // 负
        const yl = yinLine[idx]    // 正
        const inZone = hs >= yu && hs <= yl

        // 阴阳方向
        let direction, dirColor
        if (hs > 3) { direction = '阳偏（亢热/上浮）'; dirColor = '#DA6C57' }
        else if (hs < -3) { direction = '阴偏（虚寒/下坠）'; dirColor = '#4C90AF' }
        else { direction = '阴阳交合（中轴附近）'; dirColor = '#7BC4A9' }

        h += `<div style="border-top:1px dashed rgba(255,255,255,0.25);padding-top:4px;">`
        h += `<strong>体质偏移:</strong> <span style="font-size:14px;">${hs?.toFixed(1) ?? '—'}</span> `
        if (hs > 0) h += `<span style="color:#DA6C57;font-size:10px;">↑阳(+${Math.abs(hs).toFixed(1)})</span>`
        else h += `<span style="color:#4C90AF;font-size:10px;">↓阴(${Math.abs(hs).toFixed(1)})</span>`
        const zoneTag = inZone
          ? `<span style="color:#7BC4A9;margin-left:6px;">健康区间内</span>`
          : `<span style="color:#E57373;margin-left:6px;">超出区间 ⚠️</span>`
        h += zoneTag + `<span style="font-size:11px;opacity:0.7;margin-left:4px;">区间 [${yu.toFixed(0)}, ${yl.toFixed(0)}]</span>`
        h += `</div>`

        // 疾病模式
        const dm = diseaseModes[idx]
        if (dm === 'acuteDeviation') {
          h += `<div style="margin-top:4px;padding:3px 6px;background:rgba(229,57,53,0.18);border-left:3px solid #E53935;border-radius:3px;font-size:11px;color:#E57373;">⚠️ 急性偏离：突发冲出阴阳交合区</div>`
        } else if (dm === 'subtleDeviation') {
          h += `<div style="margin-top:4px;padding:3px 6px;background:rgba(255,171,64,0.15);border-left:3px solid #FFAB40;border-radius:3px;font-size:11px;color:#FFAB40;">⚠️ 亚临床偏离：凸多面体触碰边界</div>`
        } else if (dm === 'chronicBoundary') {
          h += `<div style="margin-top:4px;padding:3px 6px;background:rgba(249,168,37,0.15);border-left:3px solid #F9A825;border-radius:3px;font-size:11px;color:#FFD54F;">⚠️ 慢性贴边：长期游离于边界</div>`
        }

        // ═══ v2 SPUM 理论数据段 ═══
        if (isSpumV2 && sigmaTrend.length) {
          const st = sigmaTrend[idx]
          const hs_v2 = healthScore[idx]
          const ps = polytopeStatuses[idx]
          const vd = violationDepths[idx]
          const fr = frameResidues[idx]

          let psColor = '#7BC4A9', psLabel = '健康多面体内'
          if (ps === 'ON') { psColor = '#FFAB40'; psLabel = '触碰边界' }
          else if (ps === 'OUT') { psColor = '#E53935'; psLabel = '越界' }

          h += `<div style="margin-top:6px;border-top:1px dashed rgba(255,255,255,0.2);padding-top:4px;">`
          h += `<div style="font-size:10px;opacity:0.6;margin-bottom:3px;">── SPUM v2 理论值 ──</div>`

          // σ + health_score 进度条
          h += `<div style="display:flex;align-items:center;gap:6px;font-size:11px;margin-bottom:2px;">`
          h += `<span style="color:#B2EBF2;width:50px;">健康度</span>`
          h += `<div style="flex:1;height:6px;background:rgba(255,255,255,0.15);border-radius:3px;overflow:hidden;">`
          h += `<div style="height:100%;width:${(hs_v2 * 100).toFixed(0)}%;background:linear-gradient(90deg,${hs_v2 > 0.6 ? '#7BC4A9' : hs_v2 > 0.3 ? '#FFAB40' : '#E53935'},${hs_v2 > 0.6 ? '#B2DFDB' : hs_v2 > 0.3 ? '#FFD54F' : '#EF9A9A'});border-radius:3px;"></div>`
          h += `</div>`
          h += `<span style="color:#fff;width:32px;text-align:right;">${(hs_v2 * 100).toFixed(0)}%</span>`
          h += `</div>`

          h += `<div style="display:flex;align-items:center;gap:6px;font-size:11px;margin-bottom:2px;">`
          h += `<span style="color:#B2EBF2;width:50px;">σ 密度</span>`
          h += `<div style="flex:1;height:6px;background:rgba(255,255,255,0.15);border-radius:3px;overflow:hidden;">`
          h += `<div style="height:100%;width:${(st * 100).toFixed(0)}%;background:linear-gradient(90deg,#4DB6AC,#80CBC4);border-radius:3px;"></div>`
          h += `</div>`
          h += `<span style="color:#fff;width:32px;text-align:right;">${st.toFixed(2)}</span>`
          h += `</div>`

          h += `<div style="font-size:10px;color:${psColor};margin-top:2px;">◆ 凸多面体: ${psLabel}${vd > 0 ? ` · 越界深度 ${vd.toFixed(1)}` : ''} · 帧残留 ${fr.toFixed(2)}</div>`
          h += `</div>`
        }

        // 虚火提示（阳半带极窄且 fire↓）
        if (rawYangMax < 8 && (innate.fire ?? 50) < 48) {
          h += `<div style="margin-top:4px;padding:3px 6px;background:rgba(218,108,87,0.15);border-left:3px solid #DA6C57;border-radius:3px;font-size:11px;color:#DA6C57;">🔥 虚火：先天阳不足，阳半带收窄</div>`
        }

        if (pt.paradoxFlags?.length) {
          h += `<div style="margin-top:4px;padding:4px 6px;background:rgba(255,111,0,0.2);border-left:3px solid #FF6F00;border-radius:3px;font-size:11px;">⚠️ 悖论态：`
          h += pt.paradoxFlags.map(f => PARADOX_LABELS[f] || f).join('；') + `</div>`
        }

        const evs = (traj.events || []).filter(e => e.day === pt.day)
        for (const ev of evs) {
          const ec = ev.surgery || ev.isMedical ? '#C62828'
            : ev.isParadox ? '#FF6F00'
            : ev.isSideEffect ? '#E65100'
            : '#546E7A'
          const evt = ev.surgery || ev.isMedical ? '🔬 西医' : ev.type
          h += `<div style="margin-top:4px;padding:3px 6px;background:rgba(255,255,255,0.08);border-left:3px solid ${ec};border-radius:3px;font-size:11px;">[${evt}] ${ev.label}</div>`
        }
        return h
      }
    },
    legend: {
      bottom: 0, textStyle: { color: TEXT, fontSize: 11 }, itemWidth: 12, itemHeight: 9,
      data: [
        { name: '体质偏移', itemStyle: { color: NURBS } },
        ...(isSpumV2 && healthScore.length
          ? [{ name: '健康度', itemStyle: { color: '#4DB6AC' } }] : []),
      ]
    },
    backgroundColor: 'transparent',
    grid: {
      left: 52,
      right: isSpumV2 && healthScore.length ? 48 : 16,   // v2 给右轴留空间
      top: 28,
      bottom: bottomPad
    },
    dataZoom: n > 4 ? [
      { type: 'slider', start: 0, end: 100, height: 20, bottom: 24, borderColor: AXIS,
        fillerColor: 'rgba(26,77,69,0.15)', handleStyle: { color: NURBS },
        textStyle: { color: TEXT, fontSize: 10 }, dataBackground: { lineStyle: { color: AXIS } } },
      { type: 'inside', start: 0, end: 100, zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false },
    ] : [],
    xAxis: {
      type: 'category', data: times, boundaryGap: false,
      axisLine: { lineStyle: { color: AXIS } },
      axisLabel: { color: AXIS, fontSize: 10, interval: Math.max(0, Math.floor(n / 8)) },
      axisTick: { show: false }
    },
    yAxis: [
      {
        type: 'value', inverse: false, min: -100, max: 100, interval: 20,
        name: '阳 ↑  |  阴 ↓',
        nameTextStyle: { color: AXIS, fontSize: 11, padding: [0, 0, 0, -30] },
        axisLine: { show: false },
        axisLabel: {
          color: AXIS, fontSize: 10,
          formatter: (v) => {
            if (v === 0) return '0 中轴'
            if (v > 0) return `+${v} 阳`
            return `${v} 阴`
          }
        },
        splitLine: { lineStyle: { color: GRID, type: 'dashed' } }
      },
      // v2 右轴: 健康度 [0, 1]
      ...(isSpumV2 && healthScore.length ? [{
        type: 'value', position: 'right', min: 0, max: 1, interval: 0.25,
        name: '健康度', nameTextStyle: { color: '#4DB6AC', fontSize: 10 },
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: '#4DB6AC', fontSize: 9, formatter: v => (v * 100).toFixed(0) + '%' },
        splitLine: { show: false }
      }] : []),
    ],
    series: [
      // ═══ 阳界（动态虚线，0→16岁向下延伸，代表阳气充盛过程）═══
      {
        name: '阳界',
        type: 'line',
        smooth: true,
        symbol: 'none',
        showInLegend: false,
        lineStyle: { width: 1.5, color: dominantColor, type: 'dashed', opacity: 0.75 },
        data: yangLine,
        z: 5,
      },
      // ═══ 阴界（动态虚线，阴基本不动）═══
      {
        name: '阴界',
        type: 'line',
        smooth: true,
        symbol: 'none',
        showInLegend: false,
        lineStyle: { width: 1.5, color: dominantColor, type: 'dashed', opacity: 0.75 },
        data: yinLine,
        z: 5,
      },
      // ═══ 体质偏移曲线（西医治的就是这个波动）═══
      {
        name: '体质偏移',
        type: 'line',
        smooth: n > 1,
        symbol: n <= 1 ? 'circle' : 'none',
        symbolSize: 11,
        lineStyle: { width: 3.5, color: NURBS, opacity: 0.92 },
        itemStyle: { color: NURBS, borderColor: '#fff', borderWidth: 2 },
        data: driftData,
        z: 10,
        // ═══ markLine: 中轴 + 医疗事件（固定边界已改为 yangLine/yinLine series）═══
        markLine: {
          silent: true, symbol: 'none',
          label: { show: true, fontSize: 10, fontWeight: 600 },
          data: [
            // 中轴
            {
              yAxis: 0,
              lineStyle: { color: AXIS_COLOR, type: 'solid', width: 1.2, opacity: 0.8 },
              label: { position: 'insideStartTop', color: AXIS_COLOR, formatter: '中庸' }
            },
            // 医疗事件竖虚线
            ...medMarkLines,
          ]
        },
        markPoint: {
          symbol: 'circle',
          symbolSize: (idx) => {
            const m = diseaseModes[idx]
            if (m === 'acuteDeviation') return 14
            if (m === 'subtleDeviation') return 12
            if (m === 'chronicBoundary') return 12
            // v2: polytope ON/OUT 也显示小标记
            if (isSpumV2 && polytopeStatuses[idx] === 'OUT') return 10
            return 0
          },
          itemStyle: (params) => {
            const m = diseaseModes[params.dataIndex]
            if (m === 'acuteDeviation') return { color: '#E53935', borderColor: '#fff', borderWidth: 2 }
            if (m === 'subtleDeviation') return { color: '#FFAB40', borderColor: '#fff', borderWidth: 2 }
            if (m === 'chronicBoundary') return { color: '#F9A825', borderColor: '#fff', borderWidth: 2 }
            // v2: polytope OUT 用深红
            if (isSpumV2 && polytopeStatuses[params.dataIndex] === 'OUT')
              return { color: '#EF5350', borderColor: '#fff', borderWidth: 1.5 }
            return { color: 'transparent' }
          },
          label: { show: false },
          data: diseaseModes.map((m, i) => {
            if (m) return { coord: [i, driftData[i]] }
            // v2: polytope OUT 也标
            if (isSpumV2 && polytopeStatuses[i] === 'OUT' && !diseaseModes[i])
              return { coord: [i, driftData[i]] }
            return null
          }).filter(Boolean)
        },
      },
      // ═══ 事件 pin 叠层 ═══
      {
        name: '事件',
        type: 'line',
        smooth: false,
        symbol: 'none',
        showInLegend: false,
        lineStyle: { opacity: 0 },
        data: new Array(n).fill(null),
        z: 20,
        markPoint: {
          symbolKeepAspect: true,
          symbolSize: 22,
          label: { show: false },
          data: evMarkPts
        }
      },
      // ═══ v2: 健康度叠加层（右轴，半透明）═══
      ...(isSpumV2 && healthScore.length ? [{
        name: '健康度',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'none',
        showSymbol: false,
        lineStyle: { width: 2, color: '#4DB6AC', opacity: 0.55, type: 'solid' },
        areaStyle: { color: 'rgba(77,182,172,0.12)' },
        itemStyle: { color: '#4DB6AC' },
        data: healthScore,
        z: 3,
      }] : []),
    ]
  }, true)
}

function renderLegacy () {
  const labels = { wood:'木', fire:'火', earth:'土', metal:'金', water:'水' }
  const times = props.series.map(p => p.t)
  chart.setOption({
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(26,77,69,0.95)', borderColor: '#1A4D45', textStyle: { color: '#fff', fontSize: 12 } },
    legend: { bottom: 0, textStyle: { color: TEXT, fontSize: 12 }, itemWidth: 18, itemHeight: 3, icon: 'roundRect' },
    grid: { left: 44, right: 16, top: 20, bottom: 52 },
    xAxis: { type: 'category', data: times, axisLine: { lineStyle: { color: AXIS } }, axisLabel: { color: AXIS, fontSize: 11 }, axisTick: { show: false } },
    yAxis: { type: 'value', name: 'ΔV 漂移', axisLine: { show: false }, axisLabel: { color: AXIS, fontSize: 11 }, splitLine: { lineStyle: { color: GRID, type: 'dashed' } } },
    series: DIMS.map(k => ({
      name: labels[k], type: 'line', smooth: true, symbol: 'circle', symbolSize: 5,
      showSymbol: props.series.length <= 12,
      lineStyle: { width: 2, color: C[k].color }, itemStyle: { color: C[k].color, borderColor: '#fff', borderWidth: 1 },
      data: props.series.map(p => p.delta?.[k] ?? null)
    }))
  })
}

// ═══════════════════════════════════════════════════════════
// 生命周期
// ═══════════════════════════════════════════════════════════
const onResize = () => chart?.resize()
const attachRO = () => {
  if (!el.value || ro) return
  ro = new ResizeObserver(() => onResize()); ro.observe(el.value)
}
const tryInit = async () => {
  await nextTick()
  if (!el.value) return
  for (let i = 0; i < 10; i++) {
    if (el.value.clientWidth > 0 && el.value.clientHeight > 0) break
    await new Promise(r => setTimeout(r, 50))
  }
  if (chart) return
  chart = echarts.init(el.value); attachRO(); render()
}

onMounted(async () => { await tryInit(); window.addEventListener('resize', onResize) })
onActivated(async () => {
  if (!chart) await tryInit()
  else nextTick(() => { chart.resize(); render() })
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize); ro?.disconnect(); ro = null
  chart?.dispose(); chart = null
})

watch(() => props.trajectory, () => { chart ? render() : tryInit() }, { deep: true })
watch(() => props.series, () => { if (!useNewMode.value) chart ? render() : tryInit() }, { deep: true })
</script>

<style scoped>
.drift-chart { width: 100%; }
</style>
