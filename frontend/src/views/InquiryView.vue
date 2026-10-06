<template>
  <section class="page inquiry">
    <!-- 未启动态 -->
    <div v-if="!sessionId" class="inquiry__start">
      <h2 class="page-title">📋 问诊采集</h2>
      <p class="page-desc">
        通过 AI 引导的多阶段问诊，帮你梳理当前状态倾向。
        选择题为主，不会花太久。
      </p>
      <div class="start-info">
        <div class="info-row"><span class="num">4</span><span class="info-text">个阶段逐步深入</span></div>
        <div class="info-row"><span class="num">8-12</span><span class="info-text">道选择题 + 可追加备注</span></div>
        <div class="info-row"><span class="num">~3</span><span class="info-text">分钟完成</span></div>
      </div>
      <button class="primary-btn" :disabled="loading" @click="startSession">
        <span v-if="loading">生成第一阶段问题…</span>
        <span v-else>开始问诊</span>
      </button>
    </div>

    <!-- 进行中 -->
    <div v-else-if="status !== 'completed'" class="inquiry__active">
      <!-- 阶段进度 -->
      <div class="progress-bar">
        <div
          v-for="s in STAGES"
          :key="s.key"
          class="stage-dot"
          :class="{
            done: currentStageIdx > s.idx,
            active: currentStageIdx === s.idx,
          }"
        >
          <span class="dot-num">{{ s.idx + 1 }}</span>
          <span class="dot-label">{{ s.label }}</span>
        </div>
      </div>

      <!-- 阶段标题 -->
      <div class="stage-header">
        <h3>{{ stageLabel || STAGES[currentStageIdx]?.label }}</h3>
        <p class="stage-desc">{{ stageDesc }}</p>
      </div>

      <!-- 问题列表 -->
      <div class="questions">
        <div v-for="(q, qi) in questions" :key="q.id" class="q-card"
             :class="{ answered: isAnswered(q), skipped: answers[q.id]?.skipped }">
          <div class="q-header">
            <span class="q-num" :class="{ skipped: answers[q.id]?.skipped }">
              Q{{ qi + 1 }}{{ answers[q.id]?.skipped ? ' · 已跳过' : '' }}
            </span>
            <span class="q-text" :class="{ skipped: answers[q.id]?.skipped }">{{ q.text }}</span>
          </div>

          <!-- 单选 -->
          <div v-if="q.type === 'single' && !answers[q.id]?.skipped" class="opt-list">
            <button
              v-for="o in q.options" :key="o.id"
              class="opt-btn"
              :class="{ selected: answers[q.id]?.value === o.id }"
              @click="answers[q.id] = { value: o.id, label: o.label }"
            >{{ o.label }}</button>
          </div>

          <!-- 多选 -->
          <div v-else-if="q.type === 'multi' && !answers[q.id]?.skipped" class="opt-list">
            <button
              v-for="o in q.options" :key="o.id"
              class="opt-btn"
              :class="{ selected: (answers[q.id]?.values || []).includes(o.id) }"
              @click="toggleMulti(q.id, o)"
            >{{ o.label }}</button>
          </div>

          <!-- 纯文本 -->
          <input v-else-if="q.type === 'text' && !answers[q.id]?.skipped" class="text-input"
                 :placeholder="q.note_hint || '请输入…'"
                 :value="answers[q.id]?.text || ''"
                 @input="answers[q.id] = { text: $event.target.value }" />

          <!-- 备注 -->
          <div v-if="q.allow_note && !answers[q.id]?.skipped" class="note-row">
            <button class="note-toggle" @click="toggleNote(q.id)">
              <span>{{ notes[q.id] !== undefined ? '✎ 备注中' : '＋ 备注（可替代选择）' }}</span>
            </button>
            <textarea
              v-if="notes[q.id] !== undefined"
              class="note-input"
              rows="2"
              :placeholder="q.note_hint || '想补充点什么？（只写备注也可以提交这题）'"
              v-model="notes[q.id]"
              @input="onNoteInput(q)"
            />
          </div>

          <!-- 跳过按钮 -->
          <div v-if="q.allow_skip && !answers[q.id]?.skipped" class="skip-row">
            <button class="skip-btn" @click="skipQuestion(q.id)">跳过这题 →</button>
          </div>
          <div v-else-if="answers[q.id]?.skipped" class="unskip-row">
            <button class="unskip-btn" @click="unskipQuestion(q.id)">← 我想答这题</button>
          </div>
        </div>
      </div>

      <!-- 提交 -->
      <button class="primary-btn submit-btn" :disabled="!canSubmit || submitting" @click="submitAnswers">
        <span v-if="submitting">提交中…</span>
        <span v-else>{{ isFinal ? '完成问诊 → 查看状态摘要' : '提交并进入下一阶段' }}</span>
      </button>
      <p class="hint" v-if="!canSubmit">
        {{ unansweredCount > 0 ? `还有 ${unansweredCount} 道题没答（可跳过）` : '准备就绪' }}
      </p>
    </div>

    <!-- 完成 -->
    <div v-else class="inquiry__done">
      <div class="done-badge">✓</div>
      <h2>问诊完成</h2>
      <div v-if="summary" class="summary-card">
        <div class="summary-row">
          <span class="summary-label">核心状态倾向</span>
          <span class="summary-value">{{ summary.dominant_pattern }}</span>
        </div>
        <div class="summary-row" v-if="summary.confidence !== undefined">
          <span class="summary-label">可信度</span>
          <span class="summary-value">{{ Math.round(summary.confidence * 100) }}%</span>
        </div>
        <div v-if="summary.key_findings?.length" class="summary-block">
          <p class="summary-title">关键发现</p>
          <ul>
            <li v-for="(f, i) in summary.key_findings" :key="i">{{ f }}</li>
          </ul>
        </div>
        <div v-if="summary.lifestyle_tips?.length" class="summary-block">
          <p class="summary-title">生活建议</p>
          <ul>
            <li v-for="(t, i) in summary.lifestyle_tips" :key="i">{{ t }}</li>
          </ul>
        </div>
        <div v-if="summary.next_action" class="summary-row">
          <span class="summary-label">下一步建议</span>
          <span class="summary-value highlight">{{ summary.next_action }}</span>
        </div>
        <div v-if="summary.fallback" class="summary-warning">
          提示：当前 AI 模型未连接，本摘要由预设逻辑生成。
        </div>
      </div>
      <div class="done-actions">
        <button class="ghost-btn" @click="goChatWithSummary">💬 把这些告诉青囊 · 让 AI 解读</button>
        <button class="ghost-btn" @click="$router.back()">返回采集</button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import * as storage from '../utils/storage'

