<!-- ═══════════════════════════════════════════════════════════
     M12 AiExplainModal（AI 大白话解读 Modal）
     纯展示组件：props 进、emit 出，不碰 router / store / API
     装配层持有：anchorModal reactive, openAnchorExplain,
               renderMarkdown(), continueWithAssistant()
     ═══════════════════════════════════════════════════════════ -->
<template>
  <div v-if="modal?.show" class="modal-backdrop" @click.self="$emit('close')">
    <div class="modal-card anchor-explain-modal">
      <div class="modal-head">
        <h3>🌿 今日时空锚点 · 大白话解读</h3>
        <button class="modal-close" @click="$emit('close')">✕</button>
      </div>
      <div class="modal-body">
        <!-- 加载中 -->
        <div v-if="modal.loading" class="ae-loading">
          <div class="ae-spinner"></div>
          <p>青檬引擎正在翻译术语…</p>
          <p class="muted small">（先解读每个术语是什么意思，再结合你的体质给建议）</p>
        </div>
        <!-- 错误 -->
        <div v-else-if="modal.error" class="ae-error">
          <p>抱歉，AI 解读暂时不可用</p>
          <p class="muted small">{{ modal.error }}</p>
        </div>
        <!-- 结果 -->
        <div v-else class="ae-content">
          <div class="ae-engine-tag" v-if="modal.engine">
            {{ engineLabel }}
          </div>
          <div class="ae-markdown" v-html="renderMarkdownFn ? renderMarkdownFn(modal.text) : modal.text"></div>

          <div class="ae-footer">
            <div class="ae-footer-hint">想继续深入？把这段解读交给青囊管家，基于此展开对话</div>
            <button class="ae-chat-btn" @click="$emit('askAssistant')">
              <span class="ae-chat-icon">💬</span>
              <span>和青囊管家继续聊</span>
              <span class="ae-chat-arrow">→</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modal:            { type: Object, default: null },   // anchorModal reactive
  renderMarkdownFn: { type: Function, default: null }, // renderMarkdown 函数
})

defineEmits(['close', 'askAssistant'])

const engineLabel = computed(() => {
  const e = props.modal?.engine
  if (e === 'qingmeng') return '⚡ 青檬引擎生成'
  if (e === 'deepseek') return '⚡ DeepSeek 生成'
  return '📖 本地术语词典'
})
</script>

<!-- ═══ scoped style：从 DashboardView L1298-1378 一字不差搬运 ═══ -->
<style scoped>
/* Modal backdrop + card + head/body (原 L1298-1324) */
.modal-backdrop {
  position: fixed; inset: 0; background: rgba(26,43,26,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 200;
  /* 遮罩留安全区：内容过高时不顶穿状态栏 / 手势条 */
  padding: calc(var(--safe-top) + 20px) 20px calc(var(--safe-bottom) + 20px);
  animation: fadeIn 0.18s ease;
}
@keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
.modal-card {
  background: var(--qn-surface); border-radius: var(--radius-lg);
  max-width: 560px; width: 100%; max-height: 80vh;
  display: flex; flex-direction: column; overflow: hidden;
  box-shadow: 0 16px 48px rgba(0,0,0,0.18);
  animation: slideUp 0.22s ease;
}
@keyframes slideUp { from { transform: translateY(20px); opacity: 0 } to { transform: translateY(0); opacity: 1 } }
.modal-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 22px; border-bottom: 1px solid var(--qn-line);
}
.modal-head h3 { font-size: calc(16px * var(--qn-fs-scale)); margin: 0; color: var(--qn-ink); font-weight: 600; }
.modal-close {
  width: 32px; height: 32px; border: none; background: transparent;
  font-size: calc(18px * var(--qn-fs-scale)); color: var(--qn-ink-3); cursor: pointer;
  border-radius: 50%; transition: all 0.15s;
}
.modal-close:hover { background: var(--qn-line); color: var(--qn-ink); }
.modal-body { padding: 22px; overflow-y: auto; flex: 1; }

/* Loading (原 L1326-1333) */
.ae-loading { text-align: center; padding: 32px 0; }
.ae-spinner {
  width: 36px; height: 36px; border: 3px solid var(--qn-line);
  border-top-color: var(--qn-emerald); border-radius: 50%;
  margin: 0 auto 16px; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg) } }
.ae-loading p { margin: 4px 0; }

/* Error (原 L1336) */
.ae-error { text-align: center; padding: 16px; color: var(--qn-fire); }

/* Content (原 L1339-1372) */
.ae-engine-tag {
  display: inline-block; margin-bottom: 14px; padding: 3px 10px; border-radius: 12px;
  background: var(--qn-paper); color: var(--qn-ink-2);
  font-size: calc(11px * var(--qn-fs-scale)); font-weight: 500;
}
.ae-markdown {
  font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink); line-height: 1.8;
}
.ae-markdown strong { color: var(--qn-emerald); font-weight: 600; }
.ae-markdown p { margin: 0 0 12px; }
.ae-hr { border: none; border-top: 1px dashed var(--qn-line); margin: 16px 0; }

/* 继续聊按钮 */
.ae-footer {
  margin-top: 20px; padding-top: 18px;
  border-top: 1px dashed var(--qn-line);
}
.ae-footer-hint {
  font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3);
  margin: 0 0 12px; text-align: center;
}
.ae-chat-btn {
  display: flex; align-items: center; justify-content: center; gap: 10px;
  width: 100%; padding: 14px 18px;
  background: linear-gradient(135deg, var(--qn-emerald) 0%, var(--qn-emerald-light) 100%);
  color: #fff; border: none; border-radius: var(--qn-r-lg);
  font-size: calc(14px * var(--qn-fs-scale)); font-weight: 600;
  cursor: pointer; transition: all 0.18s;
  box-shadow: 0 4px 14px rgba(var(--qn-emerald-rgb),0.25);
}
.ae-chat-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(var(--qn-emerald-rgb),0.35); }
.ae-chat-btn:active { transform: translateY(0); }
.ae-chat-icon { font-size: calc(18px * var(--qn-fs-scale)); }
.ae-chat-arrow { opacity: 0.7; font-size: calc(16px * var(--qn-fs-scale)); }

/* 响应式 */
/* 手机竖屏：保持弹窗居中浮动卡片形态
   backdrop 的 safe-top padding 已经有了，只需调卡片尺寸 + 覆盖 base.css 的 modal-head safe-top */
@media (max-width: 480px) {
  .modal-card {
    max-width: calc(100vw - 32px);
    max-height: calc(100vh - var(--safe-top) - var(--safe-bottom) - 32px);
    border-radius: 12px;
  }
  /* 覆盖 base.css 的 modal-head safe-top —— backdrop 已避让 */
  .modal-head { padding-top: 18px !important; }
  .modal-body { padding: 16px 18px; }
}
</style>
