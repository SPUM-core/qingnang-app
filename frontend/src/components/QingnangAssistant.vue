<template>
  <div class="assistant-root" ref="rootRef" :style="fabPosStyle">
    <!-- 悬浮触发按钮（可拖动） -->
    <button class="fab" :class="{ minimized: isOpen, dragging: isDragging }"
            @click="onFabClick"
            @mousedown="onDragStart"
            @touchstart="onTouchStart"
            @touchmove="onTouchMove"
            @touchend="onTouchEnd"
            :title="isOpen ? '收起青囊管家' : '青囊管家（可拖动）'"
            :aria-label="isOpen ? '收起青囊管家' : '打开青囊管家'">
      <svg v-if="!isOpen" viewBox="0 0 100 100" width="28" height="28" class="fab-logo">
        <polygon points="50,5 90,28 90,72 50,95 10,72 10,28" fill="none" stroke="#fff" stroke-width="4"/>
        <circle cx="50" cy="50" r="14" fill="none" stroke="var(--qn-emerald-accent)" stroke-width="2" stroke-dasharray="3 2"/>
        <path d="M38 50 Q50 42 62 50 Q50 58 38 50" fill="none" stroke="var(--qn-emerald-accent)" stroke-width="2.5" stroke-linecap="round"/>
      </svg>
      <span v-else class="fab-close">✕</span>
      <span class="fab-pulse" v-if="unread > 0"></span>
    </button>

    <!-- 遮罩：仅用于变暗与拦截页面点击，关闭逻辑由 document 监听统一处理 -->
    <transition name="fade">
      <div v-if="isOpen" class="drawer-backdrop"></div>
    </transition>

    <!-- 对话抽屉 -->
    <transition name="drawer">
      <div v-if="isOpen" ref="drawerRef" class="drawer">
        <!-- 📜 历史侧栏 —— 左上按钮触发的 slide-in overlay -->
        <transition name="sidebar-slide">
          <aside v-if="historyOpen" class="history-sidebar-overlay" @click.self="historyOpen = false">
            <div class="history-sidebar">
              <div class="hs-head">
                <span class="hs-title">
                  <QIcon name="history" :size="14" />对话历史
                </span>
                <button class="hs-btn" @click="clearChat" title="新对话" aria-label="新对话">
                  <QIcon name="plus" :size="15" />
                </button>
              </div>
              <div class="hs-list">
                <div class="hs-group">
                  <div class="hs-group-title">今日</div>
                  <div v-for="(g, gi) in historyToday" :key="'t'+gi" class="hs-item"
                       @click="loadHistory(g.id); historyOpen = false">
                    <span class="hs-time">{{ g.time }}</span>
                    <span class="hs-preview">{{ g.preview }}</span>
                  </div>
                </div>
                <div v-if="historyEarlier.length" class="hs-group">
                  <div class="hs-group-title">更早</div>
                  <div v-for="(g, gi) in historyEarlier" :key="'e'+gi" class="hs-item"
                       @click="loadHistory(g.id); historyOpen = false">
                    <span class="hs-date">{{ g.date }}</span>
                    <span class="hs-preview">{{ g.preview }}</span>
                  </div>
                </div>
                <div v-if="historyToday.length === 0 && historyEarlier.length === 0" class="hs-empty">
                  <p>暂无历史</p>
                  <p class="hs-empty-hint">开始第一段对话吧～</p>
                </div>
              </div>
            </div>
          </aside>
        </transition>

        <!-- 💬 对话主区 -->
        <div class="drawer-main">
        <!-- 头部 -->
        <div class="drawer-head">
          <!-- 🆕 左上：历史对话按钮 -->
          <button class="head-btn history-toggle" @click="toggleHistory"
                  title="对话历史" aria-label="对话历史">
            <QIcon name="history" :size="16" />
          </button>
          <div class="avatar"><QIcon name="sprout" :size="20" /></div>
          <div class="head-info">
            <h3>青囊管家</h3>
            <p class="head-sub">SPUM · 你的专属健康生活顾问</p>
          </div>
          <button class="head-btn" @click="clearChat" title="新对话" aria-label="新对话">
            <QIcon name="refresh" :size="16" />
          </button>
          <button class="head-btn close" @click="toggle" title="收起" aria-label="收起">
            <QIcon name="minimize" :size="16" />
          </button>
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
            <div class="welcome-avatar"><QIcon name="sprout" :size="30" /></div>
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
            <div v-for="m in visibleMessages" :key="m.id" class="msg-row" :class="m.role">
              <div class="msg-avatar">
                <QIcon :name="m.role === 'ai' ? 'sprout' : 'user'" :size="16" />
              </div>
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
                  <div v-if="m.brief" class="brief-card">
                    <!-- L2+: LLM 填的人话解读（anchor_note / food_highlight）—— 把冷数据变成 AI 说的话 -->
                    <div v-if="m.brief_card_fill?.anchor_note || m.brief_card_fill?.food_highlight" class="brief-ai-note">
                      <span v-if="m.brief_card_fill?.anchor_note" class="brief-note-line">💡 {{ m.brief_card_fill.anchor_note }}</span>
                      <span v-if="m.brief_card_fill?.food_highlight" class="brief-note-line accent">🍜 {{ m.brief_card_fill.food_highlight }}</span>
                    </div>
                    <div v-if="m.brief.anchor?.ganzhi" class="brief-anchor">
                      <span class="brief-label">今日干支</span>
                      <span class="brief-ganzhi">{{ m.brief.anchor.ganzhi }}</span>
                      <span v-if="m.brief.anchor.chong" class="brief-chong">· 冲 {{ m.brief.anchor.chong }}</span>
                      <span v-if="m.brief.anchor.state" class="brief-state">· {{ m.brief.anchor.state }}</span>
                    </div>
                    <div class="brief-yi-ji">
                      <div v-if="m.brief.anchor?.yi" class="brief-row yi">
                        <span class="brief-tag-tag">宜</span><span>{{ m.brief.anchor.yi }}</span>
                      </div>
                      <div v-if="m.brief.anchor?.ji" class="brief-row ji">
                        <span class="brief-tag-tag">忌</span><span>{{ m.brief.anchor.ji }}</span>
                      </div>
                    </div>
                    <div v-if="m.brief.food_good?.length || m.brief.food_bad?.length" class="brief-section">
                      <span class="brief-section-title">🍜 饮食</span>
                      <div v-if="m.brief.food_good?.length" class="brief-items good">
                        <span v-for="(f, i) in m.brief.food_good.slice(0,4)" :key="'g'+i" class="brief-item good"
                              :title="f.desc">{{ f.title }}</span>
                      </div>
                      <div v-if="m.brief.food_bad?.length" class="brief-items bad">
                        <span v-for="(f, i) in m.brief.food_bad.slice(0,3)" :key="'b'+i" class="brief-item bad"
                              :title="f.desc">{{ f.title }}</span>
                      </div>
                    </div>
                    <div v-if="m.brief.cloth?.length" class="brief-section">
                      <span class="brief-section-title">👗 穿搭</span>
                      <div class="brief-items">
                        <span v-for="(c, i) in m.brief.cloth.slice(0,4)" :key="'c'+i" class="brief-item cloth"
                              :title="c.desc">{{ c.title }}</span>
                      </div>
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
          <!-- 🎤 语音按钮 -->
          <button class="voice-btn" :class="{ recording: recording }"
                  @click="toggleRecordVoice" :disabled="thinking"
                  :title="recording ? '停止录音' : '语音输入'">
            <svg v-if="!recording" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="23"/>
              <line x1="8" y1="23" x2="16" y2="23"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2"/>
            </svg>
          </button>

          <textarea
            v-model="input"
            rows="1"
            :placeholder="recording ? '录音中…再次点击停止' : placeholder"
            @keydown="onKeydown"
            @input="autoResize"
            ref="taRef"
            :disabled="recording"
          ></textarea>

          <!-- 录音状态条 -->
          <div v-if="recording" class="recording-bar">
            <span class="rec-dot"></span>
            <span class="rec-time">{{ recordingDuration }}s</span>
            <span class="rec-hint">松开发送</span>
          </div>

          <button class="send-btn" :disabled="(!input.trim() && !pendingVoice) || thinking"
                  @click="sendWithVoice(input.trim())">
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
import * as storage from '../utils/storage'
import { api } from '../api/client'
import QIcon from './ui/QIcon.vue'

