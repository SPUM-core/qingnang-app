/**
 * 青囊 APP 版本检测 + 更新工具
 * ============================
 * 
 * 版本号信源：
 *   1. 原生模式：@capacitor/app 的 App.getInfo().version（直接读 APK 的 AndroidManifest）
 *      → build.gradle 是 APK 唯一信源
 *   2. Web/Vite 模式：import.meta.env.VITE_APP_VERSION
 *      → vite.config.js 从 build.gradle 读 versionName 注入
 * 
 * HTTP 客户端：统一用 import { api } from '../api/client'
 *   → 和项目所有 API 调用走同一个 baseURL / token / 拦截器
 *   → 手机上绝对不会打 localhost
 * 
 * 工作流程：
 *   1. App.vue onMounted → 全局静默 runUpdateCheck()
 *   2. 有更新 → 弹 App.vue 的 UpdateDialog（全局唯一）
 *   3. SettingsView 手动点"检查更新" → 走同一个 checkForUpdate()
 *      → 只更新底部 badge 状态，不弹自己的 modal
 */

import { api } from '../api/client'

// ── 同步版本号（Vite 构建时直接注入 "0.1.5" 字符串）──
// import.meta.env.VITE_APP_VERSION 在 vite define 里被替换为 JSON 字符串字面量
// 这是同步可获取的，不需要 Promise
export const APP_VERSION = String(import.meta.env.VITE_APP_VERSION || '0.1.0')

// ── 异步获取真实版本（原生模式下读 AndroidManifest）──
// 优先从 APK 内部读（最靠谱 —— 就是用户手里装的那个版本）
// 读不到时回退到 Vite 注入值
let _cachedVersion = null

export async function getAppVersion() {
  if (_cachedVersion) return _cachedVersion

  // 原生模式：读 @capacitor/app
  if (typeof Capacitor !== 'undefined') {
    try {
      const { App } = await import('@capacitor/app')
      const info = await App.getInfo()
      if (info?.version) {
        _cachedVersion = String(info.version)
        console.log('[AppUpdater] 原生版本号:', _cachedVersion, '(from AndroidManifest)')
        return _cachedVersion
      }
    } catch (e) {
      console.warn('[AppUpdater] 原生版本读取失败，回退到 Vite:', e?.message)
    }
  }

  // Web/Vite 模式：用注入值
  _cachedVersion = APP_VERSION
  console.log('[AppUpdater] Vite 版本号:', _cachedVersion)
  return _cachedVersion
}

// ── 平台检测 ──
function _detectPlatform() {
  const ua = navigator.userAgent.toLowerCase()
  if (/android/i.test(ua)) return 'android'
  if (/iphone|ipad|ipod/i.test(ua)) return 'ios'
  return 'web'
}

// ── 检查是否有新版本 ──
/**
 * @returns {Promise<{has_update, latest_version, current_version, force_update, update_url?, checksum_sha256?, size_bytes?, update_note?, min_required_version?, disabled?}>}
 */
export async function checkForUpdate() {
  try {
    const version = await getAppVersion()
    const platform = _detectPlatform()
    const { data } = await api.get('/api/v1/version/app-update', {
      params: { version, platform },
      timeout: 10000,
    })
    // FastAPI 响应可能封装 { data: {...} } 或直接 {...}
    const info = data?.data ?? data
    console.log('[AppUpdater] 版本检查:', {
      current: version,
      latest: info?.latest_version,
      has_update: info?.has_update,
      platform,
    })
    return { ...info, current_version: version }
  } catch (err) {
    console.warn('[AppUpdater] 版本检查失败:', err?.message)
    const fallbackVer = _cachedVersion || APP_VERSION
    return {
      has_update: false,
      current_version: fallbackVer,
      latest_version: fallbackVer,
      disabled: true,
    }
  }
}

// ── 下载并安装 APK ──
/**
 * @param {{update_url: string}} info
 */
export async function downloadAndInstall(info) {
  if (!info?.update_url) return { success: false, error: '缺少下载 URL' }
  try {
    // Android WebView：window.location.href = APK URL 最可靠
    // Android DownloadManager 接管下载 → 完成后自动弹 Intent 安装
    console.log('[AppUpdater] 触发 APK 下载:', info.update_url)
    window.location.href = info.update_url
    return { success: true }
  } catch (err) {
    return { success: false, error: err?.message || '下载触发失败' }
  }
}

// ── 主动式更新检查（完整流程）──
/**
 * @param {{silent?: boolean}} options
 * @returns {Promise<{action: 'none'|'show_update'|'show_force_update', info?: Object}>}
 */
export async function runUpdateCheck(options = {}) {
  const { silent = false } = options
  const info = await checkForUpdate()

  if (!info.has_update) {
    if (!silent) console.log('[AppUpdater] 当前已是最新版本 v' + info.current_version)
    return { action: 'none' }
  }

  return {
    action: info.force_update ? 'show_force_update' : 'show_update',
    info,
  }
}

export default { checkForUpdate, downloadAndInstall, runUpdateCheck, getAppVersion, APP_VERSION }
