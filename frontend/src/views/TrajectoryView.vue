<template>
  <div class="trajectory-page" data-page-id="P03">
    <!-- ═══ 顶栏 ═══ -->
    <div class="tj-header">
      <div class="tj-title-row">
        <button class="back-btn" @click="$router.push('/')">←</button>
        <h1>体质曲线</h1>
        <span class="tj-version">SPUM v2 · 四视图</span>
      </div>

      <!-- ═══ 4 Tab 切换 ═══ -->
      <nav class="tj-tabs">
        <button
          v-for="t in tabs"
          :key="t.key"
          class="tj-tab"
          :class="{ active: activeTab === t.key }"
          @click="activeTab = t.key"
        >
          <span class="tj-tab-icon">{{ t.icon }}</span>
          <span class="tj-tab-label">{{ t.label }}</span>
          <span v-if="t.badge" class="tj-tab-badge">{{ t.badge }}</span>
        </button>
      </nav>

      <!-- 选年器（年视图/节气视图/调节视图需要选年份/年龄） -->
      <div v-if="activeTab !== 'lifetime'" class="tj-selector">
        <label>年龄：</label>
        <input
          type="range" min="1" max="81" :value="yearAge"
          @input="e => yearAge = parseInt(e.target.value)"
          class="tj-range"
        />
        <span class="tj-year-label">
          {{ yearAge }}岁 · {{ 1990 + yearAge }}年 · {{ yearView?.liunian?.name || '—' }}
        </span>
      </div>
    </div>

    <!-- ═══ 内容区（4 tab 渲染） ═══ -->
    <div class="tj-content">
      <!-- ① 终身推演（年粒度 · 大运+流年） -->
      <LifetimePanel v-if="activeTab === 'lifetime'" />

      <!-- ② 流年气运（某年 · 24 节气五行强度 + 流年大运叠加） -->
      <JieqiTimeline
        v-else-if="activeTab === 'year'"
        :data="yearView"
        :onPick-year="pickYear"
      />

      <!-- ③ 节气属性（24 卡片墙 · 暂不做曲线） -->
      <JieqiGrid
        v-else-if="activeTab === 'jieqi'"
        :data="yearView"
        :selected="selectedJieqiIdx"
        @select="selectedJieqiIdx = $event"
      />

      <!-- ④ 调节视图（虚线=自然发展 vs 实线=青囊介入实测） -->
      <AdjustChart
        v-else-if="activeTab === 'adjust'"
        :data="adjustData"
      />
    </div>

    <!-- ═══ 页脚说明 ═══ -->
    <footer class="tj-footer">
      <span v-if="activeTab === 'jieqi' && yearView?.user_location">
        🌐 出生地：{{ yearView.user_location.city }}
        · 经度 {{ yearView.user_location.longitude }}°E
        · 真太阳时校正 {{ yearView.user_location.true_solar_offset_min }} 分钟
      </span>
      <span v-else-if="activeTab === 'year'">
        💡 点击下方大运标签上的某一年可切换调节视图对比
      </span>
      <span v-else>
        数据来自 SPUM 五运六气引擎
      </span>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useVectorStore } from '../stores/vector'
import LifetimePanel from './trajectory/LifetimePanel.vue'
import JieqiTimeline from './trajectory/JieqiTimeline.vue'
import JieqiGrid from './trajectory/JieqiGrid.vue'
import AdjustChart from './trajectory/AdjustChart.vue'

const vectorStore = useVectorStore()

const tabs = [
  { key: 'lifetime', label: '终身推演', icon: '🌀', badge: null },
  { key: 'year',     label: '流年气运', icon: '🎋', badge: '24节' },
  { key: 'jieqi',    label: '节气属性', icon: '🗓️', badge: null },
  { key: 'adjust',   label: '调节视图', icon: '⚗️', badge: 'vs' },
]

const activeTab = ref('lifetime')
const yearAge = ref(30)
const selectedJieqiIdx = ref(0)

