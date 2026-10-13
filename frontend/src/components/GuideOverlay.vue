<template>
  <!-- ⭐ 去掉 Vue <transition>（某些浏览器 enter-from 临时阻止 pointer-events）
       改靠 CSS opacity transition 在可见/隐藏间平滑过渡 -->
  <div
    v-show="visible"
    class="guide-overlay"
    :style="{ opacity: visible ? 1 : 0 }"
  >
      <!-- ① 半透明遮罩层（主层） -->
      <div class="guide-mask"></div>

      <!-- ② 目标元素"发光框"（高亮 cutout 效果） -->
      <div
        v-if="currentTarget"
        class="guide-highlight"
        :style="highlightStyle"
      ></div>

      <!-- ③ 气泡卡片 + 箭头 -->
      <div
        ref="bubbleRef"
        class="guide-bubble"
        :class="bubblePosition"
        :style="bubbleStyle"
      >
        <div class="bubble-header">
          <span class="bubble-step">第 {{ stepIdx + 1 }} / {{ steps.length }} 步</span>
          <button class="bubble-skip" @click="finish" title="跳过引导">跳过 ×</button>
        </div>
        <h3 class="bubble-title">{{ step.title }}</h3>
        <p class="bubble-content">{{ step.content }}</p>
        <div v-if="step.cta" class="bubble-cta">
          <button class="cta-btn" @click="onCtaClick">{{ step.cta.text }}</button>
        </div>
        <div class="bubble-footer">
          <div class="bubble-actions">
            <!-- waitForClick 模式：等用户自己点目标元素，不提供下一步按钮 -->
            <template v-if="step.waitForClick">
              <span class="wait-hint">👉 请点击高亮区域继续</span>
              <button class="action-btn ghost" @click="finish">跳过</button>
            </template>
            <template v-else>
              <button v-if="stepIdx > 0" class="action-btn ghost" @click="prev">← 上一步</button>
              <button v-if="stepIdx < steps.length - 1" class="action-btn primary" @click="next">
                下一步 →
              </button>
              <button v-else class="action-btn primary" @click="finish">
                {{ lastStepCtaText }}
              </button>
            </template>
          </div>
        </div>
      </div>

      <!-- ④ 箭头（指向高亮框） -->
      <div
        v-if="currentTarget"
        class="guide-arrow"
        :class="arrowDirection"
        :style="arrowStyle"
      ></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import * as storage from '../utils/storage'

const props = defineProps({
  /** 默认 storageKey（兼容旧用法） */
  storageKey: { type: String, default: 'qingnang_guide_completed' },
})

const emit = defineEmits(['finish', 'cta'])

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// ═══════════════════════════════════════════════════════════════
// 引导脚本（按路由分组，每组独立 storageKey 控制一次性触发）
// ═══════════════════════════════════════════════════════════════
// target: CSS selector 或 null（全屏介绍）
// bubblePosition: 'bottom' | 'top' | 'left' | 'right' | 'center'
// cta: { text, action: 'router'|'finish', payload }

