<template>
  <div ref="el" class="drift-chart" :style="bgStyle"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, onActivated, watch, nextTick, computed } from 'vue'
import * as echarts from 'echarts'
import { fs, watchFsScale } from '../../utils/scale'
import { chartPalette, watchThemeChange } from '../../utils/chartTheme'

const props = defineProps({
  trajectory: { type: Object, default: null },
  series: { type: Array, default: () => [] },
  height: { type: String, default: '320px' }
})

const el = ref(null)
let chart = null
let ro = null

// ═══════════════════════════════════════════════════════════
// 主题色（每次 render 时从 chartPalette() 取最新值，
// 以支持暗色/亮色主题切换）
// ═══════════════════════════════════════════════════════════
let pal = null
function refreshPalette() {
  pal = chartPalette()
  // echarts 可读的颜色对象
  pal.C = {
    wood:  { label: '木', color: pal.wood },
    fire:  { label: '火', color: pal.fire },
    earth: { label: '土', color: pal.earth },
    metal: { label: '金', color: pal.metal },
    water: { label: '水', color: pal.water },
  }
  pal.NURBS = pal.primary
  pal.GRID = pal.gridLine
  pal.AXIS = pal.axisText
  pal.TEXT = pal.text
  pal.WHITE = pal.white
}
// 初始化一次（为了首次 render 前 pal 可用）
refreshPalette()
const DIMS = ['wood', 'fire', 'earth', 'metal', 'water']
// ⚠️ 注意：C/NURBS/GRID/AXIS/TEXT/WHITE 这些名字是在 render 函数内
// 通过 refreshPalette() 后重新 const { ... } = pal 解构获取的。
// 顶层不做一次性解构，避免 render 时拿到陈旧值。

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
const _prevMode = ref(null)   // 跟踪 renderYinYang/renderLegacy 切换，切换时强制 chart.clear()

// ═══ 动态背景（顶端先天五行色 → 中轴白 → 底端黑）═══
const dominantBg = ref('')   // 默认深绿，render 时由 refreshPalette 赋值
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
  const mode = useNewMode.value ? 'new' : 'legacy'
  if (_prevMode.value !== null && _prevMode.value !== mode) {
    chart.clear()   // ⚠️ 跨模式切换时强制清空：防 ECharts 内部 state（dataZoom/axis/graphic）残留
  }
  _prevMode.value = mode
  useNewMode.value ? renderYinYang() : renderLegacy()
}

const PARADOX_LABELS = {
  earth_false_fullness: '土假性充盈（PPG+0.60≠真旺）',
  fire_empty_float: '火虚浮（PPG+0.62≠真亢）',
}

