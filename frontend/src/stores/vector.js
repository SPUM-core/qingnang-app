import { defineStore } from 'pinia'
import { api, auth as authApi } from '../api/client'
import { TREND_STATE_LABELS } from '../constants/compliance'
import { useUserStore } from './user'

// ═══════════════════════════════════════════════════════════
// 共享纯函数：五形向量 → 箭头/摘要（所有组件统一复用）
// ═══════════════════════════════════════════════════════════

/** 五形值 → 箭头字符串。
 *  center=20 为理想中心 — v_innate 是归一化概率分布（总和=100，5维均匀分布=每维20）
 *  偏离度决定箭头层数：±2 内为 ↔（±10% 近中心），±8 内为 ↑/↓（±40%），±18 内为 ↑↑/↓↓（±90%）
 *  纯概率分布不可能全部皆强或皆弱（总和固定100），修 center=50 导致五行皆弱 bug。
 */
export function toArrow(v, center = 20) {
  if (v == null || v === '') return '↔'
  const d = +v - center
  const abs = Math.abs(d)
  if (abs <= 2) return '↔'
  if (abs <= 8) return d > 0 ? '↑' : '↓'
  if (abs <= 18) return d > 0 ? '↑↑' : '↓↓'
  return d > 0 ? '↑↑↑' : '↓↓↓'
}

/** 五形字典 → "木↑↑↑ 火↓↓ 土↔ 金↑ 水↓" 格式字符串 */
export function toModelSummary(v, center = 20) {
  if (!v) return '五形数据待建档'
  const labels = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
  return ['wood', 'fire', 'earth', 'metal', 'water']
    .map(k => `${labels[k]}${toArrow(v[k], center)}`)
    .join(' ')
}

/** 五形字典 → 核心偏失摘要，如 "木↓↓↓ · 土↓↓ · 水↑" */
export function toCoreDeviation(v, center = 20, topN = 3) {
  if (!v) return ''
  const labels = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
  const arr = ['wood', 'fire', 'earth', 'metal', 'water']
    .map(k => ({ k, v: v[k], d: (v[k] ?? center) - center }))
    .sort((a, b) => Math.abs(b.d) - Math.abs(a.d))
    .slice(0, topN)
  return arr.map(x => `${labels[x.k]}${toArrow(x.v, center)}`).join(' · ')
}

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
        const nObs = this.vObsList?.length || 0
        const stageLabel = nObs === 0 ? '数据收集中' : (nObs < 3 ? '基线建立中' : (nObs < 8 ? '调理进行中' : '稳定观察'))

        // patient
        // 八字四柱拼接（去掉胡运涛硬编码 fallback）
        const pillars = [c.ganzhi_year, c.ganzhi_month, c.ganzhi_day, c.ganzhi_hour]
          .filter(Boolean).join(' ') || c.bazi || ''
        this.casePatient = {
          name: user.displayName || userDetail.nickname || '体质档案',
          case_status: stageLabel,
          birth_ganzhi: pillars,
          age: age,
          gender: userDetail.gender || '',
          birth_date: userDetail.birth_date || '',
          birth_hour: userDetail.birth_hour || '',
          height: userDetail.height || '',
          weight: userDetail.weight || '',
        }
        // S_effective = 先天八字 v_innate
        this.caseSEffectiveBaseline = c.v_innate || c.v_baseline
        // 病机链：从 syndrome 构建三级（无 syndrome 则留空，不再硬编码胡运涛的 "木旺克土"）
        const syn = c.syndrome || ''
        this.casePathogenesis = syn ? syn.split(/[·、]/).filter(Boolean).map((s, i) => ({
          level: i + 1,
          title: s.trim(),
          desc: s.trim(),
        })) : []
        this.caseParadoxStates = syn ? [{ label: syn, desc: c.chief_complaint || '' }] : []
        this.caseTreatmentTarget = { strategy: syn, chief_complaint: c.chief_complaint }
        // 生活方式建议 → 空（后端 plans 有 lifestyle 时会覆盖；不再硬编码胡运涛的"温淡盐水"）
        this.caseLifestyle = { diet: '', avoid: '', sleep: '', exercise: '' }
        this.caseContraindications = []

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
              const b = baseline[dim] ?? 20
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
                const b = baseline[dim] ?? 20
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
                formula: isLatest ? (c.formula || null) : null,
                key_herbs: isLatest ? (c.key_herbs || null) : null,
                rationale: isLatest ? (c.rationale || null) : null,
                feedback: null,
                symptoms: null,
                result: null,
                next_check: isLatest ? (c.next_check || null) : null,
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
            wood: p.v_obs?.wood ?? 20,
            fire: p.v_obs?.fire ?? 20,
            earth: p.v_obs?.earth ?? 20,
            metal: p.v_obs?.metal ?? 20,
            water: p.v_obs?.water ?? 20,
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
      this.vBase = this.vBase || { wood: 20, fire: 20, earth: 20, metal: 20, water: 20 }
      this.caseSEffectiveBaseline = { wood: 20, fire: 20, earth: 20, metal: 20, water: 20 }
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