const GUIDE_GROUPS = {
  '/': {
    storageKey: 'guide_home_completed',
    steps: [
      {
        title: '👋 欢迎来到青囊',
        content: '你已完成先天体质建模。青囊围绕「辨体质 · 观漂移 · 调平衡」设计，下面带你快速熟悉核心功能。',
        target: null,
        bubblePosition: 'center',
      },
      {
        title: '🧭 顶部导航',
        content: '主页看每日概览，体质看你的数字档案，发现是知识和工具区。',
        target: '.layout__nav',
        bubblePosition: 'bottom',
      },
      {
        title: '📊 先天数字画像',
        content: '刚完成的八字推演 —— 五行向量、干支、时空锚点、今日宜忌。这是你的「先天基线 V_base」，所有调理都围绕它展开。',
        target: '.page.home .hero-row',
        bubblePosition: 'bottom',
      },
      {
        title: '💡 AI 今日生活建议',
        content: '结合体质 + 节气天气，青囊 AI 生成饮食、穿搭、家居、时辰方面的具体建议。点击卡片可展开详情。',
        target: '.page.home .todo-grid',
        bubblePosition: 'top',
      },
      {
        title: '🤖 青囊管家 AI',
        content: '右下角悬浮按钮是青囊管家 —— 随时对话，它知道你的体质档案。',
        target: '.assistant-root .fab',
        bubblePosition: 'top',
      },
      {
        title: '👉 点导航「体质」进入数字档案',
        content: '下一步去你的数字档案页面 —— 那里有所有历史报告的时间线，以及 7 种数据采集方式的完整说明。现在请点顶部导航的「体质」按钮，引导会自动继续。',
        target: '.layout__nav a[href="/case"]',
        bubblePosition: 'bottom',
        waitForClick: true,
      },
    ],
  },

  '/case': {
    storageKey: 'guide_case_completed',
    steps: [
      {
        title: '📜 数字体质档案',
        content: '这里是你的数字档案页面 —— 先天基底、历史调理方案、所有采集到的观测数据，都按时间线在这里汇总。',
        target: null,
        bubblePosition: 'center',
      },
      {
        title: '📅 报告时间线',
        content: '所有报告按日期倒序排列：脉诊 PPG、调理方案、AI 问诊摘要，都在这一条时间线上。点击任意一行可以展开完整内容。',
        target: '.page.case .tl-wrap',
        bubblePosition: 'bottom',
      },
      {
        title: '🏛️ 先天基底 S₀⁰',
        content: '这是你的「体质根」—— 八字推演出来的五行向量 V_base。它不会变，是所有调理方案的基准参照。',
        target: '.page.case .foundation-wrap .clickable-card',
        bubblePosition: 'bottom',
      },
      {
        title: '📥 7 种数据采集方式',
        content: '青囊的 AI 推理引擎需要持续的数据输入：AI 问诊 · 脉搏 PPG · 舌部照片 · 体态照片 · 语音样本 · 检查报告 · 日常打卡。点右上角「数据采集」按钮进入采集中心。',
        target: '.hero-cta-btn',
        bubblePosition: 'bottom',
      },
      {
        title: '👉 点「数据采集」按钮进入采集中心',
        content: '现在请点右上角的「数据采集」按钮，引导会自动跳转到采集中心继续。',
        target: '.hero-cta-btn',
        bubblePosition: 'bottom',
        waitForClick: true,
      },
    ],
  },

  '/collect': {
    storageKey: 'guide_collect_completed',
    steps: [
      {
        title: '📥 数据采集中心',
        content: '青囊的数字模型需要持续的真实数据输入。下面 7 种采集方式任选，推荐先从 AI 问诊开始 —— 最快 3 分钟就能得到你的当前状态向量 V_current。',
        target: null,
        bubblePosition: 'center',
      },
      {
        title: '🗂️ 7 种采集方式',
        content: '① AI 问诊（推荐先做） ② 脉搏 PPG（专业硬件） ③ 舌部照片 ④ 体态照片 ⑤ 语音样本 ⑥ 检查报告上传 ⑦ 日常打卡。完成得越多，青囊 AI 的漂移拟合越准。',
        target: '.page.collect-entry',
        bubblePosition: 'bottom',
      },
      {
        title: '🚀 推荐第一步：AI 问诊',
        content: 'AI 问诊是纯文本采集，4 阶段结构化问诊，约 3 分钟。完成后青囊会为你生成 V_current 向量，从此日常观测和智能方案会更精准。',
        target: null,
        bubblePosition: 'center',
        cta: { text: '🚀 立即开始 AI 问诊', action: 'router', payload: '/collect/inquiry' },
      },
    ],
  },
}

// 根据当前路由匹配分组（精确匹配，后续可加前缀匹配）
function matchGroup(path) {
  // 先精确
  if (GUIDE_GROUPS[path]) return GUIDE_GROUPS[path]
  // 前缀（/collect/* 也算 /case 的扩展 —— 但这里不需要，保持独立）
  return null
}

const currentGroup = ref(matchGroup(route.path))
const storageKey = computed(() => currentGroup.value?.storageKey || props.storageKey)
const allSteps = computed(() => currentGroup.value?.steps || [])
const steps = allSteps

// ── 状态 ──
const visible = ref(false)
const stepIdx = ref(0)
const lastStepCtaText = '开始 AI 问诊 →'

let targetEl = null
let resizeObserver = null

const step = computed(() => steps.value?.[stepIdx.value] || {})
const currentTarget = computed(() => step.value.target)

// ── 定位计算 ──
const highlightRect = ref({ top: 0, left: 0, width: 0, height: 0 })

