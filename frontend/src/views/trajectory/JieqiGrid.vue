<template>
  <div class="panel-jieqi" data-page-id="TP02">
    <!-- ═══ 24 节气卡片墙 ═══ -->
    <div class="jq-grid">
      <button
        v-for="(j, i) in data?.jieqi || []"
        :key="i"
        class="jq-card"
        :class="{ active: selected === i, 'jq-card--danger': cardZone(j) === 'OUT', 'jq-card--warn': cardZone(j) === 'CRIT' }"
        @click="$emit('select', i)"
      >
        <!-- Wuxing-FB zone 状态色点 (v3 才有) -->
        <div v-if="j.zone" class="jq-zone-dot" :style="{ background: zoneColor(j) }" :title="zoneTitle(j)"></div>
        <div class="jq-date">{{ j.month_day }}</div>
        <div class="jq-name">{{ j.name }}</div>
        <div class="jq-wx-dot" :style="{ background: wxColors[j.wuxing_main]?.hex }"></div>
        <div class="jq-wx-label" :style="{ color: wxColors[j.wuxing_main]?.hex }">
          {{ wxColors[j.wuxing_main]?.label }}
        </div>
        <!-- v3: 先天稳健 u* (最弱方向) -->
        <div v-if="j.min_tolerance" class="jq-tol">
          u*={{ j.min_tolerance.u_star.toFixed(2) }}
        </div>
      </button>
    </div>

    <!-- ═══ 选中节气详情 ═══ -->
    <div v-if="currentJieqi" class="jq-detail">
      <div class="jd-header" :style="{ borderColor: wxColors[currentJieqi.wuxing_main]?.hex }">
        <div class="jd-title">
          <span class="jd-name">{{ currentJieqi.name }}</span>
          <span class="jd-date">{{ currentJieqi.date }}</span>
        </div>
        <div class="jd-badges">
          <span class="jd-badge" :style="{ background: wxColors[currentJieqi.wuxing_main]?.hex + '33', color: wxColors[currentJieqi.wuxing_main]?.hex }">
            {{ wxColors[currentJieqi.wuxing_main]?.label }}旺
          </span>
          <span class="jd-badge">真太阳时 {{ currentJieqi.true_solar_time }}</span>
        </div>
      </div>

      <!-- 五行微调量 -->
      <div class="jd-block">
        <div class="jd-block-title">五行微调量（节气 + 流年 + 大运）</div>
        <div class="jd-wx-grid">
          <div v-for="w in wxDetail" :key="w.key" class="jd-wx-item">
            <div class="jd-wx-circle" :style="{ background: w.color }"></div>
            <div class="jd-wx-name">{{ w.label }}</div>
            <div class="jd-wx-val" :style="{ color: w.value >= 0 ? '#DA6C57' : '#4C90AF' }">
              {{ w.value >= 0 ? '+' : '' }}{{ w.value.toFixed(2) }}
            </div>
          </div>
        </div>
      </div>

      <!-- 流年 + 大运 -->
      <div class="jd-block">
        <div class="jd-block-title">气运叠加</div>
        <div class="jd-impact-row">
          <span class="jd-impact-label">流年 {{ data?.liunian?.name }}</span>
          <span class="jd-impact-desc">对各五行的加成（{{ data?.year_age }}岁所在流年）</span>
        </div>
        <div class="jd-impact-row">
          <span class="jd-impact-label">大运 {{ data?.dayun_active?.name }}</span>
          <span class="jd-impact-desc">对各五行的加成（当前大运主气）</span>
        </div>
      </div>

      <!-- 真太阳时说明 -->
      <div v-if="data?.user_location" class="jd-block jd-solar">
        <div class="jd-block-title">🌐 真太阳时校正</div>
        <div class="jd-solar-body">
          出生地 {{ data.user_location.city }}（{{ data.user_location.longitude }}°E, {{ data.user_location.latitude }}°N）
          <br/>
          标准北京时间 12:00 → 真太阳时 {{ data.user_location.true_solar_offset_min >= 0 ? '+' : '' }}{{ data.user_location.true_solar_offset_min }} 分钟
          <br/>
          <span class="jd-solar-note">
            {{ data.user_location.longitude > 120
              ? '你在东经 120° 以东，真太阳时比北京时间早'
              : data.user_location.longitude < 120
                ? '你在东经 120° 以西，真太阳时比北京时间晚'
                : '你正好在东经 120°（标准北京时间经度），无需校正' }}
          </span>
        </div>
      </div>

      <!-- v3: Wuxing-FB 分析块 -->
      <div v-if="currentJieqi?.zone" class="jd-block jd-wxfb">
        <div class="jd-block-title">⚗️ Wuxing-FB 五形生克负反馈分析</div>

        <!-- 各维带状态 -->
        <div class="jd-wxfb-zones">
          <div v-for="z in zoneBadges" :key="z.dim"
               class="jd-wxfb-zone"
               :class="{'zone-out': z.zone==='OUT' || z.virtual, 'zone-crit': z.zone==='CRIT' || z.critical, 'zone-in': z.zone==='IN' || z.zone==='带内'}">
            <span class="jwz-label">{{ z.label }}</span>
            <span class="jwz-state">{{ z.state }}</span>
            <span class="jwz-u" :title="`各维耐受强度 u*=${z.u_star}`">u*={{ z.u_star.toFixed(2) }}</span>
          </div>
        </div>

        <!-- 最弱方向 + gap -->
        <div v-if="currentJieqi.min_tolerance" class="jd-wxfb-summary">
          <span class="jws-badge" :style="{ background: weakestDimColor + '33', color: weakestDimColor }">
            最弱方向: {{ wxColors[currentJieqi.min_tolerance.dim]?.label || currentJieqi.min_tolerance.dim }}
            · u*={{ currentJieqi.min_tolerance.u_star.toFixed(2) }}
          </span>
          <span class="jws-gap" :class="gapClass">裕度 gap = {{ gapVal.toFixed(2) }} ({{ gapState }})</span>
        </div>

        <!-- 虚实判定 -->
        <div v-if="(currentJieqi.weak_virtual?.虚?.length || currentJieqi.weak_virtual?.实?.length || currentJieqi.weak_virtual?.临界?.length)"
             class="jd-wxfb-virtual">
          <span v-if="currentJieqi.weak_virtual?.实?.length" class="jwv-tag tag-bad">
            实: {{ currentJieqi.weak_virtual.实.map(d => wxColors[d]?.label || d).join('·') }}
          </span>
          <span v-if="currentJieqi.weak_virtual?.虚?.length" class="jwv-tag tag-bad">
            虚: {{ currentJieqi.weak_virtual.虚.map(d => wxColors[d]?.label || d).join('·') }}
          </span>
          <span v-if="currentJieqi.weak_virtual?.临界?.length" class="jwv-tag tag-warn">
            临界: {{ currentJieqi.weak_virtual.临界.map(d => wxColors[d]?.label || d).join('·') }}
          </span>
        </div>

        <div class="jd-wxfb-note">
          健康区间 = 动态逆转阈值；展示区间，不展示症状
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { WUXING_COLORS } from '../../utils/trajectory_contract'

