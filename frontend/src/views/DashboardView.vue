<template>
  <!-- ══ M1 下拉刷新 + 页面容器
       手势/动画已抽离 → modules/PullRefreshBar.vue ══ -->
  <section class="page home">
    <PullRefreshBar :refresh-fn="_lightRefresh">
    <!-- 问候头部（已抽离 → modules/GreetingHeader.vue） -->
    <GreetingHeader
      :greeting="greeting"
      :display-name="userStore.displayName"
      :today="today"
      :weekday="weekday"
      :case-status-label="caseStatusLabel"
      :observation-count="vectorStore.driftSeries?.length || 0"
      :archived-days="archivedDays"
    />

    <!-- 🎖️ 数字模型成熟度进度卡（4 阶段节点 + 总进度 + next_target）
         2026-10-04 隐藏：成熟度是后台隐形设定，AI 用它引导用户完善采集，不需要给用户看
         如需恢复：把 v-if="false" 改成 v-if="maturity" -->
    <div v-if="false && maturity" :class="['maturity-card', `stage-${maturity.stage}`]">
      <!-- 4 阶段节点横向进度 -->
      <div class="mc-track">
        <div class="mc-line">
          <div class="mc-fill" :style="{ width: maturityPercent + '%' }"></div>
        </div>
        <div v-for="(node, idx) in STAGE_NODES" :key="idx"
             :class="['mc-node', { done: idx + 1 < maturity.stage, current: idx + 1 === maturity.stage, locked: idx + 1 > maturity.stage }]">
          <span class="mc-node-ico">{{ node.icon }}</span>
          <span class="mc-node-label">{{ node.name }}</span>
          <span v-if="idx + 1 === maturity.stage" class="mc-node-cur">当前</span>
        </div>
      </div>
      <!-- 分数 + 分项进度 -->
      <div class="mc-body">
        <div class="mc-score">
          <span class="mc-score-num">{{ maturity.score }}</span>
          <span class="mc-score-max">/ {{ maturity.max_score || 11 }}</span>
          <span class="mc-score-pct">({{ maturityPercent }}%)</span>
        </div>
        <!-- 分项进度条（数据源：后端 /maturity 端点返回的 progress 字段） -->
        <div class="mc-items">
          <div class="mc-item" :class="{ done: maturity.progress?.profile_complete >= 4 }">
            <span class="mc-item-lbl">基本资料</span>
            <div class="mc-item-bar"><div class="mc-item-fill" :style="{ width: (maturity.progress?.profile_complete / 4 * 100) + '%' }"></div></div>
            <span class="mc-item-val">{{ maturity.progress?.profile_complete || 0 }}/4</span>
          </div>
          <div class="mc-item" :class="{ done: maturity.progress?.has_baseline }">
            <span class="mc-item-lbl">建档 + 基线</span>
            <div class="mc-item-bar"><div class="mc-item-fill" :style="{ width: maturity.progress?.has_baseline ? '100%' : '0%' }"></div></div>
            <span class="mc-item-val">{{ maturity.progress?.has_baseline ? '✅' : '—' }}</span>
          </div>
          <div class="mc-item" :class="{ done: (maturity.progress?.observation_count || 0) >= 3 }">
            <span class="mc-item-lbl">脉搏采集</span>
            <div class="mc-item-bar"><div class="mc-item-fill" :style="{ width: Math.min(100, (maturity.progress?.observation_count || 0) / 3 * 100) + '%' }"></div></div>
            <span class="mc-item-val">{{ maturity.progress?.observation_count || 0 }}/3</span>
          </div>
          <div class="mc-item" :class="{ done: maturity.progress?.inquiry_done }">
            <span class="mc-item-lbl">深度问诊</span>
            <div class="mc-item-bar"><div class="mc-item-fill" :style="{ width: maturity.progress?.inquiry_done ? '100%' : '0%' }"></div></div>
            <span class="mc-item-val">{{ maturity.progress?.inquiry_done ? '✅' : '—' }}</span>
          </div>
          <div class="mc-item" :class="{ done: (maturity.progress?.signal_tag_count || 0) >= 3 }">
            <span class="mc-item-lbl">生活信号</span>
            <div class="mc-item-bar"><div class="mc-item-fill" :style="{ width: Math.min(100, (maturity.progress?.signal_tag_count || 0) / 3 * 100) + '%' }"></div></div>
            <span class="mc-item-val">{{ maturity.progress?.signal_tag_count || 0 }}/3</span>
          </div>
        </div>
      </div>
      <!-- next_target 引导 -->
      <p v-if="maturity.next_target" class="mc-next">
        🎯 下一站：{{ maturity.next_target }}
      </p>
      <p v-if="maturity.missing_signals?.length" class="mc-missing">
        还差：{{ maturity.missing_signals.join(' · ') }}
      </p>
    </div>

    <!-- 注：问诊报告已迁移到「体质 → 报告时间线」统一展示，这里不再重复 -->

    <!-- ════ 英雄卡组：今日最重要的事 + 今日宜忌（独立两卡）
         内部组件已抽离 → modules/HeroTodoCard.vue + HeroDailyTipsCard.vue ════ -->
    <div class="hero-row">
      <HeroTodoCard
        :hero-todo="heroTodo"
        :anchor-safe="anchorSafe"
        @go-pending="goPending"
      />
      <HeroDailyTipsCard
        :anchor-safe="anchorSafe"
        :avoidance-notes="avoidanceNotes"
        @open-reminders="openReminders"
      />
    </div>

    <!-- ════ 第二行：体质调理曲线 + 今日时空锚点（横屏并列） ════ -->
    <div class="top-row">
      <!-- 左：体质调理曲线 → modules/ConstitutionCurveCard.vue -->
      <ConstitutionCurveCard
        v-model:chart-mode="chartMode"
        :drift-trajectory="driftTrajectory"
        :drift-series="driftSeries"
        :lifetime-available="!!vectorStore.lifetimeTrajectory"
        :chip-text="chartChipText"
        @navigate="$router.push({ name: 'trajectory' })"
      />

      <!-- 右：时空锚点 → modules/AnchorTimelineCard.vue -->
      <AnchorTimelineCard
        :anchor-safe="anchorSafe"
        :rhythm-segments="rhythmSegments"
        @explain="openAnchorExplain"
      />
    </div>

    <!-- ════ 生活提醒：Stage 2+ 才显示
         SSE / 缓存 / fallback 全留装配层 → modules/LifestyleReminderCard.vue 纯展示 ════ -->
    <LifestyleReminderCard
      :maturity-stage="maturity?.stage ?? 0"
      v-model:expanded="remExpanded"
      v-model:active-tab="activeRem"
      :rem-total="remTotal"
      :rem-tabs="remTabs"
      :lifestyle-loading="lifestyleLoading"
      :lifestyle-preview="lifestylePreview"
      :cloth-good-select="clothGoodSelect"
      :cloth-bad-select="clothBadSelect"
      :food-good-select="foodGoodSelect"
      :food-bad-select="foodBadSelect"
      :home-select="homeSelect"
      :relative-select="relativeSelect"
      :absolute-select="absoluteSelect"
      :stone-select="stoneSelect"
    />

    <!-- ════ 第二行：待办卡片网格 + 归档视图
         已抽离 → modules/LifeAdviceCard.vue（M8 PunchModal / M9 DetailModal 留在装配层） ════ -->
    <LifeAdviceCard
      :maturity-stage="maturity?.stage ?? 0"
      v-model:filter="activeFilter"
      :seg-tabs="segTabs"
      :filtered-todos="filteredTodos"
      :feedbacks-map="feedbacksMap"
      :archives="archives"
      :archived-days="archivedDays"
      :total-feedbacks="totalFeedbacks"
      :exec-label-fn="execLabel"
      @open-punch="openPunchModal"
      @open-detail="openDetailModal"
    />

    <!-- ════ M8 打卡弹窗 → modules/PunchModal.vue（props 进、emit 出） ════ -->
    <PunchModal
      :todo="punchModal.todo"
      :feedbacks="punchModal.feedbacks"
      :is-edit="punchModal.isEdit"
      :submitting="punchModal.submitting"
      :exec-label-fn="execLabel"
      @close="closePunchModal"
      @submit="handlePunchSubmit"
    />

    <!-- ════ M9 详情弹窗 → modules/DetailModal.vue ════ -->
    <DetailModal
      :modal="detailModal"
      :detail="dmDetail"
      :reason="dmReason"
      @close="closeDetailModal"
      @ask-qa="askDetailQA"
    />

    <!-- ════ 第三行：体质趋势（雷达图） ════
         已抽离 → modules/TrendRadarCard.vue -->
    <TrendRadarCard
      :v-base="vBase"
      :v-obs="latestObs"
      :trend-state-label="vectorStore.trendStateLabel"
      :delta-summary="deltaSummary"
      @go-case="goCase"
    />

    <!-- ════ 第四行：漂移矢量一览
         已抽离 → modules/DriftVectorCard.vue ════ -->
    <DriftVectorCard :rows="deltaTable" />

    <!-- ════ M12 AI 大白话解读 Modal → modules/AiExplainModal.vue ════ -->
    <AiExplainModal
      :modal="anchorModal"
      :render-markdown-fn="renderMarkdown"
      @close="anchorModal.show = false"
      @ask-assistant="continueWithAssistant"
    />
    </PullRefreshBar>
  </section>
