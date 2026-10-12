<template>
  <div class="panel-adjust" data-page-id="TP01">
    <!-- ═══ 方案卡片 ═══ -->
    <div v-if="data?.plan" class="adj-plan-card">
      <div class="adj-plan-left">
        <div class="adj-plan-name">{{ data.plan.name }}</div>
        <div class="adj-plan-meta">
          开始 {{ data.plan.start_date }}
          <span class="adj-plan-status" :class="data.plan.status">{{ statusLabel }}</span>
        </div>
      </div>
      <div class="adj-plan-right">
        <div class="adj-metric">
          <div class="adj-metric-val" :class="improvementClass">{{ data.comparison?.total_shift?.toFixed(1) || '—' }}</div>
          <div class="adj-metric-label">净改善量</div>
        </div>
        <div class="adj-metric">
          <div class="adj-metric-val">{{ data.comparison?.disease_days_projected || 0 }}→{{ data.comparison?.disease_days_actual || 0 }}</div>
          <div class="adj-metric-label">疾病天数</div>
        </div>
      </div>
    </div>

    <!-- ═══ 调节对比图（虚线 vs 实线）═══ -->
    <div ref="el" class="adj-chart"></div>

    <!-- ═══ 图例 + 说明 ═══ -->
    <div class="adj-legend">
      <span class="adj-legend-item"><span class="adj-legend-line dashed"></span>自然发展（反事实）</span>
      <span class="adj-legend-item"><span class="adj-legend-line solid"></span>青囊介入（实测）</span>
      <span class="adj-legend-item"><span class="adj-legend-dot"></span>介入事件</span>
    </div>

    <!-- ═══ 介入事件列表 ═══ -->
    <div v-if="data?.interventions?.length" class="adj-interventions">
      <div class="adj-block-title">⚗️ 青囊介入时间线</div>
      <div class="adj-timeline">
        <div v-for="(it, i) in data.interventions" :key="i" class="adj-tl-item">
          <div class="adj-tl-dot"></div>
          <div class="adj-tl-date">第 {{ it.day }} 天</div>
          <div class="adj-tl-label">{{ it.label }}</div>
          <div class="adj-tl-impact">预期改善 +{{ it.impact }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import { fs, watchFsScale } from '../../utils/scale'
import { chartPalette, watchThemeChange } from '../../utils/chartTheme'

const props = defineProps({
  data: { type: Object, default: null },
})

const el = ref(null)
let chart = null

const statusLabel = computed(() => ({
  ongoing: '进行中',
  completed: '已完成',
  paused: '暂停',
}[props.data?.plan?.status || 'ongoing']))

const improvementClass = computed(() => {
  const v = props.data?.comparison?.total_shift || 0
  if (v > 2) return 'good'
  if (v > 0) return 'slight'
  return 'neutral'
})

function render() {
  if (!chart || !props.data) return
  const pal = chartPalette()
  const d = props.data

  // 构建 ECharts series
  const projectedDrift = d.projected.driftData
  const actualDrift = d.actual.driftData
  const n = projectedDrift.length
  // 2026-10-08: 后端已接 v3 真实推演（年帧，age 优先于 day 显示）
  const times = d.projected.elems.map(e => (e.age != null ? `第${e.age}岁` : `第${e.day}天`))
  const yang = d.projected.yangBot   // 边界线
  const yin  = d.projected.yinTop

  // 介入事件 markPoint（映射到 actual 曲线的 idx）
  const interventionMarks = (d.interventions || []).map(it => ({
    coord: [it.idx, actualDrift[it.idx] ?? 0],
    symbol: 'diamond',
    symbolSize: 14,
    itemStyle: { color: '#FF6F00', borderColor: '#fff', borderWidth: 2 },
    label: { show: true, position: 'top', fontSize: fs(10), color: '#FF6F00', formatter: it.label },
  }))

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: pal.rgba('--qn-emerald-rgb', 0.95),
      borderColor: pal.primary,
      textStyle: { color: '#fff', fontSize: fs(12) },
      extraCssText: 'max-width:300px;',
      formatter: (params) => {
        let h = `<div style="font-weight:600;margin-bottom:6px;">${params[0].axisValue}</div>`
        for (const p of params) {
          if (p.seriesName === '健康区间') continue
          const marker = p.marker
          h += `<div style="display:flex;gap:8px;margin:2px 0;font-size:${fs(11)}px;">
            <span>${marker}${p.seriesName}</span>
            <span style="margin-left:auto;font-weight:600;">${p.data?.toFixed(1) ?? '—'}</span>
          </div>`
        }
        const i = params[0].dataIndex
        const diff = actualDrift[i] - projectedDrift[i]
        h += `<div style="margin-top:6px;border-top:1px dashed rgba(255,255,255,0.3);padding-top:4px;font-size:${fs(11)}px;">
          干预效果: ${diff >= 0 ? '+' : ''}${diff.toFixed(1)} ${diff > 0 ? '⬆️ 改善' : diff < 0 ? '⬇️ 恶化' : '持平'}
        </div>`
        return h
      },
    },
    legend: {
      data: ['自然发展', '青囊介入', '阴界', '阳界'],
      top: 0, textStyle: { color: pal.text, fontSize: fs(11) },
      itemWidth: 16, itemHeight: 10,
    },
    grid: { top: 36, left: 48, right: 16, bottom: 50 },
    xAxis: {
      type: 'category', data: times, boundaryGap: false,
      axisLine: { lineStyle: { color: pal.gridLine } },
      axisLabel: { color: pal.text, fontSize: fs(10), interval: Math.max(0, Math.floor(n / 8)) },
    },
    yAxis: {
      type: 'value',
      name: '体质偏移', nameTextStyle: { color: pal.text, fontSize: fs(11) },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: pal.gridLine, type: 'dashed' } },
      axisLabel: { color: pal.text, fontSize: fs(10) },
    },
    series: [
      // 阳界（虚线）
      {
        name: '阳界', type: 'line', smooth: true, symbol: 'none', z: 2,
        lineStyle: { width: 1.5, color: pal.primary, type: 'dashed', opacity: 0.5 },
        data: yang,
      },
      // 阴界（虚线）
      {
        name: '阴界', type: 'line', smooth: true, symbol: 'none', z: 2,
        lineStyle: { width: 1.5, color: pal.primary, type: 'dashed', opacity: 0.5 },
        data: yin,
      },
      // 自然发展（虚线 · 反事实）
      {
        name: '自然发展', type: 'line', smooth: true, symbol: 'none', z: 3,
        lineStyle: { width: 2.5, color: '#9AA0A5', type: 'dashed', opacity: 0.75 },
        data: projectedDrift,
        markLine: {
          silent: true, symbol: 'none',
          lineStyle: { color: pal.gridLine, type: 'solid' },
          data: [{ yAxis: 0, label: { show: false } }],
        },
      },
      // 青囊介入（实线 · 实测）
      {
        name: '青囊介入', type: 'line', smooth: true, symbol: 'circle', symbolSize: 5, z: 4,
        lineStyle: { width: 3, color: pal.primary },
        itemStyle: { color: pal.primary, borderColor: '#fff', borderWidth: 1 },
        areaStyle: { color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: pal.primary + '33' },
            { offset: 1, color: pal.primary + '05' },
          ],
        }},
        data: actualDrift,
        markPoint: { data: interventionMarks },
      },
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
.panel-adjust { }