const userStore = useUserStore()
const router = useRouter()

// ═══ 状态 ═══
const isOpen = ref(false)
const historyOpen = ref(false)   // 历史侧栏 overlay 是否打开
const messages = ref([])
const input = ref('')
const thinking = ref(false)
const unread = ref(0)
const msgAreaRef = ref(null)
const taRef = ref(null)
const rootRef = ref(null)
const drawerRef = ref(null)
const isFullscreen = ref(false)

// ═══ 历史消息侧栏 ═══
const chatHistory = ref([])  // 从后端 /chat/messages 拉
const historyLoaded = ref(false)

// ⭐ 过滤掉幕后 context 消息（_context=true）—— 只渲染 user/ai 可见消息
const visibleMessages = computed(() => messages.value.filter(m => !m._context))

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

// 按"一次对话"分组的历史（给左栏渲染）
// 每条 = 用户发问 + 紧随其后的 AI 回复，preview 优先用 AI 回复的开头
function groupSessions(msgs) {
  const sessions = []
  let cur = null
  for (const m of msgs) {
    if (m.role === 'user') {
      // 结束上一组（如果有 user 但没 AI 回复也算一组）
      if (cur) sessions.push(cur)
      cur = { userMsg: m, aiMsg: null }
    } else if (m.role === 'assistant' && cur) {
      cur.aiMsg = m
      sessions.push(cur)
      cur = null
    }
  }
  if (cur) sessions.push(cur)   // 最后一个没 AI 回复的 user
  return sessions
}

const historyToday = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return groupSessions(chatHistory.value)
    .filter(s => s.userMsg.dateStr === today)
    .map((s, i) => ({
      id: s.userMsg.id,                // 用 user 消息 id 作为跳转锚点
      time: s.userMsg.timeStr,
      preview: (s.aiMsg?.content || s.userMsg.content || '').slice(0, 36),
      ts: s.userMsg.ts,
    }))
    .sort((a, b) => b.ts - a.ts)     // 最新在前
})

const historyEarlier = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return groupSessions(chatHistory.value)
    .filter(s => s.userMsg.dateStr !== today)
    .map((s, i) => ({
      id: s.userMsg.id,
      date: s.userMsg.dateStr,
      preview: (s.aiMsg?.content || s.userMsg.content || '').slice(0, 36),
      ts: s.userMsg.ts,
    }))
    .sort((a, b) => b.ts - a.ts)
    .slice(0, 20)
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

// ═══ FAB 拖动相关（位置偏好是全局 key，跨账号共享） ═══
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

/** 加载 FAB 位置（全局 key，跨账号共享） */
function loadFabPos() {
  const pos = storage.getGlobal('qingnang-fab-pos', {}) || {}
  if (typeof pos.x === 'number' && typeof pos.y === 'number') {
    fabX.value = pos.x
    fabY.value = pos.y
  }
}

