<!-- ═══════════════════════════════════════════════════════════
     M5 体质调理曲线（DriftChart + chartMode 分段 tab + 四视图入口）
     纯展示组件：props 进、emit 出，不碰 router / store / SSE
     装配层持有：chartMode ref, driftTrajectory computed, driftSeries,
               vectorStore.lifetimeTrajectory, vectorStore.trendStateLabel
               以及 $router.push({ name: 'trajectory' })
     ═══════════════════════════════════════════════════════════ -->
<template>
  <div class="card chart-card">
    <div class="card-head">
      <h2>体质曲线</h2>
      <div style="display:flex;gap:6px;align-items:center;">
        <div class="view-mode-tabs">
          <button
            class="tab-btn"
            :class="{ active: chartMode === 'current' }"
            @click="$emit('update:chartMode', 'current')"
          >当前观测</button>
          <button
            class="tab-btn"
            :class="{ active: chartMode === 'lifetime' }"
            :disabled="!lifetimeAvailable"
            :title="lifetimeAvailable ? '八字大运+流年终身推演' : '等待推演数据...'"
            @click="$emit('update:chartMode', 'lifetime')"
          >终身推演</button>
        </div>
        <span class="chip-dv">{{ chipText }}</span>
      </div>
    </div>
    <DriftChart
      v-if="driftTrajectory || (driftSeries && driftSeries.length)"
      :trajectory="driftTrajectory"
      :series="driftSeries"
      height="320px"
      class="curve-chart"
    />
    <p v-else class="placeholder curve-empty">暂无观测数据 · 完成一次数据采集后生成调理曲线</p>

    <!-- 四视图入口（原 $router.push → emit('navigate')） -->
    <div class="chart-footer">
      <button class="chart-footer-btn" @click="$emit('navigate')">
        <span class="cfb-icon">🌀</span>
        查看完整体质曲线模块
        <span class="cfb-arrow">→</span>
      </button>
      <span class="chart-footer-hint">SPUM 四视图：终身推演 · 流年气运 · 节气属性 · 调节视图</span>
    </div>
  </div>
</template>

<script setup>
import DriftChart from '../components/charts/DriftChart.vue'

defineProps({
  chartMode:        { type: String,  default: 'current' },
  driftTrajectory:  { type: Object,  default: null },
  driftSeries:      { type: Array,   default: () => [] },
  lifetimeAvailable:{ type: Boolean, default: false },
  chipText:         { type: String,  default: '' },
})

defineEmits(['update:chartMode', 'navigate'])
</script>

<!-- ═══ scoped style：从 DashboardView L1261-1283 + L1384-1413 一字不差搬运 ═══ -->
<style scoped>
/* 共享 card-head + chip-dv (原 L1261-1263) */
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--qn-line); }
.card-head h2 { display: flex; align-items: center; gap: 6px; margin: 0; padding: 0; border: none; }
.chip-dv { font-size: calc(12px * var(--qn-fs-scale)); font-weight: 500; color: var(--qn-emerald); background: rgba(var(--qn-emerald-rgb),0.08); border-radius: 12px; padding: 3px 10px; }

/* 视图模式 tab 切换 (原 L1265-1283) */
.view-mode-tabs { display: flex; gap: 2px; background: var(--qn-bg-2); border-radius: 8px; padding: 2px; }
.tab-btn {
  font-size: calc(11px * var(--qn-fs-scale));
  font-weight: 500;
  padding: 3px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--qn-ink-3);
  cursor: pointer;
  transition: all .15s;
}
.tab-btn:hover:not(:disabled) { color: var(--qn-ink); }
.tab-btn.active {
  background: var(--qn-bg);
  color: var(--qn-emerald);
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.tab-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* chart-card + curve-chart (原 L1384-1391) */
.card h2 { margin-bottom: 12px; }
.chart-card { min-height: 300px; display: flex; flex-direction: column; }
.chart-card :deep(.radar-chart), .chart-card :deep(.drift-chart) { flex: 1; }
.curve-chart { flex: 1; min-height: 260px; }
.curve-empty { color: var(--qn-ink-3); text-align: center; padding: 50px 16px; font-size: calc(13px * var(--qn-fs-scale)); }

/* 体质曲线四视图模块入口 (原 L1393-1413) */
.chart-footer {
  display: flex; align-items: center; justify-content: space-between;
  gap: 10px; margin-top: 10px; padding-top: 10px;
  border-top: 1px dashed var(--qn-line);
  flex-wrap: wrap;
}
.chart-footer-btn {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: calc(12px * var(--qn-fs-scale)); font-weight: 500;
  padding: 6px 14px; border-radius: 20px;
  border: 1px solid var(--qn-primary, #17534C);
  background: transparent;
  color: var(--qn-primary, #17534C);
  cursor: pointer; transition: all 0.15s;
}
.chart-footer-btn:hover {
  background: var(--qn-primary, #17534C); color: #fff;
}
.cfb-icon { font-size: 14px; }
.cfb-arrow { font-size: 14px; opacity: 0.7; }
.chart-footer-hint {
  font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3);
}
</style>
