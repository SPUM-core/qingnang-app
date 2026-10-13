<!-- ═══════════════════════════════════════════════════════════
  ModuleLab.vue — 模块调试台（DEV ONLY）
  左侧模块列表，右侧单模块渲染 + mock 数据
  → 零后端、零 store 依赖，独立验证每个模块
══════════════════════════════════════════════════════════════ -->
<template>
  <div class="lab" data-page-id="DEV01">
    <header class="lab-head">
      <h1>🧪 Module Lab · 青囊生活管家</h1>
      <span class="lab-badge">DEV ONLY</span>
      <span class="lab-info">{{ modules.length }} 个模块 · 零后端依赖</span>
    </header>

    <main class="lab-body">
      <!-- 左侧：模块列表 -->
      <aside class="lab-nav">
        <div
          v-for="m in modules"
          :key="m.name"
          :class="['lab-nav-item', { active: selected === m.name, done: m.done, pending: !m.done }]"
          @click="selected = m.name"
        >
          <span class="lab-dot" :class="m.done ? 'ok' : 'pending'"></span>
          <div class="lab-nav-main">
            <div class="lab-nav-title">{{ m.title }}</div>
            <div class="lab-nav-sub">
              <span class="lab-tag">{{ m.name }}</span>
              <span :class="['lab-risk', `risk-${m.risk}`]">{{ riskLabel(m.risk) }}</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右侧：模块渲染区 -->
      <section class="lab-stage">
        <div v-if="current" class="lab-stage-inner">
          <!-- mock 数据面板 -->
          <details class="mock-panel" open>
            <summary>📦 Mock 数据（点击折叠/展开）</summary>
            <pre class="mock-json">{{ JSON.stringify(current.mock, null, 2) }}</pre>
          </details>

          <!-- 模块渲染 -->
          <div class="lab-render">
            <component :is="current.component" v-bind="current.mock" @goCase="onGoCase" @click="log('click')" />
          </div>

          <!-- 事件日志 -->
          <div v-if="events.length" class="event-log">
            <div class="event-log-head">📡 Emits 日志（最近 5 条）</div>
            <div v-for="(e, i) in events.slice(-5).reverse()" :key="i" class="event-line">
              <span class="event-ts">{{ e.ts }}</span>
              <span class="event-name">{{ e.name }}</span>
              <span v-if="e.payload" class="event-payload">{{ JSON.stringify(e.payload).slice(0, 80) }}</span>
            </div>
          </div>
        </div>
        <div v-else class="lab-empty">请从左侧选择一个模块</div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, shallowRef } from 'vue'

// ══ 注册所有模块 ══
import GreetingHeader from '../modules/GreetingHeader.vue'
import TrendRadarCard from '../modules/TrendRadarCard.vue'
import DriftVectorCard from '../modules/DriftVectorCard.vue'
import HeroTodoCard from '../modules/HeroTodoCard.vue'
import HeroDailyTipsCard from '../modules/HeroDailyTipsCard.vue'
import LifestyleReminderCard from '../modules/LifestyleReminderCard.vue'
import LifeAdviceCard from '../modules/LifeAdviceCard.vue'

const selected = ref('LifeAdviceCard')
const events = ref([])

