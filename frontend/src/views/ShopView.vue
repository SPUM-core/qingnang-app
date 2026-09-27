<template>
  <div class="shop-view">
    <!-- 顶部免责声明（常驻） -->
    <div class="shop-disclaimer">
      <span class="disclaimer-icon">⚠️</span>
      <span class="disclaimer-text">青囊商城为分销带货模式，商品均为第三方提供的日常调养消费品，<b>非药品，不能替代医疗诊疗</b>；青囊体质研判仅供养生参考，身体疾患请及时就医。分销商品的发货、售后由对应供货商负责。</span>
    </div>

    <!-- 头部 -->
    <header class="shop-header">
      <h1 class="shop-title">🛒 青囊商城</h1>
      <p class="shop-sub">选品对接第三方分销平台 · 青囊自建 SPUM 体质适配标签 · 不碰仓储售后</p>

      <!-- 搜索 + 筛选 -->
      <div class="shop-filters">
        <div class="filter-search">
          <input v-model="keyword" type="text" placeholder="搜索商品 / SPUM 标签（如：湿遏 气虚）" />
        </div>
        <div class="filter-sort">
          <select v-model="sortBy">
            <option value="match">适配度优先</option>
            <option value="price-asc">价格从低到高</option>
            <option value="price-desc">价格从高到低</option>
            <option value="rating">评分优先</option>
          </select>
        </div>
      </div>
    </header>

    <!-- 品类 Tab -->
    <nav class="shop-tabs">
      <button v-for="cat in categories" :key="cat" :class="{ active: activeCat === cat }" @click="activeCat = cat">
        {{ cat }}
        <span class="tab-count">{{ getCatCount(cat) }}</span>
      </button>
    </nav>

    <!-- 商品网格 -->
    <div class="shop-grid">
      <RouterLink
        v-for="item in filteredList"
        :key="item.id"
        :to="`/shop/${item.id}`"
        class="shop-card"
      >
        <div class="shop-card__cover" :style="{ background: item.cover_color }">
          <span class="cover-emoji">{{ item.emoji }}</span>
          <div v-if="item.spum_match_for_hu" class="match-badge">
            <span class="match-score">{{ item.spum_match_for_hu.score }}</span>
            <span class="match-label">适配</span>
          </div>
        </div>

        <div class="shop-card__body">
          <h3 class="shop-card__name">{{ item.name }}</h3>
          <p class="shop-card__meta">{{ item.sub_category }} · {{ item.origin.split('·')[1] || item.origin }}</p>

          <!-- SPUM 适配标签 -->
          <div class="shop-card__spum-tags">
            <span v-for="tag in item.spum_tags.wuxing" :key="tag" class="spum-tag spum-wuxing">{{ tag }}</span>
            <span v-for="tag in item.spum_tags.suitable.slice(0, 2)" :key="tag" class="spum-tag spum-good">✓ {{ tag }}</span>
            <span v-for="tag in item.spum_tags.avoid.slice(0, 1)" :key="tag" class="spum-tag spum-bad">✗ {{ tag }}</span>
          </div>

          <!-- 价格 + 评分 -->
          <div class="shop-card__footer">
            <div class="price">
              <span class="price-symbol">¥</span>
              <span class="price-num">{{ item.price }}</span>
            </div>
            <div class="rating">
              <span>★ {{ item.rating }}</span>
              <span class="orders">{{ item.order_count }} 人已购</span>
            </div>
          </div>

          <!-- 分销跳转 -->
          <div class="shop-card__cta">
            <span class="affiliate-hint">🔗 跳转分销供货商</span>
          </div>
        </div>
      </RouterLink>
    </div>

    <!-- 空状态 -->
    <div v-if="filteredList.length === 0" class="shop-empty">
      <p>😶 该品类暂无符合搜索的商品</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { shop as shopApi } from '../api/client'

const keyword = ref('')
const activeCat = ref('全部')
const sortBy = ref('match')
const items = ref([])

const categories = ['全部', '食材药膳', '体质服饰', '家居配饰', '日用调养']

