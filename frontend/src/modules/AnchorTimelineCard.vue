<!-- ═══════════════════════════════════════════════════════════
  AnchorTimelineCard.vue — 今日时空锚点（v3 重构）
  块2 我的吉时 · 块3 今日方位 · 块4 今日替换 · 块5 黄历宜忌(折叠)
  块1 时空仪表 → HeroDailyTipsCard 已独立
══════════════════════════════════════════════════════════════ -->
<template>
  <div class="anchor-wrap">

    <!-- ═══ 块2：我的吉时 ═══ -->
    <div class="at-card" @click.stop>
      <div class="c-head">
        <div class="c-title"><span class="dot"></span>我的吉时</div>
        <span class="c-sub">十二时辰 × 我的体质</span>
      </div>

      <!-- 图例 -->
      <div class="legend">
        <span><i class="lg" style="background:rgba(67,160,71,.1);border:1px solid rgba(67,160,71,.35)"></i>助我</span>
        <span><i class="lg" style="background:rgba(212,160,23,.1);border:1px solid rgba(212,160,23,.4)"></i>平</span>
        <span><i class="lg" style="background:rgba(216,67,21,.1);border:1px solid rgba(216,67,21,.4)"></i>耗我</span>
      </div>

      <!-- 十二时辰轴：只放时辰单字 + 吉凶色，具体时段点开看 -->
      <div class="sh-wrap">
        <div class="sh-axis">
          <button v-for="sc in anchorSafe.timeline" :key="sc.period"
                  class="sh"
                  :class="[shColorClass(sc), { now: isNow(sc) }]"
                  :aria-label="`${sc.period} ${sc.range} ${sc.personal_label || ''}`"
                  :aria-pressed="activePeriod === sc.period"
                  @click="togglePeriod(sc)">
            <span class="sh-n">{{ shortPeriod(sc.period) }}</span>
            <i class="sh-bar"></i>
          </button>
        </div>

        <!-- 展开的时辰详情：时间范围 + 建议 -->
        <div v-if="activeDetail" class="period-detail">
          <div class="pd-head">
            <span class="pd-badge" :class="'g-' + shColorClass(activeDetail)">
              {{ activeDetail.personal_label || '平' }}
            </span>
            <span class="pd-name">{{ activeDetail.period }} {{ activeDetail.range }}</span>
            <span class="pd-elem">{{ activeDetail.elem }}时</span>
          </div>
          <div class="pd-why">
            {{ activeDetail.desc || `${activeDetail.elem}时 · ${activeDetail.jianchu || ''}日` }}
          </div>
        </div>

        <!-- 行动推荐 -->
        <div v-if="bestAction" class="action">
          <div class="a-head">
            <span class="a-badge">推荐</span>
            <span class="a-title">{{ actionTitle(bestAction) }}</span>
            <span class="a-when">{{ bestAction.period }} {{ bestAction.range }}</span>
          </div>
          <div class="a-why">
            {{ bestAction.elem }}时{{ bestAction.personal_label || '平和' }}，
            你的<b>{{ anchorSafe.dangling_elem || '弱形' }}</b>{{ weakHint }}
            {{ actionAdvice(bestAction) }}
          </div>
        </div>
        <div v-else-if="anchorSafe.timeline?.length" class="action action-empty">
          今日无「助我」时辰，可按下方替换表调整节律。
        </div>
        <div v-else class="action action-empty">
          时辰节律待生成…
        </div>
      </div>
    </div>

    <!-- ═══ 块3：今日方位 ═══ -->
    <div v-if="anchorSafe.orientation" class="at-card">
      <div class="c-head">
        <div class="c-title"><span class="dot"></span>今日方位</div>
        <span class="c-sub">{{ anchorSafe.orientation.feixing_name }}落{{ anchorSafe.orientation.gong }}宫</span>
      </div>
      <div class="cmp">
        <div class="side ok">
          <div class="s-l">宜取方位</div>
          <div class="s-dir">{{ anchorSafe.orientation.good_dir }}</div>
          <div class="s-d">{{ dirAdvice(true) }}</div>
        </div>
        <div class="side no">
          <div class="s-l">宜避方位</div>
          <div class="s-dir">{{ anchorSafe.orientation.bad_dir }}</div>
          <div class="s-d">{{ dirAdvice(false) }}</div>
        </div>
      </div>
    </div>

    <!-- ═══ 块4：今日替换 ═══ -->
    <div v-if="anchorSafe.swaps?.length" class="at-card">
      <div class="c-head">
        <div class="c-title"><span class="dot"></span>今日替换</div>
        <span class="c-sub">不要 A，改做 B</span>
      </div>
      <div class="swap">
        <div v-for="(sw, i) in anchorSafe.swaps" :key="i" class="sw">
          <span class="sw-x">{{ sw.bad }}</span>
          <span class="sw-ar">→</span>
          <span class="sw-v">{{ sw.good }}</span>
        </div>
      </div>
    </div>

    <!-- ═══ 块5：黄历宜忌（折叠 + Tab） ═══ -->
    <div class="at-card">
      <div class="c-head">
        <div class="c-title" style="--dot-color:#D4A017">
          <span class="dot"></span>黄历宜忌
        </div>
        <span class="c-sub">经典择日 · 通用</span>
      </div>

      <!-- Tab 切换 -->
      <div class="tabs">
        <span v-for="(t, i) in tabs" :key="t.key"
              class="tab" :class="{ on: activeTab === t.key }"
              @click="activeTab = t.key">{{ t.label }}</span>
      </div>

      <!-- Tab: 宜忌 -->
      <div v-if="activeTab === 'yj'" class="yj">
        <template v-if="hasAlmanac">
          <div class="yj-row"><span class="yj-k g">宜</span>
            <span class="yj-v"><b>{{ yiFirst }}</b>{{ yiRest }}</span></div>
          <div class="yj-row"><span class="yj-k b">忌</span>
            <span class="yj-v"><b>{{ jiFirst }}</b>{{ jiRest }}</span></div>
          <div v-if="anchorSafe.jianchu" class="yj-row"><span class="yj-k g">建除</span>
            <span class="yj-v"><b>{{ anchorSafe.jianchu }}日</b> — {{ jianchuDesc }}</span></div>
          <div v-if="anchorSafe.xiu" class="yj-row"><span class="yj-k b">星宿</span>
            <span class="yj-v"><b>{{ anchorSafe.xiu }}宿</b>{{ xiuLuckText }}</span></div>
        </template>
        <div v-else class="empty">{{ emptyText }}</div>
      </div>

      <!-- Tab: 建除 -->
      <div v-if="activeTab === 'jianchu'" class="yj">
        <template v-if="anchorSafe.jianchu">
          <div class="yj-row"><span class="yj-k g">{{ anchorSafe.jianchu }}</span>
            <span class="yj-v">宜{{ (anchorSafe.jianchu_yi||[]).join('、') || '诸事' }}</span></div>
          <div v-if="(anchorSafe.jianchu_ji||[]).length" class="yj-row"><span class="yj-k b">忌</span>
            <span class="yj-v">{{ anchorSafe.jianchu_ji.join('、') }}</span></div>
        </template>
        <div v-else class="empty">{{ emptyText }}</div>
      </div>

      <!-- Tab: 星宿 -->
      <div v-if="activeTab === 'xiu'" class="yj">
        <template v-if="anchorSafe.xiu">
          <div class="yj-row"><span class="yj-k" :class="xiuLuckClass">{{ anchorSafe.xiu }}宿</span>
            <span class="yj-v">{{ xiuLuckText }}</span></div>
        </template>
        <div v-else class="empty">{{ emptyText }}</div>
      </div>

      <!-- Tab: 彭祖 -->
      <div v-if="activeTab === 'pengzu'" class="yj">
        <div v-if="anchorSafe.pengzu" class="pz"><b>彭祖百忌</b>　{{ anchorSafe.pengzu }}</div>
        <div v-else class="empty">{{ emptyText }}</div>
      </div>

      <!-- Tab: 神煞 -->
      <div v-if="activeTab === 'shensha'" class="yj">
        <template v-if="anchorSafe.tianshen || anchorSafe.chong || anchorSafe.sha">
          <div v-if="anchorSafe.tianshen" class="yj-row"><span class="yj-k g">值日天神</span>
            <span class="yj-v">{{ anchorSafe.tianshen }}</span></div>
          <div v-if="anchorSafe.chong" class="yj-row"><span class="yj-k b">冲煞</span>
            <span class="yj-v">{{ anchorSafe.chong }}</span></div>
          <div v-if="anchorSafe.sha" class="yj-row"><span class="yj-k g">煞方</span>
            <span class="yj-v">煞{{ anchorSafe.sha }}方</span></div>
        </template>
        <div v-else class="empty">{{ emptyText }}</div>
      </div>

      <!-- 彭祖百忌琥珀条（非彭祖 Tab 时托出） -->
      <div v-if="anchorSafe.pengzu && activeTab !== 'pengzu'" class="pz">
        <b>彭祖百忌</b>　{{ anchorSafe.pengzu }}
      </div>

      <div class="more" @click="$emit('explain')">AI 解读全部宜忌 ›</div>
      <p class="compliance">内容由 AI 生成，仅供参考 · 不构成医疗状态描述<br>体质趋势观察提示</p>
    </div>

  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { isNowPeriod, periodColorClass, buildDirAdvice, wxName } from '../utils/almanac'

