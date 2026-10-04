<template>
  <section class="page reminders">
    <!-- 顶部：今日时空摘要 -->
    <div class="today-card">
      <div class="today-grid">
        <div class="tg-cell">
          <span class="tg-label">今日干支</span>
          <span class="tg-val">{{ today.ganzhi }}</span>
        </div>
        <div class="tg-cell">
          <span class="tg-label">当令时辰</span>
          <span class="tg-val">{{ today.dangling }} · 旺{{ today.dangling_elem }}</span>
        </div>
        <div class="tg-cell">
          <span class="tg-label">流飞星</span>
          <span class="tg-val">{{ today.feixing }}</span>
        </div>
        <div class="tg-cell">
          <span class="tg-label">你的避忌</span>
          <span class="tg-val tg-warn">冲{{ today.chong }}</span>
        </div>
      </div>
      <p class="today-note">
        📅 {{ today.date }} · 丙戌月 · 今天宜<span class="good">{{ today.yi }}</span>，
        忌<span class="bad">{{ today.ji }}</span>
      </p>
    </div>

    <!-- 分类 Tab -->
    <div class="tabs">
      <button v-for="cat in categories" :key="cat.key" class="tab-btn"
              :class="{ active: activeCat === cat.key }" @click="activeCat = cat.key">
        {{ cat.icon }} {{ cat.label }}
        <span class="tab-count">{{ cat.count }}</span>
      </button>
    </div>

    <!-- ════ 衣：穿搭建议 ════ -->
    <div v-if="activeCat === 'cloth'" class="card-grid">
      <article class="rem-card" v-for="r in clothReminders" :key="r.id">
        <div class="rem-head">
          <span class="rem-icon" :style="{ background: r.iconBg }">{{ r.icon }}</span>
          <div class="rem-level" :class="r.level">{{ r.levelLabel }}</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <div v-if="r.tags?.length" class="rem-tags">
          <span v-for="t in r.tags" :key="t" class="rem-tag">{{ t }}</span>
        </div>
        <p v-if="r.reason" class="rem-reason">📖 原理：{{ r.reason }}</p>
      </article>
    </div>

    <!-- ════ 食：饮食宜忌 ════ -->
    <div v-else-if="activeCat === 'food'" class="card-grid">
      <article class="rem-card rem-good" v-for="r in foodGood" :key="'g-' + r.id">
        <div class="rem-head">
          <span class="rem-icon" :style="{ background: '#1A4D45' }">✅</span>
          <div class="rem-level pri-ok">宜</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <p class="rem-reason">📖 {{ r.reason }}</p>
      </article>
      <article class="rem-card rem-bad" v-for="r in foodBad" :key="'b-' + r.id">
        <div class="rem-head">
          <span class="rem-icon" :style="{ background: '#D84315' }">⚠️</span>
          <div class="rem-level pri-warn">忌</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <p class="rem-reason">📖 {{ r.reason }}</p>
      </article>
    </div>

    <!-- ════ 住：住房改造 ════ -->
    <div v-else-if="activeCat === 'home'" class="card-grid">
      <article class="rem-card" v-for="r in homeReminders" :key="r.id" :class="{ 'rem-urgent': r.urgent }">
        <div class="rem-head">
          <span class="rem-icon" :style="{ background: r.iconBg }">{{ r.icon }}</span>
          <div v-if="r.urgent" class="rem-urgent-badge">⚠️ 优先</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <div v-if="r.steps?.length" class="rem-steps">
          <p v-for="(s, i) in r.steps" :key="i">{{ i + 1 }}. {{ s }}</p>
        </div>
        <p v-if="r.reason" class="rem-reason">📖 {{ r.reason }}</p>
      </article>
    </div>

    <!-- ════ 行：出行/时辰 ════ -->
    <div v-else-if="activeCat === 'travel'" class="card-grid">
      <!-- 时辰提醒 -->
      <article class="rem-card rem-timeline">
        <h3>🕐 今日时辰节律</h3>
        <div class="timeline">
          <div v-for="t in todayTimeline" :key="t.period" class="tl-item" :class="t.type">
            <span class="tl-time">{{ t.range }}</span>
            <span class="tl-elem">{{ t.elem }}</span>
            <span class="tl-desc">{{ t.desc }}</span>
          </div>
        </div>
      </article>
      <article class="rem-card" v-for="r in travelReminders" :key="r.id">
        <div class="rem-head">
          <span class="rem-icon" :style="{ background: r.iconBg }">{{ r.icon }}</span>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <p v-if="r.reason" class="rem-reason">📖 {{ r.reason }}</p>
      </article>
    </div>

    <!-- ════ 禁忌规避 ════ -->
    <div v-else-if="activeCat === 'avoid'" class="card-grid">
      <article class="rem-card rem-absolute" v-for="r in absoluteAvoid" :key="r.id">
        <div class="rem-head">
          <span class="rem-icon" style="background: #D84315">❌</span>
          <div class="rem-level pri-danger">绝对禁忌</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <p class="rem-reason">📖 {{ r.reason }}</p>
      </article>
      <article class="rem-card" v-for="r in relativeAvoid" :key="r.id">
        <div class="rem-head">
          <span class="rem-icon" style="background: #D4A017">⚠️</span>
          <div class="rem-level pri-warn">慎用</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
        <p class="rem-reason">📖 {{ r.reason }}</p>
      </article>
      <article class="rem-card rem-stones" v-for="r in stoneReminders" :key="r.id">
        <div class="rem-head">
          <span class="rem-icon" style="background: #90A4AE">💎</span>
          <div class="rem-level pri-warn">矿物避忌</div>
        </div>
        <h3>{{ r.title }}</h3>
        <p class="rem-desc">{{ r.desc }}</p>
      </article>
    </div>

    <!-- ════ 破煞方案 ════ -->
    <div v-else class="card-grid">
      <article class="rem-card rem-solution" v-for="s in solutions" :key="s.id">
        <div class="rem-head">
          <span class="rem-icon" :style="{ background: s.iconBg }">{{ s.icon }}</span>
          <div class="rem-solution-tag">破煞方案</div>
        </div>
        <h3>{{ s.title }}</h3>
        <p class="rem-desc">{{ s.desc }}</p>
        <div class="solution-body">
          <div class="sol-target">
            <span class="sol-label">针对</span>
            <span class="sol-val">{{ s.target }}</span>
          </div>
          <div class="sol-steps">
            <p v-for="(step, i) in s.steps" :key="i" class="sol-step">
              <span class="sol-step-num">{{ i + 1 }}</span>
              {{ step }}
            </p>
          </div>
        </div>
        <p class="rem-reason">📖 原理：{{ s.reason }}</p>
      </article>
    </div>

    <!-- 底部说明 -->
    <p class="footer-notice">
      * 所有建议基于你的数字模型（{{ myCoreDeviation || '五形分布' }}）推导，
      仅供生活参考，不构成医疗诊断
    </p>
  </section>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useVectorStore, toCoreDeviation } from '../stores/vector'
