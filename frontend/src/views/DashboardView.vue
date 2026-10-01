<template>
  <section class="page home">
    <!-- 问候头部 -->
    <div class="home-header">
      <div>
        <h1 class="home-greeting">{{ greeting }}，{{ userStore.displayName }}</h1>
        <p class="home-date">{{ today }} · {{ weekday }} · 调理进行中</p>
      </div>
      <div class="home-quick">
        <div class="quick-stat">
          <span class="qs-val">{{ vectorStore.driftSeries?.length || 0 }}</span>
          <span class="qs-label">次观测</span>
        </div>
        <div class="quick-stat">
          <span class="qs-val">{{ archivedDays }}</span>
          <span class="qs-label">天归档</span>
        </div>
      </div>
    </div>

    <!-- ════ 英雄卡组：今日最重要的事 + 今日宜忌（独立两卡） ════ -->
    <div class="hero-row">
      <!-- 英雄卡 1：今日最重要的事 -->
      <div class="hero-card">
        <div class="hero-main">
          <p class="hero-tag">今日 · 时空锚点</p>
          <h2 class="hero-title">今日最重要的事</h2>
          <p class="hero-item"><span class="hero-dot"></span>{{ heroTodo?.title || '暂无待办 · 好好休息' }}</p>
          <p class="hero-sub">{{ anchor.yi }} · 当前状态 {{ anchor.state }}</p>
          <p class="hero-sub">忌 {{ anchor.ji }} · 顺当日节律</p>
          <button class="hero-btn" @click="goPending">开始调理</button>
        </div>
      </div>

      <!-- 英雄卡 2：今日宜忌（独立卡） -->
      <div class="hero-yi-card">
        <p class="hero-tag">今日 · 宜忌速览</p>
        <h2 class="hero-title">今日宜忌</h2>
        <div class="yj-pair">
          <div class="yj-block yi">
            <span class="yj-ico good"><QIcon name="check" :size="13" /></span>
            <div class="yj-text">
              <span class="yj-k">宜</span>
              <span class="yj-v">{{ anchor.yi }}</span>
            </div>
          </div>
          <div class="yj-block ji">
            <span class="yj-ico bad"><QIcon name="forbid" :size="13" /></span>
            <div class="yj-text">
              <span class="yj-k">忌</span>
              <span class="yj-v">{{ anchor.ji }}</span>
            </div>
          </div>
        </div>
        <p class="hero-yi-more" @click="openReminders">展开全部宜忌 →</p>
      </div>
    </div>

    <!-- ════ 第二行：体质调理曲线 + 今日时空锚点（横屏并列） ════ -->
    <div class="top-row">
      <!-- 左：体质调理曲线（v0.2 三曲线架构） -->
      <div class="card chart-card">
        <div class="card-head">
          <h2>体质曲线</h2>
          <div style="display:flex;gap:6px;align-items:center;">
            <button
              @click="demoCase = 'hu'"
              :style="{
                padding: '3px 10px',
                fontSize: 11,
                border: `1px solid ${demoCase==='hu' ? '#1A4D45' : '#d0d0cb'}`,
                background: demoCase==='hu' ? '#1A4D45' : 'transparent',
                color: demoCase==='hu' ? '#fff' : '#6B7277',
                borderRadius: 4,
                cursor: 'pointer'
              }">临床视图</button>
            <button
              @click="demoCase = 'zy'"
              :style="{
                padding: '3px 10px',
                fontSize: 11,
                border: `1px solid ${demoCase==='zy' ? '#1A4D45' : '#d0d0cb'}`,
                background: demoCase==='zy' ? '#1A4D45' : 'transparent',
                color: demoCase==='zy' ? '#fff' : '#6B7277',
                borderRadius: 4,
                cursor: 'pointer'
              }">终身视图 · 曾银鸾</button>
            <span class="chip-dv" style="margin-left:4px;">
              {{ driftTrajectory ? '综合健康得分' : ('ΔV ' + vectorStore.trendStateLabel) }}
            </span>
          </div>
        </div>
        <DriftChart
          v-if="driftTrajectory || driftSeries.length"
          :trajectory="driftTrajectory"
          :series="driftSeries"
          height="260px"
          class="curve-chart"
        />
        <p v-else class="placeholder curve-empty">暂无观测数据 · 完成一次数据采集后生成调理曲线</p>
      </div>

      <!-- 右：时空锚点 -->
      <div class="card chart-card anchor-card">
        <div class="card-head">
          <h2><QIcon name="anchor" :size="15" /> 今日时空锚点</h2>
          <span class="anchor-sub">{{ anchor.ganzhi }}</span>
        </div>
        <div class="anchor-grid">
          <div class="ag-cell">
            <span class="ag-label">当令时辰</span>
            <span class="ag-val">{{ anchor.dangling }}</span>
          </div>
          <div class="ag-cell">
            <span class="ag-label">流飞星</span>
            <span class="ag-val">{{ anchor.feixing }}</span>
          </div>
          <div class="ag-cell">
            <span class="ag-label">今日避忌</span>
            <span class="ag-val warn">{{ avoidText }}</span>
          </div>
        </div>

        <!-- 时辰节律线：三段式 -->
        <div class="anchor-timeline">
          <div class="tl-seg" v-for="s in rhythmSegments" :key="s.range" :class="s.color">
            <span class="tl-bar"></span>
            <span class="tl-text">{{ s.range }} {{ s.label }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ════ 生活提醒：默认折叠，点开展开全部 ════ -->
    <div class="card reminders-mini">
      <button class="rem-collapse" @click="remExpanded = !remExpanded">
        <span class="rem-collapse-text">展开全部提醒与禁忌（{{ remTotal }} 条 · 含绝对禁忌与矿物避忌）</span>
        <span class="rem-chevron" :class="{ open: remExpanded }">›</span>
      </button>

      <div v-if="remExpanded" class="rem-body">
        <!-- 分段器 -->
        <div class="rem-head">
          <div class="rem-tabs">
            <button v-for="t in remTabs" :key="t.key" class="rem-tab"
                    :class="{ active: activeRem === t.key }" @click="activeRem = t.key">
              {{ t.label }}
            </button>
          </div>
        </div>

        <!-- 流式生成中：骨架屏 + 渐进 token 预览 -->
        <div v-if="lifestyleLoading" class="lifestyle-loading">
          <div class="lifestyle-loading-header">
            <span class="spinner"><QIcon name="spark" :size="16" /></span>
            <span>青檬引擎正在生成今日提醒…（约 15-20s）</span>
          </div>
          <pre v-if="lifestylePreview" class="lifestyle-preview">{{ lifestylePreview.slice(-500) }}</pre>
          <div v-else class="lifestyle-preview-placeholder">正在连接青檬引擎…</div>
        </div>

        <!-- 宜 -->
        <div v-if="!lifestyleLoading && activeRem === 'good'" class="rem-lists">
          <div class="rem-col">
            <h4 class="rem-col-title good"><QIcon name="check" :size="13" /> 今日宜（{{ clothGoodSelect.length + foodGoodSelect.length }}）</h4>
            <div v-for="r in [...clothGoodSelect, ...foodGoodSelect]" :key="r.id" class="rem-item rem-good">
              <span class="rem-item-title">{{ r.title }}</span>
              <span class="rem-item-desc">{{ r.desc }}</span>
            </div>
          </div>
          <div class="rem-col">
            <h4 class="rem-col-title bad"><QIcon name="warn" :size="13" /> 今日忌（{{ clothBadSelect.length + foodBadSelect.length }}）</h4>
            <div v-for="r in [...clothBadSelect, ...foodBadSelect]" :key="r.id" class="rem-item rem-bad">
              <span class="rem-item-title">{{ r.title }}</span>
              <span class="rem-item-desc">{{ r.desc }}</span>
            </div>
          </div>
        </div>
        <!-- 住 -->
        <div v-else-if="!lifestyleLoading && activeRem === 'home'" class="rem-lists">
          <div v-for="r in homeSelect" :key="r.id" class="rem-item" :class="{ 'rem-urgent': r.urgent }">
            <span class="rem-item-title">{{ r.title }}</span>
            <span class="rem-item-desc">{{ r.desc }}</span>
          </div>
        </div>
        <!-- 禁忌：绝对禁忌 / 矿物避忌默认收起 -->
        <div v-else-if="!lifestyleLoading" class="rem-fold-zone">
          <h4 class="rem-col-title warn"><QIcon name="warn" :size="13" /> 慎用（{{ relativeSelect.length }}）</h4>
          <div v-for="r in relativeSelect" :key="r.id" class="rem-item">
            <span class="rem-item-title">{{ r.title }}</span>
            <span class="rem-item-desc">{{ r.desc }} · {{ r.reason }}</span>
          </div>

          <details class="rem-fold">
            <summary class="rem-fold-summary danger"><QIcon name="forbid" :size="13" /> 绝对禁忌（{{ absoluteSelect.length }}）</summary>
            <div v-for="r in absoluteSelect" :key="r.id" class="rem-item rem-danger">
              <span class="rem-item-title">{{ r.title }}</span>
              <span class="rem-item-desc">{{ r.desc }} · {{ r.reason }}</span>
            </div>
          </details>

          <details class="rem-fold">
            <summary class="rem-fold-summary"><QIcon name="gem" :size="13" /> 矿物避忌（{{ stoneSelect.length }}）</summary>
            <div v-for="r in stoneSelect" :key="r.id" class="rem-item rem-stone">
              <span class="rem-item-title">{{ r.title }}</span>
              <span class="rem-item-desc">{{ r.desc }}</span>
            </div>
          </details>
        </div>
      </div>
    </div>

    <!-- ════ 第二行：待办卡片网格 ════ -->
    <div class="section-head">
      <h2 class="section-title"><QIcon name="doc" :size="15" /> 今日生活建议</h2>
      <div class="seg-control">
        <button v-for="t in segTabs" :key="t.key" class="seg-btn"
                :class="{ active: activeFilter === t.key }" @click="activeFilter = t.key">
          {{ t.label }}
        </button>
      </div>
    </div>

    <!-- 待办卡片网格 -->
    <div v-if="activeFilter !== 'archived'" class="todo-grid">
      <TodoCard
        v-for="todo in filteredTodos"
        :key="todo.id"
        :todo="todo"
        :feedbacks="getFeedbacks(todo.id)"
        @open-punch="openPunchModal"
      />
      <div v-if="!filteredTodos.length" class="todo-empty">
        没有匹配的待办
      </div>
    </div>

    <!-- 归档视图 -->
    <div v-else class="archive-view">
      <div class="archive-summary" v-if="archivedDays > 0">
        <p>共 <strong>{{ archivedDays }}</strong> 天归档 · <strong>{{ totalFeedbacks }}</strong> 条反馈 · 用作复诊诊断数据</p>
      </div>
      <div v-if="archives.length" class="archive-list">
        <details v-for="arc in archives" :key="arc.date" class="archive-day">
          <summary class="archive-day-head">
            <span class="archive-date">{{ arc.date }}</span>
            <span class="archive-todo-count">{{ arc.todos.length }} 项</span>
            <span class="archive-fb-count"><QIcon name="chat" :size="11" /> {{ arc.totalFeedbacks }} 条反馈</span>
          </summary>
          <div class="archive-day-body">
            <div v-for="t in arc.todos" :key="t.id" class="archive-todo">
              <span class="archive-todo-title">{{ t.title }}</span>
              <span class="archive-exec" :class="'exec-' + t.exec_status">{{ execLabel(t.exec_status) }}</span>
              <span v-if="t.feedbacks?.length" class="archive-fb">{{ t.feedbacks.length }}条反馈</span>
            </div>
          </div>
        </details>
      </div>
      <p v-else class="placeholder">暂无归档 · 完成今日待办后，每日自动归档</p>
    </div>

    <!-- ════ 打卡弹窗（v-if/v-else 链之外，独立渲染） ════ -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="punchModal.todo" class="punch-modal-backdrop" @click.self="closePunchModal">
          <div class="punch-modal">
            <div class="pm-head">
              <div class="pm-title-wrap">
                <span class="pm-tag">{{ punchModal.isEdit ? '修改执行反馈' : '今日打卡' }}</span>
                <h3 class="pm-title">{{ punchModal.todo.title }}</h3>
                <p v-if="punchModal.todo.due" class="pm-due">🕐 {{ punchModal.todo.due }}</p>
              </div>
              <button class="pm-close" @click="closePunchModal" aria-label="关闭">✕</button>
            </div>

            <div class="pm-section">
              <label class="pm-label">执行状态</label>
              <div class="pm-exec-btns">
                <button class="pm-exec" :class="{ active: punchModal.execStatus === 'done' }"
                        @click="punchModal.execStatus = 'done'">已完成</button>
                <button class="pm-exec" :class="{ active: punchModal.execStatus === 'partial' }"
                        @click="punchModal.execStatus = 'partial'">部分执行</button>
                <button class="pm-exec" :class="{ active: punchModal.execStatus === 'skipped' }"
                        @click="punchModal.execStatus = 'skipped'">跳过</button>
                <button class="pm-exec" :class="{ active: punchModal.execStatus === 'failed' }"
                        @click="punchModal.execStatus = 'failed'">未执行</button>
              </div>
            </div>

            <div v-if="punchModal.feedbacks?.length" class="pm-section">
              <label class="pm-label">历史反馈（{{ punchModal.feedbacks.length }}）</label>
              <div v-for="(fb, i) in punchModal.feedbacks" :key="i" class="pm-fb-item">
                <span class="pm-fb-date">{{ fb.date }}</span>
                <span class="pm-fb-status" :class="'pm-fb-' + fb.status">{{ execLabel(fb.status) }}</span>
                <span v-if="fb.note" class="pm-fb-note">{{ fb.note }}</span>
              </div>
            </div>

            <div class="pm-section">
              <label class="pm-label">反馈（可选）</label>
              <textarea v-model="punchModal.note" placeholder="执行细节、感受或遇到的问题…" rows="3"></textarea>
            </div>

            <div class="pm-foot">
              <button class="pm-cancel" @click="closePunchModal">取消</button>
              <button class="pm-submit" @click="submitPunch" :disabled="punchModal.submitting">
                <span v-if="punchModal.submitting">提交中…</span>
                <span v-else>提交</span>
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- ════ 第三行：体质趋势（雷达图，恢复） ════ -->
    <div class="card chart-card trend-card">
      <div class="card-head">
        <h2>体质趋势</h2>
        <span class="chip-dv">ΔV {{ vectorStore.trendStateLabel }}</span>
      </div>
      <div class="trend-body">
        <RadarChart v-if="vBase || latestObs" :v-base="vBase" :v-obs="latestObs" hide-legend height="220px" class="trend-radar" />
        <p v-else class="placeholder trend-radar">暂无数据</p>
        <div class="trend-side">
          <div class="legend-row"><span class="lg-swatch base"></span>先天基底</div>
          <div class="legend-row"><span class="lg-swatch obs"></span>当前观测</div>
          <p class="trend-delta">{{ deltaSummary }}</p>
          <button class="btn-ghost-sm" @click="goCase">查看档案</button>
        </div>
      </div>
    </div>

    <!-- ════ 第四行：漂移矢量一览 ════ -->
    <div class="card table-card">
      <h2>漂移矢量一览</h2>
      <table class="table">
        <thead><tr><th>维度</th><th>先天基底</th><th>最新观测</th><th>ΔV</th></tr></thead>
        <tbody>
          <tr v-for="row in deltaTable" :key="row.k">
            <td>{{ row.label }}</td>
            <td>{{ fmt(row.base) }}</td>
            <td>{{ fmt(row.obs) }}</td>
            <td :class="{ delta: true, up: row.delta > 0, down: row.delta < 0 }">{{ fmt(row.delta) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch, reactive, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useVectorStore } from '../stores/vector'
import { useUserStore } from '../stores/user'
import { healthCheck, assistant as assistantApi, notifications as notifApi, lifestyleStream } from '../api/client'
import RadarChart from '../components/charts/RadarChart.vue'
import DriftChart from '../components/charts/DriftChart.vue'
import TodoCard from '../components/TodoCard.vue'
import QIcon from '../components/ui/QIcon.vue'
import { MOCK_TRAJECTORY, ZY_LIFETIME_TRAJECTORY, ZY_SPUM_FULL_82, isMockMode } from '../constants/mock'

const router = useRouter()

// ═══════════════════════════════════════════════════════════
// 生活提醒数据源（默认值 + 后端动态覆盖）
// ═══════════════════════════════════════════════════════════
const anchor = reactive({
  ganzhi: '丙午年 丁酉月 癸酉日', dangling: '酉时', dangling_elem: '金',
  feixing: '4绿入中', chong: '兔（卯）',
  yi: '养生·调理·静养', ji: '大动·辛辣·冷饮',
  state: '湿遏·气结74%·土枯'
})
const todayTimeline = ref([
  { period: 'zishi', range: '子时', elem: '水', desc: '必睡', type: 'critical' },
  { period: 'choushi', range: '丑时', elem: '土', desc: '熟睡中', type: 'good' },
  { period: 'yinshi', range: '寅时', elem: '木', desc: '搓腰·深呼吸', type: 'personal' },
  { period: 'maoshi', range: '卯时', elem: '木', desc: '温淡盐水', type: 'good' },
  { period: 'chenshi', range: '辰时', elem: '土', desc: '小米粥', type: 'good' },
  { period: 'wushi', range: '午时', elem: '火', desc: '闭目20分', type: 'good' },
  { period: 'weishi', range: '未时', elem: '土', desc: '八段锦', type: 'personal' },
  { period: 'youshi', range: '酉时', elem: '金', desc: '减工作', type: 'warn' },
  { period: 'xushi', range: '戌时', elem: '土', desc: '泡脚15min', type: 'good' },
  { period: 'haishi', range: '亥时', elem: '水', desc: '放下手机', type: 'good' }
])
const clothReminders = ref([
  { id: 'c1', title: '今日宜穿：绿色/青色', desc: '木形补肝 · 疏解气结', level: 'ok' },
  { id: 'c2', title: '避免：冷色调·深蓝/暗灰', desc: '加剧水形沉潜·加重湿遏', level: 'bad' },
  { id: 'c3', title: '推荐配饰：红玛瑙/蜜蜡', desc: '替代岫玉翡翠（寒）', level: 'ok' },
  { id: 'c4', title: '贴身衣物：避免靛蓝', desc: '靛蓝性寒·加重木形悖论', level: 'warn' }
])
const foodGood = ref([
  { id: 'fg1', title: '小米粥（早餐）', desc: '入脾经·温养土形' },
  { id: 'fg2', title: '鲫鱼汤（午餐）', desc: '利水而不寒·补土不助湿' },
  { id: 'fg3', title: '温淡盐水（晨起）', desc: '唤醒载流体循环' },
  { id: 'fg4', title: '蒸蛋·红枣莲子芡实', desc: '温润补中' }
])
const foodBad = ref([
  { id: 'fb1', title: '冷饮/生冷', desc: '载流体急剧降温' },
  { id: 'fb2', title: '浓茶/咖啡', desc: '提神耗阴·相火更妄' },
  { id: 'fb3', title: '晚餐后进食', desc: '子时自然降温窗口被破' },
  { id: 'fb4', title: '辛辣·生姜过量', desc: '短期S_火↑但耗S_水' }
])
const homeReminders = ref([
  { id: 'h1', title: '床头移离窗户 2 米+', desc: '酉时金旺克木·调整到东墙', urgent: true },
  { id: 'h2', title: '客厅 3-8 盆阔叶绿植', desc: '空间补木·助气结疏解', urgent: false },
  { id: 'h3', title: '卧室暖黄 2700K 灯光', desc: '助相火归位·入眠快', urgent: false },
  { id: 'h4', title: '书房加湿器', desc: '滋水护印·脑力空间降温', urgent: false },
  { id: 'h5', title: '炉灶与冰箱对角', desc: '避免水火对冲煞', urgent: false }
])
const absoluteAvoid = ref([
  { id: 'aa1', title: '苦寒直折（黄连/黄芩/大黄）', desc: '直接伤S_土形', reason: '与湿遏治疗路径完全冲突' },
  { id: 'aa2', title: '安眠药（强制关闭木环）', desc: '绝对禁止', reason: '与温和重建路径冲突' },
  { id: 'aa3', title: '岫玉/翡翠/黑曜石', desc: '寒色矿物·直接抑制火形', reason: '已活体验证有效' }
])
const relativeAvoid = ref([
  { id: 'ra1', title: '大热大补（鹿茸/附子/肉桂）', desc: '慎用', reason: '午子冲生火助火' },
  { id: 'ra2', title: '咖啡/浓茶', desc: '慎用', reason: '提神耗阴→虚火更旺' },
  { id: 'ra3', title: '辛辣过量', desc: '慎用', reason: '短期S_火↑但耗S_水' }
])
const stoneReminders = ref([
  { id: 's1', title: '岫玉/翡翠（寒）', desc: '直接抑制基线火形' },
  { id: 's2', title: '白水晶/黑曜石（寒）', desc: '同属寒性' },
  { id: 's3', title: '推荐：蜜蜡/红玛瑙（温）', desc: '温润而不燥' }
])

// ── Lifestyle 流式状态 ──
const lifestyleLoading = ref(false)
const lifestylePreview = ref('')   // 渐进 token 预览文本

// Tab 选择（生活提醒 mini）
const activeRem = ref('good')
const remExpanded = ref(false)   // 折叠行：默认收起
const remTabs = [
  { key: 'good', label: '宜·忌' },
  { key: 'home', label: '住房' },
  { key: 'avoid', label: '禁忌' }
]
const remTotal = computed(() =>
  clothReminders.value.length + foodGood.value.length + foodBad.value.length +
  homeReminders.value.length + absoluteAvoid.value.length +
  relativeAvoid.value.length + stoneReminders.value.length
)

// ── 英雄卡：今日最重要的事（第一件未完成的 P0，否则第一条待办）──
const heroTodo = computed(() => {
  const p0 = todos.value.find(t => t.priority === 'p0' && !t.done)
  return p0 || todos.value.find(t => !t.done) || todos.value[0] || null
})
function goPending() {
  activeFilter.value = 'pending'
  document.querySelector('.section-head')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
function goCase() {
  router.push({ name: 'case' })
}
function openReminders() {
  remExpanded.value = true
  nextTick(() => document.querySelector('.reminders-mini')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

// 精选筛选（压缩版：分类选 2 条 + 全部宜 3 条）
const clothGoodSelect = computed(() => clothReminders.value.filter(r => r.level === 'ok').slice(0, 2))
const clothBadSelect = computed(() => clothReminders.value.filter(r => r.level === 'bad').slice(0, 2))
const foodGoodSelect = computed(() => foodGood.value.slice(0, 2))
const foodBadSelect = computed(() => foodBad.value.slice(0, 2))
const homeSelect = computed(() => homeReminders.value)
const absoluteSelect = computed(() => absoluteAvoid.value)
const relativeSelect = computed(() => relativeAvoid.value)
const stoneSelect = computed(() => stoneReminders.value)

const vectorStore = useVectorStore()
const userStore = useUserStore()
const health = ref({ ok: false })

// v0.2 三曲线 trajectory：真实数据优先 → mock fallback → 旧模式降级
const demoCase = ref('hu')   // 'hu' = 胡运涛临床视图, 'zy' = 曾银鸾终身视图
const driftTrajectory = computed(() => {
  // 终身视图（演示用 — SPUM 三曲线新算法）
  if (demoCase.value === 'zy') return ZY_SPUM_FULL_82
  // 1. 真实数据优先（vectorStore.fetchTrajectory 拉后端 /cases/trajectories）
  if (vectorStore.trajectory?.actual?.length > 0) return vectorStore.trajectory
  // 2. 后端不可用时（health check 没过）→ mock
  if (isMockMode(health.value)) return MOCK_TRAJECTORY
  // 3. 后端可用但暂无观测 → null（降级到旧 ΔV 漂移线模式）
  return null
})

const vBase = computed(() => vectorStore.vBase)
const latestObs = computed(() => vectorStore.latestObs)
const driftSeries = computed(() => vectorStore.driftSeries)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  if (h < 22) return '晚上好'
  return '夜深了'
})
const today = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')}`
})
const weekday = computed(() => ['周日','周一','周二','周三','周四','周五','周六'][new Date().getDay()])

const deltaTable = computed(() => {
  const labels = { wood: '木', fire: '火', earth: '土', metal: '金', water: '水' }
  const delta = vectorStore.deltaV || {}
  return ['wood','fire','earth','metal','water'].map(k => ({
    k, label: labels[k],
    base: vBase.value?.[k],
    obs: latestObs.value?.values?.[k],
    delta: delta[k]
  }))
})
const fmt = (v) => v == null ? '—' : Number(v).toFixed(1)

// ═══════════════════════════════════════════════════════════
// 待办系统：种子数据 + 每日更新 + 归档
// ═══════════════════════════════════════════════════════════
const TODAY_KEY = 'qingnang_today'
const ARCHIVE_KEY = 'qingnang_archive'

const activeFilter = ref('pending')  // 默认落在「待处理」，对齐设计稿

function buildTodayTodos() {
  // 从胡运涛案例构建每日种子
  return [
    { id: 't1', title: 'PPG 复查验证 · v7.0 基线调平效果', remind: '苓桂术甘汤 5 天后复查脉搏特征', tag: '数据采集·关键节点', tagClass: 'tag-accent', priority: 'p0', due: '2026-09-20' },
    { id: 't2', title: '今日草本组合：苓桂术甘汤 + 白芍 + 砂仁', remind: '湿遏状态 · 6 味药', tag: 'v7.0', tagClass: 'tag-treatment', priority: 'p0' },
    { id: 't3', title: '22:30 前入睡', remind: '子时载流体自然降温·溶质自然析出的唯一窗口', tag: 'P0·最重要', tagClass: 'tag-accent', priority: 'p0', due: '每日 22:30' },
    { id: 't4', title: '每日脑力 ≤ 3 小时', remind: '脑力=载流体持续湍流+局部加热', tag: 'P1', priority: 'p1', due: '今日' },
    { id: 't5', title: '杜绝冷饮/生冷', remind: '冰水入口→载流体急剧降温→已沉积组织产生微裂隙', tag: 'P2', priority: 'p2' },
    { id: 't6', title: '晨起第一杯：温淡盐水', remind: '温淡盐水唤醒载流体循环', tag: '晨起·每日' },
    { id: 't7', title: '每晚泡脚 15min（40℃ · 不可出汗）', remind: '泡脚促进水形循环，但不可大汗伤阴', tag: '晚间·每日' },
    { id: 't8', title: '散步 30-40min / 八段锦', remind: '温和运动·不剧烈出汗', tag: '运动·每日' },
    { id: 't9', title: '今日饮食：小米粥（早）+ 鲫鱼汤（午）', remind: '避免生冷/辛辣/浓茶咖啡', tag: '饮食·每日' },
    { id: 't10', title: '注意：禁用苦寒直折（黄连/黄芩/大黄）', remind: '绝对禁忌 · 伤 S_土形', tag: '禁忌', tagClass: 'tag-danger' },
  ]
}

function getTodayKey() {
  return new Date().toISOString().slice(0, 10) // YYYY-MM-DD
}

function loadToday() {
  try {
    const saved = localStorage.getItem(TODAY_KEY)
    if (saved) {
      const data = JSON.parse(saved)
      // 如果存的不是今天的日期，先归档昨天的再新建
      if (data.date !== getTodayKey()) {
        archiveYesterday(data)
        return buildTodayTodos()
      }
      return data.todos
    }
  } catch {}
  return buildTodayTodos()
}

function archiveYesterday(yesterdayData) {
  try {
    const raw = localStorage.getItem(ARCHIVE_KEY)
    const archive = raw ? JSON.parse(raw) : []
    archive.unshift({
      date: yesterdayData.date,
      todos: yesterdayData.todos.map(t => ({
        id: t.id,
        title: t.title,
        exec_status: t.exec_status || null,
        feedbacks: getFeedbacks(t.id)
      })),
      totalFeedbacks: yesterdayData.todos.reduce((s, t) => s + (getFeedbacks(t.id).length), 0)
    })
    // 最多保留 90 天
    localStorage.setItem(ARCHIVE_KEY, JSON.stringify(archive.slice(0, 90)))
  } catch {}
}

function saveToday() {
  try {
    localStorage.setItem(TODAY_KEY, JSON.stringify({
      date: getTodayKey(),
      todos: todos.value
    }))
  } catch {}
}

// 反馈存储：{ [todoId]: [{status, note, date}] }
const FEEDBACK_KEY = 'qingnang_feedbacks'
function loadFeedbacks() {
  try { return JSON.parse(localStorage.getItem(FEEDBACK_KEY)) || {} } catch { return {} }
}
function saveFeedbacks() {
  try { localStorage.setItem(FEEDBACK_KEY, JSON.stringify(feedbacks.value)) } catch {}
}

const feedbacks = ref(loadFeedbacks())
function getFeedbacks(todoId) { return feedbacks.value[todoId] || [] }

const todos = ref(loadToday())
watch(todos, saveToday, { deep: true })

function toggleTodo(id) {
  const t = todos.value.find(x => x.id === id)
  if (t) { t.done = !t.done }
}

function handleFeedback(fb) {
  if (!feedbacks.value[fb.todo_id]) feedbacks.value[fb.todo_id] = []
  feedbacks.value[fb.todo_id].push(fb)
  saveFeedbacks()
}

/* ──────────────────────────────────────
   打卡弹窗状态 & 方法
   ────────────────────────────────────── */
const punchModal = reactive({
  todo: null,           // 当前待打卡的 todo 对象
  feedbacks: [],        // 该 todo 的历史反馈
  isEdit: false,        // 是否是修改已完成的打卡
  execStatus: 'done',
  note: '',
  submitting: false,
})

function openPunchModal(todo) {
  punchModal.todo = todo
  punchModal.feedbacks = getFeedbacks(todo.id)
  punchModal.isEdit = !!todo.done
  // 默认选中：新打卡→已完成；修改→上次反馈的 status
  if (punchModal.isEdit && punchModal.feedbacks.length) {
    punchModal.execStatus = punchModal.feedbacks[punchModal.feedbacks.length - 1].status || 'done'
  } else {
    punchModal.execStatus = 'done'
  }
  punchModal.note = ''
  punchModal.submitting = false
  // 禁止 body 滚动
  document.body.style.overflow = 'hidden'
}

function closePunchModal() {
  punchModal.todo = null
  punchModal.note = ''
  punchModal.execStatus = 'done'
  document.body.style.overflow = ''
}

function submitPunch() {
  punchModal.submitting = true
  const fb = {
    status: punchModal.execStatus || 'done',
    note: punchModal.note.trim(),
    date: new Date().toISOString().slice(0, 16).replace('T', ' '),
    todo_id: punchModal.todo.id
  }
  // 1) 保存反馈
  handleFeedback(fb)
  // 2) 标记完成（如果还没完成）
  if (!punchModal.todo.done) {
    toggleTodo(punchModal.todo.id)
  }
  punchModal.submitting = false
  closePunchModal()
}

const filteredTodos = computed(() => {
  const t = todos.value
  if (activeFilter.value === 'pending') return t.filter(x => !x.done)
  return t
})

// 分段器：待处理 / 全部 / 归档（设计稿三段式）
const segTabs = computed(() => [
  { key: 'pending', label: `待处理 ${pendingCount.value}` },
  { key: 'all', label: `全部 ${todos.value.length}` },
  { key: 'archived', label: `归档 ${archivedDays.value} 天` }
])

const pendingCount = computed(() => todos.value.filter(x => !x.done).length)

// ── 体质趋势卡：ΔV 摘要（图例旁一行小字）──
const deltaSummary = computed(() => {
  const rows = deltaTable.value.filter(r => r.delta != null)
  if (!rows.length) return '暂无漂移数据'
  const parts = rows
    .filter(r => Math.abs(r.delta) >= 0.5)
    .map(r => `${r.label} ${r.delta > 0 ? '▲' : '▼'} ${Math.abs(r.delta).toFixed(0)}`)
  return parts.length ? parts.join(' · ') + ' · 余稳定' : '五行 ΔV 均稳定'
})

// ── 时空锚点：今日避忌一行字（只保留一条）──
const avoidText = computed(() => {
  const chong = String(anchor.chong || '').replace(/（.*$/, '')
  return `冲${chong || '兔'} · 忌远行`
})

// ── 时辰节律线：三段式（平稳 / 宜动 / 宜静）──
const rhythmSegments = computed(() => {
  const tl = todayTimeline.value || []
  const desc = (names) => tl
    .filter(t => names.some(n => String(t.range || '').includes(n)))
    .map(t => t.desc).filter(Boolean).slice(0, 2).join(' · ')
  return [
    { range: '05-11 卯·辰', label: '平稳', color: 'calm', desc: desc(['卯', '辰']) || '温盐水 · 小米粥' },
    { range: '17-21 酉·戌', label: '宜动', color: 'active', desc: desc(['酉', '戌']) || '减工作 · 泡脚' },
    { range: '21-01 亥·子', label: '宜静', color: 'rest', desc: desc(['亥', '子']) || '放下手机 · 必睡' }
  ]
})

function execLabel(s) {
  return ({ done: '已完成', partial: '部分执行', skipped: '跳过', failed: '未执行' })[s] || '待执行'
}

// 归档数据
const archives = computed(() => {
  try { return JSON.parse(localStorage.getItem(ARCHIVE_KEY)) || [] } catch { return [] }
})
const archivedDays = computed(() => archives.value.length)
const totalFeedbacks = computed(() => archives.value.reduce((s, a) => s + a.totalFeedbacks, 0))

onMounted(async () => {
  health.value = await healthCheck()
  await vectorStore.fetchCase()
  // 从后端拉动态生活提醒 — 用 SSE 流式（generating 预览 → complete 完整 JSON）
  lifestyleLoading.value = true
  lifestylePreview.value = ''
  lifestyleStream({
    onGenerating: (token) => {
      lifestylePreview.value += token
    },
    onComplete: (d) => {
      lifestyleLoading.value = false
      lifestylePreview.value = ''
      if (d?.anchor) {
        Object.assign(anchor, d.anchor)
        if (d.timeline) todayTimeline.value = d.timeline
        if (d.cloth_reminders) clothReminders.value = d.cloth_reminders
        if (d.food_good) foodGood.value = d.food_good
        if (d.food_bad) foodBad.value = d.food_bad
        if (d.home_reminders) homeReminders.value = d.home_reminders
        if (d.absolute_avoid) absoluteAvoid.value = d.absolute_avoid
        if (d.relative_avoid) relativeAvoid.value = d.relative_avoid
        console.log(`[Dashboard] ✅ 生活提醒来自青檬引擎（engine=${d.engine || 'unknown'}）`)
      }
    },
    onNote: (text) => {
      console.log('[lifestyle note]', text)
    },
    onError: (err) => {
      lifestyleLoading.value = false
      lifestylePreview.value = ''
      console.warn('[Dashboard] ❌ 流式生活提醒失败，尝试非流式 fallback', err)
      // fallback：非流式 lifestyle → 再 fallback 到硬编码
      assistantApi.lifestyle().then((r) => {
        const d = r.data || {}
        if (d.anchor) {
          Object.assign(anchor, d.anchor)
          if (d.timeline) todayTimeline.value = d.timeline
          if (d.cloth_reminders) clothReminders.value = d.cloth_reminders
          if (d.food_good) foodGood.value = d.food_good
          if (d.food_bad) foodBad.value = d.food_bad
          if (d.home_reminders) homeReminders.value = d.home_reminders
          if (d.absolute_avoid) absoluteAvoid.value = d.absolute_avoid
          if (d.relative_avoid) relativeAvoid.value = d.relative_avoid
        }
      }).catch(() => {
        notifApi.today().then((r) => {
          if (r.data?.anchor) Object.assign(anchor, r.data.anchor)
        }).catch(() => { /* 页面里已有的常量会兜底 */ })
      })
    },
  })
})
</script>

<style scoped>
/* max-width 由全局 .page 统一管理（1200px） */

/* ── 问候头部 ── */
.home-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 20px; }
.home-greeting { font-size: 24px; font-weight: 600; color: var(--ink-primary); margin: 0; }
.home-date { font-size: 13px; color: var(--ink-tertiary); margin-top: 4px; }
/* 统计：右对齐弱化，纯文本堆叠（去白盒） */
.home-quick { display: flex; gap: 32px; padding-bottom: 4px; }
.quick-stat { display: flex; flex-direction: column; gap: 2px; text-align: left; }
.qs-val { font-size: 22px; font-weight: 600; color: var(--qingnang-emerald); font-family: var(--font-mono); line-height: 1.1; }
.qs-label { font-size: 12px; color: var(--ink-tertiary); }

