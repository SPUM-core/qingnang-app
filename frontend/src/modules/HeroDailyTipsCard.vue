<!-- ═══════════════════════════════════════════════════════════
  HeroDailyTipsCard.vue — 英雄卡 2：今日宜忌（Dashboard M4b）
  含天气头部 + AI 禁忌提醒条 + QIcon（内部 import）
  纯展示：props 进，emit 出，不碰 store / API
══════════════════════════════════════════════════════════════ -->
<template>
  <div class="hero-yi-card">
    <div class="hero-yi-head">
      <div class="hero-yi-head-left">
        <p class="hero-tag">今日 · 宜忌速览</p>
        <h2 class="hero-title">今日宜忌</h2>
      </div>
      <!-- 右上角天气 -->
      <div v-if="anchorSafe.weather" class="hero-weather">
        <span class="hw-icon" :class="'hw-' + anchorSafe.weather.icon">
          <span v-if="anchorSafe.weather.icon === 'sun'">☀️</span>
          <span v-else-if="anchorSafe.weather.icon === 'cloud'">⛅</span>
          <span v-else-if="anchorSafe.weather.icon === 'rain'">🌧️</span>
          <span v-else-if="anchorSafe.weather.icon === 'thunder'">⛈️</span>
          <span v-else-if="anchorSafe.weather.icon === 'snow'">🌨️</span>
          <span v-else-if="anchorSafe.weather.icon === 'fog'">🌫️</span>
          <span v-else>🌤️</span>
        </span>
        <div class="hw-info">
          <span class="hw-temp">{{ anchorSafe.weather.temp_high }}° / {{ anchorSafe.weather.temp_low }}°</span>
          <span class="hw-desc">{{ anchorSafe.weather.desc }} · {{ anchorSafe.weather.qihou }}</span>
        </div>
      </div>
    </div>
    <div class="yj-pair">
      <div class="yj-block yi">
        <span class="yj-ico good"><QIcon name="check" :size="13" /></span>
        <div class="yj-text">
          <span class="yj-k">宜</span>
          <span class="yj-v">{{ anchorSafe.yi }}</span>
        </div>
      </div>
      <div class="yj-block ji">
        <span class="yj-ico bad"><QIcon name="forbid" :size="13" /></span>
        <div class="yj-text">
          <span class="yj-k">忌</span>
          <span class="yj-v">{{ anchorSafe.ji }}</span>
        </div>
      </div>
    </div>
    <!-- AI 禁忌提醒（不可执行，只读警示） -->
    <div v-if="avoidanceNotes && avoidanceNotes.length" class="avoid-notes">
      <div v-for="(a, i) in avoidanceNotes" :key="i" class="avoid-item">
        <span class="avoid-dot">·</span>
        <span class="avoid-t">{{ a.title }}</span>
      </div>
    </div>
    <p class="hero-yi-more" @click="$emit('openReminders')">展开全部宜忌 →</p>
  </div>
</template>

<script setup>
import QIcon from '../components/ui/QIcon.vue'

defineProps({
  /** 同 HeroTodoCard 的 anchorSafe，额外含 weather 子对象 */
  anchorSafe:     { type: Object, required: true },
  /** AI 禁忌提醒数组：[{ title }, ...] */
  avoidanceNotes: { type: Array, default: () => [] },
})
defineEmits(['openReminders'])
</script>

<style scoped>
.hero-yi-card {
  border-radius: var(--radius-lg); padding: 22px 24px;
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.88) 0%, rgba(38,105,92,0.88) 100%);
  color: #fff;
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: 0 6px 20px rgba(9, 40, 36, 0.2);
}
.hero-yi-card .hero-title { font-size: calc(17px * var(--qn-fs-scale)); margin-bottom: 14px; }
.hero-tag { font-size: calc(12px * var(--qn-fs-scale)); letter-spacing: 3px; color: rgba(242,239,231,0.65); margin: 0; }
.hero-title { font-size: calc(21px * var(--qn-fs-scale)); font-weight: 600; margin: 0; letter-spacing: 1px; }
.hero-yi-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.hero-yi-head-left { display: flex; flex-direction: column; gap: 2px; }
.hero-weather {
  display: flex; align-items: center; gap: 10px;
  background: rgba(242,239,231,0.1);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 14px;
  padding: 8px 14px;
  backdrop-filter: blur(8px);
  flex-shrink: 0;
}
.hw-icon { font-size: 24px; line-height: 1; }
.hw-info { display: flex; flex-direction: column; gap: 1px; }
.hw-temp { font-size: calc(15px * var(--qn-fs-scale)); font-weight: 600; color: #fff; letter-spacing: 0.5px; }
.hw-desc { font-size: calc(11px * var(--qn-fs-scale)); color: rgba(255,255,255,0.7); letter-spacing: 0.5px; }
.yj-pair { display: flex; flex-direction: column; gap: 10px; }
.yj-block {
  display: flex; align-items: center; gap: 12px;
  background: rgba(242,239,231,0.08); border-radius: 10px; padding: 12px 14px;
}
.yj-ico {
  width: 30px; height: 30px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.yj-ico.good { background: rgba(123,196,169,0.25); color: #7BC4A9; }
.yj-ico.bad { background: rgba(208,138,110,0.25); color: #D08A6E; }
.yj-text { display: flex; flex-direction: column; gap: 2px; }
.yj-k { font-size: calc(11px * var(--qn-fs-scale)); letter-spacing: 2px; font-weight: 600; }
.yj-block.yi .yj-k { color: #7BC4A9; }
.yj-block.ji .yj-k { color: #D08A6E; }
.yj-v { font-size: calc(14px * var(--qn-fs-scale)); color: rgba(242,239,231,0.92); font-weight: 500; }
.hero-yi-more {
  margin: 14px 0 0; font-size: calc(12px * var(--qn-fs-scale)); color: rgba(242,239,231,0.55); cursor: pointer;
  letter-spacing: 1px; text-align: right;
}
.hero-yi-more:hover { color: rgba(242,239,231,0.85); }

/* AI 禁忌提醒条 */
.avoid-notes {
  margin-top: 12px; padding: 10px 12px;
  background: rgba(208,138,110,0.15);
  border: 1px solid rgba(208,138,110,0.35);
  border-radius: 8px;
}
.avoid-item {
  font-size: calc(12px * var(--qn-fs-scale));
  color: rgba(242,239,231,0.88);
  line-height: 1.7;
  display: flex; align-items: flex-start; gap: 4px;
}
.avoid-dot { color: #D08A6E; font-weight: 700; flex-shrink: 0; }

@media (max-width: 720px) {
  .hero-yi-card .hero-title { font-size: calc(16px * var(--qn-fs-scale)); margin-bottom: 10px; }
}
@media (max-width: 480px) {
  .hero-yi-card { padding: 18px 20px; }
}
</style>
