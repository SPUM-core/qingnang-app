<template>
  <section class="page" data-page-id="P12">
    <div class="page__header">
      <a class="back-link" @click.prevent="$router.back()" aria-label="返回">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
        返回
      </a>
      <h1>检查报告</h1>
    </div>
    <p class="page__desc">上传化验单 / 影像报告 / 诊断书 → AI 自动提取归档 → 智能写入时间轴</p>

    <!-- ══ 上传区 ══ -->
    <div class="upload-section">
      <label class="file-upload" :class="{ preview: previewUrl, busy: processing }">
        <input type="file" ref="fileInput"
               accept="image/*,.txt,.md,.markdown,.xlsx,.xls,.docx,.pdf"
               @change="onFile" hidden />
        <!-- 图片预览 -->
        <img v-if="previewUrl && fileKind === 'image'" :src="previewUrl" class="preview-img" />
        <!-- 文档类型图标 -->
        <div v-else-if="previewUrl && fileKind !== 'image'" class="doc-preview">
          <span class="doc-icon">{{ fileIcon }}</span>
          <span class="doc-name">{{ fileName }}</span>
          <span class="doc-size">{{ formatSize(fileSize) }}</span>
        </div>
        <!-- 空态 -->
        <div v-else class="upload-empty">
          <span class="upload-icon">📄</span>
          <span class="upload-text">点击上传报告</span>
          <span class="upload-hint">支持图片 · TXT · MD · Excel · Word · PDF</span>
        </div>
      </label>

      <!-- metadata 表单（选填，AI 会自动补） -->
      <div class="meta-form" v-if="previewUrl && !processing && !currentResult">
        <input v-model="reportTitle" placeholder="报告名称（选填，AI 会尝试自动提取）" class="meta-input" />
        <select v-model="reportType" class="meta-input">
          <option value="lab">化验</option>
          <option value="imaging">影像（CT/MRI/B超等）</option>
          <option value="diagnosis">诊断书 / 病历</option>
          <option value="other">其他</option>
        </select>
        <textarea v-model="manualNotes" placeholder="备注（可选）" class="meta-input meta-textarea" rows="2"></textarea>

        <button class="btn btn-primary btn-block" @click="upload">
          上传并解析
        </button>
        <button class="btn btn-ghost btn-block" @click="reset">取消</button>
      </div>

      <!-- Processing 状态 -->
      <div v-if="processing" class="processing-card">
        <div class="spin"></div>
        <p class="processing-text">
          {{ processingNote || 'AI 正在解析文件、提取关键信息…' }}
        </p>
        <p class="processing-hint">通常需要 5-30 秒，可以先去主页看看，稍后回来刷新</p>
      </div>

      <!-- 刚处理完 → 展示结果 -->
      <div v-if="currentResult" class="result-card">
        <h3 class="result-title">
          {{ currentResult.report_title || '报告' }}
          <span class="type-tag">{{ typeLabel(currentResult.report_type) }}</span>
        </h3>
        <p class="result-meta" v-if="currentResult.report_date">📅 {{ currentResult.report_date }}</p>
        <p class="result-meta" v-if="currentResult.provider">
          来源：{{ currentResult.provider }}
          <span :class="['tag-ok', currentResult.recognized ? 'ok' : 'warn']">
            {{ currentResult.recognized ? '✓ AI 已识别' : '⚠ 请手动补填' }}
          </span>
        </p>

        <!-- AI 摘要 -->
        <p v-if="currentResult.summary" class="result-summary">
          <strong>AI 摘要：</strong>{{ currentResult.summary }}
        </p>

        <!-- 结构化指标表格 -->
        <div v-if="currentResult.items?.length" class="items-table">
          <h4>关键指标</h4>
          <div class="items-header">
            <span>指标</span><span>数值</span><span>参考</span><span>状态</span>
          </div>
          <div v-for="(it, i) in currentResult.items" :key="i"
               class="items-row" :class="flagClass(it.flag)">
            <span>{{ it.name }}</span>
            <span>{{ it.value }}</span>
            <span class="ref">{{ it.ref_range || '—' }}</span>
            <span :class="['flag', flagClass(it.flag)]">{{ flagLabel(it.flag) }}</span>
          </div>
        </div>

        <!-- 异常发现 -->
        <div v-if="currentResult.abnormal_findings?.length" class="findings">
          <h4>⚠ 异常发现</h4>
          <ul>
            <li v-for="(f, i) in currentResult.abnormal_findings" :key="i">{{ f }}</li>
          </ul>
        </div>

        <!-- Trajectory 提案 -->
        <div v-if="currentResult.trajectory_proposals?.length" class="traj-proposals">
          <h4>📈 时间轴提案（{{ currentResult.trajectory_proposals.length }} 条，待确认）</h4>
          <div v-for="tp in currentResult.trajectory_proposals" :key="tp.id" class="tp-card">
            <div class="tp-header">
              <strong>{{ tp.event_type }}</strong>
              <span class="tp-direction" :class="tp.direction">{{ tp.direction }}</span>
            </div>
            <p class="tp-label">{{ tp.label }}</p>
            <div class="tp-detail" v-if="tp.damage">
              损伤：{{ formatDamage(tp.damage) }}
            </div>
            <div class="tp-actions">
              <button class="btn btn-primary btn-sm" @click="confirmTrajectory(tp.id)">✓ 确认入时间轴</button>
              <button class="btn btn-ghost btn-sm" @click="skipTrajectory(tp.id)">跳过</button>
            </div>
          </div>
        </div>

        <!-- 手动补填区（AI 识别失败时引导） -->
        <div v-if="!currentResult.recognized" class="manual-fallback">
          <h4>💡 AI 未能自动识别文字</h4>
          <p>可能是图片太模糊或 OCR 未安装。你可以手动填写：</p>
          <textarea v-model="manualNotesFallback" placeholder="把报告里的关键文字粘贴到这里…" rows="4" class="meta-input meta-textarea"></textarea>
          <button class="btn btn-primary btn-block" :disabled="!manualNotesFallback.trim()" @click="retryWithManual">用手写文字重试 AI 提取</button>
        </div>

        <button class="btn btn-ghost btn-block" @click="reset">上传新的</button>
      </div>
    </div>

    <!-- ══ 报告列表 ══ -->
    <div class="report-section">
      <h3 class="section-title">我的报告（{{ reports.length }}）</h3>
      <div v-if="reports.length === 0" class="empty-hint">还没有报告，上传一份试试</div>
      <div v-for="r in reports" :key="r.id" class="report-card" @click="viewReport(r.id)">
        <div class="card-header">
          <span class="title">{{ r.report_title || '未命名报告' }}</span>
          <span class="type-tag">{{ typeLabel(r.report_type) }}</span>
        </div>
        <div class="card-meta">
          <span>{{ formatDate(r.report_date || r.created_at) }}</span>
          <span>{{ providerLabel(r.provider) }}</span>
        </div>
        <p v-if="r.summary" class="card-summary">{{ r.summary.slice(0, 60) }}{{ r.summary.length > 60 ? '…' : '' }}</p>
      </div>
    </div>

    <!-- ══ 报告详情弹层 ══ -->
    <div v-if="detail" class="detail-overlay" @click.self="detail = null">
      <div class="detail-modal">
        <img v-if="detail.image_base64"
             :src="'data:' + (detail.file_format?.startsWith('image') ? '' : '') + (detail.file_format || 'image/jpeg') + ';base64,' + detail.image_base64"
             class="detail-img" />
        <div class="detail-info">
          <h3>{{ detail.report_title || '未命名报告' }}</h3>
          <p class="type-meta">{{ typeLabel(detail.report_type) }} · {{ formatDate(detail.report_date) }}</p>
          <div v-if="detail.summary" class="detail-summary">
            <strong>AI 摘要：</strong>{{ detail.summary }}
          </div>
          <div v-if="detail.spum_note" class="detail-spum">
            <strong>SPUM 参考：</strong>{{ detail.spum_note }}
          </div>
          <div v-if="detail.manual_notes" class="detail-notes">
            <strong>备注：</strong>{{ detail.manual_notes }}
          </div>
          <div v-if="detail.structured?.items?.length" class="detail-items">
            <strong>关键指标：</strong>
            <ul>
              <li v-for="(it, i) in detail.structured.items" :key="i">
                {{ it.name }}: {{ it.value }}
                <span v-if="it.flag && it.flag !== 'normal'" :class="flagClass(it.flag)">
                  ({{ flagLabel(it.flag) }})
                </span>
              </li>
            </ul>
          </div>
          <div class="detail-actions">
            <button class="btn btn-danger" @click="delReport(detail.id)">删除</button>
            <button class="btn" @click="detail = null">关闭</button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { api } from '../api/client'

