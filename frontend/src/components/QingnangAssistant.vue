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
      <div v-if="isOpen" class="drawer">
        <!-- 头部 -->
        <div class="drawer-head">
          <div class="avatar">🌿</div>
          <div class="head-info">
            <h3>青囊管家</h3>
            <p class="head-sub">SPUM · 你的专属健康生活顾问</p>
          </div>
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
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, nextTick, computed, onMounted, onBeforeUnmount } from 'vue'
import { useUserStore } from '../stores/user'
import { api } from '../api/client'

const userStore = useUserStore()

// ═══ 状态 ═══
const isOpen = ref(false)
const messages = ref([])
const input = ref('')
const thinking = ref(false)
const unread = ref(0)
const msgAreaRef = ref(null)
const taRef = ref(null)

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
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
})

// ═══ 快捷问题（通用，不再硬编码胡运涛） ═══
const quickQuestions = computed(() => [
  '我今天该吃什么？',
  '晚上几点睡最好？',
  '推荐一个放松方式',
  '我适合什么颜色？',
  '现在可以运动吗？',
])

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
  try {
    const history = messages.value
      .filter(m => m.id !== typingMsg.id && !m.typing)
      .slice(-10)
      .map(m => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.content }))

    const r = await api.post('/api/v1/assistant/chat', { message: text, history })
    replyText = r.data?.reply || ''
    engineLabel = r.data?.engine === 'qingmeng' ? `青檬引擎 · ${r.data.latency_ms}ms` : '本地规则回复'
    footnote = engineLabel
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

  // 替换 typingMsg
  const finalMsg = {
    id: typingMsg.id, role: 'ai',
    content: replyText, suggestions, footnote,
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
  max-height: calc(100vh - 120px);
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
