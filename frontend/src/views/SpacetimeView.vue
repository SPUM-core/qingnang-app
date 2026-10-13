<!-- ═══════════════════════════════════════════════════════════
  SpacetimeView.vue — 时空详情页
  英雄卡 + 黄历日历 + 宜忌 + 十二时辰 + 调候报告 + AI 解读
══════════════════════════════════════════════════════════════ -->
<template>
  <div class="st-page">
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
          <span class="st-gz-cell" v-for="(gz, key) in ctx.sizhu" :key="key">
            <span class="st-gz-zhi">{{ gz[1] }}</span>
            <span class="st-gz-tg">{{ gz[0] }}</span>
          </span>
        </div>
        <div class="st-qi-col">
          <span class="st-qi-val">🌤️ {{ ctx.jieqi?.current_term || '--' }}</span>
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
             :class="{ today: cell.isToday, other: !cell.inMonth, 'solar-term': cell.jieqi, selected: cell.date === selectedDate }"
             @click="selectDate(cell)">
          <span class="cal-day">{{ cell.day || '' }}</span>
          <span class="cal-lunar" v-if="cell.lunar && cell.inMonth">{{ cell.lunar }}</span>
          <span class="cal-jq" v-if="cell.jieqi">🌤️</span>
        </div>
      </div>
    </div>

    <!-- ═══ 黄历宜忌 ═══ -->
    <div class="st-section">
      <div class="sec-head">
        <span class="sec-title" style="--dot-color:#D4A017"><span class="sec-dot"></span>黄历宜忌</span>
        <span class="sec-sub">经典择日 · 通用</span>
      </div>

      <div class="yj-tabs">
        <span v-for="t in yjTabs" :key="t.key"
              class="yj-tab" :class="{ on: activeYjTab === t.key }"
              @click="activeYjTab = t.key">{{ t.label }}</span>
      </div>

      <!-- Tab: 宜忌 -->
      <div v-if="activeYjTab === 'yj'" class="yj-panel">
        <div class="yj-row"><span class="yj-k g">宜</span><span class="yj-v">{{ yiText }}</span></div>
        <div class="yj-row"><span class="yj-k b">忌</span><span class="yj-v">{{ jiText }}</span></div>
        <div v-if="ctx?.jianchu" class="yj-row"><span class="yj-k g">建除</span>
          <span class="yj-v"><b>{{ ctx.jianchu }}日</b> — {{ jianchuDesc }}</span></div>
        <div class="yj-empty" v-if="!yiText && !jiText && !ctx?.jianchu">本时段无宜忌记录</div>
      </div>

      <!-- Tab: 建除 -->
      <div v-if="activeYjTab === 'jianchu'" class="yj-panel">
        <div v-if="ctx?.jianchu" class="yj-row"><span class="yj-k g">{{ ctx.jianchu }}</span>
          <span class="yj-v">{{ jianchuDesc }}</span></div>
        <div class="yj-empty" v-else>无建除数据</div>
      </div>

      <!-- Tab: 彭祖 -->
      <div v-if="activeYjTab === 'pengzu'" class="yj-panel">
        <div v-if="anchor?.pengzu" class="pz-line"><b>彭祖百忌</b>　{{ anchor.pengzu }}</div>
        <div class="yj-empty" v-else>无彭祖百忌记录</div>
      </div>

      <!-- Tab: 神煞 -->
      <div v-if="activeYjTab === 'shensha'" class="yj-panel">
        <template v-if="anchor">
          <div v-if="anchor.chong" class="yj-row"><span class="yj-k b">冲煞</span><span class="yj-v">{{ anchor.chong }}</span></div>
          <div v-if="anchor.sha" class="yj-row"><span class="yj-k g">煞方</span><span class="yj-v">煞{{ anchor.sha }}方</span></div>
          <div v-if="anchor.feixing" class="yj-row"><span class="yj-k g">飞星</span><span class="yj-v">{{ anchor.feixing }}</span></div>
        </template>
        <div class="yj-empty" v-if="!anchor?.chong && !anchor?.sha && !anchor?.feixing">无神煞记录</div>
      </div>

      <div class="yj-more" @click="showExplain = true">🤖 AI 解读全部宜忌 ›</div>
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
          <div class="thp-why">{{ p.why }}</div>
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
  const map = { '补': '💊', '泻': '🌊', '养': '🌿', '平': '⚖️', '换时辰': '⏰' }
  return map[tiaoHou.value.priorities[0].direction] || '🧭'
})

