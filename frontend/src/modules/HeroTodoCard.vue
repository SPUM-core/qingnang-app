<!-- ═══════════════════════════════════════════════════════════
  HeroTodoCard.vue — 英雄卡 1：今日最重要的事（Dashboard M4a）
  纯展示：props 进，emit 出，不碰 store / API
══════════════════════════════════════════════════════════════ -->
<template>
  <div class="hero-card">
    <div class="hero-main">
      <h2 class="hero-title">今日最重要的事</h2>
      <p class="hero-item"><span class="hero-dot"></span>{{ heroTodo?.title || '暂无待办 · 好好休息' }}</p>
      <p class="hero-sub">{{ anchorSafe.yi }} · 当前状态 {{ anchorSafe.state }}</p>
      <p class="hero-sub">忌 {{ anchorSafe.ji }} · 顺当日节律</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  /** heroTodo computed 结果：{ id, title, priority, done, ... } | null */
  heroTodo: { type: Object, default: null },
  /** anchorSafe computed 结果：{ yi, ji, state, ganzhi, ... } */
  anchorSafe: {
    type: Object,
    required: true,
    validator: (v) => 'yi' in v && 'ji' in v && 'state' in v,
  },
})
defineEmits(['goPending'])
</script>

<style scoped>
.hero-card {
  border-radius: var(--radius-lg); padding: 26px 28px;
  background: linear-gradient(135deg, var(--qn-emerald) 0%, var(--qn-emerald-dark) 100%);
  box-shadow: 0 8px 24px rgba(9, 40, 36, 0.25);
  color: var(--qn-paper);
}
.hero-main { display: flex; flex-direction: column; gap: 8px; }
.hero-title { font-size: calc(21px * var(--qn-fs-scale)); font-weight: 600; margin: 0; letter-spacing: 1px; }
.hero-item { display: flex; align-items: center; gap: 10px; font-size: calc(16px * var(--qn-fs-scale)); font-weight: 500; margin: 4px 0 0; }
.hero-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--qingnang-spirit); flex-shrink: 0; }
.hero-sub { font-size: calc(13px * var(--qn-fs-scale)); color: rgba(242,239,231,0.72); margin: 0; }

@media (max-width: 480px) {
  .hero-card { padding: 20px; }
}
</style>