</template>

<script setup>
import { computed, onMounted, onActivated, ref, watch, reactive, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useVectorStore } from '../stores/vector'
import { useUserStore } from '../stores/user'
import * as storage from '../utils/storage'
import { healthCheck, api, assistant as assistantApi, notifications as notifApi, lifestyleStream } from '../api/client'
import RadarChart from '../components/charts/RadarChart.vue'
import DriftChart from '../components/charts/DriftChart.vue'
import TodoCard from '../components/TodoCard.vue'
import QIcon from '../components/ui/QIcon.vue'
import GreetingHeader from '../modules/GreetingHeader.vue'
import TrendRadarCard from '../modules/TrendRadarCard.vue'
import DriftVectorCard from '../modules/DriftVectorCard.vue'
import PullRefreshBar from '../modules/PullRefreshBar.vue'
import HeroTodoCard from '../modules/HeroTodoCard.vue'
import HeroDailyTipsCard from '../modules/HeroDailyTipsCard.vue'
import LifestyleReminderCard from '../modules/LifestyleReminderCard.vue'
import LifeAdviceCard from '../modules/LifeAdviceCard.vue'
import ConstitutionCurveCard from '../modules/ConstitutionCurveCard.vue'
import AnchorTimelineCard from '../modules/AnchorTimelineCard.vue'
import PunchModal from '../modules/PunchModal.vue'
import DetailModal from '../modules/DetailModal.vue'
import AiExplainModal from '../modules/AiExplainModal.vue'
// mock 数据已移除——所有内容从后端 API / reasoning 端点实时获取
// 后端不可达时为空占位，不展示任何其他用户的病历数据

const router = useRouter()

// ═══════════════════════════════════════════════════════════
// 生活提醒数据源（全部从后端拉取，无任何用户特定硬编码）
// 后端不可达时显示"加载中"占位，不展示他人病历内容
// ═══════════════════════════════════════════════════════════
const anchor = reactive({
  ganzhi: '', dangling: '', dangling_elem: '',
  feixing: '', chong: '',
  jianchu: '', pengzu: '', shaxiang: '', richuxing: '', su: '',
  yi: '', ji: '',
  state: '',
  yuxiaji: '',     // ⭐ 玉匣记摘录
  weather: null,
})
const todayTimeline = ref([])
const clothReminders = ref([])
const foodGood = ref([])
const foodBad = ref([])
const homeReminders = ref([])
const absoluteAvoid = ref([])
const relativeAvoid = ref([])
const stoneReminders = ref([])

// ── Lifestyle 流式状态 ──
const lifestyleLoading = ref(false)
const lifestylePreview = ref('')   // 渐进 token 预览文本

