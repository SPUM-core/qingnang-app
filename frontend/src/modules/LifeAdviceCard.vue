<!-- ═══════════════════════════════════════════════════════════
  LifeAdviceCard.vue — 今日生活建议卡片（Dashboard M7）
  纯展示容器：筛选 + 归档切换 + TodoCard grid 渲染
  TodoCard / PunchModal / DetailModal 全由装配层管理
══════════════════════════════════════════════════════════════ -->
<template>
  <template v-if="maturityStage >= 2">
    <div class="section-head scroll-target-advice">
      <h2 class="section-title"><QIcon name="doc" :size="15" /> 今日生活建议</h2>
      <div class="seg-control">
        <button v-for="t in segTabs" :key="t.key" class="seg-btn"
                :class="{ active: activeFilter === t.key }"
                @click="$emit('update:filter', t.key)">
          {{ t.label }}
        </button>
      </div>
    </div>

    <!-- 待办卡片网格 -->
    <div v-if="activeFilter !== 'archived'" class="todo-grid">
      <TodoCard
        v-for="todo in filteredTodos"
        :key="todo.id"
        :todo="todo"
        :feedbacks="(feedbacksMap[todo.id] || [])"
        @open-detail="$emit('openDetail', $event)"
        @open-punch="$emit('openPunch', $event)"
      />
      <div v-if="!filteredTodos.length" class="todo-empty">没有匹配的待办</div>
    </div>

    <!-- 归档视图 -->
    <div v-else class="archive-view">
      <div class="archive-summary" v-if="archivedDays > 0">
        <p>共 <strong>{{ archivedDays }}</strong> 天归档 · <strong>{{ totalFeedbacks }}</strong> 条反馈 · 用作复诊诊断数据</p>
      </div>
      <div v-if="archives.length" class="archive-list">
        <details v-for="arc in archives" :key="arc.date" class="archive-day">
          <summary class="archive-day-head">
            <span class="archive-date">{{ arc.date }}</span>
            <span class="archive-todo-count">{{ arc.todos.length }} 项</span>
            <span class="archive-fb-count"><QIcon name="chat" :size="11" /> {{ arc.totalFeedbacks }} 条反馈</span>
          </summary>
          <div class="archive-day-body">
            <div v-for="t in arc.todos" :key="t.id" class="archive-todo">
              <span class="archive-todo-title">{{ t.title }}</span>
              <span class="archive-exec" :class="'exec-' + t.exec_status">{{ execLabelFn ? execLabelFn(t.exec_status) : (t.exec_status || '') }}</span>
              <span v-if="t.feedbacks?.length" class="archive-fb">{{ t.feedbacks.length }}条反馈</span>
            </div>
          </div>
        </details>
      </div>
      <p v-else class="placeholder">暂无归档 · 完成今日待办后，每日自动归档</p>
    </div>
  </template>
</template>

<script setup>
import TodoCard from '../components/TodoCard.vue'
import QIcon from '../components/ui/QIcon.vue'

defineProps({
  /** maturity.stage，>= 2 才渲染 */
  maturityStage: { type: Number, default: 0 },

  // Tab 分段器（v-model）
  segTabs: { type: Array, default: () => [
    { key: 'pending', label: '待处理' },
    { key: 'all',      label: '全部' },
    { key: 'archived', label: '归档' },
  ]},
  activeFilter: { type: String, default: 'pending' },

  // 待办
  filteredTodos: { type: Array, default: () => [] },
  /** feedbacksMap: { [todoId]: feedback[] } —— TodoCard 需要 */
  feedbacksMap: { type: Object, default: () => ({}) },

  // 归档
  archives:       { type: Array, default: () => [] },
  archivedDays:   { type: Number, default: 0 },
  totalFeedbacks: { type: Number, default: 0 },

  /** execLabel(exec_status) → 中文标签，装配层传入 */
  execLabelFn: { type: Function, default: null },
})