/* ── 方案卡片 ── */
.adj-plan-card {
  background: var(--qn-surface, #fff); border-radius: 12px; padding: 14px 16px;
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 14px;
  border-left: 4px solid var(--qn-primary, #17534C);
}
.adj-plan-left { display: flex; flex-direction: column; gap: 4px; }
.adj-plan-name { font-size: 16px; font-weight: 700; color: var(--qn-ink); }
.adj-plan-meta { font-size: 11px; color: var(--qn-ink-3); display: flex; gap: 10px; align-items: center; }
.adj-plan-status {
  font-size: 10px; padding: 1px 6px; border-radius: 8px;
  background: rgba(23,83,76,0.15); color: var(--qn-primary, #17534C);
}
.adj-plan-status.ongoing { background: rgba(23,83,76,0.15); color: var(--qn-primary, #17534C); }
.adj-plan-status.completed { background: rgba(76,175,80,0.15); color: #4CAF50; }
.adj-plan-status.paused { background: rgba(249,168,37,0.15); color: #F9A825; }

.adj-plan-right { display: flex; gap: 18px; }
.adj-metric { text-align: center; }
.adj-metric-val {
  font-size: 18px; font-weight: 700; color: var(--qn-primary, #17534C);
}
.adj-metric-val.good { color: #4CAF50; }
.adj-metric-val.slight { color: #F9A825; }
.adj-metric-label { font-size: 10px; color: var(--qn-ink-3); }

/* ── 图表 ── */
.adj-chart { width: 100%; height: 300px; margin-bottom: 10px; }

/* ── 图例 ── */
.adj-legend {
  display: flex; gap: 16px; padding: 0 10px 12px;
  font-size: 11px; color: var(--qn-ink-2);
}
.adj-legend-item { display: flex; align-items: center; gap: 6px; }
.adj-legend-line { width: 20px; height: 2px; }
.adj-legend-line.dashed { background: repeating-linear-gradient(90deg, #9AA0A5 0 4px, transparent 4px 8px); }
.adj-legend-line.solid { background: var(--qn-primary, #17534C); }
.adj-legend-dot { width: 10px; height: 10px; border-radius: 2px; background: #FF6F00; transform: rotate(45deg); }

/* ── 介入时间线 ── */
.adj-block-title {
  font-size: 13px; font-weight: 600; color: var(--qn-ink); margin-bottom: 10px;
}
.adj-timeline {
  display: flex; flex-direction: column; gap: 0;
  border-left: 2px solid var(--qn-bg-2); padding-left: 18px; position: relative;
}
.adj-tl-item {
  position: relative; padding: 10px 12px; background: var(--qn-surface);
  border-radius: 8px; margin-bottom: 8px;
}
.adj-tl-dot {
  position: absolute; left: -23px; top: 14px;
  width: 10px; height: 10px; background: #FF6F00;
  border-radius: 50%; border: 2px solid var(--qn-surface);
}
.adj-tl-date { font-size: 11px; color: var(--qn-ink-3); }
.adj-tl-label { font-size: 13px; font-weight: 600; color: var(--qn-ink); margin: 2px 0; }
.adj-tl-impact { font-size: 11px; color: #4CAF50; font-weight: 500; }
</style>
