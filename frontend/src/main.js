import './styles/tokens.css'  // ⚠️ 必须最先引入——唯一设计变量真源（--qn-* + 兼容别名）
import './styles/base.css'    // 全局 reset + 排版 + 原子类
import 'katex/dist/katex.min.css'  // KaTeX 公式渲染样式（QMarkdown 组件用）

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useUserStore } from './stores/user'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)

// 启动时从 localStorage 恢复登录态
const userStore = useUserStore()
userStore.initFromLocalStorage()

// ── Service Worker：彻底禁用 ──
// Capacitor 远程加载模式下，SW 的 cache-first 会拦截 /assets/* 返回旧缓存
// 导致 rollup hash 未变但内容已更新时，Android 拿到旧 chunk → 白屏
// 无论生产还是开发，一律注销所有 SW + 清缓存
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations()
    .then((regs) => regs.forEach((r) => r.unregister()))
    .catch(() => {})
}
if (window.caches) {
  caches.keys().then((keys) => keys.forEach((k) => caches.delete(k))).catch(() => {})
}

// ── 全局错误边界：把 JS 崩溃渲染到屏幕（Android 上看不到 DevTools）──
window.addEventListener('error', (ev) => {
  _showCrash(`[Error] ${ev.message}\n  at ${ev.filename}:${ev.lineno}:${ev.colno}`)
})
window.addEventListener('unhandledrejection', (ev) => {
  _showCrash(`[Promise] ${ev.reason?.message || ev.reason}`)
})
function _showCrash(msg) {
  const pre = document.createElement('pre')
  pre.style.cssText = 'position:fixed;inset:0;background:#1a1a2e;color:#ff6b6b;padding:16px;z-index:99999;font:12px/1.5 monospace;white-space:pre-wrap;overflow:auto;'
  pre.textContent = '⚠️ 青囊 APP 出错了\n\n' + msg
  document.body?.appendChild(pre) || document.documentElement.appendChild(pre)
}

app.mount('#app')