/** 保存 FAB 位置到全局 scope（跨账号共享） */
function saveFabPos(x, y) {
  try {
    const FAB_SIZE = 56
    const TAB_BAR_H = window.innerWidth <= 720 ? 72 : 0  // 移动端 Tab Bar 占位
    const maxX = window.innerWidth - FAB_SIZE - 8
    const maxY = window.innerHeight - FAB_SIZE - TAB_BAR_H - 8
    const safeX = Math.max(8, Math.min(x, maxX))
    const safeY = Math.max(8, Math.min(y, maxY))
    storage.setGlobal('qingnang-fab-pos', { x: safeX, y: safeY })
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
let skipNextClick = false   // 触摸结束后跳过浏览器自动触发的 click
function onTouchStart(e) {
  isDragging.value = true
  dragMoved = false
  dragStartX = e.touches[0].clientX
  dragStartY = e.touches[0].clientY
  fabStartX = fabX.value !== null ? fabX.value : window.innerWidth - 80
  fabStartY = fabY.value !== null ? fabY.value : window.innerHeight - 100
}
function onTouchMove(e) {
  const t = e.touches[0]
  const dx = t.clientX - dragStartX
  const dy = t.clientY - dragStartY
  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) dragMoved = true
  if (dragMoved) {
    e.preventDefault()  // 只在拖动时阻止滚动
    fabX.value = fabStartX + dx
    fabY.value = fabStartY + dy
  }
}
function onTouchEnd() {
  if (dragMoved) {
    saveFabPos(fabX.value, fabY.value)
    skipNextClick = true   // 拖动了 — 阻止浏览器后续的 click
  } else {
    // 没拖动 — 这是点击！立即 toggle
    skipNextClick = true   // 阻止浏览器后续的 click 重复 toggle
    toggle()
  }
  isDragging.value = false
}

/** 桌面端鼠标点击（移动端触摸后浏览器会自动触发 click — 用 skipNextClick 跳过） */
function onFabClick() {
  if (skipNextClick) {
    skipNextClick = false
    return
  }
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

// ═══ 外部触发：带上下文打开对话（anchor 解读 → 管家聊天）═══
// 方案：onMounted 把 openWithContext 挂到 window.__qingnangAssistant
// DashboardView 直接调用，比 CustomEvent 更可靠
function openWithContext({ anchor, explain, followup }) {
  try {
    console.log('[QA.openWithContext] called', { anchor, explainLen: explain?.length })
    // 1. 开抽屉
    isOpen.value = true
    unread.value = 0
    console.log('[QA] isOpen set to true, current:', isOpen.value)
    nextTick(() => taRef.value?.focus({ preventScroll: true }))

    // 2. 注入"AI 之前给的解读"作为 system 消息（幕后，不渲染）
    if (explain) {
      if (!messages.value.some(m => m._context)) {
        messages.value = [...messages.value, {
          id: ++msgId, role: 'system',
          content: `【今日时空锚点 AI 大白话解读 · ${anchor?.ganzhi || ''}】\n${explain}`,
          time: nowTime(), segments: [{ text: explain, bold: false }], _context: true,
        }]
        console.log('[QA] context msg injected, total msgs:', messages.value.length)
      }
    }

    // 3. 自动发 follow-up —— setTimeout 300ms 等 drawer DOM 完全渲染（send() 需要访问 taRef）
    const defaultFollowup = followup || '关于今天的时空锚点解读，我还有一些问题想深入聊聊'
    console.log('[QA] about to send:', defaultFollowup)
    setTimeout(() => {
      try {
        send(defaultFollowup)
        console.log('[QA] send() called OK')
      } catch (e) {
        console.error('[QA] send() threw:', e)
      }
    }, 350)
  } catch (e) {
    console.error('[QA.openWithContext] FATAL:', e)
  }
}

onMounted(() => {
  loadFabPos()
  window.addEventListener('resize', onResize)
  // 点击空白区域关闭抽屉（pointerdown 同时覆盖鼠标与触摸）
  document.addEventListener('pointerdown', onDocPointerDown, true)
  // 🎖️ 登录后拉一次成熟度（欢迎态徽章立即显示）
  if (userStore.loggedIn && !userStore.maturity) {
    userStore.fetchMaturity().catch(() => {})
  }
  // ⭐ 暴露给外部（DashboardView 等）：直接调用比 CustomEvent 可靠
  window.__qingnangAssistant = { openWithContext, toggle }
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  document.removeEventListener('pointerdown', onDocPointerDown, true)
  if (window.__qingnangAssistant?.openWithContext === openWithContext) {
    window.__qingnangAssistant = null
  }
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

// ═══ 快捷问题（SPUM 本体论对齐，不再 Stage 分层）═══
// 设计原则：每个快捷问题对应 SPUM 的一个认知维度
//  · 拓扑健康：ΔV 偏离、五形状态
//  · 时间调制：节气/时辰/日干支对当前 S 向量的影响
//  · 边界整合：饮食/作息/运动如何作为"外来边集"被 G_body 整合
//  · 抉择引导：今天的精力适合做什么决策
//  · 身体邀请：主动采集脉搏/舌苔——补全数字模型缺口
const SPUM_QUICK_QUESTIONS = [
  "我的五形向量现在怎么样？ΔV 偏到哪里了？",
  "今天节气和时辰对我的拓扑调平有什么建议？",
  "我这种体质适合吃什么？为什么？",
  "今天精力适合做什么决策？需要注意什么边界冲突？",
  "帮我摸个脉（采集 PPG 观测）",
  "最近睡眠/情绪反映了什么拓扑状态？",
]
const quickQuestions = computed(() => SPUM_QUICK_QUESTIONS)

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
    // preventScroll：避免聚焦输入框时把抽屉内部整块滚动，导致顶部标题栏（含关闭按钮）被顶出可视区
    nextTick(() => taRef.value?.focus({ preventScroll: true }))
  }
}

/** 点击抽屉/悬浮球以外的空白区域 → 关闭抽屉 */
function onDocPointerDown(e) {
  if (!isOpen.value) return
  const d = drawerRef.value
  if (d && d.contains(e.target)) return                     // 点在抽屉内 → 忽略
  if (e.target?.closest?.('.fab')) return                    // 点在悬浮球 → 交给 onFabClick
  toggle()                                                   // 其余（含遮罩/页面空白）→ 关闭
}
const clearChat = () => {
  if (messages.value.length === 0) return
  if (confirm('开始新的对话？')) messages.value = []
}
// 🆕 历史侧栏 toggle：按需打开，自动收回
async function toggleHistory() {
  historyOpen.value = !historyOpen.value
  if (historyOpen.value && !historyLoaded.value) {
    await loadHistoryList()
  }
}
// toggleFullscreen 保留兼容但不再切换 UI（默认就全屏）
const toggleFullscreen = async () => {}

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

// ═══ 语音录音 ═══
const recording = ref(false)
const recordingDuration = ref(0)
const pendingVoice = ref(null)  // { base64, format, duration }
let mediaRecorder = null
let audioChunks = []
let recTimer = null

async function toggleRecordVoice() {
  if (recording.value) {
    // 停止
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop()
    }
    recording.value = false
    if (recTimer) { clearInterval(recTimer); recTimer = null }
  } else {
    // 开始
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      audioChunks = []
      recordingDuration.value = 0

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data)
      }

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(audioChunks, { type: 'audio/webm' })
        // 转 base64
        const b64 = await blobToBase64(blob)
        pendingVoice.value = {
          base64: b64,
          format: 'webm',
          duration: recordingDuration.value,
        }
        // 有语音了自动发（如果文字也空的话）
        if (!input.value.trim() && pendingVoice.value) {
          await sendWithVoice('')
        }
      }

      mediaRecorder.start()
      recording.value = true
      recTimer = setInterval(() => { recordingDuration.value++ }, 1000)
    } catch (e) {
      alert('麦克风访问失败：' + e.message)
    }
  }
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result.split(',')[1])
    r.onerror = reject
    r.readAsDataURL(blob)
  })
}