/* ── 英雄卡组（桌面并排 / 竖屏上下堆叠） ── */
.hero-row { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; margin-bottom: 16px; }

/* 英雄卡 1：今日最重要的事 */
.hero-card {
  border-radius: var(--radius-lg); padding: 26px 28px;
  background: linear-gradient(135deg, var(--qingnang-emerald) 0%, var(--qingnang-emerald-dark) 100%);
  box-shadow: 0 8px 24px rgba(9, 40, 36, 0.25);
  color: var(--qingnang-paper);
}
.hero-main { display: flex; flex-direction: column; gap: 8px; }
.hero-tag { font-size: 12px; letter-spacing: 3px; color: rgba(242,239,231,0.65); margin: 0; }
.hero-title { font-size: 21px; font-weight: 600; margin: 0; letter-spacing: 1px; }
.hero-item { display: flex; align-items: center; gap: 10px; font-size: 16px; font-weight: 500; margin: 4px 0 0; }
.hero-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--qingnang-spirit); flex-shrink: 0; }
.hero-sub { font-size: 13px; color: rgba(242,239,231,0.72); margin: 0; }
.hero-btn {
  margin-top: 10px; align-self: flex-start;
  padding: 9px 26px; border: none; border-radius: var(--radius-pill);
  background: var(--qingnang-paper); color: var(--qingnang-emerald);
  font-size: 14px; font-weight: 600; letter-spacing: 2px; cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.hero-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }

/* 英雄卡 2：今日宜忌（独立卡，同色系略浅） */
.hero-yi-card {
  border-radius: var(--radius-lg); padding: 22px 24px;
  background: linear-gradient(135deg, rgba(26,77,69,0.88) 0%, rgba(38,105,92,0.88) 100%);
  color: #fff;
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: 0 6px 20px rgba(9, 40, 36, 0.2);
}
.hero-yi-card .hero-title { font-size: 17px; margin-bottom: 14px; }
.yj-pair { display: flex; flex-direction: column; gap: 10px; }
.yj-block {
  display: flex; align-items: center; gap: 12px;
  background: rgba(242,239,231,0.08); border-radius: 10px; padding: 12px 14px;
}
.yj-ico {
  width: 30px; height: 30px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.yj-ico.good { background: rgba(123,196,169,0.25); color: #7BC4A9; }
.yj-ico.bad { background: rgba(208,138,110,0.25); color: #D08A6E; }
.yj-text { display: flex; flex-direction: column; gap: 2px; }
.yj-k { font-size: 11px; letter-spacing: 2px; font-weight: 600; }
.yj-block.yi .yj-k { color: #7BC4A9; }
.yj-block.ji .yj-k { color: #D08A6E; }
.yj-v { font-size: 14px; color: rgba(242,239,231,0.92); font-weight: 500; }
.hero-yi-more {
  margin: 14px 0 0; font-size: 12px; color: rgba(242,239,231,0.55); cursor: pointer;
  letter-spacing: 1px; text-align: right;
}
.hero-yi-more:hover { color: rgba(242,239,231,0.85); }

/* ── 卡头（体质调理曲线 / 时空锚点共用）── */
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--ink-line); }
.card-head h2 { display: flex; align-items: center; gap: 6px; margin: 0; padding: 0; border: none; }
.chip-dv { font-size: 12px; font-weight: 500; color: var(--qingnang-emerald); background: rgba(23,83,76,0.08); border-radius: 12px; padding: 3px 10px; }
.anchor-sub { font-size: 12px; color: var(--ink-tertiary); font-weight: 400; }
.anchor-card .anchor-grid { grid-template-columns: repeat(3, 1fr); }

/* ── 顶部并列 ── */
.top-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; align-items: stretch; }
.card { background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-md); padding: 18px; box-shadow: var(--shadow-card); }
.card h2 { font-size: 15px; color: var(--qingnang-emerald); margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--ink-line); font-weight: 600; letter-spacing: 0.5px; }
.chart-card { min-height: 300px; display: flex; flex-direction: column; }
.chart-card :deep(.radar-chart), .chart-card :deep(.drift-chart) { flex: 1; }

