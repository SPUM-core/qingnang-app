<template>
  <div ref="el" class="radar-chart" :style="{ height }"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, onActivated, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { fs, watchFsScale } from '../../utils/scale'
import { chartPalette, watchThemeChange } from '../../utils/chartTheme'

const props = defineProps({
  vBase: { type: Object, default: null },
  vObs: { type: Object, default: null },
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
let unwatchTheme = null

const render = () => {
  if (!chart) return
  const pal = chartPalette()
  const rgba = pal.rgba
  const WHITE = pal.white

  // 每次 render 取最新主题色
  const COLOR_BASE = pal.primary          // 先天基底
  const COLOR_OBS = pal.cinnabar          // 当前观测
  const COLOR_H_CENTER = pal.primaryAccent // 健康区带中心（淡绿虚线）
  const COLOR_H_ZONE = rgba('--qn-emerald-accent-rgb', 0.12)
  const COLOR_GRID = pal.gridLine
  const COLOR_TEXT = pal.axisText

  const dims = ['wood', 'fire', 'earth', 'metal', 'water']
  const labels = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
  const base = dims.map((k) => props.vBase?.[k] ?? null)
  const obs = dims.map((k) => props.vObs?.values?.[k] ?? props.vObs?.[k] ?? null)
  const hCenter = dims.map(() => 50)

  chart.setOption({
    tooltip: {
      trigger: 'item',
      backgroundColor: rgba('--qn-emerald-rgb', 0.95),
      borderColor: pal.primary,
      textStyle: { color: WHITE, fontSize: fs(12) }
    },
    legend: {
      show: !props.hideLegend,
      bottom: 0,
      textStyle: { color: COLOR_TEXT, fontSize: fs(12) },
      itemWidth: 14, itemHeight: 10
    },
    radar: {
      indicator: dims.map((k) => ({ name: labels[k], max: 100 })),
      radius: '62%',
      center: ['50%', '45%'],
      axisName: { color: COLOR_TEXT, fontSize: fs(13), fontWeight: 500 },
      splitNumber: 5,
      splitArea: {
        show: true,
        areaStyle: {
          color: [
            rgba('--qn-line', 0.4),
            rgba('--qn-line', 0.4),
            COLOR_H_ZONE,
            rgba('--qn-emerald-accent-rgb', 0.18),
            rgba('--qn-line', 0.4),
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
        {
          value: hCenter,
          name: '健康区带 H',
          symbol: 'none',
          lineStyle: { width: 1.5, color: COLOR_H_CENTER, type: 'dashed', opacity: 0.6 },
          areaStyle: { color: COLOR_H_ZONE },
          itemStyle: { color: COLOR_H_CENTER },
          emphasis: { disabled: true }
        },
        ...(props.vBase ? [{
          value: base,
          name: '先天基底 S₀⁰',
          symbol: 'circle', symbolSize: 7,
          lineStyle: { width: 1.5, color: COLOR_BASE, opacity: 0.55 },
          areaStyle: { color: COLOR_BASE, opacity: 0.06 },
          itemStyle: { color: COLOR_BASE, borderColor: WHITE, borderWidth: 1.5 }
        }] : []),
        ...(props.vObs ? [{
          value: obs,
          name: '当前观测 V_obs',
          symbol: 'circle', symbolSize: 8,
          lineStyle: { width: 2.5, color: COLOR_OBS },
          areaStyle: { color: COLOR_OBS, opacity: 0.15 },
          itemStyle: { color: COLOR_OBS, borderColor: WHITE, borderWidth: 2 }
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
  watchFsScale(() => { chart && chart.resize(); render() })
}

onMounted(async () => {
  await tryInit()
  window.addEventListener('resize', onResize)
  unwatchTheme = watchThemeChange(() => { chart && chart.resize(); render() })
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
  unwatchTheme?.()
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