const router = useRouter()

const STAGES = [
  { key: "initial",  idx: 0, label: "主诉与核心症状" },
  { key: "deepen",   idx: 1, label: "症状深化" },
  { key: "expand",   idx: 2, label: "整体状态" },
  { key: "finalize", idx: 3, label: "关键判别点" },
]

const sessionId = ref(null)
const stage = ref("initial")
const stageLabel = ref("主诉与核心症状")
const stageDesc = ref("你现在最困扰的感受是什么？")
const questions = ref([])
const answers = reactive({})     // {qid: {value/values/text}}
const notes = reactive({})       // {qid: string}
const status = ref("active")
const summary = ref(null)
const loading = ref(false)
const submitting = ref(false)

const currentStageIdx = computed(() =>
  STAGES.findIndex(s => s.key === stage.value)
)
const isFinal = computed(() => stage.value === "finalize")

// 灵活判断：题算"已处理"（可以是选择了、写了备注、纯文本写了、或者允许跳过）
function isAnswered(q) {
  const a = answers[q.id]
  if (!a) return false
  if (a.skipped) return true
  // text type：有 text 值就算
  if (q.type === 'text') return !!a.text?.trim()
  // single / multi：有选择值就算
  if (q.type === 'single') return !!a.value
  if (q.type === 'multi') return (a.values?.length || 0) > 0
  return false
}