const props = defineProps({
  data: { type: Object, required: true },
  selected: { type: Number, default: 0 },
})
defineEmits(['select'])

const wxColors = WUXING_COLORS

const currentJieqi = computed(() => props.data?.jieqi?.[props.selected])

const wxDetail = computed(() => {
  if (!currentJieqi.value) return []
  const j = currentJieqi.value
  const WX_KEYS = ['wood', 'fire', 'earth', 'metal', 'water']
  return WX_KEYS.map(k => ({
    key: k,
    label: WUXING_COLORS[k].label,
    color: WUXING_COLORS[k].hex,
    value: Math.round((
      (j.wuxing_bias?.[k] || 0) +
      (j.liunian_impact?.[k] || 0) +
      (j.dayun_impact?.[k] || 0)
    ) * 100) / 100,
  }))
})

// ═══ v3 Wuxing-FB 辅助函数 ═══

const DIMS = ['wood', 'fire', 'earth', 'metal', 'water']

/** 卡片整体 zone（最危险的状态）*/
function cardZone(j) {
  if (!j?.zone) return null
  if (Object.values(j.zone).some(z => z === 'OUT' || z === '实' || z === '虚')) return 'OUT'
  if (Object.values(j.zone).some(z => z === 'CRIT' || z === '临界')) return 'CRIT'
  return 'IN'
}

