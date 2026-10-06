/**
 * ═══════════════════════════════════════════════════════════════════════════
 * 青囊统一存储层 · storage.js
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * 设计原则：
 *  1. ❌ 业务代码不再直接调 localStorage — 全走此模块
 *  2. 🔐 业务 key 自动按 userId 命名空间隔离  qn:{userId}:{subKey}
 *  3. 🌐 全局 key（鉴权/FAB位置）跨账号共享 — 登出时单独清理
 *  4. 🔄 首次部署自动迁移旧版全局 key 到新 scope 下
 *
 * ═══════════════════════════════════════════════════════════════════════════
 */

// ───── 全局 key 白名单（跨账号共享 / 鉴权前就要读） ─────
const GLOBAL_KEYS = new Set([
  'qn_token',           // JWT token（router guard 在 login 前就要读）
  'qingnang_onboarded', // 建档标记（router guard 配对 token）
  'qingnang-fab-pos',   // FAB 悬浮球位置（纯 UI 偏好，跨账号共享）
])

// ───── 用户 scope 前缀 ─────
const SCOPE_PREFIX = 'qn:'   // 实际拼成 qn:{userId}:{subKey}

// ───── 旧版全局业务 key 清单（迁移用） ─────
const LEGACY_BIZ_KEYS = [
  'qn_user', 'qingnang_settings', 'qingnang_today', 'qingnang_archive',
  'qingnang_feedbacks', 'qingnang_chief_complaint', 'qingnang-latest-signals',
  'qingnang_user', 'qn_body_photo', 'qn_voice_sample',
]

// ───── 运行时 state（不在 localStorage，存在内存） ─────
let _userId = null      // 当前用户 qingnang_id（如 'SPUM-TCM-CASE-001'）

// ═══════════════════════════════════════════════════════════════════════════
//  命名空间管理
// ═══════════════════════════════════════════════════════════════════════════

/** 登录成功后调：激活用户命名空间 */
export function setUserScope(qingnangId) {
  _userId = qingnangId
}

/** 获取当前 scope userId（仅供内部检查用） */
export function getUserScope() {
  return _userId
}

/** 登出时调：清空该用户 scope 下所有数据 + 清全局 auth key */
export function clearUserScope(userId = _userId) {
  // 1. 清全局 auth key（token / onboarded）
  localStorage.removeItem('qn_token')
  localStorage.removeItem('qingnang_onboarded')
  // 2. 清指定 scope 下全部 key
  if (userId) {
    const prefix = `${SCOPE_PREFIX}${userId}:`
    const toRemove = []
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (k && k.startsWith(prefix)) toRemove.push(k)
    }
    toRemove.forEach(k => localStorage.removeItem(k))
  }
  _userId = null
}

// ═══════════════════════════════════════════════════════════════════════════
//  用户 scope key（自动命名空间）
// ═══════════════════════════════════════════════════════════════════════════

function _scopedKey(subKey) {
  if (!_userId) {
    console.warn('[storage] 未设置用户 scope，key 将写入全局！请先调 setUserScope()')
    return subKey   // fallback 到原样（避免 crash）
  }
  return `${SCOPE_PREFIX}${_userId}:${subKey}`
}

export function get(subKey, defaultValue = null) {
  try {
    const raw = localStorage.getItem(_scopedKey(subKey))
    if (raw === null) return defaultValue
    return JSON.parse(raw)
  } catch { return defaultValue }
}

export function set(subKey, value) {
  try { localStorage.setItem(_scopedKey(subKey), JSON.stringify(value)) }
  catch (e) { console.warn('[storage] set failed:', subKey, e) }
}

export function remove(subKey) {
  localStorage.removeItem(_scopedKey(subKey))
}

// ═══════════════════════════════════════════════════════════════════════════
//  全局 key（跨账号共享，直接用完整 key）
// ═══════════════════════════════════════════════════════════════════════════

export function getGlobal(key, defaultValue = null) {
  try {
    const raw = localStorage.getItem(key)
    if (raw === null) return defaultValue
    return JSON.parse(raw)
  } catch { return defaultValue }
}

export function setGlobal(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)) }
  catch (e) { console.warn('[storage] setGlobal failed:', key, e) }
}

export function removeGlobal(key) {
  localStorage.removeItem(key)
}

// ═══════════════════════════════════════════════════════════════════════════
//  特殊：token / onboarded 用全局 key 但存的是纯字符串（非 JSON）
// ═══════════════════════════════════════════════════════════════════════════

export function getToken() {
  return localStorage.getItem('qn_token') || null
}
export function setToken(token) {
  if (token) localStorage.setItem('qn_token', token)
  else localStorage.removeItem('qn_token')
}

/**
 * 从 JWT token 解码 qingnang_id（sub claim）
 * 不需要 scope 激活 — 只靠全局 token 就能恢复 userId，避免 bootstrap paradox
 * JWT 格式：header.payload.signature （payload 是 base64url 编码的 JSON）
 */
export function parseJwtSub(token) {
  if (!token) return null
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    let payload = parts[1]
      .replace(/-/g, '+').replace(/_/g, '/')   // base64url → base64
    while (payload.length % 4) payload += '='  // 补 padding
    const decoded = JSON.parse(atob(payload))
    return decoded.sub || null
  } catch { return null }
}

export function getOnboarded() {
  return localStorage.getItem('qingnang_onboarded') === 'true'
}
export function setOnboarded(v) {
  if (v) localStorage.setItem('qingnang_onboarded', 'true')
  else localStorage.removeItem('qingnang_onboarded')
}

// ═══════════════════════════════════════════════════════════════════════════
//  旧版全局 key 迁移（首次登录时自动跑一次）
// ═══════════════════════════════════════════════════════════════════════════

export function migrateLegacyKeys(userId) {
  if (!userId) return false
  const marker = `${SCOPE_PREFIX}${userId}:_migrate_done`
  if (localStorage.getItem(marker)) return false   // 已迁移过

  let migrated = 0
  for (const legacyKey of LEGACY_BIZ_KEYS) {
    const legacy = localStorage.getItem(legacyKey)
    if (legacy !== null) {
      const newKey = `${SCOPE_PREFIX}${userId}:${legacyKey}`
      localStorage.setItem(newKey, legacy)   // 保留原值（可能是 JSON 或纯文本）
      localStorage.removeItem(legacyKey)
      migrated++
    }
  }
  localStorage.setItem(marker, '1')
  if (migrated > 0) console.log(`[storage] 迁移完成：${migrated} 个旧 key → scope`)
  return migrated > 0
}
