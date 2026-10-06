import './styles/tokens.css'  // ⚠️ 必须最先引入——唯一设计变量真源（--qn-* + 兼容别名）
import './styles/base.css'    // 全局 reset + 排版 + 原子类

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

// ── Service Worker（PWA）──
// 仅生产环境注册；开发环境必须注销并清缓存，
// 否则 cache-first 会把旧的 JS 模块缓存下来，导致代码更新不生效（手机端尤其明显）
if ('serviceWorker' in navigator) {
  if (import.meta.env.PROD) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {})
    })
  } else {
    navigator.serviceWorker.getRegistrations()
      .then((regs) => regs.forEach((r) => r.unregister()))
      .catch(() => {})
    if (window.caches) {
      caches.keys().then((keys) => keys.forEach((k) => caches.delete(k))).catch(() => {})
    }
  }
}

app.mount('#app')
