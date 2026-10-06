import { defineStore } from 'pinia'
import { api } from '../api/client'
import { useVectorStore } from './vector'
import * as storage from '../utils/storage'

/** 清掉浏览器里所有用户 scope 下的业务数据（qn:*:*）
 *  用途：register 新账号前 + login 切换账号前 — 防止旧账号残留数据泄漏到新账号
 */
function _clearAllBusinessScopes() {
  const prefix = 'qn:'
  const toRemove = []
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i)
    // 清 qn:xxx:yyy 格式的（业务 key），但保留 qn_token（全局 auth key）
    if (k && k.startsWith(prefix) && !k.startsWith('qn_token') && !k.startsWith('qingnang_')) {
      // 只清 qn:{userId}:{bizKey} 格式，保留 qingnang_onboarded / qingnang_settings 等全局
      const parts = k.split(':')
      if (parts.length >= 3 && parts[0] === 'qn') {
        toRemove.push(k)
      }
    }
  }
  toRemove.forEach(k => localStorage.removeItem(k))
  if (toRemove.length) console.log(`[storage] 清 ${toRemove.length} 个旧 scope key:`, toRemove.map(k => k.split(':')[1]))
}

export const useUserStore = defineStore('user', {
  state: () => ({
    qingnangId: null,
    nickname: null,
    phone: null,
    isDoctor: false,
    isOnboarded: false,
    vBase: null,
    token: null,
    loading: false,
    error: null,
    // ── 用户数字模型成熟度（4 阶段）──
    maturity: null,   // { stage, name, label, icon, score, max_score, next_target, is_member, missing_signals, allowed_content, forbidden_content, progress }
    // ⭐ 引导完成标记（以 storageKey 为 key，后端持久化，换浏览器也不重弹）
    guidesSeen: {},   // { guide_home_completed: 1728100000000, ... }
  }),
  getters: {
    loggedIn:   (s) => !!s.token,
    onboarded:  (s) => s.isOnboarded,
    /** 亲切名：去掉姓氏后的 1-2 字。如 "胡运涛" → "运涛"，"素娟" → "素娟"，null → "朋友" */
    displayName:(s) => {
      const raw = s.nickname?.trim()
      if (!raw || raw.startsWith('青囊用户')) return '朋友'
      // 单字名 → 直接返回
      if (raw.length <= 2) return raw
      // 多字 → 去掉姓氏（中文姓氏一般 1 字，欧阳/司马等复姓 2 字）
      // 简化处理：先试去掉前 1 字，得到 2+ 字就返回；否则去掉前 2 字
      const without1 = raw.slice(1)
      if (without1.length >= 2) return without1
      const without2 = raw.slice(2)
      return without2 || raw
    },
  },
  actions: {
    // 启动时从 localStorage 恢复登录态
    initFromLocalStorage() {
      const token = storage.getToken()
      if (!token) return
      // 🔐 关键修复：从 JWT payload 解码 qingnang_id，避免 bootstrap paradox
      // （不依赖任何 scope key — scope key 需要 userId 才能生成，但 userId 又存在 scope key 里）
      const qingnangId = storage.parseJwtSub(token)
      if (!qingnangId) {
        // token 无法解码 → 可能被篡改，清掉
        storage.clearUserScope()
        return
      }
      // 激活命名空间 — 之后所有 storage.get 都会正确拼接前缀
      storage.setUserScope(qingnangId)
      // 迁移老用户的全局 key 到 scope 下（首次部署后自动跑一次）
      storage.migrateLegacyKeys(qingnangId)
      // 从 scope 下读用户信息
      const user = storage.get('qn_user', null)
      if (user) {
        this.token = token
        try {
          Object.assign(this, user)
          // 确保 qingnangId 也同步到 state（可能 scope key 里没存）
          if (!this.qingnangId) this.qingnangId = qingnangId
          // 同步守卫依赖的 onboarded
          if (this.isOnboarded && !storage.getOnboard()) {
            storage.setOnboarded(true)
          }
        } catch {}
      }
    },

    // ── 登录 ──
    async login(phone, password) {
      this.loading = true; this.error = null
      try {
        // ⚠️ 切换账号时先清所有旧 scope（登出不一定被调过）
        _clearAllBusinessScopes()
        
        const r = await api.post('/api/v1/auth/login', { phone, password })
        const d = r.data
        this.token = d.token
        this.qingnangId = d.qingnang_id
        this.nickname = d.nickname
        this.isDoctor = d.is_doctor
        this.isOnboarded = d.is_onboarded
        // 🔐 写鉴权全局 key
        storage.setToken(this.token)
        storage.setOnboarded(this.isOnboarded)
        // 🔐 激活用户命名空间 — 业务 key 全部走 scope
        storage.setUserScope(this.qingnangId)
        storage.migrateLegacyKeys(this.qingnangId)
        storage.set('qn_user', {
          qingnang_id: this.qingnangId, nickname: this.nickname,
          is_doctor: this.isDoctor, is_onboarded: this.isOnboarded,
        })
        // 🎖️ 登录后立即拉成熟度（全局可用，不依赖 QingnangAssistant 挂载）
        this.fetchMaturity().catch(() => {})
        return d
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
        throw e
      } finally { this.loading = false }
    },

    // ── 注册 ──
    async register(payload) {
      this.loading = true; this.error = null
      try {
        // ⚠️ 先清浏览器里所有旧 scope 数据（可能来自之前未完全登出的账号）
        _clearAllBusinessScopes()
        
        const r = await api.post('/api/v1/auth/register', payload)
        const d = r.data
        this.token = d.token
        this.qingnangId = d.qingnang_id
        this.nickname = d.nickname
        this.isDoctor = d.is_doctor
        this.isOnboarded = d.is_onboarded
        storage.setToken(this.token)
        storage.setOnboarded(this.isOnboarded)
        storage.setUserScope(this.qingnangId)
        storage.migrateLegacyKeys(this.qingnangId)
        storage.set('qn_user', {
          qingnang_id: this.qingnangId, nickname: this.nickname,
          is_doctor: this.isDoctor, is_onboarded: this.isOnboarded,
        })
        // 🎖️ 注册成功后也拉成熟度
        this.fetchMaturity().catch(() => {})
        return d
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
        throw e
      } finally { this.loading = false }
    },

    // ── 拉取当前用户完整信息 ──
    async fetchMe() {
      try {
        const r = await api.get('/api/v1/auth/me')
        const d = r.data
        Object.assign(this, {
          qingnangId: d.qingnang_id, nickname: d.nickname,
          isDoctor: d.is_doctor, isOnboarded: d.is_onboarded,
          vBase: d.v_base, phone: d.phone,
          guidesSeen: d.guides_seen || {},   // ⭐ 引导完成标记从后端拉
        })
        storage.set('qn_user', {
          qingnang_id: this.qingnangId, nickname: this.nickname,
          is_doctor: this.isDoctor, is_onboarded: this.isOnboarded,
          guides_seen: this.guidesSeen,
        })
        storage.setOnboarded(this.isOnboarded)
        return d
      } catch (e) {
        if (e.response?.status === 401) this.logout()
        throw e
      }
    },

    /** ⭐ 引导完成标记 —— 同时写 store + localStorage + 后端（后端是 source of truth） */
    async markGuideSeen(storageKey) {
      const now = Date.now()
      // 1. store
      this.guidesSeen = { ...this.guidesSeen, [storageKey]: now }
      // 2. localStorage（快速缓存）
      storage.setGlobal(storageKey, now)
      // 3. 后端持久化（换浏览器也不重弹）
      try {
        await api.patch('/api/v1/auth/me/guides-seen', { key: storageKey, value: now })
      } catch (e) {
        console.warn('[user] markGuideSeen 后端写失败（不影响前端体验）:', e.message)
      }
    },

    // ── 初始化建档（onboarding 完成后调） ──
    async doOnboarding(data) {
      try {
        const r = await api.post('/api/v1/cases/onboarding', data)
        this.isOnboarded = true
        storage.setOnboarded(true)
        const prev = storage.get('qn_user', {}) || {}
        storage.set('qn_user', { ...prev, is_onboarded: true })
        return r.data
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
        throw e
      }
    },

    // ── 拉取数字模型成熟度（每次登录/chat 响应中带，也可单独拉）──
    async fetchMaturity() {
      try {
        const r = await api.get('/api/v1/assistant/maturity')
        this.maturity = r.data
        return r.data
      } catch (e) {
        // 401 已由 interceptor 处理；其他错误静默——前端用 cached/null
        console.warn('[userStore] fetchMaturity failed:', e.message)
      }
    },

    // ── 接收 chat 响应中的 maturity（chat 返回内嵌 maturity 字段更高效）──
    updateMaturityFromChat(m) {
      if (m && m.stage) {
        // 只更新关键字段（chat 返回的是精简版），完整版等 fetchMaturity
        this.maturity = { ...(this.maturity || {}), ...m }
      }
    },

    // ── 登出（彻底清干净，避免串号残留） ──
    logout() {
      const uid = this.qingnangId
      // 🔐 storage.clearUserScope 一键清：全局 auth key + 该用户 scope 下所有业务 key
      storage.clearUserScope(uid)
      this.token = null
      this.qingnangId = null
      this.nickname = null
      this.phone = null
      this.isOnboarded = false
      this.isDoctor = false
      this.vBase = null
      this.maturity = null
      this.loading = false
      this.error = null
      // 清 vectorStore 全部缓存 — 否则换账号时会串旧账号的体质数据
      try {
        const v = useVectorStore()
        v.$reset()
      } catch {}
    }
  }
})