// ── 时空锚点 AI 解读 Modal ──
const anchorModal = reactive({
  show: false, loading: false, error: '', text: '', engine: '',
})

async function openAnchorExplain() {
  // 把当前 anchorSafe 整包发给后端
  const payload = Object.fromEntries(
    Object.entries(anchorSafe.value).filter(([k, v]) =>
      v && k !== 'state' && k !== 'weather'    // state 是 UI 字段；weather 另一个接口
    )
  )
  if (!payload.ganzhi && !payload.yi) {
    anchorModal.error = '今日时空锚点数据还在加载，请稍等'
    anchorModal.show = true
    return
  }

  anchorModal.show = true
  anchorModal.loading = true
  anchorModal.error = ''
  anchorModal.text = ''
  anchorModal.engine = ''

  try {
    const r = await fetch('/api/v1/assistant/reasoning/anchor-explain', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + storage.getToken(),
      },
      body: JSON.stringify(payload),
    })
    const data = await r.json()
    if (data.ok && data.explain) {
      anchorModal.text = data.explain
      anchorModal.engine = data.engine || ''
    } else {
      anchorModal.error = data.message || '返回数据异常'
    }
  } catch (e) {
    anchorModal.error = e.message || '网络请求失败'
  } finally {
    anchorModal.loading = false
  }
}

// 极简 markdown → HTML：支持 **粗体**、✅/⚠️/💡 emoji、--- 分隔线、换行
// 先 escape 所有 HTML 再做 markdown 替换 —— 防 XSS
function renderMarkdown(md) {
  if (!md) return ''
  const escape = (s) => s
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
  let html = escape(md)
    .replace(/---/g, '<hr class="ae-hr">')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n+/g, '</p><p>')
    .replace(/\n/g, '<br>')
  return `<p>${html}</p>`
}

// ⭐ 和青囊管家继续聊：直接调用 window.__qingnangAssistant（QingnangAssistant onMounted 挂载）
function continueWithAssistant() {
  const assistant = window.__qingnangAssistant
  if (!assistant?.openWithContext) {
    // 管家组件还没挂载 —— 提示用户
    anchorModal.error = '青囊管家还在初始化，请稍后再试'
    return
  }
  const payload = {
    anchor: Object.fromEntries(
      Object.entries(anchorSafe.value).filter(([k, v]) => v && k !== 'state' && k !== 'weather')
    ),
    explain: anchorModal.text,
    followup: '关于今天的时空锚点解读，我还有一些问题想深入聊聊 —— 比如哪些建议我可以马上开始做？',
  }
  // 关掉 anchor modal → 让管家抽屉接管
  anchorModal.show = false
  // 等一帧让 DOM 清理完，再调 openWithContext
  requestAnimationFrame(() => {
    assistant.openWithContext(payload)
  })
}

// Tab 选择（生活提醒 mini）
const activeRem = ref('good')
const remExpanded = ref(false)   // 折叠行：默认收起
const remTabs = [
  { key: 'good', label: '宜·忌' },
  { key: 'home', label: '住房' },
  { key: 'avoid', label: '禁忌' }
]
const remTotal = computed(() =>
  clothReminders.value.length + foodGood.value.length + foodBad.value.length +
  homeReminders.value.length + absoluteAvoid.value.length +
  relativeAvoid.value.length + stoneReminders.value.length
)

// ── 英雄卡：今日最重要的事（第一件未完成的 P0，否则第一条待办）──
const heroTodo = computed(() => {
  const p0 = todos.value.find(t => t.priority === 'p0' && !t.done)
  return p0 || todos.value.find(t => !t.done) || todos.value[0] || null
})
function goPending() {
  activeFilter.value = 'pending'
  nextTick(() => document.querySelector('.scroll-target-advice')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}
function goCase() {
  router.push({ name: 'case' })
}
function openReminders() {
  remExpanded.value = true
  nextTick(() => document.querySelector('.scroll-target-life')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

// 精选筛选（压缩版：分类选 2 条 + 全部宜 3 条）
const clothGoodSelect = computed(() => clothReminders.value.filter(r => r.level === 'ok').slice(0, 2))
const clothBadSelect = computed(() => clothReminders.value.filter(r => r.level === 'bad').slice(0, 2))
const foodGoodSelect = computed(() => foodGood.value.slice(0, 2))
const foodBadSelect = computed(() => foodBad.value.slice(0, 2))
const homeSelect = computed(() => homeReminders.value)
const absoluteSelect = computed(() => absoluteAvoid.value)
const relativeSelect = computed(() => relativeAvoid.value)
const stoneSelect = computed(() => stoneReminders.value)

const vectorStore = useVectorStore()
const userStore = useUserStore()
const health = ref({ ok: false })

// 三曲线 trajectory：仅显示当前用户真实数据，无硬编码 fallback
const chartMode = ref('current')   // 'current' 观测曲线 | 'lifetime' 终身推演
const driftTrajectory = computed(() => {
  if (chartMode.value === 'lifetime' && vectorStore.lifetimeTrajectory) {
    return vectorStore.lifetimeTrajectory
  }
  // 真实数据优先（vectorStore.fetchTrajectory 拉后端 /cases/trajectories）
  if (vectorStore.trajectory?.actual?.length > 0) return vectorStore.trajectory
  // 无观测数据 → null（降级到 ΔV 漂移线模式，展示当前用户 v_base vs 观测）
  return null
})

const vBase = computed(() => vectorStore.vBase)
const latestObs = computed(() => vectorStore.latestObs)
const driftSeries = computed(() => vectorStore.driftSeries)

/* 体质曲线 chip 标签（原模板里的复杂三元表达式 → 移到 computed 纯函数） */
const chartChipText = computed(() => {
  if (chartMode.value === 'lifetime') {
    const lf = vectorStore.lifetimeTrajectory
    if (lf?.stateFlags?.length) {
      return `${lf.stateFlags.filter(s => s === 'disease').length}个疾病态`
    }
    return '八字推演'
  }
  return driftTrajectory.value ? '综合健康得分' : ('ΔV ' + vectorStore.trendStateLabel)
})

// 🎖️ 四阶段节点定义（图标 + 短名），与后端 STAGE_DEFS 对齐
const STAGE_NODES = [
  { icon: '🌱', name: '娱乐级' },
  { icon: '🍲', name: '食疗级' },
  { icon: '🏠', name: '调理级' },
  { icon: '🌿', name: '方剂级' },
]

// maturity 数据源：优先 userStore 全局缓存，兜底 fetchMe 后拉
const maturity = computed(() => userStore.maturity)
const maturityPercent = computed(() => {
  if (!maturity.value) return 0
  const max = maturity.value.max_score || 11
  return Math.min(100, Math.round((maturity.value.score || 0) / max * 100))
})

// 注：问诊报告入口已迁移到「体质 → 报告时间线」，相关 fetch / goInquiryDetail 已删除

/** 根据已采集 PPG 观测数量动态判定用户所处阶段 */
const caseStatusLabel = computed(() => {
  const n = driftSeries.value?.length || 0
  if (n === 0) return '数据收集中'
  if (n < 3) return '基线建立中'
  if (n < 8) return '调理进行中'
  return '调理中 · 稳定观察'
})

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  if (h < 22) return '晚上好'
  return '夜深了'
})
const today = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')}`
})
const weekday = computed(() => ['周日','周一','周二','周三','周四','周五','周六'][new Date().getDay()])