/* ── 体质调理曲线（top-row 左侧） ── */
.curve-chart { flex: 1; min-height: 260px; }
.curve-empty { color: var(--ink-tertiary); text-align: center; padding: 50px 16px; font-size: 13px; }

/* ── 体质趋势卡：雷达图左 + 图例右 ── */
.trend-card { margin-top: 28px; }
.trend-body { display: flex; gap: 20px; align-items: center; flex: 1; min-height: 0; }
.trend-radar { flex: 1; min-width: 0; }
.trend-side { flex-shrink: 0; display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
.legend-row { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink-secondary); }
.lg-swatch { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
.lg-swatch.base { background: var(--qingnang-emerald); }
.lg-swatch.obs { background: var(--wuxing-fire, #A8442F); }
.trend-delta { margin: 2px 0 0; font-size: 12px; color: var(--ink-tertiary); line-height: 1.6; max-width: 200px; }
.btn-ghost-sm {
  align-self: flex-start; margin-top: 4px;
  font-size: 13px; padding: 6px 16px; border-radius: var(--radius-pill);
  border: 1px solid var(--qingnang-emerald); background: transparent; color: var(--qingnang-emerald);
  cursor: pointer; transition: background 0.15s;
}
.btn-ghost-sm:hover { background: rgba(23,83,76,0.06); }

/* ── 分区标题 + 三段分段器 ── */
.section-head { display: flex; justify-content: space-between; align-items: center; margin: 16px 0 12px; gap: 12px; flex-wrap: wrap; }
.section-title { font-size: 18px; font-weight: 600; color: var(--ink-primary); margin: 0; letter-spacing: 0.5px; }
.seg-control { display: flex; background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-pill); overflow: hidden; }
.seg-btn {
  font-size: 13px; padding: 7px 18px; border: none; background: transparent;
  color: var(--ink-tertiary); cursor: pointer; transition: all 0.15s; white-space: nowrap;
}
.seg-btn:hover { color: var(--qingnang-emerald); }
.seg-btn.active { background: var(--qingnang-emerald); color: var(--qingnang-paper); font-weight: 500; }

/* ── 待办卡片网格 ── */
.todo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  grid-auto-rows: 1fr;         /* 关键：每行等高，让卡片内部 flex 布局生效 */
  gap: 16px;
}
.todo-grid > * { height: 100%; }  /* 子元素（TodoCard）撑满网格单元格 */
.todo-empty { grid-column: 1 / -1; text-align: center; padding: 30px; color: var(--ink-tertiary); font-size: 13px; }

/* ── 归档 ── */
.archive-summary { background: var(--qingnang-paper); border-radius: var(--radius-sm); padding: 12px 16px; margin-bottom: 12px; font-size: 13px; color: var(--ink-secondary); }
.archive-summary strong { color: var(--qingnang-emerald); font-weight: 600; }
.archive-list { display: flex; flex-direction: column; gap: 8px; }
.archive-day { background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-sm); overflow: hidden; }
.archive-day-head {
  padding: 12px 16px; cursor: pointer;
  display: flex; gap: 14px; align-items: center; font-size: 13px;
  transition: background 0.15s;
}
.archive-day-head:hover { background: var(--qingnang-paper); }
.archive-date { font-weight: 600; color: var(--qingnang-emerald); font-family: var(--font-mono); }
.archive-todo-count { color: var(--ink-secondary); }
.archive-fb-count { color: var(--ink-tertiary); margin-left: auto; font-size: 12px; }
.archive-day-body { padding: 8px 16px 16px; border-top: 1px solid var(--ink-line); background: var(--qingnang-paper); }
.archive-todo {
  display: flex; gap: 10px; align-items: center;
  padding: 6px 8px; font-size: 12px;
  border-radius: 4px;
}
.archive-todo-title { flex: 1; color: var(--ink-primary); }
.archive-exec { font-size: 11px; padding: 1px 6px; border-radius: 3px; font-weight: 500; }
.archive-exec.exec-done { background: rgba(67,160,71,0.1); color: var(--wuxing-wood); }
.archive-exec.exec-partial { background: rgba(212,160,23,0.1); color: var(--wuxing-earth); }
.archive-exec.exec-skipped { background: rgba(107,114,119,0.1); color: var(--ink-tertiary); }
.archive-exec.exec-failed { background: rgba(216,67,21,0.1); color: var(--wuxing-fire); }
.archive-exec.exec-null { background: var(--qingnang-paper); color: var(--ink-tertiary); }
.archive-fb { font-size: 11px; color: var(--ink-tertiary); }

