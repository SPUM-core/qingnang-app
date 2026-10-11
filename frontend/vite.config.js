import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'

// ── 版本号单一信源：根目录 version.json ──
// 读不到时回退 package.json（防构建崩溃）；vite 以 frontend/ 为 cwd，../ 即项目根目录
function readAppVersion() {
  try {
    const vj = JSON.parse(readFileSync(fileURLToPath(new URL('../version.json', import.meta.url)), 'utf-8'))
    if (vj?.version) return String(vj.version)
  } catch (e) { /* 回退 */ }
  const pkg = JSON.parse(readFileSync('./package.json', 'utf-8'))
  return pkg.version
}

// ── API 地址：优先 .env.production 的 VITE_API_BASE（手机端指向服务器），本地 dev 回退 localhost ──
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiBase = env.VITE_API_BASE || 'http://localhost:8767'

  return {
    plugins: [vue()],
    define: {
      // 让前端代码可以用 import.meta.env.VITE_APP_VERSION 或全局变量 VITE_APP_VERSION
      'import.meta.env.VITE_APP_VERSION': JSON.stringify(readAppVersion()),
      VITE_APP_VERSION: JSON.stringify(readAppVersion()),
      'import.meta.env.VITE_API_BASE': JSON.stringify(apiBase),
      VITE_API_BASE: JSON.stringify(apiBase),
    },
    server: {
      host: '0.0.0.0',   // ← 允许同局域网手机访问
      port: 5173,
      proxy: {
        '/api': { target: 'http://localhost:8767', changeOrigin: true },
        '/health': { target: 'http://localhost:8767', changeOrigin: true },
        '/docs': { target: 'http://localhost:8767', changeOrigin: true },
        '/redoc': { target: 'http://localhost:8767', changeOrigin: true },
        '/openapi.json': { target: 'http://localhost:8767', changeOrigin: true },
        '/updates': { target: 'http://localhost:8767', changeOrigin: true },
      }
    }
  }
})
