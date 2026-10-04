<template>
  <div class="shop-detail" v-if="item">
    <!-- 顶部免责 -->
    <div class="shop-disclaimer">
      <span class="disclaimer-icon">⚠️</span>
      <span class="disclaimer-text">青囊商城为分销带货模式，商品均为第三方提供的日常调养消费品，<b>非药品，不能替代医疗诊疗</b>；青囊体质研判仅供养生参考，身体疾患请及时就医。分销商品的发货、售后由对应供货商负责。</span>
    </div>

    <!-- 返回 -->
    <a class="back-link" @click.prevent="$router.back()" aria-label="返回">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
      返回商城
    </a>

    <div class="detail-layout">
      <!-- 左列：商品信息 -->
      <section class="detail-left">
        <!-- 商品封面 -->
        <div class="detail-cover" :style="{ background: item.cover_color }">
          <span class="cover-emoji">{{ item.emoji }}</span>
          <div class="match-big">
            <span class="match-num">{{ item.spum_match?.score || item.spum_tags?.score || '--' }}</span>
            <span class="match-text">青囊适配度</span>
          </div>
        </div>

        <!-- 基本信息 -->
        <div class="detail-basic">
          <h1 class="detail-name">{{ item.name }}</h1>
          <div class="detail-meta">
            <span class="price"><b>¥{{ item.price }}</b></span>
            <span class="sep">·</span>
            <span>★ {{ item.rating }}</span>
            <span class="sep">·</span>
            <span>{{ item.order_count }} 人已购</span>
            <span class="sep">·</span>
            <span>佣金 {{ item.commission }}%</span>
          </div>
          <div class="detail-specs">
            <p><b>品类：</b>{{ item.category }} · {{ item.sub_category }}</p>
            <p><b>规格：</b>{{ item.specs }}</p>
            <p><b>来源：</b>{{ item.origin }}</p>
          </div>
        </div>

        <!-- 分销跳转 -->
        <div class="affiliate-block">
          <a :href="item.affiliate_url" target="_blank" class="affiliate-btn">
            🔗 前往供货商查看详情 & 购买
          </a>
          <p class="affiliate-note">点击将跳转至第三方分销平台完成购买，发货/售后由对应供货商负责</p>
        </div>

        <!-- 基础电商标签 -->
        <div class="detail-tags">
          <h4>基础标签（来自供货商）</h4>
          <div class="tag-list">
            <span v-for="t in item.base_tags" :key="t" class="tag tag-base">{{ t }}</span>
          </div>
        </div>
      </section>

      <!-- 右列：SPUM + 评价 -->
      <section class="detail-right">
        <!-- SPUM 适配分析 -->
        <div class="spum-match">
          <h3 class="section-title">🧬 SPUM 体质适配分析</h3>

          <!-- 五形适配 -->
          <div class="wuxing-row">
            <span class="wuxing-label">五形指向</span>
            <div class="wuxing-chips">
              <span v-for="w in item.spum_tags.wuxing" :key="w" class="wuxing-chip">{{ w }}</span>
            </div>
          </div>

          <!-- 适合 -->
          <div class="match-block match-good">
            <div class="match-title">✓ 适合人群</div>
            <div class="match-tags">
              <span v-for="s in item.spum_tags.suitable" :key="s" class="match-tag good">{{ s }}</span>
            </div>
          </div>

          <!-- 慎用 -->
          <div class="match-block match-bad">
            <div class="match-title">✗ 慎用人群</div>
            <div class="match-tags">
              <span v-for="a in item.spum_tags.avoid" :key="a" class="match-tag bad">{{ a }}</span>
            </div>
          </div>

          <!-- 青囊标注说明 -->
          <p class="spum-note">📝 <b>青囊标注：</b>{{ item.spum_tags.note }}</p>

          <!-- 🎯 适配你的数字模型（动态匹配，从后端 /shop/recommend 拉） -->
          <div v-if="item.spum_match" class="spum-for-me">
            <h4>🎯 适配你的数字模型</h4>
            <ul>
              <li v-for="(r, i) in item.spum_match.reasons" :key="i">{{ r }}</li>
            </ul>
            <div v-if="item.spum_match.warnings?.length" class="spum-warn">
              <b>⚠️ 注意：</b>
              <span v-for="(w, i) in item.spum_match.warnings" :key="i">{{ w }}<span v-if="i < item.spum_match.warnings.length - 1">；</span></span>
            </div>
          </div>
        </div>

        <!-- AI 聚合摘要 -->
        <div class="review-summary" v-if="reviews?.ai_summary">
          <h3 class="section-title">🤖 青囊综合体验摘要（AI 聚合）</h3>
          <p class="summary-text">{{ reviews.ai_summary }}</p>
          <p class="summary-disclaimer">{{ reviews.ai_summary_disclaimer }}</p>
        </div>
        <div v-else class="review-summary empty">
          <h3 class="section-title">🤖 青囊综合体验摘要（AI 聚合）</h3>
          <p class="summary-empty">暂无用户体验反馈</p>
          <p class="summary-disclaimer">商品新上架或暂无已购用户提交反馈</p>
        </div>

        <!-- 全部真实评价 -->
        <div class="review-real">
          <h3 class="section-title">
            💬 全部真实用户评价
            <span class="review-count">{{ reviews?.reviews?.length || 0 }} 条（总 {{ reviews?.feedback_count || 0 }} 条已购反馈）</span>
          </h3>

          <div v-if="reviews?.reviews?.length" class="review-list">
            <div v-for="r in reviews.reviews" :key="r.id" class="review-item">
              <div class="review-header">
                <span class="review-user">{{ r.user_id }}</span>
                <span class="review-trait" v-if="r['体质']">{{ r['体质'] }}</span>
                <span class="review-stars">
                  <span v-for="i in 5" :key="i" :class="{ on: i <= r.rating }">★</span>
                </span>
                <span class="review-date">{{ r.date }}</span>
              </div>
              <p class="review-text">{{ r.text }}</p>
              <div class="review-tags">
                <span v-for="t in r.tags" :key="t" class="review-tag">{{ t }}</span>
              </div>
            </div>
          </div>
          <div v-else class="review-empty">
            <p>暂无已购用户评价</p>
          </div>
        </div>

        <!-- 反馈入口（内测阶段手动） -->
        <div class="feedback-entry">
          <h4>📝 提交体验反馈</h4>
          <p class="feedback-hint">完成订单后可在此提交你的真实体验，反馈将被 AI 聚合进商品摘要。原始反馈不可篡改。</p>
          <button class="feedback-btn" @click="showFeedback = true">我要写反馈</button>
        </div>
      </section>
    </div>

    <!-- 反馈弹窗 -->
    <div v-if="showFeedback" class="feedback-modal" @click.self="showFeedback = false">
      <div class="feedback-modal__content">
        <h3>提交体验反馈</h3>
        <p class="modal-note">你的反馈必须是已完成订单的真实体验。系统会自动过滤功效宣称（如"治愈""治好"）。</p>
        <div class="form-row">
          <label>总体满意度</label>
          <div class="star-picker">
            <span v-for="i in 5" :key="i" @click="feedback.rating = i" :class="{ on: i <= feedback.rating }">★</span>
          </div>
        </div>
        <div class="form-row">
          <label>具体感受（可选）</label>
          <textarea v-model="feedback.text" rows="4" placeholder="比如：这个茶饮我喝了两周，感觉比较温润，但是空腹喝有点反酸…（请描述你的自身体感，不要写治病效果）"></textarea>
        </div>
        <p v-if="feedback.hasForbidden" class="forbidden-warn">⚠️ 检测到违规功效表述（如"治愈""治好""根治"），请修改后再提交</p>
        <div class="modal-actions">
          <button class="btn-ghost" @click="showFeedback = false">取消</button>
          <button class="btn-primary" :disabled="feedback.hasForbidden" @click="submitFeedback">提交反馈</button>
        </div>
      </div>
    </div>
  </div>

  <div v-else class="shop-detail__notfound">
    <p>😶 商品不存在</p>
    <a class="back-link" @click.prevent="$router.back()" aria-label="返回">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
      返回商城
    </a>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { shop as shopApi } from '../api/client'