import { notifications } from '../api/client'

const vectorStore = useVectorStore()
const myCoreDeviation = computed(() => toCoreDeviation(vectorStore.latestVector || vectorStore.vBase))

// ═══════════════════════════════════════════════════════════
// 数据源：从后端 /notifications/today 动态拉取
// ═══════════════════════════════════════════════════════════
const today = ref({
  date: new Date().toISOString().slice(0, 10),
  ganzhi: '—', dangling: '—', dangling_elem: '—',
  feixing: '—', chong: '—', yi: '—', ji: '—',
})
const clothReminders = ref([])
const foodGood = ref([])
const foodBad = ref([])
const homeReminders = ref([])
const absoluteAvoid = ref([])
const relativeAvoid = ref([])
const stoneReminders = ref([])
const todayTimeline = ref([])
const travelReminders = ref([])
const solutions = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const r = await notifications.today()
    const d = r.data || {}
    // 顶部时空锚点
    if (d.anchor) Object.assign(today.value, d.anchor)
    if (d.cloth_good)  clothReminders.value = d.cloth_good.map((r, i) => ({ id: 'cg'+i, icon: '👕', iconBg: '#43A047', level: 'ok', levelLabel: '宜', ...r }))
    if (d.cloth_bad)   clothReminders.value.push(...d.cloth_bad.map((r, i) => ({ id: 'cb'+i, icon: '🧥', iconBg: '#1A4D45', level: 'bad', levelLabel: '忌', ...r })))
    if (d.food_good)   foodGood.value = d.food_good.map((r, i) => ({ id: 'fg'+i, ...r }))
    if (d.food_bad)    foodBad.value = d.food_bad.map((r, i) => ({ id: 'fb'+i, ...r }))
    if (d.home)        homeReminders.value = d.home.map((r, i) => ({ id: 'h'+i, icon: '🏠', iconBg: '#1A4D45', steps: [], ...r }))
    if (d.absolute_avoid)  absoluteAvoid.value = d.absolute_avoid.map((r, i) => ({ id: 'aa'+i, ...r }))
    if (d.relative_avoid)  relativeAvoid.value = d.relative_avoid.map((r, i) => ({ id: 'ra'+i, ...r }))
    if (d.stone)       stoneReminders.value = d.stone.map((r, i) => ({ id: 's'+i, ...r }))
    if (d.timeline)    todayTimeline.value = d.timeline
    if (d.travel)      travelReminders.value = d.travel.map((r, i) => ({ id: 't'+i, ...r }))
    if (d.solutions)   solutions.value = d.solutions.map((r, i) => ({ id: 'sol'+i, icon: '💡', iconBg: '#D4A017', steps: [], ...r }))
  } catch (e) {
    console.warn('[Notifications] 拉取失败，使用空态:', e.message)
  } finally {
    loading.value = false
  }
})

