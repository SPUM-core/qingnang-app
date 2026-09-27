<template>
  <div ref="el" class="radar-chart" :style="{ height }"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, onActivated, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  vBase: { type: Object, default: null },
  vObs: { type: Object, default: null },
  height: { type: String, default: '320px' },
  hideLegend: { type: Boolean, default: false }
})

const el = ref(null)
let chart = null
let ro = null

const COLOR_BASE = '#1A4D45'
const COLOR_OBS = '#A8442F'
const COLOR_GRID = '#EAEAE4'
const COLOR_TEXT = '#6B7277'

const render = () => {
  if (!chart) return
  const dims = ['wood', 'fire', 'earth', 'metal', 'water']
  const labels = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
  const base = dims.map((k) => props.vBase?.[k] ?? 0)
  const obs = dims.map((k) => props.vObs?.[k] ?? null)

  chart.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(26, 77, 69, 0.95)',
      borderColor: '#1A4D45',
      textStyle: { color: '#fff', fontSize: 12 }
    },
    legend: {
      show: !props.hideLegend,
      bottom: 0,
      textStyle: { color: COLOR_TEXT, fontSize: 12 },
      itemWidth: 14, itemHeight: 10
    },
    radar: {
      indicator: dims.map((k) => ({ name: labels[k], max: 100 })),
      radius: '62%',
      center: ['50%', '45%'],
      axisName: { color: COLOR_TEXT, fontSize: 13, fontWeight: 500 },
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(245, 245, 240, 0.5)', 'rgba(232, 232, 224, 0.5)'],
          borderWidth: 1
        }
      },
      splitLine: { lineStyle: { color: COLOR_GRID, type: 'dashed' } },
      axisLine: { lineStyle: { color: COLOR_GRID } }
    },
    series: [{
      type: 'radar',
      symbolSize: 6,
      data: [
        {
          value: base,
          name: '先天基底 S₀⁰',
          symbol: 'circle', symbolSize: 8,
          lineStyle: { width: 2, color: COLOR_BASE },
          areaStyle: { color: COLOR_BASE, opacity: 0.12 },
          itemStyle: { color: COLOR_BASE, borderColor: '#fff', borderWidth: 2 }
        },
        {
          value: obs,
          name: '当前观测 V_obs',
          symbol: 'circle', symbolSize: 8,
          lineStyle: { width: 2.5, color: COLOR_OBS, opacity: 0.85 },
          areaStyle: { color: COLOR_OBS, opacity: 0.18 },
          itemStyle: { color: COLOR_OBS, borderColor: '#fff', borderWidth: 2 }
        }
      ]
    }]
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
  attachResizeObserver()   // RO 必须在 chart 有了之后 attach
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

watch(() => [props.vBase, props.vObs], () => {
  if (chart) render()
  else tryInit()
}, { deep: true })
</script>

<style scoped>
.radar-chart { width: 100%; }
</style>
