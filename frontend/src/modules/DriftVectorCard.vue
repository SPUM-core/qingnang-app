<!-- ═══════════════════════════════════════════════════════════
  DriftVectorCard.vue — 漂移矢量一览表格（Dashboard M11）
  纯展示：props 进，无 emit
══════════════════════════════════════════════════════════════ -->
<template>
  <div class="card table-card">
    <h2>漂移矢量一览</h2>
    <table class="table">
      <thead><tr><th>维度</th><th>先天基底</th><th>最新观测</th><th>ΔV</th></tr></thead>
      <tbody>
        <tr v-for="row in rows" :key="row.k">
          <td>{{ row.label }}</td>
          <td>{{ fmt(row.base) }}</td>
          <td>{{ fmt(row.obs) }}</td>
          <td :class="{ delta: true, up: row.delta > 0, down: row.delta < 0 }">{{ fmt(row.delta) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
defineProps({
  /** deltaTable 行：[{ k, label, base, obs, delta }] */
  rows: { type: Array, required: true },
})

/** 格式化数字，null → "—"，其余保留 1 位小数 */
const fmt = (v) => v == null ? '—' : Number(v).toFixed(1)
</script>

<style scoped>
/* 间距：给前一个 TrendRadarCard 留 16px 呼吸空间（不碰全局 .card） */
.table-card { overflow-x: auto; margin-top: 16px; }

/* 表格：table-layout:fixed 强制四列按比例分配容器宽度
   删掉 min-width:520px —— 移动端用更小字号/padding 让四列全放下 */
.table {
  table-layout: fixed;
  width: 100%;
  border-collapse: collapse;
  font-size: calc(13px * var(--qn-fs-scale));
}
.table th, .table td {
  padding: 8px 12px;
  text-align: right;
  border-bottom: 1px solid var(--qn-line);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.table th:first-child, .table td:first-child { text-align: left; }
.table thead th {
  font-size: calc(12px * var(--qn-fs-scale));
  font-weight: 500;
  color: var(--qn-ink-3);
  background: transparent;
  border-bottom: 2px solid var(--qn-line);
}
.delta { font-weight: 600; font-family: var(--font-mono); }
.delta.up { color: var(--qn-trend-up); }
.delta.down { color: var(--qn-trend-down); }

/* 手机竖屏：更小 padding + 更小字号 → 四列全放下 */
@media (max-width: 480px) {
  .table th, .table td { padding: 6px 6px; font-size: calc(11px * var(--qn-fs-scale)); }
  .table thead th { font-size: calc(10px * var(--qn-fs-scale)); }
}
</style>