// anchor 安全访问：后端不可达时显示中性占位，不展示他人病历内容
const anchorSafe = computed(() => ({
  yi: anchor.yi || '加载中...',
  ji: anchor.ji || '加载中...',
  state: anchor.state || '',
  ganzhi: anchor.ganzhi || '待生成',
  dangling: anchor.dangling || '',
  dangling_elem: anchor.dangling_elem || '',
  feixing: anchor.feixing || '',
  chong: anchor.chong || '',
  jianchu: anchor.jianchu || '',
  pengzu: anchor.pengzu || '',
  shaxiang: anchor.shaxiang || '',
  richuxing: anchor.richuxing || '',
  su: anchor.su || '',
  yuxiaji: anchor.yuxiaji || '',
  weather: anchor.weather || null,
}))

const deltaTable = computed(() => {
  const labels = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
  const delta = vectorStore.deltaV || {}
  return ['wood','fire','earth','metal','water'].map(k => ({
    k, label: labels[k],
    base: vBase.value?.[k],
    obs: latestObs.value?.values?.[k],
    delta: delta[k]
  }))
})
const fmt = (v) => v == null ? '—' : Number(v).toFixed(1)

// ═══════════════════════════════════════════════════════════
// 待办系统：种子数据 + 每日更新 + 归档
// ═══════════════════════════════════════════════════════════

const activeFilter = ref('pending')  // 默认落在「待处理」，对齐设计稿

// 🎯 详情弹窗（替代手风琴展开）
const detailModal = ref(null)
function openDetailModal(todo) { detailModal.value = todo }
function closeDetailModal() { detailModal.value = null }

function buildTodayTodos() {
  // 空列表——待办由后端 /cases/today-todos 动态聚合
  // （1）notifications 生活提醒 （2）AI 对话的 analysis.suggestions
  return []
}

// 后端 priority → TodoCard priority 映射
function mapPriority(p) {
  return ({ high: 'p0', medium: 'p1', low: 'p2' })[p] || 'p1'
}

// 后端 todos → TodoCard 格式
function mapBackendTodo(t) {
  // 🎯 source_ref 只显示真正的经典出处（如《本草纲目》）
  // 不再把 "ai·diet" / "lifestyle" 这种来源标识当成出处
  const isLifestyle = t.source_type === 'lifestyle'
  const rawSource = t.source || ''
  const looksLikeSourceTag = rawSource.startsWith('ai·') || rawSource === 'lifestyle' || rawSource.startsWith('ai')
  const source_ref = t.source_ref || (isLifestyle && !looksLikeSourceTag ? rawSource : '')

  // 🎯 双保险：保证每个 todo 有唯一 id
  // 服务器旧版可能用 category（"diet"/"ai"）当 id → 全部重复
  // 用 source_type + source + title hash 出唯一 key
  const rawId = t.id || ''
  const needsFix = !rawId || /^[a-z]+$/.test(rawId)  // 只有单词（diet/ai）→ 太泛
  const uniqueId = needsFix
    ? `${t.source_type || 'x'}|${rawSource || ''}|${t.title || ''}`
    : rawId

  return {
    id: uniqueId,
    title: t.title,
    remind: t.desc || '',
    priority: mapPriority(t.priority),
    done: false,
    source: t.source_type || '',   // 纯来源标识，不显示给用户
    route: t.route,
    icon: t.icon,
    // LLM 详情字段：点击展开时显示
    detail: t.detail || '',
    reason: t.reason || '',
    source_ref,  // 经典出处（如《本草纲目》），空就不显示
  }
}

function getTodayKey() {
  return new Date().toISOString().slice(0, 10) // YYYY-MM-DD
}

function loadToday() {
  try {
    const data = storage.get('qingnang_today', null)
    if (data) {
      // 如果存的不是今天的日期，先归档昨天的再新建
      if (data.date !== getTodayKey()) {
        archiveYesterday(data)
        return buildTodayTodos()
      }
      return data.todos
    }
  } catch {}
  return buildTodayTodos()
}

function archiveYesterday(yesterdayData) {
  try {
    const archive = storage.get('qingnang_archive', [])
    archive.unshift({
      date: yesterdayData.date,
      todos: yesterdayData.todos.map(t => ({
        id: t.id,
        title: t.title,
        exec_status: t.exec_status || null,
        feedbacks: getFeedbacks(t.id)
      })),
      totalFeedbacks: yesterdayData.todos.reduce((s, t) => s + (getFeedbacks(t.id).length), 0)
    })
    // 最多保留 90 天
    storage.set('qingnang_archive', archive.slice(0, 90))
  } catch {}
}

function saveToday() {
  try {
    storage.set('qingnang_today', {
      date: getTodayKey(),
      todos: todos.value
    })
  } catch {}
}

