<template>
  <!-- 触发按钮：看起来像原来的原生 select -->
  <button
    type="button"
    class="qselect-trigger"
    :class="{ 'is-open': open }"
    :disabled="disabled"
    @click="open = !open"
  >
    <span class="qselect-label" :title="selectedLabel">{{ selectedLabel || placeholder }}</span>
    <svg class="qselect-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  </button>

  <!-- 自定义下拉面板（不在 Teleport 里就用 fixed 定位） -->
  <div v-if="open" class="qselect-backdrop" @click="open = false">
    <div class="qselect-panel" @click.stop>
      <div class="qselect-header">
        <span class="qselect-title">{{ title || placeholder }}</span>
        <button class="qselect-close" @click="open = false" aria-label="关闭">✕</button>
      </div>
      <ul class="qselect-options">
        <li
          v-for="opt in options"
          :key="opt.value"
          class="qselect-option"
          :class="{ selected: String(modelValue) === String(opt.value) }"
          @click="select(opt.value)"
        >
          <span class="qselect-option-label">{{ opt.label }}</span>
          <span v-if="String(modelValue) === String(opt.value)" class="qselect-check">✓</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  modelValue: { type: [String, Number, Boolean], default: '' },
  options: { type: Array, required: true },
  placeholder: { type: String, default: '请选择' },
  title: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'change'])

const open = ref(false)

const selectedLabel = computed(() => {
  const match = props.options.find(o => String(o.value) === String(props.modelValue))
  return match ? match.label : ''
})

function select(value) {
  emit('update:modelValue', value)
  emit('change', value)
  open.value = false
}
</script>

<style scoped>
.qselect-trigger {
  font-size: calc(13px * var(--qn-fs-scale, 1));
  padding: 6px 28px 6px 10px;
  border: 1px solid var(--qn-line);
  border-radius: var(--qn-r-sm);
  background: var(--qn-surface);
  color: var(--qn-ink);
  cursor: pointer;
  flex-shrink: 0;
  max-width: 60%;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  line-height: 1.4;
  text-align: left;
  font-family: inherit;
}
.qselect-trigger:disabled { opacity: 0.5; cursor: not-allowed; }
.qselect-trigger.is-open { border-color: var(--qn-emerald); }
.qselect-chevron { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); }
.qselect-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 遮罩 */
.qselect-backdrop {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex; align-items: flex-end; justify-content: center;
  z-index: 99999;
}
.qselect-panel {
  background: var(--qn-surface);
  border-radius: var(--qn-r-lg) var(--qn-r-lg) 0 0;
  width: 100%;
  max-height: 70vh;
  display: flex; flex-direction: column;
  border-top: 1px solid var(--qn-line);
  animation: qselect-slide-up 0.18s ease;
}
@keyframes qselect-slide-up {
  from { transform: translateY(100%); }
  to   { transform: translateY(0); }
}
.qselect-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--qn-line);
}
.qselect-title { font-weight: 600; color: var(--qn-ink); font-size: 14px; }
.qselect-close {
  border: none; background: none; font-size: 18px; cursor: pointer;
  color: var(--qn-ink-3); padding: 0; width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%;
}
.qselect-close:hover { background: var(--qn-bg-2); }

.qselect-options {
  list-style: none; margin: 0; padding: 0;
  overflow-y: auto;
}
.qselect-option {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 20px;
  cursor: pointer;
  border-bottom: 1px solid var(--qn-line);
  color: var(--qn-ink);
  font-size: calc(14px * var(--qn-fs-scale, 1));
  transition: background 0.12s;
}
.qselect-option:last-child { border-bottom: none; }
.qselect-option:hover { background: var(--qn-bg-2); }
.qselect-option.selected { color: var(--qn-emerald); font-weight: 500; background: rgba(var(--qn-emerald-rgb, 46, 107, 96), 0.06); }
.qselect-check { color: var(--qn-emerald); font-weight: 700; }

/* PC 端：居中弹出 */
@media (min-width: 721px) {
  .qselect-backdrop { align-items: center; padding: 20px; }
  .qselect-panel {
    border-radius: var(--qn-r-lg);
    width: 360px;
    max-width: 90vw;
    border: 1px solid var(--qn-line);
    box-shadow: 0 8px 32px rgba(0,0,0,0.2);
    max-height: 60vh;
  }
}
</style>