const props = defineProps({
  anchorSafe: { type: Object, required: true },
})
defineEmits(['explain'])

const activeTab = ref('yj')
const tabs = [
  { key: 'yj',      label: '宜忌' },
  { key: 'jianchu', label: '建除' },
  { key: 'xiu',     label: '星宿' },
  { key: 'pengzu',  label: '彭祖' },
  { key: 'shensha', label: '神煞' },
]

const yiList = computed(() => props.anchorSafe.yi_list?.length ? props.anchorSafe.yi_list : [])
const jiList = computed(() => props.anchorSafe.ji_list?.length ? props.anchorSafe.ji_list : [])

const yiFirst = computed(() => yiList.value[0] || props.anchorSafe.yi || '—')
const yiRest = computed(() => yiList.value.length > 1 ? ' · ' + yiList.value.slice(1, 4).join(' · ') : '')
const jiFirst = computed(() => jiList.value[0] || props.anchorSafe.ji || '—')
const jiRest = computed(() => jiList.value.length > 1 ? ' · ' + jiList.value.slice(1, 4).join(' · ') : '')

const hasAlmanac = computed(() => !!(
  yiList.value.length || jiList.value.length ||
  props.anchorSafe.jianchu || props.anchorSafe.xiu || props.anchorSafe.pengzu
))
const emptyText = computed(() =>
  props.anchorSafe.ganzhi ? '本时段无该类记录' : '黄历待生成…'
)

