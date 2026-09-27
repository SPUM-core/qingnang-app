import { defineStore } from 'pinia'
import { api } from '../api/client'
import { useVectorStore } from './vector'

const LS_TOKEN = 'qn_token'
const LS_USER  = 'qn_user'
const LS_ONBOARD = 'qingnang_onboarded'

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
  }),
  getters: {
    loggedIn:   (s) => !!s.token,
    onboarded:  (s) => s.isOnboarded,
    displayName:(s) => s.nickname || s.qingnangId?.slice(0, 12) || '青囊用户',
  },
  actions: {
    // 启动时从 localStorage 恢复登录态
    initFromLocalStorage() {
      const token = localStorage.getItem(LS_TOKEN)
      const user  = localStorage.getItem(LS_USER)
      if (token && user) {
        this.token = token
        try {
          Object.assign(this, JSON.parse(user))
          // 同步恢复守卫依赖的 qingnang_onboarded key（防止旧数据缺失）
          if (this.isOnboarded && !localStorage.getItem(LS_ONBOARD)) {
            localStorage.setItem(LS_ONBOARD, 'true')
          }
        } catch {}
      }
    },

    // ── 登录 ──
    async login(phone, password) {
      this.loading = true; this.error = null
      try {
        const r = await api.post('/api/v1/auth/login', { phone, password })
        const d = r.data
        this.token = d.token
        this.qingnangId = d.qingnang_id
        this.nickname = d.nickname
        this.isDoctor = d.is_doctor
        this.isOnboarded = d.is_onboarded
        localStorage.setItem(LS_TOKEN, this.token)
        localStorage.setItem(LS_USER, JSON.stringify({
          qingnang_id: this.qingnangId, nickname: this.nickname,
          is_doctor: this.isDoctor, is_onboarded: this.isOnboarded,
        }))
        // 同步守卫依赖的 qingnang_onboarded key
        if (this.isOnboarded) localStorage.setItem(LS_ONBOARD, 'true')
        else localStorage.removeItem(LS_ONBOARD)
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
        const r = await api.post('/api/v1/auth/register', payload)
        const d = r.data
        this.token = d.token
        this.qingnangId = d.qingnang_id
        this.nickname = d.nickname
        this.isDoctor = d.is_doctor
        this.isOnboarded = d.is_onboarded
        localStorage.setItem(LS_TOKEN, this.token)
        localStorage.setItem(LS_USER, JSON.stringify({
          qingnang_id: this.qingnangId, nickname: this.nickname,
          is_doctor: this.isDoctor, is_onboarded: this.isOnboarded,
        }))
        if (this.isOnboarded) localStorage.setItem(LS_ONBOARD, 'true')
        else localStorage.removeItem(LS_ONBOARD)
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
        })
        localStorage.setItem(LS_USER, JSON.stringify({
          qingnang_id: this.qingnangId, nickname: this.nickname,
          is_doctor: this.isDoctor, is_onboarded: this.isOnboarded,
        }))
        if (this.isOnboarded) localStorage.setItem(LS_ONBOARD, 'true')
        else localStorage.removeItem(LS_ONBOARD)
        return d
      } catch (e) {
        if (e.response?.status === 401) this.logout()
        throw e
      }
    },

    // ── 初始化建档（onboarding 完成后调） ──
    async doOnboarding(data) {
      try {
        const r = await api.post('/api/v1/cases/onboarding', data)
        this.isOnboarded = true
        localStorage.setItem(LS_USER, JSON.stringify({
          ...JSON.parse(localStorage.getItem(LS_USER) || '{}'),
          is_onboarded: true,
        }))
        return r.data
      } catch (e) {
        this.error = e.response?.data?.detail || e.message
        throw e
      }
    },

    // ── 登出（彻底清干净，避免串号残留） ──
    logout() {
      this.token = null
      this.qingnangId = null
      this.nickname = null
      this.phone = null
      this.isOnboarded = false
      this.isDoctor = false
      this.vBase = null
      this.loading = false
      this.error = null
      localStorage.removeItem(LS_TOKEN)
      localStorage.removeItem(LS_USER)
      localStorage.removeItem(LS_ONBOARD)
      // 清 vectorStore 全部缓存 — 否则换账号时会串旧账号的体质数据
      try {
        const v = useVectorStore()
        v.$reset()
      } catch {}
    }
  }
})