// 反馈存储：{ [todoId]: [{status, note, date}] }
function loadFeedbacks() {
  return storage.get('qingnang_feedbacks', {}) || {}
}
function saveFeedbacks() {
  try { storage.set('qingnang_feedbacks', feedbacks.value) } catch {}
}

const feedbacks = ref(loadFeedbacks())
function getFeedbacks(todoId) { return feedbacks.value[todoId] || [] }

// ⭐ 预计算 feedbacksMap — LifeAdviceCard 组件需要 object 形式 (避免模板里函数调用)
const feedbacksMap = computed(() => {
  const map = {}
  for (const t of todos.value) map[t.id] = feedbacks.value[t.id] || []
  return map
})

const todos = ref(loadToday())
watch(todos, saveToday, { deep: true })

// ⚠️ 后端聚合返回的禁忌（不可执行，只做顶部提醒）
const avoidanceNotes = ref([])

function toggleTodo(id) {
  const t = todos.value.find(x => x.id === id)
  if (t) { t.done = !t.done }
}

function handleFeedback(fb) {
  if (!feedbacks.value[fb.todo_id]) feedbacks.value[fb.todo_id] = []
  feedbacks.value[fb.todo_id].push(fb)
  saveFeedbacks()
}

/* ──────────────────────────────────────
   打卡弹窗状态 & 方法
   ────────────────────────────────────── */
const punchModal = reactive({
  todo: null,           // 当前待打卡的 todo 对象
  feedbacks: [],        // 该 todo 的历史反馈
  isEdit: false,        // 是否是修改已完成的打卡
  execStatus: 'done',
  note: '',
  submitting: false,
})

function openPunchModal(todo) {
  punchModal.todo = todo
  punchModal.feedbacks = getFeedbacks(todo.id)
  punchModal.isEdit = !!todo.done
  // 默认选中：新打卡→已完成；修改→上次反馈的 status
  if (punchModal.isEdit && punchModal.feedbacks.length) {
    punchModal.execStatus = punchModal.feedbacks[punchModal.feedbacks.length - 1].status || 'done'
  } else {
    punchModal.execStatus = 'done'
  }
  punchModal.note = ''
  punchModal.submitting = false
  // 禁止 body 滚动
  document.body.style.overflow = 'hidden'
}

function closePunchModal() {
  punchModal.todo = null
  punchModal.note = ''
  punchModal.execStatus = 'done'
  document.body.style.overflow = ''
}

/* 由 PunchModal emit('submit', payload) 触发，payload = { execStatus, note } */
function handlePunchSubmit({ execStatus, note }) {
  punchModal.submitting = true
  const fb = {
    status: execStatus || 'done',
    note: note.trim(),
    date: new Date().toISOString().slice(0, 16).replace('T', ' '),
    todo_id: punchModal.todo.id
  }
  handleFeedback(fb)
  if (!punchModal.todo.done) {
    toggleTodo(punchModal.todo.id)
  }
  punchModal.submitting = false
  closePunchModal()
}

const filteredTodos = computed(() => {
  const t = todos.value
  if (activeFilter.value === 'pending') return t.filter(x => !x.done)
  return t
})

// 🎯 详情弹窗内容：去重 + 兜底推荐原因
const dmDetail = computed(() => {
  const t = detailModal.value
  if (!t?.detail) return ''
  return t.detail.trim() === (t.remind || '').trim() ? '' : t.detail
})
const dmReason = computed(() => {
  const t = detailModal.value
  if (!t) return ''
  if (t.reason) return t.reason
  const catMap = {
    diet: '饮食', exercise: '运动', sleep: '睡眠',
    cloth: '穿衣', home: '住家', avoid: '避忌',
    herb: '方药', lifestyle: '生活方式', ai: 'AI 建议',
  }
  const catName = catMap[t.source_type] || t.source_type || '生活方式'
  return `青囊根据你的当前体质和今日节律，在${catName}方面推荐你「${t.title}」。`
})

// 问问青囊管家
function askDetailQA() {
  const t = detailModal.value
  if (!t) return
  // 🎯 先关详情弹窗，再开管家（确保层级顺序正确）
  closeDetailModal()

  const parts = [`【${t.title}】`]
  if (t.remind) parts.push(`提醒：${t.remind}`)
  if (dmDetail.value) parts.push(`做法：${dmDetail.value}`)
  parts.push(`推荐原因：${dmReason.value}`)
  if (t.source_ref) parts.push(`出处：${t.source_ref}`)

  const assistant = window.__qingnangAssistant
  if (!assistant?.openWithContext) {
    alert('青囊管家还在初始化，请稍后再试')
    return
  }
  // 延迟一帧确保弹窗关闭动画完成后再开管家
  requestAnimationFrame(() => {
    assistant.openWithContext({
      anchor: { topic: '今日待办', title: t.title },
      explain: parts.join('\n\n'),
      followup: `关于「${t.title}」，我想深入聊聊 —— 比如这个建议适合我现在的体质吗？`,
    })
  })
}

// 分段器：待处理 / 全部 / 归档（设计稿三段式）
const segTabs = computed(() => [
  { key: 'pending', label: `待处理 ${pendingCount.value}` },
  { key: 'all', label: `全部 ${todos.value.length}` },
  { key: 'archived', label: `归档 ${archivedDays.value} 天` }
])

const pendingCount = computed(() => todos.value.filter(x => !x.done).length)

// ── 体质趋势卡：ΔV 摘要（图例旁一行小字）──
const deltaSummary = computed(() => {
  const rows = deltaTable.value.filter(r => r.delta != null)
  if (!rows.length) return '暂无漂移数据'
  const parts = rows
    .filter(r => Math.abs(r.delta) >= 0.5)
    .map(r => `${r.label} ${r.delta > 0 ? '▲' : '▼'} ${Math.abs(r.delta).toFixed(0)}`)
  return parts.length ? parts.join(' · ') + ' · 余稳定' : '五行 ΔV 均稳定'
})

