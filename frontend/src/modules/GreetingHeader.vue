<!-- ═══════════════════════════════════════════════════════════
  GreetingHeader.vue — 问候头部（Dashboard M2）
  ⚠️ 纯展示：props 进，不碰 store / API / SSE
  装配层：DashboardView.vue 负责 fetchMe / fetchYearView 后分发 props
══════════════════════════════════════════════════════════════ -->
<template>
  <div class="home-header">
    <div>
      <h1 class="home-greeting">{{ greeting }}，{{ displayName }}</h1>
      <p class="home-date">{{ today }} · {{ weekday }} · {{ caseStatusLabel }}</p>
    </div>
    <div class="home-quick">
      <div class="quick-stat">
        <span class="qs-val">{{ observationCount }}</span>
        <span class="qs-label">次观测</span>
      </div>
      <div class="quick-stat">
        <span class="qs-val">{{ archivedDays }}</span>
        <span class="qs-label">天归档</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  /** 问候语：早上好/下午好/晚上好/深夜好 */
  greeting:       { type: String, default: '你好' },
  /** 用户昵称 */
  displayName:    { type: String, default: '朋友' },
  /** 今日日期文本，如 "2026.10.09" */
  today:          { type: String, default: '' },
  /** 星期，如 "周五" */
  weekday:        { type: String, default: '' },
  /** 病例状态标签，如 "调理中 · 稳定观察" */
  caseStatusLabel:{ type: String, default: '' },
  /** 观测次数（vectorStore.driftSeries.length） */
  observationCount:{ type: Number, default: 0 },
  /** 归档天数 */
  archivedDays:   { type: Number, default: 0 },
})
</script>

<style scoped>
.home-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 20px; }
.home-greeting { font-size: calc(24px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); margin: 0; }
.home-date { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-top: 4px; }
.home-quick { display: flex; gap: 32px; padding-bottom: 4px; }
.quick-stat { display: flex; flex-direction: column; gap: 2px; text-align: left; }
.qs-val { font-size: calc(22px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-emerald); font-family: var(--font-mono); line-height: 1.1; }
.qs-label { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

@media (max-width: 720px) {
  .home-header { flex-direction: column; align-items: flex-start; gap: 12px; }
  .home-quick { gap: 24px; }
}
@media (max-width: 480px) {
  .home-greeting { font-size: calc(19px * var(--qn-fs-scale)); }
  .home-quick { gap: 20px; }
  .qs-val { font-size: calc(18px * var(--qn-fs-scale)); }
}
</style>
