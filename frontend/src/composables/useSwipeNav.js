/**
 * useSwipeNav — 移动端左右滑动切换 tab 页
 *
 * 极简版：只负责手势判定 + 设置 transition 方向 + router.push
 * 不做 inline transform 跟手（避免跟手和 Vue transition 两套 transform 打架）
 * 动画手感全靠 base.css 的 transition 实现
 *
 * 手势判定：
 *   - touchmove 中 |dy| > |dx| * 0.3 → 纵向滚动，放弃
 *   - touchend 中 |dx| >= 60px 且 |dx| > |dy| → 触发切换
 *   - animating 锁 400ms（> transition 0.35s）
 *   - velocity 检测：快速轻扫即使位移不够也切换
 */
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const THRESHOLD = 60
const VEL_THRESHOLD = 0.35        // px/ms，快速轻扫触发阈值
const VEL_MIN_DX = 30              // 轻扫模式下最小位移
const VERT_RATIO = 0.3
const ANIM_LOCK = 420

export function useSwipeNav({ tabOrder }) {
  const router = useRouter()
  const route = useRoute()
  const direction = ref('')
  let startX = 0, startY = 0, t0 = 0
  let ignore = false
  let animating = false

  function onTouchStart(e) {
    if (animating) return
    const t = e.touches[0]
    startX = t.clientX; startY = t.clientY; t0 = Date.now()
    ignore = false
  }

  function onTouchMove(e) {
    if (ignore || animating) return
    const t = e.touches[0]
    const dx = t.clientX - startX
    const dy = t.clientY - startY
    if (Math.abs(dy) > Math.abs(dx) * (1 / VERT_RATIO)) ignore = true
  }

  function onTouchEnd(e) {
    if (ignore || animating) return
    const t = e.changedTouches[0]
    const dx = t.clientX - startX
    const dy = t.clientY - startY
    const dt = Date.now() - t0
    if (dt === 0) return
    const vel = dx / dt   // px/ms

    if (Math.abs(dx) <= Math.abs(dy)) return              // 纵向为主
    if (!route.meta?.swipeable) return
    const idx = tabOrder.indexOf(route.path)
    if (idx === -1) return

    // 判定：位移够 OR 快速轻扫
    const byDistance = Math.abs(dx) >= THRESHOLD
    const byVelocity = Math.abs(vel) >= VEL_THRESHOLD && Math.abs(dx) >= VEL_MIN_DX
    if (!byDistance && !byVelocity) return

    if (dx < 0 && idx < tabOrder.length - 1) {
      direction.value = 'swipe-left'
      animating = true
      router.push(tabOrder[idx + 1])
      setTimeout(() => { animating = false; direction.value = '' }, ANIM_LOCK)
    } else if (dx > 0 && idx > 0) {
      direction.value = 'swipe-right'
      animating = true
      router.push(tabOrder[idx - 1])
      setTimeout(() => { animating = false; direction.value = '' }, ANIM_LOCK)
    }
  }

  return { onTouchStart, onTouchMove, onTouchEnd, direction }
}