// 后端 category → 前端分类
const CAT_MAP = {
  herb: '食材药膳', clothing: '体质服饰',
  home: '家居配饰', daily: '日用调养',
}

const EMOJI_MAP = { herb: '🌿', clothing: '👕', home: '🧘', daily: '🧊' }
const COLOR_MAP = {
  herb: 'linear-gradient(135deg,#2A6B62,#89B5AF)',
  clothing: 'linear-gradient(135deg,#8B6F47,#C9A87C)',
  home: 'linear-gradient(135deg,#3D4F5F,#7A8A99)',
  daily: 'linear-gradient(135deg,#5B7065,#A8BEB3)',
}

function adaptBackendItem(b) {
  const st = b.spum_tags || {}
  // 后端 spum_tags 结构: { tags: [], match_for: [] }
  const rawTags = st.tags || []
  const matchFor = st.match_for || []
  return {
    id: b.sku,                       // 模板用 item.id 作 key
    sku: b.sku,
    name: b.title || b.name || '未命名商品',
    category: CAT_MAP[b.category] || b.category || '其他',
    price: b.price ?? 0,
    emoji: EMOJI_MAP[b.category] || '🎁',
    cover_color: COLOR_MAP[b.category] || 'linear-gradient(135deg,#888,#bbb)',
    sub_category: rawTags[0] || '',
    origin: matchFor.length ? matchFor.join('·') : '',
    description: b.description || '',
    provider_url: b.provider_url || '',
    spum_tags: {
      suitable: rawTags.slice(0, 2),
      wuxing: matchFor.slice(0, 1),
      avoid: [],
    },
    rating: b.avg_rating ?? 0,
    review_count: b.review_count ?? 0,
    spum_match_for_hu: b.spum_match_for_hu || { score: Math.round((b.avg_rating ?? 3) * 20), reason: '' },
    image_url: b.cover_url || b.provider_url || '',
  }
}

onMounted(async () => {
  try {
    const r = await shopApi.items()
    // 后端直接返回 list（不是 {items: [...]})
    const raw = r.data
    const list = Array.isArray(raw) ? raw : (raw?.items || [])
    items.value = list.map(adaptBackendItem)
  } catch (e) {
    console.warn('[Shop] load failed:', e.message)
    items.value = []
  }
})

const getCatCount = (cat) => cat === '全部' ? items.value.length : items.value.filter(i => i.category === cat).length

const filteredList = computed(() => {
  let list = items.value

  if (activeCat.value !== '全部') {
    list = list.filter(i => i.category === activeCat.value)
  }

  if (keyword.value.trim()) {
    const k = keyword.value.trim()
    list = list.filter(i =>
      i.name.includes(k) ||
      (i.spum_tags?.suitable || []).some(t => t.includes(k)) ||
      (i.spum_tags?.wuxing || []).some(t => t.includes(k)) ||
      (i.spum_tags?.avoid || []).some(t => t.includes(k))
    )
  }

  switch (sortBy.value) {
    case 'match': list = [...list].sort((a, b) => (b.spum_match_for_hu?.score || 0) - (a.spum_match_for_hu?.score || 0)); break
    case 'price-asc': list = [...list].sort((a, b) => a.price - b.price); break
    case 'price-desc': list = [...list].sort((a, b) => b.price - a.price); break
    case 'rating': list = [...list].sort((a, b) => b.rating - a.rating); break
  }

  return list
})
</script>

<style scoped>
.shop-view { max-width: 1200px; margin: 0 auto; padding: 24px; }

