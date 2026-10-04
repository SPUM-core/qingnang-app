<template>
  <div class="assistant-root" :style="fabPosStyle">
    <!-- 悬浮触发按钮（可拖动） -->
    <button class="fab" :class="{ minimized: isOpen, dragging: isDragging }"
            @click="onFabClick"
            @mousedown="onDragStart"
            @touchstart.prevent="onTouchStart"
            :title="isOpen ? '收起青囊管家' : '青囊管家（可拖动）'">
      <svg v-if="!isOpen" viewBox="0 0 100 100" width="28" height="28" class="fab-logo">
        <polygon points="50,5 90,28 90,72 50,95 10,72 10,28" fill="none" stroke="#fff" stroke-width="4"/>
        <circle cx="50" cy="50" r="14" fill="none" stroke="#45C4A8" stroke-width="2" stroke-dasharray="3 2"/>
        <path d="M38 50 Q50 42 62 50 Q50 58 38 50" fill="none" stroke="#45C4A8" stroke-width="2.5" stroke-linecap="round"/>
      </svg>
      <span v-else class="fab-close">✕</span>
      <span class="fab-pulse" v-if="unread > 0"></span>
    </button>

    <!-- 对话抽屉 -->
    <transition name="drawer">
      <div v-if="isOpen" :class="['drawer', { fullscreen: isFullscreen }]">
        <!-- 📜 全屏模式专属：历史左栏 -->
        <aside v-if="isFullscreen" class="history-sidebar">
          <div class="hs-head">
            <span class="hs-title">📜 对话历史</span>
            <button class="hs-btn" @click="clearChat" title="新对话">＋</button>
          </div>
          <div class="hs-list">
            <!-- 今日 -->
            <div class="hs-group">
              <div class="hs-group-title">今日</div>
              <div v-for="(g, gi) in historyToday" :key="'t'+gi" class="hs-item"
                   @click="loadHistory(g.id)">
                <span class="hs-time">{{ g.time }}</span>
                <span class="hs-preview">{{ g.preview }}</span>
              </div>
            </div>
            <!-- 更早 -->
            <div v-if="historyEarlier.length" class="hs-group">
              <div class="hs-group-title">更早</div>
              <div v-for="(g, gi) in historyEarlier" :key="'e'+gi" class="hs-item"
                   @click="loadHistory(g.id)">
                <span class="hs-date">{{ g.date }}</span>
                <span class="hs-preview">{{ g.preview }}</span>
              </div>
            </div>
            <!-- 空态 -->
            <div v-if="historyToday.length === 0 && historyEarlier.length === 0" class="hs-empty">
              <p>暂无历史</p>
              <p class="hs-empty-hint">开始第一段对话吧～</p>
            </div>
          </div>
        </aside>

        <!-- 💬 对话主区 -->
        <div class="drawer-main">
        <!-- 头部 -->
        <div class="drawer-head">
          <div class="avatar">🌿</div>
          <div class="head-info">
            <h3>青囊管家</h3>
            <p class="head-sub">SPUM · 你的专属健康生活顾问</p>
          </div>
          <button class="head-btn" @click="toggleFullscreen" :title="isFullscreen ? '退出全屏' : '全屏模式'">
            <span v-if="isFullscreen" class="fs-icon">⤢</span>
            <span v-else class="fs-icon">⛶</span>
          </button>
          <button class="head-btn" @click="clearChat" title="新对话">🔄</button>
          <button class="head-btn close" @click="toggle" title="收起">—</button>
        </div>

        <!-- 状态条（从 userStore 动态取，不再硬编码胡运涛） -->
        <div v-if="ctxItems.length" class="ctx-bar">
          <template v-for="(it, i) in ctxItems" :key="i">
            <span :class="['ctx-item', it.cls]">{{ it.icon }} {{ it.text }}</span>
            <span class="ctx-sep" v-if="i < ctxItems.length - 1">·</span>
          </template>
        </div>

        <!-- 消息区 -->
        <div class="msg-area" ref="msgAreaRef" @scroll="onScroll">
          <!-- 欢迎态 -->
          <div v-if="messages.length === 0" class="welcome">
            <div class="welcome-avatar">🌿</div>
            <h2>{{ greetingTimeText }}，{{ userStore.displayName || '朋友' }}</h2>
            <p class="welcome-time">{{ todayStr }}</p>
            <!-- 🎖️ 数字模型成熟度徽章 -->
            <div v-if="stageBadge" class="stage-badge">
              <span class="sb-icon">{{ stageBadge.icon }}</span>
              <span class="sb-text">{{ stageBadge.text }}</span>
              <span class="sb-score">{{ stageBadge.score }}</span>
            </div>
            <p v-if="ctxSummary" class="welcome-status">你的数字模型：{{ ctxSummary }}</p>
            <p class="welcome-hint">我是你的青囊管家，随时聊聊——</p>
            <div class="quick-chips">
              <button v-for="(q, i) in quickQuestions" :key="i" class="chip-btn"
                      @click="send(q)">{{ q }}</button>
            </div>
          </div>

          <!-- 消息列表 -->
          <template v-else>
            <div v-for="m in messages" :key="m.id" class="msg-row" :class="m.role">
              <div class="msg-avatar">{{ m.role === 'ai' ? '🌿' : '🧑' }}</div>
              <div class="msg-bubble">
                <div v-if="m.role === 'ai' && m.typing" class="typing-dots">
                  <span></span><span></span><span></span>
                </div>
                <template v-else>
                  <!-- XSS 安全：不用 v-html，用文本节点 + 分段渲染 -->
                  <div class="msg-text">
                    <template v-for="(seg, si) in m.segments" :key="si">
                      <strong v-if="seg.bold">{{ seg.text }}</strong>
                      <template v-else>{{ seg.text }}</template>
                      <br v-if="si < m.segments.length - 1" />
                    </template>
                  </div>
                  <div v-if="m.suggestions?.length" class="suggest-row">
                    <button v-for="(s, i) in m.suggestions" :key="i" class="sugg-btn" @click="send(s)">{{ s }}</button>
                  </div>
                  <!-- 🎯 AI 调用应用功能（青囊管家的"四肢"） -->
                  <div v-if="m.actions?.length" class="action-row">
                    <button v-for="(a, i) in m.actions" :key="i"
                            :class="['action-btn', a.priority]"
                            @click="doAction(a)">
                      <span class="action-icon">{{ a.icon }}</span>
                      <span>{{ a.label }}</span>
                      <span class="action-arrow">→</span>
                    </button>
                  </div>
                  <!-- 📊 AI 深度解析摘要（病理 + 建议） -->
                  <div v-if="m.analysis?.pathologies?.length || m.analysis?.suggestions?.length" class="analysis-card">
                    <div v-if="m.analysis.pathologies?.length" class="ana-section">
                      <span class="ana-tag">📌 状态梳理</span>
                      <span v-for="(p, pi) in m.analysis.pathologies" :key="pi" class="ana-path">
                        {{ p.label }}<span v-if="p.base" class="ana-base">（{{ p.base }}）</span>
                      </span>
                    </div>
                    <div v-if="m.analysis.suggestions?.length" class="ana-section">
                      <span class="ana-tag">💡 调理建议</span>
                      <span v-for="(s, si) in m.analysis.suggestions.slice(0,3)" :key="si"
                            :class="['ana-sugg', s.priority]">
                        {{ s.title }}
                      </span>
                    </div>
                  </div>
                  <div v-if="m.footnote" class="msg-footnote">{{ m.footnote }}</div>
                </template>
                <div class="msg-time">{{ m.time }}</div>
              </div>
            </div>
          </template>
        </div>

        <!-- 输入区 -->
        <div class="input-area">
          <textarea
            v-model="input"
            rows="1"
            :placeholder="placeholder"
            @keydown="onKeydown"
            @input="autoResize"
            ref="taRef"
          ></textarea>
          <button class="send-btn" :disabled="!input.trim() || thinking" @click="send(input.trim())">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
        <p class="disclaimer">* 青囊管家基于你的数字模型给出生活参考，不构成医疗建议</p>
        </div><!-- /drawer-main -->
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, nextTick, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { api } from '../api/client'