// ── 黄历宜忌 tab ──
const activeYjTab = ref('yj')
const yjTabs = [
  { key: 'yj', label: '宜忌' },
  { key: 'jianchu', label: '建除' },
  { key: 'pengzu', label: '彭祖' },
  { key: 'shensha', label: '神煞' },
]

const yiText = computed(() => {
  if (!anchor.value) return ''
  const lst = anchor.value.yi_list || []
  return lst.length ? lst.join('、') : (anchor.value.yi || '')
})
const jiText = computed(() => {
  if (!anchor.value) return ''
  const lst = anchor.value.ji_list || []
  return lst.length ? lst.join('、') : (anchor.value.ji || '')
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
const calMonth = ref(today.getMonth())
const selectedDate = ref(today.getDate())

function prevMonth() {
  if (calMonth.value === 0) { calMonth.value = 11; calYear.value-- }
  else calMonth.value--
}
function nextMonth() {
  if (calMonth.value === 11) { calMonth.value = 0; calYear.value++ }
  else calMonth.value++
}

const calCells = computed(() => {
  const firstDay = new Date(calYear.value, calMonth.value, 1).getDay()
  const daysInMonth = new Date(calYear.value, calMonth.value + 1, 0).getDate()
  const cells = []
  // 上月尾部
  const prevDays = new Date(calYear.value, calMonth.value, 0).getDate()
  for (let i = firstDay - 1; i >= 0; i--) {
    cells.push({ day: prevDays - i, inMonth: false, date: prevDays - i, lunar: '', jieqi: false, isToday: false })
  }
  // 本月
  const isCurMonth = (calYear.value === today.getFullYear() && calMonth.value === today.getMonth())
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({
      day: d, inMonth: true, date: d,
      lunar: '', jieqi: false,
      isToday: isCurMonth && d === today.getDate(),
    })
  }
  // 下月头部
  const total = cells.length
  const pad = (7 - total % 7) % 7
  for (let d = 1; d <= pad; d++) {
    cells.push({ day: d, inMonth: false, date: d, lunar: '', jieqi: false, isToday: false })
  }
  return cells
})

function selectDate(cell) {
  if (cell.inMonth) selectedDate.value = cell.date
}

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

onMounted(loadAll)
</script>

<style scoped>
.st-page { min-height: 100vh; padding-bottom: 40px; }

/* ── 顶部导航 ── */
.st-nav {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #E8E8E8;
  position: sticky; top: 0; z-index: 10;
}
.st-back {
  font-size: 13px; color: #2E6B60; background: none; border: none;
  padding: 4px 8px; border-radius: 6px; cursor: pointer;
}
.st-nav-title { font-size: 15px; font-weight: 700; color: #1a2a25; margin-left: 4px; }
.st-nav-spacer { flex: 1; }

/* ── 英雄卡（mini 版） ── */
.st-hero-mini {
  background: linear-gradient(135deg, #0d3b2e 0%, #1a5c48 40%, #2d7a5e 100%);
  margin: 10px 12px; border-radius: 16px; padding: 14px 16px; color: #fff;
  box-shadow: 0 4px 16px rgba(13,59,46,0.2);
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
.stb-wood { border-top-color: #66bb6a; } .stb-fire { border-top-color: #ef5350; }
.stb-earth { border-top-color: #d4a017; } .stb-metal { border-top-color: #bdbdbd; }
.stb-water { border-top-color: #42a5f5; }
.stb-wx { font-size: 11px; font-weight: 600; }
.stb-status { font-size: 9px; font-weight: 600; padding: 1px 4px; border-radius: 6px; }
.sts-旺 { background: rgba(76,175,80,0.3); color: #a5d6a7; }
.sts-相 { background: rgba(76,175,80,0.18); color: #c8e6c9; }
.sts-休 { background: rgba(158,158,158,0.2); color: #e0e0e0; }
.sts-囚 { background: rgba(212,160,23,0.25); color: #ffe082; }
.sts-死 { background: rgba(244,67,54,0.25); color: #ef9a9a; }
.sts-平 { background: rgba(255,255,255,0.15); color: rgba(255,255,255,0.7); }

.st-th-line {
  display: flex; gap: 8px; align-items: flex-start;
  padding: 8px 12px; background: rgba(255,255,255,0.1); border-radius: 10px;
}
.st-th-emoji { font-size: 16px; flex-shrink: 0; }
.st-th-text { font-size: 12px; color: rgba(255,255,255,0.9); line-height: 1.55; }

/* ── 通用 section ── */
.st-section {
  background: #fff; margin: 10px 12px; border-radius: 14px;
  border: 1px solid #E8E8E8; overflow: hidden;
}
.sec-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 13px 14px 0;
}
.sec-title { font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.sec-dot { width: 6px; height: 6px; border-radius: 50%; background: #2E6B60; flex-shrink: 0; }
.sec-sub { font-size: 11px; color: #8A9A94; }

/* ── 日历 ── */
.cal-nav { display: flex; align-items: center; gap: 6px; }
.cal-btn {
  width: 26px; height: 26px; border-radius: 6px; border: 1px solid #E8E8E8;
  background: #fff; cursor: pointer; font-size: 14px; color: #5F6E68;
}
.cal-title { font-size: 12px; font-weight: 600; color: #1a2a25; min-width: 80px; text-align: center; }

.cal-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); padding: 8px 10px 4px; }
.cal-wd { text-align: center; font-size: 11px; color: #8A9A94; font-weight: 500; }

.cal-grid {
  display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px;
  padding: 2px 8px 10px;
}
.cal-cell {
  aspect-ratio: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; border-radius: 8px; cursor: pointer;
  background: #FAFAF7; border: 1px solid transparent;
  transition: background .15s, border-color .15s;
}
.cal-cell:hover { background: #F1F5F2; }
.cal-cell.other { background: transparent; color: #C8CECA; }
.cal-cell.today { background: #2E6B60; color: #fff; font-weight: 600; }
.cal-cell.selected { border-color: #D4A017; box-shadow: 0 0 0 2px rgba(212,160,23,0.2); }
.cal-cell.solar-term { color: #D4A017; }
.cal-day { font-size: 14px; font-weight: 500; }
.cal-lunar { font-size: 9px; color: #8A9A94; margin-top: 1px; }
.cal-jq { font-size: 9px; }

/* ── 黄历宜忌 ── */
.yj-tabs { display: flex; gap: 5px; padding: 10px 14px 0; flex-wrap: wrap; }
.yj-tab {
  font-size: 11.5px; padding: 4px 10px; border-radius: 12px; cursor: pointer;
  border: 1px solid #E8E8E8; background: #fff; color: #5F6E68;
  transition: all .15s;
}
.yj-tab.on { background: #144842; border-color: #144842; color: #fff; }

.yj-panel { display: flex; flex-direction: column; gap: 6px; padding: 10px 14px; }
.yj-row { display: flex; gap: 8px; align-items: flex-start; }
.yj-k {
  font-size: 11px; font-weight: 600; width: 22px; height: 20px; border-radius: 5px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px;
}
.yj-k.g { background: rgba(67,160,71,.1); color: #43A047; border: 1px solid rgba(67,160,71,.35) }
.yj-k.b { background: rgba(216,67,21,.1); color: #D84315; border: 1px solid rgba(216,67,21,.4) }
.yj-v { font-size: 12px; color: #5F6E68; line-height: 1.6; padding-top: 1px }
.yj-v b { color: #33403B; font-weight: 500 }
.yj-empty { font-size: 11px; color: #8A9A94; text-align: center; padding: 10px 0; font-style: italic; }
.pz-line { font-size: 11.5px; line-height: 1.65; color: #6B5418; padding: 8px 10px; background: rgba(212,160,23,.08); border-radius: 8px; }
.pz-line b { color: #5A4514; }
.yj-more {
  padding: 8px 14px; font-size: 11.5px; color: #2E6B60; text-align: right;
  cursor: pointer; border-top: 1px solid #F0F0EC;
}

/* ── 十二时辰 ── */
.legend-row { display: flex; gap: 12px; font-size: 10.5px; color: #8A9A94; margin: 8px 14px 0; }
.legend-row span { display: flex; align-items: center; gap: 4px; }
.lg { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }
.lg.g { background: rgba(67,160,71,.4); border: 1px solid rgba(67,160,71,.6); }
.lg.w { background: rgba(212,160,23,.4); border: 1px solid rgba(212,160,23,.6); }
.lg.b { background: rgba(216,67,21,.4); border: 1px solid rgba(216,67,21,.6); }

.sh-axis { display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px; padding: 10px 12px; }
.sh-btn {
  padding: 8px 2px; border-radius: 6px; border: 1px solid #E8E8E8;
  background: #F5F5EE; cursor: pointer; display: flex; flex-direction: column;
  align-items: center; gap: 2px; color: #8A9A94; font-size: 11px;
  transition: transform .12s, box-shadow .12s;
}
.sh-btn:active { transform: scale(0.96); }
.sh-btn.g { background: rgba(67,160,71,.08); border-color: rgba(67,160,71,.35); color: #43A047; }
.sh-btn.w { background: rgba(212,160,23,.08); border-color: rgba(212,160,23,.4); color: #8A6A18; }
.sh-btn.b { background: rgba(216,67,21,.08); border-color: rgba(216,67,21,.4); color: #D84315; }
.sh-btn.now { box-shadow: 0 0 0 2px #2E6B60; font-weight: 600; }
.sh-n { font-size: 12px; font-weight: 500; line-height: 1; }
.sh-r { font-size: 9px; opacity: .7; }

.period-detail {
  margin: 0 12px 10px; padding: 10px 12px; border-radius: 10px;
  background: var(--qn-brand-050, #F1F5F2); border: 1px solid #E8E8E8;
}
.pd-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.pd-badge { font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 8px; border: 1px solid; }
.pd-badge.g-g { background: rgba(67,160,71,.12); color: #43A047; border-color: rgba(67,160,71,.35); }
.pd-badge.g-w { background: rgba(212,160,23,.12); color: #8A6A18; border-color: rgba(212,160,23,.4); }
.pd-badge.g-b { background: rgba(216,67,21,.12); color: #D84315; border-color: rgba(216,67,21,.4); }
.pd-badge.g-n { background: #F5F5EE; color: #8A9A94; border-color: #E8E8E8; }
.pd-name { font-size: 12.5px; font-weight: 600; color: #33403B; }
.pd-why { font-size: 11.5px; color: #5F6E68; line-height: 1.6; }

/* ── 调候报告 ── */
.th-summary {
  display: flex; gap: 8px; align-items: flex-start;
  padding: 12px 14px; background: rgba(34,139,34,0.06); margin: 12px;
  border-radius: 10px; border: 1px solid rgba(34,139,34,0.15);
}
.th-emoji { font-size: 18px; flex-shrink: 0; }
.th-text { font-size: 13px; color: #1a2a25; line-height: 1.65; }

.th-priorities { display: flex; flex-direction: column; gap: 8px; padding: 0 12px 12px; }
.th-pri {
  padding: 10px 12px; border-radius: 10px; border: 1px solid #E8E8E8;
  background: #FAFAF7;
}
.thp-top { display: flex; align-items: center; gap: 8px; margin-bottom: 3px; }
.thp-cn { font-size: 13px; font-weight: 600; color: #1a2a25; }
.thp-dir {
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px;
}
.thp-dir.d-补 { background: rgba(67,160,71,.15); color: #43A047; }
.thp-dir.d-泻 { background: rgba(216,67,21,.12); color: #D84315; }
.thp-dir.d-养 { background: rgba(107,114,119,.1); color: #5F6E68; }
.thp-dir.d-平 { background: rgba(158,158,158,.1); color: #5F6E68; }
.thp-dir.d-换时辰 { background: rgba(212,160,23,.15); color: #8A6A18; }
.thp-raw { font-size: 11px; color: #8A9A94; margin-bottom: 3px; }
.thp-why { font-size: 11.5px; color: #5F6E68; line-height: 1.55; }

/* ── Modal ── */
.modal-mask {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45); z-index: 100;
  display: flex; align-items: flex-end;
}
.modal-body {
  width: 100%; max-height: 80vh; background: #fff;
  border-radius: 18px 18px 0 0; display: flex; flex-direction: column;
  animation: slideUp .25s cubic-bezier(.2,0,.2,1);
}
@keyframes slideUp { from { transform: translateY(100%) } to { transform: translateY(0) } }
.modal-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid #E8E8E8;
}
.modal-title { font-size: 15px; font-weight: 700; color: #1a2a25; }
.modal-close {
  width: 28px; height: 28px; border-radius: 14px; border: none;
  background: #F5F5EE; cursor: pointer; font-size: 14px; color: #5F6E68;
}
.modal-content { flex: 1; padding: 14px 16px; overflow-y: auto; font-size: 13px; line-height: 1.7; color: #33403B; }
.modal-content.loading { display: flex; align-items: center; justify-content: center; }
.loading-dots { font-size: 13px; color: #8A9A94; }
.explain-text { white-space: pre-wrap; }
.modal-foot { display: flex; gap: 10px; padding: 10px 16px; border-top: 1px solid #E8E8E8; }
.btn-retry {
  flex: 1; padding: 10px; border-radius: 10px; border: 1px solid #E8E8E8;
  background: #F5F5EE; color: #5F6E68; font-size: 13px; cursor: pointer;
}
.btn-close {
  flex: 1; padding: 10px; border-radius: 10px; border: none;
  background: #144842; color: #fff; font-size: 13px; cursor: pointer;
}

.compliance {
  text-align: center; font-size: 10.5px; color: #8A9A94;
  padding: 14px 20px; line-height: 1.6;
}
</style>
