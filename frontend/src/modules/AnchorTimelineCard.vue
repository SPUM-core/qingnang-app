<!-- ═══════════════════════════════════════════════════════════
     M5b 今日时空锚点（三格指标 + 彭祖百忌 + 玉匣记 + 节律线）
     纯展示组件：props 进、emit 出
     装配层持有：anchorSafe computed, rhythmSegments computed, openAnchorExplain
     ═══════════════════════════════════════════════════════════ -->
<template>
  <div class="card chart-card anchor-card clickable" @click="$emit('explain')">
    <div class="card-head">
      <h2><QIcon name="anchor" :size="15" /> 今日时空锚点</h2>
      <span class="anchor-sub">{{ anchorSafe?.ganzhi }} · <span class="ai-hint">点我 AI 解读</span></span>
    </div>
    <div class="anchor-grid">
      <div class="ag-cell">
        <span class="ag-label">当令时辰</span>
        <span class="ag-val">{{ anchorSafe?.dangling }}</span>
      </div>
      <div class="ag-cell">
        <span class="ag-label">流飞星</span>
        <span class="ag-val">{{ anchorSafe?.feixing }}</span>
      </div>
      <div class="ag-cell">
        <span class="ag-label">十二建除</span>
        <span class="ag-val">{{ anchorSafe?.jianchu }}</span>
      </div>
      <div class="ag-cell">
        <span class="ag-label">冲煞</span>
        <span class="ag-val warn">{{ anchorSafe?.chong }}</span>
      </div>
      <div class="ag-cell">
        <span class="ag-label">煞方</span>
        <span class="ag-val">{{ anchorSafe?.shaxiang }}</span>
      </div>
      <div class="ag-cell">
        <span class="ag-label">值日星辰</span>
        <span class="ag-val">{{ anchorSafe?.richuxing }}</span>
      </div>
    </div>

    <!-- 彭祖百忌 + 二十八宿 -->
    <div class="anchor-extras">
      <div class="ae-row" v-if="anchorSafe?.pengzu">
        <span class="ae-label">彭祖百忌</span>
        <span class="ae-val">{{ anchorSafe.pengzu }}</span>
      </div>
      <div class="ae-row" v-if="anchorSafe?.su">
        <span class="ae-label">二十八宿</span>
        <span class="ae-val">{{ anchorSafe.su }}宿</span>
      </div>
    </div>

    <!-- 玉匣记摘录条 -->
    <div v-if="anchorSafe?.yuxiaji" class="anchor-yuxiaji">
      <span class="yxj-quote">{{ anchorSafe.yuxiaji }}</span>
    </div>

    <!-- 时辰节律线：三段式 -->
    <div class="anchor-timeline">
      <div class="tl-seg" v-for="s in rhythmSegments" :key="s.range" :class="s.color">
        <span class="tl-bar"></span>
        <span class="tl-text">{{ s.range }} {{ s.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import QIcon from '../components/ui/QIcon.vue'

defineProps({
  anchorSafe:      { type: Object, default: () => ({}) },
  rhythmSegments:  { type: Array,  default: () => [] },
})

defineEmits(['explain'])
</script>

<!-- ═══ scoped style：从 DashboardView L1261 + L1284-1295 + L1441-1469 一字不差搬运 ═══ -->
<style scoped>
/* 共享 card-head (原 DashboardView L1261-1262) */
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--qn-line); }
.card-head h2 { display: flex; align-items: center; gap: 6px; margin: 0; padding: 0; border: none; }
.chip-dv { font-size: calc(12px * var(--qn-fs-scale)); font-weight: 500; color: var(--qn-emerald); background: rgba(var(--qn-emerald-rgb),0.08); border-radius: 12px; padding: 3px 10px; }

/* 原 DashboardView L1090/L1206 — .card h2 / .chart-card 基础 */
.card h2 { margin-bottom: 12px; }
.chart-card { min-height: 300px; display: flex; flex-direction: column; }

/* 原 L1284-1295 */
.anchor-sub { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); font-weight: 400; }
.anchor-card .anchor-grid { grid-template-columns: repeat(3, 1fr); }
.anchor-card.clickable { cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; }
.anchor-card.clickable:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
.anchor-card.clickable:active { transform: translateY(0); }
.ai-hint {
  display: inline-block; margin-left: 6px; padding: 2px 8px; border-radius: 10px;
  background: rgba(var(--qn-emerald-rgb),0.1); color: var(--qn-emerald);
  font-size: calc(11px * var(--qn-fs-scale)); font-weight: 500;
}

/* 原 L1441-1469 */
.anchor-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 10px; }
.ag-cell { background: var(--qn-paper); border: none; border-radius: 12px; padding: 10px 12px; text-align: left; min-height: 60px; display: flex; flex-direction: column; justify-content: center; }
.ag-label { display: block; font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-bottom: 4px; }
.ag-val { font-size: calc(16px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); line-height: 1.2; }
.ag-val.warn { color: var(--wuxing-fire, var(--qn-cinnabar)); }

.anchor-extras { border-top: 1px dashed rgba(26,43,26,0.12); padding-top: 8px; margin-bottom: 8px; display: flex; flex-direction: column; gap: 4px; }
.ae-row { display: flex; font-size: calc(12px * var(--qn-fs-scale)); }
.ae-label { color: var(--qn-ink-3); flex-shrink: 0; width: 72px; }
.ae-val { color: var(--qn-ink-2); }

.anchor-yuxiaji {
  background: rgba(168, 68, 47, 0.06);
  border-left: 3px solid var(--qn-cinnabar);
  border-radius: 0 8px 8px 0;
  padding: 8px 12px;
  margin-bottom: 4px;
}
.yxj-quote { font-family: "STKaiti", "KaiTi", serif; font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-cinnabar); letter-spacing: 0.5px; }

.anchor-timeline { display: flex; gap: 8px; }
.tl-seg { flex: 1; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.tl-bar { display: block; height: 4px; border-radius: 2px; }
.tl-seg.calm .tl-bar { background: #C9D8D2; }
.tl-seg.active .tl-bar { background: var(--qn-emerald); }
.tl-seg.rest .tl-bar { background: var(--wuxing-earth, var(--qn-earth)); }
.tl-text { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tl-seg.active .tl-text { color: var(--qn-emerald); font-weight: 500; }
.tl-seg.rest .tl-text { color: var(--wuxing-earth, #B8860B); }

/* 原 480px media query (L1433-1436) */
@media (max-width: 480px) {
  .anchor-grid { gap: 8px; }
  .ag-cell { padding: 10px 8px; }
  .ag-val { font-size: calc(13px * var(--qn-fs-scale)); }
  .anchor-timeline { flex-direction: column; gap: 10px; }
}
</style>
