<template>
  <!-- 📅 今日时空锚点卡：四柱 + 当令五行 + 旺相休囚 + 建除宜忌 + 调候总结 -->
  <div v-if="ctx" class="st-spacetime-card" :class="{ degraded: ctx.is_degraded }">
    <div class="st-head">
      <div class="st-gz-row">
        <span class="st-gz-cell" v-for="(gz, key) in ctx.sizhu" :key="key">
          <span class="st-gz-label">{{ gz[0] }}</span>
          <span class="st-gz-zhi">{{ gz[1] }}</span>
          <span class="st-gz-wx" :style="{ color: wxColor(ctx.sizhu.wuxing[key]) }">
            {{ wxCn(ctx.sizhu.wuxing[key]) }}
          </span>
        </span>
      </div>
      <div class="st-meta">
        <span class="st-jieqi">🌤️ {{ ctx.jieqi || '--' }}</span>
        <span class="st-ts" v-if="ctx.is_degraded" title="节气近似计算">
          ⚠️ 近似
        </span>
      </div>
    </div>

    <div class="st-body">
      <div class="st-lingshou">
        <span class="st-ls-label">当令</span>
        <span class="st-ls-gz">{{ ctx.lingshou_gz }}</span>
        <span class="st-ls-wx" :style="{ color: wxColor(ctx.lingshou_cn || lingshouWx) }">
          {{ ctx.lingshou_cn || lingshouWx }}
        </span>
        <span class="st-ls-tag">{{ statusTag(lingshouStatus) }}</span>
      </div>

      <div class="st-wuxing-row">
        <div v-for="wx in wxList" :key="wx" class="st-wx-cell" :class="'st-' + wx">
          <span class="st-wx-cn">{{ wxCn(wx) }}</span>
          <span class="st-wx-status" :class="'st-' + (ctx.wuxing_status[wx] || '平')">
            {{ ctx.wuxing_status[wx] || '平' }}
          </span>
        </div>
      </div>

      <div class="st-jianchu-row">
        <span class="st-jc-tag">{{ ctx.jianchu }}日</span>
        <span v-if="ctx.jianchu_advice?.good" class="st-jc-good">宜：{{ ctx.jianchu_advice.good }}</span>
        <span v-if="ctx.jianchu_advice?.bad" class="st-jc-bad">忌：{{ ctx.jianchu_advice.bad }}</span>
      </div>

      <div v-if="tiaoHou" class="st-tiao-hou">
        <span class="st-th-emoji">{{ thEmoji }}</span>
        <span class="st-th-text">{{ tiaoHou.summary }}</span>
      </div>

      <div v-if="tiaoHou?.priorities?.length" class="st-priorities">
        <span v-for="(p, i) in tiaoHou.priorities.slice(0, 3)" :key="i"
              class="st-pri-chip" :class="'st-pri-' + p.direction">
          {{ p.cn }}形{{ p.direction }}
        </span>
      </div>
    </div>

    <div class="st-foot" @click="refresh">
      <span class="st-refresh-ico">🔄</span>
      <span>更新时空</span>
    </div>
  </div>
  <div v-else class="st-spacetime-card st-loading">
    <span class="st-loading-text">⏳ 正在计算今日时空…</span>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { api } from '../api/client'

const props = defineProps({
  /** 是否开启时空调候（默认开启） */
  enabled: { type: Boolean, default: true },
})

const ctx = ref(null)
const tiaoHou = ref(null)
const loading = ref(false)

// 五行名映射
const WX_CN = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
function wxCn(w) { return WX_CN[w] || w }
const WX_COLOR = {
  wood: 'var(--qn-wood)', fire: 'var(--qn-fire)', earth: 'var(--qn-earth)',
  metal: 'var(--qn-metal)', water: 'var(--qn-water)',
}
function wxColor(cn) {
  const wx = Object.keys(WX_CN).find(k => WX_CN[k] === cn)
  return wx ? WX_COLOR[wx] : 'var(--qn-ink-2)'
}
const wxList = ['wood', 'fire', 'earth', 'metal', 'water']

const lingshouWx = computed(() => {
  if (!ctx.value?.ctx) return ''
  return ctx.value.ctx.lingshou_cn || ''
})
const lingshouStatus = computed(() => {
  if (!ctx.value?.ctx?.wuxing_status) return ''
  const lingshouKey = ctx.value.ctx.wuxing
  return ctx.value.ctx.wuxing_status[lingshouKey] || ''
})

const thEmoji = computed(() => {
  if (!tiaoHou.value?.priorities?.length) return '🧭'
  const top = tiaoHou.value.priorities[0]
  const map = { '补': '💊', '泻': '🌊', '养': '🌿', '平': '⚖️', '换时辰': '⏰' }
  return map[top.direction] || '🧭'
})

function statusTag(s) {
  return s || '平'
}