const userStore = useUserStore()
const router = useRouter()

// ═══ 状态 ═══
const isOpen = ref(false)
const messages = ref([])
const input = ref('')
const thinking = ref(false)
const unread = ref(0)
const msgAreaRef = ref(null)
const taRef = ref(null)
const isFullscreen = ref(false)

// ═══ 历史消息侧栏 ═══
const chatHistory = ref([])  // 从后端 /chat/messages 拉
const historyLoaded = ref(false)

async function loadHistoryList() {
  try {
    const r = await api.get('/api/v1/assistant/chat/messages?limit=50')
    // 后端返回 [{role, content, created_at, signals?}]
    // 转成 history 条目：按时间戳分今天/更早
    chatHistory.value = (r.data || []).map((m, i) => ({
      id: m.id || i,
      role: m.role,
      content: m.content,
      signals: m.signals || null,
      ts: new Date(m.created_at).getTime(),
      dateStr: new Date(m.created_at).toISOString().slice(0, 10),
      timeStr: new Date(m.created_at).toLocaleTimeString('zh-CN', {
        hour: '2-digit', minute: '2-digit'
      }),
    })).reverse()  // 最新在前
    historyLoaded.value = true
  } catch (e) {
    console.warn('[history] 拉历史失败', e)
  }
}

// 按日期分组的历史（给左栏渲染）
const historyToday = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  const todayItems = chatHistory.value
    .filter(m => m.role === 'user' && m.dateStr === today)
    .map(m => ({
      id: m.id,
      time: m.timeStr,
      preview: (m.content || '').slice(0, 30),
      ts: m.ts,
    }))
    .sort((a, b) => b.ts - a.ts)
  // 每个 user 消息 + 下一个 ai 消息拼成一组（用 ai 的 preview 如果有）
  return todayItems
})

