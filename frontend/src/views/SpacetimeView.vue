<!-- ═══════════════════════════════════════════════════════════
  SpacetimeView.vue — 时空详情页
  英雄卡 + 黄历日历 + 宜忌 + 十二时辰 + 调候报告 + AI 解读
══════════════════════════════════════════════════════════════ -->
<template>
  <div class="st-page page">
    <!-- 顶部导航 -->
    <div class="st-nav">
      <button class="st-back" @click="$router.back()">‹ 返回</button>
      <span class="st-nav-title">时空</span>
      <span class="st-nav-spacer"></span>
    </div>

    <!-- ═══ 英雄卡（静态展示） ═══ -->
    <div v-if="ctx" class="st-hero-mini">
      <div class="st-top">
        <div class="st-gz-row">
        <span v-for="key in ['year','month','day','hour']" :key="key" class="st-gz-cell">
          <span class="st-gz-zhi">{{ (ctx.sizhu?.ganzhi?.[key] || ['',''])[1] }}</span>
          <span class="st-gz-tg">{{ (ctx.sizhu?.ganzhi?.[key] || ['',''])[0] }}</span>
        </span>
      </div>
        <div class="st-qi-col">
          <span class="st-qi-val">🌤️ {{ (typeof ctx.jieqi === 'string') ? ctx.jieqi : (ctx.jieqi?.current_term || '--') }}</span>
        </div>
      </div>
      <div class="st-lingshou-row">
        <div class="st-ls-pill">
          <span class="st-ls-label">当令</span>
          <span class="st-ls-gz">{{ ctx.lingshou_gz }}</span>
        </div>
        <div class="st-wx-bars">
          <div v-for="wx in wxList" :key="wx" class="st-bar-cell" :class="'stb-' + wx">
            <span class="stb-wx">{{ wxCn(wx) }}</span>
            <span class="stb-status" :class="'sts-' + (ctx.wuxing_status[wx] || '平')">
              {{ ctx.wuxing_status[wx] || '平' }}
            </span>
          </div>
        </div>
      </div>
      <div v-if="tiaoHou" class="st-th-line">
        <span class="st-th-emoji">{{ thEmoji }}</span>
        <span class="st-th-text">{{ tiaoHou.summary }}</span>
      </div>
    </div>

    <!-- ═══ 黄历日历 ═══ -->
    <div class="st-section">
      <div class="sec-head">
        <span class="sec-title"><span class="sec-dot"></span>黄历日历</span>
        <div class="cal-nav">
          <button @click="prevMonth" class="cal-btn">‹</button>
          <span class="cal-title">{{ calYear }}年{{ calMonth + 1 }}月</span>
          <button @click="nextMonth" class="cal-btn">›</button>
        </div>
      </div>
      <div class="cal-weekdays">
        <span v-for="w in ['日','一','二','三','四','五','六']" :key="w" class="cal-wd">{{ w }}</span>
      </div>
      <div class="cal-grid">
        <div v-for="(cell, i) in calCells" :key="i"
             class="cal-cell"
             :class="{
               today: cell.isToday, other: !cell.inMonth, selected: cell.isSelected,
               'has-jq': cell.jieqi,
             }"
             @click="selectDate(cell)">
          <span class="cal-day">{{ cell.day || '' }}</span>
          <template v-if="cell.inMonth">
            <span class="cal-jq" v-if="cell.jieqi">{{ cell.jieqi }}</span>
            <span class="cal-lunar" v-else>{{ cell.lunar }}</span>
          </template>
        </div>
      </div>

      <!-- 选中日期的完整详情 -->
      <div v-if="dayDetail" class="cal-detail">
        <div class="cd-head">
          <span class="cd-date">{{ dayDetail.date }}</span>
          <span class="cd-gz">{{ dayDetail.ganzhi_year }} {{ dayDetail.ganzhi_month }} {{ dayDetail.ganzhi_day }}</span>
          <span class="cd-lunar">{{ dayDetail.lunar_month }}月{{ dayDetail.lunar_day }} · {{ dayDetail.shengxiao }}</span>
        </div>
        <div class="cd-meta">
          <span class="cd-jc">{{ dayDetail.jianchu }}日</span>
          <span class="cd-tianshen" :class="dayDetail.tianshen_luck === '吉' ? 't-good' : 't-bad'">
            {{ dayDetail.tianshen_type }} · {{ dayDetail.tianshen_luck }}
          </span>
          <span class="cd-xiu">{{ dayDetail.xiu }}宿 {{ dayDetail.xiu_luck }}</span>
          <span class="cd-chong" v-if="dayDetail.chong">冲{{ dayDetail.chong }}</span>
          <span class="cd-sha" v-if="dayDetail.sha">煞{{ dayDetail.sha }}</span>
        </div>
        <div v-if="dayDetail.festival" class="cd-festival">
          <span class="cd-f-label">三元五腊</span>
          <span class="cd-f-name">{{ dayDetail.festival }}</span>
        </div>
        <div class="cd-yj">
          <div class="cd-row"><span class="cd-k g">宜</span><span class="cd-v">{{ (dayDetail.yi||[]).join('、') || '无' }}</span></div>
          <div class="cd-row"><span class="cd-k b">忌</span><span class="cd-v">{{ (dayDetail.ji||[]).join('、') || '无' }}</span></div>
        </div>
        <div v-if="dayDetail.pengzu" class="cd-pz">彭祖百忌：{{ dayDetail.pengzu }}</div>
        <div v-if="(dayDetail.ji_shen||[]).length" class="cd-shen">
          <span class="cd-shen-label">吉神：</span>
          <span class="cd-shen-v">{{ dayDetail.ji_shen.join('、') }}</span>
        </div>
      </div>
    </div>

    <!-- ═══ 十二时辰 ═══ -->
    <div class="st-section">
      <div class="sec-head">
        <span class="sec-title"><span class="sec-dot"></span>十二时辰当令</span>
        <span class="sec-sub">你的体质节律</span>
      </div>

      <div class="legend-row">
        <span><i class="lg g"></i>助我</span>
        <span><i class="lg w"></i>平</span>
        <span><i class="lg b"></i>耗我</span>
      </div>

      <div class="sh-axis">
        <button v-for="sc in timeline" :key="sc.period"
                class="sh-btn" :class="[periodClass(sc), { now: isNow(sc) }]"
                @click="activePeriod = activePeriod === sc.period ? null : sc.period">
          <span class="sh-n">{{ shortPeriod(sc.period) }}</span>
          <span class="sh-r">{{ sc.range }}</span>
        </button>
      </div>

      <div v-if="activeDetail" class="period-detail">
        <div class="pd-head">
          <span class="pd-badge" :class="'g-' + periodClass(activeDetail)">{{ activeDetail.personal_label || '平' }}</span>
          <span class="pd-name">{{ activeDetail.period }} {{ activeDetail.range }}</span>
        </div>
        <div class="pd-why">{{ activeDetail.desc || activeDetail.elem + '时' }}</div>
      </div>
    </div>

    <!-- ═══ 时空调候报告 ═══ -->
    <div v-if="tiaoHou" class="st-section">
      <div class="sec-head">
        <span class="sec-title" style="--dot-color:#43A047"><span class="sec-dot"></span>时空调候报告</span>
        <span class="sec-sub">时空 × 体质 动态推演</span>
      </div>

      <div class="th-summary">
        <span class="th-emoji">{{ thEmoji }}</span>
        <span class="th-text">{{ tiaoHou.summary }}</span>
      </div>

      <div class="th-priorities">
        <div v-for="(p, i) in tiaoHou.priorities" :key="i" class="th-pri" :class="'p-' + p.direction">
          <div class="thp-top">
            <span class="thp-cn">{{ p.cn }}形</span>
            <span class="thp-dir" :class="'d-' + p.direction">{{ p.direction }}</span>
          </div>
          <div class="thp-raw">静态偏值 {{ p.raw?.toFixed(1) || '-' }}（{{ p.status || '平' }}）</div>
          <div class="thp-why">
            <template v-if="p.chain_from">五形{{ p.chain_from }}→{{ p.cn }}→{{ p.chain_to }}链{{ p.peaks?.length ? '，'+p.peaks.join('/')+'形堆积为峰' : '' }}{{ p.valleys?.length ? '，'+p.valleys.join('/')+'形匮乏为谷' : '' }}</template>
            {{ p.reason }}
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ AI 解读 Modal ═══ -->
    <div v-if="showExplain" class="modal-mask" @click="showExplain = false">
      <div class="modal-body" @click.stop>
        <div class="modal-head">
          <span class="modal-title">🤖 AI 解读 · 今日时空</span>
          <button class="modal-close" @click="showExplain = false">✕</button>
        </div>
        <div class="modal-content" :class="{ loading: explaining }">
          <div v-if="explaining" class="loading-dots">解读中…</div>
          <div v-else-if="explainText" class="explain-text" v-html="explainText"></div>
          <div v-else class="loading-dots">点击上方触发解读</div>
        </div>
        <div class="modal-foot">
          <button class="btn-retry" @click="fetchExplain">重新解读</button>
          <button class="btn-close" @click="showExplain = false">关闭</button>
        </div>
      </div>
    </div>

    <div class="compliance">内容由 AI 生成，仅供参考 · 不构成医疗状态描述</div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { api } from '../api/client'
