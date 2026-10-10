<!-- ═══════════════════════════════════════════════════════════
     M8 PunchModal（打卡弹窗 · Teleport body）
     纯展示组件：props 进、emit 出，不碰 store / API
     装配层持有：punchModal reactive, openPunchModal, closePunchModal,
               submitPunch, handleFeedback, toggleTodo, execLabel()
     ═══════════════════════════════════════════════════════════ -->
<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="todo" class="punch-modal-backdrop" @click.self="$emit('close')">
        <div class="punch-modal">
          <div class="pm-head">
            <div class="pm-title-wrap">
              <span class="pm-tag">{{ isEdit ? '修改执行反馈' : '今日打卡' }}</span>
              <h3 class="pm-title">{{ todo.title }}</h3>
              <p v-if="todo.due" class="pm-due">🕐 {{ todo.due }}</p>
            </div>
            <button class="pm-close" @click="$emit('close')" aria-label="关闭">✕</button>
          </div>

          <div class="pm-section">
            <label class="pm-label">执行状态</label>
            <div class="pm-exec-btns">
              <button class="pm-exec" :class="{ active: localExecStatus === 'done' }"
                      @click="localExecStatus = 'done'">已完成</button>
              <button class="pm-exec" :class="{ active: localExecStatus === 'partial' }"
                      @click="localExecStatus = 'partial'">部分执行</button>
              <button class="pm-exec" :class="{ active: localExecStatus === 'skipped' }"
                      @click="localExecStatus = 'skipped'">跳过</button>
              <button class="pm-exec" :class="{ active: localExecStatus === 'failed' }"
                      @click="localExecStatus = 'failed'">未执行</button>
            </div>
          </div>

          <div v-if="feedbacks?.length" class="pm-section">
            <label class="pm-label">历史反馈（{{ feedbacks.length }}）</label>
            <div v-for="(fb, i) in feedbacks" :key="i" class="pm-fb-item">
              <span class="pm-fb-date">{{ fb.date }}</span>
              <span class="pm-fb-status" :class="'pm-fb-' + fb.status">{{ execLabelFn?.(fb.status) }}</span>
              <span v-if="fb.note" class="pm-fb-note">{{ fb.note }}</span>
            </div>
          </div>

          <div class="pm-section">
            <label class="pm-label">反馈（可选）</label>
            <textarea v-model="localNote" placeholder="执行细节、感受或遇到的问题…" rows="3"></textarea>
          </div>

          <div class="pm-foot">
            <button class="pm-cancel" @click="$emit('close')">取消</button>
            <button class="pm-submit" @click="$emit('submit', { execStatus: localExecStatus, note: localNote })" :disabled="submitting">
              <span v-if="submitting">提交中…</span>
              <span v-else>提交</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  todo:        { type: Object, default: null },
  feedbacks:   { type: Array,  default: () => [] },
  isEdit:      { type: Boolean, default: false },
  submitting:  { type: Boolean, default: false },
  execLabelFn: { type: Function, default: null },
})

defineEmits(['close', 'submit'])

/* 本地状态：每次 todo 变化时从装配层传入的值重置 */
const localExecStatus = ref('done')
const localNote = ref('')

watch(() => props.todo, (todo) => {
  if (todo) {
    if (props.isEdit && props.feedbacks.length) {
      localExecStatus.value = props.feedbacks[props.feedbacks.length - 1].status || 'done'
    } else {
      localExecStatus.value = 'done'
    }
    localNote.value = ''
  }
}, { immediate: true })
</script>

<!-- ═══ scoped style：从 DashboardView L1476-1620 一字不差搬运 ═══ -->
<style scoped>
/* 遮罩 + 卡片容器 */
.punch-modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(16, 24, 40, 0.45);
  backdrop-filter: blur(3px);
  z-index: 9999;
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.punch-modal {
  background: var(--qn-surface);
  border-radius: 16px;
  width: 100%; max-width: 520px;
  max-height: 92vh;
  overflow-y: auto;
  padding: 24px;
  box-shadow: 0 20px 60px rgba(16, 24, 40, 0.25);
  animation: pm-slide-up 0.25s ease-out;
}
@keyframes pm-slide-up {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* 弹窗头部 */
.pm-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 20px; padding-bottom: 14px;
  border-bottom: 1px solid var(--qn-line);
}
.pm-title-wrap { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.pm-tag {
  display: inline-block; width: fit-content;
  font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-emerald);
  background: rgba(var(--qn-emerald-rgb),0.08);
  padding: 2px 10px; border-radius: 10px;
  letter-spacing: 1px; font-weight: 500;
}
.pm-title { font-size: calc(18px * var(--qn-fs-scale)); color: var(--qn-ink); margin: 0; font-weight: 600; line-height: 1.35; }
.pm-due { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 0; }
.pm-close {
  width: 32px; height: 32px; border-radius: 50%;
  border: 1px solid var(--qn-line); background: var(--qn-surface);
  color: var(--qn-ink-3); font-size: calc(14px * var(--qn-fs-scale)); line-height: 1;
  cursor: pointer; transition: all 0.15s;
  flex-shrink: 0; margin-left: 12px;
}
.pm-close:hover { color: var(--wuxing-fire); border-color: var(--wuxing-fire); }