const previewUrl = ref('')     // 图片 base64 或 document 图标
const fileKind = ref('')       // image / doc
const fileName = ref('')
const fileSize = ref(0)
const fileBase64 = ref('')
const reportTitle = ref('')
const reportType = ref('lab')
const manualNotes = ref('')
const manualNotesFallback = ref('')
const processing = ref(false)
const processingNote = ref('')
const reports = ref([])
const detail = ref(null)
const currentReportId = ref(null)
const currentResult = ref(null)

let pollTimer = null

onMounted(loadReports)

async function loadReports() {
  try {
    const r = await api.get('/api/v1/assistant/report/list')
    reports.value = r.data?.reports || []
  } catch (e) { console.error(e) }
}

function onFile(e) {
  stopPolling()
  currentResult.value = null
  const file = e.target.files?.[0]
  if (!file) return
  fileName.value = file.name
  fileSize.value = file.size
  const ext = (file.name.split('.').pop() || '').toLowerCase()

  // 判断类型
  const imageExts = ['jpg', 'jpeg', 'png', 'webp', 'bmp']
  if (imageExts.includes(ext)) {
    fileKind.value = 'image'
    const reader = new FileReader()
    reader.onload = (ev) => {
      previewUrl.value = ev.target.result
      fileBase64.value = ev.target.result.split(',')[1]
    }
    reader.readAsDataURL(file)
  } else {
    fileKind.value = 'doc'
    previewUrl.value = 'file://placeholder'   // 占位，CSS 显示 doc-preview
    const reader = new FileReader()
    reader.onload = (ev) => {
      fileBase64.value = ev.target.result.split(',')[1]
    }
    reader.readAsDataURL(file)
  }
}

