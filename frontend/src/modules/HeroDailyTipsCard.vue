<!-- ═══════════════════════════════════════════════════════════
  HeroDailyTipsCard.vue — 时空仪表（v3 重构）
  只保留块1：绿底时空仪表 — 干支、建除、星宿、当令时辰、四宫格
  宜忌/吉时/方位/替换/黄历 → 全部下沉到 AnchorTimelineCard
══════════════════════════════════════════════════════════════ -->
<template>
  <div class="anchor-card">
    <!-- 顶行：干支 + 建除/星宿 chip -->
    <div class="a-top">
      <div class="a-title-group">
        <p class="a-tag">{{ anchorSafe.ganzhi_year || '' }} · {{ anchorSafe.ganzhi_day || '' }}当令</p>
        <p class="a-gz">{{ anchorSafe.ganzhi_day || '' }} · {{ anchorSafe.jianchu || '' }}日</p>
        <p class="a-sub">{{ anchorSafe.ganzhi_month || '' }} · {{ anchorSafe.weather?.desc || '今日' }}</p>
      </div>
      <div class="a-seal">
        <span v-if="anchorSafe.jianchu" class="a-chip jc">{{ anchorSafe.jianchu }}日</span>
        <span v-if="anchorSafe.xiu" class="a-chip">{{ anchorSafe.xiu }}宿</span>
      </div>
    </div>

    <!-- 当令时辰状态条 -->
    <div class="a-now" v-if="nowPeriod">
      <div class="a-now-ring">
        <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round">
          <circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/>
        </svg>
      </div>
      <div class="a-now-txt">
        <span class="a-now-t">{{ nowPeriod.period }} {{ nowPeriod.range }} · {{ nowPeriod.elem }}气当令</span>
        <span class="a-now-s">你的{{ anchorSafe.dangling_elem || '弱形' }}偏弱，此段宜静不宜劳</span>
      </div>
      <span class="a-grade" :class="'g-' + (nowPeriod.personal_type || 'neutral')">{{ nowPeriod.personal_label || '平' }}</span>
    </div>

    <!-- 四宫格：值日 / 纳音 / 冲煞 / 日飞星 -->
    <div class="a-meta">
      <div class="a-cell" v-if="anchorSafe.tianshen">
        <span class="l">值日</span><span class="v">{{ anchorSafe.tianshen }}</span>
      </div>
      <div class="a-cell" v-if="anchorSafe.na_yin_day">
        <span class="l">纳音</span><span class="v">{{ anchorSafe.na_yin_day }}</span>
      </div>
      <div class="a-cell" v-if="anchorSafe.chong">
        <span class="l">冲煞</span><span class="v">{{ anchorSafe.chong }}</span>
      </div>
      <div class="a-cell" v-if="anchorSafe.feixing_day">
        <span class="l">日飞星</span><span class="v">{{ anchorSafe.feixing_day }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  anchorSafe: { type: Object, required: true },
})

// 当前时辰（从 timeline 找，无则占位）
const nowPeriod = computed(() => {
  const tl = props.anchorSafe.timeline || []
  if (!tl.length) return null
  const now = new Date()
  const h = now.getHours()
  // range 是 "23-1", "1-3" 格式
  for (const item of tl) {
    if (!item?.range) continue
    try {
      const [s, e] = item.range.split('-').map(Number)
      if (isNaN(s) || isNaN(e)) continue
      if (s < e && h >= s && h < e) return item
      if (s >= e && (h >= s || h < e)) return item
    } catch { continue }
  }
  return tl[8] || tl[0] || null  // fallback 申时 / 子时 / null
})
</script>

<style scoped>
.anchor-card {
  border-radius: var(--radius-lg); padding: 18px 20px 16px; color: #fff;
  background: linear-gradient(152deg, #1D5A50 0%, #144842 62%, #0E3A34 100%);
  box-shadow: 0 4px 14px rgba(14, 58, 52, .22);
}
.a-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.a-tag { font-size: 11px; letter-spacing: 2.5px; color: rgba(255,255,255,.6); margin: 0 0 3px; }
.a-gz { font-size: 24px; font-weight: 600; letter-spacing: 3px; line-height: 1.1; margin: 0; }
.a-sub { font-size: 12px; color: rgba(255,255,255,.72); margin-top: 4px; letter-spacing: .5px; }
.a-seal { display: flex; flex-direction: column; align-items: flex-end; gap: 5px; flex-shrink: 0; }
.a-chip {
  font-size: 11px; padding: 3px 9px; border-radius: 11px; letter-spacing: .6px;
  background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.2); white-space: nowrap;
}
.a-chip.jc { background: rgba(212,160,23,.26); border-color: rgba(212,160,23,.42) }

.a-now {
  margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,.14);
  display: flex; align-items: center; gap: 10px;
}
.a-now-ring {
  width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
  background: rgba(255,255,255,.12); border: 1.5px solid rgba(255,255,255,.35);
  display: flex; align-items: center; justify-content: center;
}
.a-now-txt { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.a-now-t { font-size: 13px; font-weight: 500; }
.a-now-s { font-size: 11px; color: rgba(255,255,255,.66); line-height: 1.45; }
.a-grade {
  margin-left: auto; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 12px;
  flex-shrink: 0; letter-spacing: .5px;
}
.g-good { background: rgba(134,212,168,.24); color: #C7EFDD; border: 1px solid rgba(134,212,168,.4); }
.g-neutral { background: rgba(230,183,80,.24); color: #F4DFAE; border: 1px solid rgba(230,183,80,.4); }
.g-bad { background: rgba(224,120,95,.24); color: #F5CFC2; border: 1px solid rgba(224,120,95,.4); }

.a-meta {
  margin-top: 12px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px;
  background: rgba(255,255,255,.13); border-radius: 9px; overflow: hidden;
}
.a-cell { background: rgba(255,255,255,.07); padding: 8px 4px; text-align: center; display: flex; flex-direction: column; gap: 2px; }
.a-cell .l { font-size: 10px; color: rgba(255,255,255,.55); letter-spacing: .4px; }
.a-cell .v { font-size: 12px; font-weight: 600; color: #fff; line-height: 1.3; }

@media (max-width: 480px) {
  .a-meta { grid-template-columns: repeat(2, 1fr); }
  .anchor-card { padding: 16px 18px; }
}
</style>
