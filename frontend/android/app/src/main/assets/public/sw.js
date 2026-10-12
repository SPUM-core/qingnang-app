/**
 * 青囊 PWA Service Worker
 * 策略：
 *   - 导航请求 / 非指纹化资源（HTML、开发模块）→ 网络优先，保证代码永远最新
 *   - 指纹化静态资源（/assets/*，带内容哈希）→ 缓存优先，秒开
 *   - 后端 API（/api/*）→ 永不缓存
 *   - 跨域资源 → 网络优先 + 缓存兜底
 */

const VERSION = 'qn-v1.1.0'
const STATIC_CACHE = `static-${VERSION}`
const RUNTIME_CACHE = `runtime-${VERSION}`

// ── 预缓存：核心资源 ──
const PRECACHE_URLS = ['/', '/index.html', '/manifest.webmanifest']

// ── 安装 ──
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  )
})

// ── 激活：清理旧版本缓存（只删本应用的，且版本不同的）──
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => (k.startsWith('static-') || k.startsWith('runtime-')) && !k.endsWith(VERSION))
            .map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  )
})

// 需要绕过 SW 的路径（后端接口）
const bypass = (p) =>
  p.startsWith('/api/') ||
  p.startsWith('/health') ||
  p.startsWith('/docs') ||
  p.startsWith('/redoc') ||
  p.startsWith('/openapi.json')

const putRuntime = (req, resp) => {
  if (resp && resp.ok) {
    const clone = resp.clone()
    caches.open(RUNTIME_CACHE).then((c) => c.put(req, clone))
  }
  return resp
}

// ── 请求拦截 ──
self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return

  const url = new URL(req.url)
  if (bypass(url.pathname)) return

  // 🌐 跨域资源 → 网络优先 + 缓存兜底
  if (url.origin !== self.location.origin) {
    event.respondWith(
      fetch(req).then((resp) => putRuntime(req, resp)).catch(() => caches.match(req))
    )
    return
  }

  // 🔄 导航 / 非指纹化资源 → 网络优先（保证每次拿到最新 HTML 与代码）
  const isHashedAsset = url.pathname.startsWith('/assets/')
  if (req.mode === 'navigate' || !isHashedAsset) {
    event.respondWith(
      fetch(req)
        .then((resp) => putRuntime(req, resp))
        .catch(() =>
          caches.match(req).then(
            (c) => c || (req.mode === 'navigate' ? caches.match('/index.html') : new Response('离线状态 · 请检查网络', { status: 503 }))
          )
        )
    )
    return
  }

  // 📦 指纹化静态资源 → 缓存优先（内容哈希，可安全长期缓存）
  event.respondWith(
    caches.match(req).then(
      (cached) =>
        cached ||
        fetch(req).then((resp) => putRuntime(req, resp))
    )
  )
})

// ── 支持手动更新 ──
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting()
})