const historyEarlier = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  const earlierItems = chatHistory.value
    .filter(m => m.role === 'user' && m.dateStr !== today)
    .map(m => ({
      id: m.id,
      date: m.dateStr,
      preview: (m.content || '').slice(0, 30),
      ts: m.ts,
    }))
    .sort((a, b) => b.ts - a.ts)
  return earlierItems.slice(0, 20)  // 最多显示 20 条更早
})

function loadHistory(msgId) {
  // 点击历史条目 → 找到这条消息及其后的所有消息，重建 messages
  const idx = chatHistory.value.findIndex(m => m.id === msgId)
  if (idx === -1) return
  // 从这条消息开始，取后面的（包括这条）
  const sub = chatHistory.value.slice(idx)
  messages.value = sub.map(m => ({
    id: m.id,
    role: m.role,
    content: m.content,
    suggestions: [],
    footnote: '',
    actions: m.signals ? [] : [],
    analysis: m.signals,
    time: m.timeStr,
    typing: false,
  }))
  scrollBottom()
}

// ═══ FAB 拖动相关 ═══
const FAB_STORAGE_KEY = 'qingnang-fab-pos'
const fabX = ref(null)   // px from left
const fabY = ref(null)   // px from top
const isDragging = ref(false)
let dragStartX = 0, dragStartY = 0, fabStartX = 0, fabStartY = 0
let dragMoved = false   // 区分「点击」和「拖动」

/** 计算 fab 的 style —— 有记忆位置用绝对定位，否则用默认 fixed */
const fabPosStyle = computed(() => {
  if (fabX.value !== null && fabY.value !== null) {
    return {
      position: 'fixed',
      left: fabX.value + 'px',
      top: fabY.value + 'px',
      right: 'auto',
      bottom: 'auto',
      transform: 'none',
    }
  }
  return {}  // 默认 CSS 的 right:24px; bottom:24px
})

/** 从 localStorage 加载记忆位置 */
function loadFabPos() {
  try {
    const raw = localStorage.getItem(FAB_STORAGE_KEY)
    if (raw) {
      const { x, y } = JSON.parse(raw)
      if (typeof x === 'number' && typeof y === 'number') {
        fabX.value = x
        fabY.value = y
      }
    }
  } catch {}
}

/** 保存位置到 localStorage（边界对齐窗口） */
function saveFabPos(x, y) {
  try {
    const FAB_SIZE = 56
    const TAB_BAR_H = window.innerWidth <= 720 ? 72 : 0  // 移动端 Tab Bar 占位
    const maxX = window.innerWidth - FAB_SIZE - 8
    const maxY = window.innerHeight - FAB_SIZE - TAB_BAR_H - 8
    const safeX = Math.max(8, Math.min(x, maxX))
    const safeY = Math.max(8, Math.min(y, maxY))
    localStorage.setItem(FAB_STORAGE_KEY, JSON.stringify({ x: safeX, y: safeY }))
    fabX.value = safeX
    fabY.value = safeY
  } catch {}
}

// ── 桌面端鼠标拖动 ──
function onDragStart(e) {
  if (e.button !== 0) return   // 只响应左键
  isDragging.value = true
  dragMoved = false
  dragStartX = e.clientX
  dragStartY = e.clientY
  fabStartX = fabX.value !== null ? fabX.value : window.innerWidth - 80
  fabStartY = fabY.value !== null ? fabY.value : window.innerHeight - 100
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
  e.preventDefault()
}
function onDragMove(e) {
  const dx = e.clientX - dragStartX
  const dy = e.clientY - dragStartY
  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) dragMoved = true
  if (dragMoved) {
    fabX.value = fabStartX + dx
    fabY.value = fabStartY + dy
  }
}
function onDragEnd() {
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  if (dragMoved) {
    saveFabPos(fabX.value, fabY.value)
  }
  isDragging.value = false
}

// ── 移动端触摸拖动 ──
let touchIdentifier = null
function onTouchStart(e) {
  const t = e.changedTouches[0]
  touchIdentifier = t.identifier
  isDragging.value = true
  dragMoved = false
  dragStartX = t.clientX
  dragStartY = t.clientY
  fabStartX = fabX.value !== null ? fabX.value : window.innerWidth - 80
  fabStartY = fabY.value !== null ? fabY.value : window.innerHeight - 100
  document.addEventListener('touchmove', onTouchMove, { passive: false })
  document.addEventListener('touchend', onTouchEnd)
}
function onTouchMove(e) {
  const t = Array.from(e.changedTouches).find(tt => tt.identifier === touchIdentifier)
  if (!t) return
  e.preventDefault()   // 防止页面滚动
  const dx = t.clientX - dragStartX
  const dy = t.clientY - dragStartY
  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) dragMoved = true
  if (dragMoved) {
    fabX.value = fabStartX + dx
    fabY.value = fabStartY + dy
  }
}
function onTouchEnd(e) {
  const t = Array.from(e.changedTouches).find(tt => tt.identifier === touchIdentifier)
  if (t && dragMoved) {
    saveFabPos(fabX.value, fabY.value)
  }
  touchIdentifier = null
  document.removeEventListener('touchmove', onTouchMove)
  document.removeEventListener('touchend', onTouchEnd)
  isDragging.value = false
}

