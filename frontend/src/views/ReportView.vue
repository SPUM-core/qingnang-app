<template>
  <section class="page">
    <h1>报告查看</h1>
    <p class="page__desc">历次推演报告 + 趋势观察提示（非医疗措辞）</p>

    <div v-if="reports.length" class="list">
      <article v-for="r in reports" :key="r.id" class="report-card">
        <h3>{{ r.title }}</h3>
        <p class="meta">{{ r.created_at }} · {{ r.scope }}</p>
        <p class="notice">{{ r.notice }}</p>
      </article>
    </div>
    <p v-else class="placeholder">暂无报告 — 采集 PPG 观测或确认调理方案后自动生成</p>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client'

const reports = ref([])

onMounted(async () => {
  try {
    const res = await api.get('/api/v1/cases/reports')
    reports.value = res.data?.reports || []
  } catch (e) {
    console.error('[Report] load failed:', e.message)
    reports.value = []
  }
})
</script>

<style scoped>
.list { display: grid; gap: 14px; margin-top: 16px; }
.report-card { background: #fff; border: 1px solid #e4e8ee; border-radius: 8px; padding: 16px; }
.meta { font-size: 12px; color: #8a94a0; margin-top: 4px; }
.notice { margin-top: 10px; font-size: 12px; color: #7a5b2e; background: #fdf3e3; padding: 8px; border-radius: 4px; }
.placeholder { margin-top: 16px; color: #98a2b3; }
</style>
