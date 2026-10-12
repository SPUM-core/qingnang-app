<template>
  <div class="panel-lifetime" data-page-id="TP04">
    <div class="panel-info-bar">
      <span class="info-item">🗓️ 推演 {{ userBirth }} → 81 岁</span>
      <span class="info-item">🎯 {{ traj?.dayun?.length || 10 }} 段大运</span>
      <span class="info-item">📊 {{ n }} 个流年观测点</span>
    </div>
    <DriftChart
      v-if="traj"
      :trajectory="traj"
      height="360px"
    />
    <div v-else class="panel-empty">
      <p>尚未排盘八字大运</p>
      <button @click="loadData">加载终身推演</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import DriftChart from '../../components/charts/DriftChart.vue'
import { useVectorStore } from '../../stores/vector'
import { useUserStore } from '../../stores/user'

const vectorStore = useVectorStore()
const userStore = useUserStore()

const traj = computed(() => vectorStore.lifetimeTrajectory)
const n = computed(() => traj.value?.elems?.length || 0)
const userBirth = computed(() => userStore.birth_date || '—')

async function loadData() {
  await vectorStore.fetchYearView(81)
}

onMounted(() => {
  if (!vectorStore.lifetimeTrajectory) {
    loadData()
  }
})
</script>

<style scoped>
.panel-lifetime { }
.panel-info-bar {
  display: flex; gap: 12px; flex-wrap: wrap;
  padding: 8px 0 12px;
  font-size: 12px; color: var(--qn-ink-2);
}
.info-item {
  background: var(--qn-bg-2); padding: 4px 10px; border-radius: 12px;
}
.panel-empty {
  text-align: center; padding: 40px 20px; color: var(--qn-ink-3);
}
.panel-empty button {
  margin-top: 12px;
  padding: 8px 20px; border-radius: 20px; border: none;
  background: var(--qn-primary, #17534C); color: #fff;
  cursor: pointer;
}
</style>