// sendWithVoice：同时发文字和语音
const sendWithVoice = async (text) => {
  if ((!text && !pendingVoice.value) || thinking.value) return
  await send(text, pendingVoice.value)
  pendingVoice.value = null
}

const send = async (text, voiceData = null) => {
  if (!text && !voiceData) return

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
      .filter(m => m.id !== typingMsg.id && !m.typing && !m._context)   // context 消息不进 history（我们把它作为新对话的 system prompt 前缀注入）
      .slice(-10)
      .map(m => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.content }))

    // ⭐ 把 context 解读作为 system prompt 前缀 —— 确保 LLM 知道"前置上下文"
    const contextMsg = messages.value.find(m => m._context)
    if (contextMsg) {
      // 插到 history 最前面（DeepSeek 要求 system 必须在第一条）
      history.unshift({ role: 'system', content: contextMsg.content })
    }

    const settings = storage.get('qingnang_settings', {}) || {}
    let provider = settings.llm_provider || undefined  // 不传 → 后端默认

    const chatPayload = { message: text || '', history, provider }
    if (voiceData) {
      chatPayload.voice_base64 = voiceData.base64
      chatPayload.voice_format = voiceData.format
      chatPayload.voice_duration = voiceData.duration
    }
    r = await api.post('/api/v1/assistant/chat', chatPayload)
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
  const actions = (r.data?.actions || []).map(a => ({
    ...a,
    type: a.type || 'navigate',  // 兼容旧后端（只有 route 没有 type）
  }))
  const analysis = r.data?.analysis || null
  // brief 卡片：后端决定何时渲染，前端只管消费
  const briefCtx = r.data?.render_brief_card ? r.data?.brief_context : null
  // extracted_signals 存到 scope 方便同账号消费
  if (r.data?.extracted_signals?.length) {
    storage.set('qingnang-latest-signals', {
      signals: r.data.extracted_signals,
      at: Date.now(),
    })
  }

  // 替换 typingMsg
  const finalMsg = {
    id: typingMsg.id, role: 'ai',
    content: replyText, suggestions, footnote,
    actions, analysis,
    brief: briefCtx,                  // 后端说渲染才渲染（冷数据）
    brief_card_fill: r.data?.brief_card_fill || null,  // L2+: LLM 填的人话注释
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

// 🎯 AI Tool Calling：点击青囊建议的动作按钮
async function doAction(a) {
  if (!a) return
  const type = a.type || 'navigate'

  // 按钮禁用防抖（api_call 过程中）
  if (a._executing) return
  a._executing = true

  try {
    if (type === 'api_call') {
      // ── 真实执行：调后端 /execute 端点 ──
      const r = await api.post('/api/v1/assistant/execute', {
        action_id: a.action_id,
        params: a.params || {},
      })
      const ok = r.data?.ok
      const result = r.data?.result
      // 反馈 toast（用 alert 兜底，避免再引 toast 组件依赖）
      if (ok) {
        const detail = result?.created?.title
          || result?.updated?.chief_complaint
          || (result?.skipped ? '已存在，跳过' : '执行成功')
        showToast(`✅ ${a.label?.split('「')[0].trim() || '已执行'} — ${detail}`)
      } else {
        showToast(`⚠️ 执行失败：${result?.reason || '未知原因'}`)
      }
    } else {
      // ── 跳转页面（navigate，兼容旧后端）──
      isOpen.value = false
      setTimeout(() => {
        router.push(a.route)
      }, 200)
    }
  } catch (e) {
    const status = e.response?.status
    const detail = e.response?.data?.detail || e.message
    let human
    if (status === 403) {
      human = '当前阶段不允许此操作'
    } else if (status === 404) {
      human = '未知操作'
    } else if (status === 422) {
      // L3: Pydantic 模板验证失败 — 后端会返回 detail 指出缺哪个字段
      // 例子："action_id='add_reminder' 的 params 不符合模板: {}"
      human = `参数不合法：${typeof detail === 'string' ? detail : JSON.stringify(detail)}`
    } else {
      human = `操作失败(${status || '网络'})`
    }
    showToast(`❌ ${human}`)
  } finally {
    a._executing = false
  }
}

// 轻量 toast（不引入新组件，用 DOM + 自动移除）
function showToast(text) {
  // 清除旧的
  document.querySelectorAll('.qn-toast').forEach(n => n.remove())
  const el = document.createElement('div')
  el.className = 'qn-toast'
  el.textContent = text
  Object.assign(el.style, {
    position: 'fixed', bottom: '80px', left: '50%',
    transform: 'translateX(-50%)',
    background: 'rgba(var(--qn-emerald-rgb),0.92)', color: '#fff',
    padding: '10px 18px', borderRadius: '20px', fontSize: '13px',
    zIndex: 9999, pointerEvents: 'none',
    boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
    maxWidth: '80vw', textAlign: 'center',
  })
  document.body.appendChild(el)
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.3s' }, 2200)
  setTimeout(() => el.remove(), 2600)
}
</script>

<style scoped>
.assistant-root { position: fixed; right: 24px; bottom: 24px; z-index: 1000; }

/* 悬浮按钮 */
.fab {
  width: 56px; height: 56px; border-radius: 50%;
  background: linear-gradient(135deg, var(--qn-emerald) 0%, var(--qn-emerald-dark) 100%);
  border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 20px rgba(var(--qn-emerald-rgb),0.35);
  transition: all 0.2s; position: relative;
}
.fab:hover { transform: scale(1.08); box-shadow: 0 6px 28px rgba(var(--qn-emerald-rgb),0.45); }
.fab:active { transform: scale(0.95); }
.fab.minimized { width: 40px; height: 40px; box-shadow: 0 2px 10px rgba(0,0,0,0.15); }
.fab-logo { filter: drop-shadow(0 1px 2px rgba(0,0,0,0.2)); }
.fab-close { color: #fff; font-size: calc(18px * var(--qn-fs-scale)); font-weight: 300; }
.fab-pulse {
  position: absolute; top: -2px; right: -2px; width: 14px; height: 14px;
  background: var(--wuxing-fire); border-radius: 50%;
  border: 2px solid #fff; animation: pulse-ring 1.5s infinite;
}
@keyframes pulse-ring {
  0% { transform: scale(1); opacity: 1; }
  100% { transform: scale(1.5); opacity: 0; }
}

/* 遮罩：点击空白区域关闭抽屉 */
.drawer-backdrop {
  position: fixed; inset: 0;
  background: rgba(18, 38, 34, 0.28);
  z-index: 1;  /* 位于 .assistant-root 内部，低于抽屉(1001) */
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* 抽屉 —— 所有视口统一全屏（DeepSeek 风格） */
.drawer {
  position: fixed; right: 0; bottom: 0; left: 0; top: 0;
  width: 100vw; height: 100dvh;
  background: var(--qn-paper); border-radius: 0;
  display: flex; flex-direction: column; overflow: hidden;
  z-index: 2000;
  transition: opacity 0.2s;
}
/* 电脑端不再需要 fullscreen 类 —— 默认就是全屏 */
.drawer.fullscreen { /* 兼容老类名，已在上层覆盖 */ }

/* ═══ 移动端适配 ═══ */
/* 安全区适配 */
@media (max-width: 720px) {
  .drawer-head { padding-top: calc(14px + env(safe-area-inset-top)); }
  .input-area { padding-bottom: calc(12px + env(safe-area-inset-bottom)); }
  .disclaimer { padding-bottom: calc(6px + env(safe-area-inset-bottom)); }
}

/* 📜 历史侧栏 overlay —— 左上按钮触发，slide-in */
.history-sidebar-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.3);
  z-index: 2100;
  display: flex;
}
.history-sidebar-overlay .history-sidebar {
  width: 280px; height: 100%;
  display: flex; flex-direction: column;
}
.sidebar-slide-enter-active,
.sidebar-slide-leave-active {
  transition: opacity 0.2s ease;
}
.sidebar-slide-enter-from,
.sidebar-slide-leave-to {
  opacity: 0;
}
.sidebar-slide-enter-active .history-sidebar,
.sidebar-slide-leave-active .history-sidebar {
  transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}
.sidebar-slide-enter-from .history-sidebar,
.sidebar-slide-leave-to .history-sidebar {
  transform: translateX(-100%);
}
/* history-sidebar 本体（被 overlay 嵌套时自动继承 280px 宽） */
.history-sidebar {
  background: linear-gradient(180deg, #faf9f5, #f3f1ea);
  border-right: 1px solid var(--qn-line);
  overflow: hidden;
}
.hs-head {
  padding: 14px 16px;
  display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid var(--qn-line);
  background: rgba(var(--qn-emerald-rgb),0.04);
}
.hs-title {
  font-size: calc(13px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-emerald);
  display: inline-flex; align-items: center; gap: 5px;
}
.hs-btn {
  width: 28px; height: 28px; border-radius: 6px;
  border: 1px solid rgba(var(--qn-emerald-rgb),0.3); background: var(--qn-surface);
  color: var(--qn-emerald); line-height: 1;
  display: inline-flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all 0.15s;
}
.hs-btn:hover { background: var(--qn-emerald); color: #fff; }
.hs-list { flex: 1; overflow-y: auto; padding: 8px; }
.hs-group { margin-bottom: 12px; }
.hs-group-title {
  font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-3);
  padding: 6px 10px; text-transform: uppercase; letter-spacing: 0.5px;
}
.hs-item {
  padding: 8px 10px; border-radius: 6px; cursor: pointer;
  display: flex; flex-direction: column; gap: 2px;
  transition: background 0.12s;
}
.hs-item:hover { background: rgba(var(--qn-emerald-rgb),0.06); }
.hs-time, .hs-date {
  font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-3);
}
.hs-preview {
  font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.hs-empty {
  padding: 40px 20px; text-align: center; color: var(--qn-ink-3);
}
.hs-empty p { margin: 4px 0; }
.hs-empty-hint { font-size: calc(11px * var(--qn-fs-scale)); opacity: 0.6; }

/* 💬 全屏下的对话主区 */
.drawer.fullscreen .drawer-main {
  flex: 1; display: flex; flex-direction: column;
  min-width: 0; min-height: 0; overflow: hidden;
}
/* 非全屏时 drawer-main 就是 drawer 本身 */
.drawer:not(.fullscreen) .drawer-main {
  flex: 1; display: flex; flex-direction: column;
  min-width: 0; min-height: 0; overflow: hidden;
}
.drawer-enter-active, .drawer-leave-active { transition: all 0.25s cubic-bezier(0.2, 0.8, 0.2, 1); }
.drawer-enter-from, .drawer-leave-to { opacity: 0; transform: translateY(20px) scale(0.95); }

/* 头部 */
.drawer-head {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 16px;
  background: linear-gradient(135deg, var(--qn-emerald) 0%, var(--qn-emerald-dark) 100%);
  color: #fff; flex-shrink: 0;
}
.avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: rgba(255,255,255,0.15);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; color: #fff;
}
.welcome-avatar {
  width: 64px; height: 64px; border-radius: 50%;
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.1), rgba(var(--qn-emerald-light-rgb),0.2));
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 14px;
  color: var(--qn-emerald);
  box-shadow: 0 4px 20px rgba(var(--qn-emerald-rgb),0.15);
}
.head-info { flex: 1; }
.head-info h3 { margin: 0; font-size: calc(15px * var(--qn-fs-scale)); font-weight: 600; }
.head-sub { margin: 2px 0 0; font-size: calc(11px * var(--qn-fs-scale)); color: rgba(255,255,255,0.65); }
.head-btn {
  width: 32px; height: 32px; border-radius: 50%;
  border: none; background: rgba(255,255,255,0.15);
  color: #fff; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s, transform 0.15s;
}
.head-btn:hover { background: rgba(255,255,255,0.25); }
.head-btn:active { transform: scale(.92); }
/* 图标按钮的键盘焦点环（青囊绿在深绿底上看不见，用白色半透明） */
.head-btn:focus-visible {
  outline: 2px solid rgba(255,255,255,.7);
  outline-offset: 2px;
}

