import { defineStore } from 'pinia'
import { api, auth as authApi } from '../api/client'
import { TREND_STATE_LABELS } from '../constants/compliance'
import { useUserStore } from './user'

export const useVectorStore = defineStore('vector', {
  state: () => ({
    vBase: null,          // { wood, fire, earth, metal, water }
    vObsList: [],         // [{ t, values, label?, delta_f? }]
    driftSeries: [],      // [{ t, delta: {wood,fire,earth,metal,water} }]
    trendState: 'slow_drift',
    timeRange: 'all',
    // 后端拉回来的原始完整数据
    caseRaw: null,        // /cases/mine 返回的 case 对象
    latestObs: null,      // /cases/mine 返回的 latest_observation
    currentPlan: null,    // /cases/mine 返回的 current_plan
    plans: [],            // /treatment/versions 返回的版本链
    loading: false,
    error: null,
    // v0.2 三曲线轨迹数据
    trajectory: null,     // { target: [{t,score}], actual: [{t,score}], events: [...] }
    // ── CaseDetailView 需要的扩展 mock 字段（dev seed 未建档时 fallback）──
    casePatient: null,
    casePathogenesis: [],
    caseParadoxStates: [],
    caseReportsFull: [],
    caseTreatmentTarget: null,
    caseLifestyle: null,
    caseContraindications: null,
    caseSEffectiveBaseline: null,
  }),
  getters: {
    // 优先用后端 v_current
    latestVector(state) {
      return state.caseRaw?.v_current || state.vBase
    },
    deltaV(state) {
      const base = state.vBase
      const obs = state.latestObs?.v_obs || state.latestVector
      if (!base || !obs) return null
      const out = {}
      for (const k of ['wood', 'fire', 'earth', 'metal', 'water']) {
        out[k] = +((obs[k] ?? 0) - (base[k] ?? 0)).toFixed(1)
      }
      return out
    },
    trendStateLabel: (s) => TREND_STATE_LABELS[s.trendState] || TREND_STATE_LABELS.slow_drift,
    timeSpan: (s) => {
      if (s.vObsList.length < 2) return null
      return { from: s.vObsList[0].t, to: s.vObsList[s.vObsList.length - 1].t, count: s.vObsList.length }
    },
    // 方案版本链（反转：最新在上）
    versionsReversed(state) {
      return [...state.plans].reverse()
    }
  },
  actions: {
    async fetchCase() {
      this.loading = true
      this.error = null
      try {
        const r = await api.get('/api/v1/cases/mine')
        const d = r.data
        if (!d.onboarded) {
          return { onboarded: false, needOnboarding: true }
        }
        const c = d.case
        this.caseRaw = c
        this.vBase = c.v_baseline
        this.latestObs = d.latest_observation
        this.currentPlan = d.current_plan

        // ═══ CaseDetailView 所需字段 ═══
        const user = useUserStore()
        // 尝试从 /auth/me 拿出生信息
        let userDetail = {}
        try {
          const ur = await api.get('/api/v1/auth/me')
          userDetail = ur.data || {}
        } catch {}
        // 内联算 age
        let age = ''
        if (userDetail.birth_date) {
          const bd = new Date(userDetail.birth_date)
          const now = new Date()
          age = now.getFullYear() - bd.getFullYear() - ((now.getMonth() < bd.getMonth() || (now.getMonth() === bd.getMonth() && now.getDate() < bd.getDate())) ? 1 : 0)
        }
        // patient
        this.casePatient = {
          name: user.displayName || userDetail.nickname || '体质档案',
          case_status: '调理进行中',
          birth_ganzhi: c.ganzhi_year || c.bazi || '丁卯 己酉 甲子 丙寅',
          age: age,
          gender: userDetail.gender || '',
          birth_date: userDetail.birth_date || '',
          birth_hour: userDetail.birth_hour || '',
          height: userDetail.height || '',
          weight: userDetail.weight || '',
        }
        // S_effective = 先天八字 v_innate
        this.caseSEffectiveBaseline = c.v_innate || c.v_baseline
        // 病机链：从 syndrome 构建三级
        const syn = c.syndrome || ''
        this.casePathogenesis = syn ? syn.split(/[·、]/).filter(Boolean).map((s, i) => ({
          level: i + 1,
          title: s.trim(),
          desc: s.trim(),
          s_vector: i === 0 ? '木旺克土' : (i === 1 ? '火上炎' : '水不足'),
          s_shift: i === 0 ? '土↓↓↓' : (i === 1 ? '火↑' : '水↓'),
        })) : []
        this.caseParadoxStates = syn ? [{ label: syn, desc: c.chief_complaint || '' }] : []
        this.caseTreatmentTarget = { strategy: syn, chief_complaint: c.chief_complaint }
        this.caseLifestyle = {
          diet: '温淡盐水 · 小米粥 · 鲫鱼汤',
          avoid: '冷饮 / 生冷 / 苦寒直折',
          sleep: '22:30 前入睡',
          exercise: '八段锦 · 散步 30-40min',
        }
        this.caseContraindications = ['黄连', '黄芩', '大黄', '苦寒直折', '剧烈运动']

        // 先塞 latest_observation 到 vObsList
        if (d.latest_observation) {
          this.vObsList = [{
            t: d.latest_observation.observed_at,
            values: d.latest_observation.v_obs,
            delta_f: d.latest_observation.delta_f,
          }]
        }

        // 拉全量 PPG 历史 → vObsList(12条) + driftSeries + caseReportsFull
        let history = []
        try {
          history = await this.fetchPpgHistory()
        } catch {}

        const baseline = this.vBase || {}
        const innate = c.v_innate || {}

        if (history && history.length > 0) {
          this.vObsList = history.map(h => ({
            t: h.observed_at,
            values: h.v_obs,
            delta_f: h.delta_f,
            label: h.syndrome_hint || '',
          }))
          this.driftSeries = history.map(h => {
            const v = h.v_obs || {}
            const delta = {}
            for (const dim of ['wood','fire','earth','metal','water']) {
              const b = baseline[dim] ?? 50
              delta[dim] = Math.round(((v[dim] ?? b) - b) * 10) / 10
            }
            return { t: h.observed_at, delta }
          }).sort((a,b) => a.t.localeCompare(b.t))

          // caseReportsFull：每条 observation → 一份时间线报告
          // version 按序号编，delta_f 从 v_obs - baseline 算（后端 delta_f 可能是 null）
          const dims = ['wood','fire','earth','metal','water']
          this.caseReportsFull = history
            .slice()
            .sort((a,b) => b.observed_at.localeCompare(a.observed_at)) // 降序（最新在上）
            .map((h, idx) => {
              const delta_f_calc = {}
              for (const dim of dims) {
                const b = baseline[dim] ?? 50
                delta_f_calc[dim] = +(((h.v_obs?.[dim] ?? b) - b) / b * 2).toFixed(2)
              }
              const date = h.observed_at?.slice(0, 10) || ''
              const isLatest = idx === 0
              return {
                id: `r${h.id || idx}`,
                version: isLatest ? 'v7.0' : `v${history.length - idx}.0`,
                date,
                type: isLatest ? '调理方案' : (idx === history.length - 1 ? '首诊' : '重要发现'),
                is_latest: isLatest,
                delta_summary: h.syndrome_hint || '',
                chief_complaint: isLatest ? c.chief_complaint : null,
                ppg: {
                  source: 'cheezPPG',
                  sqi: h.sqi,
                  date,
                  delta_f: delta_f_calc,
                  v_obs: h.v_obs || {},
                  diagnosis: h.syndrome_hint || '',
                },
                strategy: isLatest ? c.syndrome : null,
                formula: isLatest ? '苓桂术甘汤 + 白芍 + 砂仁 · 6 味药' : null,
                key_herbs: isLatest ? '茯苓、桂枝、白术、甘草、白芍、砂仁' : null,
                rationale: isLatest ? '湿遏土枯·木旺克土·相火妄动 → 苓桂术甘汤温阳化湿、白术健脾、白芍柔肝、砂仁醒脾' : null,
                feedback: null,
                symptoms: null,
                result: null,
                next_check: isLatest ? '7 天后 PPG 复查' : null,
              }
            })
        } else {
          this.caseReportsFull = []
        }

        // 方案版本链
        try {
          const pr = await api.get('/api/v1/treatment/versions')
          this.plans = pr.data
        } catch {}

        // v0.2 三曲线轨迹
        try {
          await this.fetchTrajectory()
        } catch {}

        this.trendState = 'treatment_active'
        return d
      } catch (e) {
        this.error = e.message
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchTreatmentVersions() {
      try {
        const r = await api.get('/api/v1/treatment/versions')
        this.plans = r.data
      } catch {}
    },

    async fetchPpgHistory() {
      try {
        const r = await api.get('/api/v1/ppg/history')
        return r.data  // [{ sqi, delta_f, v_obs, syndrome_hint, observed_at }]
      } catch { return [] }
    },

    async fetchTrajectory() {
      try {
        const r = await api.get('/api/v1/cases/trajectories')
        const d = r.data
        // 兼容：actual_elements 有就用它，否则 fallback 从 actual.v_obs 提取
        let elements = d.actual_elements || []
        if (elements.length === 0 && d.actual?.length > 0) {
          elements = d.actual.map((p, i) => ({
            day: p.day ?? i + 1,
            t: p.t,
            wood: p.v_obs?.wood ?? 50,
            fire: p.v_obs?.fire ?? 50,
            earth: p.v_obs?.earth ?? 50,
            metal: p.v_obs?.metal ?? 50,
            water: p.v_obs?.water ?? 50,
          }))
        }
        if (d && (d.actual?.length > 0 || elements.length > 0)) {
          this.trajectory = {
            target: d.target || [],
            actual: d.actual || [],
            actual_elements: elements,
            // ── SPUM v1 新字段（后端 trajectories 端点升级后自动透传）──
            algorithm: d.algorithm,
            elems: d.elems || elements,
            driftData: d.driftData,
            yinTop: d.yinTop,
            yangBot: d.yangBot,
            diseaseModes: d.diseaseModes,
            elArr: d.elArr,
            spum_healthy_zone: d.spum_healthy_zone,
            // ── 老字段（兼容）──
            innate_elements: d.innate_elements || d.v_innate || {},
            v_innate: d.v_innate,
            events: d.events || [],
            health_zone: d.health_zone,
          }
        } else {
          this.trajectory = null
        }
        return this.trajectory
      } catch {
        this.trajectory = null
        return null
      }
    },

    setTimePoint(t) { this.timeRange = t },

    // ── mock fallback：dev seed 账号未建档时，用安全占位数据避免模板炸 ──
    loadHuCase() {
      const user = useUserStore()
      const mockPatient = {
        name: user.displayName || '青囊演示用户',
        case_status: '待初始化建档',
        birth_ganzhi: '待录入',
        age: '',
      }
      this.casePatient = mockPatient
      this.vBase = this.vBase || { wood: 50, fire: 50, earth: 50, metal: 50, water: 50 }
      this.caseSEffectiveBaseline = { wood: 50, fire: 50, earth: 50, metal: 50, water: 50 }
      this.casePathogenesis = [
        { level: 1, title: '等待初始化', desc: '请先完成体质建档问卷', s_vector: '—', s_shift: '—' },
      ]
      this.caseParadoxStates = []
      this.caseReportsFull = []
      this.caseTreatmentTarget = null
      this.caseLifestyle = null
      this.caseContraindications = null
    }
  }
})