const highlightStyle = computed(() => {
  const r = highlightRect.value
  if (!r.width || !r.height) return { opacity: 0 }
  return {
    top: `${r.top - 6}px`,
    left: `${r.left - 6}px`,
    width: `${r.width + 12}px`,
    height: `${r.height + 12}px`,
    opacity: 1,
  }
})

const bubblePosition = computed(() => step.value.bubblePosition || 'bottom')

function measureTarget() {
  if (!currentTarget.value) {
    highlightRect.value = { top: 0, left: 0, width: 0, height: 0 }
    return
  }
  nextTick(() => {
    targetEl = document.querySelector(currentTarget.value)
    if (!targetEl) {
      // fallback 到屏幕中心
      highlightRect.value = {
        top: window.innerHeight * 0.35,
        left: window.innerWidth * 0.15,
        width: window.innerWidth * 0.7,
        height: window.innerHeight * 0.3,
      }
      return
    }
    // ⭐ 手机端关键修复：用 instant scroll（smooth 在 iOS Safari 被忽略）
    targetEl.scrollIntoView({ behavior: 'auto', block: 'center', inline: 'nearest' })

    // ⭐ 多次取 rect：0ms / 100ms / 250ms —— 取最后一次（确保滚动完全停稳）
    const measureAt = (delay) => {
      setTimeout(() => {
        if (!targetEl) return
        const rect = targetEl.getBoundingClientRect()
        highlightRect.value = {
          top: rect.top,
          left: rect.left,
          width: rect.width,
          height: rect.height,
          right: rect.right,
          bottom: rect.bottom,
        }
      }, delay)
    }
    measureAt(0)      // 立即（如果不需要滚动就准）
    measureAt(120)    // 第一次补正
    measureAt(280)    // 第二次补正（兜底）
  })
}

const bubbleRef = ref(null)   // ⭐ 动态测量 bubble 真实高度

// ⭐ 边界钳制：确保 bubble 完全在 viewport 内
function clamp(val, min, max) { return Math.min(Math.max(val, min), max) }
function getBubbleWidth() { return Math.min(380, window.innerWidth - 32) }
// ⭐ 动态测 bubble 真实高度（不用固定值 220）
function getBubbleHeight() {
  const el = bubbleRef.value?.$el || bubbleRef.value
  if (el) {
    const h = el.getBoundingClientRect().height
    if (h > 0) return h + 16   // +16 补偿可能的误差
  }
  return 220  // fallback
}

// ⭐ 手机端简化策略：强制 top/bottom，优先有空间的一侧
const effectiveBubblePos = computed(() => {
  const p = bubblePosition.value
  if (p === 'center') return p
  const vw = window.innerWidth, vh = window.innerHeight
  const isMobile = vw < 640
  if (!isMobile) return p
  const r = highlightRect.value
  if (!r.width || !r.height) return p

  const spaceBelow = vh - r.bottom - 16
  const spaceAbove = r.top - 16
  const bh = getBubbleHeight()

  if (p === 'left' || p === 'right') {
    return spaceBelow >= bh ? 'bottom' : 'top'
  }
  if (p === 'bottom' && spaceBelow < bh) {
    return spaceAbove >= bh ? 'top' : 'bottom'
  }
  if (p === 'top' && spaceAbove < bh) {
    return spaceBelow >= bh ? 'bottom' : 'top'
  }
  return p
})

