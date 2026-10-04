<template>
  <section class="page case">
    <!-- 顶部：数字模型总览 -->
    <div class="case-hero">
      <div class="hero-left">
        <h1>📋 {{ patient?.name || '体质档案' }}</h1>
        <p class="hero-sub">
          {{ patient?.case_status }} · 八字 {{ patient?.birth_ganzhi }} · {{ patient?.age }}岁
        </p>
        <div class="hero-model">
          <span class="model-label">当前数字模型</span>
          <div class="model-chips">
            <span v-for="v in latestVectorChips" :key="v.label" :class="'chip chip-' + v.key">
              {{ v.label }}{{ v.arrow }}
            </span>
          </div>
        </div>
      </div>
      <div class="hero-right">
        <div class="stat-row">
          <div class="stat-block">
            <span class="stat-num">{{ reportsFull.length }}</span>
            <span class="stat-label">份报告</span>
          </div>
          <div class="stat-block">
            <span class="stat-num">{{ ppgObsCount }}</span>
            <span class="stat-label">次脉诊</span>
          </div>
          <div class="stat-block">
            <span class="stat-num">{{ spanDays }}</span>
            <span class="stat-label">天调理</span>
          </div>
        </div>
        <RouterLink to="/collect" class="hero-cta-btn">
          <QIcon name="chart" :size="13" />
          <span>数据采集</span>
          <span class="cta-arrow">→</span>
        </RouterLink>
      </div>
    </div>

    <!-- Tab 切换 -->
    <div class="tabs">
      <button v-for="tab in tabs" :key="tab.key" class="tab-btn"
              :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">
        {{ tab.icon }} {{ tab.label }}
      </button>
    </div>

    <!-- ═══ Tab: 报告时间线（反转 + 可展开） ═══ -->
    <div v-if="activeTab === 'timeline'" class="tl-wrap">
      <p class="tl-intro">共 {{ reportsFull.length }} 份报告 · 最新在上 · 点击展开完整内容</p>

      <div class="timeline">
        <div v-for="(r, idx) in reportsFull" :key="r.id" class="tl-item"
             :class="{ expanded: expandedId === r.id, latest: r.is_latest }">

          <!-- 时间线节点圆点 -->
          <div class="tl-dot">
            <span v-if="r.is_latest" class="dot-ring"></span>
          </div>

          <!-- 摘要卡（始终可见） -->
          <div class="tl-summary" @click="toggleExpand(r.id)">
            <div class="tl-summary-head">
              <span class="tl-version">{{ r.version }}</span>
              <span class="tl-date">{{ r.date }}</span>
              <span class="tl-type-badge" :class="'type-' + typeClass(r.type)">{{ r.type }}</span>
              <span v-if="r.is_latest" class="latest-badge">🟢 当前</span>
              <span class="expand-icon">{{ expandedId === r.id ? '▲' : '▼' }}</span>
            </div>
            <div class="tl-delta-row" v-if="r.delta_summary">
              <span class="delta-text">{{ r.delta_summary }}</span>
            </div>
          </div>

          <!-- 展开内容 -->
          <div class="tl-detail" v-if="expandedId === r.id">

            <!-- 主诉/目标 -->
            <div class="detail-section" v-if="r.chief_complaint">
              <h4>📌 主诉/目标</h4>
              <p>{{ r.chief_complaint }}</p>
            </div>

            <!-- PPG 脉诊快照 -->
            <div class="detail-section ppg-section" v-if="r.ppg">
              <h4>📊 脉诊观测（{{ r.ppg.source }} · SQI {{ r.ppg.sqi }}）</h4>
              <p class="ppg-date">观测日期：{{ r.ppg.date }}</p>

              <!-- 五形 ΔF 条 -->
              <div class="ppg-bars">
                <div v-for="k in elements" :key="k" class="ppg-bar-row">
                  <span class="ppg-label" :style="{ color: colors[k] }">{{ labels[k] }}</span>
                  <div class="ppg-track">
                    <div class="ppg-bar ppg-bar-neg" v-if="(r.ppg.delta_f[k] || 0) < 0"
                         :style="{ width: Math.min(Math.abs(r.ppg.delta_f[k] || 0) * 100, 100) + '%', background: colors[k] }"></div>
                    <div class="ppg-bar ppg-bar-pos" v-else
                         :style="{ width: Math.min((r.ppg.delta_f[k] || 0) * 100, 100) + '%', background: colors[k] }"></div>
                  </div>
                  <span class="ppg-val" :class="(r.ppg.delta_f[k] || 0) >= 0 ? 'pos' : 'neg'">
                    {{ (r.ppg.delta_f[k] || 0) >= 0 ? '+' : '' }}{{ (Math.abs(r.ppg.delta_f[k] || 0) === Infinity ? 0 : (r.ppg.delta_f[k] || 0)).toFixed(2) }}
                  </span>
                  <span class="ppg-vobs">{{ r.ppg.v_obs[k] ?? r.ppg.v_obs[k] }}</span>
                </div>
              </div>

              <p class="ppg-diagnosis">💡 {{ r.ppg.diagnosis }}</p>
            </div>

            <!-- 方案/处方 -->
            <div class="detail-section" v-if="r.formula || r.adjustment || r.strategy">
              <h4>💊 调理方案</h4>
              <p v-if="r.strategy" class="formula-strategy">🎯 {{ r.strategy }}</p>
              <p v-if="r.formula" class="formula-text">📜 {{ r.formula }}</p>
              <p v-if="r.key_herbs" class="herbs-text">💊 {{ r.key_herbs }}</p>
              <p v-if="r.adjustment" class="adjust-text">🔧 {{ r.adjustment }}</p>
              <p v-if="r.frame" class="frame-text">🗂️ {{ r.frame }}</p>
            </div>

            <!-- 推导原理 -->
            <div class="detail-section" v-if="r.rationale || r.key_discovery || r.key_finding || r.correction">
              <h4>📖 推导原理</h4>
              <p v-if="r.rationale">{{ r.rationale }}</p>
              <p v-if="r.key_discovery" class="highlight">💡 {{ r.key_discovery }}</p>
              <p v-if="r.key_finding" class="highlight">🔍 {{ r.key_finding }}</p>
              <p v-if="r.correction" class="correction">🔄 {{ r.correction }}</p>
            </div>

            <!-- 反馈/症状 -->
            <div class="detail-section two-col" v-if="r.feedback || r.symptoms || r.result">
              <div v-if="r.feedback" class="sub-col good">
                <h5>✅ 用户反馈</h5>
                <p>{{ r.feedback }}</p>
              </div>
              <div v-if="r.symptoms" class="sub-col bad">
                <h5>⚠️ 当前症状</h5>
                <p>{{ r.symptoms }}</p>
              </div>
              <div v-if="r.result" class="sub-col">
                <h5>📈 阶段结果</h5>
                <p>{{ r.result }}</p>
              </div>
            </div>

            <!-- 下一步 -->
            <div class="detail-section" v-if="r.next_check" :style="{ padding: '10px 14px', background: 'rgba(26,77,69,0.04)', borderRadius: 6 }">
              <p style="margin:0; font-size:13px;">🗓️ <strong>下一步：</strong>{{ r.next_check }}</p>
            </div>

          </div>
        </div>
      </div>
    </div>

    <!-- ═══ Tab: 先天基底 + 病机链 ═══ -->
    <div v-else-if="activeTab === 'foundation'" class="foundation-wrap">
      <!-- S_0 先天基底 -->
      <div class="card clickable-card" @click="showInnateReport = true" title="点击查看完整文字报告">
        <h2>1. 先天基底 S_0^0 <span class="card-hint">点击查看完整报告 →</span></h2>
        <p class="s0-desc">S_0^0 = ({{ s0ArrowSummary }}) · 八字 {{ patient?.birth_ganzhi || '待推演' }}</p>
        <div class="vector-compare">
          <div class="vector-col">
            <h3>先天基底 V_base</h3>
            <div class="bar-row" v-for="row in baseTable" :key="row.k">
              <span class="bar-label" :style="{ color: row.color }">{{ row.label }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: row.value + '%', background: row.color }"></div>
              </div>
              <span class="bar-value">{{ row.value }}</span>
              <span class="bar-arrow">{{ row.arrow }}</span>
            </div>
          </div>
          <div class="vector-col">
            <h3>调理前基线 S_effective</h3>
            <div class="bar-row" v-for="row in effectiveTable" :key="row.k">
              <span class="bar-label" :style="{ color: row.color }">{{ row.label }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: row.value + '%', background: row.color }"></div>
              </div>
              <span class="bar-value">{{ row.value }}</span>
              <span class="bar-arrow" v-if="row.arrow">{{ row.arrow }}</span>
            </div>
          </div>
        </div>
        <p class="paradox-hint" v-if="coreDeviation">⚠️ 核心偏移：{{ coreDeviation }}</p>
        <p class="paradox-hint muted" v-else>💡 先天基底调和，暂无显著偏失</p>
      </div>

      <!-- 病机链 -->
      <div class="card">
        <h2>2. 完整体质变化链</h2>
        <div class="pathogenesis">
          <div v-for="(step, i) in pathogenesis" :key="i" class="patho-step">
            <div class="patho-num">Step {{ step.level }}</div>
            <div class="patho-body">
              <h4>{{ step.title }}</h4>
              <p class="patho-desc">{{ step.desc }}</p>
              <p class="patho-shift" v-if="step.s_shift || step.s_vector">
                <span v-if="step.s_vector">S_0^0: {{ step.s_vector }}</span>
                <span v-if="step.s_shift">→ {{ step.s_shift }}</span>
              </p>
            </div>
          </div>
        </div>
        <div class="paradoxes" v-if="paradoxStates?.length">
          <h4>🔥 悖论态汇总</h4>
          <div v-for="p in paradoxStates" :key="p.name" class="paradox-item">
            <strong>{{ p.name }}：</strong>{{ p.desc }}
            <em>{{ p.metaphor }}</em>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ Tab: 历史调理方案档案 ═══ -->
    <div v-else class="plan-wrap">
      <!-- 顶部：当前方案醒目卡 -->
      <div class="card current-plan-card" v-if="currentPlan">
        <div class="cp-head">
          <span class="cp-current-badge">🟢 当前方案</span>
          <span class="cp-version">{{ currentPlan.version }}</span>
          <span class="cp-date">{{ currentPlan.created_at?.slice(0,10) }}</span>
        </div>
        <h3 class="cp-strategy">🎯 {{ currentPlan.strategy }}</h3>
        <p class="cp-prescription">📜 {{ currentPlan.prescription }}</p>
        <div class="cp-herbs" v-if="currentPlan.herbs?.length">
          <h4>💊 药味组成（{{ currentPlan.herbs.length }} 味）</h4>
          <ul class="herb-list">
            <li v-for="(h, i) in currentPlan.herbs" :key="i">{{ h }}</li>
          </ul>
        </div>
        <div class="cp-reasoning" v-if="currentPlan.reasoning">
          <h4>📖 推导原理</h4>
          <p>{{ currentPlan.reasoning }}</p>
        </div>
        <div class="cp-avoid" v-if="currentPlan.avoidances?.length">
          <h4>⚠️ 注意事项</h4>
          <p>{{ currentPlan.avoidances.join(' · ') }}</p>
        </div>
      </div>

      <!-- 历史方案时间线 -->
      <div class="plan-timeline-header" v-if="plans.length > 1">
        <span class="pt-title">📜 历史调理方案档案</span>
        <span class="pt-count">共 {{ plans.length }} 版 · 最新在上</span>
      </div>

      <div class="plan-history" v-if="historyPlans.length">
        <div v-for="p in historyPlans" :key="p.id"
             class="plan-item"
             :class="{ expanded: expandedPlanId === p.id }">
          <div class="plan-head" @click="togglePlan(p.id)">
            <span class="plan-version">{{ p.version }}</span>
            <span class="plan-type-badge" :class="'type-' + p.plan_type">{{ planTypeLabel(p.plan_type) }}</span>
            <span class="plan-date">{{ p.created_at?.slice(0,10) }}</span>
            <span class="plan-expand">{{ expandedPlanId === p.id ? '▲' : '▼' }}</span>
          </div>
          <div class="plan-body" v-if="expandedPlanId === p.id">
            <p class="plan-strategy" v-if="p.strategy">🎯 {{ p.strategy }}</p>
            <p class="plan-prescription" v-if="p.prescription">📜 {{ p.prescription }}</p>
            <div class="plan-herbs" v-if="p.herbs?.length">
              <h5>💊 药味（{{ p.herbs.length }} 味）</h5>
              <ul class="herb-list-sm">
                <li v-for="(h, i) in p.herbs" :key="i">{{ h }}</li>
              </ul>
            </div>
            <div class="plan-reasoning" v-if="p.reasoning">
              <h5>📖 推导原理</h5>
              <p>{{ p.reasoning }}</p>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">
        <p>暂无历史调理方案档案</p>
      </div>
    </div>

    <!-- ═══ 先天基底完整文字报告弹窗 ═══ -->
    <transition name="modal">
      <div v-if="showInnateReport" class="modal-overlay" @click.self="showInnateReport = false">
        <div class="modal-content innate-report-modal">
          <div class="modal-header">
            <h2>📜 先天基底完整文字报告</h2>
            <button class="modal-close" @click="showInnateReport = false">✕</button>
          </div>
          <div class="modal-body" v-html="innateReportHtml"></div>
        </div>
      </div>
    </transition>
  </section>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import QIcon from '../components/ui/QIcon.vue'