/** 点击 vs 拖动：拖动了就不 toggle */
function onFabClick() {
  if (dragMoved) {
    dragMoved = false
    return
  }
  toggle()
}

// ── 窗口 resize 时重新对齐（避免拖出屏幕） ──
function onResize() {
  if (fabX.value !== null && fabY.value !== null) {
    saveFabPos(fabX.value, fabY.value)
  }
}

onMounted(() => {
  loadFabPos()
  window.addEventListener('resize', onResize)
  // 🎖️ 登录后拉一次成熟度（欢迎态徽章立即显示）
  if (userStore.loggedIn && !userStore.maturity) {
    userStore.fetchMaturity().catch(() => {})
  }
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
})

// ═══ 成熟度徽章（从 userStore.maturity 取，chat 响应也会更新）═══
const stageBadge = computed(() => {
  const m = userStore.maturity
  if (!m?.stage) return null
  return {
    icon: m.icon || '🌱',
    text: `Stage ${m.stage} · ${m.name}`,
    score: `${m.score}/${m.max_score || 11}`,
    next: m.next_target || '',
  }
})

// ═══ 快捷问题（按成熟度阶段动态生成）═══
const STAGE_QUICK_QUESTIONS = {
  1: ['今天天气怎么样？', '最近有什么节日？', '推荐一首放松的音乐', '讲讲四季养生常识'],
  2: ['我今天该吃什么？', '推荐什么颜色适合我？', '简单的食疗建议', '这个季节该注意什么？'],
  3: ['我的体质适合几点睡？', '适合我的穿衣颜色', '今天饮食宜忌', '家居方位有什么建议？', '做什么运动合适？'],
  4: ['我的深层调理方案', '方剂方案调整建议', '长期体质调平计划'],
}
const quickQuestions = computed(() => {
  const stage = userStore.maturity?.stage || 1
  return STAGE_QUICK_QUESTIONS[stage] || STAGE_QUICK_QUESTIONS[1]
})

const placeholder = computed(() =>
  thinking.value ? '青囊管家正在思考…' : '问问青囊管家…（Enter 发送）'
)

// ═══ 从 userStore + case 派生的上下文展示（动态，不再硬编码） ═══
const ctxItems = computed(() => {
  const items = []
  if (userStore.displayName) {
    items.push({ icon: '🆔', text: userStore.displayName.substring(0, 10), cls: '' })
  }
  const v = userStore.caseData?.v_current || userStore.caseData?.v_baseline || {}
  const labels = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
  const weak = []
  for (const [k, val] of Object.entries(v)) {
    if (typeof val === 'number' && val < 45) weak.push(labels[k] + '弱')
  }
  if (weak.length) {
    items.push({ icon: '⚠️', text: weak.slice(0, 2).join('·'), cls: 'ctx-warn' })
  }
  return items
})

const ctxSummary = computed(() => {
  const v = userStore.caseData?.v_current || userStore.caseData?.v_baseline
  if (!v) return ''
  const labels = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
  const parts = []
  for (const [k, val] of Object.entries(v)) {
    if (typeof val === 'number' && val < 45) parts.push(labels[k] + '形偏弱')
  }
  if (!parts.length) parts.push('五形基本调和')
  return parts.slice(0, 2).join(' · ')
})

// ═══ 时间工具 ═══
const greetingTimeText = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '深夜'
  if (h < 9) return '早上'
  if (h < 12) return '上午'
  if (h < 14) return '中午'
  if (h < 18) return '下午'
  if (h < 22) return '晚上'
  return '深夜'
})
const todayStr = computed(() => {
  const d = new Date()
  const names = ['周日','周一','周二','周三','周四','周五','周六']
  return `${d.getMonth()+1}月${d.getDate()}日 ${names[d.getDay()]}`
})

// ═══ 开关抽屉 ═══
const toggle = () => {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    unread.value = 0
    nextTick(() => taRef.value?.focus())
  }
}
const clearChat = () => {
  if (messages.value.length === 0) return
  if (confirm('开始新的对话？')) messages.value = []
}
const toggleFullscreen = async () => {
  isFullscreen.value = !isFullscreen.value
  // 进入全屏时拉一次历史（如果还没拉过）
  if (isFullscreen.value && !historyLoaded.value) {
    await loadHistoryList()
  }
}

// ═══ 发送消息（通过青囊后端代理，不再直连 8000） ═══
const onKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send(input.value.trim())
  }
}
const autoResize = () => {
  const ta = taRef.value
  if (!ta) return
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
}

