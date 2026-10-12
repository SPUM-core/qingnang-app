<!-- ════════════════════════════════════════════════════════════════
  DebugBadge.vue — 页面调试角标（DEV ONLY）
  自动读取当前页面根元素的 data-page-id，固定显示在右上角。
  用法：在 App.vue 里 <DebugBadge v-if="import.meta.env.DEV" />
  ════════════════════════════════════════════════════════════════ -->
<template>
  <div class="dbg-badge" :title="'路由: ' + route.path">
    <span class="dbg-label">ID</span>
    <span class="dbg-id">{{ currentId }}</span>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const currentId = ref('--')

function readPageId() {
  // 等 router-view 渲染完再 query
  nextTick(() => {
    const el = document.querySelector('[data-page-id]')
    currentId.value = el?.dataset.pageId || '--'
  })
}

// 路由切换 → 重新读
watch(() => route.fullPath, readPageId)

onMounted(readPageId)
</script>

<style scoped>
.dbg-badge {
  position: fixed;
  top: 6px;
  right: 6px;
  z-index: 99999;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  background: rgba(216, 125, 27, 0.92);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  border-radius: 4px;
  letter-spacing: 0.5px;
  user-select: none;
  pointer-events: none;
  box-shadow: 0 1px 4px rgba(0,0,0,0.2);
}
.dbg-label { opacity: 0.85; }
.dbg-id { font-weight: 700; }
</style>