/* ── 表格 ── */
.table-card { margin-top: 16px; }
.placeholder { color: var(--ink-tertiary); text-align: center; padding: 40px 16px; font-size: 13px; }

/* ── 响应式：竖屏 / 窄窗修复 ── */
@media (max-width: 960px) {
  .top-row { grid-template-columns: 1fr; }
  .chart-card { min-height: 0; }
  .todo-grid { grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
  /* 英雄卡：桌面并排 → 竖屏上下堆叠 */
  .hero-row { grid-template-columns: 1fr; gap: 12px; }
  .hero-yi-card .hero-title { font-size: 16px; margin-bottom: 10px; }
  /* 体质趋势：图上文下 */
  .trend-body { flex-direction: column; align-items: stretch; }
  .trend-radar { width: 100%; }
  .trend-side { align-items: flex-start; }
  .trend-delta { max-width: none; }
  /* 问候区改上下两行，统计左对齐 */
  .home-header { flex-direction: column; align-items: flex-start; gap: 12px; }
  .home-quick { gap: 24px; }
  .table-card { overflow-x: auto; }
  .table { min-width: 520px; }
}
@media (max-width: 640px) {
  .home-greeting { font-size: 19px; }
  .home-quick { gap: 20px; }
  .qs-val { font-size: 18px; }
  .hero-card { padding: 20px; }
  .hero-yi-card { padding: 18px 20px; }
  .anchor-grid { gap: 8px; }
  .ag-cell { padding: 10px 8px; }
  .ag-val { font-size: 13px; }
  .todo-grid { grid-template-columns: 1fr; }
  .anchor-timeline { flex-direction: column; gap: 10px; }
  .seg-control { width: 100%; }
  .seg-btn { flex: 1; padding: 7px 8px; text-align: center; }
  .rem-lists { grid-template-columns: 1fr; }
}

/* ═══════════════════════════════════════════════════════════
   今日时空锚点：三格指标条 + 三段节律线
   ═══════════════════════════════════════════════════════════ */
.anchor-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 14px; }
.ag-cell { background: var(--qingnang-paper); border: none; border-radius: 12px; padding: 12px; text-align: left; }
.ag-label { display: block; font-size: 11px; color: var(--ink-tertiary); margin-bottom: 4px; }
.ag-val { font-size: 16px; font-weight: 600; color: var(--ink-primary); }
.ag-val.warn { color: var(--wuxing-fire, #A8442F); }

.anchor-timeline { display: flex; gap: 8px; }
.tl-seg { flex: 1; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.tl-bar { display: block; height: 4px; border-radius: 2px; }
.tl-seg.calm .tl-bar { background: #C9D8D2; }
.tl-seg.active .tl-bar { background: var(--qingnang-emerald); }
.tl-seg.rest .tl-bar { background: var(--wuxing-earth, #D4A017); }
.tl-text { font-size: 11px; color: var(--ink-tertiary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tl-seg.active .tl-text { color: var(--qingnang-emerald); font-weight: 500; }
.tl-seg.rest .tl-text { color: var(--wuxing-earth, #B8860B); }

/* ═══════════════════════════════════════════════════════════
   生活提醒：折叠行 + 展开区
   ═══════════════════════════════════════════════════════════ */
.reminders-mini { margin-bottom: 16px; padding: 0 18px; }
.rem-collapse {
  width: 100%; display: flex; justify-content: space-between; align-items: center;
  background: transparent; border: none; padding: 14px 0;
  font-size: 13px; color: var(--ink-secondary); cursor: pointer; text-align: left;
}
.rem-collapse:hover .rem-collapse-text { color: var(--qingnang-emerald); }
.rem-collapse-text { transition: color 0.15s; }
.rem-chevron { font-size: 16px; color: var(--ink-tertiary); transition: transform 0.2s; font-weight: 300; }
.rem-chevron.open { transform: rotate(90deg); }
.rem-body { border-top: 1px dashed var(--ink-line); padding: 12px 0 16px; }
.rem-fold-zone { display: flex; flex-direction: column; gap: 10px; }
.rem-fold { border: 1px solid var(--ink-line); border-radius: 8px; background: #fff; }
.rem-fold-summary {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 12px; font-size: 12px; font-weight: 600; color: var(--wuxing-earth);
  cursor: pointer; list-style: none; user-select: none;
}
.rem-fold-summary::-webkit-details-marker { display: none; }
.rem-fold-summary.danger { color: var(--wuxing-fire); }
.rem-fold-summary::after { content: '›'; margin-left: auto; font-size: 14px; color: var(--ink-tertiary); transition: transform 0.2s; font-weight: 300; }
.rem-fold[open] .rem-fold-summary::after { transform: rotate(90deg); }
.rem-fold .rem-item { margin: 0 10px 10px; }
.rem-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.rem-head h2 { font-size: 15px; color: var(--qingnang-emerald); margin: 0; }

/* ── Lifestyle 流式加载 ── */
.lifestyle-loading { padding: 20px 12px; }
.lifestyle-loading-header { display: flex; align-items: center; gap: 10px; color: var(--qingnang-emerald); font-size: 13px; margin-bottom: 12px; font-weight: 500; }
.spinner { animation: pulse 1.2s ease-in-out infinite; display: inline-block; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.lifestyle-preview { background: #f7f9fa; border: 1px solid var(--ink-line); border-radius: var(--radius-sm); padding: 10px 12px; font-family: var(--font-mono, monospace); font-size: 11px; color: var(--ink-tertiary); max-height: 120px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; margin: 0; line-height: 1.6; }
.lifestyle-preview-placeholder { color: var(--ink-tertiary); font-size: 12px; font-style: italic; padding: 20px 0; text-align: center; }
.rem-tabs { display: flex; gap: 4px; }
.rem-tab {
  font-size: 12px; padding: 5px 12px; border-radius: 14px;
  border: 1px solid var(--ink-line); background: #fff; color: var(--ink-secondary);
  cursor: pointer; transition: all 0.15s;
}
.rem-tab:hover { border-color: var(--qingnang-emerald); color: var(--qingnang-emerald); }
.rem-tab.active { background: var(--qingnang-emerald); border-color: var(--qingnang-emerald); color: #fff; }

.rem-lists { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 720px) { .rem-lists { grid-template-columns: 1fr; } }
.rem-col { display: flex; flex-direction: column; gap: 6px; }
.rem-col-title { font-size: 12px; margin: 0 0 4px; padding-bottom: 4px; border-bottom: 1px dashed var(--ink-line); }
.rem-col-title.good { color: var(--wuxing-wood); }
.rem-col-title.bad { color: var(--wuxing-fire); }
.rem-col-title.warn { color: var(--wuxing-earth); }

.rem-item {
  padding: 10px 12px; border-radius: 8px; border: 1px solid var(--ink-line);
  background: #fff; display: flex; flex-direction: column; gap: 3px;
}
.rem-item-title { font-size: 13px; font-weight: 600; color: var(--ink-primary); }
.rem-item-desc { font-size: 12px; color: var(--ink-secondary); line-height: 1.5; }
.rem-item.rem-good { border-left: 3px solid var(--wuxing-wood); }
.rem-item.rem-bad { border-left: 3px solid var(--wuxing-fire); }
.rem-item.rem-danger { border-left: 4px solid var(--wuxing-fire); background: linear-gradient(135deg, #fff, rgba(216,67,21,0.03)); }
.rem-item.rem-stone { border-left: 3px solid var(--wuxing-metal); }
.rem-item.rem-urgent { border-left: 3px solid var(--wuxing-fire); background: rgba(216,67,21,0.04); }

/* ═══════════════════════════════════════════
   打卡弹窗（全屏遮罩 + 居中卡片）
   ═══════════════════════════════════════════ */
.punch-modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(16, 24, 40, 0.45);
  backdrop-filter: blur(3px);
  z-index: 9999;
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.punch-modal {
  background: #fff;
  border-radius: 16px;
  width: 100%; max-width: 520px;
  max-height: 92vh;
  overflow-y: auto;
  padding: 24px;
  box-shadow: 0 20px 60px rgba(16, 24, 40, 0.25);
  animation: pm-slide-up 0.25s ease-out;
}
@keyframes pm-slide-up {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

/* 弹窗头部 */
.pm-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 20px; padding-bottom: 14px;
  border-bottom: 1px solid var(--ink-line);
}
.pm-title-wrap { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.pm-tag {
  display: inline-block; width: fit-content;
  font-size: 11px; color: var(--qingnang-emerald);
  background: rgba(26,77,69,0.08);
  padding: 2px 10px; border-radius: 10px;
  letter-spacing: 1px; font-weight: 500;
}
.pm-title { font-size: 18px; color: var(--ink-primary); margin: 0; font-weight: 600; line-height: 1.35; }
.pm-due { font-size: 12px; color: var(--ink-tertiary); margin: 0; }
.pm-close {
  width: 32px; height: 32px; border-radius: 50%;
  border: 1px solid var(--ink-line); background: #fff;
  color: var(--ink-tertiary); font-size: 14px; line-height: 1;
  cursor: pointer; transition: all 0.15s;
  flex-shrink: 0; margin-left: 12px;
}
.pm-close:hover { color: var(--wuxing-fire); border-color: var(--wuxing-fire); }

/* section */
.pm-section { margin-bottom: 18px; }
.pm-label {
  font-size: 12px; color: var(--ink-tertiary);
  display: block; margin-bottom: 8px; font-weight: 500;
}

/* 执行状态按钮 */
.pm-exec-btns { display: flex; gap: 8px; flex-wrap: wrap; }
.pm-exec {
  font-size: 13px; padding: 7px 16px;
  border-radius: 20px;
  border: 1px solid var(--ink-line);
  background: #fff; color: var(--ink-secondary);
  cursor: pointer; transition: all 0.15s;
}
.pm-exec:hover { border-color: var(--qingnang-emerald); color: var(--qingnang-emerald); }
.pm-exec.active {
  background: var(--qingnang-emerald); border-color: var(--qingnang-emerald);
  color: #fff; box-shadow: 0 2px 6px rgba(23, 83, 76, 0.25);
}

/* 历史反馈 */
.pm-fb-item {
  display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  font-size: 12px; padding: 8px 10px; background: var(--qingnang-paper);
  border-radius: 6px; margin-bottom: 6px;
  border-left: 3px solid var(--ink-line);
}
.pm-fb-date { color: var(--ink-tertiary); font-family: var(--font-mono); font-size: 11px; }
.pm-fb-status { font-weight: 600; padding: 1px 8px; border-radius: 3px; font-size: 11px; }
.pm-fb-done { background: rgba(67,160,71,0.1); color: var(--wuxing-wood); }
.pm-fb-partial { background: rgba(212,160,23,0.1); color: var(--wuxing-earth); }
.pm-fb-skipped { background: rgba(107,114,119,0.1); color: var(--ink-tertiary); }
.pm-fb-failed { background: rgba(216,67,21,0.1); color: var(--wuxing-fire); }
.pm-fb-note { flex: 1 0 100%; color: var(--ink-secondary); line-height: 1.5; margin-top: 3px; }

/* 反馈输入 */
.pm-section textarea {
  width: 100%; border: 1px solid var(--ink-line); border-radius: 10px;
  padding: 12px; font-size: 14px; font-family: var(--font-body);
  resize: vertical; background: #fff; color: var(--ink-primary);
  line-height: 1.55; transition: border-color 0.15s;
  box-sizing: border-box;
}
.pm-section textarea:focus { outline: none; border-color: var(--qingnang-emerald); }

/* 底部按钮 */
.pm-foot {
  display: flex; justify-content: flex-end; gap: 10px;
  margin-top: 22px; padding-top: 16px;
  border-top: 1px solid var(--ink-line);
}
.pm-cancel {
  padding: 9px 22px; border: 1px solid var(--ink-line); border-radius: var(--radius-pill);
  background: #fff; color: var(--ink-secondary); font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.pm-cancel:hover { color: var(--ink-primary); border-color: var(--ink-tertiary); }
.pm-submit {
  padding: 9px 24px; border: none; border-radius: var(--radius-pill);
  background: var(--qingnang-emerald); color: var(--qingnang-paper);
  font-size: 13px; font-weight: 500; letter-spacing: 2px; cursor: pointer;
  transition: all 0.15s;
}
.pm-submit:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(23, 83, 76, 0.3); }
.pm-submit:disabled { opacity: 0.5; cursor: not-allowed; }

/* Transition */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-active .punch-modal, .fade-leave-active .punch-modal { transition: transform 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.fade-enter-from .punch-modal, .fade-leave-to .punch-modal { transform: translateY(10px) scale(0.97); }

/* 弹窗手机竖屏 */
@media (max-width: 480px) {
  .punch-modal-backdrop { padding: 0; }
  .punch-modal {
    max-width: 100%; max-height: 100vh; border-radius: 0;
    padding: 20px;
    animation: none;
  }
  .pm-title { font-size: 16px; }
  .pm-exec-btns { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .pm-foot { gap: 8px; }
  .pm-cancel, .pm-submit { flex: 1; padding: 11px 0; text-align: center; }
}
</style>