import { isNowPeriod, periodColorClass } from '../utils/almanac'

// ── 时空数据 ──
const ctx = ref(null)
const tiaoHou = ref(null)
const anchor = ref(null)
const timeline = ref([])

const WX_CN = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
function wxCn(w) { return WX_CN[w] || w }
const wxList = ['wood', 'fire', 'earth', 'metal', 'water']

const thEmoji = computed(() => {
  if (!tiaoHou.value?.priorities?.length) return '🧭'
  const map = { '增益': '🔧', '顺势增益': '✨', '增益待时': '⏸', '不干预': '⚖️' }
  return map[tiaoHou.value.priorities[0].direction] || '🧭'
})

const jianchuDesc = computed(() => {
  const jc = ctx.value?.jianchu
  const map = { '建':'宜出行、赴任、开市', '除':'宜除服、解除、打扫', '满':'宜祈福、嫁娶、出行', '平':'平常日',
    '定':'宜冠笄、订婚', '执':'宜捕捉、畋猎', '破':'破日、诸事不宜', '危':'危日、宜守不宜攻',
    '成':'宜嫁娶、签约、开市', '收':'宜收敛、纳财', '开':'宜祭祀、出行、开市', '闭':'闭日、诸事不宜' }
  return map[jc] || '平日'
})