// ═══ 真实数据源（后端 API）═══
const yearView = computed(() => vectorStore.jieqiView)
const adjustData = computed(() => vectorStore.adjustView)

// 选年变化 → 拉节气/调节数据
watch(yearAge, async (age) => {
  await Promise.all([
    vectorStore.fetchJieqiView(age),
    vectorStore.fetchAdjustmentView(),
  ])
})

// 切 tab → 懒加载对应数据
watch(activeTab, async (tab) => {
  await nextTick()
  if (tab === 'lifetime' && !vectorStore.lifetimeTrajectory) {
    vectorStore.fetchYearView(81)
  } else if ((tab === 'year' || tab === 'jieqi') && !vectorStore.jieqiView) {
    vectorStore.fetchJieqiView(yearAge.value)
  } else if (tab === 'adjust' && !vectorStore.adjustView) {
    vectorStore.fetchAdjustmentView()
  }
})

function pickYear({ age }) {
  yearAge.value = age
}

onMounted(async () => {
  // 预拉默认数据（登录状态下自动触发）
  try {
    await Promise.all([
      vectorStore.fetchYearView(40),           // 终身推演（默认 tab）
      vectorStore.fetchJieqiView(yearAge.value),
      vectorStore.fetchAdjustmentView(),
    ])
  } catch {}
})
</script>

<style scoped>
.trajectory-page {
  min-height: 100%;
  padding: 16px;
  padding-bottom: 80px;   /* 给 tab bar 留空间 */
}
.tj-header {
  margin-bottom: 16px;
}
.tj-title-row {
  display: flex; align-items: center; gap: 10px; margin-bottom: 14px;
}
.back-btn {
  width: 32px; height: 32px; border-radius: 50%; border: none;
  background: var(--qn-bg-2); color: var(--qn-ink);
  font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center;
}
.back-btn:hover { background: var(--qn-line); }
.tj-title-row h1 { font-size: 20px; margin: 0; color: var(--qn-ink); }
.tj-version { font-size: 10px; color: var(--qn-ink-3); background: var(--qn-bg-2); padding: 2px 8px; border-radius: 10px; }

.tj-tabs {
  display: flex; gap: 2px; background: var(--qn-bg-2); border-radius: 10px; padding: 3px;
  overflow-x: auto; white-space: nowrap;
}
.tj-tab {
  flex: 1; min-width: 90px;
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 10px 8px; border: none; border-radius: 8px;
  background: transparent; color: var(--qn-ink-2);
  cursor: pointer; font-size: 11px; font-weight: 500;
  transition: background 0.15s, color 0.15s;
  position: relative;
}
.tj-tab:hover { color: var(--qn-ink); }
.tj-tab.active {
  background: var(--qn-surface);
  color: var(--qn-primary);
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.tj-tab-icon { font-size: 16px; }
.tj-tab-badge {
  position: absolute; top: 4px; right: 6px;
  font-size: 9px; padding: 1px 4px; border-radius: 6px;
  background: var(--qn-primary, #17534C); color: #fff;
}

.tj-selector {
  margin-top: 12px;
  display: flex; align-items: center; gap: 10px;
  font-size: 13px; color: var(--qn-ink-2);
}
.tj-range {
  flex: 1; max-width: 300px;
  height: 4px; -webkit-appearance: none;
  background: var(--qn-bg-2); border-radius: 2px; outline: none;
}
.tj-range::-webkit-slider-thumb {
  -webkit-appearance: none; width: 16px; height: 16px;
  border-radius: 50%; background: var(--qn-primary, #17534C);
  cursor: pointer;
}
.tj-year-label { font-size: 12px; color: var(--qn-ink); font-weight: 500; }

.tj-content {
  /* 子组件各自撑满 */
}

.tj-footer {
  position: fixed; bottom: 0; left: 0; right: 0;
  padding: 8px 16px; font-size: 11px; color: var(--qn-ink-3);
  background: var(--qn-bg, #fff); border-top: 1px solid var(--qn-line);
  text-align: center;
}
</style>
