<template>
  <section class="page collect-entry" data-page-id="P06">
    <div class="page__header">
      <a class="back-link" @click.prevent="$router.back()" aria-label="返回">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
        返回
      </a>
      <h1>数据采集</h1>
    </div>
    <p class="page__desc">原始数据直接采集，时间戳对齐后上传 · 数据仅供漂移拟合参考</p>

    <div class="entry-grid">
      <router-link to="/collect/body" class="entry-btn">
        <span class="entry-icon">📷</span>
        <div class="entry-text">
          <span class="entry-label">体态照片</span>
          <span class="entry-sub">照片 / 体型数据</span>
        </div>
        <span class="entry-arrow">›</span>
      </router-link>

      <router-link to="/collect/voice" class="entry-btn">
        <span class="entry-icon">🎙️</span>
        <div class="entry-text">
          <span class="entry-label">语音样本</span>
          <span class="entry-sub">10-20 秒语音采集</span>
        </div>
        <span class="entry-arrow">›</span>
      </router-link>

      <router-link to="/collect/ppg" class="entry-btn">
        <span class="entry-icon">💓</span>
        <div class="entry-text">
          <span class="entry-label">脉搏采集</span>
          <span class="entry-sub">硬件 PPG · 五形 ΔF</span>
        </div>
        <span class="entry-arrow">›</span>
      </router-link>

      <router-link to="/collect/inquiry" class="entry-btn">
        <span class="entry-icon">📋</span>
        <div class="entry-text">
          <span class="entry-label">AI 问诊</span>
          <span class="entry-sub">多阶段选择题 · 状态摘要</span>
        </div>
        <span class="entry-arrow">›</span>
      </router-link>

      <router-link to="/collect/tongue" class="entry-btn">
        <span class="entry-icon">👅</span>
        <div class="entry-text">
          <span class="entry-label">舌部照片</span>
          <span class="entry-sub">望诊 · HSV 颜色分析 · SPUM 舌象判定</span>
        </div>
        <span class="entry-arrow">›</span>
      </router-link>

      <router-link to="/collect/report" class="entry-btn">
        <span class="entry-icon">📄</span>
        <div class="entry-text">
          <span class="entry-label">检查报告</span>
          <span class="entry-sub">上传归档 · 随时调取</span>
        </div>
        <span class="entry-arrow">›</span>
      </router-link>
    </div>
  </section>
</template>

<script setup>
// 入口页仅做路由分发，三个子页面各自承载采集逻辑
</script>

<style scoped>
.collect-entry {
  /* 页面内所有元素左对齐；entry-grid 单独居中 */
}

.page__header { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }

.entry-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: 20px auto 0;  /* auto → 水平居中 */
  width: 100%;
  max-width: 520px;
}

.entry-btn {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px 20px;
  background: var(--qn-paper);
  border: 1px solid var(--qn-line);
  border-radius: var(--qn-r-lg);
  text-decoration: none;
  color: var(--qn-ink);
  cursor: pointer;
  transition: all 0.2s;
}

.entry-btn:hover {
  border-color: var(--qingnang-spirit);
  background: rgba(var(--qn-emerald-light-rgb), 0.06);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.entry-icon { font-size: calc(40px * var(--qn-fs-scale)); flex-shrink: 0; }
.entry-text { display: flex; flex-direction: column; gap: 2px; flex: 1; }
.entry-label { font-size: calc(16px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); }
.entry-sub { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }
.entry-arrow { font-size: calc(22px * var(--qn-fs-scale)); color: var(--qn-ink-3); flex-shrink: 0; }

/* 桌面横屏：入口页也居中，三个按钮横排 */
@media (min-width: 721px) and (orientation: landscape) {
  .entry-grid { max-width: none; }
}
</style>