// ── 日历 ──
const today = new Date()
const calYear = ref(today.getFullYear())
const calMonth = ref(today.getMonth())  // 0-indexed
const selectedDate = ref(today.getDate())
const monthlyData = ref({})   // { day: { lunar, jieqi, jianchu } }
const dayDetail = ref(null)

function prevMonth() {
  if (calMonth.value === 0) { calMonth.value = 11; calYear.value-- }
  else calMonth.value--
}
function nextMonth() {
  if (calMonth.value === 11) { calMonth.value = 0; calYear.value++ }
  else calMonth.value++
}

// 日历格子：从 monthlyData 合并农历/节气/建除
const calCells = computed(() => {
  const firstDay = new Date(calYear.value, calMonth.value, 1).getDay()
  const daysInMonth = new Date(calYear.value, calMonth.value + 1, 0).getDate()
  const cells = []
  const prevDays = new Date(calYear.value, calMonth.value, 0).getDate()
  for (let i = firstDay - 1; i >= 0; i--) {
    cells.push({ day: prevDays - i, inMonth: false, date: prevDays - i, lunar: '', jieqi: false, isToday: false, isSelected: false })
  }
  const isCurMonth = (calYear.value === today.getFullYear() && calMonth.value === today.getMonth())
  for (let d = 1; d <= daysInMonth; d++) {
    const md = monthlyData.value[d] || {}
    cells.push({
      day: d, inMonth: true, date: d,
      lunar: md.lunar || '',
      jieqi: md.jieqi || '',
      festival: md.festival || '',
      jianchu: md.jianchu || '',
      isToday: isCurMonth && d === today.getDate(),
      isSelected: d === selectedDate.value,
    })
  }
  const total = cells.length
  const pad = (7 - total % 7) % 7
  for (let d = 1; d <= pad; d++) {
    cells.push({ day: d, inMonth: false, date: d, lunar: '', jieqi: false, isToday: false, isSelected: false })
  }
  return cells
})

function selectDate(cell) {
  if (!cell.inMonth) return
  selectedDate.value = cell.date
  fetchDayDetail()
}

// 拉月历（切换月份时触发）
let _monthlyLoading = false
async function fetchMonthly() {
  if (_monthlyLoading) return
  _monthlyLoading = true
  try {
    const r = await api.get('/api/v1/spacetime/monthly', {
      params: { year: calYear.value, month: calMonth.value + 1 }  // 后端 month 1-indexed
    })
    const obj = {}
    for (const d of r.data?.days || []) {
      obj[d.day] = { lunar: d.lunar || '', jieqi: d.jieqi || '', festival: d.festival || '', jianchu: d.jianchu || '' }
    }
    monthlyData.value = obj
  } catch (e) {
    console.warn('[Spacetime] monthly 加载失败:', e.message)
  } finally {
    _monthlyLoading = false
  }
}

// 拉单日详情（选中日期时触发）
async function fetchDayDetail() {
  const mm = String(calMonth.value + 1).padStart(2, '0')
  const dd = String(selectedDate.value).padStart(2, '0')
  const dateStr = `${calYear.value}-${mm}-${dd}`
  try {
    const r = await api.get('/api/v1/spacetime/day-detail', { params: { date: dateStr } })
    dayDetail.value = r.data
  } catch (e) {
    console.warn('[Spacetime] day-detail 加载失败:', e.message)
    dayDetail.value = null
  }
}

