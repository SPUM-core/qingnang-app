<template>
  <section class="page">
    <div class="page__header">
      <a class="back-link" @click.prevent="$router.back()" aria-label="返回">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
        返回
      </a>
      <h1>舌部照片</h1>
    </div>
    <p class="page__desc">自然光照 · 舌头完全伸出 · 正对镜头</p>

    <div class="collect-wrap">
      <label class="file-upload" :class="{ preview: previewUrl }">
        <input type="file" accept="image/*" capture="environment" @change="onFile" hidden />
        <img v-if="previewUrl" :src="previewUrl" alt="舌象照片预览" class="preview-img" />
        <div v-else class="upload-empty">
          <span class="upload-icon">👅</span>
          <span class="upload-text">点击或拍照上传舌部照片</span>
        </div>
      </label>

      <button class="btn btn-primary btn-block"
              :disabled="!previewUrl || uploading" @click="upload">
        {{ uploading ? '分析中...' : '上传并分析舌象' }}
      </button>

      <!-- 分析结果 -->
      <div v-if="result" class="result-panel" :class="resultConfClass">
        <div class="result-header">
          <span class="conf-badge" :class="'conf-' + result.confidence">
            {{ confLabel(result.confidence) }}
          </span>
          <span class="tongue-type">{{ result.tongue_type }}</span>
        </div>
        <div class="s-vector" v-if="result.s_vector">
          <span class="sv-label">S修正:</span>
          <span v-for="(arrow, wx) in result.s_vector" :key="wx" class="sv-item">
            S<sub>{{ wx }}</sub>{{ arrow }}
          </span>
        </div>
        <div class="rationale" v-if="result.rationale">
          <div class="rat-label">依据:</div>
          <div v-for="(r, i) in result.rationale" :key="i" class="rat-item">· {{ r }}</div>
        </div>
        <div class="warnings" v-if="result.warnings && result.warnings.length">
          <div v-for="(w, i) in result.warnings" :key="i" class="warn-item">⚠️ {{ w }}</div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api/client'

const fileName = ref('')
const previewUrl = ref('')
const uploading = ref(false)
const result = ref(null)
const resultOk = ref(false)
const resultConfClass = ref('')

const onFile = (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  fileName.value = file.name
  const reader = new FileReader()
  reader.onload = (ev) => { previewUrl.value = ev.target.result }
  reader.readAsDataURL(file)
}

async function upload() {
  if (!previewUrl.value) return
  uploading.value = true
  result.value = null

  try {
    // 从 dataURL 里取 base64
    const b64 = previewUrl.value.split(',')[1]
    const ext = fileName.value.split('.').pop()?.toLowerCase() || 'jpeg'

    const r = await api.post('/api/v1/assistant/tongue/upload', {
      image_base64: b64,
      format: ext,
    })
    result.value = r
    resultOk.value = true
    resultConfClass.value = 'conf-' + (r.confidence || 'low')
  } catch (e) {
    result.value = { error: e.message || '上传失败' }
    resultOk.value = false
  } finally {
    uploading.value = false
  }
}

function confLabel(c) {
  return { high: '高置信', medium: '中置信', low: '仅供参考' }[c] || c
}
</script>

<style scoped>
.page__header { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }

.file-upload {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  border: 2px dashed var(--qn-line); border-radius: var(--qn-r-lg);
  padding: 40px 20px; cursor: pointer; color: var(--qn-ink-3);
  font-size: calc(14px * var(--qn-fs-scale)); transition: all 0.2s; background: var(--qn-paper);
  margin-bottom: 16px; min-height: 200px;
}
.file-upload:hover { border-color: var(--qingnang-spirit); color: var(--qn-emerald); }
.file-upload.preview { padding: 12px; border-style: solid; border-color: var(--qn-line); }

.preview-img { max-width: 100%; max-height: 300px; border-radius: 8px; }
.upload-icon { font-size: calc(48px * var(--qn-fs-scale)); margin-bottom: 8px; }

.btn { padding: 10px 20px; border-radius: var(--qn-r-sm); border: none; cursor: pointer; font-size: calc(14px * var(--qn-fs-scale)); font-family: var(--qn-font-body); transition: all 0.2s; }
.btn-primary { background: var(--qn-emerald); color: #fff; }
.btn-primary:hover:not(:disabled) { background: var(--qn-emerald-light); }
.btn-primary:disabled { background: var(--qn-line); cursor: not-allowed; opacity: 0.6; }
.btn-block { width: 100%; }

.result-panel { margin-top: 16px; padding: 16px; border-radius: var(--qn-r-lg); background: var(--qn-paper); border: 1px solid var(--qn-line); }
.result-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.conf-badge { font-size: calc(12px * var(--qn-fs-scale)); padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.conf-high { background: rgba(46,134,126,0.15); color: var(--qn-emerald); }
.conf-medium { background: rgba(220,160,60,0.15); color: #b37a2b; }
.conf-low { background: rgba(201,79,58,0.1); color: var(--trend-up); }
.tongue-type { font-size: calc(16px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); }

.s-vector { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.sv-label { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }
.sv-item { font-size: calc(13px * var(--qn-fs-scale)); font-family: monospace; background: rgba(46,134,126,0.08); padding: 2px 8px; border-radius: 4px; color: var(--qn-emerald); }

.rat-label, .warn-item { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-bottom: 4px; }
.rat-item { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin-bottom: 2px; }
.warnings { margin-top: 8px; }
.warn-item { color: var(--trend-up); }
</style>
