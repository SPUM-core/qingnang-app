<!-- ═══════════════════════════════════════════════════════════
  LifestyleReminderCard.vue — 生活提醒（Dashboard M6）
  ⚠️ 纯展示！SSE / 缓存 / fallback 全留在装配层。
     高频 prop lifestylePreview 由装配层 onGenerating 回调驱动。

  Props:
    maturityStage      控制 v-if 显示（stage >= 2 才显示）
    remTotal           折叠行的总条数
    lifestyleLoading   SSE 是否正在生成
    lifestylePreview   流式 token 预览文本（高频更新，直接渲染 slice(-500)）
    remTabs            [{key, label}]
    clothGoodSelect / clothBadSelect / foodGoodSelect / foodBadSelect
    homeSelect / relativeSelect / absoluteSelect / stoneSelect

  Emits (v-model):
    update:expanded    折叠/展开
    update:activeTab   切 Tab
══════════════════════════════════════════════════════════════ -->
<template>
  <div v-if="maturityStage >= 2" class="card reminders-mini scroll-target-life">
    <button class="rem-collapse" @click="$emit('update:expanded', !expanded)">
      <span class="rem-collapse-text">展开全部提醒与注意事项（{{ remTotal }} 条 · 含绝对注意事项与矿物避忌）</span>
      <span class="rem-chevron" :class="{ open: expanded }">›</span>
    </button>

    <div v-if="expanded" class="rem-body">
      <!-- 分段器 -->
      <div class="rem-head">
        <div class="rem-tabs">
          <button v-for="t in remTabs" :key="t.key" class="rem-tab"
                  :class="{ active: activeTab === t.key }"
                  @click="$emit('update:activeTab', t.key)">
            {{ t.label }}
          </button>
        </div>
      </div>

      <!-- 流式生成中：骨架屏 + 渐进 token 预览 -->
      <div v-if="lifestyleLoading" class="lifestyle-loading">
        <div class="lifestyle-loading-header">
          <span class="spinner"><QIcon name="spark" :size="16" /></span>
          <span>青檬引擎正在生成今日提醒…（约 15-20s）</span>
        </div>
        <pre v-if="lifestylePreview" class="lifestyle-preview">{{ lifestylePreview.slice(-500) }}</pre>
        <div v-else class="lifestyle-preview-placeholder">正在连接青檬引擎…</div>
      </div>

      <!-- 宜 -->
      <div v-if="!lifestyleLoading && activeTab === 'good'" class="rem-lists">
        <div class="rem-col">
          <h4 class="rem-col-title good"><QIcon name="check" :size="13" /> 今日宜（{{ clothGoodSelect.length + foodGoodSelect.length }}）</h4>
          <div v-for="r in [...clothGoodSelect, ...foodGoodSelect]" :key="r.id" class="rem-item rem-good">
            <span class="rem-item-title">{{ r.title }}</span>
            <span class="rem-item-desc">{{ r.desc }}</span>
          </div>
        </div>
        <div class="rem-col">
          <h4 class="rem-col-title bad"><QIcon name="warn" :size="13" /> 今日忌（{{ clothBadSelect.length + foodBadSelect.length }}）</h4>
          <div v-for="r in [...clothBadSelect, ...foodBadSelect]" :key="r.id" class="rem-item rem-bad">
            <span class="rem-item-title">{{ r.title }}</span>
            <span class="rem-item-desc">{{ r.desc }}</span>
          </div>
        </div>
      </div>

      <!-- 住 -->
      <div v-else-if="!lifestyleLoading && activeTab === 'home'" class="rem-lists">
        <div v-for="r in homeSelect" :key="r.id" class="rem-item" :class="{ 'rem-urgent': r.urgent }">
          <span class="rem-item-title">{{ r.title }}</span>
          <span class="rem-item-desc">{{ r.desc }}</span>
        </div>
      </div>

      <!-- 注意事项：绝对注意事项 / 矿物避忌默认收起 -->
      <div v-else-if="!lifestyleLoading" class="rem-fold-zone">
        <h4 class="rem-col-title warn"><QIcon name="warn" :size="13" /> 慎用（{{ relativeSelect.length }}）</h4>
        <div v-for="r in relativeSelect" :key="r.id" class="rem-item">
          <span class="rem-item-title">{{ r.title }}</span>
          <span class="rem-item-desc">{{ r.desc }} · {{ r.reason }}</span>
        </div>

        <details class="rem-fold">
          <summary class="rem-fold-summary danger"><QIcon name="forbid" :size="13" /> 绝对注意事项（{{ absoluteSelect.length }}）</summary>
          <div v-for="r in absoluteSelect" :key="r.id" class="rem-item rem-danger">
            <span class="rem-item-title">{{ r.title }}</span>
            <span class="rem-item-desc">{{ r.desc }} · {{ r.reason }}</span>
          </div>
        </details>

        <details class="rem-fold">
          <summary class="rem-fold-summary"><QIcon name="gem" :size="13" /> 矿物避忌（{{ stoneSelect.length }}）</summary>
          <div v-for="r in stoneSelect" :key="r.id" class="rem-item rem-stone">
            <span class="rem-item-title">{{ r.title }}</span>
            <span class="rem-item-desc">{{ r.desc }}</span>
          </div>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup>
import QIcon from '../components/ui/QIcon.vue'

