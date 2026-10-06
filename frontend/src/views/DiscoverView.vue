<template>
  <section class="page discover">
    <!-- 顶部双 Tab -->
    <div class="discover-tabs">
      <button class="dtab" :class="{ active: activeTab === 'knowledge' }"
              @click="switchTab('knowledge')">
        <QIcon name="book" :size="16" />
        <span>知识</span>
      </button>
      <button class="dtab" :class="{ active: activeTab === 'shop' }"
              @click="switchTab('shop')">
        <QIcon name="cart" :size="16" />
        <span>商城</span>
      </button>
    </div>

    <!-- 内容区（keep-alive 保留滚动位置） -->
    <KeepAlive>
      <KnowledgeBaseView v-if="activeTab === 'knowledge'" />
      <ShopView v-else-if="activeTab === 'shop'" />
    </KeepAlive>
  </section>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import QIcon from '../components/ui/QIcon.vue'
import KnowledgeBaseView from './KnowledgeBaseView.vue'
import ShopView from './ShopView.vue'

const route = useRoute()
const activeTab = ref('knowledge')

function switchTab(tab) {
  activeTab.value = tab
  // 同步 URL query（深链友好）
  const next = new URLSearchParams(route.query)
  if (tab === 'knowledge') next.delete('tab')
  else next.set('tab', tab)
  history.replaceState(null, '', next.toString() ? ('?' + next.toString()) : route.path)
}

onMounted(() => {
  // 从 URL query 恢复
  const tab = route.query.tab
  if (tab === 'shop') activeTab.value = 'shop'
})

watch(() => route.query.tab, (t) => {
  if (t === 'shop') activeTab.value = 'shop'
  else activeTab.value = 'knowledge'
})
</script>

<style scoped>
.discover-tabs {
  display: flex; gap: 0; margin: 0 16px 8px;
  background: var(--qn-surface); border: 1px solid var(--qn-line); border-radius: 12px;
  overflow: hidden;
}
.dtab {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 10px 16px; border: none; background: transparent;
  color: var(--qn-ink-3); font-size: calc(13px * var(--qn-fs-scale)); font-weight: 500;
  cursor: pointer; transition: all 0.2s;
  letter-spacing: 1px;
  -webkit-tap-highlight-color: transparent;
}
.dtab:hover { color: var(--qn-emerald); background: rgba(var(--qn-emerald-rgb),0.04); }
.dtab.active {
  color: #fff;
  background: linear-gradient(135deg, var(--qn-emerald) 0%, var(--qn-emerald-dark) 100%);
  font-weight: 600;
}

/* 纵向屏：tab 自适应宽度 */
@media (orientation: portrait) {
  .discover-tabs { margin: 0 0 8px; }
}
</style>