import { useVectorStore, toArrow } from '../stores/vector'

const vectorStore = useVectorStore()

onMounted(async () => {
  // 强制拉取后端最新数据
  let ok = false
  try {
    const res = await vectorStore.fetchCase()
    ok = !!res
  } catch {
    ok = false
  }
  // 后端拉不到 → 才算真错误（不再 fallback 到胡运涛种子数据）
  if (!ok) {
    vectorStore.loadHuCase()   // 仅后端挂了才 fallback
  }
  // ⚠️ caseReportsFull 为空 = 用户还没采过 PPG，这是正常新用户态
  //     不再触发 loadHuCase！让 computed/UI 自己处理空态
})

const patient = computed(() => vectorStore.casePatient)
const pathogenesis = computed(() => vectorStore.casePathogenesis)
const paradoxStates = computed(() => vectorStore.caseParadoxStates)
const reportsFull = computed(() => vectorStore.caseReportsFull || [])

// ── 历史调理方案相关 ──
const plans = computed(() => vectorStore.plans || [])
const currentPlan = computed(() => {
  const all = plans.value
  if (!all.length) return null
  // 优先 is_current，否则 created_at 最大
  return all.find(p => p.is_current) || all.sort((a,b) => b.created_at?.localeCompare(a.created_at))[0]
})
const historyPlans = computed(() => {
  const cur = currentPlan.value
  return plans.value
    .filter(p => p.id !== cur?.id)
    .sort((a,b) => (b.created_at || '').localeCompare(a.created_at || ''))
})
const expandedPlanId = ref(null)
const togglePlan = (id) => {
  expandedPlanId.value = expandedPlanId.value === id ? null : id
}
const planTypeLabel = (t) => ({
  initial: '首诊方案', iteration: '迭代', validation: '验证',
}[t] || t)

