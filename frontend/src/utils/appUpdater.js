/**
 * 青囊 APP 自动更新工具
 * ====================
 * 
 * 工作原理：
 * 1. APP 启动时调用 checkForUpdate() → 请求后端 /api/v1/version/app-update
 * 2. 后端返回 { has_update, latest_version, update_url, checksum_sha256, force_update, update_note }
 * 3. has_update=true → 弹出对话框提示用户升级（force_update=true 时不可跳过）
 * 4. 用户确认后 → downloadAndInstall() → 下载 APK → 校验 SHA256 → 触发系统 Intent 安装
 * 
 * 依赖：@capacitor-community/app-updater
 * 安装：npm install @capacitor-community/app-updater
 *       npx cap sync android
 * 
 * Fallback：如果插件未安装（web 环境 / 开发模式），会退化为 window.open(update_url)
 */

import axios from 'axios'

// ── 当前 APP 版本（从 package.json / 构建时注入） ──
// VITE_APP_VERSION 在 vite.config.js 的 define 里注入，capacitor.config.json version 字段也可以读
// 开发期回退值
const APP_VERSION = (typeof VITE_APP_VERSION !== 'undefined')
  ? VITE_APP_VERSION
  : '0.1.0'

// ── API 基础 URL ──
const API_BASE = (typeof VITE_API_BASE !== 'undefined')
  ? VITE_API_BASE
  : 'http://localhost:8767'

// ── 是否运行在原生 APP 环境 ──
function isNative() {
  return typeof Capacitor !== 'undefined'
}

/**
 * 检查是否有新版本
 * @returns {Promise<{has_update, latest_version, current_version, force_update, update_url, checksum_sha256, size_bytes, update_note, disabled}>}
 */
export async function checkForUpdate() {
  try {
    const url = `${API_BASE}/api/v1/version/app-update`
    const { data } = await axios.get(url, {
      params: { version: APP_VERSION, platform: 'android' },
      timeout: 10000,
    })
    console.log('[AppUpdater] 版本检查结果:', data)
    return data
  } catch (err) {
    console.warn('[AppUpdater] 版本检查失败（后端可能未启动）:', err?.message)
    return { has_update: false, current_version: APP_VERSION, latest_version: APP_VERSION, disabled: true }
  }
}

/**
 * 下载并安装 APK
 * @param {{update_url: string, checksum_sha256?: string}} info
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function downloadAndInstall(info) {
  if (!info?.update_url) {
    return { success: false, error: '缺少下载 URL' }
  }

  // 原生环境：直接调用 Capacitor AppUpdater 插件（通过 window.Capacitor.Plugins 桥接）
  // ⚠️ 不在顶层 import @capacitor-community/app-updater —— 包未 install 时 Vite 预构建会崩
  if (isNative()) {
    try {
      const AppUpdater = window.Capacitor?.Plugins?.AppUpdater
      if (!AppUpdater) {
        throw new Error('AppUpdater 插件未注册（npm i @capacitor-community/app-updater && npx cap sync android）')
      }

      // 先下载
      const downloadResult = await AppUpdater.download({
        url: info.update_url,
        sha256: info.checksum_sha256,
      })
      console.log('[AppUpdater] 下载完成:', downloadResult)

      // 安装
      await AppUpdater.install()
      return { success: true }
    } catch (err) {
      console.error('[AppUpdater] 原生更新失败:', err)
      
      // Fallback：打开浏览器手动下载
      console.warn('[AppUpdater] 回退到浏览器下载...')
      window.open(info.update_url, '_blank')
      return { success: false, error: err?.message || '原生更新失败' }
    }
  }

  // Web 环境：直接打开下载 URL
  console.log('[AppUpdater] Web 环境，在浏览器中打开下载 URL')
  window.open(info.update_url, '_blank')
  return { success: true }
}

/**
 * 主动式更新检查（完整流程）
 * 1. 查版本
 * 2. 如果有更新 → 返回更新信息（UI 层决定要不要弹对话框）
 * 3. force_update=true 时必须升级
 * 
 * @param {Object} options
 * @param {boolean} options.silent 静默模式：无更新时不 log 也不返回（默认 false）
 * @returns {Promise<{action: 'none'|'show_update'|'show_force_update', info?: Object}>}
 */
export async function runUpdateCheck(options = {}) {
  const { silent = false } = options
  const info = await checkForUpdate()

  if (!info.has_update) {
    if (!silent) console.log('[AppUpdater] 当前已是最新版本')
    return { action: 'none' }
  }

  return {
    action: info.force_update ? 'show_force_update' : 'show_update',
    info,
  }
}

export { APP_VERSION }