const bubbleStyle = computed(() => {
  const vw = window.innerWidth, vh = window.innerHeight
  const bw = getBubbleWidth(), bh = getBubbleHeight()

  if (effectiveBubblePos.value === 'center') {
    return {
      top: '50%', left: '50%',
      transform: 'translate(-50%, -50%)',
      maxWidth: `${Math.min(480, vw - 24)}px`,
    }
  }
  const r = highlightRect.value
  if (!r.width || !r.height) {
    return { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }
  }

  const pos = effectiveBubblePos.value
  const gap = 12
  let rawTop, rawLeft

  switch (pos) {
    case 'top':    rawTop = r.top - gap;    rawLeft = r.left + r.width / 2; break
    case 'left':   rawTop = r.top + r.height / 2; rawLeft = r.left - gap; break
    case 'right':  rawTop = r.top + r.height / 2; rawLeft = r.right + gap; break
    default:       rawTop = r.bottom + gap; rawLeft = r.left + r.width / 2; break
  }

  // clamp（与 bubble 位置对应的实际边界）
  let bLeft, bTop
  switch (pos) {
    case 'top':    bLeft = rawLeft - bw / 2; bTop = rawTop - bh; break
    case 'left':   bLeft = rawLeft - bw;     bTop = rawTop - bh / 2; break
    case 'right':  bLeft = rawLeft;          bTop = rawTop - bh / 2; break
    default:       bLeft = rawLeft - bw / 2; bTop = rawTop; break
  }
  bLeft = clamp(bLeft, 8, vw - bw - 8)
  bTop  = clamp(bTop, 8, vh - bh - 8)

  let newLeft, newTop, newTransform
  switch (pos) {
    case 'top':    newTop = bTop + bh;   newLeft = bLeft + bw / 2; newTransform = 'translate(-50%, -100%)'; break
    case 'left':   newTop = bTop + bh / 2; newLeft = bLeft + bw;    newTransform = 'translate(-100%, -50%)'; break
    case 'right':  newTop = bTop + bh / 2; newLeft = bLeft;         newTransform = 'translate(0, -50%)'; break
    default:       newTop = bTop;         newLeft = bLeft + bw / 2; newTransform = 'translate(-50%, 0)'; break
  }

  return {
    top: `${newTop}px`,
    left: `${newLeft}px`,
    transform: newTransform,
    maxWidth: `${bw}px`,
  }
})

const arrowDirection = computed(() => {
  const p = effectiveBubblePos.value
  if (p === 'center') return ''
  return `arrow-${p}`
})

const arrowStyle = computed(() => {
  const p = effectiveBubblePos.value
  const r = highlightRect.value
  if (p === 'center' || !r.width) return {}
  const gap = 4
  const size = 12
  let top, left
  switch (p) {
    case 'top':
      top = r.top - gap
      left = r.left + r.width / 2
      return { top: `${top}px`, left: `${left}px`, width: `${size * 2}px`, height: `${size}px`, transform: 'translate(-50%, -100%)' }
    case 'left':
      top = r.top + r.height / 2
      left = r.left - gap
      return { top: `${top}px`, left: `${left}px`, width: `${size}px`, height: `${size * 2}px`, transform: 'translate(-100%, -50%)' }
    case 'right':
      top = r.top + r.height / 2
      left = r.right + gap
      return { top: `${top}px`, left: `${left}px`, width: `${size}px`, height: `${size * 2}px`, transform: 'translate(0, -50%)' }
    default:
      top = r.bottom + gap
      left = r.left + r.width / 2
      return { top: `${top}px`, left: `${left}px`, width: `${size * 2}px`, height: `${size}px`, transform: 'translate(-50%, 0)' }
  }
})

// ── 方法 ──
// 注：measureTarget 定义在上面（含 scrollIntoView + 延迟 280ms 取 rect）

function next() {
  if (stepIdx.value < steps.value.length - 1) {
    stepIdx.value++
    measureTarget()
  }
}

function prev() {
  if (stepIdx.value > 0) {
    stepIdx.value--
    measureTarget()
  }
}

async function finish() {
  visible.value = false
  // ⭐ 统一写：store + localStorage + 后端（后端持久化，换浏览器也不重弹）
  await userStore.markGuideSeen(storageKey.value)
  console.log(`[Guide] finish → 写标记 ${storageKey.value}（后端 + store + ls）`)
  emit('finish')
}

function onBackdropClick() {
  // 点击遮罩不关闭，强制走引导流程；但可加一个小提示
}

function onCtaClick() {
  const cta = step.value.cta
  if (!cta) return
  emit('cta', cta)
  if (cta.action === 'router' && cta.payload) {
    finish()
    router.push(cta.payload)
  } else if (cta.action === 'finish') {
    finish()
  }
}