const activeCat = ref('cloth')

const categories = computed(() => [
  { key: 'cloth', icon: '👕', label: '穿衣配饰', count: clothReminders.value.length },
  { key: 'food', icon: '🍜', label: '饮食宜忌', count: foodGood.value.length + foodBad.value.length },
  { key: 'home', icon: '🏠', label: '住房改造', count: homeReminders.value.length },
  { key: 'travel', icon: '🕐', label: '时辰出行', count: todayTimeline.value.length + travelReminders.value.length },
  { key: 'avoid', icon: '⚠️', label: '禁忌规避', count: absoluteAvoid.value.length + relativeAvoid.value.length + stoneReminders.value.length },
  { key: 'solution', icon: '💡', label: '破煞方案', count: solutions.length }
])
</script>

<style scoped>
/* max-width 由全局 .page 统一管理（1200px） */

/* 今日时空卡片 */
.today-card {
  background: linear-gradient(135deg, rgba(26,77,69,0.06), rgba(212,160,23,0.05));
  border: 1px solid rgba(26,77,69,0.15); border-radius: var(--radius-md);
  padding: 16px 20px; margin-bottom: 18px;
}
.today-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 10px; }
.tg-cell { text-align: center; }
.tg-label { display: block; font-size: 11px; color: var(--ink-tertiary); font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 4px; }
.tg-val { font-size: 14px; font-weight: 600; color: var(--qingnang-emerald); font-family: var(--font-mono); }
.tg-warn { color: var(--wuxing-fire); }
.today-note { font-size: 12px; color: var(--ink-secondary); margin: 0; padding-top: 10px; border-top: 1px dashed rgba(26,77,69,0.15); }
.today-note .good { color: var(--wuxing-wood); font-weight: 600; }
.today-note .bad { color: var(--wuxing-fire); font-weight: 600; }