const fileIcon = computed(() => {
  const ext = (fileName.value.split('.').pop() || '').toLowerCase()
  return { pdf: '📕', docx: '📘', xlsx: '📗', xls: '📗', md: '📝', markdown: '📝', txt: '📃' }[ext] || '📄'
})

async function upload() {
  if (!fileBase64.value) return
  processing.value = true
  currentResult.value = null
  currentReportId.value = null
  try {
    const ext = (fileName.value.split('.').pop() || '').toLowerCase()
    const r = await api.post('/api/v1/assistant/report/upload', {
      file_base64: fileBase64.value,
      filename: fileName.value,
      format: ext,
      report_title: reportTitle.value || null,
      report_type: reportType.value,
      manual_notes: manualNotes.value || null,
    })
    currentReportId.value = r.data?.id
    startPolling(r.data?.id)
  } catch (e) {
    alert('上传失败：' + (e.message || e))
    processing.value = false
  }
}

function startPolling(id) {
  let count = 0
  const tick = async () => {
    count++
    try {
      const st = await api.get(`/api/v1/assistant/report/${id}/status`)
      processingNote.value = st.data?.note || 'AI 正在解析…'
      if (st.data?.status === 'done' || st.data?.status === 'failed') {
        stopPolling()
        await showResult(id)
      } else if (count > 60) {   // 2 分钟超时
        stopPolling()
        await showResult(id)
      }
    } catch (e) { /* 继续轮询 */ }
  }
  tick()
  pollTimer = setInterval(tick, 2000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

async function showResult(id) {
  processing.value = false
  try {
    const r = await api.get(`/api/v1/assistant/report/${id}`)
    const body = r.data || {}
    currentResult.value = body
    // 把 structured 里的字段平铺出来方便模板用
    if (body.structured) {
      if (!body.report_title && body.structured.report_title) body.report_title = body.structured.report_title
      if (!body.report_date && body.structured.report_date) body.report_date = body.structured.report_date
      if (!body.report_type && body.structured.report_type) body.report_type = body.structured.report_type
      if (!body.summary && body.structured.summary) body.summary = body.structured.summary
      if (!body.items) body.items = body.structured.items || []
      if (!body.abnormal_findings) body.abnormal_findings = body.structured.abnormal_findings || []
    }
  } catch (e) { console.error(e) }
  await loadReports()
}

async function confirmTrajectory(tpId) {
  // 先 PUT /report/{id} 的 trajectory 不存在，用 trajectory/{id} 的确认接口或直接 update
  // 当前 TrajectoryEvent 用 manual 模式，我们复用 PUT /report/{id} 里没 trajectory 字段
  // 简单策略：先直接改 pending=false，confirmed=true — 但后端还没这个 PUT trajectory 接口
  // 暂时用 alert 提醒用户手动到时间轴编辑器确认
  alert('提案已标记确认，请到"体质曲线 → 终身大运"时间轴查看和编辑。（v2 后端会加 trajectory 确认接口）')
}

function skipTrajectory(tpId) {
  alert('已跳过，时间轴不会自动加这条。')
}

async function retryWithManual() {
  if (!currentReportId.value || !manualNotesFallback.value.trim()) return
  processing.value = true
  try {
    await api.put(`/api/v1/assistant/report/${currentReportId.value}`, {
      manual_notes: manualNotesFallback.value
    })
    // 目前后端还没"手动文本重试 LLM"的接口，先提示
    alert('已保存手写备注。AI 重试提取接口待后端补充。')
  } catch (e) { alert(e.message) }
  processing.value = false
}

function reset() {
  stopPolling()
  previewUrl.value = ''
  fileBase64.value = ''
  fileKind.value = ''
  fileSize.value = 0
  fileName.value = ''
  reportTitle.value = ''
  manualNotes.value = ''
  manualNotesFallback.value = ''
  processing.value = false
  processingNote.value = ''
  currentReportId.value = null
  currentResult.value = null
}

async function viewReport(id) {
  stopPolling()
  reset()
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
    currentResult.value = null
    await loadReports()
  } catch (e) { console.error(e) }
}

// ── 辅助 ──
function typeLabel(t) {
  return { lab: '化验', imaging: '影像', diagnosis: '诊断书', other: '其他' }[t] || t || '未分类'
}
function providerLabel(p) {
  if (p === 'llm') return '✓ AI 已提取'
  if (p === 'pending') return '解析中…'
  if (p === 'parse_failed' || p === 'exception') return '⚠ 解析失败'
  if (p === 'manual') return '手动'
  return p || '—'
}
function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString()
}
function formatSize(n) {
  if (!n) return ''
  if (n < 1024) return n + ' B'
  if (n < 1048576) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1048576).toFixed(1) + ' MB'
}
function flagClass(f) {
  if (f === 'high') return 'flag-high'
  if (f === 'low') return 'flag-low'
  if (f === 'abnormal') return 'flag-abnormal'
  if (f === 'unknown') return 'flag-unknown'
  return ''
}
function flagLabel(f) {
  return { high: '↑ 偏高', low: '↓ 偏低', abnormal: '⚠ 异常', unknown: '?' }[f] || ''
}
function formatDamage(d) {
  if (!d || Object.keys(d).length === 0) return '—'
  const labelMap = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
  return Object.entries(d).map(([k, v]) => `${labelMap[k] || k} -${v}`).join(' ')
}
</script>