// 监听月份变化 → 重新拉月历
watch([calYear, calMonth], () => {
  monthlyData.value = {}
  fetchMonthly()
  // 选中月份第一天
  selectedDate.value = 1
  fetchDayDetail()
})

// ── 时辰 ──
const activePeriod = ref(null)
function periodClass(sc) { return periodColorClass(sc) }
function isNow(sc) { return isNowPeriod(sc) }
function shortPeriod(p) { return String(p || '').replace('时', '') }
const activeDetail = computed(() =>
  timeline.value.find(s => s?.period === activePeriod.value) || null
)

// ── AI 解读 ──
const showExplain = ref(false)
const explaining = ref(false)
const explainText = ref('')

async function fetchExplain() {
  explaining.value = true
  explainText.value = ''
  try {
    const body = {
      ganzhi: ctx.value?.ganzhi || '',
      dangling: ctx.value?.lingshou_gz || '',
      jianchu: ctx.value?.jianchu || '',
      yi: ctx.value?.jianchu_advice?.good || '',
      ji: ctx.value?.jianchu_advice?.bad || '',
      wuxing_status: ctx.value?.wuxing_status || {},
      jianchu_advice: ctx.value?.jianchu_advice || {},
      tiao_hou: tiaoHou.value || {},
      jieqi: ctx.value?.jieqi?.current_term || '',
    }
    const r = await api.post('/api/v1/assistant/reasoning/anchor-explain', body, { timeout: 30000 })
    explainText.value = (r.data.explain || '').replace(/\n/g, '<br>')
  } catch (e) {
    explainText.value = `AI 暂时离线，使用本地解读：<br><br>${localFallback()}`
  } finally {
    explaining.value = false
  }
}

function localFallback() {
  const lines = []
  if (ctx.value?.lingshou_gz) lines.push(`当令${ctx.value.lingshou_gz}——今天${ctx.value.lingshou || ''}形气场最强`)
  if (tiaoHou.value?.summary) lines.push(tiaoHou.value.summary)
  if (ctx.value?.jianchu) lines.push(`${ctx.value.jianchu}日——${jianchuDesc.value}`)
  return lines.join('<br>')
}

watch(showExplain, v => { if (v && !explainText.value) fetchExplain() })

// ── 加载数据 ──
async function loadAll() {
  try {
    const r = await api.get('/api/v1/spacetime/daily-brief', { timeout: 5000 })
    const d = r.data
    ctx.value = d.ctx
    tiaoHou.value = d.tiao_hou
  } catch {
    try {
      const r2 = await api.get('/api/v1/spacetime/context', { timeout: 3000 })
      ctx.value = r2.data
    } catch {}
  }

  // 拉 anchor 数据（时辰 + 宜忌）
  try {
    const r3 = await api.get('/api/v1/cases/anchor', { timeout: 5000 })
    anchor.value = r3.data
    timeline.value = r3.data.timeline || []
  } catch {
    // 用 fallback 生成时辰轴
    timeline.value = fallbackTimeline()
  }
}

function fallbackTimeline() {
  const periods = [
    { period: '子时', range: '23:00-01:00', elem: '水' },
    { period: '丑时', range: '01:00-03:00', elem: '土' },
    { period: '寅时', range: '03:00-05:00', elem: '木' },
    { period: '卯时', range: '05:00-07:00', elem: '木' },
    { period: '辰时', range: '07:00-09:00', elem: '土' },
    { period: '巳时', range: '09:00-11:00', elem: '火' },
    { period: '午时', range: '11:00-13:00', elem: '火' },
    { period: '未时', range: '13:00-15:00', elem: '土' },
    { period: '申时', range: '15:00-17:00', elem: '金' },
    { period: '酉时', range: '17:00-19:00', elem: '金' },
    { period: '戌时', range: '19:00-21:00', elem: '土' },
    { period: '亥时', range: '21:00-23:00', elem: '水' },
  ]
  const now = new Date().getHours()
  return periods.map(p => ({
    ...p,
    personal_type: 'n', personal_label: '平',
    is_current: (p.period === '子时' && now === 0) ||
                (now >= parseInt(p.range.split(':')[0])),
  }))
}

onMounted(async () => {
  // 并行拉：daily-brief + 月历 + day-detail + anchor
  loadAll()
  fetchMonthly()
  fetchDayDetail()
})
</script>