const labels = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
const colors = { wood: '#43A047', fire: '#D84315', earth: '#D4A017', metal: '#90A4AE', water: '#0288D1' }
const elements = ['wood','fire','earth','metal','water']

const tabs = [
  { key: 'timeline', icon: '📜', label: '报告时间线' },
  { key: 'foundation', icon: '🧬', label: '先天基底' },
  { key: 'plan', icon: '🎯', label: '调理方案' }
]
const activeTab = ref('timeline')
const expandedId = ref('r8') // 默认展开最新的
const showInnateReport = ref(false)

const toggleExpand = (id) => {
  expandedId.value = expandedId.value === id ? null : id
}
const typeClass = (t) => ({ '首诊': 'first', '调理方案': 'plan', 'on-off 验证': 'verify', '重要发现': 'discover',
  '复诊': 'followup', '迭代': 'iteration', '脉诊': 'ppg', '方案': 'initial', '验证': 'verify' }[t] || 'plan')

// 最新观测 chip（动态，从 vectorStore.latestVector 读）
const latestVectorChips = computed(() => {
  const v = vectorStore.latestVector || vectorStore.vBase || vectorStore.caseSEffectiveBaseline || {}
  return elements.map(k => ({ label: labels[k], key: k, arrow: toArrow(v[k] ?? 50), value: v[k] ?? 50 }))
})

// 统计
const ppgObsCount = computed(() => reportsFull.value.filter(r => r.ppg).length)
const spanDays = computed(() => {
  if (reportsFull.value.length < 2) return 0
  const latest = new Date(reportsFull.value[0].date)
  const earliest = new Date(reportsFull.value[reportsFull.value.length - 1].date)
  return Math.round((latest - earliest) / (1000 * 60 * 60 * 24))
})