const modules = [
  { name: 'GreetingHeader',   title: 'M2 问候头部',     component: GreetingHeader,   done: true,  risk: 'low',  mock: { greeting: '晚上好', displayName: '运涛', today: '2026.10.10', weekday: '周五', caseStatusLabel: '调理中 · 稳定观察', observationCount: 15, archivedDays: 3 } },
  { name: 'TrendRadarCard',   title: 'M10 体质趋势',   component: TrendRadarCard,   done: true,  risk: 'low',  mock: { vBase: { wood:60, fire:45, earth:35, metal:58, water:47 }, vObs: { wood:61, fire:43, earth:37, metal:56, water:49 }, trendStateLabel: '稳定观察中', deltaSummary: '木 ▲ 1 · 火 ▼ 2 · 余稳定' } },
  { name: 'DriftVectorCard',  title: 'M11 漂移矢量',   component: DriftVectorCard,  done: true,  risk: 'low',  mock: { rows: [{ k:'wood', label:'木', base:60, obs:61, delta:1.2 }, { k:'fire', label:'火', base:45, obs:43, delta:-2.1 }, { k:'earth', label:'土', base:35, obs:37, delta:2.3 }, { k:'metal', label:'金', base:58, obs:56, delta:-2.0 }, { k:'water', label:'水', base:47, obs:49, delta:2.5 }] } },
  { name: 'HeroTodoCard',     title: 'M4a 英雄卡1',    component: HeroTodoCard,     done: true,  risk: 'mid',  mock: { heroTodo: { id:'t1', title:'喝一碗山药薏米粥养土', priority:'p0', done:false }, anchorSafe: { yi:'今日火日·宜黄褐系·养土形', ji:'忌辛辣助木', state:'rule-based', ganzhi:'丁卯', dangling:'木', dangling_elem:'wood', feixing:'太阳', chong:'鸡' } } },
  { name: 'HeroDailyTipsCard',title: 'M4b 英雄卡2',   component: HeroDailyTipsCard,done: true,  risk: 'mid',  mock: { anchorSafe: { yi:'今日火日·宜黄褐系·养土形', ji:'忌辛辣助木', weather: { icon:'cloud', temp_high:22, temp_low:14, desc:'多云', qihou:'燥' } }, avoidanceNotes: [{ title:'今日冲鸡，属鸡者忌远行' }, { title:'五形差>25，慎用过木类事物' }] } },
  { name: 'LifestyleReminderCard', title: 'M6 生活提醒', component: LifestyleReminderCard, done: true, risk: 'high', mock: {
    maturityStage: 3, expanded: true, activeTab: 'good',
    remTotal: 14, remTabs: [{key:'good',label:'宜·忌'},{key:'home',label:'住房'},{key:'avoid',label:'注意事项'}],
    lifestyleLoading: false, lifestylePreview: '',
    clothGoodSelect: [{ id:'c1', title:'多穿黄褐系', desc:'补土形，抑制木形过旺' }],
    clothBadSelect: [{ id:'c3', title:'忌青绿系', desc:'助木形过旺，土形更弱' }],
    foodGoodSelect: [{ id:'f1', title:'宜吃山药等补土食物', desc:'山药、薏米、南瓜、红薯' }],
    foodBadSelect: [{ id:'f2', title:'忌辛辣', desc:'辛辣、茴香、花椒' }],
    homeSelect: [{ id:'h1', title:'辰时养胃', desc:'7:00-9:00 辰时脾经旺', urgent: true }],
    relativeSelect: [{ id:'r1', title:'慎用过木类事物', reason:'五形差 > 25 触发警示' }],
    absoluteSelect: [{ id:'a1', title:'今日冲鸡', desc:'属鸡者忌远行' }],
    stoneSelect: [{ id:'s1', title:'忌戴木质饰品', desc:'助木克土' }]
  } },
  { name: 'LifeAdviceCard',   title: 'M7 今日建议',    component: LifeAdviceCard,   done: true,  risk: 'high', mock: {
    maturityStage: 3, activeFilter: 'pending',
    segTabs: [{key:'pending',label:'待处理 2'},{key:'all',label:'全部 3'},{key:'archived',label:'归档 1 天'}],
    filteredTodos: [
      { id:'t1', title:'喝一碗山药薏米粥养土', priority:'p0', done:false, priority_label:'必做' },
      { id:'t2', title:'辰时温热早餐', priority:'p1', done:false, priority_label:'建议' },
    ],
    feedbacksMap: { t1: [], t2: [] },
    archives: [{ date:'2026-10-09', todos:[{ title:'早睡', exec_status:'done', feedbacks:[] }], totalFeedbacks: 1 }],
    archivedDays: 1, totalFeedbacks: 1,
  } },
  { name: 'PullRefreshBar',   title: 'M1 下拉刷新',    component: null, done: false, risk: 'low',  mock: {} },
  { name: 'ConstitutionCurveCard', title: 'M5 调理曲线', component: null, done: false, risk: 'mid', mock: {} },
  { name: 'AnchorTimelineCard',    title: 'M5b 时空锚点', component: null, done: false, risk: 'mid', mock: {} },
]

const current = shallowRef(modules.find(m => m.name === selected.value))