// 必须答的题（不可跳过 + 没答）
// 兜底：allow_skip 缺省当 true（宁肯让用户能跳过，不让提交按钮卡死）
const unansweredCount = computed(() =>
  questions.value.filter(q => {
    if (q.allow_skip !== false) return false   // 缺省 true → 可跳过，不算
    return !isAnswered(q)                       // 不可跳过且没答
  }).length
)

// 可提交：所有"不可跳过"的题都已答
const canSubmit = computed(() => unansweredCount.value === 0)

function skipQuestion(qid) {
  answers[qid] = { skipped: true }
}

function unskipQuestion(qid) {
  delete answers[qid]
}

// 备注输入时，自动创建空 answers 对象（表示"用备注作答"）
function onNoteInput(q) {
  const noteVal = notes[q.id]?.trim()
  if (!noteVal) return
  // 如果这题还没选也没跳过，自动补一个 answers 占位（让 isAnswered 在有备注时也算答）
  if (!answers[q.id] || answers[q.id].skipped) {
    if (q.type === 'multi') {
      answers[q.id] = answers[q.id] || { values: [], labels: [] }
    } else {
      answers[q.id] = answers[q.id] || {}
    }
  }
}

function toggleMulti(qid, opt) {
  // 如果之前跳过了，先取消跳过
  if (answers[qid]?.skipped) delete answers[qid]
  if (!answers[qid]?.values) {
    answers[qid] = { values: [], labels: [] }
  }
  const v = answers[qid].values
  const l = answers[qid].labels
  const i = v.indexOf(opt.id)
  if (i >= 0) { v.splice(i, 1); l.splice(i, 1) }
  else { v.push(opt.id); l.push(opt.label) }
}

function toggleNote(qid) {
  if (notes[qid] !== undefined) delete notes[qid]
  else notes[qid] = ""
}

async function startSession() {
  loading.value = true
  try {
    const provider = (storage.get('qingnang_settings', {}) || {}).llm_provider || 'spum'
    const r = await api.post('/api/v1/assistant/inquiry/start', { provider })
    loadStage(r.data)
  } catch (e) {
    alert(e.response?.data?.detail || '启动问诊失败')
  } finally { loading.value = false }
}

function loadStage(d) {
  sessionId.value = d.session_id
  stage.value = d.stage
  stageLabel.value = d.stage_label
  stageDesc.value = d.stage_desc
  questions.value = d.questions
  // 清上一阶段答案（保留历史 answers? 不——前端每阶段独立提交）
  // 但不清 notes，让用户能回来看到自己写了什么（简化：全清）
  Object.keys(answers).forEach(k => delete answers[k])
}

async function submitAnswers() {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true

  // 组装 answer payload
  const payload = {}
  for (const q of questions.value) {
    let a = answers[q.id]
    if (a) payload[q.id] = a
    // 备注合并进 payload
    if (notes[q.id]?.trim()) {
      payload[q.id] = { ...(payload[q.id] || {}), note: notes[q.id].trim() }
    }
  }

  try {
    const r = await api.post(
      `/api/v1/assistant/inquiry/${sessionId.value}/answer`,
      { stage: stage.value, answers: payload }
    )
    const d = r.data
    if (d.is_final && d.stage === "done") {
      status.value = "completed"
      summary.value = d.summary
    } else {
      loadStage(d)
    }
  } catch (e) {
    alert(e.response?.data?.detail || '提交失败')
  } finally { submitting.value = false }
}

function goChatWithSummary() {
  // 把 summary 的关键发现注入 localStorage，让青囊管家 AI 自动读取并解读
  const sm = summary.value
  if (sm) {
    storage.set('qingnang_inquiry_summary', {
      dominant_pattern: sm.dominant_pattern,
      key_findings: sm.key_findings?.slice(0, 3) || [],
      next_action: sm.next_action,
      ts: Date.now(),
    })
  }
  router.push('/')  // 回 Dashboard，青囊管家在那里
}