// ── 生命周期 ──
function checkAndShow() {
  // ⭐ fullScreen 页（登录/建档）强制不弹引导
  if (route.meta?.fullScreen) {
    console.log('[Guide] checkAndShow → fullScreen 拦截')
    return
  }

  const group = currentGroup.value
  if (!group) {
    console.log('[Guide] checkAndShow → 无引导组', route.path)
    return                              // 当前路由没有引导组
  }
  const key = storageKey.value

  // ⭐ 优先级：后端 store（source of truth） → localStorage（快速缓存）
  const done = userStore.guidesSeen?.[key] || storage.getGlobal(key)
  console.log(`[Guide] checkAndShow → key=${key}, store_done=${!!userStore.guidesSeen?.[key]}, ls_done=${!!storage.getGlobal(key)}, steps=${steps.value?.length}`)
  if (done) return                      // 已完成过（后端或缓存任一有记录）
  if (!steps.value?.length) return

  visible.value = true
  stepIdx.value = 0
  console.log(`[Guide] ✨ 弹出引导 ${key}，共 ${steps.value.length} 步`)
  setTimeout(measureTarget, 300)
}

let _scrollRaf = null
function _onScroll() {
  if (_scrollRaf) return   // 节流：一帧最多一次
  _scrollRaf = requestAnimationFrame(() => {
    _scrollRaf = null
    measureTarget()
  })
}

onMounted(() => {
  // 等 LayoutShell/Dashboard 渲染好
  setTimeout(checkAndShow, 500)

  // ⭐ 手机端关键：orientationchange + passive scroll（避免卡顿）
  window.addEventListener('resize', measureTarget)
  window.addEventListener('orientationchange', measureTarget)
  window.addEventListener('scroll', _onScroll, { passive: true, capture: true })

  // 某些 Android 浏览器地址栏收起/展开会改变 innerHeight
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', measureTarget, { passive: true })
  }
})

// ⭐ 监听路由变化 —— 切换到新的引导组（每组独立 storageKey）
watch(() => route.path, (newPath, oldPath) => {
  console.log(`[Guide] route change: ${oldPath} → ${newPath}`)
  // 路由变了：旧引导组无论走完没走完，都写标记（避免下次重弹）
  // ⭐ 走 store.markGuideSeen → 后端持久化
  if (oldPath) {
    const oldGroup = GUIDE_GROUPS[oldPath]
    const oldKey = oldGroup?.storageKey
    if (oldKey && !userStore.guidesSeen?.[oldKey] && !storage.getGlobal(oldKey)) {
      userStore.markGuideSeen(oldKey)   // async 不 await，不阻塞路由切换
      console.log(`[Guide] 旧路由 ${oldPath} → 写标记 ${oldKey}`)
    }
  }
  // 关旧引导
  visible.value = false

  // ⭐ 特殊：onboarding 建档完跳主页 → 强制弹引导（不管之前有没有标记）
  const freshFromOnboarding = oldPath?.includes('onboarding')

  // 匹配新组
  const newGroup = matchGroup(newPath)
  currentGroup.value = newGroup
  if (newGroup) {
    if (freshFromOnboarding) {
      // 清掉旧标记（store + ls）→ 强制弹
      storage.removeGlobal(newGroup.storageKey)
      if (userStore.guidesSeen?.[newGroup.storageKey]) {
        const { [newGroup.storageKey]: _, ...rest } = userStore.guidesSeen
        userStore.guidesSeen = rest
      }
      console.log(`[Guide] fresh from onboarding → 清 ${newGroup.storageKey}`)
    }
    // 延迟让新页面渲染完 DOM 再 show
    setTimeout(checkAndShow, 1200)   // ⭐ 拉长到 1200ms（让 Dashboard 充分渲染）
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', measureTarget)
  window.removeEventListener('orientationchange', measureTarget)
  window.removeEventListener('scroll', _onScroll, true)
  if (window.visualViewport) {
    window.visualViewport.removeEventListener('resize', measureTarget)
  }
  if (resizeObserver) resizeObserver.disconnect()
})

watch(stepIdx, () => {
  setTimeout(measureTarget, 50)
})

// 暴露给父组件（方便测试 / 手动触发）
defineExpose({ show: () => { visible.value = true; stepIdx.value = 0; setTimeout(measureTarget, 200) } })
</script>

<style scoped>
/* ═══ 半透明遮罩 + 引导高亮 + 气泡 ═══ */
.guide-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  /* ⭐ overlay 容器穿透 —— 只有 bubble 内部拦截点击 */
  pointer-events: none;
  /* ⭐ 手动 opacity 过渡（替代 Vue <transition>，避免浏览器兼容问题） */
  transition: opacity 0.25s ease;
}

/* 遮罩层：完全穿透 */
.guide-mask {
  position: absolute; inset: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(2px);
  pointer-events: none;
}