const route = useRoute()
const itemData = ref(null)
const reviewsData = ref(null)

onMounted(async () => {
  const sku = route.params.id
  try {
    const r = await shopApi.detail(sku)
    itemData.value = r.data?.item || r.data
  } catch (e) {
    console.warn('[ShopDetail] load failed:', e.message)
  }
})

const item = computed(() => itemData.value)
const reviews = computed(() => reviewsData.value)

const showFeedback = ref(false)
const feedback = reactive({ rating: 5, text: '', hasForbidden: false })

const forbiddenWords = ['治好', '治愈', '根治', '见效', '快速下降', '直接降']

// 简单功效拦截
import { watch } from 'vue'
watch(() => feedback.text, (v) => {
  feedback.hasForbidden = forbiddenWords.some(w => v.includes(w))
})

async function submitFeedback() {
  try {
    await shopApi.review({
      sku: route.params.id,
      rating: feedback.rating,
      content: feedback.text,
    })
    alert('反馈已提交 ✅')
  } catch (e) {
    alert('反馈提交失败：' + (e.response?.data?.detail || e.message))
    return
  }
  showFeedback.value = false
  feedback.text = ''
  feedback.rating = 5
}
</script>

<style scoped>
.shop-detail { max-width: 1200px; margin: 0 auto; padding: 24px; }

