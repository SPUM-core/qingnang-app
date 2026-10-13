<!-- ═══════════════════════════════════════════════════════════
  SpacetimeHeroCard.vue — Dashboard 英雄卡 · 时空入口
  合并原 SpacetimeContextCard + AnchorTimelineCard 精华，
  点击整张卡进入 /spacetime 时空详情页
══════════════════════════════════════════════════════════════ -->
<template>
  <div v-if="ctx" class="st-hero-card" :class="{ degraded: ctx.is_degraded }" @click="goDetail">
    <!-- 顶部：四柱干支 + 节气 -->
    <div class="st-top">
      <div class="st-gz-row">
        <span class="st-gz-cell" v-for="(gz, key) in ctx.sizhu" :key="key">
          <span class="st-gz-zhi">{{ gz[1] }}</span>
          <span class="st-gz-tg">{{ gz[0] }}</span>
          <span class="st-gz-wx" :style="{ color: wxColor(ctx.sizhu.wuxing[key]) }">
            {{ wxCn(ctx.sizhu.wuxing[key]) }}
          </span>
        </span>
      </div>
      <div class="st-qi-col">
        <span class="st-qi-val">🌤️ {{ ctx.jieqi?.current_term || '--' }}</span>
        <span v-if="ctx.is_degraded" class="st-qi-warn">⚠️ 近似</span>
      </div>
    </div>

    <!-- 当令 + 旺相休囚 -->
    <div class="st-lingshou-row">
      <div class="st-ls-pill">
        <span class="st-ls-label">当令</span>
        <span class="st-ls-gz">{{ ctx.lingshou_gz }}</span>
        <span class="st-ls-wx" :style="{ color: wxColor(ctx.lingshou) }">{{ lingshouWx }}</span>
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

    <!-- 建除 + 调候 + chip -->
    <div class="st-bottom">
      <div class="st-jc-line">
        <span class="st-jc-badge">{{ ctx.jianchu }}日</span>
        <span v-if="ctx.jianchu_advice?.good" class="st-jc-good">宜 {{ ctx.jianchu_advice.good }}</span>
      </div>
      <div v-if="tiaoHou" class="st-th-snippet">
        <span class="st-th-emoji">{{ thEmoji }}</span>
        <span class="st-th-text">{{ tiaoHou.summary }}</span>
      </div>
      <div v-if="tiaoHou?.priorities?.length" class="st-pri-row">
        <span v-for="(p, i) in tiaoHou.priorities.slice(0, 3)" :key="i"
              class="st-pri-chip" :class="'stp-' + p.direction">
          {{ p.cn }}形{{ p.direction }}
        </span>
        <span class="st-arrow">›</span>
      </div>
    </div>

    <div v-if="loading" class="st-loader">⏳</div>
  </div>
  <div v-else class="st-hero-card st-hero-loading">⏳ 时空计算中…</div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'

const router = useRouter()

const ctx = computed(() => {
  if (rawCtx.value && rawCtx.value.ctx) return rawCtx.value
  return rawCtx.value
})
const rawCtx = ref(null)
const tiaoHou = computed(() => rawTh.value)
const rawTh = ref(null)
const loading = ref(false)

import { ref } from 'vue'

const WX_CN = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
function wxCn(w) { return WX_CN[w] || w }
const WX_COLOR = { wood: '#2E7D32', fire: '#C62828', earth: '#8D6E00', metal: '#616161', water: '#1565C0' }
function wxColor(key) { return WX_COLOR[key] || '#5F6E68' }
const wxList = ['wood', 'fire', 'earth', 'metal', 'water']

const lingshouWx = computed(() => {
  const c = rawCtx.value
  if (!c) return ''
  const wxKey = c.lingshou || c.ctx?.lingshou || ''
  return WX_CN[wxKey] || wxKey
})

const thEmoji = computed(() => {
  if (!rawTh.value?.priorities?.length) return '🧭'
  const map = { '补': '💊', '泻': '🌊', '养': '🌿', '平': '⚖️', '换时辰': '⏰' }
  return map[rawTh.value.priorities[0].direction] || '🧭'
})

async function refresh() {
  if (loading.value) return
  loading.value = true
  try {
    const r = await api.get('/api/v1/spacetime/daily-brief', { timeout: 5000 })
    const d = r.data
    rawCtx.value = d.ctx
    rawTh.value = d.tiao_hou
  } catch {
    try {
      const r2 = await api.get('/api/v1/spacetime/context', { timeout: 3000 })
      rawCtx.value = r2.data
    } catch (e) {
      console.warn('[Spacetime] load failed:', e.message)
    }
  } finally {
    loading.value = false
  }
}

function goDetail() {
  router.push('/spacetime')
}

onMounted(() => refresh())

defineExpose({ refresh })
</script>