/* 高亮框：穿透 */
.guide-highlight { pointer-events: none !important; z-index: 2; }

/* 气泡卡片及所有子元素：⭕ 唯一拦截点击的区域 */
.guide-bubble {
  pointer-events: auto !important;
  z-index: 3;
}
.guide-bubble * { pointer-events: auto !important; }  /* ⭐ 强制所有后代都能点 */
.guide-arrow { pointer-events: none !important; z-index: 2; }

/* 高亮"发光框"——用 outline + box-shadow 做洞 */
.guide-highlight {
  position: absolute;
  background: transparent;
  border-radius: 12px;
  outline: 3px solid var(--qn-emerald-accent);
  outline-offset: 4px;
  box-shadow:
    0 0 0 6px rgba(var(--qn-emerald-accent-rgb), 0.25),
    0 0 24px rgba(var(--qn-emerald-accent-rgb), 0.4);
  transition: top 0.25s ease, left 0.25s ease, width 0.25s ease, height 0.25s ease, opacity 0.2s;
  animation: pulse 2s infinite;
  z-index: 2;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 6px rgba(var(--qn-emerald-accent-rgb),0.25), 0 0 24px rgba(var(--qn-emerald-accent-rgb),0.4); }
  50% { box-shadow: 0 0 0 10px rgba(var(--qn-emerald-accent-rgb),0.15), 0 0 32px rgba(var(--qn-emerald-accent-rgb),0.5); }
}

/* 气泡卡片 */
.guide-bubble {
  position: absolute;
  background: var(--qn-banner-card-bg);
  border-radius: 16px;
  padding: 20px 22px 16px;
  max-width: 380px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25), 0 2px 8px rgba(0, 0, 0, 0.12);
  border: 1px solid rgba(var(--qn-emerald-accent-rgb), 0.3);
  z-index: 3;
  animation: bubbleIn 0.3s ease;
}
@keyframes bubbleIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.guide-bubble.center { text-align: center; }

.bubble-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 8px;
}
.bubble-step {
  font-size: 11px; font-weight: 600;
  color: var(--qn-emerald-accent); text-transform: uppercase; letter-spacing: 1px;
}
.bubble-skip {
  background: none; border: none;
  font-size: 14px; color: var(--qn-ink-3);
  cursor: pointer; padding: 2px 6px;
  transition: color 0.15s;
}
.bubble-skip:hover { color: var(--qn-fire); }

.bubble-title {
  font-size: 17px; font-weight: 600;
  color: var(--qn-emerald); margin: 0 0 8px; line-height: 1.4;
}
.bubble-content {
  font-size: 13px; line-height: 1.7;
  color: var(--qn-ink-2); margin: 0 0 14px;
}

.bubble-cta { margin-bottom: 12px; }
.cta-btn {
  width: 100%; padding: 12px 20px;
  background: linear-gradient(135deg, var(--qn-emerald), var(--qn-emerald-light));
  color: #fff; border: none; border-radius: 10px;
  font-size: 14px; font-weight: 500; cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  box-shadow: 0 2px 8px rgba(var(--qn-emerald-rgb),0.3);
}
.cta-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(var(--qn-emerald-rgb),0.4);
}

.bubble-footer {
  display: flex; justify-content: space-between; align-items: center;
  padding-top: 12px;
  border-top: 1px solid #F0EBE0;
}
.bubble-dots { display: flex; gap: 5px; }
.dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #E5E1D6;
  transition: all 0.2s;
}
.dot.active { background: var(--qn-emerald-accent); width: 16px; border-radius: 3px; }
.dot.done { background: var(--qn-emerald); }

