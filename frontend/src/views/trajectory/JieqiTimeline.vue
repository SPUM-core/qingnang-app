<template>
  <div class="panel-year">
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

    <!-- ═══ 五行强度堆叠柱状图 ═══ -->
    <div ref="el" class="yj-chart"></div>

    <!-- ═══ 五行强度汇总 ═══ -->
    <div class="yj-summary">
      <div v-for="w in wuxingTotals" :key="w.key" class="wx-bar-row">
        <span class="wx-label" :style="{ color: w.color }">{{ w.label }}</span>
        <div class="wx-bar-track">
          <div class="wx-bar-fill"
            :style="{
              width: Math.min(100, Math.abs(w.value) * 20) + '%',
              background: w.color,
              marginLeft: w.value < 0 ? 'auto' : '0',
              opacity: 0.85,
            }"
          ></div>
        </div>
        <span class="wx-value" :style="{ color: w.value >= 0 ? '#DA6C57' : '#4C90AF' }">
          {{ w.value >= 0 ? '+' : '' }}{{ w.value.toFixed(1) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import { WUXING_COLORS } from '../../utils/trajectory_contract'
import { fs, watchFsScale } from '../../utils/scale'
import { chartPalette, watchThemeChange } from '../../utils/chartTheme'

const props = defineProps({
  data: { type: Object, required: true },
})

const el = ref(null)
let chart = null

const WUXING_KEYS = ['wood', 'fire', 'earth', 'metal', 'water']
const WUXING_LABELS = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }

// 五行累计（24 节气该五行微调量之和）
const wuxingTotals = computed(() => {
  if (!props.data?.jieqi) return []
  const totals = WUXING_KEYS.map(k => ({ key: k, label: WUXING_LABELS[k], color: WUXING_COLORS[k].hex, value: 0 }))
  for (const j of props.data.jieqi) {
    for (const k of WUXING_KEYS) {
      totals.find(t => t.key === k).value += (j.wuxing_bias?.[k] || 0) + (j.liunian_impact?.[k] || 0) + (j.dayun_impact?.[k] || 0)
    }
  }
  return totals.map(t => ({ ...t, value: Math.round(t.value * 10) / 10 }))
})

function render() {
  if (!chart || !props.data?.jieqi?.length) return

  const pal = chartPalette()
  const jieqi = props.data.jieqi
  const xData = jieqi.map(j => j.name)

  // 每个五行的 24 点值：节气微调 + 流年加成 + 大运加成
  const wuxingSeries = WUXING_KEYS.map(k => ({
    name: WUXING_LABELS[k],
    type: 'bar',
    stack: 'total',
    barMaxWidth: 20,
    itemStyle: { color: WUXING_COLORS[k].hex, borderRadius: [2, 2, 0, 0] },
    data: jieqi.map(j => {
      const v = (j.wuxing_bias?.[k] || 0) + (j.liunian_impact?.[k] || 0) + (j.dayun_impact?.[k] || 0)
      return Math.round(v * 10) / 10
    }),
  }))

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: pal.rgba('--qn-emerald-rgb', 0.95),
      borderColor: pal.primary,
      textStyle: { color: '#fff', fontSize: fs(12) },
      formatter: (params) => {
        const j = jieqi[params[0].dataIndex]
        const liunian = Object.values(j.liunian_impact || {}).reduce((a, b) => a + b, 0)
        const dayun = Object.values(j.dayun_impact || {}).reduce((a, b) => a + b, 0)
        let h = `<div style="font-weight:600;margin-bottom:4px;">${j.name} · ${j.date}</div>`
        h += `<div style="font-size:${fs(10)}px;opacity:0.7;margin-bottom:6px;">
          真太阳时 ${j.true_solar_time} · 主五行 ${WUXING_COLORS[j.wuxing_main]?.label || j.wuxing_main}</div>`
        for (const p of params) {
          if (Math.abs(p.value) < 0.01) continue
          h += `<div style="display:flex;gap:8px;margin:2px 0;">
            <span style="color:${p.color};font-weight:600;">${p.marker}${p.seriesName}</span>
            <span style="margin-left:auto;">${p.value >= 0 ? '+' : ''}${p.value.toFixed(1)}</span>
          </div>`
        }
        h += `<div style="margin-top:6px;border-top:1px dashed rgba(255,255,255,0.3);padding-top:4px;font-size:${fs(10)}px;opacity:0.7;">
          流年叠加: ${liunian >= 0 ? '+' : ''}${liunian.toFixed(1)} · 大运叠加: ${dayun >= 0 ? '+' : ''}${dayun.toFixed(1)}
        </div>`
        return h
      },
    },
    legend: {
      data: WUXING_KEYS.map(k => WUXING_LABELS[k]),
      top: 0, right: 0,
      textStyle: { color: pal.text, fontSize: fs(11) },
      itemWidth: 12, itemHeight: 10,
    },
    grid: { top: 36, left: 40, right: 20, bottom: 60 },
    xAxis: {
      type: 'category',
      data: xData,
      axisLine: { lineStyle: { color: pal.gridLine } },
      axisLabel: {
        color: pal.text, fontSize: fs(9),
        interval: 0, rotate: 45,
      },
    },
    yAxis: {
      type: 'value',
      name: '五行强度', nameTextStyle: { color: pal.text, fontSize: fs(10) },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: pal.gridLine, type: 'dashed' } },
      axisLabel: { color: pal.text, fontSize: fs(10) },
    },
    series: wuxingSeries,
  })
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
  display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap;
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

.yj-chart { width: 100%; height: 280px; margin-bottom: 16px; }

.yj-summary {
  background: var(--qn-surface); border-radius: 10px; padding: 12px 14px;
  display: flex; flex-direction: column; gap: 6px;
}
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
</style>