function zoneColor(j) {
  const z = cardZone(j)
  if (z === 'OUT') return '#E53935'
  if (z === 'CRIT') return '#FFAB40'
  if (z === 'IN') return '#7BC4A9'
  return 'transparent'
}

function zoneTitle(j) {
  if (!j?.zone) return ''
  const outs = Object.entries(j.zone).filter(([d, z]) => z === 'OUT' || z === '实' || z === '虚').map(([d]) => wxColors[d]?.label || d)
  const crits = Object.entries(j.zone).filter(([d, z]) => z === 'CRIT' || z === '临界').map(([d]) => wxColors[d]?.label || d)
  if (outs.length) return `带外 ⚠️ ${outs.join('·')}`
  if (crits.length) return `临界 ⚡ ${crits.join('·')}`
  return '全部安全（带内）'
}

/** 各维带状态详情（详情面板）*/
const zoneBadges = computed(() => {
  if (!currentJieqi.value?.zone) return []
  const j = currentJieqi.value
  return DIMS.map(d => ({
    dim: d,
    label: wxColors[d]?.label || d,
    zone: j.zone[d],
    u_star: j.tolerance_u?.[d] ?? 0,
    virtual: (j.weak_virtual?.虚 || []).includes(d) || (j.weak_virtual?.实 || []).includes(d),
    critical: (j.weak_virtual?.临界 || []).includes(d),
    state: (j.zone[d] === 'OUT' || j.zone[d] === '实' || j.zone[d] === '虚') ? '带外'
         : (j.zone[d] === 'CRIT' || j.zone[d] === '临界') ? '临界'
         : '带内',
  }))
})

/** gap 计算（详情面板）*/
const gapVal = computed(() => {
  const j = currentJieqi.value
  if (!j?.min_tolerance) return 0
  // gap = u* - s_mean；s_mean 用 |s_wuxing| 近似
  const sMean = j.s_wuxing ? Math.max(...DIMS.map(d => Math.abs(j.s_wuxing[d] || 0))) : 0
  return Math.max(0, j.min_tolerance.u_star - sMean)
})

const gapState = computed(() => {
  const j = currentJieqi.value
  if (!j?.min_tolerance) return '—'
  const ratio = gapVal.value / j.min_tolerance.u_star
  if (ratio < 0.3) return '高危'
  if (ratio < 0.6) return '紧张'
  return '安全'
})

const gapClass = computed(() => {
  if (gapState.value === '高危') return 'gap-danger'
  if (gapState.value === '紧张') return 'gap-warn'
  return 'gap-safe'
})

const weakestDimColor = computed(() => {
  const d = currentJieqi.value?.min_tolerance?.dim
  return wxColors[d]?.hex || '#B4433C'
})
</script>

<style scoped>
.panel-jieqi { }