/* 状态条 */
.ctx-bar {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  padding: 8px 16px;
  background: var(--qn-paper); border-bottom: 1px solid var(--qn-line);
  font-size: calc(11px * var(--qn-fs-scale)); flex-shrink: 0;
}
.ctx-item { color: var(--qn-ink-2); font-weight: 500; }
.ctx-sep { color: var(--qn-ink-3); opacity: 0.4; }
.ctx-warn { color: var(--qn-emerald); font-weight: 600; }

/* 消息区 */
.msg-area {
  flex: 1; min-height: 0; overflow-y: auto; padding: 16px;
  background: var(--qn-paper);
  scroll-behavior: smooth;
}
.msg-area::-webkit-scrollbar { width: 4px; }
.msg-area::-webkit-scrollbar-thumb { background: var(--qn-line); border-radius: 2px; }

/* 欢迎态 */
.welcome { text-align: center; padding: 20px 10px; }
.welcome h2 { margin: 0 0 4px; font-size: calc(18px * var(--qn-fs-scale)); color: var(--qn-ink); }
.welcome-time { margin: 0 0 12px; font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }
.welcome-status { margin: 0 0 6px; font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); line-height: 1.6; }

/* 🎖️ 数字模型成熟度徽章 */
.stage-badge {
  display: inline-flex; align-items: center; gap: 6px;
  margin: 4px 0 8px; padding: 5px 12px;
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.08), rgba(var(--qn-emerald-accent-rgb),0.12));
  border: 1px solid rgba(var(--qn-emerald-rgb),0.2);
  border-radius: 16px;
  font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-emerald);
}
.sb-icon { font-size: calc(14px * var(--qn-fs-scale)); }
.sb-text { font-weight: 600; }
.sb-score {
  margin-left: 2px; padding: 1px 6px;
  background: rgba(var(--qn-emerald-rgb),0.12); border-radius: 10px;
  font-weight: 500; color: var(--qn-emerald);
}

