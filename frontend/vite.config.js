import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'

// ═══════════════════════════════════════════════════════════════
// 版本号单信源：frontend/android/app/build.gradle
// ───────────────────────────────────────────────────────────────
// 为什么从 build.gradle 读而不是 version.json？
//   APK 内嵌时 Android 系统认的是 build.gradle 的 versionName ——
//   这个值写入 AndroidManifest.xml，Google Play / 系统安装都看它。
//   如果 version.json 和 build.gradle 不同步 → JS 里版本号 ≠ APK 实际版本号
//   → 后端永远返回 has_update=true → 无限推更新。
// 
// version.json 保留在项目根目录（release.py 会同步更新它），但 Vite 注入
// 的值永远来自 build.gradle —— 确保 APP_VERSION 和 APK 内部版本严格一致。
// ═══════════════════════════════════════════════════════════════
function readAppVersion() {
  // 1. 优先：从 build.gradle 解析 versionName
  try {
    // vite cwd = frontend/，../android/app/build.gradle
    const gradlePath = fileURLToPath(new URL('./android/app/build.gradle', import.meta.url))
    const content = readFileSync(gradlePath, 'utf-8')
    const m = content.match(/versionName\s+["'](\d+\.\d+\.\d+)["']/)
    if (m) {
      console.log('[vite] 版本号来自 build.gradle:', m[1])
      return m[1]
    }
  } catch (e) {
    console.warn('[vite] 读取 build.gradle 失败，尝试 version.json:', e?.message)
  }

  // 2. 回退：version.json（根目录）
  try {
    const vj = JSON.parse(readFileSync(fileURLToPath(new URL('../version.json', import.meta.url)), 'utf-8'))
    if (vj?.version) {
      console.log('[vite] 版本号来自 version.json:', vj.version)
      return String(vj.version)
    }
  } catch (e) { /* 回退 */ }

  // 3. 终极回退：package.json
  try {
    const pkg = JSON.parse(readFileSync('./package.json', 'utf-8'))
    console.log('[vite] 版本号来自 package.json:', pkg.version)
    return pkg.version
  } catch {
    return '0.1.0'
  }
}

// ── API 地址：优先 .env.production 的 VITE_API_BASE（手机端指向服务器），本地 dev 回退 localhost ──
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiBase = env.VITE_API_BASE || 'http://localhost:8767'
  const appVersion = readAppVersion()

  return {
    plugins: [vue()],
    define: {
      // ⭐ 所有前端版本号注入点，全部来自 build.gradle
      'import.meta.env.VITE_APP_VERSION': JSON.stringify(appVersion),
      VITE_APP_VERSION: JSON.stringify(appVersion),
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