.bubble-actions { display: flex; gap: 10px; flex: 1; }
.action-btn {
  padding: 10px 20px; border-radius: 10px;
  font-size: 14px; font-weight: 500;
  border: none; cursor: pointer; transition: all 0.15s;
  min-height: 40px;
  white-space: nowrap;
}
.action-btn.ghost {
  background: transparent; color: #5A6A64;
  border: 1px solid #D5E2DD;
}
.action-btn.ghost:hover { color: var(--qn-emerald); border-color: var(--qn-emerald); }
.action-btn.primary {
  background: linear-gradient(135deg, var(--qn-emerald), var(--qn-emerald-light)); color: #fff;
  box-shadow: 0 2px 8px rgba(var(--qn-emerald-rgb),0.3);
}
.action-btn.primary:hover { background: linear-gradient(135deg, #123F3A, #277060); box-shadow: 0 4px 12px rgba(var(--qn-emerald-rgb),0.4); }

/* 箭头（纯 CSS triangle） */
.guide-arrow {
  position: absolute;
  background: transparent;
  z-index: 2;
}
.guide-arrow::before {
  content: ''; position: absolute;
  background: var(--qn-banner-card-bg); border: 1px solid rgba(var(--qn-emerald-accent-rgb),0.3);
}
/* arrow-top — 在高亮框顶部，指向气泡（气泡在下方） */
.guide-arrow.arrow-top { }
.guide-arrow.arrow-top::before {
  top: -7px; left: 50%; transform: translateX(-50%) rotate(45deg);
  width: 14px; height: 14px;
  border-right: none; border-bottom: none;
}
/* arrow-bottom */
.guide-arrow.arrow-bottom::before {
  bottom: -7px; left: 50%; transform: translateX(-50%) rotate(-135deg);
  width: 14px; height: 14px;
  border-left: none; border-top: none;
}
/* arrow-left */
.guide-arrow.arrow-left::before {
  left: -7px; top: 50%; transform: translateY(-50%) rotate(-45deg);
  width: 14px; height: 14px;
  border-right: none; border-top: none;
}
/* arrow-right */
.guide-arrow.arrow-right::before {
  right: -7px; top: 50%; transform: translateY(-50%) rotate(135deg);
  width: 14px; height: 14px;
  border-left: none; border-bottom: none;
}

/* 过渡 */
/* ⭐ 已改由 .guide-overlay 上的 transition: opacity 处理 —— 不再用 Vue <transition> */

/* 响应式：小屏气泡更紧凑 + 按钮 touch-friendly — 归并到 480px 档位（原 640px） */
@media (max-width: 480px) {
  .guide-bubble {
    max-width: calc(100vw - 24px);
    padding: 14px 16px 12px;
    border-radius: 14px;
    /* ⭐ 底部安全区（统一变量 --safe-bottom：原生桥值 + env 取大） */
    padding-bottom: calc(12px + var(--safe-bottom));
  }
  .bubble-title { font-size: 15px; margin-bottom: 6px; }
  .bubble-content { font-size: 13px; line-height: 1.6; margin-bottom: 10px; }

  /* ⭐ 手机端按钮更大（touch target ≥ 44px） */
  .cta-btn { padding: 14px 18px; font-size: 15px; border-radius: 12px; }
  .action-btn { padding: 10px 18px; font-size: 14px; border-radius: 10px; min-height: 40px; }
  .bubble-skip { font-size: 16px; padding: 4px 10px; }

  .bubble-footer { padding-top: 10px; }
  .wait-hint { font-size: 13px; padding: 8px 14px; }

  /* ⭐ 高亮框在手机上更紧凑 */
  .guide-highlight { border-radius: 10px; }
}

/* ⭐ 老年关怀模式：所有按钮更大 */
html.elder-mode .cta-btn { padding: 16px 24px; font-size: 17px; border-radius: 14px; }
html.elder-mode .action-btn { padding: 12px 22px; font-size: 16px; min-height: 48px; }
html.elder-mode .guide-bubble { padding: 22px 24px 18px; max-width: calc(100vw - 16px); }
html.elder-mode .bubble-title { font-size: 19px; }
html.elder-mode .bubble-content { font-size: 15px; line-height: 1.8; }
html.elder-mode .wait-hint { font-size: 15px; padding: 10px 16px; }

/* 横屏手机：气泡更矮更宽 */
@media (max-height: 420px) and (orientation: landscape) {
  .guide-bubble { padding: 10px 14px 8px; }
  .bubble-title { font-size: 14px; margin-bottom: 4px; }
  .bubble-content { font-size: 12px; line-height: 1.5; margin-bottom: 6px; }
  .bubble-footer { padding-top: 6px; }
}

/* waitForClick 模式下的提示文字 */
.wait-hint {
  font-size: calc(12px * var(--fs-scale, 1));
  font-weight: 600;
  color: var(--qn-fire);
  background: rgba(216, 67, 21, 0.08);
  padding: 6px 12px;
  border-radius: 6px;
  animation: hintPulse 1.6s ease-in-out infinite;
}
@keyframes hintPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
</style>
