<template>
  <div v-if="visible" class="update-dialog">
    <div class="update-mask" @click="onMaskClick"></div>
    <div class="update-card" :class="{ 'force': info?.force_update }">
      <div class="update-header">
        <span class="update-icon">📦</span>
        <h3>{{ info?.force_update ? '需要升级' : '发现新版本' }}</h3>
      </div>

      <div class="update-body">
        <div class="version-row">
          <span class="ver-old">{{ info?.current_version }}</span>
          <span class="ver-arrow">→</span>
          <span class="ver-new">{{ info?.latest_version }}</span>
        </div>

        <div v-if="info?.update_note" class="update-note">
          <div class="note-label">更新内容</div>
          <p>{{ info.update_note }}</p>
        </div>

        <div v-if="info?.size_bytes" class="update-size">
          大小：{{ formatSize(info.size_bytes) }}
        </div>

        <div v-if="info?.force_update" class="force-banner">
          ⚠️ 当前版本过低，请升级后继续使用
        </div>
      </div>

      <div class="update-footer">
        <button 
          v-if="!info?.force_update"
          class="btn-ghost" 
          @click="onLater"
          :disabled="installing"
        >
          稍后再说
        </button>
        <button 
          class="btn-primary" 
          @click="onInstall"
          :disabled="installing"
        >
          <span v-if="installing">下载中...</span>
          <span v-else>{{ info?.force_update ? '立即升级' : '立即更新' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { downloadAndInstall } from '../utils/appUpdater'

const props = defineProps({
  visible: { type: Boolean, default: false },
  info: { type: Object, default: null },
})

const emit = defineEmits(['update:visible', 'update-installed'])

const installing = ref(false)

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function onMaskClick() {
  // 强制更新不允许点遮罩关闭
  if (!props.info?.force_update) {
    emit('update:visible', false)
  }
}

function onLater() {
  emit('update:visible', false)
}

async function onInstall() {
  if (!props.info) return
  installing.value = true
  try {
    const result = await downloadAndInstall(props.info)
    if (result.success) {
      emit('update-installed')
    }
  } finally {
    installing.value = false
  }
}
</script>

<style scoped>
.update-dialog {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  /* 遮罩留安全区（base.css 兜底层另有 !important 保险） */
  padding: var(--safe-top) 0 var(--safe-bottom);
}

.update-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(2px);
}

.update-card {
  position: relative;
  width: min(92%, 360px);
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  overflow: hidden;
  animation: slideUp 0.25s ease-out;
}

.update-card.force {
  border-top: 4px solid #e74c3c;
}

@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.update-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 20px 10px;
}

.update-icon { font-size: 28px; }
.update-header h3 { margin: 0; font-size: 16px; color: #2d5016; }

.update-body { padding: 4px 20px 14px; }

.version-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  padding: 12px;
  background: #f6f8f4;
  border-radius: 12px;
  justify-content: center;
}

.ver-old { color: #999; text-decoration: line-through; font-size: 14px; }
.ver-arrow { color: #2d5016; }
.ver-new { color: #2d5016; }

.update-note {
  margin-top: 12px;
  font-size: 14px;
  color: #555;
}

.note-label { font-weight: 600; margin-bottom: 4px; color: #333; }
.update-note p { margin: 0; line-height: 1.6; }

.update-size {
  margin-top: 8px;
  font-size: 12px;
  color: #999;
}

.force-banner {
  margin-top: 12px;
  padding: 8px 12px;
  background: #fdecea;
  color: #c0392b;
  border-radius: 8px;
  font-size: 13px;
}

.update-footer {
  display: flex;
  gap: 10px;
  padding: 14px 20px 20px;
  border-top: 1px solid #f0f0ea;
}

.btn-ghost {
  flex: 1;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid #ddd;
  background: transparent;
  color: #666;
  font-size: 15px;
  cursor: pointer;
}
.btn-ghost:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-primary {
  flex: 1;
  padding: 12px;
  border-radius: 12px;
  border: none;
  background: #2d5016;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