<style scoped>
/* ═════════════════════════════════════════════════════════════
   2026-10-14 重构：全量 token 化 + 暗色 scoped 覆盖 + 宽屏限宽
   ────────────────────────────────────────────────────────────
   · 全部硬编码 hex → var(--qn-*) token
   · 英雄卡五形色 → var(--qn-wood/fire/earth/metal/water)
   · 通用 card/section 背景 → var(--qn-surface) / --qn-surface-page
   · 描边 → var(--qn-line) / --qn-border-subtle
   · 主文字 → var(--qn-text-primary)
   · 次文字 → var(--qn-text-secondary)
   · 辅助 → var(--qn-text-tertiary)
   · 品牌绿 → var(--qn-brand-*) 系列
   · 暗色覆盖：html[data-theme="dark"] scoped 块（文末）
   ═════════════════════════════════════════════════════════════ */

.st-page { min-height: 100vh; padding-bottom: 40px; }

/* ── 顶部导航 ── */
.st-nav {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px;
  background: var(--qn-surface);
  border-bottom: 1px solid var(--qn-line);
  position: sticky; top: 0; z-index: 10;
}
.st-back {
  font-size: 13px; color: var(--qn-brand-800); background: none; border: none;
  padding: 4px 8px; border-radius: 6px; cursor: pointer;
}
.st-nav-title { font-size: 15px; font-weight: 700; color: var(--qn-text-primary); margin-left: 4px; }
.st-nav-spacer { flex: 1; }

/* ── 英雄卡（mini 版） — 品牌绿渐变，暗色下调亮 ── */
.st-hero-mini {
  background: linear-gradient(135deg, var(--qn-brand-900) 0%, var(--qn-brand-800) 40%, var(--qn-brand-600) 100%);
  margin: 10px 12px; border-radius: 16px; padding: 14px 16px; color: var(--qn-text-on-brand);
  box-shadow: 0 4px 16px rgba(var(--qn-brand-rgb),0.25);
}
.st-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.st-gz-row { display: flex; gap: 6px; }
.st-gz-cell {
  display: flex; flex-direction: column; align-items: center;
  padding: 4px 7px; background: rgba(255,255,255,0.12);
  border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);
}
.st-gz-zhi { font-size: 16px; font-weight: 700; line-height: 1.1; }
.st-gz-tg { font-size: 10px; color: rgba(255,255,255,0.75); line-height: 1; }
.st-qi-col { display: flex; flex-direction: column; align-items: flex-end; padding-top: 4px; }
.st-qi-val { font-size: 12px; color: rgba(255,255,255,0.85); }

.st-lingshou-row { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; }
.st-ls-pill {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 10px; background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.2); border-radius: 16px; flex-shrink: 0;
}
.st-ls-label { font-size: 10px; color: rgba(255,255,255,0.7); }
.st-ls-gz { font-size: 13px; font-weight: 700; }