/* Tab */
.tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 16px; }
.tab-btn {
  font-size: 13px; padding: 7px 16px; border-radius: 20px;
  border: 1px solid var(--ink-line); background: #fff; color: var(--ink-secondary);
  cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 6px;
}
.tab-btn:hover { border-color: var(--qingnang-emerald); color: var(--qingnang-emerald); }
.tab-btn.active { background: var(--qingnang-emerald); border-color: var(--qingnang-emerald); color: #fff; }
.tab-count { background: var(--qingnang-paper); color: var(--ink-tertiary); padding: 0 6px; border-radius: 10px; font-size: 11px; }
.tab-btn.active .tab-count { background: rgba(255,255,255,0.2); color: #fff; }

/* 卡片网格 */
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }

.rem-card {
  background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-md);
  padding: 16px 18px; transition: all 0.15s; display: flex; flex-direction: column;
}
.rem-card:hover { box-shadow: var(--shadow-card-hover); border-color: rgba(26,77,69,0.2); }
.rem-card.rem-urgent { border-left: 3px solid var(--wuxing-fire); }
.rem-card.rem-good { border-left: 3px solid var(--wuxing-wood); }
.rem-card.rem-bad { border-left: 3px solid var(--wuxing-fire); }
.rem-card.rem-absolute { border-left: 4px solid var(--wuxing-fire); background: linear-gradient(135deg, #fff, rgba(216,67,21,0.02)); }
.rem-card.rem-stones { border-left: 3px solid var(--wuxing-metal); }

.rem-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.rem-icon {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 16px;
}
.rem-level, .rem-solution-tag, .rem-urgent-badge {
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; letter-spacing: 0.5px;
}
.rem-level.pri-ok, .rem-level.ok { background: rgba(67,160,71,0.1); color: var(--wuxing-wood); }
.rem-level.pri-warn, .rem-level.warn { background: rgba(212,160,23,0.1); color: var(--wuxing-earth); }
.rem-level.pri-danger, .rem-level.bad { background: rgba(216,67,21,0.1); color: var(--wuxing-fire); }
.rem-urgent-badge { background: var(--wuxing-fire); color: #fff; }
.rem-solution-tag { background: var(--qingnang-emerald); color: #fff; }

.rem-card h3 { font-size: 14px; font-weight: 600; color: var(--ink-primary); margin: 0 0 4px; line-height: 1.4; }
.rem-desc { font-size: 12px; color: var(--ink-secondary); margin: 0 0 8px; line-height: 1.6; }
.rem-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 6px; }
.rem-tag {
  font-size: 10px; color: var(--qingnang-emerald);
  background: rgba(26,77,69,0.06); padding: 1px 6px; border-radius: 3px; font-weight: 500;
}
.rem-reason { font-size: 11px; color: var(--ink-tertiary); margin: 8px 0 0; line-height: 1.5; font-style: italic; }
.rem-steps { margin: 6px 0; padding-left: 14px; }
.rem-steps p { font-size: 12px; color: var(--ink-secondary); margin: 2px 0; line-height: 1.5; }

/* 时辰时间线 */
.rem-timeline { grid-column: 1 / -1; }
.timeline { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }
.tl-item {
  display: flex; align-items: center; gap: 8px; padding: 10px 12px;
  border-radius: var(--radius-sm); border: 1px solid var(--ink-line);
  font-size: 12px;
}
.tl-time { font-family: var(--font-mono); font-weight: 600; color: var(--ink-primary); font-size: 11px; }
.tl-elem { font-size: 10px; color: var(--ink-tertiary); padding: 1px 6px; background: var(--qingnang-paper); border-radius: 3px; }
.tl-desc { flex: 1; margin-left: 4px; color: var(--ink-secondary); line-height: 1.4; }
.tl-item.critical { border-color: var(--wuxing-fire); background: rgba(216,67,21,0.03); }
.tl-item.good { border-color: var(--wuxing-wood); background: rgba(67,160,71,0.03); }
.tl-item.personal { border-color: var(--qingnang-emerald); background: rgba(26,77,69,0.03); }
.tl-item.warn { border-color: var(--wuxing-earth); background: rgba(212,160,23,0.04); }

/* 破煞方案 */
.rem-solution { background: linear-gradient(135deg, rgba(26,77,69,0.03), rgba(46,125,106,0.03)); border-color: rgba(26,77,69,0.2); }
.solution-body { margin: 8px 0; background: var(--qingnang-paper); border-radius: var(--radius-sm); padding: 10px 12px; }
.sol-target { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px dashed var(--ink-line); }
.sol-label { font-size: 11px; color: var(--ink-tertiary); font-weight: 600; letter-spacing: 0.5px; }
.sol-val { font-size: 12px; color: var(--qingnang-emerald); font-weight: 500; }
.sol-steps { display: flex; flex-direction: column; gap: 5px; }
.sol-step { font-size: 12px; color: var(--ink-primary); display: flex; gap: 8px; align-items: flex-start; line-height: 1.5; }
.sol-step-num {
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--qingnang-emerald); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: 700; flex-shrink: 0; margin-top: 1px;
}

.footer-notice { font-size: 11px; color: var(--ink-tertiary); margin-top: 20px; text-align: center; line-height: 1.6; padding: 0 10px; }

@media (max-width: 720px), (orientation: portrait) {
  .today-grid { grid-template-columns: repeat(2, 1fr); }
  .card-grid { grid-template-columns: 1fr; gap: 12px; }
  .today-card { padding: 12px 14px; }
  .rem-card { padding: 14px 14px; }
}
</style>
