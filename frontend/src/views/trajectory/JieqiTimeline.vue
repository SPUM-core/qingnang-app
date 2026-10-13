<template>
  <div class="panel-year" data-page-id="TP03">
    <!-- ═══ 年视图头部 ═══ -->
    <div class="yj-header">
      <div class="yj-year-card">
        <span class="yj-cy">{{ data?.calendar_year }} 年</span>
        <span class="yj-age">{{ data?.year_age }} 岁</span>
        <span class="yj-liunian">
          <span class="yj-gz">{{ data?.liunian?.name || '—' }}</span>
          <span class="yj-wx">流年</span>
        </span>
      </div>
      <div class="yj-dayun-card">
        <span class="yj-dayun-label">所在大运</span>
        <span class="yj-dayun-gz">{{ data?.dayun_active?.name || '—' }}</span>
        <span class="yj-dayun-range">{{ data?.dayun_active?.start }}-{{ data?.dayun_active?.end }}岁</span>
      </div>
    </div>

    <!-- ═══ Wuxing-FB 年度摘要（v3 新增 · 最脆维提示）═══ -->
    <div v-if="isWxFb" class="yj-wx-summary">
      <div class="yj-wx-card" :class="worstTag.cls">
        <span class="yj-wx-icon">⚠️</span>
        <span class="yj-wx-label">最脆方向</span>
        <span class="yj-wx-dim">{{ worstTag.dimLabel }}</span>
        <span class="yj-wx-star">u*={{ worstTag.uStar }}</span>
      </div>
      <div class="yj-wx-card neutral">
        <span class="yj-wx-icon">⚗️</span>
        <span class="yj-wx-label">全年最弱</span>
        <span class="yj-wx-val">{{ overallWeakest }}</span>
      </div>
      <div class="yj-wx-card neutral">
        <span class="yj-wx-icon">📊</span>
        <span class="yj-wx-label">平均 u*</span>
        <span class="yj-wx-val">{{ avgUStar }}</span>
      </div>
    </div>

    <!-- ═══ 主图：v2 五行强度柱状图 + v3 s_wuxing 偏移曲线（双 Y 轴）═══ -->
    <div ref="el" class="yj-chart"></div>

    <!-- ═══ 五行强度汇总（v2 总量 + v3 s_wuxing 偏移）═══ -->
    <div class="yj-summary">
      <div class="yj-summary-title">
        <span>全年五行累积</span>
        <span v-if="isWxFb" class="yj-summary-sub">+ Wuxing-FB 相对偏移</span>
      </div>
      <div v-for="w in wuxingTotals" :key="w.key" class="wx-bar-row">
        <span class="wx-label" :style="{ color: w.color }">{{ w.label }}</span>
        <div class="wx-bar-track">
          <div class="wx-bar-fill"
            :style="{
              width: Math.min(100, Math.abs(w.v2_value) * 20) + '%',
              background: w.color,
              marginLeft: w.v2_value < 0 ? 'auto' : '0',
              opacity: 0.85,
            }"
          ></div>
        </div>
        <span class="wx-value" :style="{ color: w.v2_value >= 0 ? '#DA6C57' : '#4C90AF' }">
          {{ w.v2_value >= 0 ? '+' : '' }}{{ w.v2_value.toFixed(1) }}
        </span>
        <!-- v3 s_wuxing 全年均值（相对空间 ±1 量级，弱=负 → 带外） -->
        <span v-if="isWxFb" class="wx-s" :class="w.s_class">
          s={{ w.v3_s.toFixed(2) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import { WUXING_COLORS, WUXING_DIMS, WUXING_LABELS } from '../../utils/trajectory_contract'
import { fs, watchFsScale } from '../../utils/scale'
import { chartPalette, watchThemeChange } from '../../utils/chartTheme'

const props = defineProps({
  data: { type: Object, required: true },
})

const el = ref(null)
let chart = null

const DIM_CN = WUXING_LABELS

// ═══ v3 Wuxing-FB 信号检测 ═══
const jieqi = computed(() => props.data?.jieqi || [])
const isWxFb = computed(() =>
  jieqi.value.length > 0 && jieqi.value.some(j => j.zone && j.tolerance_u)
)

// 全年最弱方向（最脆维 = min_tolerance.u_star 最小的那个节气的 dim）
const worstTag = computed(() => {
  if (!isWxFb.value) return { cls: 'neutral', dimLabel: '—', uStar: '—' }
  let worst = null, minU = Infinity
  for (const j of jieqi.value) {
    if (j.min_tolerance && j.min_tolerance.u_star < minU) {
      minU = j.min_tolerance.u_star
      worst = j.min_tolerance.dim
    }
  }
  if (!worst) return { cls: 'neutral', dimLabel: '—', uStar: '—' }
  // 严重度分档
  const cls = minU < 0.5 ? 'critical' : minU < 1.0 ? 'warn' : 'neutral'
  return { cls, dimLabel: DIM_CN[worst], uStar: minU.toFixed(2) }
})

// 全年平均 u*（所有节气 mean_tolerance_u）
const avgUStar = computed(() => {
  if (!isWxFb.value) return '—'
  const arr = jieqi.value.map(j => {
    if (!j.tolerance_u) return null
    const vals = Object.values(j.tolerance_u).map(Number)
    return vals.reduce((a, b) => a + b, 0) / vals.length
  }).filter(v => v != null)
  if (!arr.length) return '—'
  return (arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(2)
})

// 全年最常 OUT/CRIT 的维度
const overallWeakest = computed(() => {
  if (!isWxFb.value) return '—'
  const counts = { wood: 0, fire: 0, earth: 0, metal: 0, water: 0 }
  for (const j of jieqi.value) {
    for (const [d, tag] of Object.entries(j.zone || {})) {
      if (tag === 'OUT' || tag === '实' || tag === '虚') counts[d] += 3
      else if (tag === 'CRIT' || tag === '临界') counts[d] += 1
    }
  }
  let worst = null, maxC = 0
  for (const d of WUXING_DIMS) {
    if (counts[d] > maxC) { maxC = counts[d]; worst = d }
  }
  return worst ? `${DIM_CN[worst]}（${maxC}次带外）` : '—'
})

// ═══ 五行汇总（v2 总量 + v3 s_wuxing 年均值）═══
const wuxingTotals = computed(() => {
  if (!jieqi.value.length) return []
  const out = WUXING_DIMS.map(k => ({
    key: k, label: WUXING_LABELS[k], color: WUXING_COLORS[k].hex,
    v2_value: 0, v3_s: 0, s_count: 0,
  }))
  for (const j of jieqi.value) {
    for (const k of WUXING_DIMS) {
      const row = out.find(r => r.key === k)
      row.v2_value += (j.wuxing_bias?.[k] || 0) + (j.liunian_impact?.[k] || 0) + (j.dayun_impact?.[k] || 0)
      if (j.s_wuxing && j.s_wuxing[k] != null) {
        row.v3_s += j.s_wuxing[k]
        row.s_count++
      }
    }
  }
  return out.map(r => {
    const v2 = Math.round(r.v2_value * 10) / 10
    const v3 = r.s_count > 0 ? r.v3_s / r.s_count : 0
    // s < -0.3 = 虚（弱 → 需补 · 橙色），s > 0.3 = 实（过旺 → 需泄 · 红色），中间 = 平（绿色）
    let s_class = 's-neutral'
    if (v3 < -0.3) s_class = 's-empty'
    else if (v3 > 0.3) s_class = 's-full'
    return { ...r, v2_value: v2, v3_s: v3, s_class }
  })
})

function render() {
  if (!chart || !jieqi.value.length) return
  const pal = chartPalette()
  const jq = jieqi.value
  const xData = jq.map(j => j.name)

  // ═══ v2 五行强度堆叠柱状图 ═══
  const wuxingSeries = WUXING_DIMS.map(k => ({
    name: WUXING_LABELS[k],
    type: 'bar',
    stack: 'total',
    barMaxWidth: 20,
    yAxisIndex: 0,
    itemStyle: { color: WUXING_COLORS[k].hex, borderRadius: [2, 2, 0, 0] },
    data: jq.map(j => {
      const v = (j.wuxing_bias?.[k] || 0) + (j.liunian_impact?.[k] || 0) + (j.dayun_impact?.[k] || 0)
      return Math.round(v * 10) / 10
    }),
  }))

  // ═══ v3 s_wuxing 相对偏移（各维 max|s| 代表该帧最脆维的偏移）═══
  // 语义：每帧 24 节气 → s_wuxing 五维 → 取 |s| 最大维的有符号值 = 该节气"体质偏移方向+强度"
  let driftS = null, sColors = null, zoneMarks = null
  if (isWxFb.value) {
    driftS = jq.map(j => {
      const s = j.s_wuxing || {}
      let maxAbs = 0, val = 0
      for (const k of WUXING_DIMS) {
        const v = s[k] || 0
        if (Math.abs(v) > maxAbs) { maxAbs = Math.abs(v); val = v }
      }
      return Math.round(val * 100) / 100
    })
    // markPoint：OUT/实/虚 → 大红点；CRIT/临界 → 橙点；s_wuxing max维 颜色
    zoneMarks = jq.map((j, i) => {
      const zone = j.zone || {}
      let worst = 2  // 2=安全
      for (const tag of Object.values(zone)) {
        if (tag === 'OUT' || tag === '实' || tag === '虚') worst = Math.min(worst, 0)
        else if (tag === 'CRIT' || tag === '临界') worst = Math.min(worst, 1)
      }
      if (worst === 2) return null
      return {
        coord: [i, driftS[i]],
        symbol: 'circle',
        symbolSize: worst === 0 ? 14 : 11,
        itemStyle: {
          color: worst === 0 ? '#E53935' : '#FFA726',
          borderColor: '#fff', borderWidth: 2,
        },
        label: { show: false },
      }
    }).filter(Boolean)
    sColors = jq.map((j, i) => {
      const s = j.s_wuxing || {}
      let maxAbs = 0, key = 'fire'
      for (const k of WUXING_DIMS) {
        const v = Math.abs(s[k] || 0)
        if (v > maxAbs) { maxAbs = v; key = k }
      }
      return WUXING_COLORS[key].hex
    })
  }

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: pal.rgba('--qn-emerald-rgb', 0.95),
      borderColor: pal.primary,
      textStyle: { color: '#fff', fontSize: fs(12) },
      extraCssText: 'max-width:320px;',
      formatter: (params) => {
        const j = jq[params[0].dataIndex]
        let h = `<div style="font-weight:600;margin-bottom:4px;">${j.name} · ${j.date}</div>`
        h += `<div style="font-size:${fs(10)}px;opacity:0.7;margin-bottom:6px;">
          真太阳时 ${j.true_solar_time || '—'} · 主五行 ${WUXING_COLORS[j.wuxing_main]?.label || j.wuxing_main}</div>`

        // v2 五行强度（只列非零）
        h += `<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:2px 10px;margin-bottom:4px;">`
        for (const p of params) {
          if (Math.abs(p.value) < 0.01) continue
          h += `<div><span style="color:${p.color};font-weight:600;">${p.marker}${p.seriesName}</span>
            <span style="margin-left:auto;float:right;">${p.value >= 0 ? '+' : ''}${p.value.toFixed(1)}</span></div>`
        }
        h += `</div>`

        // v3 Wuxing-FB 段
        if (isWxFb.value) {
          h += `<div style="border-top:1px dashed rgba(255,255,255,0.3);padding-top:4px;font-size:${fs(10)}px;line-height:1.5;">`
          // zone 状态
          const zone = j.zone || {}
          const outs = Object.entries(zone).filter(([d, z]) => z === 'OUT' || z === '实' || z === '虚').map(([d]) => DIM_CN[d])
          const crits = Object.entries(zone).filter(([d, z]) => z === 'CRIT' || z === '临界').map(([d]) => DIM_CN[d])
          if (outs.length) h += `<div style="color:#E53935;">⚠️ 带外：${outs.join('·')}</div>`
          if (crits.length) h += `<div style="color:#FFA726;">⚡ 临界：${crits.join('·')}</div>`
          // 最弱方向 u*
          if (j.min_tolerance) {
            h += `<div style="margin-top:2px;color:#B4433C;">最脆 ${DIM_CN[j.min_tolerance.dim]} · u*=${j.min_tolerance.u_star.toFixed(2)}</div>`
          }
          // gap 裕度
          if (j.gap) {
            const gaps = Object.entries(j.gap)
              .map(([d, g]) => `${DIM_CN[d]}:${g.toFixed(2)}`)
              .join(' ')
            h += `<div style="opacity:0.7;margin-top:2px;">gap = ${gaps}</div>`
          }
          // 虚实
          if (j.weak_virtual) {
            const wv = j.weak_virtual
            const parts = []
            if (wv['虚']?.length) parts.push(`<span style="color:#E57373;">虚:${wv['虚'].map(DIM_CN).join('·')}</span>`)
            if (wv['实']?.length) parts.push(`<span style="color:#DA6C57;">实:${wv['实'].map(DIM_CN).join('·')}</span>`)
            if (parts.length) h += `<div style="margin-top:2px;">${parts.join(' · ')}</div>`
          }
          h += `</div>`
        }

        return h
      },
    },
    legend: {
      data: [
        ...WUXING_DIMS.map(k => WUXING_LABELS[k]),
        ...(isWxFb.value ? ['体质偏移(s)'] : []),
      ],
      top: 0, right: 0,
      textStyle: { color: pal.text, fontSize: fs(11) },
      itemWidth: 12, itemHeight: 10,
    },
    grid: { top: 36, left: 40, right: isWxFb.value ? 50 : 20, bottom: 60 },
    xAxis: {
      type: 'category',
      data: xData,
      axisLine: { lineStyle: { color: pal.gridLine } },
      axisLabel: {
        color: pal.text, fontSize: fs(9),
        interval: 0, rotate: 45,
      },
    },
    yAxis: [
      {
        type: 'value',
        name: '五行强度', nameTextStyle: { color: pal.text, fontSize: fs(10) },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: pal.gridLine, type: 'dashed' } },
        axisLabel: { color: pal.text, fontSize: fs(10) },
      },
      // v3 右轴：s_wuxing 偏移（相对空间 ±1 量级，健康区间 ≈ [-0.3, +0.3]）
      ...(isWxFb.value ? [{
        type: 'value', position: 'right',
        min: -1.5, max: 1.5, interval: 0.5,
        name: 's 偏移', nameTextStyle: { color: '#DA6C57', fontSize: fs(10) },
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: {
          color: '#DA6C57', fontSize: fs(9),
          formatter: v => v.toFixed(1),
        },
        splitLine: { show: false },
      }] : []),
    ],
    series: [
      ...wuxingSeries,
      // v3 s_wuxing 相对偏移曲线（右轴）
      ...(isWxFb.value ? [{
        name: '体质偏移(s)',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        yAxisIndex: 1,
        z: 10,
        lineStyle: { width: 2.5, color: '#DA6C57', opacity: 0.85 },
        itemStyle: {
          color: (params) => sColors[params.dataIndex] || '#DA6C57',
          borderColor: '#fff', borderWidth: 1,
        },
        markLine: {
          silent: true, symbol: 'none',
          lineStyle: { color: 'rgba(218,108,87,0.4)', type: 'dashed', width: 1 },
          data: [
            { yAxis: 0.3, label: { show: true, position: 'insideEndTop', color: '#DA6C57', fontSize: fs(9), formatter: '+0.3 实界' } },
            { yAxis: -0.3, label: { show: true, position: 'insideEndBottom', color: '#4C90AF', fontSize: fs(9), formatter: '-0.3 虚界' } },
          ],
        },
        markPoint: {
          data: zoneMarks,
          symbolSize: 14,
        },
        data: driftS,
      }] : []),
    ],
  }, true)
}