let msgId = 1
const nowTime = () => {
  const d = new Date()
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

/**
 * 将 AI 回复文本解析为 segments 数组，安全渲染（替代 v-html）
 * - 先用 DOM API 对原始文本做 HTML escape（防 XSS）
 * - 再按 **bold** 和换行拆分，标记 bold 段
 */
function safeParseSegments(raw) {
  if (!raw) return [{ text: '', bold: false }]
  // HTML escape — 防 XSS 的核心步骤
  const div = document.createElement('div')
  div.textContent = raw
  const escaped = div.innerHTML  // 纯文本已被 escape
  // 但我们直接用原始文本（Vue template 会 escape 文本插值），
  // 所以只做语义分段，交给 Vue 的 {{ }} 自动 escape
  const lines = raw.split('\n')
  const segs = []
  for (const line of lines) {
    // **bold** → 分割为 bold/普通段
    const parts = line.split(/(\*\*[^*]+\*\*)/)
    for (const part of parts) {
      if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
        segs.push({ text: part.slice(2, -2), bold: true })
      } else if (part) {
        segs.push({ text: part, bold: false })
      }
    }
    segs.push({ text: '\n', bold: false, _newline: true })
  }
  // 去掉末尾多余换行
  while (segs.length && segs[segs.length - 1]._newline) segs.pop()
  if (!segs.length) segs.push({ text: '', bold: false })
  return segs
}

const send = async (text) => {
  if (!text || thinking.value) return

  // 用户消息（用户输入已经是安全文本，无 bold 处理）
  const uMsg = { id: msgId++, role: 'user', content: text, time: nowTime(), segments: [{ text, bold: false }] }
  messages.value = [...messages.value, uMsg]
  input.value = ''
  autoResize()
  scrollBottom()

  // AI 打字占位
  const typingMsg = { id: msgId++, role: 'ai', content: '', time: nowTime(), typing: true, segments: [{ text: '', bold: false }] }
  messages.value = [...messages.value, typingMsg]
  thinking.value = true
  scrollBottom()

  // 后端代理调用（不再直连 8000）
  let replyText = ''
  let footnote = ''
  let engineLabel = ''
  let r = null  // ⚠️ 先声明，catch 后也能访问
  try {
    const history = messages.value
      .filter(m => m.id !== typingMsg.id && !m.typing)
      .slice(-10)
      .map(m => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.content }))

    // 从设置读取用户选择的 provider
    let provider = 'spum'
    try { provider = JSON.parse(localStorage.getItem('qingnang_settings') || '{}').llm_provider || 'spum' } catch {}

    r = await api.post('/api/v1/assistant/chat', { message: text, history, provider })
    replyText = r.data?.reply || ''
    // 🎖️ 后端返回的成熟度阶段 → 更新 store（下次欢迎态立刻显示）
    if (r.data?.maturity) {
      userStore.updateMaturityFromChat(r.data.maturity)
    }
    // engine 标签：反映实际 provider + 是否在线
    const eng = r.data?.engine
    const prov = r.data?.provider || provider
    const ms = r.data?.latency_ms || 0
    if (eng === 'local_fallback') {
      footnote = '本地规则回复（模型不可达）'
    } else if (prov === 'deepseek') {
      footnote = `DeepSeek · ${ms}ms`
    } else {
      footnote = `SPUM 本地模型 · ${ms}ms`
    }
  } catch (e) {
    const code = e.response?.status
    if (code === 401 || code === 403) {
      replyText = '需要先登录才能使用青囊管家。'
    } else {
      replyText = '青囊管家暂时无法连接，请稍后再试。'
    }
    footnote = '· 连接失败'
  }

  // 提取建议（从回复的短行里猜）
  const suggestions = replyText
    .split('\n')
    .filter(l => l.trim().length >= 4 && l.trim().length <= 20 && !l.includes('**'))
    .slice(0, 3)

  // 从后端响应读 actions + analysis（AI Tool Calling 结果）
  const actions = r.data?.actions || []
  const analysis = r.data?.analysis || null
  // extracted_signals 也存到全局 window 方便 Dashboard 后续消费
  if (r.data?.extracted_signals?.length) {
    try {
      const key = 'qingnang-latest-signals'
      localStorage.setItem(key, JSON.stringify({
        signals: r.data.extracted_signals,
        at: Date.now(),
      }))
    } catch {}
  }

  // 替换 typingMsg
  const finalMsg = {
    id: typingMsg.id, role: 'ai',
    content: replyText, suggestions, footnote,
    actions, analysis,
    time: nowTime(), typing: false,
    segments: safeParseSegments(replyText),
  }
  const idx = messages.value.findIndex(m => m.id === typingMsg.id)
  if (idx >= 0) {
    const copy = [...messages.value]
    copy[idx] = finalMsg
    messages.value = copy
  }
  thinking.value = false
  scrollBottom()
}

