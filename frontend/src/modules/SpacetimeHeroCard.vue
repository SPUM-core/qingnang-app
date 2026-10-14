<!-- ═══════════════════════════════════════════════════════════
  SpacetimeHeroCard.vue — 黄历卡片 v2
  严格按 2026-10-13 设计伪代码 780×528 布局令牌重排：
    padding 24 / gap 16 / radius 24 / 渐变 #12412E→#15553C
    Header → Divider → Section时辰 → Section五行 → Row开日+宜 → Callout → Footer
══════════════════════════════════════════════════════════════ -->
<template>
  <div v-if="ctx" class="st-card" :class="{ degraded: ctx.is_degraded }"
       @click="goDetail"
       @touchstart="_onTouchStart"
       @touchend="_onTouchEnd">

    <!-- ═══ Header：标题+节气徽章 两端对齐 ═══ -->
    <div class="st-header">
      <div class="st-dateblock">
        <span class="st-title"><span class="st-hour">{{ ctx.hour_name }}</span><span v-if="hourWxLabel" class="st-hour-suffix">· {{ hourWxLabel }}</span></span>
        <span class="st-sub">
          <span v-if="pillarYear" class="st-pillar">{{ pillarYear }}</span>
          <span v-if="pillarYear && (pillarMonth || pillarDay)" class="st-pillar-sep">·</span>
          <span v-if="pillarMonth" class="st-pillar">{{ pillarMonth }}</span>
          <span v-if="pillarMonth && pillarDay" class="st-pillar-sep">·</span>
          <span v-if="pillarDay" class="st-pillar">{{ pillarDay }}</span>
        </span>
      </div>
      <div class="st-solarterm">
        <span class="st-solarterm-ico">☀</span>
        <span class="st-solarterm-label">{{ jieqiLabel }}</span>
      </div>
    </div>

    <!-- ═══ Divider 顶部 ═══ -->
    <div class="st-divider"></div>

    <!-- ═══ Section：时辰 干支 ═══ -->
    <div class="st-section">
      <span class="st-section-title">时辰 · 干支</span>
      <div class="st-shichen-row">
        <div v-for="(gz, key) in gzLabels" :key="key" class="st-shichen-cell">
          <span class="ssc-zhi">{{ gz[1] }}</span>
          <span class="ssc-tg">{{ gz[0] }}{{ wxCn(ctx.sizhu?.wuxing?.[key]) }}</span>
        </div>      </div>
    </div>

    <!-- ═══ Section：五行 当令+木火土金水 6格等宽 ═══ -->
    <div class="st-section">
      <span class="st-section-title">五行 · 旺相休囚</span>
      <div class="st-wx-row">
        <!-- 当令格（高亮 surface.raise + gold 顶条） -->
        <div class="st-wx-cell st-current">
          <div class="swx-bar swx-bar-gold"></div>
          <span class="swx-label">当令</span>
          <span class="swx-value">{{ ctx.lingshou_gz }}</span>
        </div>
        <!-- 木火土金水 5 格 -->
        <div v-for="wx in wxList" :key="wx" class="st-wx-cell">
          <div class="swx-bar" :class="'swx-bar-' + wx"></div>
          <span class="swx-label">{{ wxCn(wx) }}</span>
          <span class="swx-state" :class="'swx-' + (ctx.wuxing_status[wx] || '平')">
            {{ ctx.wuxing_status[wx] || '平' }}
          </span>
        </div>
      </div>
    </div>

    <!-- ═══ Row：开日徽章 + 宜事项 ═══ -->
    <div class="st-yiji-row">
      <div class="st-daybadge">
        <span class="sdb-main">{{ ctx.jianchu }}日</span>
        <span class="sdb-micro">值日</span>
      </div>
      <div class="st-yi-content">
        <span class="syi-tag">宜</span>
        <template v-if="ctx.jianchu_advice?.good">
          <span v-for="(item, i) in ctx.jianchu_advice.good.split('、').slice(0,4)" :key="i" class="syi-item">
            {{ item }}<span v-if="i < Math.min(ctx.jianchu_advice.good.split('、').length, 4) - 1" class="syi-dot">·</span>
          </span>
        </template>
        <span v-else class="syi-empty">—</span>
      </div>
    </div>

    <!-- ═══ Callout：调理建议 描边提示块 ═══ -->
    <div v-if="tiaoHou" class="st-callout">
      <div class="sc-ico">
        <!-- 药丸 SVG（伪代码 2.8：替换 emoji → SVG） -->
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
          <rect x="3" y="8" width="18" height="8" rx="4" stroke="#E8C67A" stroke-width="1.8"/>
          <line x1="12" y1="8" x2="12" y2="16" stroke="#E8C67A" stroke-width="1.8" stroke-dasharray="2 1.5"/>
        </svg>
      </div>
      <div class="sc-text">
        <span class="sc-title">{{ thTitle }}</span>
        <span class="sc-desc">{{ thDesc }}</span>
      </div>
    </div>

    <!-- ═══ Footer：TagGroup（聚左防撑散）+ 箭头 ═══ -->
    <div class="st-footer">
      <div class="st-taggroup">
        <span v-for="(p, i) in tiaoHou?.priorities?.slice(0, 3) || []" :key="i"
              class="st-tag" :class="{ active: i === 0 }">
          {{ p.cn }}形{{ p.direction }}
        </span>
      </div>
      <span class="st-chevron">›</span>
    </div>

    <div v-if="loading" class="st-loader">⏳</div>
  </div>
  <div v-else class="st-card st-card-loading">⏳ 时空计算中…</div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'

