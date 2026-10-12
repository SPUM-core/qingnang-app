<!-- ═══════════════════════════════════════════════════════════
  TrendRadarCard.vue — 体质趋势雷达（Dashboard M10）
  纯展示：props 进，emit 出，不碰 store / API
══════════════════════════════════════════════════════════════ -->
<template>
  <div class="card chart-card trend-card">
    <div class="card-head">
      <h2>体质趋势</h2>
      <span class="chip-dv">ΔV {{ trendStateLabel }}</span>
    </div>
    <div class="trend-body">
      <RadarChart v-if="vBase || vObs"
                 :v-base="vBase"
                 :v-obs="vObs"
                 hide-legend
                 height="220px"
                 class="trend-radar" />
      <p v-else class="placeholder trend-radar">暂无数据</p>
      <div class="trend-side">
        <div class="legend-row"><span class="lg-swatch base"></span>先天基底</div>
        <div class="legend-row"><span class="lg-swatch obs"></span>当前观测</div>
        <p class="trend-delta">{{ deltaSummary }}</p>
        <button class="btn-ghost-sm" @click="$emit('goCase')">查看档案</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import RadarChart from '../components/charts/RadarChart.vue'

defineProps({
  /** 先天基底五形向量 {wood,fire,earth,metal,water} */
  vBase:          { type: Object, default: null },
  /** 最新观测五形向量 */
  vObs:           { type: Object, default: null },
  /** ΔV 状态标签，如 "基线调平中" */
  trendStateLabel:{ type: String, default: '' },
  /** ΔV 摘要文字，如 "木 ▲ 1 · 火 ▼ 2 · 余稳定" */
  deltaSummary:   { type: String, default: '' },
})
defineEmits(['goCase'])
</script>

<style scoped>
.trend-card { margin-top: 0; }
.trend-body { display: flex; gap: 20px; align-items: center; flex: 1; min-height: 0; }
.trend-radar { flex: 1; min-width: 0; }
.trend-side { flex-shrink: 0; display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
.legend-row { display: flex; align-items: center; gap: 8px; font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); }
.lg-swatch { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
.lg-swatch.base { background: var(--qn-emerald); }
.lg-swatch.obs { background: var(--wuxing-fire, var(--qn-cinnabar)); }
.trend-delta { margin: 2px 0 0; font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); line-height: 1.6; max-width: 200px; }
.btn-ghost-sm {
  align-self: flex-start; margin-top: 4px;
  font-size: calc(13px * var(--qn-fs-scale)); padding: 6px 16px; border-radius: var(--qn-r-pill);
  border: 1px solid var(--qn-emerald); background: transparent; color: var(--qn-emerald);
  cursor: pointer; transition: background 0.15s;
}
.btn-ghost-sm:hover { background: rgba(var(--qn-emerald-rgb),0.06); }

@media (max-width: 720px) {
  .trend-body { flex-direction: column; align-items: stretch; }
  .trend-radar { width: 100%; }
  .trend-side { align-items: flex-start; }
  .trend-delta { max-width: none; }
}
</style>