// ── 时空锚点：今日避忌一行字（只保留一条）──
const avoidText = computed(() => {
  const chong = String(anchor.chong || '').replace(/（.*$/, '')
  if (!chong) return '待生成'
  return `冲${chong} · 忌远行`
})

// ── 时辰节律线：三段式（平稳 / 宜动 / 宜静）──
const rhythmSegments = computed(() => {
  const tl = todayTimeline.value || []
  const desc = (names) => tl
    .filter(t => names.some(n => String(t.range || '').includes(n)))
    .map(t => t.desc).filter(Boolean).slice(0, 2).join(' · ')
  return [
    { range: '05-11 卯·辰', label: '平稳', color: 'calm', desc: desc(['卯', '辰']) || '温盐水 · 小米粥' },
    { range: '17-21 酉·戌', label: '宜动', color: 'active', desc: desc(['酉', '戌']) || '减工作 · 泡脚' },
    { range: '21-01 亥·子', label: '宜静', color: 'rest', desc: desc(['亥', '子']) || '放下手机 · 必睡' }
  ]
})

function execLabel(s) {
  return ({ done: '已完成', partial: '部分执行', skipped: '跳过', failed: '未执行' })[s] || '待执行'
}

// 归档数据
const archives = computed(() => storage.get('qingnang_archive', []) || [])
const archivedDays = computed(() => archives.value.length)
const totalFeedbacks = computed(() => archives.value.reduce((s, a) => s + a.totalFeedbacks, 0))

// ── 统一清理：防止重新建档/切换账号后旧 ref 残留 ──
function _resetAllLocalState() {
  Object.assign(anchor, { ganzhi:'', dangling:'', dangling_elem:'', feixing:'', chong:'', jianchu:'', pengzu:'', shaxiang:'', richuxing:'', su:'', yi:'', ji:'', state:'', yuxiaji:'', weather: null })
  todayTimeline.value = []
  clothReminders.value = []
  foodGood.value = []
  foodBad.value = []
  homeReminders.value = []
  absoluteAvoid.value = []
  relativeAvoid.value = []
  stoneReminders.value = []
  lifestyleLoading.value = false
  lifestylePreview.value = ''
}

onMounted(async () => {
  _resetAllLocalState()   // 首次进 Dashboard，清旧状态
  await _onBoard()
})

// SPA keep-alive 时路由回来：内存数据完好，不重跑 LLM！
// 只有真正需要刷新（用户点了"刷新"按钮或 vBase 变了）才触发 _invalidateAndReload
onActivated(async () => {
  // 不调 _resetAllLocalState，不清缓存，不重跑 LLM
  // 只做最轻量的：确认 token 还在（登出后 SPA 路由回来需要重定向）
  if (!userStore.loggedIn) {
    router.replace('/login')
  }
})

// ── 主动失效 + 重新生成（给"刷新"按钮 / vBase 变化时调）──
function _invalidateAndReload() {
  storage.remove(_lifestyleCacheKey())
  _resetAllLocalState()
  return _onBoard()
}

// ═══════════════════════════════════════════════════════════
// 💡 轻量刷新（下拉刷新专用）：不清除已计算卡片
//  只重新拉可能变化的动态数据（新上传的观测、最新 SPUM 分析）
//  已按天缓存的卡片（干支/宜忌/穿衣/饮食）保持不变
// ═══════════════════════════════════════════════════════════
async function _lightRefresh() {
  // 1) 用户信息（可能刚更新了昵称）
  try { await userStore.fetchMe() } catch {}
  // 2) 健康快照（可能有新观测上传）
  try { health.value = await healthCheck() } catch {}
  // 3) SPUM 分析（vBase 可能因新观测而变 —— 必须重拉）
  try { await vectorStore.fetchCase() } catch {}
  // 4) 终身推演（八字大运 = 静态数据，只在首次无数据时拉）
  if (!vectorStore.lifetimeTrajectory) {
    vectorStore.fetchYearView().catch(() => {})
  }
  // 5) 今日待办（后端聚合）
  try {
    const r = await api.get('/api/v1/cases/today-todos')
    todos.value = (r.data?.todos || []).map(mapBackendTodo)
    avoidanceNotes.value = r.data?.avoidances || []
    saveToday()
  } catch {}
  // ⚠️ 注意：不清 anchor / food / cloth / lifestyle —— 这些是按天缓存的
  // 同一天干支不变，LLM 结果也不会变，无需重复计算
}

// ═══════════════════════════════════════════════════════════
// M1 下拉刷新 → modules/PullRefreshBar.vue（自管理手势，emit('refresh') 时调用 _lightRefresh）
// ═══════════════════════════════════════════════════════════

// ── 缓存键：按天（同一天干支一样，LLM 结果可复用）──
function _lifestyleCacheKey() {
  const d = new Date()
  const key = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
  return `lifestyle:v1:${key}`
}