// 从 v_base 生成 S_0^0 文字描述
const s0ArrowSummary = computed(() => {
  const base = vectorStore.vBase || vectorStore.caseSEffectiveBaseline || {}
  if (!Object.keys(base).length) return '待推演'
  return elements.map(k => {
    const arrow = toArrow(base[k])
    const label = labels[k]
    return `${label}${arrow}`
  }).join(', ')
})
// 核心偏移描述：找偏离最大的 2-3 个维度
const coreDeviation = computed(() => {
  const base = vectorStore.vBase || vectorStore.caseSEffectiveBaseline || {}
  if (!Object.keys(base).length) return ''
  const degs = elements.map(k => ({ k, d: Math.abs((base[k] ?? 50) - 50), v: base[k] ?? 50 }))
  degs.sort((a, b) => b.d - a.d)
  const top = degs.filter(x => x.d > 10).slice(0, 3)
  if (!top.length) return ''
  return top.map(x => {
    const arrow = toArrow(x.v)
    const tag = labels[x.k]
    // 根据五行特性自动解释
    const descMap = {
      wood: { low: '木形偏弱（疏泄不足）', high: '木形偏旺（疏泄过亢）' },
      fire: { low: '火形偏弱（心阳不足）', high: '火形偏旺（相火妄动）' },
      earth: { low: '土形偏弱（脾失健运）', high: '土形偏旺（湿浊壅滞）' },
      metal:{ low: '金形偏弱（肺卫不固）', high: '金形偏旺（燥气偏盛）' },
      water:{ low: '水形偏弱（肾精不足）', high: '水形偏旺（水气泛滥）' },
    }
    const desc = (x.v < 50 ? descMap[x.k]?.low : descMap[x.k]?.high) || ''
    return `S_${tag}${arrow}（${desc}）`
  }).join(' + ')
})

// 先天基底完整文字报告（弹窗内容，v-html）
const innateReportHtml = computed(() => {
  const base = vectorStore.vBase || vectorStore.caseSEffectiveBaseline || {}
  const innate = vectorStore.caseSEffectiveBaseline || {}
  const patient = vectorStore.casePatient || {}
  const ganzhi = patient.birth_ganzhi || '待推演'
  const nickname = patient.name || '朋友'

  if (!Object.keys(innate).length && !Object.keys(base).length) {
    return `<p class="report-empty">尚未完成八字推演，先天基底数据为空。</p>`
  }

  const descMap = {
    wood: { low: '木形偏弱——疏泄不足，情志易低落，视力可能下降', high: '木形偏旺——疏泄过亢，性情急躁，头侧易胀痛' },
    fire: { low: '火形偏弱——心阳不足，手脚发凉，容易心悸', high: '火形偏旺——相火妄动，心烦易怒，睡眠不实' },
    earth: { low: '土形偏弱——脾失健运，食欲不振，大便不调', high: '土形偏旺——湿浊壅滞，身体沉重，舌苔厚腻' },
    metal:{ low: '金形偏弱——肺卫不固，容易感冒，皮肤干燥', high: '金形偏旺——燥气偏盛，口鼻发干，干咳少痰' },
    water:{ low: '水形偏弱——肾精不足，腰膝酸软，健忘耳鸣', high: '水形偏旺——水气泛滥，身体困重，便溏腹泻' },
  }

  // 每维度一行
  const dimRows = elements.map(k => {
    const v = base[k] ?? innate[k] ?? 50
    const arrow = toArrow(v)
    const dev = v < 50 ? descMap[k].low : (v > 50 ? descMap[k].high : '调和，无明显偏失')
    return `<div class="report-dim"><span class="dim-name" style="color:${colors[k]}">${labels[k]} ${arrow}</span><span class="dim-val">${v}</span><span class="dim-desc">${dev}</span></div>`
  }).join('')

  // 先天 vs 调理前对比
  let compareHtml = ''
  if (Object.keys(base).length && Object.keys(innate).length) {
    compareHtml = elements.map(k => {
      const v1 = innate[k] ?? 50
      const v2 = base[k] ?? 50
      const diff = (v2 - v1).toFixed(1)
      const sign = diff > 0 ? '+' : ''
      return `${labels[k]}: ${v1}→${v2} (${sign}${diff})`
    }).join(' · ')
  }

  // 核心偏移解读
  let deviationHtml = ''
  const top3 = elements.map(k => ({ k, d: Math.abs((base[k] ?? innate[k] ?? 50) - 50), v: base[k] ?? innate[k] ?? 50 }))
    .sort((a, b) => b.d - a.d).slice(0, 3)
  const significant = top3.filter(x => x.d > 8)
  if (significant.length) {
    deviationHtml = significant.map((x, i) => {
      const arrow = toArrow(x.v)
      const tag = labels[x.k]
      const desc = x.v < 50 ? descMap[x.k].low : descMap[x.k].high
      return `<p><strong>偏失 #${i+1}：</strong>${tag} ${arrow} → ${desc}</p>`
    }).join('')
  }

  // 体质定性（简单规则：看偏离最大维度）
  const primary = significant[0] || top3[0]
  let constitution = ''
  if (significant.length >= 2) {
    const pair = significant.slice(0, 2).map(x => labels[x.k]).join('+')
    constitution = `<p><strong>综合定性：</strong>以 ${pair} 失衡为主的复合偏失体质</p>`
  } else if (primary && primary.d > 8) {
    constitution = `<p><strong>综合定性：</strong>以 ${labels[primary.k]} 形偏${primary.v < 50 ? '弱' : '旺'} 为主要特征</p>`
  } else {
    constitution = `<p><strong>综合定性：</strong>先天五行较为调和，无显著偏失</p>`
  }

  return `
    <div class="report-header-block">
      <p><strong>${nickname}</strong> · 八字 ${ganzhi}</p>
      <p class="report-sub">先天基底 S_0^0 完整解读（基于 SPUM 结构化五行统一模型）</p>
    </div>
    <h3>一、五形先天分布</h3>
    <div class="report-dims">${dimRows}</div>
    ${compareHtml ? `<h3>二、先天基底 → 调理前基线 变化</h3><p class="report-compare">${compareHtml}</p>` : ''}
    <h3>三、核心偏失解读</h3>
    ${deviationHtml || '<p>五形较为调和，暂无显著偏失</p>'}
    <h3>四、体质定性</h3>
    ${constitution}
    <p class="report-footer">* 本报告基于你的出生时间推演，结合日常观测可动态修正</p>
  `
})

