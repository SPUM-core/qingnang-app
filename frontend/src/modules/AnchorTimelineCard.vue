<!-- ═══════════════════════════════════════════════════════════
     今日时空锚点（三格指标 + 彭祖百忌 + 玉匣记 + 节律线 + 12 时辰）
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
        <span class="ag-val">{{ anchorSafe?.dangling }} · 旺{{ anchorSafe?.dangling_elem }}</span>
      </div>
      <div class="ag-cell">
        <span class="ag-label">流飞星</span>
        <span class="ag-val">{{ anchorSafe?.feixing || '—' }}</span>
      </div>
      <div class="ag-cell">
        <span class="ag-label">纳音</span>
        <span class="ag-val">{{ anchorSafe?.na_yin_day || '—' }}</span>
      </div>
      <div class="ag-cell">
        <span class="ag-label">十二建除</span>
        <span class="ag-val">{{ anchorSafe?.jianchu || '—' }}日</span>
      </div>
      <div class="ag-cell">
        <span class="ag-label">值日星宿</span>
        <span class="ag-val">{{ anchorSafe?.xiu || '—' }}宿</span>
      </div>
      <div class="ag-cell">
        <span class="ag-label">冲煞</span>
        <span class="ag-val warn">{{ anchorSafe?.chong || '—' }}</span>
      </div>
    </div>

    <!-- 彭祖百忌 + 煞方 + 值日天神 -->
    <div class="anchor-extras">
      <div class="ae-row" v-if="anchorSafe?.sha">
        <span class="ae-label">煞方</span><span class="ae-val">{{ anchorSafe.sha }}方</span>
      </div>
      <div class="ae-row" v-if="anchorSafe?.tianshen">
        <span class="ae-label">值日天神</span><span class="ae-val">{{ anchorSafe.tianshen }}</span>
      </div>
      <div class="ae-row" v-if="anchorSafe?.pengzu">
        <span class="ae-label">彭祖百忌</span><span class="ae-val">{{ anchorSafe.pengzu }}</span>
      </div>
    </div>

    <!-- 玉匣记摘录条 -->
    <div v-if="anchorSafe?.yuxiaji" class="anchor-yuxiaji">
      <span class="yxj-quote">{{ anchorSafe.yuxiaji }}</span>
    </div>

    <!-- ⭐ 12 时辰 timeline（协纪辨方 · 每时辰建除 + 宜忌 + SPUM 交叉） -->
    <div class="shichen-timeline" v-if="(anchorSafe?.timeline || []).length">
      <div class="st-head">
        <span class="st-title">🕐 十二时辰 · 建除宜忌</span>
        <span class="st-hint">协纪辨方 + 玉匣记</span>
      </div>
      <div class="st-row">
        <div v-for="sc in anchorSafe.timeline" :key="sc.period" class="st-cell" :class="sc.type">
          <div class="st-period">{{ sc.period }}</div>
          <div class="st-range">{{ sc.range }}</div>
          <div class="st-elem">{{ sc.elem }}·{{ sc.jianchu }}</div>
          <div class="st-yi" v-if="sc.yi?.length">{{ sc.yi.slice(0, 2).join('·') }}</div>
        </div>
      </div>
    </div>

    <!-- 时辰节律线（三段式，保留原来的） -->
    <div class="anchor-timeline" v-if="rhythmSegments?.length">
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

<!-- ═══ scoped style ═══ -->
<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--qn-line); }
.card-head h2 { display: flex; align-items: center; gap: 6px; margin: 0; padding: 0; border: none; }
.chip-dv { font-size: calc(12px * var(--qn-fs-scale)); font-weight: 500; color: var(--qn-emerald); background: rgba(var(--qn-emerald-rgb),0.08); border-radius: 12px; padding: 3px 10px; }

.card h2 { margin-bottom: 12px; }
.chart-card { min-height: 300px; display: flex; flex-direction: column; }

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
  margin-bottom: 10px;
}
.yxj-quote { font-family: "STKaiti", "KaiTi", serif; font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-cinnabar); letter-spacing: 0.5px; white-space: pre-line; }

/* ⭐ 12 时辰 timeline */
.shichen-timeline {
  margin-bottom: 10px; padding: 10px 12px;
  background: rgba(var(--qn-emerald-rgb), 0.04);
  border: 1px solid rgba(var(--qn-emerald-rgb), 0.1);
  border-radius: 10px;
}
.st-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.st-title { font-size: calc(13px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); }
.st-hint { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); }
.st-row { display: flex; gap: 4px; overflow-x: auto; padding-bottom: 4px; }
.st-row::-webkit-scrollbar { height: 3px; }
.st-row::-webkit-scrollbar-thumb { background: var(--qn-line); border-radius: 2px; }
.st-cell {
  flex: 0 0 auto; width: 72px;
  padding: 6px 6px; border-radius: 8px;
  background: var(--qn-surface); border: 1px solid var(--qn-line);
  text-align: center;
}
.st-cell.good { border-color: rgba(67,160,71,0.35); background: rgba(67,160,71,0.04); }
.st-cell.critical { border-color: rgba(216,67,21,0.4); background: rgba(216,67,21,0.04); }
.st-cell.warn { border-color: rgba(212,160,23,0.35); background: rgba(212,160,23,0.04); }
.st-period { font-size: calc(12px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); }
.st-range { font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-3); font-family: var(--font-mono); }
.st-elem { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-emerald); font-weight: 500; margin-top: 2px; }
.st-yi { font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.anchor-timeline { display: flex; gap: 8px; }
.tl-seg { flex: 1; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.tl-bar { display: block; height: 4px; border-radius: 2px; }
.tl-seg.calm .tl-bar { background: #C9D8D2; }
.tl-seg.active .tl-bar { background: var(--qn-emerald); }
.tl-seg.rest .tl-bar { background: var(--wuxing-earth, var(--qn-earth)); }
.tl-text { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tl-seg.active .tl-text { color: var(--qn-emerald); font-weight: 500; }
.tl-seg.rest .tl-text { color: var(--wuxing-earth, #B8860B); }

@media (max-width: 720px) {
  .anchor-grid { grid-template-columns: repeat(2, 1fr); }
  .st-cell { width: 64px; }
}
@media (max-width: 480px) {
  .anchor-grid { gap: 8px; }
  .ag-cell { padding: 10px 8px; }
  .ag-val { font-size: calc(13px * var(--qn-fs-scale)); }
  .anchor-timeline { flex-direction: column; gap: 10px; }
  .st-cell { width: 58px; padding: 5px 4px; }
  .st-period { font-size: calc(11px * var(--qn-fs-scale)); }
}
</style>
