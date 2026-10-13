/**
 * 青囊 APP 版本检测 + 更新工具
 * ============================
 * 
 * 版本号信源优先级（从高到低）：
 *   1. 原生模式：@capacitor/app 的 App.getInfo().version（直接读 APK 的 AndroidManifest）
 *      → build.gradle 是 APK 唯一信源，最靠谱
 *   2. Web/开发模式：VITE_APP_VERSION（vite.config.js 从 build.gradle 同步读取注入）
 *      → 同一条链，和 APK 保持一致
 * 
 * HTTP 客户端：统一用 import { api } from '../api/client'
 *   → 和项目其他所有 API 调用走同一个 baseURL / token / 拦截器
 *   → 绝对不会出现手机上打 localhost 的情况
 * 
 * 工作流程：
 *   1. App.vue / SettingsView 在 onMounted 调 checkForUpdate()
 *   2. 后端 /api/v1/version/app-update 返回 { has_update, latest_version, update_url, ... }
 *   3. has_update=true → 弹 UpdateDialog（App.vue 全局挂载）
 *   4. 用户确认 → downloadAndInstall() → window.location.href 下载 APK
 */

import { api } from '../api/client'

// ── 获取当前 APP 版本号 ──
// 原生环境：读 APK 内部的 AndroidManifest（build.gradle versionName 写入）
// Web 环境：读 Vite 注入的 VITE_APP_VERSION
let _cachedVersion = null

export async function getAppVersion() {
  if (_cachedVersion) return _cachedVersion

  // 1. 原生模式：读 @capacitor/app
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
      console.warn('[AppUpdater] 原生版本读取失败，回退到 VITE_APP_VERSION:', e?.message)
    }
  }

  // 2. Vite 注入版本（vite.config.js 从 build.gradle 读取 → 单一信源）
  _cachedVersion = (typeof VITE_APP_VERSION !== 'undefined')
    ? String(VITE_APP_VERSION)
    : (typeof import !== 'undefined' && import.meta?.env?.VITE_APP_VERSION)
      ? String(import.meta.env.VITE_APP_VERSION)
      : '0.1.0'  // 极端兜底（不会出现）

  console.log('[AppUpdater] Vite 版本号:', _cachedVersion)
  return _cachedVersion
}

// ── 同步获取版本（不依赖 Promise）──
// 用于同步上下文（SettingsView 的 groups 配置里），会先跑一次异步 getAppVersion 缓存
function _syncVersion() {
  if (_cachedVersion) return _cachedVersion
  if (typeof VITE_APP_VERSION !== 'undefined') {
    _cachedVersion = String(VITE_APP_VERSION)
  }
  return _cachedVersion || '0.1.0'
}

// 导出常量（同步值，SettingsView 里用）
// 首次 import 时 Vite define 已经替换好，这个值就是最终值
export const APP_VERSION = (typeof VITE_APP_VERSION !== 'undefined')
  ? String(VITE_APP_VERSION)
  : '0.1.0'

// ── 平台检测 ──
function _detectPlatform() {
  const ua = navigator.userAgent.toLowerCase()
  if (/android/i.test(ua)) return 'android'
  if (/iphone|ipad|ipod/i.test(ua)) return 'ios'
  return 'web'
}

// ── 检查是否有新版本 ──
/**
 * @returns {Promise<{has_update: boolean, latest_version: string, current_version: string, force_update: boolean, update_url?: string, checksum_sha256?: string, size_bytes?: number, update_note?: string, min_required_version?: string, disabled?: boolean}>}
 */
export async function checkForUpdate() {
  try {
    const version = await getAppVersion()
    const platform = _detectPlatform()
    const { data } = await api.get('/api/v1/version/app-update', {
      params: { version, platform },
      timeout: 10000,
    })
    // FastAPI 响应封装：{ data: {...}, code: 0, ... } 或直接 {...}
    const info = data?.data ?? data
    console.log('[AppUpdater] 版本检查结果:', {
      current: version,
      latest: info?.latest_version,
      has_update: info?.has_update,
      platform,
      disabled: info?.disabled,
    })
    return { ...info, current_version: version }
  } catch (err) {
    console.warn('[AppUpdater] 版本检查失败（后端可能未启动）:', err?.message)
    const fallbackVer = _syncVersion()
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
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function downloadAndInstall(info) {
  if (!info?.update_url) {
    return { success: false, error: '缺少下载 URL' }
  }

  try {
    // Android WebView：window.location.href = APK URL 最可靠
    // Android DownloadManager 会接管 .apk 下载，完成后自动弹 Intent 让用户安装
    // @capacitor-community/app-updater 需要额外安装且桥接复杂，这里不用
    console.log('[AppUpdater] 触发 APK 下载:', info.update_url)
    window.location.href = info.update_url
    return { success: true }
  } catch (err) {
    console.error('[AppUpdater] 下载触发失败:', err)
    return { success: false, error: err?.message || '下载触发失败' }
  }
}

// ── 主动式更新检查（完整流程）──
/**
 * @param {Object} options
 * @param {boolean} options.silent 静默模式：无更新时不 log 也不返回（默认 false）
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