function renderYinYang () {
  refreshPalette()
  const { C, NURBS, GRID, AXIS, TEXT, WHITE } = pal
  const rgba = pal.rgba
  const traj = props.trajectory
  // ═══ 版本检测: v1/v2/v3 都走新算法路径（v3 后端仍返回 v1 兼容字段）═══
  const isSpumNew = /spum_computeHealthBounds_v[123]/.test(traj.algorithm) || !!traj.elems
  const isSpumV2 = /spum_computeHealthBounds_v[23]/.test(traj.algorithm)  // v2 或 v3 → 有完整向量分析
  const _isYearView = !!traj._isYearView   // 年视图（LifetimePanel 终身推演）
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
    dominantColor, dominantLabel, dominant, stateFlags, spikeUp, spikeDown,
    spikeUp5d, spikeDown5d, velocityArr, directionArr, driftCenteredArr

  // ═══ v3 Wuxing-FB 信号检测 + gap 预计算（提前到 options 外面，避免嵌套三元让 parser 混淆）═══
  const slice = arr => (arr || []).slice(0, n)   // 必须先声明！gapData 要用到

  const wxFb = traj.wuxing_fb
  const isWxFb = !!(wxFb && wxFb.available && wxFb.tolerance_u_series?.length)

  // gap 每帧值 & tolerance_u* 天花板
  let gapData = null, avgUStar = null, driftWx = null
  if (isWxFb) {
    const tolSeries = wxFb.tolerance_u_series
    driftWx = slice(wxFb.driftData_wuxing) || []   // 相对空间 s 均值（后端已去 ×5）
    // 区间状态剖面：最差维 zone → 分数（IN=2 安全 / CRIT=1 紧张 / OUT=0 高危）
    // 语义 = 健康区间（分岔式判据），不再用 u*−sMean 的跨空间相减
    gapData = (wxFb.zone_series || []).slice(0, n).map(z => {
      const dims = z.zone || {}
      let worst = 2
      for (const d of Object.keys(dims)) {
        const tag = dims[d]
        const sc = tag === 'OUT' || tag === '实' || tag === '虚' ? 0 : tag === 'CRIT' || tag === '临界' ? 1 : 2
        if (sc < worst) worst = sc
      }
      return worst
    })
    avgUStar = tolSeries.reduce((s, t) => s + t.tolerance_u_star, 0) / tolSeries.length
  }
  // 阴阳投影层（tizhi-curve 借鉴 · 2026-10-09）：有符号阴阳偏移主曲线
  // 定义在函数作用域（tooltip formatter 也要用）；isSpumNew 分支消费
  const yyLayer = (isWxFb && wxFb.yin_yang && wxFb.yin_yang.drift_yy?.length)
    ? wxFb.yin_yang : null

  // v2 新增字段加载（后端并行返回）═══
  const sigmaTrend       = slice(traj.sigma_trend)        // [0, 1] 密度
  const healthScore      = slice(traj.health_score)       // [0, 1] 综合健康度
  const polytopeStatuses = slice(traj.polytope_statuses)  // IN/ON/OUT
  const violationDepths  = slice(traj.violation_depths)   // 越界深度
  const frameResidues    = slice(traj.frame_residues)     // 不完美残留

  // ═══ 大运 markArea + graphic 标签条准备（year-view 推演数据有 dayun）═══
  // 简化地支→五行映射（跟后端 Python ganzhi_main_elem 取地支主气一致）
  const ZHI_TO_ELEM = {
    0:'water', 1:'earth', 2:'wood', 3:'wood', 4:'earth', 5:'fire',
    6:'fire', 7:'earth', 8:'metal', 9:'metal', 10:'earth', 11:'water'
  }
  const DAYUN_ZHI = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
  const ganzhiMainElem = (gan, zhi) => {
    if (!zhi) return ''
    const zIdx = DAYUN_ZHI.indexOf(zhi)
    if (zIdx < 0) return ''
    return ZHI_TO_ELEM[zIdx]
  }

  // 大运数据（从顶层 traj.dayun 或每点 elem.dayun 推导）
  const dayunList = traj.dayun || []   // [{gan, zhi, start, end, name}]
  const hasDayunData = dayunList.length > 0 && elems.some(p => p.dayun)
  let dayunMarkArea = []
  let dayunLabels = []
  // ── 安全 hex → hex8/rgba（给 markArea 渐变加透明度）──
  const withAlpha = (color, alphaHex = '55') => {
    if (!color) return '#999999' + alphaHex
    // 6 位 hex → 8 位
    if (/^#[0-9a-fA-F]{6}$/.test(color)) return color + alphaHex
    // 3 位 hex → 6 位 → 8 位
    if (/^#[0-9a-fA-F]{3}$/.test(color)) {
      const h6 = '#' + color.slice(1).split('').map(c => c + c).join('')
      return h6 + alphaHex
    }
    // rgb/rgba → 转成 rgba 带 alpha
    const m = color.match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/)
    if (m) return `rgba(${m[1]},${m[2]},${m[3]},0.33)`
    return '#999999' + alphaHex   // fallback
  }

  if (hasDayunData) {
    // ⚠️ 后端 dayunMarkArea 是元数据（start_age/end_age），不是 ECharts 格式
    // 永远从 dayun 数组自己算（跟沙盒 L955-997 一样）
    const centers = dayunList.map(dy => {
      const midAge = (dy.start + dy.end) / 2
      const idx = elems.findIndex(p => (p.age ?? 0) >= midAge)
      return idx < 0 ? elems.length - 1 : idx
    })
    for (let i = 0; i < dayunList.length; i++) {
      const xStart = i === 0 ? 0 : centers[i - 1]
      const xEnd = i === dayunList.length - 1 ? n : centers[i]
      if (xEnd <= xStart) continue
      const dy = dayunList[i]
      const mainElem = ganzhiMainElem(dy.gan, dy.zhi)
      const cRight = C[mainElem]?.color || '#999999'
      const prevMainElem = ganzhiMainElem(dayunList[i-1]?.gan, dayunList[i-1]?.zhi)
      const cLeft = i === 0 ? cRight : (C[prevMainElem]?.color || cRight)
      const grad = new echarts.graphic.LinearGradient(0, 0, 1, 0, [
        { offset: 0, color: withAlpha(cLeft) },
        { offset: 1, color: withAlpha(cRight) },
      ])
      dayunMarkArea.push([
        { xAxis: xStart, itemStyle: { color: grad, borderWidth: 0 },
          label: { show: true, position: 'insideTop', distance: 4,
            formatter: dy.name, color: '#fff', fontSize: fs(9), fontWeight: 600,
            backgroundColor: rgba('--qn-emerald-rgb', 0.6), padding: [1, 6], borderRadius: 3 }
        },
        { xAxis: xEnd, label: { show: false } },
      ])
      dayunLabels.push({
        xStart, xEnd,
        name: dy.name,
        mainElem,
        dyColor: cRight,
        startAge: dy.start, endAge: dy.end,
      })
    }
  }

  // ─── 逐年流年五行色底图（年视图专用，借鉴 tizhi-curve 沙盒）───
  // 后端 elems[i].liunian_elem 已给出每年流年主气五行
  const liunianMarkArea = []
  if (_isYearView && n > 1) {
    for (let i = 0; i < n; i++) {
      const pt = elems[i]
      const elem = pt.liunian_elem || ganzhiMainElem(pt.liunian?.[0], pt.liunian?.[1])
      const color = C[elem]?.color || '#999999'
      liunianMarkArea.push([
        { xAxis: i, itemStyle: { color: withAlpha(color, '38'), borderWidth: 0 } },
        { xAxis: Math.min(i + 0.99, n - 1) },
      ])
    }
  }

  if (isSpumNew) {
    // ═══ DEBUG: 直接看到底拿到什么数据 ═══
    if (n > 0 || traj.algorithm) {
      console.log('[DriftChart DEBUG]', JSON.stringify({
        algorithm: traj.algorithm,
        n,
        dayun_list_len: (traj.dayun || []).length,
        elems0_has_dayun: !!(elems[0]?.dayun),
        hasDayunData,
        driftData_sample: (traj.driftData || []).slice(0, 5),
        yinTop_sample: (traj.yinTop || []).slice(0, 3),
        yangBot_sample: (traj.yangBot || []).slice(0, 3),
        stateFlags_sample: (traj.stateFlags || []).slice(0, 5),
        v_innate: traj.v_innate,
        _isYearView: traj._isYearView,
      }, null, 0))
    }

    // ═══════════════════════════════════════════════════════════
    //   → driftData 翻转符号
    //   沙盒 yangBot ≤0, 老 yangLine ≤0; 沙盒 yinTop ≥0, 老 yinLine ≥0
    //   → 边界线符号一致，直接用
    // ═══════════════════════════════════════════════════════════
    // 2026-10-09：v3 主图切换 —— 有 wuxing_fb.yin_yang（tizhi-curve 借鉴的
    // 阴阳投影：火木→阳 / 土水→阴，金只调弹性）时，用有符号阴阳偏移作主曲线：
    //   实线 = drift_yy（正=阳偏↑ 负=阴偏↓）
    //   黄/红虚线 = yy_bot/yy_top（逆转阈值 θ 投影 × 金弹性 × 生命周期包络）
    // 该区间为 2D 呈现层（判定仍在 5D zone_series，见 markPoint）
    if (yyLayer) {
      driftData = slice(yyLayer.drift_yy)   // 有符号阴阳偏移（相对空间 ±1 量级）
      yangLine  = slice(yyLayer.yy_bot)     // 负值（阳界）
      yinLine   = slice(yyLayer.yy_top)     // 正值（阴界）
    } else {
      driftData   = slice(traj.driftData).map(d => -d)   // 翻转！
      yangLine    = slice(traj.yangBot)                   // 直接用（负值）
      yinLine     = slice(traj.yinTop)                    // 直接用（正值）
    }
    diseaseModes = slice(traj.diseaseModes)

    // v2: 后端已返回三态 + 尖峰（坐标系与后端一致，无需翻转）
    stateFlags  = slice(traj.stateFlags)
    spikeUp     = slice(traj.spikeUp)      // 后端撞 yinTop（正）→ 前端正方向
    spikeDown   = slice(traj.spikeDown)    // 后端撞 yangBot（负）→ 前端负方向

    // 2026-10-10 新增：5D 触边尖峰 + 速度/方向 + S₀ 中心化漂移（后端 v2 增强字段）
    spikeUp5d     = slice(traj.spikeUp5d)
    spikeDown5d   = slice(traj.spikeDown5d)
    velocityArr   = slice(traj.velocity)
    directionArr  = slice(traj.direction)
    driftCenteredArr = slice(traj.driftCentered)

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
  const AXIS_COLOR = NURBS

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
      lineStyle: { color: C.fire, type: 'dashed', width: 1.5, opacity: 0.7 },
      symbol: 'none',
      label: { show: true, position: 'start', color: C.fire, fontSize: fs(9),
        fontWeight: 600, formatter: ev.label || ev.type },
    }
  }).filter(Boolean)

  // 体质偏移曲线上的事件 markPoint
  const evMarkPts = (traj.events || []).map(ev => {
    const idx = elems.findIndex(p => p.day === ev.day)
    if (idx < 0) return null
    let color
    if (ev.isParadox) color = rgba('--qn-cinnabar-rgb', 0.85)
    else if (ev.surgery || ev.isMedical) color = C.fire
    else if (ev.isSideEffect) color = rgba('--qn-cinnabar-rgb', 0.75)
    else color = AXIS
    return {
      coord: [idx, driftData[idx] ?? 0],
      symbol: ev.surgery || ev.isMedical ? 'rect' : (ev.isParadox ? 'triangle' : 'pin'),
      symbolSize: ev.surgery || ev.isMedical ? 24 : (ev.isParadox ? 22 : 22),
      itemStyle: { color, borderColor: WHITE, borderWidth: 2 },
      label: { show: false }
    }
  }).filter(Boolean)

  const hasMedical = (traj.events || []).some(ev => ev.surgery || ev.isMedical)
  // bottomPad: dataZoom slider + 底部 legend + 可选医疗事件区
  const bottomPad = 56 + (hasMedical ? 20 : 0)

  // ─── driftData 每点五行色（沙盒 L1142-1149）───
  // v3 路径：用 s_series 相对偏移（|s| 最大维）；v2 路径：先天偏差最大维
  const driftColors = elems.map((p, i) => {
    if (isWxFb && wxFb.s_series?.[i]) {
      const s = wxFb.s_series[i]
      let maxAbs = 0, key = 'fire'
      for (const k of DIMS) {
        const a = Math.abs(s[k] ?? 0)
        if (a > maxAbs) { maxAbs = a; key = k }
      }
      return C[key]?.color || NURBS
    }
    let maxDev = 0, key = 'fire'
    for (const k of DIMS) {
      const d = Math.abs((p[k] ?? 50) - (innate[k] ?? 50))
      if (d > maxDev) { maxDev = d; key = k }
    }
    return C[key]?.color || NURBS
  })

  // ─── yAxis 动态范围（沙盒 L1152-1154）───
  const allVals = [...yangLine, ...yinLine, ...driftData]
  const yMaxCalc = Math.max(5, Math.ceil(Math.max(...allVals) * 1.3))
  const yMinCalc = Math.min(-5, Math.floor(Math.min(...allVals) * 1.3))

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
      confine: true,               // ← 防越界到容器外
      backgroundColor: rgba('--qn-emerald-rgb', 0.95),
      borderColor: NURBS,
      textStyle: { color: WHITE, fontSize: fs(12) },
      axisPointer: { type: 'cross', lineStyle: { color: NURBS, opacity: 0.3 } },
      extraCssText: 'max-width:280px;line-height:1.45;',
      formatter: (params) => {
        const idx = params[0].dataIndex
        const pt = elems[idx]
        if (!pt) return ''
        let h = `<div style="font-weight:600;margin-bottom:6px;">第 ${pt.day} 天 · ${pt.t}`
        if (pt.hhmm) h += ` <span style="opacity:0.6;font-weight:400;font-size:${fs(11)}px;">${pt.hhmm}</span>`
        h += `</div>`
        if (pt.age) h += `<div style="font-size:${fs(11)}px;opacity:0.7;margin-bottom:2px;">年龄 ${pt.age} 岁 · ${innateTag()}</div>`
        if (pt.syndromeHint) h += `<div style="font-size:${fs(11)}px;opacity:0.8;margin-bottom:4px;font-style:italic;">${pt.syndromeHint}</div>`

        h += `<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:3px 10px;margin-bottom:6px;">`
        if (isWxFb && wxFb.s_series?.[idx]) {
          // v3：五行相对偏移（s 相对空间，θ=1.0 量级）
          const s = wxFb.s_series[idx]
          for (const k of DIMS) {
            const v = s[k] ?? 0, dev = Math.round(v * 100) / 100
            const devC = dev > 0 ? '#F9A825' : dev < 0 ? '#1E88E5' : TEXT
            h += `<div><span style="color:${C[k].color};font-weight:700;">${C[k].label}</span> <span style="font-size:${fs(10)}px;opacity:0.7;">相对偏移</span> <span style="color:${devC};">${dev >= 0 ? '+' : ''}${dev}</span></div>`
          }
        } else {
          for (const k of DIMS) {
            const v = pt[k] ?? 50, dev = Math.round((v - 50) * 10) / 10
            const devC = dev > 0 ? '#F9A825' : dev < 0 ? '#1E88E5' : TEXT
            h += `<div><span style="color:${C[k].color};font-weight:700;">${C[k].label}</span> ${v.toFixed(1)} <span style="color:${devC};font-size:${fs(10)}px;">(${dev >= 0 ? '+' : ''}${dev})</span></div>`
          }
        }
        h += `</div>`

        const hs = driftData[idx]
        const yu = yangLine[idx]   // 负
        const yl = yinLine[idx]    // 正
        const inZone = hs >= yu && hs <= yl

        // 阴阳方向（v3 阴阳投影为相对空间 ±1 量级，阈值用 0.3；v2 老量纲 ±3）
        const yyThresh = yyLayer ? 0.3 : 3
        let direction, dirColor
        if (hs > yyThresh) { direction = '阳偏（发散/浮越）'; dirColor = '#DA6C57' }
        else if (hs < -yyThresh) { direction = '阴偏（收敛/下坠）'; dirColor = '#4C90AF' }
        else { direction = '阴阳交合（中轴附近）'; dirColor = '#7BC4A9' }

        h += `<div style="border-top:1px dashed rgba(255,255,255,0.25);padding-top:4px;">`
        h += `<strong>体质偏移:</strong> <span style="font-size:${fs(14)}px;">${hs?.toFixed(2) ?? '—'}</span> `
        if (hs > 0) h += `<span style="color:#DA6C57;font-size:${fs(10)}px;">↑阳(+${Math.abs(hs).toFixed(2)})</span>`
        else h += `<span style="color:#4C90AF;font-size:${fs(10)}px;">↓阴(${Math.abs(hs).toFixed(2)})</span>`

        // ═══ 三态判定（v3 用 5D zone 分岔 / v2 用 stateFlags，fallback inZone）═══
        let zoneTag = ''
        const st = stateFlags?.[idx]  // ⚠️ 提前定义：L651 subhealthy 检查在 v3/v2 分支外，v3 路径也需要
        if (isWxFb) {
          const g = gapData?.[idx]
          if (g === 0) {
            zoneTag = `<span style="color:#E57373;margin-left:6px;">⚠️ 已越出逆转阈值（失衡态）</span>`
          } else if (g === 1) {
            zoneTag = `<span style="color:#FFA726;margin-left:6px;">⚠️ 临界（逼近逆转阈值）</span>`
          } else {
            zoneTag = `<span style="color:#7BC4A9;margin-left:6px;">健康区间内（生克制约在度）</span>`
          }
        } else {
          if (st === 'disease') {
            zoneTag = `<span style="color:#E57373;margin-left:6px;">⚠️ 已穿出有效边界（疾病态）</span>`
          } else if (st === 'subhealthy') {
            zoneTag = `<span style="color:#FFA726;margin-left:6px;">⚠️ 反复尖峰触边（亚健康态）</span>`
          } else if (st === 'healthy') {
            zoneTag = `<span style="color:#7BC4A9;margin-left:6px;">健康区间内（健康态）</span>`
          } else if (inZone) {
            zoneTag = `<span style="color:#7BC4A9;margin-left:6px;">健康区间内</span>`
          } else {
            zoneTag = `<span style="color:#E57373;margin-left:6px;">超出区间 ⚠️</span>`
          }
        }
        h += zoneTag + `<span style="font-size:${fs(11)}px;opacity:0.7;margin-left:4px;">区间 [${yu.toFixed(2)}, ${yl.toFixed(2)}]</span>`
        h += `</div>`

        // ═══ 尖峰触边细节（健康态本帧是尖峰也标记）═══
        const isSpike = spikeUp?.[idx] || spikeDown?.[idx]
        if (isSpike) {
          const spikeSrc5d = spikeUp5d?.[idx] || spikeDown5d?.[idx]
          const spikeDir = spikeUp?.[idx]
            ? `<span style="color:#DA6C57;">上撞阴界</span>`
            : `<span style="color:#4C90AF;">下撞阳界</span>`
          // 2026-10-10：弹回降级为子类型（金形弹性状态），不回弹=金形失职需干预
          let reboundTag = ''
          if (spikeSrc5d) {
            const reb = (spikeUp5d?.[idx] ? reboundUp?.[idx] : reboundDown?.[idx])
            reboundTag = reb
              ? `<span style="color:#7BC4A9;">弹回·金形弹性尚可</span>`
              : `<span style="color:#E57373;">未弹回·金形修剪不足</span>`
          }
          // ⚠️ 2D 路径（老算法）无后端弹回标记 → 不说弹回（之前硬编码 '→弹回' 误导）
          const spikeTail = reboundTag ? `·${reboundTag}` : (spikeSrc5d ? '' : '（2D EMA 路径无弹回判定）')
          h += `<div style="margin-top:4px;padding:3px 6px;background:rgba(249,168,37,0.15);border-left:3px solid #F9A825;border-radius:3px;font-size:${fs(11)}px;color:#FFD54F;">⚡ ${spikeDir}·快冲→触边${spikeTail}（${spikeSrc5d ? '5D健康多面体根判定' : '2D投影EMA路径'}）</div>`
        } else if (st === 'subhealthy') {
          let upHit = 0, dnHit = 0
          const wh = 2  // 窗口半宽（老算法路径 fallback）
          const wl = Math.max(0, idx - (adaptiveParams?.windowHalf ?? wh))
          const whh = Math.min(n - 1, idx + (adaptiveParams?.windowHalf ?? wh))
          for (let j = wl; j <= whh; j++) {
            if (spikeUp?.[j]) upHit++
            if (spikeDown?.[j]) dnHit++
          }
          const dirLabel = upHit >= dnHit ? `上撞阴界${upHit}次` : `下撞阳界${dnHit}次`
          h += `<div style="margin-top:4px;padding:3px 6px;background:rgba(249,168,37,0.15);border-left:3px solid #F9A825;border-radius:3px;font-size:${fs(11)}px;color:#FFD54F;">反复撞边弹回·${dirLabel}·金形弹性持续紧张（2D投影）</div>`
        }

        // ═══ 2026-10-10：速度/方向（S₀ 中心化漂移一阶差分）═══
        const vel = velocityArr?.[idx]
        if (vel != null) {
          const vDir = directionArr?.[idx]
          const vColor = vDir === 'up' ? '#DA6C57' : vDir === 'down' ? '#4C90AF' : TEXT
          const vLabel = vDir === 'up' ? '上行' : vDir === 'down' ? '下行' : '持平'
          h += `<div style="margin-top:2px;font-size:${fs(10)}px;opacity:0.8;">速度 <span style="color:${vColor};font-weight:600;">${vel >= 0 ? '+' : ''}${vel.toFixed(3)}</span> /帧 · ${vLabel}`
          if (driftCenteredArr?.[idx] != null) {
            const dc = driftCenteredArr[idx]
            h += ` · 中心化漂移 <span style="color:${dc >= 0 ? '#DA6C57' : '#4C90AF'};">${dc >= 0 ? '+' : ''}${dc.toFixed(3)}</span>`
          }
          h += `</div>`
        }

        // ═══ v2 SPUM 理论数据段（紧凑单行）═══
        if (isSpumV2 && sigmaTrend.length) {
          const st = sigmaTrend[idx]
          const hs_v2 = healthScore[idx]
          const ps = polytopeStatuses[idx]
          const vd = violationDepths[idx]

          let psColor = '#7BC4A9', psLabel = 'IN'
          if (ps === 'ON') { psColor = '#FFAB40'; psLabel = 'ON' }
          else if (ps === 'OUT') { psColor = '#E53935'; psLabel = 'OUT' }

          h += `<div style="margin-top:4px;border-top:1px dashed rgba(255,255,255,0.2);padding-top:3px;font-size:${fs(10)}px;display:flex;gap:6px;align-items:center;flex-wrap:wrap;">`
          h += `<span style="color:#B2EBF2;">健康 ${(hs_v2*100).toFixed(0)}%</span>`
          h += `<span style="color:#B2EBF2;">σ ${st.toFixed(2)}</span>`
          h += `<span style="color:${psColor};font-weight:600;">◆${psLabel}${vd>0?` ${vd.toFixed(1)}`:''}</span>`
          h += `</div>`
        }

        // ═══ v3 Wuxing-FB 信号段 ═══
        if (isWxFb && wxFb.tolerance_u_series?.[idx]) {
          const wxTol = wxFb.tolerance_u_series[idx]
          const wxZone = wxFb.zone_series?.[idx]?.zone || {}
          const wxWeak = wxFb.weak_virtual_series?.[idx] || {}
          const driftWxVal = wxFb.driftData_wuxing?.[idx]
          const sMean = driftWxVal != null ? Math.abs(driftWxVal) : 0   // 后端已去 ×5

          // 区间状态（最差维 zone）：OUT/实/虚=0 高危 · CRIT/临界=1 紧张 · IN=2 安全
          let worst = 2, worstDim = ''
          for (const d of Object.keys(wxZone)) {
            const tag = wxZone[d]
            const sc = tag === 'OUT' || tag === '实' || tag === '虚' ? 0 : tag === 'CRIT' || tag === '临界' ? 1 : 2
            if (sc < worst) { worst = sc; worstDim = d }
          }
          let gapColor = '#7BC4A9', gapState = '安全'
          if (worst === 0) { gapColor = '#E53935'; gapState = '高危' }
          else if (worst === 1) { gapColor = '#FFAB40'; gapState = '紧张' }
          const wxName = d => ({wood:'木',fire:'火',earth:'土',metal:'金',water:'水'}[d] || d)

          h += `<div style="margin-top:4px;border-top:1px dashed rgba(255,255,255,0.2);padding-top:3px;font-size:${fs(10)}px;line-height:1.5;">`
          h += `<span style="color:#7BC4A9;font-weight:600;">⚗️ Wuxing-FB</span> `
          h += `<span style="color:${gapColor};">区间=${gapState}${worstDim ? `（最脆 ${wxName(worstDim)}）` : ''}</span>`
          h += `<span style="color:#B4433C;margin-left:4px;">u*=${wxTol.tolerance_u_star.toFixed(2)}</span>`
          h += `<span style="opacity:0.7;margin-left:4px;">偏移=${sMean.toFixed(2)}</span>`

          // zone 带状态摘要（OUT/CRIT 的维度）
          const outs = Object.entries(wxZone).filter(([d, z]) => z === 'OUT' || z === '实' || z === '虚').map(([d]) => d)
          const crits = Object.entries(wxZone).filter(([d, z]) => z === 'CRIT' || z === '临界').map(([d]) => d)
          if (outs.length) h += `<span style="color:#E53935;margin-left:4px;">⚠️ 带外 ${outs.map(d => ({wood:'木',fire:'火',earth:'土',metal:'金',water:'水'}[d])).join('·')}</span>`
          if (crits.length) h += `<span style="color:#FFAB40;margin-left:4px;">⚡ 临界 ${crits.map(d => ({wood:'木',fire:'火',earth:'土',metal:'金',water:'水'}[d])).join('·')}</span>`
          h += `</div>`
        }

        // 虚火提示（阳半带极窄且 fire↓）
        if (rawYangMax < 8 && (innate.fire ?? 50) < 48) {
          h += `<div style="margin-top:4px;padding:3px 6px;background:rgba(218,108,87,0.15);border-left:3px solid #DA6C57;border-radius:3px;font-size:${fs(11)}px;color:#DA6C57;">🔥 虚火：先天阳不足，阳半带收窄</div>`
        }

        if (pt.paradoxFlags?.length) {
          h += `<div style="margin-top:4px;padding:4px 6px;background:rgba(255,111,0,0.2);border-left:3px solid #FF6F00;border-radius:3px;font-size:${fs(11)}px;">⚠️ 悖论态：`
          h += pt.paradoxFlags.map(f => PARADOX_LABELS[f] || f).join('；') + `</div>`
        }

        const evs = (traj.events || []).filter(e => e.day === pt.day)
        for (const ev of evs) {
          const ec = ev.surgery || ev.isMedical ? C.fire
            : ev.isParadox ? rgba('--qn-cinnabar-rgb', 0.85)
            : ev.isSideEffect ? rgba('--qn-cinnabar-rgb', 0.75)
            : AXIS
          const evt = ev.surgery || ev.isMedical ? '🔬 西医' : ev.type
          h += `<div style="margin-top:4px;padding:3px 6px;background:rgba(255,255,255,0.08);border-left:3px solid ${ec};border-radius:3px;font-size:${fs(11)}px;">[${evt}] ${ev.label}</div>`
        }
        return h
      }
    },
    legend: {
      bottom: 0, textStyle: { color: TEXT, fontSize: fs(11) }, itemWidth: 12, itemHeight: 9,
      data: [
        { name: '体质偏移', itemStyle: { color: NURBS } },
        ...(isWxFb && wxFb.tolerance_u_series?.length
          ? [{ name: '裕度 gap', itemStyle: { color: '#2E7D5B' } }]
          : (isSpumV2 && healthScore.length ? [{ name: '健康度', itemStyle: { color: NURBS } }] : [])),
      ]
    },
    // ═══ 年视图专属工具条：缩放/还原/导出 ═══
    toolbox: _isYearView ? {
      right: 8, top: 6,
      iconStyle: { borderColor: AXIS, opacity: 0.75 },
      feature: {
        dataZoom: { yAxisIndex: 'all', iconStyle: { borderColor: NURBS } },
        restore: { iconStyle: { borderColor: AXIS } },
        saveAsImage: { pixelRatio: 2, name: 'spum-trajectory-' + (props.trajectory?.birth_year || 'lifetime') },
      },
    } : undefined,
    backgroundColor: 'transparent',
    grid: {
      left: 52,
      right: (_isYearView || isSpumV2 && healthScore.length || isWxFb) ? 48 : 16,   // 年视图/右轴模式给右轴留空间
      top: 28,
      bottom: bottomPad
    },
    // ═══ 注：大运干支标签已用 markArea label 渲染（跟 dataZoom 同步缩放），不再用 graphic ═══
    graphic: [],
    // ═══ 缩放/拖动控制（只管 X 轴，Y 轴用户可直接拖动左边轴）═══
    // 年视图（82 点）默认只显示前 ~50 岁，避免全挤在一起
    dataZoom: n > 4 ? [
      // 底部水平拖动条（只管 X 轴）
      { type: 'slider',
        start: 0,
        end: _isYearView && n > 50 ? Math.round(50 / n * 100) : 100,
        height: 18, bottom: 24, borderColor: AXIS,
        fillerColor: rgba('--qn-emerald-rgb', 0.15), handleStyle: { color: NURBS },
        textStyle: { color: TEXT, fontSize: fs(10) }, dataBackground: { lineStyle: { color: AXIS } },
        labelFormatter: (v) => (elems[v]?.age ?? v) + '岁',
      },
      // 画布内：滚轮缩放 + 点击拖动平移（slider 和 inside 必须同 start/end 才不冲突）
      { type: 'inside',
        start: 0,
        end: _isYearView && n > 50 ? Math.round(50 / n * 100) : 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,     // 点击拖动平移
        moveOnMouseWheel: true,    // 触摸板双指平移
      },
    ] : [],
    xAxis: {
      type: 'category', data: times, boundaryGap: false,
      axisLine: { lineStyle: { color: AXIS } },
      axisLabel: {
        color: AXIS, fontSize: fs(9),
        // 年视图：两行（年龄 + 年份后两位），interval 后面 datazoom 事件动态调
        interval: _isYearView
          ? (n > 50 ? 5 : n > 30 ? 3 : n > 15 ? 2 : n > 8 ? 1 : 0)
          : Math.max(0, Math.floor(n / 6)),
        formatter: _isYearView ? (val, idx) => {
          const pt = elems[idx];
          if (!pt) return '';
          const age = pt.age ?? idx;
          const yy = (pt.t || '').split('·')[0].slice(-2);  // 1987 → 87
          return age + '\n' + yy;
        } : undefined,
        lineHeight: fs(10),
        margin: 16,
      },
      axisTick: { show: false }
    },
    yAxis: [
      {
        type: 'value', inverse: false,
        min: yMinCalc, max: yMaxCalc,
        interval: Math.max(1, Math.round((yMaxCalc - yMinCalc) / 5)),
        name: '',
        nameTextStyle: { color: AXIS, fontSize: fs(11) },
        axisLine: { show: false },
        axisLabel: {
          color: AXIS, fontSize: fs(10),
          formatter: (v) => {
            if (v === 0) return '中轴'
            if (v > 0) return `+${v}`   // 正值（阴方向，下方）
            return `${v}`               // 负值（阳方向，上方）
          }
        },
        splitLine: { lineStyle: { color: GRID, type: 'dashed' } }
      },
      // v2 右轴: 健康度 [0, 1] 或 v3: 区间状态剖面 (Wuxing-FB) — 用提前计算的变量避免嵌套三元
      ...(_isYearView ? [{
        type: 'value', position: 'right',
        min: 0, max: 100,
        interval: 25,
        name: '五行浓度',
        nameTextStyle: { color: TEXT, fontSize: fs(10) },
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: TEXT, fontSize: fs(9), formatter: '{value}' },
        splitLine: { show: false }
      }] : isWxFb ? [{
        type: 'value', position: 'right',
        min: 0,
        max: 2,
        interval: 1,
        name: '区间',
        nameTextStyle: { color: '#7BC4A9', fontSize: fs(10) },
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: '#7BC4A9', fontSize: fs(9), formatter: v => v === 2 ? '带内' : v === 1 ? '临界' : '带外' },
        splitLine: { show: false }
      }] : (isSpumV2 && healthScore.length ? [{
        type: 'value', position: 'right', min: 0, max: 1, interval: 0.25,
        name: '健康度', nameTextStyle: { color: NURBS, fontSize: fs(10) },
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: NURBS, fontSize: fs(9), formatter: v => (v * 100).toFixed(0) + '%' },
        splitLine: { show: false }
      }] : [])),
    ],
    series: [
      // ═══ 年视图：五条五行曲线（右轴 0~100，z=3 在 SPUM 曲线下方、markArea 上方）═══
      ...(_isYearView ? DIMS.map((k) => ({
        name: C[k].label,
        type: 'line', smooth: 0.5,
        symbol: 'none',
        showInLegend: true,
        lineStyle: { width: 1.6, color: C[k].color, opacity: 0.72 },
        itemStyle: { color: C[k].color },
        emphasis: { lineStyle: { width: 2.5, opacity: 1 } },
        data: elems.map(p => Math.round((p[k] ?? 50) * 10) / 10),
        yAxisIndex: 1,
        z: 3,
      })) : []),
      // ═══ 阳界（动态虚线）═══
      {
        name: '阳界',
        type: 'line',
        smooth: true,
        symbol: 'none',
        showInLegend: false,
        lineStyle: { width: 1.5, color: dominantColor, type: 'dashed', opacity: 0.75 },
        data: yangLine,
        z: 5,
        // 逐年流年底图 + 大运分段（年视图渲染）
        markArea: (liunianMarkArea.length || hasDayunData) ? {
          silent: true, label: { show: false },
          data: [
            ...(_isYearView ? liunianMarkArea : []),   // 最底层：逐年流年五行色
            ...(hasDayunData ? dayunMarkArea : []),    // 上层：大运分段渐变
          ],
        } : undefined,
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
        // 每点按偏离最大的五行上色（沙盒 L1142-1149）
        itemStyle: {
          color: (params) => driftColors[params.dataIndex] || NURBS,
          borderColor: WHITE, borderWidth: 2,
        },
        data: driftData,
        z: 10,
        // ═══ markLine: 中轴 + 医疗事件（固定边界已改为 yangLine/yinLine series）═══
        markLine: {
          silent: true, symbol: 'none',
          label: { show: true, fontSize: fs(10), fontWeight: 600 },
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
            // 2026-10-09：v3 主图判定层切 5D zone（逆转阈值分岔）
            // 0=带外(OUT/实/虚) → 大红点；1=临界(CRIT) → 橙点；2=带内 → 无
            if (isWxFb) {
              const g = gapData?.[idx]
              return g === 0 ? 14 : g === 1 ? 11 : 0
            }
            const dm = diseaseModes[idx]
            const st = stateFlags?.[idx]
            const isSpike = spikeUp?.[idx] || spikeDown?.[idx]
            // 疾病态最大
            if (st === 'disease' || dm === 'acuteDeviation') return 14
            if (dm === 'subtleDeviation') return 12
            // 尖峰标记
            if (isSpike) return 12
            if (st === 'subhealthy') return 12
            if (dm === 'chronicBoundary') return 12
            // v2: polytope ON/OUT
            if (isSpumV2 && polytopeStatuses[idx] === 'OUT') return 10
            return 0
          },
          itemStyle: (params) => {
            if (isWxFb) {
              const g = gapData?.[params.dataIndex]
              if (g === 0) return { color: C.fire, borderColor: WHITE, borderWidth: 2 }
              if (g === 1) return { color: rgba('--qn-earth-rgb', 0.9), borderColor: WHITE, borderWidth: 2 }
              return { color: 'transparent' }
            }
            const dm = diseaseModes[params.dataIndex]
            const st = stateFlags?.[params.dataIndex]
            const isSpike = spikeUp?.[params.dataIndex] || spikeDown?.[params.dataIndex]
            // 尖峰标记用橙色三角
            if (isSpike && st !== 'disease') {
              return { color: '#FFD54F', borderColor: '#F9A825', borderWidth: 2 }
            }
            if (st === 'disease' || dm === 'acuteDeviation') {
              return { color: C.fire, borderColor: WHITE, borderWidth: 2 }
            }
            if (dm === 'subtleDeviation' || st === 'subhealthy') {
              return { color: rgba('--qn-earth-rgb', 0.9), borderColor: WHITE, borderWidth: 2 }
            }
            if (dm === 'chronicBoundary') return { color: C.earth, borderColor: WHITE, borderWidth: 2 }
            if (isSpumV2 && polytopeStatuses[params.dataIndex] === 'OUT')
              return { color: C.fire, borderColor: WHITE, borderWidth: 1.5 }
            return { color: 'transparent' }
          },
          label: { show: false },
          data: isWxFb
            ? gapData.map((g, i) => (g < 2 ? { coord: [i, driftData[i]] } : null)).filter(Boolean)
            : diseaseModes.map((m, i) => {
              const st = stateFlags?.[i]
              const isSpike = spikeUp?.[i] || spikeDown?.[i]
              if (st === 'disease' || m === 'acuteDeviation' || m === 'subtleDeviation' || m === 'chronicBoundary' || isSpike)
                return { coord: [i, driftData[i]] }
              // v2: polytope OUT 也标
              if (isSpumV2 && polytopeStatuses[i] === 'OUT')
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
      // ═══ v2: 健康度叠加层（右轴，半透明）—— 只有 v3 没上时才显示健康度 ═══
      ...(!isWxFb && isSpumV2 && healthScore.length ? [{
        name: '健康度',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'none',
        showSymbol: false,
        lineStyle: { width: 2, color: NURBS, opacity: 0.55, type: 'solid' },
        areaStyle: { color: 'rgba(77,182,172,0.12)' },
        itemStyle: { color: NURBS },
        data: healthScore,
        z: 3,
      }] : []),
      // ═══ v3 Wuxing-FB: 区间状态剖面（副轴：2=带内 1=临界 0=带外）═══
      ...(isWxFb ? [{
        name: '区间状态',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'none',
        showSymbol: false,
        lineStyle: { width: 1.5, color: '#2E7D5B', opacity: 0.85, type: 'solid' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(46,125,91,0.40)' },     // 顶部绿（带内）
            { offset: 0.5, color: 'rgba(249,168,37,0.22)' },  // 中间黄（临界）
            { offset: 1, color: 'rgba(180,67,60,0.18)' },    // 底部红（带外）
          ])
        },
        itemStyle: { color: '#2E7D5B' },
        data: gapData,
        z: 4,
        markLine: {
          silent: true, symbol: 'none',
          label: { show: true, fontSize: fs(9), fontWeight: 700, position: 'insideEndTop', color: '#B4433C' },
          data: [{
            yAxis: 1,
            lineStyle: { color: '#B4433C', type: 'dashed', width: 1.5, opacity: 0.85 },
            label: { formatter: '临界下沿', color: '#B4433C' }
          }]
        },
        markArea: {
          silent: true,
          data: [[
            { yAxis: 0, itemStyle: { color: 'rgba(180,67,60,0.12)' } },
            { yAxis: 1 }   // 0~1 = 带外/临界高危带
          ]]
        }
      }] : []),
    ]
  }, true)

  // ═══ datazoom 事件：X 轴标签密度自适应 ═══
  if (_isYearView) {
    // 先解绑旧的（每次 renderYinYang 都重绑，防重复）
    chart.off('datazoom');
    let _dzLock = false;
    chart.on('datazoom', () => {
      if (_dzLock) return;
      _dzLock = true;
      try {
        const opt = chart.getOption();
        const dzArr = opt.dataZoom || [];
        const dz = dzArr.find(d => d.type === 'slider') || dzArr[0];
        const start = dz?.start ?? 0;
        const end = dz?.end ?? 100;
        const visible = Math.round(n * (end - start) / 100);
        let interval;
        if (visible > 50) interval = 5;
        else if (visible > 30) interval = 3;
        else if (visible > 15) interval = 2;
        else if (visible > 8) interval = 1;
        else interval = 0;
        chart.setOption({ xAxis: { axisLabel: { interval } } });
      } finally {
        setTimeout(() => { _dzLock = false; }, 0);
      }
    });
  }
}