const jianchuDesc = computed(() => {
  const jc = props.anchorSafe.jianchu
  const map = { '建':'宜出行、赴任、开市', '除':'宜除服、解除、打扫', '满':'宜祈福、嫁娶、出行', '平':'平常日',
    '定':'宜冠笄、订婚', '执':'宜捕捉、畋猎', '破':'破日、诸事不宜', '危':'危日、宜守不宜攻',
    '成':'宜嫁娶、签约、开市', '收':'宜收敛、纳财', '开':'宜祭祀、出行、开市', '闭':'闭日、诸事不宜' }
  return map[jc] || '平日'
})

// 星宿吉凶：后端 xiu_luck 未提供时，从 xiu_yi 有无做弱判断
const xiuLuck = computed(() => {
  const l = props.anchorSafe.xiu_luck
  if (l === '吉' || l === '凶' || l === '大吉' || l === '大凶') return l
  return null
})
const xiuLuckClass = computed(() => {
  const l = xiuLuck.value
  if (!l) return 'n'
  return (l.includes('吉')) ? 'g' : 'b'
})
const xiuLuckText = computed(() => {
  const l = xiuLuck.value
  if (l) return l
  const yi = props.anchorSafe.xiu_yi || []
  return yi.length ? ' — 宜' + yi.slice(0, 3).join('、') : ''
})