/* 免责 */
.shop-disclaimer {
  background: #FFF8E1; border-left: 4px solid #D4A017; border-radius: 4px;
  padding: 12px 16px; margin-bottom: 16px;
  display: flex; gap: 10px; align-items: flex-start;
  font-size: 13px; color: #6B5B2C; line-height: 1.6;
}
.disclaimer-icon { font-size: 16px; }
.disclaimer-text b { color: #B8860B; }

/* back-btn 已废弃 → 全局 .back-link */

.detail-layout { display: grid; grid-template-columns: 360px 1fr; gap: 32px; }
@media (max-width: 900px) { .detail-layout { grid-template-columns: 1fr; } }

/* 左列 */
.detail-cover {
  height: 280px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  color: rgba(255,255,255,0.9); position: relative;
}
.cover-emoji { font-size: 120px; filter: drop-shadow(0 4px 12px rgba(0,0,0,0.2)); }

.match-big {
  position: absolute; bottom: 20px; right: 20px;
  background: rgba(255,255,255,0.95); border-radius: 12px;
  padding: 10px 16px; text-align: center;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}
.match-num { font-size: 28px; font-weight: 800; color: var(--qingnang-emerald); display: block; line-height: 1; }
.match-text { font-size: 12px; color: var(--ink-tertiary); margin-top: 2px; }

.detail-basic { padding: 20px 0; border-bottom: 1px solid var(--ink-line); }
.detail-name { font-size: 20px; margin: 0 0 10px; line-height: 1.4; color: var(--ink-primary); }
.detail-meta { font-size: 13px; color: var(--ink-secondary); display: flex; gap: 6px; align-items: baseline; flex-wrap: wrap; }
.detail-meta .price b { font-size: 20px; color: var(--trend-up); }
.detail-meta .sep { color: var(--ink-tertiary); }
.detail-specs { margin-top: 16px; font-size: 13px; color: var(--ink-secondary); }
.detail-specs p { margin: 4px 0; }

.affiliate-block { padding: 20px 0; border-bottom: 1px solid var(--ink-line); text-align: center; }
.affiliate-btn {
  display: block; background: var(--qingnang-emerald); color: #fff;
  padding: 14px 20px; border-radius: 10px; text-decoration: none;
  font-size: 15px; font-weight: 600; transition: background 0.2s;
}
.affiliate-btn:hover { background: #13403a; }
.affiliate-note { font-size: 12px; color: var(--ink-tertiary); margin: 10px 0 0; }

.detail-tags { padding: 16px 0; }
.detail-tags h4 { font-size: 13px; margin: 0 0 8px; color: var(--ink-secondary); }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { font-size: 12px; padding: 4px 10px; border-radius: 12px; }
.tag-base { background: var(--ink-line); color: var(--ink-secondary); }

/* 右列 */
.section-title { font-size: 16px; margin: 0 0 14px; color: var(--ink-primary); }
.review-count { font-size: 12px; color: var(--ink-tertiary); font-weight: 400; margin-left: 8px; }

.spum-match {
  background: var(--qingnang-card); border: 1px solid var(--ink-line);
  border-radius: 12px; padding: 20px; margin-bottom: 24px;
}
.wuxing-row { display: flex; gap: 10px; align-items: center; margin-bottom: 14px; }
.wuxing-label { font-size: 13px; color: var(--ink-secondary); min-width: 80px; }
.wuxing-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.wuxing-chip { font-size: 12px; padding: 4px 10px; background: #E8F5E9; color: #2E7D32; border-radius: 12px; }

.match-block { margin-bottom: 12px; }
.match-title { font-size: 13px; margin-bottom: 6px; }
.match-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.match-tag { font-size: 12px; padding: 4px 12px; border-radius: 14px; }
.match-tag.good { background: #E3F2FD; color: #1565C0; }
.match-tag.bad { background: #FFEBEE; color: #C62828; }

.spum-note { font-size: 13px; color: var(--ink-secondary); margin-top: 14px; padding-top: 12px; border-top: 1px dashed var(--ink-line); }

.spum-for-me {
  margin-top: 16px; padding: 14px; background: var(--qingnang-paper);
  border-radius: 8px; border-left: 3px solid var(--qingnang-spirit);
}
.spum-for-me h4 { margin: 0 0 8px; font-size: 13px; color: var(--qingnang-emerald); }
.spum-for-me ul { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.8; color: var(--ink-primary); }
.spum-warn { margin-top: 10px; font-size: 12px; color: #C62828; }

/* AI 摘要 */
.review-summary {
  background: linear-gradient(135deg, #E8F5E9 0%, #F1F8E9 100%);
  border: 1px solid #C8E6C9; border-radius: 12px;
  padding: 20px; margin-bottom: 24px;
}
.review-summary.empty { background: #FAFAFA; border-color: var(--ink-line); }
.summary-text { font-size: 14px; line-height: 1.8; color: var(--ink-primary); margin: 0 0 10px; }
.summary-empty { font-size: 14px; color: var(--ink-tertiary); margin: 0; }
.summary-disclaimer { font-size: 11px; color: #666; margin: 0; padding-top: 8px; border-top: 1px dashed rgba(0,0,0,0.1); }

/* 全部真实评价 */
.review-real {
  background: var(--qingnang-card); border: 1px solid var(--ink-line);
  border-radius: 12px; padding: 20px; margin-bottom: 24px;
}
.review-list { display: flex; flex-direction: column; gap: 16px; }
.review-item { padding: 14px; background: var(--qingnang-paper); border-radius: 8px; }
.review-header { display: flex; gap: 10px; align-items: center; margin-bottom: 6px; font-size: 13px; }
.review-user { font-weight: 600; color: var(--ink-primary); }
.review-trait { background: #E8F5E9; color: #2E7D32; padding: 2px 8px; border-radius: 10px; font-size: 11px; }
.review-stars { color: #FF9800; }
.review-stars span { color: #E0E0E0; margin-right: 2px; }
.review-stars span.on { color: #FF9800; }
.review-date { margin-left: auto; color: var(--ink-tertiary); font-size: 12px; }
.review-text { font-size: 14px; color: var(--ink-primary); margin: 6px 0 8px; line-height: 1.6; }
.review-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.review-tag { font-size: 11px; padding: 2px 8px; background: #F5F5F0; color: var(--ink-secondary); border-radius: 10px; }
.review-empty { text-align: center; padding: 40px; color: var(--ink-tertiary); }

/* 反馈入口 */
.feedback-entry {
  background: var(--qingnang-card); border: 1px dashed var(--ink-line);
  border-radius: 12px; padding: 20px; text-align: center;
}
.feedback-entry h4 { margin: 0 0 6px; font-size: 14px; color: var(--ink-primary); }
.feedback-hint { font-size: 13px; color: var(--ink-tertiary); margin: 0 0 12px; line-height: 1.6; }
.feedback-btn {
  background: var(--qingnang-spirit); color: #fff; border: none;
  padding: 10px 24px; border-radius: 20px; cursor: pointer;
  font-size: 14px; font-weight: 500;
}
.feedback-btn:hover { background: #36A88F; }

/* 反馈弹窗 */
.feedback-modal {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.feedback-modal__content {
  background: #fff; border-radius: 12px; padding: 24px;
  width: 90%; max-width: 480px;
}
.feedback-modal h3 { margin: 0 0 10px; font-size: 18px; color: var(--ink-primary); }
.modal-note { font-size: 13px; color: var(--ink-tertiary); margin: 0 0 18px; }
.form-row { margin-bottom: 14px; }
.form-row label { display: block; font-size: 13px; color: var(--ink-secondary); margin-bottom: 6px; }
.form-row textarea {
  width: 100%; padding: 10px; border: 1px solid var(--ink-line);
  border-radius: 8px; font-size: 14px; resize: vertical; box-sizing: border-box;
}
.form-row textarea:focus { outline: none; border-color: var(--qingnang-spirit); }
.star-picker { font-size: 24px; cursor: pointer; }
.star-picker span { color: #E0E0E0; margin-right: 4px; }
.star-picker span.on { color: #FF9800; }
.forbidden-warn { background: #FFEBEE; color: #C62828; padding: 10px; border-radius: 8px; font-size: 13px; margin: 0 0 14px; }
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; }
.btn-ghost { background: none; border: 1px solid var(--ink-line); padding: 8px 18px; border-radius: 8px; cursor: pointer; font-size: 14px; }
.btn-primary { background: var(--qingnang-emerald); color: #fff; border: none; padding: 8px 18px; border-radius: 8px; cursor: pointer; font-size: 14px; }
.btn-primary:disabled { background: #BDBDBD; cursor: not-allowed; }

/* notfound */
.shop-detail__notfound { text-align: center; padding: 80px; color: var(--ink-tertiary); }
.shop-detail__notfound button { background: var(--qingnang-emerald); color: #fff; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 14px; margin-top: 14px; }
</style>