function renderLegacy () {
  refreshPalette()
  const { C, NURBS, GRID, AXIS, TEXT, WHITE } = pal
  const rgba = pal.rgba
  const labels = { wood:'木', fire:'火', earth:'土', metal:'金', water:'水' }
  const times = props.series.map(p => p.t)
  chart.setOption({
    tooltip: { trigger: 'axis', backgroundColor: rgba('--qn-emerald-rgb', 0.95), borderColor: NURBS, textStyle: { color: WHITE, fontSize: fs(12) } },
    legend: { bottom: 0, textStyle: { color: TEXT, fontSize: fs(12) }, itemWidth: 18, itemHeight: 3, icon: 'roundRect' },
    grid: { left: 44, right: 16, top: 20, bottom: 52 },
    xAxis: { type: 'category', data: times, axisLine: { lineStyle: { color: AXIS } }, axisLabel: { color: AXIS, fontSize: fs(11) }, axisTick: { show: false } },
    yAxis: { type: 'value', name: 'ΔV 漂移', axisLine: { show: false }, axisLabel: { color: AXIS, fontSize: fs(11) }, splitLine: { lineStyle: { color: GRID, type: 'dashed' } } },
    series: DIMS.map(k => ({
      name: labels[k], type: 'line', smooth: true, symbol: 'circle', symbolSize: 5,
      showSymbol: props.series.length <= 12,
      lineStyle: { width: 2, color: C[k].color }, itemStyle: { color: C[k].color, borderColor: WHITE, borderWidth: 1 },
      data: props.series.map(p => p.delta?.[k] ?? null)
    }))
  }, true)   // ⚠️ notMerge=true：彻底替换 option，防止 lifetime 旧 series 残留叠画
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
  watchFsScale(() => {
    chart && chart.resize()
    render()
  })
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

watch(() => props.trajectory, async () => {
  await nextTick()
  // ECharts 5.5+ 要求 resize/setOption 不在 Vue 同步更新周期内
  // 再等一帧确保脱离 Vue scheduler 的 flush
  if (chart) setTimeout(() => { chart.resize(); render() }, 0)
  else await tryInit()
}, { deep: true })
watch(() => props.series, async () => {
  await nextTick()
  if (!useNewMode.value) {
    if (chart) setTimeout(render, 0)
    else await tryInit()
  }
}, { deep: true })
</script>

<style scoped>
.drift-chart { width: 100%; }
</style>