const router = useRouter()

const rawCtx = ref(null)
const ctx = computed(() => {
  if (rawCtx.value && rawCtx.value.ctx) return rawCtx.value
  return rawCtx.value
})
const rawTh = ref(null)
const tiaoHou = computed(() => rawTh.value)
const loading = ref(false)

const WX_CN = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
function wxCn(w) { return WX_CN[w] || w }
const wxList = ['wood', 'fire', 'earth', 'metal', 'water']

/** 年月日三柱干支（后端 sizhu.ganzhi: {year:['丙','午'], month:['戊','戌'], day:['辛','酉']}） */
const pillarYear = computed(() => {
  const g = ctx.value?.sizhu?.ganzhi?.year
  return g?.length === 2 ? g.join('') : ''
})
const pillarMonth = computed(() => {
  const g = ctx.value?.sizhu?.ganzhi?.month
  return g?.length === 2 ? g.join('') : ''
})
const pillarDay = computed(() => {
  const g = ctx.value?.sizhu?.ganzhi?.day
  return g?.length === 2 ? g.join('') : ''
})

/** 四柱干支（ganzhi 子对象扁平化） */
const gzLabels = computed(() => {
  const g = ctx.value?.sizhu?.ganzhi || {}
  return {
    year:  g.year  || ['', ''],
    month: g.month || ['', ''],
    day:   g.day   || ['', ''],
    hour:  g.hour  || ['', ''],
  }
})

const jieqiLabel = computed(() => {
  const j = ctx.value?.jieqi
  if (!j) return '--'
  return typeof j === 'string' ? j : (j.current_term || '--')
})

const hourWxLabel = computed(() => {
  const wxKey = ctx.value?.lingshou
  return wxKey ? wxCn(wxKey) + '当值' : ''
})

/** Callout 标题：合并 priorities 首方向 */
const thTitle = computed(() => {
  if (!rawTh.value?.priorities?.length) return ''
  const top = rawTh.value.priorities[0]
  return `当令${ctx.value?.lingshou ? wxCn(ctx.value.lingshou) : ''}形旺 · 宜${top.cn}形${top.direction}`
})

/** Callout 描述：summary 字段截断 */
const thDesc = computed(() => {
  const s = rawTh.value?.summary || ''
  return s.length > 60 ? s.slice(0, 60) + '…' : s
})

async function refresh() {
  if (loading.value) return
  loading.value = true
  try {
    const r = await api.get('/api/v1/spacetime/daily-brief', { timeout: 5000 })
    rawCtx.value = r.data.ctx
    rawTh.value = r.data.tiao_hou
  } catch {
    try {
      const r2 = await api.get('/api/v1/spacetime/context', { timeout: 3000 })
      rawCtx.value = r2.data
    } catch (e) {
      console.warn('[Spacetime] load failed:', e.message)
    }
  } finally { loading.value = false }
}