function resetSession() {
  sessionId.value = null
  stage.value = "initial"
  questions.value = []
  status.value = "active"
  summary.value = null
  Object.keys(answers).forEach(k => delete answers[k])
  Object.keys(notes).forEach(k => delete notes[k])
}
</script>

<style scoped>
.inquiry { max-width: 640px; margin: 0 auto; padding: 16px; }

.inquiry__start { text-align: center; padding: 32px 20px; }
.page-title { font-size: calc(22px * var(--qn-fs-scale)); font-weight: 600; margin-bottom: 8px; color: var(--qn-emerald); }
.page-desc { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin-bottom: 24px; line-height: 1.7; }
.start-info { display: flex; justify-content: center; gap: 24px; margin-bottom: 28px; }
.info-row { display: flex; flex-direction: column; align-items: center; }
.num { font-size: calc(22px * var(--qn-fs-scale)); font-weight: 700; color: var(--qn-emerald); }
.info-text { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-top: 4px; }

.primary-btn {
  background: var(--qn-emerald); color: #fff;
  border: none; padding: 14px 36px; border-radius: 24px;
  font-size: calc(14px * var(--qn-fs-scale)); font-weight: 600; cursor: pointer;
  transition: all 0.15s;
}
.primary-btn:hover:not(:disabled) { background: #166f63; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.submit-btn { margin-top: 20px; width: 100%; }
.hint { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); text-align: center; margin-top: 8px; }

/* 进度条 */
.progress-bar {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 8px; padding: 16px 4px 20px; border-bottom: 1px solid var(--qn-line); margin-bottom: 16px;
}
.stage-dot {
  display: flex; flex-direction: column; align-items: center; flex: 1;
  font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3);
}
.dot-num {
  width: 26px; height: 26px; border-radius: 50%;
  border: 2px solid var(--qn-line);
  display: flex; align-items: center; justify-content: center;
  font-size: calc(12px * var(--qn-fs-scale)); font-weight: 600; margin-bottom: 6px; background: var(--qn-surface);
}
.stage-dot.done .dot-num { background: var(--qn-emerald); border-color: var(--qn-emerald); color: #fff; }
.stage-dot.active .dot-num { border-color: var(--qn-emerald); color: var(--qn-emerald); font-weight: 700; transform: scale(1.1); }
.stage-dot.active { color: var(--qn-emerald); font-weight: 600; }
.dot-label { text-align: center; line-height: 1.2; }

.stage-header { text-align: center; margin-bottom: 20px; }
.stage-header h3 { margin: 0 0 6px; font-size: calc(16px * var(--qn-fs-scale)); color: var(--qn-ink); }
.stage-desc { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); }

/* 问题卡片 */
.questions { display: flex; flex-direction: column; gap: 16px; }
.q-card {
  /* ⚠️ border 已删 */
  background: var(--qn-surface);
  border-radius: var(--qn-r-lg); padding: 16px 18px;
}
.q-card.answered { border-color: var(--qn-emerald); background: rgba(var(--qn-emerald-light-rgb),0.03); }
.q-header { display: flex; gap: 10px; align-items: flex-start; margin-bottom: 12px; }
.q-num {
  background: var(--qn-emerald); color: #fff;
  font-size: calc(10px * var(--qn-fs-scale)); font-weight: 700;
  padding: 2px 7px; border-radius: 4px;
  flex-shrink: 0;
}
.q-text { font-size: calc(14px * var(--qn-fs-scale)); font-weight: 500; color: var(--qn-ink); line-height: 1.5; }

/* 选项 */
.opt-list { display: flex; flex-direction: column; gap: 8px; }
.opt-btn {
  padding: 11px 14px; border: 1px solid var(--qn-line);
  border-radius: 8px; background: var(--qn-surface); font-size: calc(13px * var(--qn-fs-scale));
  color: var(--qn-ink); cursor: pointer; text-align: left;
  transition: all 0.12s;
}
.opt-btn:hover { border-color: var(--qn-emerald); }
.opt-btn.selected {
  border-color: var(--qn-emerald);
  background: rgba(var(--qn-emerald-light-rgb),0.08);
  color: var(--qn-emerald);
  font-weight: 600;
}