.welcome-hint { margin: 16px 0 10px; font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); letter-spacing: 0.5px; }
.quick-chips { display: flex; flex-direction: column; gap: 8px; max-width: 320px; margin: 0 auto; }
.chip-btn {
  font-size: calc(13px * var(--qn-fs-scale)); padding: 10px 16px;
  border: 1px solid rgba(var(--qn-emerald-rgb),0.2); background: var(--qn-surface);
  color: var(--qn-emerald); border-radius: 20px;
  cursor: pointer; text-align: center; transition: all 0.15s;
}
.chip-btn:hover {
  background: var(--qn-emerald); color: #fff;
  border-color: var(--qn-emerald);
  transform: translateY(-1px);
}

/* 消息行 —— DeepSeek 平铺风格 */
.msg-row { display: flex; gap: 12px; margin-bottom: 20px; align-items: flex-start; }
.msg-row.ai { flex-direction: row; }
.msg-row.user { flex-direction: row-reverse; }
.msg-row .msg-avatar {
  width: 28px; height: 28px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  font-size: calc(12px * var(--qn-fs-scale));
}
.msg-row.ai .msg-avatar { background: linear-gradient(135deg, var(--qn-emerald), var(--qn-emerald-dark)); color: #fff; }
.msg-row.user .msg-avatar { background: rgba(var(--qn-ink-3), 0.15); color: var(--qn-ink-2); }

/* DeepSeek 风格：扁平无边框无气泡 */
.msg-bubble {
  max-width: 100%; padding: 0; border-radius: 0;
  font-size: calc(14px * var(--qn-fs-scale)); line-height: 1.7; position: relative;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
.msg-row.user .msg-bubble {
  color: var(--qn-ink);
  text-align: right;
}
.msg-text strong { color: var(--qn-emerald); }
.msg-row.user .msg-text strong { color: #fff; }

.typing-dots { display: flex; gap: 4px; padding: 4px 0; }
.typing-dots span {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--qn-emerald); opacity: 0.4;
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
  font-size: calc(11px * var(--qn-fs-scale)); padding: 4px 10px;
  border: 1px solid rgba(var(--qn-emerald-rgb),0.2); background: var(--qn-surface);
  color: var(--qn-emerald); border-radius: 12px;
  cursor: pointer; transition: all 0.15s;
}
.sugg-btn:hover { background: rgba(var(--qn-emerald-rgb),0.06); border-color: var(--qn-emerald); }

/* 🎯 AI Tool Calling 动作按钮 */
.action-row {
  display: flex; flex-direction: column; gap: 6px; margin-top: 10px;
}
.action-btn {
  display: flex; align-items: center; gap: 6px;
  font-size: calc(12px * var(--qn-fs-scale)); padding: 8px 12px;
  border: 1px solid rgba(var(--qn-emerald-rgb),0.25); background: linear-gradient(135deg, rgba(var(--qn-emerald-light-rgb),0.08), var(--qn-surface));
  color: var(--qn-emerald); border-radius: 8px;
  cursor: pointer; transition: all 0.15s;
  text-align: left; font-weight: 500;
}
.action-btn:hover {
  background: linear-gradient(135deg, #e0f5ee, #f5fff9);
  border-color: var(--qn-emerald);
  transform: translateX(2px);
}
.action-btn.high { border-color: var(--qn-fire); color: var(--qn-fire); background: linear-gradient(135deg, rgba(216,67,21,0.08), var(--qn-surface)); }
.action-btn.high:hover { background: linear-gradient(135deg, rgba(216,67,21,0.12), var(--qn-surface)); }
.action-icon { font-size: calc(14px * var(--qn-fs-scale)); }
.action-arrow { margin-left: auto; opacity: 0.5; font-size: calc(11px * var(--qn-fs-scale)); }

/* 📊 AI 深度解析摘要卡 */
.analysis-card {
  margin-top: 10px; padding: 10px 12px;
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.05), rgba(212,160,23,0.04));
  border: 1px solid rgba(var(--qn-emerald-rgb),0.12);
  border-radius: 10px; font-size: calc(11px * var(--qn-fs-scale)); line-height: 1.6;
}
.ana-section { margin-bottom: 6px; }
.ana-section:last-child { margin-bottom: 0; }
.ana-tag {
  display: inline-block; margin-right: 6px;
  color: var(--qn-ink-3); font-weight: 500;
}
.ana-path {
  display: inline-block; margin: 0 3px;
  background: rgba(216,67,21,0.08); color: var(--qn-fire);
  padding: 1px 7px; border-radius: 4px; font-weight: 500;
}
.ana-base { color: var(--qn-ink-3); font-size: calc(10px * var(--qn-fs-scale)); font-weight: 400; }
.ana-sugg {
  display: inline-block; margin: 0 3px;
  background: rgba(var(--qn-emerald-rgb),0.08); color: var(--qn-emerald);
  padding: 1px 7px; border-radius: 4px;
}
.ana-sugg.high { background: rgba(216,67,21,0.1); color: var(--qn-fire); font-weight: 500; }
.ana-sugg.low { opacity: 0.7; }

/* 📅 今日宜忌/饮食/穿搭卡片（AI 真实输出 APP 数据） */
.brief-card {
  margin-top: 10px; padding: 12px 14px;
  background: linear-gradient(135deg, rgba(var(--qn-emerald-accent-rgb),0.08), rgba(var(--qn-emerald-rgb),0.04));
  border: 1px solid rgba(var(--qn-emerald-accent-rgb),0.25);
  border-radius: 10px; font-size: calc(12px * var(--qn-fs-scale)); line-height: 1.6;
}
/* L2+: LLM 填的人话解读 — 把冷数据变成 AI 说的话 */
.brief-ai-note {
  margin-bottom: 8px; padding-bottom: 8px;
  border-bottom: 1px dashed rgba(var(--qn-emerald-rgb),0.15);
  font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-emerald);
  font-style: italic;
}
.brief-note-line { display: block; margin-bottom: 2px; }
.brief-note-line.accent { color: var(--qn-fire); font-style: normal; font-weight: 500; }
.brief-anchor {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  padding-bottom: 8px; border-bottom: 1px dashed rgba(var(--qn-emerald-rgb),0.15); margin-bottom: 8px;
}
.brief-label { font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-3); letter-spacing: 0.5px; }
.brief-ganzhi { font-weight: 600; color: var(--qn-emerald); font-size: calc(14px * var(--qn-fs-scale)); }
.brief-chong { color: var(--qn-fire); font-size: calc(11px * var(--qn-fs-scale)); }
.brief-state { color: var(--qn-ink-2); font-size: calc(11px * var(--qn-fs-scale)); }
.brief-yi-ji { margin-bottom: 8px; }
.brief-row { display: flex; align-items: flex-start; gap: 6px; margin-bottom: 3px; font-size: calc(11px * var(--qn-fs-scale)); }
.brief-row .brief-tag-tag {
  flex-shrink: 0; width: 16px; height: 16px; line-height: 16px;
  border-radius: 4px; text-align: center; font-size: calc(10px * var(--qn-fs-scale)); font-weight: 600;
}
.brief-row.yi .brief-tag-tag { background: rgba(var(--qn-emerald-accent-rgb),0.2); color: var(--qn-emerald); }
.brief-row.ji .brief-tag-tag { background: rgba(216,67,21,0.15); color: var(--qn-fire); }
.brief-section { margin-top: 6px; }
.brief-section-title {
  display: block; font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3);
  margin-bottom: 6px; font-weight: 500;
}
.brief-items { display: flex; flex-wrap: wrap; gap: 5px; }
.brief-item {
  font-size: calc(11px * var(--qn-fs-scale)); padding: 3px 9px; border-radius: 12px;
  cursor: default;
}
.brief-item.good { background: rgba(var(--qn-emerald-accent-rgb),0.12); color: var(--qn-emerald); }
.brief-item.bad { background: rgba(216,67,21,0.1); color: var(--qn-fire); }
.brief-item.cloth { background: rgba(156,39,176,0.08); color: #6A1B9A; }

.msg-footnote {
  margin-top: 8px; padding-top: 6px;
  border-top: 1px dashed var(--qn-line);
  font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-3); font-style: italic;
}
.msg-row.user .msg-footnote { display: none; }