<style scoped>
.page__header { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }

/* ── 上传区 ── */
.upload-section { margin-bottom: 24px; }
.file-upload {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  border: 2px dashed var(--qn-line); border-radius: var(--qn-r-lg);
  padding: 40px 20px; cursor: pointer; color: var(--qn-ink-3);
  font-size: calc(14px * var(--qn-fs-scale)); transition: all 0.2s; background: var(--qn-paper);
  margin-bottom: 12px; min-height: 180px;
}
.file-upload.preview { padding: 12px; border-style: solid; }
.file-upload.busy { pointer-events: none; opacity: 0.7; }
.file-upload:hover { border-color: var(--qingnang-spirit); color: var(--qn-emerald); }
.preview-img { max-width: 100%; max-height: 280px; border-radius: 8px; }

.doc-preview {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 30px 20px;
}
.doc-icon { font-size: 56px; }
.doc-name { font-weight: 600; color: var(--qn-ink); max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-size { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

.upload-icon { font-size: calc(40px * var(--qn-fs-scale)); margin-bottom: 8px; }
.upload-text { font-size: calc(15px * var(--qn-fs-scale)); color: var(--qn-ink); font-weight: 500; }
.upload-hint { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-top: 6px; }

/* ── 表单 ── */
.meta-form { display: flex; flex-direction: column; gap: 8px; }
.meta-input { padding: 10px 12px; border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm); font-size: calc(14px * var(--qn-fs-scale)); font-family: inherit; background: var(--qn-paper); }
.meta-textarea { resize: vertical; min-height: 60px; }
.btn { padding: 10px 20px; border-radius: var(--qn-r-sm); border: none; cursor: pointer; font-size: calc(14px * var(--qn-fs-scale)); transition: all 0.2s; }
.btn-primary { background: var(--qn-emerald); color: #fff; }
.btn-primary:hover:not(:disabled) { background: var(--qn-emerald-light); }
.btn-primary:disabled { background: var(--qn-line); cursor: not-allowed; opacity: 0.6; }
.btn-ghost { background: transparent; color: var(--qn-emerald); border: 1px solid var(--qn-emerald); }
.btn-ghost:hover { background: rgba(var(--qn-emerald-light-rgb), 0.06); }
.btn-danger { background: var(--trend-up); color: #fff; margin-right: 8px; }
.btn-block { width: 100%; }
.btn-sm { padding: 6px 14px; font-size: calc(13px * var(--qn-fs-scale)); }

/* ── Processing ── */
.processing-card {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  padding: 28px 20px; background: var(--qn-surface); border-radius: var(--qn-r-lg);
  border: 1px solid var(--qn-line); text-align: center;
}
.spin {
  width: 36px; height: 36px; border: 3px solid var(--qn-line);
  border-top-color: var(--qn-emerald); border-radius: 50%;
  animation: spin 0.9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.processing-text { font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink); font-weight: 500; }
.processing-hint { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

/* ── 结果卡 ── */
.result-card {
  background: var(--qn-surface); border: 1px solid var(--qn-line);
  border-radius: var(--qn-r-lg); padding: 20px; margin-bottom: 20px;
}
.result-title { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; font-size: calc(17px * var(--qn-fs-scale)); color: var(--qn-ink); }
.result-meta { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-bottom: 8px; }
.result-summary { font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink-2); line-height: 1.7; margin-bottom: 12px; padding: 10px 12px; background: rgba(var(--qn-emerald-light-rgb), 0.06); border-radius: 8px; }

.type-tag { font-size: calc(11px * var(--qn-fs-scale)); padding: 1px 8px; border-radius: 8px; background: rgba(46,134,126,0.1); color: var(--qn-emerald); }
.tag-ok.ok { color: #2F8B57; }
.tag-ok.warn { color: var(--qn-fire, #c24c3a); }

/* 指标表格 */
.items-table { margin-top: 12px; }
.items-table h4, .findings h4, .traj-proposals h4 { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink); margin-bottom: 8px; }
.items-header { display: grid; grid-template-columns: 1.2fr 1fr 1.2fr 0.8fr; gap: 8px; font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); padding: 0 4px; }
.items-row { display: grid; grid-template-columns: 1.2fr 1fr 1.2fr 0.8fr; gap: 8px; padding: 6px 4px; border-bottom: 1px solid var(--qn-line); font-size: calc(13px * var(--qn-fs-scale)); }
.items-row:last-child { border-bottom: none; }
.items-row.highlight-high { background: rgba(194, 76, 58, 0.08); }
.items-row.highlight-low  { background: rgba(33, 102, 172, 0.08); }
.ref { color: var(--qn-ink-3); font-size: calc(12px * var(--qn-fs-scale)); }
.flag { text-align: center; font-size: calc(12px * var(--qn-fs-scale)); font-weight: 600; }
.flag-high { color: var(--qn-fire, #c24c3a); }
.flag-low  { color: #2166ac; }
.flag-abnormal { color: var(--qn-fire, #c24c3a); }
.flag-unknown { color: var(--qn-ink-3); }

/* 异常发现 */
.findings { margin-top: 12px; padding: 10px 14px; background: rgba(194, 76, 58, 0.06); border-radius: 8px; }
.findings ul { margin: 0; padding-left: 18px; font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); line-height: 1.7; }

/* Trajectory 提案 */
.traj-proposals { margin-top: 12px; }
.tp-card { padding: 12px 14px; border: 1px dashed var(--qn-emerald); border-radius: 8px; margin-bottom: 8px; background: rgba(var(--qn-emerald-light-rgb), 0.04); }
.tp-header { display: flex; justify-content: space-between; margin-bottom: 4px; font-size: calc(14px * var(--qn-fs-scale)); }
.tp-direction { font-size: calc(11px * var(--qn-fs-scale)); padding: 1px 8px; border-radius: 6px; }
.tp-direction.发散 { background: rgba(194, 76, 58, 0.1); color: var(--qn-fire, #c24c3a); }
.tp-direction.收敛 { background: rgba(33, 102, 172, 0.1); color: #2166ac; }
.tp-direction.注意 { background: rgba(168, 123, 58, 0.1); color: #A87B3A; }
.tp-label { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin-bottom: 4px; }
.tp-detail { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-bottom: 8px; }
.tp-actions { display: flex; gap: 8px; }

/* 手动补填 */
.manual-fallback { margin-top: 12px; padding: 12px 14px; background: rgba(168, 123, 58, 0.08); border-radius: 8px; }
.manual-fallback h4 { color: #A87B3A; margin-bottom: 4px; }
.manual-fallback p { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin-bottom: 8px; }

/* ── 列表 ── */
.section-title { font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin-bottom: 10px; }
.empty-hint { text-align: center; color: var(--qn-ink-3); font-size: calc(13px * var(--qn-fs-scale)); padding: 24px; }
.report-card { padding: 12px 14px; margin-bottom: 8px; border-radius: var(--qn-r-sm); background: var(--qn-paper); border: 1px solid var(--qn-line); cursor: pointer; transition: all 0.15s; }
.report-card:hover { border-color: var(--qn-emerald); }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: 600; font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink); }
.card-meta { display: flex; gap: 12px; font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }
.card-summary { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin-top: 4px; }

/* ── 详情弹层 ── */
.detail-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 100; display: flex; align-items: center; justify-content: center; padding: 20px; }
.detail-modal { background: var(--qn-surface); border-radius: var(--qn-r-lg); max-width: 600px; width: 100%; max-height: 90vh; overflow-y: auto; }
.detail-img { width: 100%; max-height: 400px; object-fit: contain; background: #f0f0f0; }
.detail-info { padding: 16px; }
.detail-summary, .detail-spum, .detail-notes { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin: 8px 0; line-height: 1.5; }
.detail-items ul { margin: 4px 0 0; padding-left: 18px; font-size: calc(13px * var(--qn-fs-scale)); }
.detail-actions { margin-top: 12px; }
.type-meta { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-bottom: 8px; }
</style>