const scrollBottom = () => {
  nextTick(() => {
    const el = msgAreaRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}
const onScroll = () => {}

// 🎯 AI Tool Calling：点击青囊建议的动作按钮 → 跳转对应页面
function doAction(a) {
  // 先关闭抽屉，避免路由跳转时视觉混乱
  isOpen.value = false
  // 小延迟让关闭动画完成
  setTimeout(() => {
    if (a?.route) {
      router.push(a.route)
    }
  }, 200)
}
</script>

<style scoped>
.assistant-root { position: fixed; right: 24px; bottom: 24px; z-index: 1000; }

/* 悬浮按钮 */
.fab {
  width: 56px; height: 56px; border-radius: 50%;
  background: linear-gradient(135deg, var(--qingnang-emerald) 0%, var(--qingnang-emerald-dark) 100%);
  border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 20px rgba(26,77,69,0.35);
  transition: all 0.2s; position: relative;
}
.fab:hover { transform: scale(1.08); box-shadow: 0 6px 28px rgba(26,77,69,0.45); }
.fab:active { transform: scale(0.95); }
.fab.minimized { width: 40px; height: 40px; box-shadow: 0 2px 10px rgba(0,0,0,0.15); }
.fab-logo { filter: drop-shadow(0 1px 2px rgba(0,0,0,0.2)); }
.fab-close { color: #fff; font-size: 18px; font-weight: 300; }
.fab-pulse {
  position: absolute; top: -2px; right: -2px; width: 14px; height: 14px;
  background: var(--wuxing-fire); border-radius: 50%;
  border: 2px solid #fff; animation: pulse-ring 1.5s infinite;
}
@keyframes pulse-ring {
  0% { transform: scale(1); opacity: 1; }
  100% { transform: scale(1.5); opacity: 0; }
}

/* 抽屉 */
.drawer {
  position: fixed; right: 24px; bottom: 24px;
  width: 420px; height: 620px;
  background: #fff; border-radius: 16px;
  box-shadow: 0 12px 48px rgba(26,77,69,0.18), 0 2px 8px rgba(0,0,0,0.06);
  display: flex; flex-direction: column; overflow: hidden;
  border: 1px solid var(--ink-line);
  z-index: 1001;
  transition: width .25s ease, height .25s ease, right .25s ease, bottom .25s ease, border-radius .25s ease;
}
.drawer.fullscreen {
  right: 0; bottom: 0; left: 0; top: 0;
  width: 100vw; height: 100vh;
  border-radius: 0;
  z-index: 2000;
  flex-direction: row;
}

/* 📜 历史侧栏（全屏专属） */
.history-sidebar {
  width: 260px; flex-shrink: 0;
  background: linear-gradient(180deg, #faf9f5, #f3f1ea);
  border-right: 1px solid var(--ink-line);
  display: flex; flex-direction: column;
  overflow: hidden;
}
.hs-head {
  padding: 14px 16px;
  display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid var(--ink-line);
  background: rgba(26,77,69,0.04);
}
.hs-title { font-size: 13px; font-weight: 600; color: #1A4D45; }
.hs-btn {
  width: 26px; height: 26px; border-radius: 6px;
  border: 1px solid rgba(26,77,69,0.3); background: #fff;
  color: #1A4D45; font-size: 14px; line-height: 1;
  cursor: pointer; transition: all 0.15s;
}
.hs-btn:hover { background: #1A4D45; color: #fff; }
.hs-list { flex: 1; overflow-y: auto; padding: 8px; }
.hs-group { margin-bottom: 12px; }
.hs-group-title {
  font-size: 10px; color: var(--ink-tertiary);
  padding: 6px 10px; text-transform: uppercase; letter-spacing: 0.5px;
}
.hs-item {
  padding: 8px 10px; border-radius: 6px; cursor: pointer;
  display: flex; flex-direction: column; gap: 2px;
  transition: background 0.12s;
}
.hs-item:hover { background: rgba(26,77,69,0.06); }
.hs-time, .hs-date {
  font-size: 10px; color: var(--ink-tertiary);
}
.hs-preview {
  font-size: 12px; color: var(--ink-primary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.hs-empty {
  padding: 40px 20px; text-align: center; color: var(--ink-tertiary);
}
.hs-empty p { margin: 4px 0; }
.hs-empty-hint { font-size: 11px; opacity: 0.6; }

/* 💬 全屏下的对话主区 */
.drawer.fullscreen .drawer-main {
  flex: 1; display: flex; flex-direction: column;
  min-width: 0; /* flex 子元素防溢出 */
}
/* 非全屏时 drawer-main 就是 drawer 本身 */
.drawer:not(.fullscreen) .drawer-main {
  flex: 1; display: flex; flex-direction: column; min-width: 0;
}
.drawer-enter-active, .drawer-leave-active { transition: all 0.25s cubic-bezier(0.2, 0.8, 0.2, 1); }
.drawer-enter-from, .drawer-leave-to { opacity: 0; transform: translateY(20px) scale(0.95); }

/* 头部 */
.drawer-head {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 16px;
  background: linear-gradient(135deg, var(--qingnang-emerald) 0%, var(--qingnang-emerald-dark) 100%);
  color: #fff; flex-shrink: 0;
}
.avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: rgba(255,255,255,0.15);
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; flex-shrink: 0;
}
.welcome-avatar {
  width: 64px; height: 64px; border-radius: 50%;
  background: linear-gradient(135deg, rgba(26,77,69,0.1), rgba(46,125,106,0.2));
  display: flex; align-items: center; justify-content: center;
  font-size: 32px; margin: 0 auto 14px;
  box-shadow: 0 4px 20px rgba(26,77,69,0.15);
}
.head-info { flex: 1; }
.head-info h3 { margin: 0; font-size: 15px; font-weight: 600; }
.head-sub { margin: 2px 0 0; font-size: 11px; color: rgba(255,255,255,0.65); }
.head-btn {
  width: 30px; height: 30px; border-radius: 50%;
  border: none; background: rgba(255,255,255,0.15);
  color: #fff; cursor: pointer; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.15s;
}
.head-btn:hover { background: rgba(255,255,255,0.25); }

/* 状态条 */
.ctx-bar {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  padding: 8px 16px;
  background: var(--qingnang-paper); border-bottom: 1px solid var(--ink-line);
  font-size: 11px; flex-shrink: 0;
}
.ctx-item { color: var(--ink-secondary); font-weight: 500; }
.ctx-sep { color: var(--ink-tertiary); opacity: 0.4; }
.ctx-warn { color: var(--qingnang-emerald); font-weight: 600; }

/* 消息区 */
.msg-area {
  flex: 1; overflow-y: auto; padding: 16px;
  background: var(--qingnang-paper);
  scroll-behavior: smooth;
}
.msg-area::-webkit-scrollbar { width: 4px; }
.msg-area::-webkit-scrollbar-thumb { background: var(--ink-line); border-radius: 2px; }

/* 欢迎态 */
.welcome { text-align: center; padding: 20px 10px; }
.welcome h2 { margin: 0 0 4px; font-size: 18px; color: var(--ink-primary); }
.welcome-time { margin: 0 0 12px; font-size: 12px; color: var(--ink-tertiary); }
.welcome-status { margin: 0 0 6px; font-size: 12px; color: var(--ink-secondary); line-height: 1.6; }

/* 🎖️ 数字模型成熟度徽章 */
.stage-badge {
  display: inline-flex; align-items: center; gap: 6px;
  margin: 4px 0 8px; padding: 5px 12px;
  background: linear-gradient(135deg, rgba(26,77,69,0.08), rgba(69,196,168,0.12));
  border: 1px solid rgba(26,77,69,0.2);
  border-radius: 16px;
  font-size: 11px; color: #1A4D45;
}
.sb-icon { font-size: 14px; }
.sb-text { font-weight: 600; }
.sb-score {
  margin-left: 2px; padding: 1px 6px;
  background: rgba(26,77,69,0.12); border-radius: 10px;
  font-weight: 500; color: var(--qingnang-emerald);
}

.welcome-hint { margin: 16px 0 10px; font-size: 11px; color: var(--ink-tertiary); letter-spacing: 0.5px; }
.quick-chips { display: flex; flex-direction: column; gap: 8px; max-width: 320px; margin: 0 auto; }
.chip-btn {
  font-size: 13px; padding: 10px 16px;
  border: 1px solid rgba(26,77,69,0.2); background: #fff;
  color: var(--qingnang-emerald); border-radius: 20px;
  cursor: pointer; text-align: center; transition: all 0.15s;
}
.chip-btn:hover {
  background: var(--qingnang-emerald); color: #fff;
  border-color: var(--qingnang-emerald);
  transform: translateY(-1px);
}

/* 消息行 */
.msg-row { display: flex; gap: 8px; margin-bottom: 12px; }
.msg-row.ai { flex-direction: row; }
.msg-row.user { flex-direction: row-reverse; }
.msg-row .msg-avatar {
  width: 30px; height: 30px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; flex-shrink: 0;
  background: rgba(26,77,69,0.08);
}
.msg-row.ai .msg-avatar { background: rgba(26,77,69,0.1); }
.msg-row.user .msg-avatar { background: rgba(46,125,106,0.2); }

.msg-bubble {
  max-width: 82%; padding: 10px 14px; border-radius: 12px;
  font-size: 13px; line-height: 1.6; position: relative;
}
.msg-row.ai .msg-bubble {
  background: #fff; color: var(--ink-primary);
  border: 1px solid var(--ink-line); border-top-left-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}
.msg-row.user .msg-bubble {
  background: linear-gradient(135deg, var(--qingnang-emerald) 0%, var(--qingnang-emerald-light) 100%);
  color: #fff; border-top-right-radius: 4px;
}
.msg-text strong { color: var(--qingnang-emerald); }
.msg-row.user .msg-text strong { color: #fff; }

.typing-dots { display: flex; gap: 4px; padding: 4px 0; }
.typing-dots span {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--qingnang-emerald); opacity: 0.4;
  animation: bounce 1.4s infinite ease-in-out both;
}
.typing-dots span:nth-child(1) { animation-delay: -0.32s; }
.typing-dots span:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.suggest-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.sugg-btn {
  font-size: 11px; padding: 4px 10px;
  border: 1px solid rgba(26,77,69,0.2); background: #fff;
  color: var(--qingnang-emerald); border-radius: 12px;
  cursor: pointer; transition: all 0.15s;
}
.sugg-btn:hover { background: rgba(26,77,69,0.06); border-color: var(--qingnang-emerald); }

/* 🎯 AI Tool Calling 动作按钮 */
.action-row {
  display: flex; flex-direction: column; gap: 6px; margin-top: 10px;
}
.action-btn {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; padding: 8px 12px;
  border: 1px solid rgba(26,77,69,0.25); background: linear-gradient(135deg, #f0faf7, #fff);
  color: #1A4D45; border-radius: 8px;
  cursor: pointer; transition: all 0.15s;
  text-align: left; font-weight: 500;
}
.action-btn:hover {
  background: linear-gradient(135deg, #e0f5ee, #f5fff9);
  border-color: var(--qingnang-emerald);
  transform: translateX(2px);
}
.action-btn.high { border-color: #D84315; color: #D84315; background: linear-gradient(135deg, #fff5f2, #fff); }
.action-btn.high:hover { background: linear-gradient(135deg, #ffeae2, #fff); }
.action-icon { font-size: 14px; }
.action-arrow { margin-left: auto; opacity: 0.5; font-size: 11px; }

/* 📊 AI 深度解析摘要卡 */
.analysis-card {
  margin-top: 10px; padding: 10px 12px;
  background: linear-gradient(135deg, rgba(26,77,69,0.05), rgba(212,160,23,0.04));
  border: 1px solid rgba(26,77,69,0.12);
  border-radius: 10px; font-size: 11px; line-height: 1.6;
}
.ana-section { margin-bottom: 6px; }
.ana-section:last-child { margin-bottom: 0; }
.ana-tag {
  display: inline-block; margin-right: 6px;
  color: var(--ink-tertiary); font-weight: 500;
}
.ana-path {
  display: inline-block; margin: 0 3px;
  background: rgba(216,67,21,0.08); color: #D84315;
  padding: 1px 7px; border-radius: 4px; font-weight: 500;
}
.ana-base { color: var(--ink-tertiary); font-size: 10px; font-weight: 400; }
.ana-sugg {
  display: inline-block; margin: 0 3px;
  background: rgba(26,77,69,0.08); color: #1A4D45;
  padding: 1px 7px; border-radius: 4px;
}
.ana-sugg.high { background: rgba(216,67,21,0.1); color: #D84315; font-weight: 500; }
.ana-sugg.low { opacity: 0.7; }

.msg-footnote {
  margin-top: 8px; padding-top: 6px;
  border-top: 1px dashed var(--ink-line);
  font-size: 10px; color: var(--ink-tertiary); font-style: italic;
}
.msg-row.user .msg-footnote { display: none; }

.msg-time {
  font-size: 10px; color: var(--ink-tertiary); margin-top: 4px; opacity: 0.6;
}
.msg-row.user .msg-time { text-align: right; }

/* 输入区 */
.input-area {
  display: flex; align-items: flex-end; gap: 8px;
  padding: 12px 14px; background: #fff; border-top: 1px solid var(--ink-line);
  flex-shrink: 0;
}
.input-area textarea {
  flex: 1; resize: none; border: 1px solid var(--ink-line); border-radius: 20px;
  padding: 9px 16px; font-size: 13px; font-family: inherit;
  background: var(--qingnang-paper); color: var(--ink-primary);
  max-height: 120px; line-height: 1.5; outline: none;
  transition: border-color 0.15s;
}
.input-area textarea:focus { border-color: var(--qingnang-emerald); background: #fff; }
.send-btn {
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--qingnang-emerald); border: none; color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0; transition: all 0.15s;
}
.send-btn:hover:not(:disabled) { background: var(--qingnang-emerald-light); transform: scale(1.05); }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.disclaimer {
  margin: 0; padding: 6px 16px;
  background: var(--qingnang-paper); border-top: 1px solid var(--ink-line);
  font-size: 10px; color: var(--ink-tertiary); text-align: center; flex-shrink: 0;
  line-height: 1.4;
}

@media (max-width: 520px) {
  .drawer {
    right: 12px; left: 12px; width: auto;
    bottom: calc(72px + env(safe-area-inset-bottom));
    height: calc(100vh - 140px);
    max-height: calc(100vh - 140px);
  }
}
</style>