async function _onBoard() {
  // 进主页先拉一遍最新用户信息（nickname 可能在 onboarding 刚更新）
  try { await userStore.fetchMe() } catch {}
  // 🎖️ 成熟度兜底拉取（页面刷新后 store 可能丢失）
  if (userStore.loggedIn && !userStore.maturity) {
    try { await userStore.fetchMaturity() } catch {}
  }
  // 注：问诊报告已迁移到「体质 → 报告时间线」
  health.value = await healthCheck()
  await vectorStore.fetchCase()
  // 后台预拉终身推演数据（八字大运+流年）——不阻塞主流程
  vectorStore.fetchYearView().then(() => {
    console.log('[Dashboard] ✅ 终身推演数据就绪')
  }).catch(e => console.warn('[Dashboard] 终身推演拉取失败（未建档或无八字数据）', e))

  // ── 从后端聚合今日待办（聊天 suggestions + 生活提醒）──
  try {
    const r = await api.get('/api/v1/cases/today-todos')
    const todosFromBackend = (r.data?.todos || []).map(mapBackendTodo)
    // ⚠️ 2026-10-05 修复：无条件覆盖 todos，不要用 length > 0 判断
    // 否则 reset 后后端返回空时，localStorage 残留的旧 todos 不会被清掉
    todos.value = todosFromBackend
    // 🎯 禁忌单独存（不进 todos，进顶部提醒栏）
    avoidanceNotes.value = r.data?.avoidances || []
    saveToday()
    console.log(`[Dashboard] ✅ 今日待办来自后端聚合：${todosFromBackend.length} 条，禁忌 ${avoidanceNotes.value.length} 条`)
    // 也存一下 chief_complaint 方便青囊聊天读
    if (r.data?.chief_complaint) {
      storage.set('qingnang_chief_complaint', r.data.chief_complaint)
    }
  } catch (e) {
    console.warn('[Dashboard] 今日待办后端不可达，使用本地缓存', e)
  }

  // Stage 1 跳过生活提醒（后端也会跳过，但前端也不调，省一次请求）
  if (maturity.value?.stage < 2) {
    console.log('[Dashboard] Stage 1 → 跳过生活提醒生成')
  } else {
  // ── 缓存优先：同一天干支一样，LLM 结果可复用 ──
  const _cacheKey = _lifestyleCacheKey()
  const _cached = storage.get(_cacheKey)
  if (_cached && _cached.anchor) {
    _applyLifestyleResult(_cached)
    console.log(`[Dashboard] ✅ 生活提醒命中缓存（key=${_cacheKey}）`)
  } else {
  // 缓存未命中 → 调 LLM
  const _settings = storage.get('qingnang_settings', {}) || {}
  const _lsPayload = {
    city: _settings.city || null,
  }
  lifestyleLoading.value = true
  lifestylePreview.value = ''
  lifestyleStream(_lsPayload, {
    onGenerating: (token) => {
      lifestylePreview.value += token
    },
    onComplete: (d) => {
      lifestyleLoading.value = false
      lifestylePreview.value = ''
      if (d?.anchor) {
        _applyLifestyleResult(d)
        storage.set(_cacheKey, d)  // ⭐ 写缓存
        console.log(`[Dashboard] ✅ 生活提醒来自青檬引擎（engine=${d.engine || 'unknown'}，已缓存）`)
      }
    },
    onNote: (text) => {
      console.log('[lifestyle note]', text)
    },
    onError: (err) => {
      lifestyleLoading.value = false
      lifestylePreview.value = ''
      console.warn('[Dashboard] ❌ 流式生活提醒失败，尝试非流式 fallback', err)
      assistantApi.lifestyle(_lsPayload).then((r) => {
        const d = r.data || {}
        if (d.anchor) {
          _applyLifestyleResult(d)
          storage.set(_cacheKey, d)
        }
      }).catch(() => {
        notifApi.today().then((r) => {
          if (r.data?.anchor) Object.assign(anchor, r.data.anchor)
        }).catch(() => { /* 页面里已有的常量会兜底 */ })
      })
    },
  })
  } // 缓存命中/未命中
  } // stage >= 2
}

// ── lifestyle 结果填充（缓存命中 / onComplete / fallback 共用）──
function _applyLifestyleResult(d) {
  if (d.anchor) Object.assign(anchor, d.anchor)
  if (d.timeline) todayTimeline.value = d.timeline
  if (d.cloth_reminders) clothReminders.value = d.cloth_reminders
  if (d.food_good) foodGood.value = d.food_good
  if (d.food_bad) foodBad.value = d.food_bad
  if (d.home_reminders) homeReminders.value = d.home_reminders
  if (d.absolute_avoid) absoluteAvoid.value = d.absolute_avoid
  if (d.relative_avoid) relativeAvoid.value = d.relative_avoid
}
</script>

<style scoped>
/* max-width 由全局 .page 统一管理（1200px） */

/* M1 下拉刷新 → modules/PullRefreshBar.vue scoped */

/* M2 问候头部 → modules/GreetingHeader.vue scoped */

/* ═══════════════════════════════════════════════════════════
   🎖️ 数字模型成熟度进度卡
   ═══════════════════════════════════════════════════════════ */