/* 免责声明 */
.shop-disclaimer {
  background: #FFF8E1; border-left: 4px solid #D4A017; border-radius: 4px;
  padding: 12px 16px; margin-bottom: 20px;
  display: flex; gap: 10px; align-items: flex-start;
  font-size: 13px; color: #6B5B2C; line-height: 1.6;
}
.disclaimer-icon { font-size: 16px; }
.disclaimer-text b { color: #B8860B; }

/* 头部 */
.shop-header { margin-bottom: 20px; }
.shop-title { font-size: 28px; margin: 0 0 4px; color: var(--qingnang-emerald); }
.shop-sub { font-size: 13px; color: var(--ink-tertiary); margin: 0 0 16px; }
.shop-filters { display: flex; gap: 12px; flex-wrap: wrap; }
.filter-search input {
  flex: 1; min-width: 240px; padding: 10px 14px; border: 1px solid var(--ink-line);
  border-radius: 8px; font-size: 14px; background: var(--qingnang-card);
}
.filter-search input:focus { outline: none; border-color: var(--qingnang-spirit); }
.filter-sort select {
  padding: 10px 14px; border: 1px solid var(--ink-line); border-radius: 8px;
  font-size: 14px; background: var(--qingnang-card); cursor: pointer;
}

/* 品类 Tab */
.shop-tabs { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
.shop-tabs button {
  padding: 8px 18px; border: 1px solid var(--ink-line); border-radius: 20px;
  background: var(--qingnang-card); color: var(--ink-secondary);
  cursor: pointer; font-size: 14px; transition: all 0.2s;
  display: flex; gap: 6px; align-items: center;
}
.shop-tabs button:hover { border-color: var(--qingnang-spirit); color: var(--qingnang-emerald); }
.shop-tabs button.active {
  background: var(--qingnang-emerald); color: #fff; border-color: var(--qingnang-emerald);
}
.tab-count {
  background: rgba(0,0,0,0.06); padding: 1px 7px; border-radius: 10px; font-size: 12px;
}
.shop-tabs button.active .tab-count { background: rgba(255,255,255,0.25); }

/* 商品网格 */
.shop-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 20px;
}
.shop-card {
  background: var(--qingnang-card); border: 1px solid var(--ink-line); border-radius: 12px;
  overflow: hidden; text-decoration: none; color: inherit;
  transition: transform 0.2s, box-shadow 0.2s; display: flex; flex-direction: column;
}
.shop-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(26, 77, 69, 0.12);
  border-color: var(--qingnang-spirit);
}

.shop-card__cover {
  height: 140px; display: flex; align-items: center; justify-content: center;
  position: relative; color: rgba(255,255,255,0.9);
}
.cover-emoji { font-size: 56px; filter: drop-shadow(0 2px 8px rgba(0,0,0,0.2)); }

.match-badge {
  position: absolute; top: 12px; right: 12px;
  background: rgba(255,255,255,0.95); border-radius: 8px;
  padding: 4px 10px; display: flex; gap: 2px; align-items: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.match-score { font-weight: 700; color: var(--qingnang-emerald); font-size: 15px; }
.match-label { font-size: 11px; color: var(--ink-tertiary); }

.shop-card__body { padding: 14px; display: flex; flex-direction: column; flex: 1; }
.shop-card__name { font-size: 15px; margin: 0 0 4px; line-height: 1.4; color: var(--ink-primary); }
.shop-card__meta { font-size: 12px; color: var(--ink-tertiary); margin: 0 0 10px; }

.shop-card__spum-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }
.spum-tag { font-size: 11px; padding: 3px 8px; border-radius: 12px; line-height: 1; }
.spum-wuxing { background: #E8F5E9; color: #2E7D32; }
.spum-good { background: #E3F2FD; color: #1565C0; }
.spum-bad { background: #FFEBEE; color: #C62828; }

.shop-card__footer { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.price { display: flex; align-items: baseline; gap: 2px; }
.price-symbol { font-size: 13px; color: var(--trend-up); }
.price-num { font-size: 20px; font-weight: 700; color: var(--trend-up); }
.rating { font-size: 12px; color: var(--ink-secondary); text-align: right; }
.rating .orders { display: block; color: var(--ink-tertiary); font-size: 11px; margin-top: 2px; }

.shop-card__cta { margin-top: auto; padding-top: 8px; border-top: 1px dashed var(--ink-line); }
.affiliate-hint { font-size: 12px; color: var(--qingnang-spirit); }

.shop-empty { text-align: center; padding: 80px; color: var(--ink-tertiary); }
</style>
