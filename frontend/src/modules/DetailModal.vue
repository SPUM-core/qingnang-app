<!-- ═══════════════════════════════════════════════════════════
     M9 DetailModal（待办详情弹窗 · Teleport body）
     纯展示组件：props 进、emit 出，不碰 store / API
     装配层持有：detailModal ref, dmDetail computed, dmReason computed,
               closeDetailModal, askDetailQA
     ═══════════════════════════════════════════════════════════ -->
<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="modal" class="punch-modal-backdrop" @click.self="$emit('close')">
        <div class="punch-modal">
          <div class="pm-head">
            <div class="pm-title-wrap">
              <span class="pm-tag">今日建议</span>
              <h3 class="pm-title">{{ modal.title }}</h3>
              <p v-if="modal.remind" class="pm-desc">{{ modal.remind }}</p>
            </div>
            <button class="pm-close" @click="$emit('close')" aria-label="关闭">✕</button>
          </div>

          <div v-if="detail" class="pm-section">
            <label class="pm-label">📋 做法</label>
            <p class="pm-text">{{ detail }}</p>
          </div>

          <div class="pm-section">
            <label class="pm-label">💡 推荐原因</label>
            <p class="pm-text">{{ reason }}</p>
          </div>

          <div v-if="modal.source_ref" class="pm-section">
            <label class="pm-label">📚 出处</label>
            <p class="pm-text source-text">{{ modal.source_ref }}</p>
          </div>

          <div class="pm-foot">
            <button class="pm-cancel" @click="$emit('close')">关闭</button>
            <button class="pm-submit" @click="$emit('askQA')">💬 问问青囊管家</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
defineProps({
  modal:  { type: Object, default: null },  // detailModal ref 的值
  detail: { type: String, default: '' },    // dmDetail computed
  reason: { type: String, default: '' },    // dmReason computed
})

defineEmits(['close', 'askQA'])
</script>

<!-- ═══ scoped style：和 PunchModal 共享全套 CSS（一字不差搬运） ═══ -->
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
.pm-desc { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 4px 0 0; line-height: 1.55; }
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

/* 详情文本（非 PunchModal 独有，L1598-1608） */
.pm-text {
  font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink-2);
  line-height: 1.7; margin: 0;
}
.pm-text.source-text {
  font-family: 'STKaiti', 'KaiTi', '楷体', serif;
  color: var(--qn-cinnabar);
  border-left: 2px solid #B8392A;
  padding-left: 10px;
  font-size: calc(13px * var(--qn-fs-scale));
}

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
  .pm-foot { gap: 8px; }
  .pm-cancel, .pm-submit { flex: 1; padding: 11px 0; text-align: center; }
}
</style>
