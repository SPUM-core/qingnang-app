<template>
  <div class="kb-head" data-page-id="P14">
      <div>
        <h1>知识卡片</h1>
        <p class="kb-desc">系统根据你的数字模型，为你推荐这些内容</p>
      </div>
      <div class="kb-filters">
        <button
          v-for="f in filters" :key="f.key"
          class="filter-btn" :class="{ active: activeFilter === f.key }"
          @click="activeFilter = f.key">
          {{ f.icon }} {{ f.label }}
          <span class="filter-count">{{ f.count }}</span>
        </button>
      </div>
    </div>

    <!-- 个性化推荐 banner -->
    <div class="kb-banner" v-if="personalizedHints.length">
      <span class="banner-icon">🎯</span>
      <div class="banner-body">
        <p class="banner-title">青囊为你定制推荐</p>
        <p class="banner-desc">基于你的数字模型（{{ myCoreDeviation || '五形分布' }}），
          优先推荐{{ personalizedHints.join('、') }}相关内容</p>
      </div>
    </div>

    <!-- 卡片网格 -->
    <div class="kb-grid">
      <article
        v-for="item in filteredItems"
        :key="item.id"
        class="kb-card"
        @click="openItem(item)">

        <!-- 封面 -->
        <div class="kb-card-cover" :style="{ background: item.coverGradient }">
          <span class="kb-card-type">{{ typeIcon(item.type) }}</span>
          <span v-if="item.duration || item.readTime" class="kb-card-meta">
            {{ item.duration || item.readTime }}
          </span>
          <span v-if="item.personalized" class="kb-card-badge">🎯 为你推荐</span>
        </div>

        <!-- 内容 -->
        <div class="kb-card-body">
          <h3 class="kb-card-title">{{ item.title }}</h3>
          <p class="kb-card-summary">{{ item.summary }}</p>

          <div class="kb-card-tags">
            <span v-for="t in item.tags.slice(0, 3)" :key="t" class="kb-tag">{{ t }}</span>
          </div>

          <div class="kb-card-foot">
            <span class="kb-card-author">{{ item.author }}</span>
            <span v-if="item.source" class="kb-card-source">{{ item.source }}</span>
          </div>
        </div>
      </article>
    </div>

    <p v-if="!filteredItems.length" class="placeholder">暂无匹配的知识卡片</p>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api/client'
import { useVectorStore, toCoreDeviation } from '../stores/vector'

const vectorStore = useVectorStore()
const myCoreDeviation = computed(() => toCoreDeviation(vectorStore.latestVector || vectorStore.vBase))

const ITEMS = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const r = await api.get('/api/v1/knowledge/')
    ITEMS.value = r.data?.items || []
  } catch (e) {
    console.warn('[KB] load failed:', e.message)
    ITEMS.value = []
  } finally {
    loading.value = false
  }
})

const filters = [
  { key: 'all', label: '全部', icon: '📚' },
  { key: 'video', label: '短视频', icon: '🎬' },
  { key: 'article', label: '文章', icon: '📖' },
  { key: 'podcast', label: '收听', icon: '🎧' }
].map(f => ({ ...f, count: ITEMS.value.filter(i => f.key === 'all' ? true : i.type === f.key).length }))

const activeFilter = ref('all')
const filteredItems = computed(() =>
  activeFilter.value === 'all'
    ? ITEMS.value
    : ITEMS.value.filter(i => i.type === activeFilter.value)
)

// 个性化标签（从后端返回的 personalized items 动态推导）
const personalizedHints = computed(() => {
  const set = new Set()
  ITEMS.value.filter(i => i.personalized).forEach(i => {
    if (i.reason) set.add(i.reason)
  })
  return [...set]
})
function typeIcon(t) {
  return ({ video: '🎬', article: '📖', podcast: '🎧' })[t] || '📄'
}

function openItem(item) {
  if (item.url) {
    window.open(item.url, '_blank')
  } else {
    console.info('[KnowledgeBase] item has no url yet:', item.id, item.title)
  }
}
</script>

<style scoped>
/* max-width 由全局 .page 统一管理（1200px） */

.kb-head {
  display: flex; justify-content: space-between; align-items: flex-end;
  flex-wrap: wrap; gap: 16px;
  margin-bottom: 16px;
}
.kb-head h1 { font-size: calc(22px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-emerald); margin: 0; }
.kb-desc { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 4px 0 0; }

