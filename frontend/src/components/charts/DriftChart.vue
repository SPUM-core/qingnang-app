<template>
  <div ref="el" class="drift-chart" :style="{ height }"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, onActivated, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  series: { type: Array, default: () => [] },
  height: { type: String, default: '280px' }
})

const el = ref(null)
let chart = null
let ro = null

const WUXING_COLORS = {
  wood: '#43A047',
  fire: '#D84315',
  earth: '#D4A017',
  metal: '#90A4AE',
  water: '#0288D1'
}
const COLOR_TEXT = '#6B7277'
const COLOR_GRID = '#EAEAE4'
const COLOR_AXIS = '#9AA0A5'

const render = () => {
  if (!chart) return
  const dims = ['wood', 'fire', 'earth', 'metal', 'water']
  const labels = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
  const times = props.series.map((p) => p.t)

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(26, 77, 69, 0.95)',
      borderColor: '#1A4D45',
      textStyle: { color: '#fff', fontSize: 12 }
    },
    legend: {
      bottom: 0,
      textStyle: { color: COLOR_TEXT, fontSize: 12 },
      itemWidth: 18, itemHeight: 3,
      icon: 'roundRect'
    },
    grid: { left: 44, right: 16, top: 20, bottom: 52 },
    xAxis: {
      type: 'category',
      data: times,
      axisLine: { lineStyle: { color: COLOR_AXIS } },
      axisLabel: { color: COLOR_AXIS, fontSize: 11, rotate: 0 },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: 'ΔV 漂移',
      nameTextStyle: { color: COLOR_AXIS, fontSize: 12 },
      axisLine: { show: false },
      axisLabel: { color: COLOR_AXIS, fontSize: 11 },
      splitLine: { lineStyle: { color: COLOR_GRID, type: 'dashed' } }
    },
    series: dims.map((k) => ({
      name: labels[k],
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      showSymbol: props.series.length <= 12,
      lineStyle: { width: 2, color: WUXING_COLORS[k] },
      itemStyle: { color: WUXING_COLORS[k], borderColor: '#fff', borderWidth: 1 },
      areaStyle: props.series.length <= 8 ? {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: WUXING_COLORS[k] + '33' },
          { offset: 1, color: WUXING_COLORS[k] + '05' }
        ])
      } : undefined,
      data: props.series.map((p) => p.delta?.[k] ?? null)
    }))
  })
}

const onResize = () => chart?.resize()

const attachResizeObserver = () => {
  if (!el.value || ro) return
  ro = new ResizeObserver(() => onResize())
  ro.observe(el.value)
}

const tryInit = async () => {
  await nextTick()
  if (!el.value) return
  for (let i = 0; i < 10; i++) {
    const w = el.value.clientWidth
    const h = el.value.clientHeight
    if (w > 0 && h > 0) break
    await new Promise(r => setTimeout(r, 50))
  }
  if (chart) return
  chart = echarts.init(el.value)
  attachResizeObserver()
  render()
}

onMounted(async () => {
  await tryInit()
  window.addEventListener('resize', onResize)
})

onActivated(async () => {
  if (!chart) {
    await tryInit()
  } else {
    nextTick(() => { chart.resize(); render() })
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  ro?.disconnect()
  ro = null
  chart?.dispose()
  chart = null
})

watch(() => props.series, () => {
  if (chart) render()
  else tryInit()
}, { deep: true })
</script>

<style scoped>
.drift-chart { width: 100%; }
</style>