/* ── 24 节气卡片墙 ── */
.jq-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 6px;
  margin-bottom: 16px;
}
.jq-card {
  background: var(--qn-surface, #fff);
  border: 2px solid transparent;
  border-radius: 8px;
  padding: 8px 4px;
  cursor: pointer;
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  transition: border-color 0.15s, transform 0.1s;
}
.jq-card:hover { transform: translateY(-2px); }
.jq-card.active {
  border-color: var(--qn-primary, #17534C);
  box-shadow: 0 2px 10px rgba(23, 83, 76, 0.3);
}
.jq-date { font-size: 9px; color: var(--qn-ink-3); }
.jq-name { font-size: 13px; font-weight: 600; color: var(--qn-ink); }
.jq-wx-dot { width: 10px; height: 10px; border-radius: 50%; }
.jq-wx-label { font-size: 9px; font-weight: 500; }

/* ── 详情面板 ── */
.jq-detail {
  background: var(--qn-surface, #fff); border-radius: 12px; padding: 16px;
}
.jd-header {
  border-left: 4px solid;
  padding-left: 12px; margin-bottom: 14px;
}
.jd-title { display: flex; gap: 10px; align-items: baseline; }
.jd-name { font-size: 20px; font-weight: 700; color: var(--qn-ink); }
.jd-date { font-size: 13px; color: var(--qn-ink-3); }
.jd-badges { display: flex; gap: 8px; margin-top: 6px; }
.jd-badge {
  font-size: 10px; padding: 2px 8px; border-radius: 10px;
  background: var(--qn-bg-2); color: var(--qn-ink-2);
}

.jd-block { margin-bottom: 14px; }
.jd-block-title {
  font-size: 12px; font-weight: 600; color: var(--qn-ink-2);
  margin-bottom: 8px; padding-bottom: 4px;
  border-bottom: 1px solid var(--qn-bg-2);
}
.jd-wx-grid {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px;
}
.jd-wx-item {
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  padding: 8px 4px; background: var(--qn-bg-2); border-radius: 8px;
}
.jd-wx-circle { width: 14px; height: 14px; border-radius: 50%; }
.jd-wx-name { font-size: 11px; font-weight: 600; color: var(--qn-ink); }
.jd-wx-val { font-size: 12px; font-weight: 700; }

.jd-impact-row {
  display: flex; gap: 8px; align-items: center; padding: 4px 0;
  font-size: 11px;
}
.jd-impact-label { font-weight: 600; color: var(--qn-ink); min-width: 80px; }
.jd-impact-desc { color: var(--qn-ink-3); }

.jd-solar {
  background: linear-gradient(135deg, rgba(66,165,245,0.08), rgba(66,165,245,0.02));
  border-radius: 8px; padding: 10px 12px;
}
.jd-solar-body {
  font-size: 11px; color: var(--qn-ink-2); line-height: 1.7;
}
.jd-solar-note {
  display: block; margin-top: 6px; padding: 6px 8px;
  background: rgba(66,165,245,0.1); border-radius: 6px;
  font-size: 10px; color: var(--qn-ink-3); font-style: italic;
}

/* ═══ v3 Wuxing-FB 样式 ═══ */

/* 卡片 zone 状态点 */
.jq-zone-dot {
  position: absolute; top: 4px; right: 4px;
  width: 6px; height: 6px; border-radius: 50%;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.8);
}
.jq-card { position: relative; }
.jq-card--danger { border-color: rgba(229,57,53,0.6) !important; }
.jq-card--warn { border-color: rgba(255,171,64,0.5) !important; }
.jq-tol {
  font-size: 9px; font-weight: 600; color: var(--qn-ink-3);
  font-family: Consolas, monospace; letter-spacing: 0.5px;
}

/* 详情面板 Wuxing-FB 块 */
.jd-wxfb {
  background: linear-gradient(135deg, rgba(46,125,91,0.06), rgba(46,125,91,0.01));
  border-radius: 8px; padding: 10px 12px;
}
.jd-wxfb-zones {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-bottom: 10px;
}
.jd-wxfb-zone {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 6px 2px; border-radius: 6px; font-size: 10px;
  background: var(--qn-bg-2, #f5f5f7); border: 1px solid transparent;
}
.jd-wxfb-zone.zone-in { border-color: rgba(46,125,91,0.3); }
.jd-wxfb-zone.zone-crit { border-color: rgba(249,168,37,0.5); background: rgba(249,168,37,0.08); }
.jd-wxfb-zone.zone-out { border-color: rgba(229,57,53,0.6); background: rgba(229,57,53,0.1); }
.jwz-label { font-weight: 700; color: var(--qn-ink); }
.jwz-state { font-size: 9px; font-weight: 600; }
.zone-in .jwz-state { color: #2E7D5B; }
.zone-crit .jwz-state { color: #FFAB40; }
.zone-out .jwz-state { color: #E53935; }
.jwz-u { font-family: Consolas, monospace; font-size: 9px; color: var(--qn-ink-3); }

.jd-wxfb-summary {
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px;
}
.jws-badge {
  font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 12px;
}
.jws-gap { font-size: 11px; font-weight: 700; }
.jws-gap.gap-safe { color: #2E7D5B; }
.jws-gap.gap-warn { color: #FFAB40; }
.jws-gap.gap-danger { color: #E53935; }

.jd-wxfb-virtual { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.jwv-tag { font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 10px; }
.jwv-tag.tag-bad { background: rgba(229,57,53,0.12); color: #E53935; }
.jwv-tag.tag-warn { background: rgba(249,168,37,0.12); color: #FFAB40; }

.jd-wxfb-note {
  font-size: 10px; color: var(--qn-ink-3); font-style: italic;
  padding-top: 6px; border-top: 1px dashed var(--qn-bg-3);
}

@media (max-width: 480px) {
  .jq-grid { grid-template-columns: repeat(4, 1fr); }
  .jd-wxfb-zones { grid-template-columns: repeat(3, 1fr); }
}
</style>