// 监听切换
import { watch } from 'vue'
watch(selected, (n) => {
  current.value = modules.find(m => m.name === n)
  events.value = []
})

function riskLabel(r) { return { low: '低风险', mid: '中风险', high: '高风险' }[r] || r }
function log(name, payload) {
  events.value.push({ ts: new Date().toLocaleTimeString(), name, payload })
}
function onGoCase() { log('goCase') }
</script>

<style scoped>
.lab { min-height: 100vh; background: #F2EFE7; font-family: 'Noto Sans SC', sans-serif; color: #33403B; }
.lab-head {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 24px; background: #17534C; color: #fff;
}
.lab-head h1 { margin: 0; font-size: 18px; font-weight: 600; }
.lab-badge {
  padding: 2px 10px; background: #C0392B; border-radius: 12px;
  font-size: 11px; font-weight: 600; letter-spacing: 1px;
}
.lab-info { margin-left: auto; font-size: 12px; opacity: 0.7; }
.lab-body { display: grid; grid-template-columns: 280px 1fr; min-height: calc(100vh - 56px); }

/* 左侧导航 */
.lab-nav { background: #fff; border-right: 1px solid #E5E1D6; padding: 12px 0; overflow-y: auto; }
.lab-nav-item {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 10px 16px; cursor: pointer; border-left: 3px solid transparent;
  transition: background 0.15s;
}
.lab-nav-item:hover { background: #F1F5F2; }
.lab-nav-item.active { background: #E8F1EE; border-left-color: #17534C; }
.lab-nav-item.pending { opacity: 0.55; cursor: not-allowed; }
.lab-dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 6px; flex-shrink: 0; }
.lab-dot.ok { background: #2E6B60; }
.lab-dot.pending { background: #ccc; }
.lab-nav-title { font-size: 14px; font-weight: 500; }
.lab-nav-sub { display: flex; gap: 6px; margin-top: 4px; font-size: 11px; color: #5F6E68; }
.lab-tag { background: #F1F5F2; padding: 1px 6px; border-radius: 3px; font-family: monospace; }
.lab-risk { padding: 1px 6px; border-radius: 3px; }
.risk-low { background: #E8F1EE; color: #2E6B60; }
.risk-mid { background: #F7F0E4; color: #A8681C; }
.risk-high { background: #FCEDEA; color: #C0392B; }

/* 右侧渲染区 */
.lab-stage { padding: 20px; overflow-y: auto; }
.lab-stage-inner { max-width: 640px; margin: 0 auto; }
.lab-empty { text-align: center; padding: 80px 20px; color: #8A9A94; }

/* mock 数据面板 */
.mock-panel {
  margin-bottom: 16px; border: 1px solid #D8E2DE; border-radius: 8px;
  background: #fff; overflow: hidden;
}
.mock-panel summary {
  padding: 10px 14px; cursor: pointer; font-size: 13px;
  background: #F1F5F2; border-bottom: 1px solid #D8E2DE;
}
.mock-panel summary:hover { background: #DFE8E4; }
.mock-json {
  margin: 0; padding: 12px 14px; font-family: 'JetBrains Mono', monospace;
  font-size: 12px; max-height: 240px; overflow: auto; color: #5F6E68;
}

/* 模块渲染区 */
.lab-render {
  padding: 24px; background: #fff; border-radius: 10px;
  box-shadow: 0 1px 2px rgba(14,58,52,0.04);
  border: 1px solid #E5E1D6;
}

/* 事件日志 */
.event-log { margin-top: 16px; border-radius: 8px; background: #fff; border: 1px solid #E5E1D6; }
.event-log-head { padding: 8px 14px; font-size: 12px; color: #5F6E68; border-bottom: 1px solid #E5E1D6; background: #F9F9F5; }
.event-line { padding: 6px 14px; font-size: 12px; border-bottom: 1px solid #F2EFE7; font-family: 'JetBrains Mono', monospace; }
.event-line:last-child { border-bottom: none; }
.event-ts { color: #8A9A94; margin-right: 8px; }
.event-name { color: #17534C; font-weight: 600; }
.event-payload { color: #A8681C; margin-left: 8px; }
</style>