.msg-time {
  font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-top: 4px; opacity: 0.6;
}
.msg-row.user .msg-time { text-align: right; }

/* 输入区 */
.input-area {
  display: flex; align-items: flex-end; gap: 8px;
  padding: 12px 14px; background: var(--qn-surface); border-top: 1px solid var(--qn-line);
  flex-shrink: 0;
}
.input-area textarea {
  flex: 1; resize: none; border: 1px solid var(--qn-line); border-radius: 20px;
  padding: 9px 16px; font-size: calc(13px * var(--qn-fs-scale)); font-family: inherit;
  background: var(--qn-paper); color: var(--qn-ink);
  max-height: 120px; line-height: 1.5; outline: none;
  transition: border-color 0.15s;
}
.input-area textarea:focus { border-color: var(--qn-emerald); background: var(--qn-surface); }
.send-btn {
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--qn-emerald); border: none; color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0; transition: all 0.15s;
}
.send-btn:hover:not(:disabled) { background: var(--qn-emerald-light); transform: scale(1.05); }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* 🎤 语音按钮 */
.voice-btn {
  width: 36px; height: 36px; flex-shrink: 0;
  background: transparent; border: 1.5px solid var(--qn-line);
  border-radius: 50%; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: var(--qn-ink-3); transition: all 0.15s;
}
.voice-btn:hover:not(:disabled) { border-color: var(--qn-emerald); color: var(--qn-emerald); }
.voice-btn.recording { background: #d33; border-color: #d33; color: #fff; animation: pulse-rec 1.2s ease-in-out infinite; }
@keyframes pulse-rec { 0%,100% { transform: scale(1); } 50% { transform: scale(1.08); } }
.voice-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* 录音状态条 */
.recording-bar {
  position: absolute; bottom: 100%; left: 40px; margin-bottom: 8px;
  background: #333; color: #fff; padding: 4px 10px; border-radius: 14px;
  font-size: calc(12px * var(--qn-fs-scale)); display: flex; align-items: center; gap: 6px;
  white-space: nowrap; z-index: 10;
}
.rec-dot { width: 8px; height: 8px; background: #ff4444; border-radius: 50%; animation: rec-blink 1s infinite; }
@keyframes rec-blink { 0%,100%{opacity:1} 50%{opacity:0.2} }
.rec-time { font-weight: 600; font-variant-numeric: tabular-nums; }
.rec-hint { color: #aaa; }

.disclaimer {
  margin: 0; padding: 6px 16px;
  background: var(--qn-paper); border-top: 1px solid var(--qn-line);
  font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-3); text-align: center; flex-shrink: 0;
  line-height: 1.4;
}

/* 注：旧的 520px media query 已合并入上面 720px 规则 —— 手机端抽屉始终全屏铺满 */
</style>