.st-wx-bars { display: flex; gap: 4px; flex: 1; }
.st-bar-cell {
  flex: 1; display: flex; flex-direction: column; align-items: center; gap: 1px;
  padding: 4px 2px; background: rgba(255,255,255,0.08); border-radius: 6px;
  border-top: 2px solid transparent;
}
.stb-wood { border-top-color: var(--qn-wood); } .stb-fire { border-top-color: var(--qn-fire); }
.stb-earth { border-top-color: var(--qn-earth); } .stb-metal { border-top-color: var(--qn-metal); }
.stb-water { border-top-color: var(--qn-water); }
.stb-wx { font-size: 11px; font-weight: 600; }
.stb-status { font-size: 9px; font-weight: 600; padding: 1px 4px; border-radius: 6px; }
.sts-旺 { background: rgba(var(--qn-wood-rgb),0.35); color: #a5d6a7; }
.sts-相 { background: rgba(var(--qn-wood-rgb),0.20); color: #c8e6c9; }
.sts-休 { background: rgba(var(--qn-metal-rgb),0.25); color: #cfd8dc; }
.sts-囚 { background: rgba(var(--qn-earth-rgb),0.30); color: #ffe082; }
.sts-死 { background: rgba(var(--qn-fire-rgb),0.30); color: #ef9a9a; }
.sts-平 { background: rgba(255,255,255,0.15); color: rgba(255,255,255,0.7); }

.st-th-line {
  display: flex; gap: 8px; align-items: flex-start;
  padding: 8px 12px; background: rgba(255,255,255,0.1); border-radius: 10px;
}
.st-th-emoji { font-size: 16px; flex-shrink: 0; }
.st-th-text { font-size: 12px; color: rgba(255,255,255,0.9); line-height: 1.55; }

/* ── 通用 section ── */
.st-section {
  background: var(--qn-surface); margin: 10px 12px; border-radius: 14px;
  border: 1px solid var(--qn-border-subtle); overflow: hidden;
}
.sec-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 13px 14px 0;
}
.sec-title { font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.sec-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--qn-brand-800); flex-shrink: 0; }
.sec-sub { font-size: 11px; color: var(--qn-text-tertiary); }

/* ── 日历 ── */
.cal-nav { display: flex; align-items: center; gap: 6px; }
.cal-btn {
  width: 26px; height: 26px; border-radius: 6px; border: 1px solid var(--qn-border-subtle);
  background: var(--qn-surface); cursor: pointer; font-size: 14px; color: var(--qn-text-secondary);
}
.cal-title { font-size: 12px; font-weight: 600; color: var(--qn-text-primary); min-width: 80px; text-align: center; }

.cal-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); padding: 8px 10px 4px; }
.cal-wd { text-align: center; font-size: 11px; color: var(--qn-text-tertiary); font-weight: 500; }

.cal-grid {
  display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px;
  padding: 2px 8px 10px;
}
.cal-cell {
  aspect-ratio: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; border-radius: 8px; cursor: pointer;
  background: var(--qn-surface-page); border: 1px solid transparent;
  transition: background .15s, border-color .15s;
}
.cal-cell:hover { background: var(--qn-brand-050); }
.cal-cell.other { background: transparent; color: var(--qn-ink-3); }
.cal-cell.today { background: var(--qn-brand-800); color: var(--qn-text-on-brand); font-weight: 600; }
.cal-cell.selected { border-color: var(--qn-earth); box-shadow: 0 0 0 2px rgba(var(--qn-earth-rgb),0.2); }
.cal-cell.has-jq { color: var(--qn-fire); }
.cal-day { font-size: 14px; font-weight: 500; }
.cal-cell.today .cal-lunar, .cal-cell.today .cal-jq { color: rgba(255,255,255,0.85); }
.cal-lunar { font-size: 9px; color: var(--qn-text-tertiary); margin-top: 1px; }
.cal-jq { font-size: 9px; color: var(--qn-fire); margin-top: 1px; font-weight: 600; }
.cal-cell.today .cal-jq { color: rgba(255,255,255,0.9); }

/* ── 选中日期详情卡 ── */
.cal-detail {
  margin: 8px 10px 10px; padding: 12px 14px;
  background: var(--qn-surface-page); border-radius: 10px; border: 1px solid var(--qn-border-subtle);
}
.cd-head { display: flex; flex-direction: column; gap: 2px; margin-bottom: 8px; }
.cd-date { font-size: 13px; font-weight: 700; color: var(--qn-text-primary); }
.cd-gz { font-size: 11px; color: var(--qn-text-secondary); letter-spacing: 0.5px; }
.cd-lunar { font-size: 11px; color: var(--qn-text-tertiary); }
.cd-meta {
  display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 10px;
  padding-bottom: 8px; border-bottom: 1px solid var(--qn-border-subtle);
}
.cd-meta span {
  font-size: 10.5px; padding: 2px 8px; border-radius: 10px;
  border: 1px solid var(--qn-border-subtle); background: var(--qn-surface);
}
.cd-jc { font-weight: 600; color: var(--qn-text-primary); }
.cd-tianshen.t-good { color: var(--qn-wood); border-color: rgba(var(--qn-wood-rgb),0.3); background: rgba(var(--qn-wood-rgb),0.08); }
.cd-tianshen.t-bad { color: var(--qn-fire); border-color: rgba(var(--qn-fire-rgb),0.3); background: rgba(var(--qn-fire-rgb),0.08); }
.cd-xiu { color: #8A6A18; background: rgba(var(--qn-earth-rgb),0.08); border-color: rgba(var(--qn-earth-rgb),0.25); }
.cd-chong { color: var(--qn-fire); }
.cd-sha { color: var(--qn-text-tertiary); }
.cd-yj { display: flex; flex-direction: column; gap: 6px; }
.cd-row { display: flex; gap: 8px; align-items: flex-start; }
.cd-k {
  font-size: 11px; font-weight: 600; width: 22px; height: 20px; border-radius: 5px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px;
}
.cd-k.g { background: rgba(var(--qn-wood-rgb),0.10); color: var(--qn-wood); border: 1px solid rgba(var(--qn-wood-rgb),0.35); }
.cd-k.b { background: rgba(var(--qn-fire-rgb),0.10); color: var(--qn-fire); border: 1px solid rgba(var(--qn-fire-rgb),0.40); }
.cd-v { font-size: 12px; color: var(--qn-text-primary); line-height: 1.6; }
.cd-pz {
  margin-top: 8px; padding: 6px 10px; font-size: 11px; color: #8A6A18; line-height: 1.6;
  background: rgba(var(--qn-earth-rgb),0.08); border-radius: 6px;
}
.cd-shen { margin-top: 6px; font-size: 11px; color: var(--qn-text-secondary); line-height: 1.6; }
.cd-shen-label { color: var(--qn-text-tertiary); }
.cd-shen-v { color: var(--qn-wood); }

/* ── 三元五腊节日（详情卡） ── */
.cd-festival {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 8px; padding: 6px 10px;
  background: linear-gradient(135deg, rgba(var(--qn-earth-rgb),0.12), rgba(198,105,31,0.08));
  border: 1px solid rgba(var(--qn-earth-rgb),0.35);
  border-radius: 6px;
}
.cd-f-label {
  font-size: 10px; font-weight: 600; color: #8A6A18;
  padding: 1px 6px; border-radius: 8px;
  background: rgba(var(--qn-earth-rgb),0.15); border: 1px solid rgba(var(--qn-earth-rgb),0.3);
  letter-spacing: 0.5px; flex-shrink: 0;
}
.cd-f-name { font-size: 12px; color: #6B5418; font-weight: 600; }

/* ── 十二时辰 ── */
.legend-row { display: flex; gap: 12px; font-size: 10.5px; color: var(--qn-text-tertiary); margin: 8px 14px 0; }
.legend-row span { display: flex; align-items: center; gap: 4px; }
.lg { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }
.lg.g { background: rgba(var(--qn-wood-rgb),0.40); border: 1px solid rgba(var(--qn-wood-rgb),0.60); }
.lg.w { background: rgba(var(--qn-earth-rgb),0.40); border: 1px solid rgba(var(--qn-earth-rgb),0.60); }
.lg.b { background: rgba(var(--qn-fire-rgb),0.40); border: 1px solid rgba(var(--qn-fire-rgb),0.60); }

.sh-axis { display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px; padding: 10px 12px; }
.sh-btn {
  padding: 8px 2px; border-radius: 6px; border: 1px solid var(--qn-border-subtle);
  background: var(--qn-surface-page); cursor: pointer; display: flex; flex-direction: column;
  align-items: center; gap: 2px; color: var(--qn-text-tertiary); font-size: 11px;
  transition: transform .12s, box-shadow .12s;
}
.sh-btn:active { transform: scale(0.96); }
.sh-btn.g { background: rgba(var(--qn-wood-rgb),0.08); border-color: rgba(var(--qn-wood-rgb),0.35); color: var(--qn-wood); }
.sh-btn.w { background: rgba(var(--qn-earth-rgb),0.08); border-color: rgba(var(--qn-earth-rgb),0.40); color: #8A6A18; }
.sh-btn.b { background: rgba(var(--qn-fire-rgb),0.08); border-color: rgba(var(--qn-fire-rgb),0.40); color: var(--qn-fire); }
.sh-btn.now { box-shadow: 0 0 0 2px var(--qn-brand-800); font-weight: 600; }
.sh-n { font-size: 12px; font-weight: 500; line-height: 1; }
.sh-r { font-size: 9px; opacity: .7; }

.period-detail {
  margin: 0 12px 10px; padding: 10px 12px; border-radius: 10px;
  background: var(--qn-brand-050); border: 1px solid var(--qn-border-subtle);
}
.pd-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.pd-badge { font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 8px; border: 1px solid; }
.pd-badge.g-g { background: rgba(var(--qn-wood-rgb),0.12); color: var(--qn-wood); border-color: rgba(var(--qn-wood-rgb),0.35); }
.pd-badge.g-w { background: rgba(var(--qn-earth-rgb),0.12); color: #8A6A18; border-color: rgba(var(--qn-earth-rgb),0.40); }
.pd-badge.g-b { background: rgba(var(--qn-fire-rgb),0.12); color: var(--qn-fire); border-color: rgba(var(--qn-fire-rgb),0.40); }
.pd-badge.g-n { background: var(--qn-surface-page); color: var(--qn-text-tertiary); border-color: var(--qn-border-subtle); }
.pd-name { font-size: 12.5px; font-weight: 600; color: var(--qn-text-primary); }
.pd-why { font-size: 11.5px; color: var(--qn-text-secondary); line-height: 1.6; }

/* ── 调候报告 ── */
.th-summary {
  display: flex; gap: 8px; align-items: flex-start;
  padding: 12px 14px; background: rgba(var(--qn-wood-rgb),0.06); margin: 12px;
  border-radius: 10px; border: 1px solid rgba(var(--qn-wood-rgb),0.15);
}
.th-emoji { font-size: 18px; flex-shrink: 0; }
.th-text { font-size: 13px; color: var(--qn-text-primary); line-height: 1.65; }

.th-priorities { display: flex; flex-direction: column; gap: 8px; padding: 0 12px 12px; }
.th-pri {
  padding: 10px 12px; border-radius: 10px; border: 1px solid var(--qn-border-subtle);
  background: var(--qn-surface-page);
}
.thp-top { display: flex; align-items: center; gap: 8px; margin-bottom: 3px; }
.thp-cn { font-size: 13px; font-weight: 600; color: var(--qn-text-primary); }
.thp-dir {
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px;
}
.thp-dir.d-增益 { background: rgba(var(--qn-wood-rgb),0.15); color: var(--qn-wood); }
.thp-dir.d-顺势增益 { background: linear-gradient(90deg, rgba(var(--qn-wood-rgb),0.18), rgba(var(--qn-earth-rgb),0.18)); color: var(--qn-brand-700); }
.thp-dir.d-增益待时 { background: rgba(var(--qn-earth-rgb),0.15); color: #8A6A18; }
.thp-dir.d-不干预 { background: rgba(var(--qn-metal-rgb),0.15); color: var(--qn-text-secondary); }
.thp-raw { font-size: 11px; color: var(--qn-text-tertiary); margin-bottom: 3px; }
.thp-why { font-size: 11.5px; color: var(--qn-text-secondary); line-height: 1.55; }

/* ── Modal ── */
.modal-mask {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45); z-index: 100;
  display: flex; align-items: flex-end;
}
.modal-body {
  width: 100%; max-height: 80vh; background: var(--qn-surface);
  border-radius: 18px 18px 0 0; display: flex; flex-direction: column;
  animation: slideUp .25s cubic-bezier(.2,0,.2,1);
}
@keyframes slideUp { from { transform: translateY(100%) } to { transform: translateY(0) } }
.modal-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid var(--qn-line);
}
.modal-title { font-size: 15px; font-weight: 700; color: var(--qn-text-primary); }
.modal-close {
  width: 28px; height: 28px; border-radius: 14px; border: none;
  background: var(--qn-surface-page); cursor: pointer; font-size: 14px; color: var(--qn-text-secondary);
}
.modal-content { flex: 1; padding: 14px 16px; overflow-y: auto; font-size: 13px; line-height: 1.7; color: var(--qn-text-primary); }
.modal-content.loading { display: flex; align-items: center; justify-content: center; }
.loading-dots { font-size: 13px; color: var(--qn-text-tertiary); }
.explain-text { white-space: pre-wrap; }
.modal-foot { display: flex; gap: 10px; padding: 10px 16px; border-top: 1px solid var(--qn-line); }
.btn-retry {
  flex: 1; padding: 10px; border-radius: 10px; border: 1px solid var(--qn-border-subtle);
  background: var(--qn-surface-page); color: var(--qn-text-secondary); font-size: 13px; cursor: pointer;
}
.btn-close {
  flex: 1; padding: 10px; border-radius: 10px; border: none;
  background: var(--qn-brand-800); color: var(--qn-text-on-brand); font-size: 13px; cursor: pointer;
}

.compliance {
  text-align: center; font-size: 10.5px; color: var(--qn-text-tertiary);
  padding: 14px 20px; line-height: 1.6;
}

/* ═════════════════════════════════════════════════════════════
   暗色主题 scoped 覆盖（B 类）
   hero 内部的 rgba(255,255,255,0.*) 半透明 — 深头上白半透明两主题通用 → 不动
   ═════════════════════════════════════════════════════════════ */
html[data-theme="dark"] .st-hero-mini {
  /* 暗色下英雄卡深绿渐变调亮一档，保证对比度 */
  background: linear-gradient(135deg, #1E5A4E 0%, #2E6B60 40%, #4FA08C 100%);
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}
html[data-theme="dark"] .cd-f-name { color: #C4A060; }
html[data-theme="dark"] .cd-f-label { color: #E0B870; }
html[data-theme="dark"] .cd-pz { color: #C4A060; }
html[data-theme="dark"] .thp-dir.d-不干预 { background: rgba(148,163,184,0.15); color: #B0ACA0; }
html[data-theme="dark"] .cal-cell.today .cal-jq { color: rgba(255,255,255,0.92); }
html[data-theme="dark"] .cal-cell.today .cal-lunar { color: rgba(255,255,255,0.88); }
</style>