// ── 时辰轴 ──
const activePeriod = ref(null)
function shColorClass(sc) { return periodColorClass(sc) }
function isNow(sc) { return isNowPeriod(sc) }
function shortPeriod(p) { return String(p || '').replace('时', '') }

function togglePeriod(sc) {
  activePeriod.value = activePeriod.value === sc.period ? null : sc.period
}
const activeDetail = computed(() =>
  (props.anchorSafe.timeline || []).find(s => s?.period === activePeriod.value) || null
)

// 最佳时辰：优先「助我」且非当前；若当前正助我则直接用当前
const bestAction = computed(() => {
  const tl = props.anchorSafe.timeline || []
  if (!tl.length) return null
  const cur = tl.find(s => isNow(s))
  if (cur?.personal_type === 'good') return cur
  const good = tl.find(s => s?.personal_type === 'good')
  if (good) return good
  return cur || null
})

function actionTitle(p) {
  return p?.personal_type === 'good' ? '静养蓄气' : '日常节律'
}
function actionAdvice(p) {
  if (!p) return ''
  if (p.personal_type === 'good') return `此段${p.elem}气助你，宜静养、宜缓行。`
  if (p.personal_type === 'bad') return `此段${p.elem}气耗你，宜避开剧烈活动。`
  return `此段平和，按常规节律即可。`
}
const weakHint = computed(() => {
  const e = props.anchorSafe.dangling_elem
  return e ? '偏弱' : '需调养'
})

// ── 方位：显示依据真实飞星元素生成的生克推理 ──
const dirAdvice = (isGood) => {
  const o = props.anchorSafe.orientation
  if (!o) return ''
  // 后端 reason 为硬编码话术（与实际飞星无关），前端按真实元素生成
  const v = props.anchorSafe.v_base || {}
  let weak = null, strong = null
  const keys = ['wood', 'fire', 'earth', 'metal', 'water']
  if (Object.keys(v).length) {
    const sorted = [...keys].sort((a, b) => (v[a] ?? 50) - (v[b] ?? 50))
    weak = sorted[0]; strong = sorted[sorted.length - 1]
  }
  const text = buildDirAdvice({
    feixingElem: o.element, dir: isGood ? o.good_dir : o.bad_dir,
    isGood, weakElem: weak, strongElem: strong,
  })
  if (text) return text
  return isGood ? (o.good_advice || '') : (o.bad_advice || '')
}
</script>

