<template>
  <div class="todo-card" :class="[todo.done ? 'done' : '', todo.priority ? ('priority pri-' + todo.priority) : '']">
    <!-- 卡头：时间 + 优先级标签 + 印章 -->
    <div class="todo-head">
      <span v-if="todo.due" class="todo-due">{{ todo.due }}</span>
      <span v-if="todo.priority === 'p0'" class="pri-chip p0">P0 关键</span>
      <span v-else-if="todo.priority === 'p1'" class="pri-chip p1">P1 推荐</span>
      <span v-else-if="todo.priority === 'p2'" class="pri-chip p2">P2 留意</span>
      <span v-if="feedbackCount > 0" class="fb-count"><QIcon name="chat" :size="12" /> {{ feedbackCount }}</span>
      <span v-if="todo.done" class="done-seal">已完成</span>
    </div>

    <!-- 标题 + 说明 -->
    <div class="todo-main">
      <p class="todo-title">{{ todo.title }}</p>
      <p v-if="todo.remind" class="todo-desc">{{ todo.remind }}</p>
    </div>

    <!-- 底部按钮 -->
    <div class="todo-foot">
      <button v-if="todo.done" class="modify-btn" @click="$emit('open-punch', todo)">修改</button>
      <button v-else class="punch-btn" @click="$emit('open-punch', todo)">打卡</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import QIcon from './ui/QIcon.vue'

const props = defineProps({
  todo: { type: Object, required: true },
  feedbacks: { type: Array, default: () => [] }
})

defineEmits(['open-punch'])

const feedbackCount = computed(() => props.feedbacks?.length || 0)
</script>

<style scoped>
.todo-card {
  background: #fff;
  border: 1px solid var(--ink-line);
  border-radius: 14px;
  padding: 18px;
  display: flex; flex-direction: column;
  transition: box-shadow 0.15s, border-color 0.15s, opacity 0.15s;
  min-height: 170px;
  cursor: default;
}
.todo-card:hover { box-shadow: var(--shadow-card); border-color: rgba(26,77,69,0.2); }
.todo-card.done { opacity: 0.72; }
.todo-card.done .todo-title { color: var(--ink-primary); }

/* ── 卡头 ── */
.todo-head { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.todo-due { font-size: 12px; color: var(--ink-tertiary); margin-right: auto; }
.fb-count { font-size: 11px; color: var(--ink-tertiary); }

/* ── 已完成印章：朱砂方形章 ── */
.done-seal {
  margin-left: auto;
  display: inline-flex; align-items: center; justify-content: center;
  width: 56px; height: 26px;
  border: 2px solid #B8392A;
  color: #B8392A;
  font-family: 'STKaiti', 'KaiTi', '楷体', serif;
  font-size: 13px; font-weight: 700;
  letter-spacing: 3px;
  border-radius: 3px;
  background: rgba(184, 57, 42, 0.06);
  transform: rotate(-2deg);
  line-height: 1; padding: 0 2px;
}

/* 优先级标签 */
.pri-chip { font-size: 11px; font-weight: 500; padding: 3px 10px; border-radius: 11px; white-space: nowrap; }
.pri-chip.p0 { background: rgba(168, 68, 47, 0.1); color: #A8442F; }
.pri-chip.p1 { background: rgba(212, 160, 23, 0.12); color: #B8860B; }
.pri-chip.p2 { background: rgba(26, 77, 69, 0.08); color: var(--qingnang-emerald); }

/* ── 标题 + 说明区（flex:1 撑满） ── */
.todo-main {
  flex: 1 1 auto;
  display: flex; flex-direction: column; gap: 4px;
  padding: 8px 0;
  min-height: 0;
}
.todo-title {
  font-size: 16px; color: var(--ink-primary); margin: 0;
  font-weight: 500; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.todo-desc {
  font-size: 13px; color: var(--ink-tertiary); margin: 0;
  line-height: 1.55;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── 底部按钮区（固定贴底） ── */
.todo-foot {
  flex-shrink: 0;
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px solid var(--ink-line);
}
.punch-btn {
  padding: 7px 18px; border: none; border-radius: var(--radius-pill);
  background: var(--qingnang-emerald); color: var(--qingnang-paper);
  font-size: 13px; font-weight: 500; letter-spacing: 2px; cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
}
.punch-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(23, 83, 76, 0.25); }
.modify-btn {
  padding: 7px 18px; border: 1px solid var(--ink-line); border-radius: var(--radius-pill);
  background: #fff; color: var(--ink-secondary);
  font-size: 13px; letter-spacing: 1px; cursor: pointer;
  transition: all 0.15s;
}
.modify-btn:hover { border-color: var(--qingnang-emerald); color: var(--qingnang-emerald); }

/* ═══════════════════════════════════════════
   手机竖屏优化
   ═══════════════════════════════════════════ */
@media (max-width: 480px) {
  .todo-card { padding: 14px; border-radius: 12px; min-height: 150px; }
  .todo-main { padding: 6px 0; }
  .done-seal { width: 48px; height: 22px; font-size: 11px; letter-spacing: 2px; }

  .punch-btn, .modify-btn {
    width: 100%; padding: 9px 0; font-size: 14px; letter-spacing: 3px;
    text-align: center;
  }
  .todo-title { font-size: 15px; }
  .todo-desc { font-size: 12px; }
  .todo-head { flex-wrap: wrap; gap: 4px; }
}
</style>
