<!-- ═══════════════════════════════════════════════════════════
  PullRefreshBar.vue — 下拉刷新指示器 + 手势（Dashboard M1）
  自管理手势状态。refreshFn prop 是 async 函数，onPullEnd 里真 await 它。
  外层 touch 事件也在此组件上，使用时包裹最外层页面。

  用法: 组件包裹页面内容即可
══════════════════════════════════════════════════════════════ -->
<template>
  <div class="pull-refresh-wrap"
       @touchstart="onPullStart"
       @touchmove="onPullMove"
       @touchend="onPullEnd">
    <!-- ══ 下拉刷新指示器 ══ -->
    <div class="pull-refresh"
         :style="{ height: _pullDistance + 'px', opacity: _pullDistance > 0 ? 1 : 0 }">
      <template v-if="!_refreshing">
        <div class="pr-arrow" :class="{ spin: _pullDistance > PULL_THRESHOLD }">↓</div>
      </template>
      <template v-else>
        <div class="pr-loader">
          <div class="pr-ring pr-ring-outer"></div>
          <div class="pr-ring pr-ring-inner"></div>
          <div class="pr-dots">
            <span></span><span></span><span></span>
          </div>
        </div>
      </template>
      <span class="pr-text">
        {{ _refreshing ? '青囊正在更新…' : (_pullDistance > PULL_THRESHOLD ? '释放刷新' : '下拉刷新') }}
      </span>
    </div>

    <!-- 插槽：页面内容 -->
    <slot />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const PULL_THRESHOLD = 80
const PULL_MAX = 140
const PULL_BACK_DAMPING = 0.5
const REFRESH_TIMEOUT_MS = 10000   // 10s 兜底，避免 refreshFn 永不返回

const props = defineProps({
  /**
   * 装配层传入的 async 刷新函数（如 _lightRefresh）。
   * onPullEnd 里真 await 它，loading spinner 持续到函数返回。
   */
  refreshFn: { type: Function, default: null },
})

const emit = defineEmits(['refresh'])  // 事件通知（可用于日志/埋点）

// 内部手势状态
const _pullDistance = ref(0)
const _internalRefreshing = ref(false)
let _pullStartY = 0
let _pullActive = false

const _refreshing = computed(() => _internalRefreshing.value)

function onPullStart(e) {
  if (_internalRefreshing.value) return
  if ((window.scrollY || document.documentElement.scrollTop) > 0) return
  _pullStartY = e.touches[0].clientY
  _pullActive = true
}

function onPullMove(e) {
  if (!_pullActive || _internalRefreshing.value) return
  const dy = e.touches[0].clientY - _pullStartY
  if (dy > 0) {
    _pullDistance.value = Math.min(PULL_MAX, dy * PULL_BACK_DAMPING)
    if (e.cancelable) e.preventDefault()
  } else {
    _pullDistance.value = 0
  }
}

async function onPullEnd() {
  if (!_pullActive) return
  _pullActive = false

  if (_pullDistance.value >= PULL_THRESHOLD && !_internalRefreshing.value) {
    _internalRefreshing.value = true
    _pullDistance.value = 60
    try {
      emit('refresh')
      // ✅ 真 await 装配层的刷新函数（带 10s 兜底）
      if (props.refreshFn) {
        await Promise.race([
          Promise.resolve(props.refreshFn()),
          new Promise(resolve => setTimeout(resolve, REFRESH_TIMEOUT_MS)),
        ])
      }
    } catch (err) {
      // 刷新失败也不要卡死——吞掉错误（装配层自己处理 toast）
      console.warn('[PullRefreshBar] refreshFn error:', err)
    } finally {
      _internalRefreshing.value = false
      _pullDistance.value = 0
    }
  } else {
    _pullDistance.value = 0
  }
}
</script>

<style scoped>
.pull-refresh-wrap { width: 100%; min-height: 100%; }
.pull-refresh {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 0; overflow: hidden; transition: height 0.2s cubic-bezier(.4,0,.2,1);
  background: #F1F5F2; border-bottom: 1px solid #DFE8E4;
}
.pr-arrow { font-size: 24px; color: var(--qn-emerald); transition: transform 0.2s; }
.pr-arrow.spin { transform: rotate(180deg); }
.pr-text { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-top: 4px; }
.pr-loader { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.pr-ring { width: 28px; height: 28px; border: 2px solid transparent; border-radius: 50%; animation: pr-spin 1s linear infinite; }
.pr-ring-outer { border-top-color: var(--qn-emerald); border-left-color: var(--qn-emerald); }
.pr-ring-inner { width: 18px; height: 18px; border-bottom-color: var(--qn-cinnabar); border-right-color: var(--qn-cinnabar); animation-duration: 0.7s; animation-direction: reverse; }
@keyframes pr-spin { to { transform: rotate(360deg); } }
.pr-dots { display: flex; gap: 4px; }
.pr-dots span {
  width: 5px; height: 5px; border-radius: 50%; background: var(--qn-emerald);
  animation: pr-bounce 0.6s ease-in-out infinite;
}
.pr-dots span:nth-child(2) { animation-delay: 0.15s; }
.pr-dots span:nth-child(3) { animation-delay: 0.3s; }
@keyframes pr-bounce { 0%, 100% { transform: translateY(0); opacity: 0.4; } 50% { transform: translateY(-4px); opacity: 1; } }
</style>