<style scoped>
.st-hero-card {
  position: relative; cursor: pointer;
  background: linear-gradient(135deg, #0d3b2e 0%, #1a5c48 40%, #2d7a5e 100%);
  border: 1px solid rgba(46,204,113,0.25);
  border-radius: 18px;
  padding: 16px 18px 14px;
  margin: 10px 0 8px;
  box-shadow: 0 4px 20px rgba(13,59,46,0.25), inset 0 1px 0 rgba(255,255,255,0.08);
  transition: transform .25s cubic-bezier(.2,0,.2,1), box-shadow .25s;
  color: #e8f5e9;
  overflow: hidden;
}
.st-hero-card:active { transform: scale(0.98); box-shadow: 0 2px 10px rgba(13,59,46,0.3) }
.st-hero-card.degraded { border-color: rgba(212,160,23,0.4); background: linear-gradient(135deg, #5d4e18 0%, #7a6a2a 100%) }
.st-hero-loading { text-align: center; padding: 28px; color: rgba(255,255,255,0.6); font-size: 14px; }

/* ═══ 顶部：四柱 + 节气 ═══ */
.st-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 14px; }
.st-gz-row { display: flex; gap: 8px; }
.st-gz-cell {
  display: flex; flex-direction: column; align-items: center; gap: 1px;
  padding: 5px 8px;
  background: rgba(255,255,255,0.12);
  backdrop-filter: blur(4px);
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.1);
}
.st-gz-zhi { font-size: 18px; font-weight: 700; color: #fff; line-height: 1.1; }
.st-gz-tg { font-size: 11px; font-weight: 500; color: rgba(255,255,255,0.75); line-height: 1; }
.st-gz-wx { font-size: 10px; font-weight: 600; letter-spacing: 0.5px; }

.st-qi-col { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; padding-top: 3px; }
.st-qi-val { font-size: 13px; font-weight: 500; color: rgba(255,255,255,0.85); }
.st-qi-warn { font-size: 10px; color: #f7d36b; }

/* ═══ 当令 + 旺相休囚 ═══ */
.st-lingshou-row { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }

.st-ls-pill {
  display: flex; align-items: center; gap: 5px;
  padding: 5px 12px;
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 20px;
  flex-shrink: 0;
}
.st-ls-label { font-size: 11px; color: rgba(255,255,255,0.7); }
.st-ls-gz { font-size: 14px; font-weight: 700; color: #fff; }
.st-ls-wx { font-size: 12px; font-weight: 700; }

.st-wx-bars { display: flex; gap: 5px; flex: 1; }
.st-bar-cell {
  flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 5px 2px;
  background: rgba(255,255,255,0.08);
  border-radius: 8px;
  border-top: 3px solid transparent;
}
.stb-wood { border-top-color: #66bb6a; }
.stb-fire { border-top-color: #ef5350; }
.stb-earth { border-top-color: #d4a017; }
.stb-metal { border-top-color: #bdbdbd; }
.stb-water { border-top-color: #42a5f5; }

.stb-wx { font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.9); }
.stb-status { font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 8px; }
.sts-旺 { background: rgba(76,175,80,0.3); color: #a5d6a7; }
.sts-相 { background: rgba(76,175,80,0.18); color: #c8e6c9; }
.sts-休 { background: rgba(158,158,158,0.2); color: #e0e0e0; }
.sts-囚 { background: rgba(212,160,23,0.25); color: #ffe082; }
.sts-死 { background: rgba(244,67,54,0.25); color: #ef9a9a; }
.sts-平 { background: rgba(255,255,255,0.15); color: rgba(255,255,255,0.7); }

/* ═══ 底部：建除 + 调候 + chip ═══ */
.st-bottom { display: flex; flex-direction: column; gap: 7px; }

.st-jc-line { display: flex; align-items: center; gap: 8px; }
.st-jc-badge {
  font-size: 13px; font-weight: 700; padding: 3px 10px;
  background: rgba(212,160,23,0.25); color: #ffe082;
  border-radius: 6px; border: 1px solid rgba(212,160,23,0.4);
}
.st-jc-good { font-size: 12px; color: rgba(255,255,255,0.8); }

.st-th-snippet {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 8px 12px;
  background: rgba(255,255,255,0.1);
  border-radius: 10px;
}
.st-th-emoji { font-size: 16px; flex-shrink: 0; }
.st-th-text { font-size: 12px; color: rgba(255,255,255,0.9); line-height: 1.55; }

.st-pri-row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.st-pri-chip {
  font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 12px;
}
.stp-补 { background: rgba(76,175,80,0.3); color: #a5d6a7; border: 1px solid rgba(76,175,80,0.5); }
.stp-泻 { background: rgba(244,67,54,0.25); color: #ef9a9a; border: 1px solid rgba(244,67,54,0.4); }
.stp-养 { background: rgba(158,158,158,0.2); color: #e0e0e0; border: 1px solid rgba(158,158,158,0.3); }
.stp-平 { background: rgba(255,255,255,0.12); color: rgba(255,255,255,0.75); }
.stp-换时辰 { background: rgba(212,160,23,0.25); color: #ffe082; border: 1px solid rgba(212,160,23,0.4); }
.st-arrow { margin-left: auto; font-size: 18px; color: rgba(255,255,255,0.5); font-weight: 300; }

.st-loader {
  position: absolute; right: 14px; top: 14px;
  font-size: 14px; opacity: 0.7;
}
</style>