function tryInit() {
  if (!el.value) return
  if (chart) { render(); return }
  chart = echarts.init(el.value)
  render()
  new ResizeObserver(() => chart?.resize()).observe(el.value)
}

onMounted(tryInit)
watch(() => props.data, () => render(), { deep: true })
watchFsScale(render)
watchThemeChange(render)
</script>

<style scoped>
.panel-year { }
.yj-header {
  display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap;
}
.yj-year-card, .yj-dayun-card {
  flex: 1; min-width: 140px;
  background: var(--qn-surface); border-radius: 10px; padding: 10px 14px;
  display: flex; flex-direction: column; gap: 4px;
}
.yj-cy { font-size: 18px; font-weight: 700; color: var(--qn-ink); }
.yj-age { font-size: 11px; color: var(--qn-ink-3); }
.yj-liunian { display: flex; align-items: baseline; gap: 6px; }
.yj-gz { font-size: 14px; font-weight: 600; color: var(--qn-primary, #17534C); }
.yj-wx { font-size: 10px; color: var(--qn-ink-3); }
.yj-dayun-label { font-size: 10px; color: var(--qn-ink-3); }
.yj-dayun-gz { font-size: 16px; font-weight: 600; color: var(--qn-ink); }
.yj-dayun-range { font-size: 11px; color: var(--qn-ink-2); }

/* v3 Wuxing-FB 年度摘要 */
.yj-wx-summary {
  display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap;
}
.yj-wx-card {
  flex: 1; min-width: 110px;
  background: var(--qn-surface); border-radius: 8px; padding: 8px 12px;
  display: flex; align-items: center; gap: 6px; font-size: 12px;
  border-left: 3px solid var(--qn-bg-2);
}
.yj-wx-card.neutral { border-left-color: var(--qn-primary, #17534C); }
.yj-wx-card.warn    { border-left-color: #FFA726; }
.yj-wx-card.critical { border-left-color: #E53935; background: rgba(229,57,53,0.06); }
.yj-wx-icon { font-size: 14px; }
.yj-wx-label { color: var(--qn-ink-3); font-size: 10px; }
.yj-wx-dim { font-weight: 700; color: var(--qn-ink); }
.yj-wx-star { font-size: 11px; color: var(--qn-ink-2); }
.yj-wx-val { font-weight: 700; color: var(--qn-primary, #17534C); }

.yj-chart { width: 100%; height: 320px; margin-bottom: 14px; }

.yj-summary {
  background: var(--qn-surface); border-radius: 10px; padding: 12px 14px;
  display: flex; flex-direction: column; gap: 6px;
}
.yj-summary-title {
  font-size: 11px; color: var(--qn-ink-3); font-weight: 600;
  display: flex; justify-content: space-between; align-items: baseline;
}
.yj-summary-sub { font-weight: 400; font-size: 10px; color: var(--qn-primary, #17534C); }

.wx-bar-row {
  display: flex; align-items: center; gap: 10px; font-size: 12px;
}
.wx-label { width: 20px; font-weight: 600; }
.wx-bar-track {
  flex: 1; height: 6px; background: var(--qn-bg-2); border-radius: 3px;
  position: relative;
}
.wx-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.wx-value { width: 48px; text-align: right; font-weight: 600; }
.wx-s {
  font-size: 11px; font-weight: 600; width: 70px; text-align: right;
}
.wx-s.s-neutral { color: var(--qn-primary, #17534C); opacity: 0.7; }
.wx-s.s-empty   { color: #E53935; }
.wx-s.s-full    { color: #FFA726; }
</style>