.text-input {
  width: 100%; padding: 10px 12px; border: 1px solid var(--qn-line);
  border-radius: 8px; font-size: calc(13px * var(--qn-fs-scale)); font-family: inherit; resize: vertical;
  box-sizing: border-box;
}

.note-row { margin-top: 10px; }
.note-toggle {
  font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); background: none; border: none;
  cursor: pointer; padding: 0;
}
.note-toggle:hover { color: var(--qn-emerald); }
.note-input {
  width: 100%; padding: 8px 10px; border: 1px dashed var(--qn-line);
  border-radius: 6px; font-size: calc(12px * var(--qn-fs-scale)); margin-top: 6px; font-family: inherit;
  resize: vertical; box-sizing: border-box;
}

/* 完成页 */
.inquiry__done { text-align: center; padding: 20px 0; }
.done-badge {
  width: 60px; height: 60px; border-radius: 50%;
  background: var(--qn-emerald); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: calc(30px * var(--qn-fs-scale)); margin: 0 auto 16px;
}
.summary-card {
  /* ⚠️ border 已删 */
  background: var(--qn-surface);
  border-radius: var(--qn-r-lg); padding: 20px 22px;
  margin: 20px 0; text-align: left;
}
.summary-row { display: flex; justify-content: space-between; align-items: center; margin: 8px 0; }
.summary-label { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }
.summary-value { font-size: calc(14px * var(--qn-fs-scale)); font-weight: 500; color: var(--qn-ink); }
.summary-value.highlight { color: var(--qn-emerald); }
.summary-block { margin-top: 14px; padding-top: 12px; border-top: 1px dashed var(--qn-line); }
.summary-title { font-size: calc(12px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink-2); margin: 0 0 6px; text-transform: uppercase; letter-spacing: 1px; }
.summary-block ul { margin: 0; padding-left: 18px; font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink); line-height: 1.7; }
.summary-warning {
  background: rgba(216,125,27,0.08); border: 1px solid rgba(216,125,27,0.3);
  border-radius: 6px; padding: 8px 12px; font-size: calc(11px * var(--qn-fs-scale)); color: #b07612; margin-top: 12px;
}
.done-actions { display: flex; gap: 12px; justify-content: center; margin-top: 20px; }
.ghost-btn {
  padding: 10px 22px; border: 1px solid var(--qn-line);
  background: var(--qn-surface); border-radius: 20px; font-size: calc(13px * var(--qn-fs-scale));
  color: var(--qn-ink-2); cursor: pointer;
}
/* 跳过状态 */
.q-card.skipped {
  background: color-mix(in srgb, var(--qn-surface) 60%, transparent) !important;
  border-color: var(--qn-line) !important;
  opacity: 0.7;
}
.q-card.skipped .q-text { text-decoration: line-through; color: var(--qn-ink-3); }
.q-num.skipped { background: var(--qn-ink-3) !important; }
.q-text.skipped { color: var(--qn-ink-3); }

/* 跳过按钮 */
.skip-row { margin-top: 10px; text-align: right; }
.skip-btn {
  font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3);
  background: none; border: 1px dashed var(--qn-line);
  padding: 4px 12px; border-radius: 12px; cursor: pointer;
  transition: all 0.12s;
}
.skip-btn:hover { color: var(--qn-fire); border-color: var(--qn-fire); }

.unskip-row { margin-top: 10px; }
.unskip-btn {
  font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-emerald);
  background: none; border: 1px solid var(--qn-emerald);
  padding: 4px 12px; border-radius: 12px; cursor: pointer;
}
.unskip-btn:hover { background: rgba(var(--qn-emerald-light-rgb),0.08); }
</style>