defineProps({
  maturityStage:      { type: Number, default: 0 },

  // 折叠/展开 + Tab 选择（v-model 入口）
  expanded:           { type: Boolean, default: false },
  activeTab:          { type: String, default: 'good' },

  // 折叠行总条数
  remTotal:           { type: Number, default: 0 },
  remTabs:            { type: Array, default: () => [
    { key: 'good', label: '宜·忌' },
    { key: 'home', label: '住房' },
    { key: 'avoid', label: '注意事项' }
  ] },

  // ⚠️ SSE 流式状态（高频更新！直接传给装配层，装配层管 onGenerating 回调）
  lifestyleLoading:   { type: Boolean, default: false },
  lifestylePreview:   { type: String, default: '' },

  // 精选列表（全部 computed 结果由装配层传入）
  clothGoodSelect:    { type: Array, default: () => [] },
  clothBadSelect:     { type: Array, default: () => [] },
  foodGoodSelect:     { type: Array, default: () => [] },
  foodBadSelect:      { type: Array, default: () => [] },
  homeSelect:         { type: Array, default: () => [] },
  relativeSelect:     { type: Array, default: () => [] },
  absoluteSelect:     { type: Array, default: () => [] },
  stoneSelect:        { type: Array, default: () => [] },
})

defineEmits(['update:expanded', 'update:activeTab'])
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════════
   生活提醒：折叠行 + 展开区
   ═══════════════════════════════════════════════════════════ */
.reminders-mini { margin-bottom: 16px; padding: 0 18px; }
.rem-collapse {
  width: 100%; display: flex; justify-content: space-between; align-items: center;
  background: transparent; border: none; padding: 14px 0;
  font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); cursor: pointer; text-align: left;
}
.rem-collapse:hover .rem-collapse-text { color: var(--qn-emerald); }
.rem-collapse-text { transition: color 0.15s; }
.rem-chevron { font-size: calc(16px * var(--qn-fs-scale)); color: var(--qn-ink-3); transition: transform 0.2s; font-weight: 300; }
.rem-chevron.open { transform: rotate(90deg); }
.rem-body { border-top: 1px dashed var(--qn-line); padding: 12px 0 16px; }
.rem-fold-zone { display: flex; flex-direction: column; gap: 10px; }
.rem-fold { border-radius: 8px; background: var(--qn-surface); }
.rem-fold-summary {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 12px; font-size: calc(12px * var(--qn-fs-scale)); font-weight: 600; color: var(--wuxing-earth);
  cursor: pointer; list-style: none; user-select: none;
}
.rem-fold-summary::-webkit-details-marker { display: none; }
.rem-fold-summary.danger { color: var(--wuxing-fire); }
.rem-fold-summary::after { content: '›'; margin-left: auto; font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink-3); transition: transform 0.2s; font-weight: 300; }
.rem-fold[open] .rem-fold-summary::after { transform: rotate(90deg); }
.rem-fold .rem-item { margin: 0 10px 10px; }
.rem-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }

/* ── Lifestyle 流式加载 ── */
.lifestyle-loading { padding: 20px 12px; }
.lifestyle-loading-header { display: flex; align-items: center; gap: 10px; color: var(--qn-emerald); font-size: calc(13px * var(--qn-fs-scale)); margin-bottom: 12px; font-weight: 500; }
.spinner { animation: pulse 1.2s ease-in-out infinite; display: inline-block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.lifestyle-preview { background: #f7f9fa; border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm); padding: 10px 12px; font-family: var(--font-mono, monospace); font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); max-height: 120px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; margin: 0; line-height: 1.6; }
.lifestyle-preview-placeholder { color: var(--qn-ink-3); font-size: calc(12px * var(--qn-fs-scale)); font-style: italic; padding: 20px 0; text-align: center; }

/* ── Tab 分段器 ── */
.rem-tabs { display: flex; gap: 4px; }
.rem-tab {
  font-size: calc(12px * var(--qn-fs-scale)); padding: 5px 12px; border-radius: 14px;
  border: 1px solid var(--qn-line); background: var(--qn-surface); color: var(--qn-ink-2);
  cursor: pointer; transition: all 0.15s;
}
.rem-tab:hover { border-color: var(--qn-emerald); color: var(--qn-emerald); }
.rem-tab.active { background: var(--qn-emerald); border-color: var(--qn-emerald); color: #fff; }

/* ── 列表 ── */
.rem-lists { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 720px) { .rem-lists { grid-template-columns: 1fr; } }
.rem-col { display: flex; flex-direction: column; gap: 6px; }
.rem-col-title { font-size: calc(12px * var(--qn-fs-scale)); margin: 0 0 4px; padding-bottom: 4px; border-bottom: 1px dashed var(--qn-line); }
.rem-col-title.good { color: var(--wuxing-wood); }
.rem-col-title.bad { color: var(--wuxing-fire); }
.rem-col-title.warn { color: var(--wuxing-earth); }

.rem-item {
  padding: 10px 12px; border-radius: 8px; border: 1px solid var(--qn-line);
  background: var(--qn-surface); display: flex; flex-direction: column; gap: 3px;
}
.rem-item-title { font-size: calc(13px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); }
.rem-item-desc { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); line-height: 1.5; }
.rem-item.rem-good { border-left: 3px solid var(--wuxing-wood); }
.rem-item.rem-bad { border-left: 3px solid var(--wuxing-fire); }
.rem-item.rem-danger { border-left: 4px solid var(--wuxing-fire); background: linear-gradient(135deg, var(--qn-surface), rgba(216,67,21,0.03)); }
.rem-item.rem-stone { border-left: 3px solid var(--wuxing-metal); }
.rem-item.rem-urgent { border-left: 3px solid var(--wuxing-fire); background: rgba(216,67,21,0.04); }
</style>