/* section */
.pm-section { margin-bottom: 18px; }
.pm-label {
  font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3);
  display: block; margin-bottom: 8px; font-weight: 500;
}

/* 执行状态按钮 */
.pm-exec-btns { display: flex; gap: 8px; flex-wrap: wrap; }
.pm-exec {
  font-size: calc(13px * var(--qn-fs-scale)); padding: 7px 16px;
  border-radius: 20px;
  border: 1px solid var(--qn-line);
  background: var(--qn-surface); color: var(--qn-ink-2);
  cursor: pointer; transition: all 0.15s;
}
.pm-exec:hover { border-color: var(--qn-emerald); color: var(--qn-emerald); }
.pm-exec.active {
  background: var(--qn-emerald); border-color: var(--qn-emerald);
  color: #fff; box-shadow: 0 2px 6px rgba(var(--qn-emerald-rgb), 0.25);
}

/* 历史反馈 */
.pm-fb-item {
  display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  font-size: calc(12px * var(--qn-fs-scale)); padding: 8px 10px; background: var(--qn-paper);
  border-radius: 6px; margin-bottom: 6px;
  border-left: 3px solid var(--qn-line);
}
.pm-fb-date { color: var(--qn-ink-3); font-family: var(--font-mono); font-size: calc(11px * var(--qn-fs-scale)); }
.pm-fb-status { font-weight: 600; padding: 1px 8px; border-radius: 3px; font-size: calc(11px * var(--qn-fs-scale)); }
.pm-fb-done { background: rgba(67,160,71,0.1); color: var(--wuxing-wood); }
.pm-fb-partial { background: rgba(212,160,23,0.1); color: var(--wuxing-earth); }
.pm-fb-skipped { background: rgba(107,114,119,0.1); color: var(--qn-ink-3); }
.pm-fb-failed { background: rgba(216,67,21,0.1); color: var(--wuxing-fire); }
.pm-fb-note { flex: 1 0 100%; color: var(--qn-ink-2); line-height: 1.5; margin-top: 3px; }

/* 反馈输入 */
.pm-section textarea {
  width: 100%; border: 1px solid var(--qn-line); border-radius: 10px;
  padding: 12px; font-size: calc(14px * var(--qn-fs-scale)); font-family: var(--qn-font-body);
  resize: vertical; background: var(--qn-surface); color: var(--qn-ink);
  line-height: 1.55; transition: border-color 0.15s;
  box-sizing: border-box;
}
.pm-section textarea:focus { outline: none; border-color: var(--qn-emerald); }

/* 底部按钮 */
.pm-foot {
  display: flex; justify-content: flex-end; gap: 10px;
  margin-top: 22px; padding-top: 16px;
  border-top: 1px solid var(--qn-line);
}
.pm-cancel {
  padding: 9px 22px; border: 1px solid var(--qn-line); border-radius: var(--qn-r-pill);
  background: var(--qn-surface); color: var(--qn-ink-2); font-size: calc(13px * var(--qn-fs-scale)); cursor: pointer;
  transition: all 0.15s;
}
.pm-cancel:hover { color: var(--qn-ink); border-color: var(--qn-ink-3); }
.pm-submit {
  padding: 9px 24px; border: none; border-radius: var(--qn-r-pill);
  background: var(--qn-emerald); color: var(--qn-paper);
  font-size: calc(13px * var(--qn-fs-scale)); font-weight: 500; letter-spacing: 2px; cursor: pointer;
  transition: all 0.15s;
}
.pm-submit:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(var(--qn-emerald-rgb), 0.3); }
.pm-submit:disabled { opacity: 0.5; cursor: not-allowed; }

/* Transition */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-active .punch-modal, .fade-leave-active .punch-modal { transition: transform 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.fade-enter-from .punch-modal, .fade-leave-to .punch-modal { transform: translateY(10px) scale(0.97); }

/* 弹窗手机竖屏（原 DashboardView L1289-1302 一字不差） */
@media (max-width: 480px) {
  .punch-modal-backdrop { padding: 0; }
  .punch-modal {
    max-width: 100%; max-height: 100vh; border-radius: 0;
    padding: 20px;
    animation: none;
  }
  .pm-head { margin-bottom: 16px; padding-bottom: 12px; }
  .pm-title { font-size: calc(16px * var(--qn-fs-scale)); }
  .pm-exec-btns { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .pm-foot { gap: 8px; }
  .pm-cancel, .pm-submit { flex: 1; padding: 11px 0; text-align: center; }
}
</style>
