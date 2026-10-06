/* ═══════════════════════════════════════════════════════════════
   src/utils/chartTheme.js —— echarts 主题色跟随 CSS 变量
   
   为什么需要这个？
   echarts 配置里的颜色必须是字面量（#hex / rgb / rgba），
   不能直接写 CSS 变量字符串 'var(--qn-xxx)'。
   这里用 getComputedStyle 实时取 DOM 上解析后的变量值。
   
   用法：
     import { chartPalette, watchThemeChange } from '@/utils/chartTheme'
     const colors = chartPalette()   // { primary, text, line, wuxing: [...] }
     watchThemeChange(() => render())  // 主题/字号变了 → 重新 render
   
   注意：主题切换会触发 render，但 echarts canvas 不会自动更新，
   必须手动调 chart.setOption / render。
   ═══════════════════════════════════════════════════════════════ */

/**
 * 从 :root 取 CSS 变量的解析值
 * @param {string} name - 变量名，如 '--qn-emerald'
 * @returns {string} 解析后的值，如 '#17534C' 或 '23, 83, 76'
 */
function cssVar(name) {
  if (typeof getComputedStyle === 'undefined') return ''
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

/**
 * 取 rgba 格式（用 --xxx-rgb 的 RGB 分量 + 自定义 alpha）
 * @param {string} rgbVar - 变量名，如 '--qn-emerald-rgb'
 * @param {number} alpha - 0~1
 * @returns {string} 'rgba(r, g, b, a)'
 */
function cssRgba(rgbVar, alpha) {
  const rgb = cssVar(rgbVar)
  if (!rgb) return ''
  return `rgba(${rgb}, ${alpha})`
}

/**
 * 返回 echarts 可用的完整配色表
 * @returns {Object}
 */
export function chartPalette() {
  return {
    // 品牌主色
    primary: cssVar('--qn-emerald'),
    primaryLight: cssVar('--qn-emerald-light'),
    primaryAccent: cssVar('--qn-emerald-accent'),
    cinnabar: cssVar('--qn-cinnabar'),
    cinnabarSoft: cssVar('--qn-cinnabar-soft'),

    // 五形语义色
    wuxing: [
      cssVar('--qn-wood'),   // 木
      cssVar('--qn-fire'),   // 火
      cssVar('--qn-earth'),  // 土
      cssVar('--qn-metal'),  // 金
      cssVar('--qn-water'),  // 水
    ],
    wood:  cssVar('--qn-wood'),
    fire:  cssVar('--qn-fire'),
    earth: cssVar('--qn-earth'),
    metal: cssVar('--qn-metal'),
    water: cssVar('--qn-water'),

    // 中性色（跟随明暗主题）
    gridLine: cssVar('--qn-line'),     // 网格线
    axisText: cssVar('--qn-ink-3'),    // 轴文字
    text: cssVar('--qn-ink-2'),         // 图例/标签文字
    textPrimary: cssVar('--qn-ink'),    // 主要文字
    bgSurface: cssVar('--qn-surface'),  // 卡片底（tooltip 用）

    // 通用白（borderColor / 对比色）——不跟随暗色
    white: '#fff',
    whiteSoft: 'rgba(255,255,255,0.2)',

    // rgba 便捷方法
    rgba: cssRgba,
  }
}

/**
 * 监听主题 / 字号 / 老年模式变化，触发 echarts 重建
 * @param {() => void} cb - 重建回调（通常是 render()）
 * @returns {() => void} 取消监听
 */
export function watchThemeChange(cb) {
  if (typeof MutationObserver === 'undefined') return () => {}

  const mo = new MutationObserver(cb)
  mo.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme', 'data-font', 'class'],
  })

  // 字号 scale 也可能在无 mutation 时变化（user settings persist 后）
  // 用定时兜底——节流到 500ms 内不重复触发
  let pending = null
  const handle = () => {
    if (pending) return
    pending = setTimeout(() => {
      pending = null
      cb()
    }, 100)
  }

  mo.addEventListener?.('mutations', handle)  // 标准接口
  const interval = setInterval(() => {
    // 检测 theme / font / elder-mode 是否变了
    const theme = document.documentElement.getAttribute('data-theme')
    const font = document.documentElement.getAttribute('data-font')
    const elder = document.documentElement.classList.contains('elder-mode')
    const cached = watchThemeChange._cache || {}
    if (theme !== cached.theme || font !== cached.font || elder !== cached.elder) {
      watchThemeChange._cache = { theme, font, elder }
      cb()
    }
  }, 500)

  return () => {
    mo.disconnect()
    clearInterval(interval)
  }
}