defineEmits(['update:filter', 'openPunch', 'openDetail'])
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════════
   原始 CSS 值 — 从 DashboardView scoped style 直接搬过来，
   保证视觉完全一致（HTTP 200 检查不出来静默回归）
═══════════════════════════════════════════════════════════ */

/* ── 分区标题 + 三段分段器 ── */
.section-head { display: flex; justify-content: space-between; align-items: center; margin: 16px 0 12px; gap: 12px; flex-wrap: wrap; }
.section-title { font-size: calc(18px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); margin: 0; letter-spacing: 0.5px; }
.seg-control { display: flex; background: var(--qn-surface); border: 1px solid var(--qn-line); border-radius: var(--qn-r-pill); overflow: hidden; }
.seg-btn {
  font-size: calc(13px * var(--qn-fs-scale)); padding: 7px 18px; border: none; background: transparent;
  color: var(--qn-ink-3); cursor: pointer; transition: all 0.15s; white-space: nowrap;
}
.seg-btn:hover { color: var(--qn-emerald); }
.seg-btn.active { background: var(--qn-emerald); color: var(--qn-paper); font-weight: 500; }

/* ── 待办卡片网格 ── */
.todo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  grid-auto-rows: 1fr;         /* 关键：每行等高，让卡片内部 flex 布局生效 */
  gap: 16px;
}
.todo-grid > * { height: 100%; }  /* 子元素（TodoCard）撑满网格单元格 */
.todo-empty { grid-column: 1 / -1; text-align: center; padding: 30px; color: var(--qn-ink-3); font-size: calc(13px * var(--qn-fs-scale)); }

/* ── 归档 ── */
.archive-summary { background: var(--qn-paper); border-radius: var(--qn-r-sm); padding: 12px 16px; margin-bottom: 12px; font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); }
.archive-summary strong { color: var(--qn-emerald); font-weight: 600; }
.archive-list { display: flex; flex-direction: column; gap: 8px; }
.archive-day { background: var(--qn-surface); border-radius: var(--qn-r-sm); overflow: hidden; }
.archive-day-head {
  padding: 12px 16px; cursor: pointer;
  display: flex; gap: 14px; align-items: center; font-size: calc(13px * var(--qn-fs-scale));
  transition: background 0.15s;
}
.archive-day-head:hover { background: var(--qn-paper); }
.archive-date { font-weight: 600; color: var(--qn-emerald); font-family: var(--font-mono); }
.archive-todo-count { color: var(--qn-ink-2); }
.archive-fb-count { color: var(--qn-ink-3); margin-left: auto; font-size: calc(12px * var(--qn-fs-scale)); }
.archive-day-body { padding: 8px 16px 16px; border-top: 1px solid var(--qn-line); background: var(--qn-paper); }
.archive-todo {
  display: flex; gap: 10px; align-items: center;
  padding: 6px 8px; font-size: calc(12px * var(--qn-fs-scale));
  border-radius: 4px;
}
.archive-todo-title { flex: 1; color: var(--qn-ink); }
.archive-exec { font-size: calc(11px * var(--qn-fs-scale)); padding: 1px 6px; border-radius: 3px; font-weight: 500; }
.archive-exec.exec-done { background: rgba(67,160,71,0.1); color: var(--wuxing-wood); }
.archive-exec.exec-partial { background: rgba(212,160,23,0.1); color: var(--wuxing-earth); }
.archive-exec.exec-skipped { background: rgba(107,114,119,0.1); color: var(--qn-ink-3); }
.archive-exec.exec-failed { background: rgba(216,67,21,0.1); color: var(--wuxing-fire); }
.archive-exec.exec-null { background: var(--qn-paper); color: var(--qn-ink-3); }
.archive-fb { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

/* ── 响应式：原始 media query 全部搬过来 ── */
@media (max-width: 1024px) {
  .todo-grid { grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
}
@media (max-width: 480px) {
  .todo-grid { grid-template-columns: 1fr; }
  .seg-control { width: 100%; }
  .seg-btn { flex: 1; padding: 7px 8px; text-align: center; }
}
</style>