.maturity-card {
  background: var(--qn-surface);
  border: 1px solid rgba(var(--qn-emerald-rgb),0.12);
  border-radius: var(--radius-lg);
  padding: 18px 22px;
  margin-bottom: 16px;
  position: relative; overflow: hidden;
}
.maturity-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, var(--qn-emerald), var(--qn-emerald-accent));
  opacity: 0.6;
}
/* 不同阶段主题色 */
.maturity-card.stage-1::before { background: linear-gradient(90deg, #8B7355, #D4A574); }
.maturity-card.stage-2::before { background: linear-gradient(90deg, var(--qn-emerald), var(--qn-emerald-accent)); }
.maturity-card.stage-3::before { background: linear-gradient(90deg, var(--qn-emerald), var(--qn-emerald-accent), #6BE8C9); }
.maturity-card.stage-4::before { background: linear-gradient(90deg, var(--qn-emerald), var(--qn-emerald-accent), #6BE8C9, #FFD700); }

/* —— 4 阶段节点轨道 —— */
.mc-track { position: relative; padding: 12px 0 8px; margin-bottom: 14px; }
.mc-line {
  position: absolute; top: 28px; left: 24px; right: 24px;
  height: 3px; background: rgba(var(--qn-emerald-rgb),0.1); border-radius: 2px;
}
.mc-fill {
  height: 100%; border-radius: 2px;
  background: linear-gradient(90deg, var(--qn-emerald), var(--qn-emerald-accent));
  transition: width 0.6s ease;
}
.mc-node {
  position: relative; z-index: 2;
  display: inline-flex; flex-direction: column; align-items: center; gap: 4px;
  width: 25%;
}
.mc-node-ico {
  width: 42px; height: 42px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: calc(20px * var(--qn-fs-scale));
  background: #f5f7f6; border: 2px solid rgba(var(--qn-emerald-rgb),0.15);
  transition: all 0.3s;
}
.mc-node.done .mc-node-ico {
  background: var(--qn-emerald); border-color: var(--qn-emerald);
  box-shadow: 0 0 0 4px rgba(var(--qn-emerald-accent-rgb),0.2);
}
.mc-node.current .mc-node-ico {
  background: var(--qn-surface); border-color: var(--qn-emerald);
  box-shadow: 0 0 0 5px rgba(var(--qn-emerald-accent-rgb),0.3);
  animation: pulse-ring 2s infinite;
}
.mc-node.locked .mc-node-ico {
  background: #f0f0f0; border-color: #d0d0d0; opacity: 0.5;
}
@keyframes pulse-ring {
  0%, 100% { box-shadow: 0 0 0 4px rgba(var(--qn-emerald-accent-rgb),0.3); }
  50% { box-shadow: 0 0 0 8px rgba(var(--qn-emerald-accent-rgb),0.15); }
}
.mc-node-label { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); }
.mc-node.done .mc-node-label { color: var(--qn-emerald); font-weight: 600; }
.mc-node.current .mc-node-label { color: var(--qn-emerald-dark); font-weight: 700; }
.mc-node.locked .mc-node-label { color: #aaa; }
.mc-node-cur {
  position: absolute; top: -4px;
  font-size: calc(9px * var(--qn-fs-scale)); padding: 1px 6px; border-radius: 8px;
  background: var(--qn-emerald); color: #fff;
  letter-spacing: 0.5px;
}

/* —— 主体：分数 + 分项进度 —— */
.mc-body { display: flex; gap: 24px; align-items: flex-start; }
.mc-score {
  flex-shrink: 0; padding: 8px 16px;
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.08), rgba(var(--qn-emerald-accent-rgb),0.15));
  border-radius: var(--qn-r-lg); text-align: center;
  border: 1px solid rgba(var(--qn-emerald-rgb),0.12);
}
.mc-score-num { font-size: calc(28px * var(--qn-fs-scale)); font-weight: 700; color: var(--qn-emerald-dark); }
.mc-score-max { font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink-3); }
.mc-score-pct { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-left: 2px; }
.mc-items { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.mc-item {
  display: grid; grid-template-columns: 72px 1fr 48px; gap: 8px;
  align-items: center; font-size: calc(12px * var(--qn-fs-scale));
}
.mc-item-lbl { color: var(--qn-ink-2); }
.mc-item.done .mc-item-lbl { color: var(--qn-emerald); font-weight: 600; }
.mc-item-bar {
  height: 6px; background: #eef1f0; border-radius: 3px; overflow: hidden;
}
.mc-item-fill {
  height: 100%; border-radius: 3px;
  background: linear-gradient(90deg, var(--qn-emerald), var(--qingnang-spirit));
  transition: width 0.5s ease;
}
.mc-item.done .mc-item-fill { background: var(--qn-emerald); }
.mc-item-val { text-align: right; color: var(--qn-ink-3); font-variant-numeric: tabular-nums; }
.mc-item.done .mc-item-val { color: var(--qn-emerald); font-weight: 600; }

/* —— next_target / missing_signals —— */
.mc-next { margin: 12px 0 4px; font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-emerald-dark); font-weight: 500; }
.mc-missing { margin: 0; font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

/* ════ 注：问诊报告入口 CSS 已删除（迁移到体质页） ════ */

/* —— 移动端适配 —— 归并到 480px 档位（原 640px） */
@media (max-width: 480px) {
  .maturity-card { padding: 14px 14px; }
  .mc-node { width: 24%; }
  .mc-node-ico { width: 34px; height: 34px; font-size: calc(16px * var(--qn-fs-scale)); }
  .mc-line { left: 18px; right: 18px; top: 23px; }
  .mc-node-label { font-size: calc(10px * var(--qn-fs-scale)); }
  .mc-body { flex-direction: column; gap: 14px; }
  .mc-score { padding: 6px 12px; align-self: flex-start; }
  .mc-item { grid-template-columns: 60px 1fr 36px; font-size: calc(11px * var(--qn-fs-scale)); }
}

/* ── 英雄卡组容器（子卡样式已抽离 → HeroTodoCard.vue + HeroDailyTipsCard.vue） ── */
.hero-row { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; margin-bottom: 16px; }
@media (max-width: 720px) {
  .hero-row { grid-template-columns: 1fr; gap: 12px; }
}

/* M5 ConstitutionCurveCard → modules/ConstitutionCurveCard.vue scoped */
/* M5b AnchorTimelineCard → modules/AnchorTimelineCard.vue scoped */
/* M12 AiExplainModal → modules/AiExplainModal.vue scoped */

/* ── 顶部并列 ── */
.top-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; align-items: stretch; }
/* ⚠️ .card 基础样式已统一到 App.vue 全局（无 border、shadow-only、圆角 16）
   Dashboard 独有：只覆盖 h2 的 margin-bottom */
.card h2 { margin-bottom: 12px; }
/* M5 ConstitutionCurveCard → scoped 已有 */
/* .chart-card / .curve-chart / .chart-footer / .cfb-* 均已移至 ConstitutionCurveCard.vue scoped */

/* M10 体质趋势雷达 → modules/TrendRadarCard.vue scoped */

/* M7 今日生活建议 → modules/LifeAdviceCard.vue scoped */

/* M11 漂移矢量表格 → modules/DriftVectorCard.vue scoped */
.placeholder { color: var(--qn-ink-3); text-align: center; padding: 40px 16px; font-size: calc(13px * var(--qn-fs-scale)); }

/* ── 响应式：竖屏 / 窄窗修复 — 归并到 1024px 档位（原 960px） ── */
@media (max-width: 1024px) {
  .top-row { grid-template-columns: 1fr; }
  /* 所有模块响应式 → 各模块 scoped */
}
/* —— 小屏字体再压一下 — 归并到 480px 档位 —— */
@media (max-width: 480px) {
  /* 所有模块响应式 → 各模块 scoped */
}
/* M5b AnchorTimelineCard → modules/AnchorTimelineCard.vue scoped */
/* M6 生活提醒 → modules/LifestyleReminderCard.vue scoped */
/* M8 PunchModal → modules/PunchModal.vue scoped */
/* M9 DetailModal → modules/DetailModal.vue scoped */
</style>
