/**
 * 字号缩放工具 — 读 CSS 变量 --fs-scale，用于 ECharts 等不走 CSS 的组件
 */

let _cachedScale = null
let _listenersAttached = false

function _readScale() {
  try {
    const v = getComputedStyle(document.documentElement).getPropertyValue('--fs-scale')
    const n = parseFloat(v)
    return isNaN(n) ? 1 : n
  } catch {
    return 1
  }
}

/** 当前全局字号缩放系数 */
export function getFsScale() {
  if (typeof document === 'undefined') return 1
  if (_cachedScale === null) _cachedScale = _readScale()
  return _cachedScale
}

/** 把基准 px 乘以 scale（返回整数，ECharts 要整数） */
export function fs(basePx) {
  return Math.round(basePx * getFsScale())
}

/**
 * 监听 --fs-scale 变化 — 当用户切字体/老年模式时，图表能自动 resize
 * @param {() => void} cb 回调（一般是 chart.setOption / chart.resize）
 */
export function watchFsScale(cb) {
  if (typeof window === 'undefined') return
  // 用 MutationObserver 监听 documentElement attribute 变化（elder-mode class 变了会触发）
  // 或者用 setInterval 轮询（简单但不优雅）— 这里用 polling 因为 scale 变化不频繁
  if (!_listenersAttached) {
    _listenersAttached = true
    setInterval(() => {
      const current = _readScale()
      if (Math.abs(current - _cachedScale) > 0.001) {
        _cachedScale = current
        // 全局广播
        window.dispatchEvent(new CustomEvent('fs-scale-change', { detail: { scale: current } }))
      }
    }, 500)
  }
  window.addEventListener('fs-scale-change', cb)
}