<style scoped>
/* ═══ 主容器：多卡堆叠 ═══ */
.anchor-wrap { display: flex; flex-direction: column; gap: 12px; }
.at-card {
  background: #fff; border: 1px solid var(--border-subtle, #D8E2DE);
  border-radius: var(--radius-lg, 14px);
  box-shadow: 0 1px 2px rgba(14,58,52,.04), 0 1px 1px rgba(14,58,52,.03);
}
.c-head { display: flex; align-items: center; justify-content: space-between; padding: 13px 16px 0 }
.c-title { font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 7px; }
.c-title .dot { width: 6px; height: 6px; border-radius: 50%; background: #2E6B60; flex-shrink: 0; }
.c-sub { font-size: 11px; color: #8A9A94; letter-spacing: .3px }

/* ═══ 块2：吉时轴 ═══ */
.legend { display: flex; gap: 12px; font-size: 10.5px; color: #8A9A94; margin: 10px 16px 0; flex-wrap: wrap }
.legend span { display: flex; align-items: center; gap: 4px }
.lg { width: 8px; height: 8px; border-radius: 2px; display: inline-block }

.sh-wrap { padding: 12px 16px 15px }
.sh-axis { display: flex; gap: 3px; margin-bottom: 9px }
.sh {
  flex: 1; min-width: 0; height: 44px; border-radius: 6px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 4px; position: relative; padding: 0; cursor: pointer;
  background: #F5F5EE; border: 1px solid var(--border-subtle, #D8E2DE); color: #8A9A94;
  transition: transform .14s cubic-bezier(.2,0,0,1), box-shadow .14s;
}
.sh:hover { transform: translateY(-1px) }
.sh:active { transform: translateY(0) }
.sh-n { font-size: 12px; font-weight: 500; line-height: 1 }
.sh-bar { width: 14px; height: 2.5px; border-radius: 2px; background: currentColor; opacity: .55; display: block }
.sh.g { background: rgba(67,160,71,.08); border-color: rgba(67,160,71,.35); color: #43A047 }
.sh.w { background: rgba(212,160,23,.08); border-color: rgba(212,160,23,.4); color: #8A6A18 }
.sh.b { background: rgba(216,67,21,.08); border-color: rgba(216,67,21,.4); color: #D84315 }
.sh.n { background: #F5F5EE; border-color: var(--border-subtle, #D8E2DE); color: #8A9A94 }
/* 当令：实心环 */
.sh.now { box-shadow: 0 0 0 2px #2E6B60; font-weight: 600 }
/* 展开中 */
.sh[aria-pressed="true"] { box-shadow: 0 0 0 2px #144842 }

/* 时辰详情 */
.period-detail {
  padding: 10px 12px; border-radius: 10px; margin-bottom: 9px;
  background: var(--qn-brand-050, #F1F5F2); border: 1px solid var(--border-subtle, #D8E2DE);
}
.pd-head { display: flex; align-items: center; gap: 8px; margin-bottom: 5px }
.pd-badge {
  font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 9px;
  border: 1px solid; letter-spacing: .4px;
}
.pd-badge.g { background: rgba(67,160,71,.12); color: #43A047; border-color: rgba(67,160,71,.35) }
.pd-badge.w { background: rgba(212,160,23,.12); color: #8A6A18; border-color: rgba(212,160,23,.4) }
.pd-badge.b { background: rgba(216,67,21,.12); color: #D84315; border-color: rgba(216,67,21,.4) }
.pd-badge.n { background: #F5F5EE; color: #8A9A94; border-color: var(--border-subtle, #D8E2DE) }
.pd-name { font-size: 12.5px; font-weight: 600; color: #33403B }
.pd-elem { font-size: 11px; color: #5F6E68; margin-left: auto }
.pd-why { font-size: 11.5px; color: #5F6E68; line-height: 1.65 }

.action { padding: 11px 12px; border-radius: 10px; background: #F1F5F2; border: 1px solid var(--border-subtle, #D8E2DE) }
.action-empty {
  font-size: 11.5px; color: #8A9A94; text-align: center;
  background: #F5F5EE; border-style: dashed;
}
.a-head { display: flex; align-items: center; gap: 7px; margin-bottom: 5px; flex-wrap: wrap }
.a-badge { font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 10px; background: #144842; color: #fff; letter-spacing: .4px; flex-shrink: 0 }
.a-title { font-size: 12.5px; font-weight: 600 }
.a-when { font-size: 11px; color: #2E6B60; font-weight: 500; margin-left: auto; white-space: nowrap }
.a-why { font-size: 11.5px; color: #5F6E68; line-height: 1.65 }
.a-why b { color: #33403B; font-weight: 500 }

/* ═══ 块3：方位 ═══ */
.cmp { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; padding: 12px 16px 14px }
.side { border-radius: 10px; padding: 10px 11px; border: 1px solid }
.side.ok { background: rgba(67,160,71,.08); border-color: rgba(67,160,71,.35) }
.side.no { background: rgba(216,67,21,.08); border-color: rgba(216,67,21,.4) }
.s-l { font-size: 10.5px; letter-spacing: .6px; margin-bottom: 5px }
.side.ok .s-l { color: #43A047 }
.side.no .s-l { color: #D84315 }
.s-dir { font-size: 17px; font-weight: 600; letter-spacing: 1px; margin-bottom: 3px }
.side.ok .s-dir { color: #2E6B2E }
.side.no .s-dir { color: #8F2F12 }
.s-d { font-size: 11px; color: #5F6E68; line-height: 1.55 }

/* ═══ 块4：替换表 ═══ */
.swap { display: flex; flex-direction: column; gap: 8px; padding: 12px 16px 14px }
.sw {
  display: flex; align-items: center; gap: 9px; padding: 9px 11px; border-radius: 10px;
  background: #F1F5F2; border: 1px solid var(--border-subtle, #D8E2DE);
}
.sw-x { font-size: 12px; color: #D84315; text-decoration: line-through; opacity: .75; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis }
.sw-ar { font-size: 11px; color: #8A9A94; flex-shrink: 0 }
.sw-v { font-size: 12px; color: #43A047; font-weight: 500; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-align: right }

/* ═══ 块5：黄历宜忌 Tab ═══ */
.tabs { display: flex; gap: 5px; padding: 12px 16px 0; flex-wrap: wrap }
.tab {
  font-size: 11.5px; padding: 4px 11px; border-radius: 13px; cursor: pointer;
  border: 1px solid var(--border-subtle, #D8E2DE); background: #fff;
  color: #5F6E68; transition: all .16s cubic-bezier(.2,0,0,1); white-space: nowrap;
}
.tab.on { background: #144842; border-color: #144842; color: #fff }

.yj { display: flex; flex-direction: column; gap: 8px; padding: 11px 16px 0 }
.yj-row { display: flex; gap: 9px; align-items: flex-start }
.yj-k {
  font-size: 11px; font-weight: 600; width: 22px; height: 20px; border-radius: 5px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px;
}
.yj-k.g { background: rgba(67,160,71,.1); color: #43A047; border: 1px solid rgba(67,160,71,.35) }
.yj-k.b { background: rgba(216,67,21,.1); color: #D84315; border: 1px solid rgba(216,67,21,.4) }
.yj-v { font-size: 12px; color: #5F6E68; line-height: 1.6; padding-top: 1px }
.yj-v b { color: #33403B; font-weight: 500 }

.pz {
  margin: 11px 16px 0; padding: 9px 11px; border-radius: 10px;
  background: rgba(212,160,23,.08); border: 1px solid rgba(212,160,23,.4);
  font-size: 11.5px; line-height: 1.65; color: #6B5418;
}
.pz b { font-weight: 600; color: #5A4514 }

.more {
  padding: 10px 16px 13px; font-size: 11.5px; color: #8A9A94;
  text-align: right; cursor: pointer; letter-spacing: .4px;
}

/* 空态 */
.empty {
  padding: 14px 0; text-align: center; font-size: 11.5px;
  color: #8A9A94; font-style: italic;
}

/* 合规条（AGENT.md §四 硬约束） */
.compliance {
  margin: 0; padding: 9px 16px 11px; font-size: 10.5px; line-height: 1.6;
  color: #8A9A94; text-align: center;
  border-top: 1px solid var(--border-subtle, #D8E2DE);
}

/* 小屏 */
@media (max-width: 480px) {
  .cmp { grid-template-columns: 1fr }
  .sh-axis { gap: 2px }
  .sh { height: 40px }
  .sh-n { font-size: 11px }
  .sh-bar { width: 11px }
  .tabs { gap: 4px }
  .tab { padding: 4px 9px; font-size: 11px }
}
</style>
