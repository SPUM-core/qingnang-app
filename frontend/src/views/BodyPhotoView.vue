<template>
  <section class="page" data-page-id="P07">
    <div class="page__header">
      <a class="back-link" @click.prevent="$router.back()" aria-label="返回">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
        返回
      </a>
      <h1>体态照片</h1>
    </div>
    <p class="page__desc">自然光照 · 头部放松 · 拍摄后系统自动压缩</p>

    <div class="collect-wrap">
      <label class="file-upload">
        <input type="file" accept="image/*" capture="environment" @change="onFile" hidden />
        <div v-if="!fileName" class="upload-empty">
          <span class="upload-icon">📷</span>
          <span class="upload-text">点击或拍照上传</span>
        </div>
        <div v-else class="upload-done">
          <span class="done-icon">✓</span>
          <span class="done-name">{{ fileName }}</span>
          <span class="done-hint">· 重新选择</span>
        </div>
      </label>

      <button
        class="btn btn-primary btn-block"
        :disabled="!fileName || uploading"
        @click="upload"
      >
        {{ uploading ? '上传中...' : '上传体态照片' }}
      </button>

      <p v-if="result" class="result" :class="resultOk ? 'result-success' : 'result-error'">{{ result }}</p>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import * as storage from '../utils/storage'

const fileName = ref('')
const uploading = ref(false)
const result = ref('')
const resultOk = ref(false)

const onFile = (e) => {
  const file = e.target.files?.[0]
  if (file) fileName.value = file.name
}

const upload = async () => {
  if (!fileName.value) return
  uploading.value = true
  result.value = ''
  try {
    // 体态照片当前无后端端点，本地暂存
    storage.set('qn_body_photo', { name: fileName.value, ts: Date.now() })
    result.value = `✓ ${fileName.value} 已暂存本地`
    resultOk.value = true
  } catch (e) {
    result.value = `上传失败：${e.message}`
    resultOk.value = false
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.page__header { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
.collect-wrap { } /* 内容铺满 .page */

.file-upload {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  border: 2px dashed var(--qn-line); border-radius: var(--qn-r-lg);
  padding: 60px 20px; cursor: pointer; color: var(--qn-ink-3);
  font-size: calc(14px * var(--qn-fs-scale)); transition: all 0.2s; background: var(--qn-paper);
  margin-bottom: 20px;
}
.file-upload:hover { border-color: var(--qingnang-spirit); color: var(--qn-emerald); background: rgba(var(--qn-emerald-light-rgb),0.06); }

.upload-icon { font-size: calc(48px * var(--qn-fs-scale)); margin-bottom: 12px; }
.upload-text { font-size: calc(14px * var(--qn-fs-scale)); }

.upload-done { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.done-icon { font-size: calc(32px * var(--qn-fs-scale)); color: var(--qn-emerald); }
.done-name { color: var(--qingnang-spirit); font-weight: 500; font-size: calc(14px * var(--qn-fs-scale)); }
.done-hint { color: var(--qn-ink-3); font-size: calc(12px * var(--qn-fs-scale)); }

.btn { padding: 10px 20px; border-radius: var(--qn-r-sm); border: none; cursor: pointer; font-size: calc(14px * var(--qn-fs-scale)); font-family: var(--qn-font-body); transition: all 0.2s; }
.btn-primary { background: var(--qn-emerald); color: #fff; }
.btn-primary:hover { background: var(--qn-emerald-light); }
.btn-primary:disabled { background: var(--qn-line); cursor: not-allowed; opacity: 0.6; }
.btn-block { width: 100%; }

.result { margin-top: 12px; font-size: calc(13px * var(--qn-fs-scale)); padding: 8px 12px; border-radius: var(--qn-r-sm); }
.result-success { background: rgba(46, 134, 126, 0.1); color: var(--qn-emerald); }
.result-error { background: rgba(201, 79, 58, 0.1); color: var(--trend-up); }
</style>