const baseTable = computed(() => {
  const base = vectorStore.vBase || {}
  if (!Object.keys(base).length) {
    // fallback：从 v_innate 推
    const innate = vectorStore.caseSEffectiveBaseline || {}
    return elements.map(k => ({
      k, label: labels[k], value: innate[k] ?? 50,
      color: colors[k], arrow: toArrow(innate[k] ?? 50)
    }))
  }
  return elements.map(k => ({
    k, label: labels[k], value: base[k] ?? 50,
    color: colors[k], arrow: toArrow(base[k] ?? 50)
  }))
})
const effectiveTable = computed(() => {
  const eff = vectorStore.caseSEffectiveBaseline || {}
  return elements.map(k => ({
    k, label: labels[k], value: eff[k] ?? 50,
    color: colors[k], arrow: toArrow(eff[k] ?? 50)
  }))
})
</script>

<style scoped>
.case { max-width: 960px; }

/* Hero */
.case-hero {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 20px;
  background: linear-gradient(135deg, var(--qingnang-emerald) 0%, #2A6B60 100%);
  color: #fff; border-radius: var(--radius-md); padding: 20px 24px; margin-bottom: 18px;
}
.hero-left h1 { margin: 0 0 6px; font-size: 20px; font-weight: 600; }
.hero-sub { margin: 0 0 12px; font-size: 12px; color: rgba(255,255,255,0.7); }
.hero-model { display: flex; align-items: center; gap: 10px; }
.model-label { font-size: 11px; color: rgba(255,255,255,0.6); letter-spacing: 1px; }
.model-chips { display: flex; gap: 4px; flex-wrap: wrap; }
.chip { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; background: rgba(255,255,255,0.15); }
.chip-wood { background: rgba(67,160,71,0.3); }
.chip-fire { background: rgba(216,67,21,0.3); }
.chip-earth { background: rgba(212,160,23,0.3); }
.chip-metal { background: rgba(144,164,174,0.3); }
.chip-water { background: rgba(2,136,209,0.3); }
.hero-right { display: flex; flex-direction: column; align-items: flex-end; gap: 14px; }
.stat-row { display: flex; gap: 24px; }
.stat-block { text-align: center; }
.stat-num { display: block; font-size: 24px; font-weight: 700; font-family: var(--font-mono); color: var(--qingnang-spirit); }
.stat-label { font-size: 11px; color: rgba(255,255,255,0.6); letter-spacing: 1px; }

/* 数据采集 CTA 按钮 */
.hero-cta-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px; border-radius: 20px;
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.35);
  color: #fff; font-size: 13px; font-weight: 500;
  text-decoration: none; cursor: pointer;
  backdrop-filter: blur(4px);
  transition: all 0.2s;
}
.hero-cta-btn:hover {
  background: rgba(255,255,255,0.28);
  border-color: rgba(255,255,255,0.6);
  transform: translateY(-1px);
}
.cta-arrow { font-size: 14px; opacity: 0.8; transition: transform 0.2s; }
.hero-cta-btn:hover .cta-arrow { transform: translateX(2px); }

/* Tabs */
.tabs { display: flex; gap: 6px; margin-bottom: 16px; border-bottom: 2px solid var(--ink-line); padding-bottom: 0; }
.tab-btn {
  font-size: 14px; padding: 10px 20px; border: none; background: none;
  color: var(--ink-tertiary); cursor: pointer; border-bottom: 2px solid transparent;
  margin-bottom: -2px; transition: all 0.15s; font-weight: 500;
}
.tab-btn:hover { color: var(--qingnang-emerald); }
.tab-btn.active { color: var(--qingnang-emerald); border-bottom-color: var(--qingnang-emerald); font-weight: 600; }

/* Timeline */
.tl-intro { font-size: 12px; color: var(--ink-tertiary); margin: 0 0 14px; }
.timeline { position: relative; padding-left: 28px; }
.timeline::before {
  content: ''; position: absolute; left: 8px; top: 8px; bottom: 8px;
  width: 2px; background: linear-gradient(180deg, var(--qingnang-emerald) 0%, var(--ink-line) 100%);
}

.tl-item { position: relative; margin-bottom: 12px; }
.tl-item.latest .tl-dot { background: var(--qingnang-emerald); }
.tl-item.latest .tl-summary { border-color: var(--qingnang-emerald); box-shadow: 0 2px 12px rgba(26,77,69,0.1); }

.tl-dot {
  position: absolute; left: -26px; top: 14px;
  width: 14px; height: 14px; border-radius: 50%;
  background: var(--ink-tertiary); border: 3px solid #fff;
  box-shadow: 0 0 0 2px var(--ink-tertiary);
  z-index: 2;
}
.tl-dot .dot-ring {
  position: absolute; inset: -6px; border-radius: 50%;
  border: 2px solid var(--qingnang-emerald); opacity: 0.5;
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.3); opacity: 0; }
}

