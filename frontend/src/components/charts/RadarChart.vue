<template>
  <div ref="el" class="radar-chart" :style="{ height }"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, onActivated, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  vBase: { type: Object, default: null },
  vObs: { type: Object, default: null },
  // v0.2 新增：健康区带（每维范围，默认为 40-60 对称区间）
  healthyZone: {
    type: Object,
    default: () => ({ min: 40, max: 60 })
  },
  height: { type: String, default: '320px' },
  hideLegend: { type: Boolean, default: false }
})

const el = ref(null)
let chart = null
let ro = null

const COLOR_BASE = '#1A4D45'        // 先天基底（细灰绿线）
const COLOR_OBS = '#A8442F'         // 当前观测（粗红线）
const COLOR_H_CENTER = '#7BC4A9'     // 健康区带中心（淡绿虚线圆）
const COLOR_H_ZONE = 'rgba(123, 196, 169, 0.06)'  // 健康区带填充
const COLOR_GRID = '#EAEAE4'
const COLOR_TEXT = '#6B7277'

const render = () => {
  if (!chart) return
  const dims = ['wood', 'fire', 'earth', 'metal', 'water']
  const labels = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
  const base = dims.map((k) => props.vBase?.[k] ?? null)
  const obs = dims.map((k) => props.vObs?.values?.[k] ?? props.vObs?.[k] ?? null)

  // 健康区带中心（理想值 50）
  const hCenter = dims.map(() => 50)

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
      splitNumber: 5,
      splitArea: {
        show: true,
        areaStyle: {
          // 健康区带（index 3-4 = 40-60）用淡绿色，其余淡灰
          color: [
            'rgba(245, 245, 240, 0.3)',
            'rgba(245, 245, 240, 0.3)',
            'rgba(123, 196, 169, 0.08)',  // 健康区带内
            'rgba(123, 196, 169, 0.12)',  // 健康区带内
            'rgba(245, 245, 240, 0.3)',
          ]
        }
      },
      splitLine: { lineStyle: { color: COLOR_GRID, type: 'dashed' } },
      axisLine: { lineStyle: { color: COLOR_GRID } }
    },
    series: [{
      type: 'radar',
      symbolSize: 6,
      data: [
        // 3. 健康区带中心（最浅，底层）
        {
          value: hCenter,
          name: '健康区带 H',
          symbol: 'none',
          lineStyle: { width: 1.5, color: COLOR_H_CENTER, type: 'dashed', opacity: 0.6 },
          areaStyle: { color: COLOR_H_ZONE },
          itemStyle: { color: COLOR_H_CENTER },
          emphasis: { disabled: true }
        },
        // 1. 先天基底（细淡线）
        ...(props.vBase ? [{
          value: base,
          name: '先天基底 S₀⁰',
          symbol: 'circle', symbolSize: 7,
          lineStyle: { width: 1.5, color: COLOR_BASE, opacity: 0.55 },
          areaStyle: { color: COLOR_BASE, opacity: 0.06 },
          itemStyle: { color: COLOR_BASE, borderColor: '#fff', borderWidth: 1.5 }
        }] : []),
        // 2. 当前观测（最粗，顶层）
        ...(props.vObs ? [{
          value: obs,
          name: '当前观测 V_obs',
          symbol: 'circle', symbolSize: 8,
          lineStyle: { width: 2.5, color: COLOR_OBS },
          areaStyle: { color: COLOR_OBS, opacity: 0.15 },
          itemStyle: { color: COLOR_OBS, borderColor: '#fff', borderWidth: 2 }
        }] : [])
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

watch(() => [props.vBase, props.vObs, props.healthyZone], () => {
  if (chart) render()
  else tryInit()
}, { deep: true })
</script>

<style scoped>
.radar-chart { width: 100%; }
</style>