let _touchStartX = 0, _touchStartY = 0, _touchLongPressed = false
function _onTouchStart(e) {
  const t = e.touches[0]
  _touchStartX = t.clientX; _touchStartY = t.clientY; _touchLongPressed = false
  // 长按 > 1.2s 视为非点击（避免触发时空详情跳转）
  clearTimeout(_longPressCancelTimer)
  _longPressCancelTimer = setTimeout(() => { _touchLongPressed = true }, 1200)
}
let _longPressCancelTimer = null
function _onTouchEnd(e) {
  clearTimeout(_longPressCancelTimer)
  if (_touchLongPressed) return   // 长按了，不触发跳转
  const t = e.changedTouches[0]
  const dx = t.clientX - _touchStartX, dy = t.clientY - _touchStartY
  if (Math.abs(dx) < 12 && Math.abs(dy) < 12) {
    goDetail()
  }
}
let _navigating = false
function goDetail() {
  if (_navigating) return
  _navigating = true
  router.push('/spacetime').finally(() => {
    setTimeout(() => { _navigating = false }, 500)
  })
}

onMounted(() => refresh())
defineExpose({ refresh })
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════
   设计令牌（伪代码 Section 0）
   padding:24 / gap:16 / radius:24
   渐变 180deg #12412E → #15553C