async function refresh() {
  if (loading.value) return
  loading.value = true
  try {
    // 优先调 /api/v1/spacetime/daily-brief（一站式带调候）
    const r = await api.get('/api/v1/spacetime/daily-brief', { timeout: 5000 })
    const d = r.data
    ctx.value = d.ctx
    tiaoHou.value = d.tiao_hou
  } catch {
    // fallback：单独拉 context
    try {
      const r2 = await api.get('/api/v1/spacetime/context', { timeout: 3000 })
      ctx.value = r2.data
      tiaoHou.value = null
    } catch (e) {
      console.warn('[Spacetime] load failed:', e.message)
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => { if (props.enabled) refresh() })

defineExpose({ refresh })
</script>

<style scoped>
.st-spacetime-card {
  background: linear-gradient(135deg, rgba(34,139,34,0.08), rgba(212,160,23,0.06));
  border: 1px solid rgba(34,139,34,0.18);
  border-radius: 14px;
  padding: 14px 16px 10px;
  margin: 10px 0 6px;
}
.st-spacetime-card.st-loading { text-align: center; padding: 20px; }
.st-spacetime-card.degraded { border-color: rgba(212,160,23,0.35); }

.st-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }

.st-gz-row { display: flex; gap: 12px; }
.st-gz-cell {
  display: flex; flex-direction: column; align-items: center; gap: 1px;
  padding: 4px 8px; background: rgba(255,255,255,0.6); border-radius: 8px;
}
.st-gz-label { font-size: calc(12px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); }
.st-gz-zhi { font-size: calc(14px * var(--qn-fs-scale)); font-weight: 700; color: var(--qn-ink-2); }
.st-gz-wx { font-size: calc(10px * var(--qn-fs-scale)); font-weight: 500; }

.st-meta { display: flex; align-items: center; gap: 6px; }
.st-jieqi { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); }
.st-ts { font-size: calc(10px * var(--qn-fs-scale)); color: #D4A017; }

.st-body { display: flex; flex-direction: column; gap: 8px; }

.st-lingshou {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; background: rgba(34,139,34,0.08); border-radius: 20px; align-self: flex-start;
}
.st-ls-label { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); }
.st-ls-gz { font-size: calc(13px * var(--qn-fs-scale)); font-weight: 700; color: var(--qn-ink); }
.st-ls-wx { font-size: calc(13px * var(--qn-fs-scale)); font-weight: 700; }
.st-ls-tag {
  font-size: calc(10px * var(--qn-fs-scale));
  background: rgba(34,139,34,0.18); color: var(--qn-emerald);
  padding: 1px 8px; border-radius: 10px; font-weight: 600;
}

.st-wuxing-row { display: flex; gap: 6px; justify-content: space-between; }
.st-wx-cell {
  flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 6px 2px; background: rgba(255,255,255,0.4); border-radius: 8px;
  border-top: 2px solid transparent;
}
.st-wx-cell.st-wood { border-top-color: var(--qn-wood); }
.st-wx-cell.st-fire { border-top-color: var(--qn-fire); }
.st-wx-cell.st-earth { border-top-color: var(--qn-earth); }
.st-wx-cell.st-metal { border-top-color: var(--qn-metal); }
.st-wx-cell.st-water { border-top-color: var(--qn-water); }

.st-wx-cn { font-size: calc(12px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); }
.st-wx-status {
  font-size: calc(10px * var(--qn-fs-scale)); font-weight: 600;
  padding: 1px 6px; border-radius: 8px;
}
.st-wx-status.st-旺 { background: rgba(34,139,34,0.15); color: var(--qn-emerald); }
.st-wx-status.st-相 { background: rgba(34,139,34,0.08); color: var(--qn-emerald); }
.st-wx-status.st-休 { background: rgba(107,114,119,0.1); color: var(--qn-ink-2); }
.st-wx-status.st-囚 { background: rgba(212,160,23,0.12); color: #8A6A10; }
.st-wx-status.st-死 { background: rgba(216,67,21,0.12); color: var(--qn-fire); }

.st-jianchu-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 6px 10px; background: rgba(212,160,23,0.08); border-radius: 8px;
}
.st-jc-tag { font-size: calc(12px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); }
.st-jc-good { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-emerald); font-weight: 500; }
.st-jc-bad { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-fire); font-weight: 500; }

.st-tiao-hou {
  display: flex; gap: 8px; align-items: flex-start;
  padding: 8px 12px; background: rgba(34,139,34,0.06); border-radius: 10px;
}
.st-th-emoji { font-size: calc(18px * var(--qn-fs-scale)); flex-shrink: 0; }
.st-th-text { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink); line-height: 1.6; }

.st-priorities { display: flex; gap: 6px; flex-wrap: wrap; }
.st-pri-chip {
  font-size: calc(11px * var(--qn-fs-scale)); font-weight: 600;
  padding: 3px 10px; border-radius: 12px;
}
.st-pri-chip.st-pri-补 { background: rgba(34,139,34,0.15); color: var(--qn-emerald); }
.st-pri-chip.st-pri-泻 { background: rgba(220,20,60,0.12); color: var(--qn-fire); }
.st-pri-chip.st-pri-养 { background: rgba(107,114,119,0.1); color: var(--qn-ink-2); }
.st-pri-chip.st-pri-平 { background: rgba(107,114,119,0.08); color: var(--qn-ink-3); }
.st-pri-chip.st-pri-换时辰 { background: rgba(212,160,23,0.12); color: #8A6A10; }

.st-foot {
  display: flex; justify-content: flex-end; gap: 4px;
  padding-top: 6px; margin-top: 6px;
  border-top: 1px dashed rgba(34,139,34,0.2);
  font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3);
  cursor: pointer;
}
.st-foot:hover { color: var(--qn-emerald); }
</style>