/* 摘要卡 */
.tl-summary {
  background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-md);
  padding: 14px 18px; cursor: pointer; transition: all 0.15s;
}
.tl-summary:hover { border-color: rgba(26,77,69,0.3); }
.tl-summary-head {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.tl-version { font-size: 15px; font-weight: 600; color: var(--ink-primary); }
.tl-date { font-family: var(--font-mono); font-size: 12px; color: var(--ink-tertiary); }
.tl-type-badge {
  font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600; letter-spacing: 0.5px;
}
.tl-type-badge.type-first { background: rgba(216,67,21,0.1); color: var(--wuxing-fire); }
.tl-type-badge.type-plan { background: rgba(26,77,69,0.1); color: var(--qingnang-emerald); }
.tl-type-badge.type-verify { background: rgba(2,136,209,0.1); color: var(--wuxing-water); }
.tl-type-badge.type-discover { background: rgba(212,160,23,0.15); color: var(--wuxing-earth); }
.tl-type-badge.type-followup { background: rgba(123,31,162,0.1); color: #6A1B9A; }  /* 紫色 — 复诊 */
.tl-type-badge.type-iteration { background: rgba(46,125,50,0.12); color: #2E7D32; }   /* 绿色 — 迭代 */
.tl-type-badge.type-ppg { background: rgba(255,112,67,0.12); color: #E64A19; }        /* 橙色 — 脉诊 */
.tl-type-badge.type-initial { background: rgba(212,160,23,0.12); color: #8a6300; }     /* 金棕 — 初诊方案 */
.latest-badge {
  font-size: 10px; padding: 2px 8px; border-radius: 10px;
  background: rgba(67,160,71,0.12); color: var(--wuxing-wood); font-weight: 600;
}
.expand-icon { margin-left: auto; font-size: 10px; color: var(--ink-tertiary); }
.tl-delta-row { margin-top: 6px; }
.delta-text { font-size: 12px; color: var(--ink-secondary); line-height: 1.5; }

/* 展开详情 */
.tl-detail {
  margin-top: -2px; margin-bottom: 12px;
  background: linear-gradient(180deg, #fff, var(--qingnang-paper));
  border: 1px solid var(--ink-line); border-top: none; border-radius: 0 0 var(--radius-md) var(--radius-md);
  padding: 16px 20px;
  animation: slideDown 0.2s ease-out;
}
@keyframes slideDown {
  from { opacity: 0; max-height: 0; }
  to { opacity: 1; max-height: 2000px; }
}
.detail-section { margin-bottom: 14px; }
.detail-section h4 {
  font-size: 12px; color: var(--qingnang-emerald);
  text-transform: uppercase; letter-spacing: 1px; margin: 0 0 8px; font-weight: 600;
}
.detail-section p { font-size: 13px; color: var(--ink-primary); margin: 0 0 4px; line-height: 1.6; }

/* PPG 脉诊 */
.ppg-section { background: rgba(26,77,69,0.03); padding: 12px 14px; border-radius: var(--radius-sm); }
.ppg-date { font-size: 11px; color: var(--ink-tertiary); margin-bottom: 10px; }
.ppg-bars { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.ppg-bar-row { display: grid; grid-template-columns: 32px 1fr 50px 50px; gap: 8px; align-items: center; font-size: 12px; }
.ppg-label { font-weight: 600; }
.ppg-track {
  height: 10px; background: var(--ink-line); border-radius: 5px;
  position: relative; overflow: visible; display: flex; align-items: center;
}
.ppg-center {
  position: absolute; left: 50%; width: 1px; height: 14px; background: var(--ink-tertiary);
  transform: translateX(-0.5px); top: -2px;
}
.ppg-bar { height: 100%; border-radius: 5px; transition: width 0.3s; }
.ppg-bar-neg { margin-left: auto; }
.ppg-bar-pos { }
.ppg-val { font-family: var(--font-mono); font-weight: 600; text-align: right; }
.ppg-val.pos { color: var(--wuxing-wood); }
.ppg-val.neg { color: var(--wuxing-fire); }
.ppg-vobs { font-family: var(--font-mono); color: var(--ink-tertiary); text-align: right; font-size: 11px; }
.ppg-diagnosis {
  margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--ink-line);
  font-size: 12px; color: var(--ink-secondary); font-style: italic;
}

/* 处方/推导 */
.formula-strategy { background: rgba(26,77,69,0.08); padding: 8px 12px; border-radius: 4px; font-weight: 500; color: var(--qingnang-emerald); }
.formula-text { font-weight: 600; color: var(--ink-primary); }
.herbs-text { color: var(--ink-secondary); font-size: 12px; }
.adjust-text { color: var(--wuxing-water); font-weight: 500; }
.frame-text { color: var(--ink-tertiary); font-size: 12px; }
.highlight { background: rgba(212,160,23,0.1); padding: 8px 12px; border-radius: 4px; font-size: 12px; color: #7c4a00; }
.correction { background: rgba(2,136,209,0.08); padding: 6px 10px; border-radius: 4px; font-size: 12px; color: var(--wuxing-water); }

/* 两列反馈 */
.detail-section.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.sub-col { background: #fff; padding: 10px 12px; border-radius: var(--radius-sm); border: 1px solid var(--ink-line); }
.sub-col.good { border-color: rgba(67,160,71,0.3); background: rgba(67,160,71,0.04); }
.sub-col.bad { border-color: rgba(216,67,21,0.3); background: rgba(216,67,21,0.04); }
.sub-col h5 { margin: 0 0 6px; font-size: 11px; color: var(--ink-tertiary); text-transform: uppercase; letter-spacing: 0.5px; }
.sub-col p { font-size: 12px; color: var(--ink-primary); margin: 0; line-height: 1.5; }

/* ═══ 先天基底 tab ═══ */
.card { background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-md); padding: 18px 20px; margin-bottom: 16px; }
.card h2 { margin: 0 0 12px; font-size: 15px; color: var(--ink-primary); border-bottom: 2px solid rgba(26,77,69,0.1); padding-bottom: 8px; }

.s0-desc { background: rgba(212,160,23,0.08); padding: 8px 12px; border-radius: 4px; color: #7c4a00; font-family: var(--font-mono); margin: 8px 0 14px; font-size: 12px; letter-spacing: 1px; }

.vector-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.vector-col h3 { font-size: 12px; color: var(--ink-tertiary); margin: 0 0 10px; }
.bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 12px; }
.bar-label { width: 28px; font-weight: 600; }
.bar-track { flex: 1; height: 12px; background: var(--qingnang-paper); border-radius: 3px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 3px; }
.bar-value { width: 28px; text-align: right; color: var(--ink-secondary); font-family: var(--font-mono); }
.bar-arrow { width: 36px; text-align: left; color: var(--wuxing-fire); font-family: var(--font-mono); font-weight: 600; font-size: 11px; }

.paradox-hint { background: rgba(216,67,21,0.06); border-left: 4px solid var(--wuxing-fire); padding: 8px 12px; border-radius: 0 4px 4px 0; margin-top: 14px; color: #991b1b; font-size: 13px; }

/* 病机链 */
.pathogenesis { display: flex; flex-direction: column; gap: 10px; }
.patho-step { display: flex; gap: 12px; }
.patho-num {
  flex-shrink: 0; width: 52px; height: 26px;
  background: var(--qingnang-emerald); color: #fff; border-radius: 13px;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600;
}
.patho-body { flex: 1; background: var(--qingnang-paper); border-radius: var(--radius-sm); padding: 10px 12px; }
.patho-body h4 { margin: 0 0 4px; font-size: 13px; color: var(--ink-primary); }
.patho-desc { margin: 0; font-size: 12px; color: var(--ink-secondary); line-height: 1.5; }
.patho-shift { margin: 6px 0 0; font-size: 11px; color: #92400e; font-family: var(--font-mono); }

.paradoxes { margin-top: 16px; background: linear-gradient(135deg, rgba(212,160,23,0.06), rgba(216,67,21,0.03)); border: 1px solid rgba(212,160,23,0.2); border-radius: var(--radius-sm); padding: 12px 14px; }
.paradoxes h4 { margin: 0 0 8px; color: #9a3412; font-size: 13px; }
.paradox-item { margin-bottom: 8px; font-size: 12px; color: var(--ink-primary); }
.paradox-item em { display: block; color: #7c4a00; font-size: 11px; margin-top: 2px; font-style: normal; background: rgba(212,160,23,0.1); padding: 3px 8px; border-radius: 3px; }

/* ═══ 调理方案 tab ═══ */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.col h2 { margin-top: 0; }
.strategy { background: rgba(67,160,71,0.08); padding: 10px 14px; border-radius: var(--radius-sm); color: #166534; margin: 0 0 14px; font-size: 12px; line-height: 1.6; }
.delta-target .dt-row { font-size: 12px; padding: 5px 0; border-bottom: 1px dashed var(--ink-line); }
.delta-target .dt-row:last-child { border-bottom: none; }
.delta-target strong { width: 24px; display: inline-block; font-weight: 700; }

.ls-row { margin-bottom: 10px; }
.ls-row strong { display: block; font-size: 12px; color: var(--ink-primary); margin-bottom: 2px; }
.ls-row p { margin: 0; font-size: 11px; color: var(--ink-tertiary); line-height: 1.5; }
.card h4 { margin: 14px 0 6px; font-size: 12px; color: var(--ink-secondary); font-weight: 600; }
.ls-list { margin: 4px 0; padding-left: 16px; font-size: 12px; color: var(--ink-primary); }
.ls-list li { margin-bottom: 3px; line-height: 1.5; }

/* 禁忌 */
.contra { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
.contra-col h4 { margin: 0 0 6px; font-size: 12px; color: var(--wuxing-fire); font-weight: 600; }
.contra-col ul { margin: 0; padding-left: 16px; font-size: 12px; color: var(--ink-primary); }
.contra-col li { margin-bottom: 4px; line-height: 1.5; }

@media (max-width: 720px) {
  .case-hero { flex-direction: column; }
  .hero-right { align-items: flex-start; }
  .vector-compare, .two-col, .contra { grid-template-columns: 1fr; }
  .detail-section.two-col { grid-template-columns: 1fr; }
}

/* ═══ 历史调理方案档案 ═══ */
.current-plan-card {
  border: 2px solid var(--qingnang-emerald);
  background: linear-gradient(135deg, rgba(23,83,76,0.04) 0%, rgba(23,83,76,0.01) 100%);
}
.cp-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.cp-current-badge {
  background: var(--qingnang-emerald); color: #fff;
  padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;
}
.cp-version { font-size: 15px; font-weight: 700; color: var(--qingnang-emerald); letter-spacing: 1px; }
.cp-date { font-size: 12px; color: var(--ink-tertiary); margin-left: auto; }
.cp-strategy { margin: 0 0 8px; font-size: 15px; color: var(--ink-primary); font-weight: 600; }
.cp-prescription { margin: 0 0 14px; font-size: 13px; color: var(--ink-secondary); line-height: 1.6; }
.cp-herbs, .cp-reasoning, .cp-avoid { margin-top: 14px; }
.cp-herbs h4, .cp-reasoning h4, .cp-avoid h4 {
  margin: 0 0 8px; font-size: 12px; color: var(--ink-tertiary); font-weight: 600; letter-spacing: 0.5px;
}
.cp-reasoning p { margin: 0; font-size: 13px; line-height: 1.7; color: var(--ink-secondary); }
.cp-avoid p { margin: 0; font-size: 12px; color: #A8442F; }
.herb-list { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.9; color: var(--ink-primary); }
.herb-list-sm { margin: 0; padding-left: 16px; font-size: 12px; line-height: 1.8; color: var(--ink-secondary); }

.plan-timeline-header {
  display: flex; justify-content: space-between; align-items: center;
  margin: 24px 0 12px; padding-bottom: 8px; border-bottom: 1px dashed rgba(26,77,69,0.15);
}
.pt-title { font-size: 14px; font-weight: 600; color: var(--ink-primary); }
.pt-count { font-size: 12px; color: var(--ink-tertiary); }

.plan-history { display: flex; flex-direction: column; gap: 10px; }
.plan-item {
  background: var(--qingnang-paper); border-radius: 10px;
  overflow: hidden; border: 1px solid rgba(26,77,69,0.08); transition: all 0.2s;
}
.plan-item.expanded { border-color: var(--qingnang-emerald); box-shadow: 0 2px 12px rgba(23,83,76,0.08); }
.plan-head {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px; cursor: pointer; user-select: none;
  transition: background 0.15s;
}
.plan-head:hover { background: rgba(26,77,69,0.03); }
.plan-version { font-weight: 700; color: var(--ink-primary); font-family: var(--font-mono); font-size: 14px; }
.plan-type-badge {
  font-size: 10px; padding: 2px 8px; border-radius: 8px; font-weight: 500;
}
.plan-type-badge.type-iteration { background: rgba(23,83,76,0.1); color: var(--qingnang-emerald); }
.plan-type-badge.type-validation { background: rgba(168,68,47,0.1); color: #A8442F; }
.plan-type-badge.type-initial { background: rgba(212,160,23,0.12); color: #8a6300; }
.plan-date { font-size: 12px; color: var(--ink-tertiary); margin-left: auto; }
.plan-expand { color: var(--ink-tertiary); font-size: 11px; }
.plan-body {
  padding: 0 16px 14px; border-top: 1px solid rgba(26,77,69,0.06); padding-top: 12px;
}
.plan-strategy { margin: 0 0 6px; font-size: 13px; font-weight: 500; color: var(--ink-primary); }
.plan-prescription { margin: 0 0 10px; font-size: 12px; color: var(--ink-secondary); line-height: 1.6; }
.plan-herbs h5, .plan-reasoning h5 {
  margin: 10px 0 4px; font-size: 11px; color: var(--ink-tertiary); font-weight: 600;
}
.plan-reasoning p { margin: 0; font-size: 12px; line-height: 1.7; color: var(--ink-secondary); }

.empty-state { text-align: center; padding: 40px; color: var(--ink-tertiary); font-size: 13px; }

/* ═══ 弹窗 ═══ */
.clickable-card { cursor: pointer; transition: box-shadow .2s; }
.clickable-card:hover { box-shadow: 0 6px 24px rgba(26,77,69,0.2); }
.card-hint { font-size: 12px; color: var(--qingnang-emerald); font-weight: 400; margin-left: 8px; }
.paradox-hint.muted { color: var(--ink-tertiary); font-size: 12px; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 3000; display: flex; align-items: center; justify-content: center; padding: 24px; }
.modal-content { background: #fff; border-radius: 16px; max-width: 640px; width: 100%; max-height: 80vh; overflow: hidden; display: flex; flex-direction: column; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 18px 24px; border-bottom: 1px solid var(--ink-line); flex-shrink: 0; }
.modal-header h2 { margin: 0; font-size: 16px; font-weight: 600; }
.modal-close { border: none; background: none; font-size: 18px; cursor: pointer; color: var(--ink-tertiary); padding: 4px 8px; }
.modal-body { padding: 20px 24px; overflow-y: auto; line-height: 1.7; color: var(--ink-primary); font-size: 14px; }

/* 报告内容样式（v-html 渲染） */
.modal-body h3 { margin: 18px 0 10px; font-size: 14px; font-weight: 600; color: var(--qingnang-emerald); border-bottom: 1px solid rgba(26,77,69,0.1); padding-bottom: 4px; }
.modal-body p { margin: 6px 0; }
.modal-body strong { color: var(--ink-primary); }
.report-header-block { background: linear-gradient(135deg, rgba(26,77,69,0.06), rgba(46,125,106,0.1)); border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; }
.report-header-block p { margin: 2px 0; }
.report-sub { color: var(--ink-tertiary); font-size: 12px; }
.report-dims { display: flex; flex-direction: column; gap: 8px; margin-bottom: 8px; }
.report-dim { display: flex; align-items: baseline; gap: 12px; padding: 6px 10px; background: rgba(26,77,69,0.03); border-radius: 6px; }
.dim-name { font-weight: 600; min-width: 72px; font-size: 14px; }
.dim-val { font-family: var(--font-mono); color: var(--ink-tertiary); min-width: 30px; font-size: 12px; }
.dim-desc { flex: 1; font-size: 13px; color: var(--ink-secondary); }
.report-compare { font-family: var(--font-mono); font-size: 12px; color: var(--ink-secondary); padding: 8px 12px; background: rgba(26,77,69,0.03); border-radius: 6px; }
.report-footer { margin-top: 20px; color: var(--ink-tertiary); font-size: 11px; font-style: italic; }
.report-empty { text-align: center; padding: 40px; color: var(--ink-tertiary); }

/* 弹窗过渡 */
.modal-enter-active, .modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-content, .modal-leave-active .modal-content { transition: transform .2s; }
.modal-enter-from .modal-content, .modal-leave-to .modal-content { transform: scale(0.96); }
</style>