═══════════════════════════════════════════════════════ */
.st-card {
  position: relative; cursor: pointer;
  touch-action: manipulation;
  background: linear-gradient(180deg, #12412E 0%, #15553C 100%);
  border-radius: 24px;
  padding: 24px;
  margin: 10px 0 8px;
  display: flex; flex-direction: column;
  gap: 16px;
  box-shadow: 0 6px 24px rgba(13,59,46,0.3), inset 0 1px 0 rgba(255,255,255,0.08);
  color: #F2F7F4;
  overflow: hidden;
  transition: transform .25s cubic-bezier(.2,0,.2,1), box-shadow .25s;
}
.st-card:active { transform: scale(0.985) }
.st-card.degraded { background: linear-gradient(180deg, #5d4e18 0%, #7a6a2a 100%) }
.st-card-loading { text-align: center; color: rgba(255,255,255,0.6); padding: 28px }

/* ── Header ── */
.st-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.st-dateblock { display: flex; flex-direction: column; gap: 3px; }
.st-title { font-size: 17px; font-weight: 700; color: #F2F7F4; letter-spacing: 1.5px; line-height: 1.1 }
/* 时辰后方"· 土当值" —— 更小更淡 */
.st-hour-suffix { font-size: 11px; font-weight: 400; color: #8FB3A8; letter-spacing: 0.5px }
.st-sub { font-size: 14px; font-weight: 500; color: #DCEAE2; letter-spacing: 0.5px; line-height: 1.4 }
/* 年月日三柱：浅金色标签，用细点分隔 */
.st-sub .st-pillar { color: #E8C67A; font-weight: 600 }
.st-sub .st-pillar-sep { color: #5F8574; margin: 0 6px; font-size: 10px }
/* 时辰前后的方块装饰（▪ 字符在 Android WebView fallback，用纯 CSS 画） */
.st-hour { display: inline-block; padding: 0 4px; }
.st-hour::before, .st-hour::after {
  content: ''; display: inline-block;
  width: 4px; height: 4px;
  background: #E8C67A;  /* 金色小方块 */
  border-radius: 1px;
  vertical-align: middle;
  margin: 0 3px;
}
.st-hour::before { margin-left: 0; }
.st-hour::after { margin-right: 0; }
.st-solarterm {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 12px;
  background: #1E6B50;  /* surface.raise */
  border-radius: 999px;
  flex-shrink: 0;
}
.st-solarterm-ico { font-size: 13px; color: #E8C67A; line-height: 1 }
.st-solarterm-label { font-size: 12px; font-weight: 500; color: #F2F7F4 }

/* ── Divider ── */
.st-divider { width: 100%; height: 1px; background: rgba(255,255,255,0.1) }

/* ── Section 通用骨架 ── */
.st-section { display: flex; flex-direction: column; gap: 8px }
.st-section-title {
  font-size: 11px; font-weight: 500; color: #7FA79A;
  letter-spacing: 1px;
}

/* ── 时辰：4 条等宽 fill ── */
.st-shichen-row { display: flex; gap: 8px; width: 100% }
.st-shichen-cell {
  flex: 1 1 0;   /* 严格等宽，不设固定宽 */
  min-width: 0;
  display: flex; flex-direction: row; align-items: baseline; justify-content: center; gap: 3px;
  padding: 10px 8px;
  background: #144A37;  /* surface.cell */
  border-radius: 12px;
}
.ssc-zhi { font-size: 18px; font-weight: 700; color: #F2F7F4; line-height: 1.1 }
.ssc-tg { font-size: 12px; font-weight: 400; color: #8FB3A8; line-height: 1.1 }

/* ── 五行：6 格等宽（当令 + 木火土金水） ── */
.st-wx-row { display: flex; gap: 8px; width: 100% }
.st-wx-cell {
  flex: 1 1 0;
  min-width: 0;
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 10px 8px;
  background: #144A37;  /* surface.cell */
  border-radius: 14px;
}
/* 当令格加宽（flex 权重是普通格的 1.75 倍） */
.st-wx-cell.st-current {
  flex: 1.75 1 0;
  background: #1E6B50;  /* surface.raise 高亮 */
}
/* AccentBar 一律 width:fill（满格等长） */
.swx-bar { width: 100%; height: 3px; border-radius: 2px; flex-shrink: 0 }
.swx-bar-gold { background: #E8C67A }
.swx-bar-wood { background: #4CA97A }
.swx-bar-fire { background: #D9554D }
.swx-bar-earth { background: #D8A63C }
.swx-bar-metal { background: #C6CBCC }
.swx-bar-water { background: #3E8FD0 }

.swx-label { font-size: 12px; font-weight: 500; color: #A9CBB8; line-height: 1 }
.st-current .swx-label { color: #A9CBB8 }
.swx-value { font-size: 14px; font-weight: 700; color: #F5F1E4; line-height: 1; white-space: nowrap; }
.swx-state { font-size: 11px; font-weight: 500; padding: 1px 5px; border-radius: 7px; line-height: 1.3 }
/* 旺/相 → gold 吉；休 → muted 中；囚/死 → 暗金/红 */
.swx-旺.swx-state, .swx-相.swx-state { background: rgba(232,198,122,0.25); color: #E8C67A }
.swx-休.swx-state { background: rgba(143,179,168,0.2); color: #DCEAE2 }
.swx-囚.swx-state { background: rgba(216,166,60,0.25); color: #D8A63C }
.swx-死.swx-state { background: rgba(217,85,77,0.25); color: #D9554D }
.swx-平.swx-state { background: rgba(255,255,255,0.1); color: #8FB3A8 }

/* ── Row：开日徽章 + 宜 ── */
.st-yiji-row { display: flex; align-items: center; gap: 10px; width: 100% }
.st-daybadge {
  width: 72px; flex-shrink: 0;
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 9px 6px;
  background: #3A3316;
  border-radius: 12px;
}
.sdb-main { font-size: 14px; font-weight: 700; color: #E8C67A; line-height: 1 }
.sdb-micro { font-size: 10px; font-weight: 400; color: #A08C4E; line-height: 1 }
.st-yi-content {
  flex: 1; display: flex; align-items: center; gap: 4px; min-width: 0;
  flex-wrap: wrap;
}
.syi-tag {
  padding: 4px 7px; border-radius: 6px;
  background: #1E6B50;
  font-size: 12px; font-weight: 700; color: #DCF0E2;
  flex-shrink: 0;
}
.syi-item {
  font-size: 13px; font-weight: 400; color: #DCEAE2; line-height: 1.3;
  white-space: nowrap;
}
.syi-dot { color: #5F8574; margin: 0 2px }
.syi-empty { font-size: 13px; color: #8FB3A8 }

/* ── Callout：描边建议块 ── */
.st-callout {
  display: flex; align-items: center; gap: 12px;
  padding: 14px;
  background: #12452F;
  border: 1px solid #2E7355;
  border-radius: 14px;
}
.sc-ico { flex-shrink: 0; display: flex; align-items: center }
.sc-text { flex: 1; display: flex; flex-direction: column; gap: 3px; min-width: 0 }
.sc-title { font-size: 13px; font-weight: 500; color: #F2F7F4; line-height: 1.4 }
.sc-desc { font-size: 11px; font-weight: 400; color: #8FB3A8; line-height: 1.55 }

/* ── Footer：TagGroup（聚左防撑散）+ Chevron ── */
.st-footer {
  display: flex; align-items: center; gap: 8px; width: 100%;
}
.st-taggroup { display: flex; gap: 8px; flex-shrink: 0 }
.st-tag {
  padding: 7px 12px; border-radius: 999px;
  background: #1B6149;
  font-size: 12px; font-weight: 500; color: #CDE2D6;
  white-space: nowrap;
}
.st-tag.active { background: #2A7A57; color: #F0F7F3 }
.st-chevron { margin-left: auto; font-size: 16px; color: #7FA79A; font-weight: 300; line-height: 1 }

.st-loader { position: absolute; right: 24px; top: 24px; font-size: 14px; opacity: 0.7 }
</style>