.kb-filters { display: flex; gap: 6px; flex-wrap: wrap; }
.filter-btn {
  font-size: calc(13px * var(--qn-fs-scale)); padding: 6px 14px; border-radius: 20px;
  border: 1px solid var(--qn-line); background: var(--qn-surface); color: var(--qn-ink-2);
  cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 6px;
}
.filter-btn:hover { border-color: var(--qn-emerald); color: var(--qn-emerald); }
.filter-btn.active { background: var(--qn-emerald); border-color: var(--qn-emerald); color: #fff; }
.filter-count {
  background: var(--qn-paper); color: var(--qn-ink-3);
  padding: 0 6px; border-radius: 10px; font-size: calc(11px * var(--qn-fs-scale)); font-weight: 600;
}
.filter-btn.active .filter-count { background: rgba(255,255,255,0.2); color: #fff; }

/* ── 个性化 banner ── */
.kb-banner {
  display: flex; gap: 14px; align-items: flex-start;
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.06) 0%, rgba(var(--qn-emerald-light-rgb),0.08) 100%);
  border: 1px solid rgba(var(--qn-emerald-rgb),0.15);
  border-radius: var(--qn-r-lg); padding: 14px 18px;
  margin-bottom: 18px;
}
.banner-icon { font-size: calc(22px * var(--qn-fs-scale)); flex-shrink: 0; }
.banner-title { font-size: calc(13px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-emerald); margin: 0 0 4px; }
.banner-desc { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin: 0; line-height: 1.6; }

/* ── 卡片网格 ── */
.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.kb-card {
  /* ⚠️ border 已删 */
  background: var(--qn-surface); border-radius: var(--qn-r-lg);
  overflow: hidden; cursor: pointer; transition: all 0.2s;
  display: flex; flex-direction: column;
}
.kb-card:hover {
  box-shadow: var(--qn-shadow-2);
  border-color: rgba(var(--qn-emerald-rgb),0.25);
  transform: translateY(-2px);
}

/* 封面 */
.kb-card-cover {
  position: relative; height: 120px;
  display: flex; align-items: center; justify-content: center;
}
.kb-card-type { font-size: calc(36px * var(--qn-fs-scale)); opacity: 0.9; }
.kb-card-meta {
  position: absolute; bottom: 8px; right: 10px;
  font-size: calc(11px * var(--qn-fs-scale)); color: rgba(255,255,255,0.9);
  background: rgba(0,0,0,0.25); padding: 1px 7px; border-radius: 10px;
}
.kb-card-badge {
  position: absolute; top: 8px; left: 10px;
  font-size: calc(10px * var(--qn-fs-scale)); color: #fff; font-weight: 600;
  background: rgba(var(--qn-emerald-rgb),0.85); padding: 2px 8px; border-radius: 10px;
}

/* 内容 */
.kb-card-body { padding: 14px; flex: 1; display: flex; flex-direction: column; }
.kb-card-title {
  font-size: calc(15px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); margin: 0 0 6px;
  line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.kb-card-summary {
  font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); margin: 0 0 10px; line-height: 1.6;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.kb-card-tags { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 10px; }
.kb-tag {
  font-size: calc(10px * var(--qn-fs-scale)); color: var(--qn-ink-3);
  background: var(--qn-paper); border: 1px solid var(--qn-line);
  padding: 1px 6px; border-radius: 3px; font-weight: 500;
}
.kb-card-foot {
  display: flex; justify-content: space-between; align-items: center;
  font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-top: auto;
  padding-top: 8px; border-top: 1px dashed var(--qn-line);
}
.kb-card-author { font-weight: 500; color: var(--qn-ink-2); }

.placeholder { color: var(--qn-ink-3); text-align: center; padding: 40px; font-size: calc(13px * var(--qn-fs-scale)); }

/* ── 纵向屏（portrait）/窄屏：卡片单列、减 padding ── */
@media (orientation: portrait), (max-width: 480px) {
  .kb-grid { grid-template-columns: 1fr; gap: 12px; }
  .kb-head { flex-direction: column; align-items: flex-start; gap: 10px; }
  .kb-banner { padding: 10px 12px; }
}
</style>
