<template>
  <section class="page" data-page-id="P12">
    <div class="page__header">
      <a class="back-link" @click.prevent="$router.back()" aria-label="返回">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
        返回
      </a>
      <h1>检查报告</h1>
    </div>
    <p class="page__desc">上传化验单 / 影像报告 / 诊断书，自动归档可随时调取</p>

    <!-- 上传区 -->
    <div class="upload-section">
      <label class="file-upload" :class="{ preview: previewUrl }">
        <input type="file" accept="image/*" capture="environment" @change="onFile" hidden />
        <img v-if="previewUrl" :src="previewUrl" alt="报告预览" class="preview-img" />
        <div v-else class="upload-empty">
          <span class="upload-icon">📄</span>
          <span class="upload-text">点击或拍照上传报告</span>
        </div>
      </label>

      <!-- metadata 表单 -->
      <div class="meta-form" v-if="previewUrl">
        <input v-model="reportTitle" placeholder="报告名称（如：血常规、甲状腺功能）" class="meta-input" />
        <select v-model="reportType" class="meta-input">
          <option value="lab">化验</option>
          <option value="imaging">影像（CT/MRI/B超等）</option>
          <option value="diagnosis">诊断书 / 病历</option>
          <option value="other">其他</option>
        </select>
        <textarea v-model="manualNotes" placeholder="备注（可选，如：体检发现甲状腺结节）" class="meta-input meta-textarea" rows="2"></textarea>

        <button class="btn btn-primary btn-block" :disabled="uploading" @click="upload">
          {{ uploading ? '上传中...' : '上传报告' }}
        </button>
      </div>
    </div>

    <!-- 报告列表 -->
    <div class="report-section">
      <h3 class="section-title">我的报告（{{ reports.length }}）</h3>
      <div v-if="reports.length === 0" class="empty-hint">还没有报告，上传一张试试</div>
      <div v-for="r in reports" :key="r.id" class="report-card" @click="viewReport(r.id)">
        <div class="card-header">
          <span class="title">{{ r.report_title || '未命名报告' }}</span>
          <span class="type-tag">{{ typeLabel(r.report_type) }}</span>
        </div>
        <div class="card-meta">
          <span>{{ formatDate(r.report_date || r.created_at) }}</span>
          <span>{{ r.recognized ? '✓ 已识别' : '手动' }}</span>
        </div>
      </div>
    </div>

    <!-- 报告详情弹层 -->
    <div v-if="detail" class="detail-overlay" @click.self="detail = null">
      <div class="detail-modal">
        <img v-if="detail.image_base64"
             :src="'data:image/' + (detail.file_format || 'jpeg') + ';base64,' + detail.image_base64"
             class="detail-img" />
        <div class="detail-info">
          <h3>{{ detail.report_title || '未命名报告' }}</h3>
          <p class="type-meta">{{ typeLabel(detail.report_type) }} · {{ formatDate(detail.report_date) }}</p>
          <div v-if="detail.summary" class="detail-summary">
            <strong>摘要：</strong>{{ detail.summary }}
          </div>
          <div v-if="detail.spum_note" class="detail-spum">
            <strong>SPUM 参考：</strong>{{ detail.spum_note }}
          </div>
          <div v-if="detail.manual_notes" class="detail-notes">
            <strong>备注：</strong>{{ detail.manual_notes }}
          </div>
          <button class="btn btn-danger" @click="delReport(detail.id)">删除</button>
          <button class="btn" @click="detail = null">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client'

const previewUrl = ref('')
const reportTitle = ref('')
const reportType = ref('lab')
const manualNotes = ref('')
const uploading = ref(false)
const reports = ref([])
const detail = ref(null)
let fileName = ''

onMounted(loadReports)

async function loadReports() {
  try {
    const r = await api.get('/api/v1/assistant/report/list')
    reports.value = r.reports || []
  } catch (e) { console.error(e) }
}

function onFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  fileName = file.name
  const reader = new FileReader()
  reader.onload = (ev) => { previewUrl.value = ev.target.result }
  reader.readAsDataURL(file)
}

async function upload() {
  if (!previewUrl.value) return
  uploading.value = true
  try {
    const b64 = previewUrl.value.split(',')[1]
    const ext = fileName.split('.').pop()?.toLowerCase() || 'jpeg'
    await api.post('/api/v1/assistant/report/upload', {
      image_base64: b64,
      format: ext,
      report_title: reportTitle.value || null,
      report_type: reportType.value,
      manual_notes: manualNotes.value || null,
    })
    // 重置
    previewUrl.value = ''
    reportTitle.value = ''
    manualNotes.value = ''
    await loadReports()
  } catch (e) { alert('上传失败：' + e.message) }
  finally { uploading.value = false }
}

async function viewReport(id) {
  try {
    const r = await api.get(`/api/v1/assistant/report/${id}`)
    detail.value = r
  } catch (e) { console.error(e) }
}

async function delReport(id) {
  if (!confirm('确定删除这份报告？')) return
  try {
    await api.delete(`/api/v1/assistant/report/${id}`)
    detail.value = null
    await loadReports()
  } catch (e) { console.error(e) }
}

function typeLabel(t) {
  return { lab: '化验', imaging: '影像', diagnosis: '诊断书', other: '其他' }[t] || t
}
function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString()
}
</script>

<style scoped>
.page__header { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }

.upload-section { margin-bottom: 24px; }

.file-upload {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  border: 2px dashed var(--qn-line); border-radius: var(--qn-r-lg);
  padding: 40px 20px; cursor: pointer; color: var(--qn-ink-3);
  font-size: calc(14px * var(--qn-fs-scale)); transition: all 0.2s; background: var(--qn-paper);
  margin-bottom: 12px; min-height: 180px;
}
.file-upload.preview { padding: 12px; border-style: solid; }
.file-upload:hover { border-color: var(--qingnang-spirit); color: var(--qn-emerald); }

.preview-img { max-width: 100%; max-height: 280px; border-radius: 8px; }
.upload-icon { font-size: calc(48px * var(--qn-fs-scale)); margin-bottom: 8px; }

.meta-form { display: flex; flex-direction: column; gap: 8px; }
.meta-input { padding: 10px 12px; border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm); font-size: calc(14px * var(--qn-fs-scale)); font-family: var(--qn-font-body); background: var(--qn-paper); }
.meta-textarea { resize: vertical; }

.btn { padding: 10px 20px; border-radius: var(--qn-r-sm); border: none; cursor: pointer; font-size: calc(14px * var(--qn-fs-scale)); font-family: var(--qn-font-body); transition: all 0.2s; }
.btn-primary { background: var(--qn-emerald); color: #fff; }
.btn-primary:hover:not(:disabled) { background: var(--qn-emerald-light); }
.btn-primary:disabled { background: var(--qn-line); cursor: not-allowed; opacity: 0.6; }
.btn-danger { background: var(--trend-up); color: #fff; margin-right: 8px; }
.btn-block { width: 100%; }

.section-title { font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin-bottom: 10px; }
.empty-hint { text-align: center; color: var(--qn-ink-3); font-size: calc(13px * var(--qn-fs-scale)); padding: 24px; }

.report-card { display: flex; flex-direction: column; gap: 4px; padding: 12px 14px; margin-bottom: 8px;
              border-radius: var(--qn-r-sm); background: var(--qn-paper); border: 1px solid var(--qn-line);
              cursor: pointer; transition: all 0.15s; }
.report-card:hover { border-color: var(--qn-emerald); }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: 600; font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink); }
.type-tag { font-size: calc(11px * var(--qn-fs-scale)); padding: 1px 8px; border-radius: 8px; background: rgba(46,134,126,0.1); color: var(--qn-emerald); }
.card-meta { display: flex; gap: 12px; font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

/* 详情弹层 */
.detail-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 100; display: flex; align-items: center; justify-content: center; padding: 20px; }
.detail-modal { background: var(--qn-surface); border-radius: var(--qn-r-lg); max-width: 600px; width: 100%; max-height: 90vh; overflow-y: auto; }
.detail-img { width: 100%; max-height: 400px; object-fit: contain; background: #f0f0f0; }
.detail-info { padding: 16px; }
.detail-summary, .detail-spum, .detail-notes { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin: 8px 0; line-height: 1.5; }
.type-meta { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-bottom: 8px; }
</style>
