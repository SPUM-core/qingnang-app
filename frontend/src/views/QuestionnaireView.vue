<template>
  <section class="onboarding">
    <!-- 步骤指示器 -->
    <div class="steps">
      <div v-for="s in steps" :key="s.idx"
           class="step" :class="{ active: currentStep >= s.idx, done: currentStep > s.idx }">
        <span class="step-num">{{ s.idx }}</span>
        <span class="step-label">{{ s.title }}</span>
      </div>
    </div>

    <!-- 返回登录 — 仅 Step 1 显示 -->
    <button v-if="currentStep === 1" class="back-to-login" type="button" @click="goLogin">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      <span>返回登录</span>
    </button>

    <!-- ═══ Step 1: 基础信息 → 推演先天八字 → 直接进问诊 ═══ -->
    <div v-if="currentStep === 1" class="card">
      <h2>先让青囊认识你</h2>
      <p class="step-desc">请填写您的真实信息，这将影响青囊对您的数字建模。</p>

      <div class="form">
        <div class="form-grid">
          <label class="field">
            <span>真实姓名 <em>*</em></span>
            <input v-model="form.nickname"/>
          </label>
          <label class="field">
            <span>小名（可选）</span>
            <input v-model="form.nickname_alias"/>
          </label>
          <label class="field">
            <span>性别 <em>*</em></span>
            <select v-model="form.gender">
              <option disabled value="">请选择</option>
              <option value="男">男</option>
              <option value="女">女</option>
            </select>
          </label>
          <label class="field">
            <span>出生日期 <em>*</em>
              <label class="date-toggle">
                <input type="radio" v-model="form.birth_date_type" value="solar" />
                <span>阳历</span>
              </label>
              <label class="date-toggle">
                <input type="radio" v-model="form.birth_date_type" value="lunar" />
                <span>阴历</span>
              </label>
            </span>
            <div v-if="form.birth_date_type === 'solar'" class="date-picker">
              <select v-model.number="form.solar_year">
                <option disabled :value="null">年</option>
                <option v-for="y in SOLAR_YEARS" :key="y" :value="y">{{ y }}年</option>
              </select>
              <select v-model.number="form.solar_month">
                <option disabled :value="null">月</option>
                <option v-for="m in 12" :key="m" :value="m">{{ m }}月</option>
              </select>
              <select v-model.number="form.solar_day">
                <option disabled :value="null">日</option>
                <option v-for="d in solarDayOptions" :key="d" :value="d">{{ d }}日</option>
              </select>
            </div>
            <div v-else class="date-picker">
              <select v-model.number="form.lunar_year" @change="fetchLunarMonths">
                <option disabled :value="null">年</option>
                <option v-for="y in LUNAR_YEARS" :key="y" :value="y">{{ y }}年</option>
              </select>
              <select v-model="form.lunar_month_key">
                <option disabled :value="null">月</option>
                <option v-for="m in lunarMonths" :key="m.key" :value="m.key">{{ m.label }}</option>
              </select>
              <select v-model.number="form.lunar_day">
                <option disabled :value="null">日</option>
                <option v-for="d in lunarDayOptions" :key="d" :value="d">{{ d }}日</option>
              </select>
            </div>
          </label>
          <label class="field">
            <span>出生时辰（可选 · 更精准）</span>
            <select v-model="form.birth_hour">
              <option value="">未知</option>
              <option>子时（23-1点）</option>
              <option>丑时（1-3点）</option>
              <option>寅时（3-5点）</option>
              <option>卯时（5-7点）</option>
              <option>辰时（7-9点）</option>
              <option>巳时（9-11点）</option>
              <option>午时（11-13点）</option>
              <option>未时（13-15点）</option>
              <option>申时（15-17点）</option>
              <option>酉时（17-19点）</option>
              <option>戌时（19-21点）</option>
              <option>亥时（21-23点）</option>
            </select>
          </label>
          <label class="field">
            <span>身高（cm）<em>*</em></span>
            <input v-model.number="form.height" type="number" placeholder="如 170" min="120" max="230" />
          </label>
          <label class="field">
            <span>体重（kg）<em>*</em></span>
            <input v-model.number="form.weight" type="number" step="0.1" placeholder="如 65" min="30" max="200" />
          </label>
          <label class="field field-full">
            <span>出生地 <em>*</em></span>
            <div class="cascader">
              <select v-model="form.birth_province" @change="onProvinceChange">
                <option disabled value="">请选择省份</option>
                <option v-for="p in PROVINCES" :key="p.code" :value="p.code">{{ p.name }}</option>
              </select>
              <select v-model="form.birth_city" :disabled="!form.birth_province">
                <option disabled value="">{{ form.birth_province ? '请选择城市' : '先选省份' }}</option>
                <option v-for="c in availableCities" :key="c.name" :value="c.name">
                  {{ c.name }}
                  <span v-if="c.lng" class="city-lng">{{ c.lng.toFixed(2) }}°E</span>
                </option>
              </select>
            </div>
            <span class="field-hint" v-if="birthCityLng">
              真太阳时经度修正：当前 {{ birthCityLng.toFixed(2) }}°E（北京时间以 120°E 为基准，{{ (birthCityLng - 120).toFixed(2) }}° → {{ ((birthCityLng - 120) * 4).toFixed(1) }} 分钟时差）
            </span>
          </label>
          <label class="field field-full">
            <span class="living-label">
              常住地
              <button type="button" class="btn-same-as" :class="{ active: form.same_as_birth }" @click="toggleSameAsBirth">
                {{ form.same_as_birth ? '✓ 与出生地相同' : '与出生地相同' }}
              </button>
            </span>
            <div class="cascader">
              <select v-model="form.living_province" :disabled="form.same_as_birth" @change="onLivingProvinceChange">
                <option disabled value="">请选择省份</option>
                <option v-for="p in PROVINCES" :key="p.code" :value="p.code">{{ p.name }}</option>
              </select>
              <select v-model="form.living_city" :disabled="form.same_as_birth || !form.living_province">
                <option disabled value="">{{ livingProvince ? '请选择城市' : '先选省份' }}</option>
                <option v-for="c in livingCities" :key="c.name" :value="c.name">
                  {{ c.name }}
                </option>
              </select>
            </div>
          </label>
        </div>
        <button class="btn btn-primary" @click="doOnboardAndInquiry" :disabled="calculating || !canCalcBazi">
          <span v-if="calculating">🧠 推演中…</span>
          <span v-else>下一步</span>
        </button>
      </div>
    </div>

    <!-- ═══ Step 2: 体质推理报告 · 病历式 6 段 ═══ -->
    <div v-else-if="currentStep === 2" class="card medical-report">
      <h2>你的先天体质画像</h2>
      <p class="step-desc">基于八字排盘 + SPUM 五行推演 + 大运流年，青囊为你生成病历级体质画像。</p>

      <!-- 体质总纲 hero -->
      <div v-if="constitutionData?.constitution_summary" class="constitution-hero">
        <div class="ch-bazi">{{ constitutionData.rule_data?.bazi || constitutionData.bazi }}</div>
        <div class="ch-summary">{{ constitutionData.constitution_summary }}</div>
      </div>

      <!-- 五行雷达（规则可视化，始终保留作为锚点） -->
      <div class="radar-anchor" v-if="constitutionData">
        <div v-for="el in ELEMENT_META" :key="el.name" class="radar-bar-mini">
          <span class="r-label">{{ el.emoji }}{{ el.cn }}</span>
          <div class="r-track">
            <div class="r-fill" :style="{ width: (constitutionData.rule_data?.v_innate?.[el.name] || 0) + '%' }"></div>
          </div>
          <span class="r-score">{{ (constitutionData.rule_data?.v_innate?.[el.name] || 0).toFixed(0) }}</span>
        </div>
      </div>

      <!-- ═══ 6 段病历式内容 ═══ -->
      <template v-if="constitutionData?.llm_sections?.sections">
        <!-- ① 八字排盘 -->
        <section class="m-section" v-if="constitutionData.llm_sections.sections.bazi_analysis">
          <h4>❶ 八字排盘</h4>
          <div class="m-body" v-html="renderMd(constitutionData.llm_sections.sections.bazi_analysis)"></div>
        </section>

        <!-- ② 先天基底推估 -->
        <section class="m-section" v-if="constitutionData.llm_sections.sections.innate_base">
          <h4>❷ 先天基底推估</h4>
          <div class="m-body" v-html="renderMd(constitutionData.llm_sections.sections.innate_base)"></div>
        </section>

        <!-- ③ 地缘因子修正 -->
        <section class="m-section" v-if="constitutionData.llm_sections.sections.geo_factor">
          <h4>❸ 地缘因子修正</h4>
          <div class="m-body" v-html="renderMd(constitutionData.llm_sections.sections.geo_factor)"></div>
        </section>

        <!-- ④ 姓名与职业因子 -->
        <section class="m-section" v-if="constitutionData.llm_sections.sections.name_career">
          <h4>❹ 姓名与职业因子</h4>
          <div class="m-body" v-html="renderMd(constitutionData.llm_sections.sections.name_career)"></div>
        </section>

        <!-- ⑤ 大运流年排盘与当前大运分析 -->
        <section class="m-section" v-if="constitutionData.llm_sections.sections.dayun_current">
          <h4>❺ 大运流年排盘</h4>
          <div class="m-body" v-html="renderMd(constitutionData.llm_sections.sections.dayun_current)"></div>
        </section>

        <!-- ⑥ 先天体质倾向与核心体质特征 -->
        <section class="m-section m-section-highlight" v-if="constitutionData.llm_sections.sections.constitution_summary_detail">
          <h4>❻ 先天体质倾向</h4>
          <div class="m-body" v-html="renderMd(constitutionData.llm_sections.sections.constitution_summary_detail)"></div>
        </section>
      </template>

      <!-- fallback：如果 LLM 没返回（降级），显示规则版 -->
      <template v-else-if="constitutionData">
        <div class="m-fallback">规则计算结果，LLM 润色未启用。</div>
      </template>

      <!-- 底部操作 -->
      <div class="report-actions">
        <button class="btn btn-ghost" @click="currentStep = 1">← 修改基础信息</button>
        <button class="btn btn-primary" @click="submitAll" :disabled="submitting">
          {{ submitting ? '✓ 正在创建数字模型…' : '✓ 确认创建我的数字模型' }}
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { assistant as assistantApi, auth as authApi, cases as casesApi } from '../api/client'
import * as storage from '../utils/storage'
import { useUserStore } from '../stores/user'
import { CHINA_PROVINCES, CHINA_CITIES } from '../constants/china-cities.js'

const router = useRouter()
const userStore = useUserStore()

/** 返回登录 — 清状态 + 跳路由 */
function goLogin() {
  userStore.logout()
  router.replace({ name: 'login' })
}

// ── 状态 ──
const currentStep = ref(1)           // 1: 基础信息 → 2: 体质推理报告
const calculating = ref(false)
const submitting = ref(false)
const baziResult = ref(null)         // 八字推演结果
const constitutionData = ref(null)   // 体质分析结果

const steps = [
  { idx: 1, title: '基础信息' },
  { idx: 2, title: '体质画像' },
]

// ── 极简 Markdown 渲染器（处理 LLM 返回的病历文本） ──
function renderMd(md) {
  if (!md) return ''
  let html = md
  // 1. 标题：### 文字 → <h5>文字</h5>；## → <h4>
  html = html.replace(/^### (.+)$/gm, '<h5>$1</h5>')
  html = html.replace(/^## (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^# (.+)$/gm, '<h3>$1</h3>')
  // 2. 表格：| a | b | → <table>（简单处理：逐行转 tr/td）
  if (html.includes('|')) {
    html = html.split('\n').map(line => {
      if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
        const cells = line.split('|').slice(1, -1).map(c => c.trim())
        if (cells.every(c => c === '---' || c === '-')) return ''  // 跳过分隔行
        const tag = cells.every(c => c.startsWith('**') && c.endsWith('**')) ? 'th' : 'td'
        return `<tr>${cells.map(c => `<${tag}>${c.replace(/\*\*/g, '')}</${tag}>`).join('')}</tr>`
      }
      return line
    }).join('\n')
    // 包裹 <table>
    html = html.replace(/((?:<tr>.*<\/tr>\n?)+)/g, '<table>$1</table>')
  }
  // 3. 无序列表：- 文字 → <li>
  html = html.replace(/^  - (.+)$/gm, '<li>$1</li>')
  html = html.replace(/^  ─ (.+)$/gm, '<li class="li-dash">$1</li>')
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  // 4. 分隔线：--- → <hr>
  html = html.replace(/^---$/gm, '<hr>')
  // 5. 加粗：**文字** → <strong>
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // 6. 行内代码/标记：`文字` → <code>
  html = html.replace(/`(.+?)`/g, '<code>$1</code>')
  // 7. 行内「」引号保留（已经是中文引号）
  // 8. 段落换行：空行 → </p><p>；非空行 → <p>...</p>
  html = html.split('\n\n').map(block => {
    block = block.trim()
    if (!block) return ''
    // 已经是 HTML 标签开头的块（table, ul, h3, h4, h5, hr）→ 保持原样
    if (/^<(table|tr|li|h3|h4|h5|hr|ul)/.test(block)) return block
    // 含 <tr> 开头 → 表格块，保持原样
    if (block.includes('<tr>')) return block
    // 含 <li> 开头 → 列表块
    if (block.includes('<li>')) return `<ul>${block}</ul>`
    // 普通段落
    return `<p>${block.replace(/\n/g, '<br>')}</p>`
  }).join('')
  return html
}

// 五行元素元数据
const ELEMENT_META = {
  wood:  { name: 'wood',  cn: '木', emoji: '🌲' },
  fire:  { name: 'fire',  cn: '火', emoji: '🔥' },
  earth: { name: 'earth', cn: '土', emoji: '🪨' },
  metal: { name: 'metal', cn: '金', emoji: '⚙️' },
  water: { name: 'water', cn: '水', emoji: '💧' },
}

const PROVINCES = CHINA_PROVINCES

// ── 阳历/阴历年份常量 ──
const SOLAR_YEARS = Array.from({ length: 120 }, (_, i) => 2025 - i)   // 1906~2025
const LUNAR_YEARS = Array.from({ length: 120 }, (_, i) => 2025 - i)   // 同范围

// ── 阳历时天数（动态算，处理闰年） ──
const _SOLAR_BIG = [1,3,5,7,8,10,12]    // 31天
const _SOLAR_SMALL = [4,6,9,11]         // 30天
function _isLeap(y) { return y % 400 === 0 || (y % 100 !== 0 && y % 4 === 0) }
function _solarDaysInMonth(y, m) {
  if (_SOLAR_BIG.includes(m)) return 31
  if (_SOLAR_SMALL.includes(m)) return 30
  if (m === 2) return _isLeap(y) ? 29 : 28
  return 30
}

// ── 阴历天数需要后端 lunar_python ──
const lunarDaysCache = ref({})
const lunarMonths = ref([])   // [{key: "6", label: "6月"}, {key: "leap-6", label: "闰6月"}]

async function fetchLunarDays(y, m, isLeap = false) {
  if (!y || !m) return 29
  const key = `${y}-${m}${isLeap ? '-leap' : ''}`
  if (lunarDaysCache.value[key]) return lunarDaysCache.value[key]
  try {
    const r = await api.get(
      `/api/v1/assistant/lunar-days?year=${y}&month=${m}&is_leap=${isLeap ? 1 : 0}`
    )
    const days = r.data?.days || 29
    lunarDaysCache.value[key] = days
    return days
  } catch { return 29 }
}

async function fetchLunarMonths() {
  if (!form.lunar_year) return
  try {
    const r = await api.get(`/api/v1/assistant/lunar-months?year=${form.lunar_year}`)
    const months = r.data?.months || []
    lunarMonths.value = months.map(m => ({
      key: m.is_leap ? `leap-${m.month}` : String(m.month),
      label: m.is_leap ? `闰${m.month}月` : `${m.month}月`,
    }))
  } catch {
    lunarMonths.value = Array.from({ length: 12 }, (_, i) => ({
      key: String(i + 1), label: `${i + 1}月`,
    }))
  }
}

// ── 表单数据 ──
const form = reactive({
  nickname: '',
  nickname_alias: '',     // 小名（可选）
  gender: '',
  birth_date: '',           // 阳历存 YYYY-MM-DD，阴历由 lunar_* 拼
  birth_date_type: 'solar', // 'solar' (阳历) | 'lunar' (阴历)
  birth_hour: '',
  height: null,            // cm
  weight: null,            // kg
  birth_province: '',      // 省 code
  birth_city: '',          // 市 name
  living_province: '',     // 常住省 code
  living_city: '',         // 常住市 name
  same_as_birth: false,    // 常住地 = 出生地开关
  answers: {},
  // 选择器中间态（不直接提交，watch 拼 birth_date）
  solar_year: null,
  solar_month: null,
  solar_day: null,
  lunar_year: null,
  lunar_month_key: null,    // 字符串: "6" 或 "leap-6"
  lunar_day: null,
})

// 解析阴历月份 key → { month: number, is_leap: boolean }
const lunarMonthParsed = computed(() => {
  const k = form.lunar_month_key
  if (!k) return { month: null, is_leap: false }
  if (k.startsWith('leap-')) return { month: Number(k.slice(5)), is_leap: true }
  return { month: Number(k), is_leap: false }
})

// ── 级联联动：省 → 市 ──
function onProvinceChange() {
  form.birth_city = ''  // 省变了，清空市
}
const availableCities = computed(() => {
  if (!form.birth_province) return []
  return CHINA_CITIES[form.birth_province] || []
})
/** 当前所选城市的经度（用于真太阳时修正） */
const birthCityLng = computed(() => {
  if (!form.birth_province || !form.birth_city) return null
  const city = CHINA_CITIES[form.birth_province]?.find(c => c.name === form.birth_city)
  return city?.lng ?? null
})

/** 常住地级联 */
function onLivingProvinceChange() {
  form.living_city = ''
}
const livingProvince = computed(() => form.living_province)
const livingCities = computed(() => {
  if (!form.living_province) return []
  return CHINA_CITIES[form.living_province] || []
})

/** "常住地与出生地相同"开关 */
function toggleSameAsBirth() {
  form.same_as_birth = !form.same_as_birth
  if (form.same_as_birth) {
    // 记住用户原来填的常住地（方便取消开关后恢复）
    form._living_prev_province = form.living_province
    form._living_prev_city = form.living_city
    // 同步出生地
    form.living_province = form.birth_province
    form.living_city = form.birth_city
  } else {
    // 如果之前手动填过，恢复；否则保留当前值（让用户自己改）
    if (form._living_prev_province || form._living_prev_city) {
      form.living_province = form._living_prev_province || ''
      form.living_city = form._living_prev_city || ''
    }
    // 清掉"之前值"记忆
    form._living_prev_province = ''
    form._living_prev_city = ''
  }
}

// watch：开着"与出生地相同"时，出生地变了自动同步常住地
watch(
  () => [form.same_as_birth, form.birth_province, form.birth_city],
  ([same, bp, bc]) => {
    if (same) {
      form.living_province = bp
      form.living_city = bc
    }
  }
)

// ── 阳/阴历日选择：根据月份大小切换 28-30 天 ──
// 阳历：前端直接算（闰年处理）
const solarDayOptions = computed(() => {
  if (!form.solar_year || !form.solar_month) return []
  const n = _solarDaysInMonth(form.solar_year, form.solar_month)
  return Array.from({ length: n }, (_, i) => i + 1)
})

// 阴历：等后端返回（大小月不固定 + 有闰月）
const lunarDayOptions = ref([])   // ref（不用 computed —— 异步 fetch 完直接赋值）

// watch 阴历年月变化 → fetch 天数 → 更新下拉选项
watch(
  () => [form.lunar_year, form.lunar_month_key],
  async ([ly, lk], [oldY]) => {
    // 年变了同时拉月份列表
    if (ly && ly !== oldY && !lunarMonths.value.length) {
      await fetchLunarMonths()
    }
    if (!ly || !lk) { lunarDayOptions.value = []; return }
    const lp = lunarMonthParsed.value
    const days = await fetchLunarDays(ly, lp.month, lp.is_leap)
    lunarDayOptions.value = Array.from({ length: days }, (_, i) => i + 1)
  }
)

// ── 统一 watch → 自动拼 birth_date ──
watch(
  () => [
    form.birth_date_type,
    form.solar_year, form.solar_month, form.solar_day,
    form.lunar_year, form.lunar_month_key, form.lunar_day,
  ],
  ([type, sy, sm, sd, ly, lk, ld]) => {
    if (type === 'solar') {
      if (sy && sm && sd) {
        form.birth_date = `${sy}-${String(sm).padStart(2,'0')}-${String(sd).padStart(2,'0')}`
      } else { form.birth_date = '' }
    } else {
      const lp = lunarMonthParsed.value
      if (ly && lp.month && ld) {
        form.birth_date = `${ly}-${String(lp.month).padStart(2,'0')}-${String(ld).padStart(2,'0')}${lp.is_leap ? '闰' : ''}`
      } else { form.birth_date = '' }
    }
  }
)

// 切换阴/阳历时，清空 birth_date + 两种 select 互不污染
watch(
  () => form.birth_date_type,
  () => {
    form.birth_date = ''
    form.solar_year = null; form.solar_month = null; form.solar_day = null
    form.lunar_year = null; form.lunar_month = null; form.lunar_day = null
  }
)

// ── Step 1 校验 ──
const canCalcBazi = computed(() => {
  return form.nickname.trim()
    && form.gender
    && form.birth_date
    && form.birth_city
    && form.height && form.height >= 120 && form.height <= 230
    && form.weight && form.weight >= 30 && form.weight <= 200
})

// ── Step 1 → 推演八字 → 体质分析 → Step 2 ──
async function doOnboardAndInquiry() {
  if (!canCalcBazi.value) return
  calculating.value = true
  try {
    // 1. 八字推演
    const resp = await assistantApi.bazi(
      form.birth_date, form.birth_hour || null,
      form.birth_city, form.birth_date_type,
    )
    baziResult.value = resp.data || resp

    // 2. 调体质分析接口（传完整八字上下文，让 LLM 做病历级可验证预测）
    const constResp = await assistantApi.constitutionAnalysis({
      v_innate: baziResult.value.v_innate,
      day_master_element: baziResult.value.day_master_element,
      day_master: baziResult.value.day_master,
      bazi: baziResult.value.bazi,
      pillars: baziResult.value.pillars,
      ganzhi_year: baziResult.value.ganzhi_year,
      ganzhi_month: baziResult.value.ganzhi_month,
      ganzhi_day: baziResult.value.ganzhi_day,
      ganzhi_hour: baziResult.value.ganzhi_hour,
      birth_date: form.birth_date,
      birth_hour: form.birth_hour || null,
      birth_city: form.birth_city,
      gender: form.gender,
      nickname: form.nickname,
    })
    constitutionData.value = constResp.data || constResp

    // 3. PATCH 用户档案
    await authApi.patchMe({
      nickname: form.nickname, gender: form.gender,
      height: form.height, weight: form.weight,
      birth_date: form.birth_date, birth_hour: form.birth_hour || null,
    })
    userStore.nickname = form.nickname
    const saved = storage.get('qingnang_user', {}) || {}
    saved.nickname = form.nickname
    storage.set('qingnang_user', saved)

    currentStep.value = 2
  } catch (e) {
    alert('初始化失败：' + (e.message || e))
  } finally {
    calculating.value = false
  }
}

// ── 选项集 ──
const FREQ_OPTS = [
  { value: 3, label: '经常' }, { value: 2, label: '有时' },
  { value: 1, label: '很少' }, { value: 0, label: '从不' },
]
const QUALITY_OPTS = [
  { value: 2, label: '好' }, { value: 1, label: '一般' }, { value: 0, label: '差' },
]
const STATE_OPTS = [
  { value: 2, label: '正常' }, { value: 1, label: '偶有' }, { value: 0, label: '明显' },
]

// ── 五行体质题库（症状描述题 → 频率选项 FREQ_OPTS）──
const _ELEMENT_META = {
  wood:  { cn: '木', emoji: '🌲' },
  fire:  { cn: '火', emoji: '🔥' },
  earth: { cn: '土', emoji: '🪨' },
  metal: { cn: '金', emoji: '⚙️' },
  water: { cn: '水', emoji: '💧' },
}

const _SYMPTOM_BANK = {
  wood_weak: [
    '容易情绪低落或叹气',
    '眼睛容易干涩、视物模糊',
    '肢体偶尔麻木或关节酸痛',
    '遇事容易想不开、纠结',
  ],
  wood_strong: [
    '容易急躁易怒、发火',
    '头部或胁肋部偶尔胀痛',
    '晚上入睡困难、梦多',
    '口干口苦、大便偏干',
  ],
  fire_weak: [
    '怕冷、手脚常发凉',
    '容易心悸或心慌',
    '夜尿多或清长',
    '说话声音偏低、气短',
  ],
  fire_strong: [
    '口舌容易生疮或牙龈肿痛',
    '心烦失眠、脑子停不下来',
    '面红耳赤或容易出汗',
    '大便干结、小便黄赤',
  ],
  earth_weak: [
    '食欲不振、吃一点就胀',
    '大便偏稀或黏腻',
    '容易乏力、不想动',
    '体型偏瘦或不易长肉',
  ],
  earth_strong: [
    '脘腹胀满、打嗝多',
    '口苦口粘、舌苔厚',
    '体型偏胖或易腹胀',
    '头重身困、总想睡',
  ],
  metal_weak: [
    '皮肤容易干燥、脱屑',
    '容易咳嗽或喉咙痒',
    '气短、说话没力气',
    '容易感冒或过敏',
  ],
  metal_strong: [
    '咳痰黄稠或咽痛',
    '鼻子干燥或出血',
    '大便干结如羊粪',
    '声音洪亮但易嘶哑',
  ],
  water_weak: [
    '腰膝酸软、容易疲劳',
    '头晕耳鸣或健忘',
    '头发容易脱落或早白',
    '夜寐不安、多梦易醒',
  ],
  water_strong: [
    '畏寒肢冷、腰膝冷痛',
    '小便清长或夜尿多',
    '面色偏白或怕冷风',
    '性欲偏低或精力不济',
  ],
}

// ── 状态评估题（通用补漏题 → 程度选项 QUALITY_OPTS）──
const _STATE_BANK = [
  '整体精力状态如何？',
  '睡眠质量如何？',
  '食欲和消化如何？',
  '情绪状态如何？',
]

/**
 * 根据 v_innate 规则化生成 5-10 道验证题
 * 症状描述题 → FREQ_OPTS（经常/有时/很少/从不）
 * 状态评估题 → QUALITY_OPTS（好/一般/差）
 */
function buildVerifyQuestions(vInnate) {
  const DEV_THRESHOLD = 15
  const PER_ELEM = 2
  const target = 8   // 总题数 8 道左右

  // 1. 计算每个五行的偏离程度
  const deviations = Object.entries(vInnate || {}).map(([el, score]) => ({
    el, score, absDelta: Math.abs(score - 50),
    polarity: score < 50 ? 'weak' : 'strong',
  }))

  // 2. 按偏离绝对值排序，取前 3 个
  deviations.sort((a, b) => b.absDelta - a.absDelta)
  const top3 = deviations.filter(d => d.absDelta >= DEV_THRESHOLD).slice(0, 3)

  const picked = []
  top3.forEach(d => {
    const key = `${d.el}_${d.polarity}`
    const bank = _SYMPTOM_BANK[key] || []
    for (let i = 0; i < Math.min(PER_ELEM, bank.length); i++) {
      picked.push({
        id: `${key}_${i}`,
        text: bank[i],
        options: FREQ_OPTS,
        element: d.el,
        polarity: d.polarity,
        idealFreq: 3,   // 特征题理想答案是"经常"(3)
      })
    }
  })

  // 3. 用状态评估题补到 target 道
  const needMore = target - picked.length
  if (needMore > 0) {
    const shuffledStates = [..._STATE_BANK].sort(() => Math.random() - 0.5)
    for (let i = 0; i < Math.min(needMore, shuffledStates.length); i++) {
      const t = shuffledStates[i]
      picked.push({
        id: `state_${i}`,
        text: t,
        options: QUALITY_OPTS,   // 好/一般/差
        idealFreq: 2,            // 理想答案是"好"(2)
      })
    }
  }

  // 4. 打乱
  for (let i = picked.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [picked[i], picked[j]] = [picked[j], picked[i]]
  }

  return picked
}

/** v_innate 偏离 Top3（旧版，保留兼容） */
const deviationTop3 = computed(() => {
  const v = baziResult.value?.v_innate
  if (!v) return []
  return Object.entries(v)
    .map(([el, score]) => ({
      el, score,
      cn: ELEMENT_META[el]?.cn || el,
      emoji: ELEMENT_META[el]?.emoji || '?',
    }))
    .sort((a, b) => Math.abs(b.score - 20) - Math.abs(a.score - 20))
    .slice(0, 3)
    .map(it => ({
      ...it,
      polarity: it.score > 20 ? 'strong' : it.score < 20 ? 'weak' : 'balanced',
    }))
})

/** 体质分析返回的 top3 偏离（新版，来自后端 constitution/analysis） */
const top3Deviations = computed(() => {
  return constitutionData.value?.constitution?.top3_deviations || []
})

// ── Step 2 → 提交 onboarding ──
async function submitAll() {
  submitting.value = true
  try {
    const v = baziResult.value
    const onboardingBody = {
      nickname: form.nickname,
      nickname_alias: form.nickname_alias || null,
      gender: form.gender,
      height: form.height,
      weight: form.weight,
      birth_date: form.birth_date,
      birth_hour: form.birth_hour || null,
      birth_province: form.birth_province,
      birthplace: form.birth_city,
      living_province: form.living_province,
      living_city: form.living_city,
      same_as_birth: form.same_as_birth,
      longitude: birthCityLng.value,
      engine: v?.engine || 'spum_bazi',
      v_innate: v?.v_innate,
      bazi_result: v,
      constitution_data: constitutionData.value,   // 体质画像（含 LLM 大白话）
    }

    await casesApi.onboarding(onboardingBody)
    userStore.isOnboarded = true   // 修正：state 里是 camelCase isOnboarded，不是 snake_case
    // 关键：onboarding 里用户填了 nickname/身高/体重 → 全量刷新 userStore
    await userStore.fetchMe()
    storage.setOnboarded(true)
    console.log('[Onboarding] ✅ 初始化完成，跳转主页')
    router.push('/')
  } catch (e) {
    alert('初始化建档失败：' + (e.message || e))
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.onboarding { max-width: 720px; margin: 0 auto; }

/* 步骤条 */
.steps { display: flex; justify-content: center; gap: 0; margin-bottom: 28px; padding: 0 10px; }
.step { display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 1; position: relative; }
.step-num {
  width: 32px; height: 32px; border-radius: 50%;
  background: var(--qn-surface); border: 2px solid var(--qn-line);
  display: flex; align-items: center; justify-content: center;
  font-size: calc(13px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink-3);
  transition: all 0.2s;
}
.step.active .step-num { border-color: var(--qn-emerald); color: var(--qn-emerald); background: var(--qn-surface); }
.step.done .step-num { background: var(--qn-emerald); border-color: var(--qn-emerald); color: #fff; }
.step-label { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }
.step.active .step-label { color: var(--qn-emerald); font-weight: 500; }
.step.done .step-label { color: var(--qn-ink-2); }

/* 返回登录按钮 — 步骤条下方，卡片上方 */
.back-to-login {
  display: inline-flex; align-items: center; gap: 4px;
  margin: -8px 0 16px; padding: 6px 12px;
  background: none; border: none;
  color: var(--qn-emerald);
  font-size: calc(13px * var(--qn-fs-scale)); font-weight: 500;
  cursor: pointer;
  transition: color 0.15s, transform 0.15s, background 0.15s;
  border-radius: 20px;
}
.back-to-login:hover { color: var(--qn-emerald-light); background: rgba(var(--qn-emerald-rgb),0.08); }
.back-to-login:active { transform: translateX(-1px); }

/* ⚠️ .card 基础样式已统一到 App.vue 全局
   Questionnaire 独有：步骤条卡片更宽松 padding 28px */
.card { padding: 28px; }
.card h2 { font-size: calc(17px * var(--qn-fs-scale)); color: var(--qn-emerald); margin: 0 0 6px; font-weight: 600; letter-spacing: 0.5px; }
.step-desc { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 0 0 20px; line-height: 1.6; }

.form { display: flex; flex-direction: column; gap: 16px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field > span { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); font-weight: 500; }
.field em { color: #E57373; font-style: normal; }
.field input, .field select {
  padding: 9px 12px; border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm);
  font-size: calc(14px * var(--qn-fs-scale)); font-family: var(--qn-font-body); background: var(--qn-surface); color: var(--qn-ink);
  transition: border-color 0.15s;
}
.field input:focus, .field select:focus { outline: none; border-color: var(--qn-emerald); }
.field input::placeholder { color: var(--qn-ink-3); }
.field-full { grid-column: 1 / -1; }
.field-hint { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); line-height: 1.6; }

/* 推演摘要（五行偏离 Top3） */
.verify-summary {
  display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px;
  padding: 12px 14px; border-radius: 10px;
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.05), rgba(var(--qn-emerald-rgb),0.02));
  border: 1px solid rgba(var(--qn-emerald-rgb),0.12);
}
.vs-item {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 10px; border-radius: 20px;
  background: var(--qn-surface); border: 1px solid var(--qn-line);
  font-size: calc(12px * var(--qn-fs-scale));
}
.vs-emoji { font-size: calc(14px * var(--qn-fs-scale)); }
.vs-name { color: var(--qn-ink); font-weight: 500; }
.vs-score { font-family: var(--font-mono); font-weight: 600; font-size: calc(13px * var(--qn-fs-scale)); }
.vs-score.weak { color: #d4752a; }
.vs-score.strong { color: #2a8fd4; }
.vs-tag {
  font-size: calc(10px * var(--qn-fs-scale)); padding: 1px 6px; border-radius: 8px; font-weight: 500;
}
.vs-tag.weak { background: rgba(212,117,42,0.12); color: #d4752a; }
.vs-tag.strong { background: rgba(42,143,212,0.12); color: #2a8fd4; }

/* 验证题表单 */
.verify-form .field { gap: 10px; }
.verify-form .field > span:not(.radio-option) {
  display: flex; align-items: flex-start; gap: 6px; font-weight: 500; color: var(--qn-ink);
}
.q-num {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 22px; height: 22px; padding: 0 5px;
  background: var(--qn-emerald); color: #fff;
  border-radius: 11px; font-size: calc(11px * var(--qn-fs-scale)); font-weight: 600; flex-shrink: 0; margin-top: 1px;
}
.q-text { line-height: 1.55; }
.verify-form .radio-group {
  grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 4px;
}
.verify-form .radio-group.wider {
  grid-template-columns: repeat(3, 1fr);
}
.verify-form .radio-option {
  padding: 7px 8px; font-size: calc(13px * var(--qn-fs-scale)); justify-content: center; text-align: center;
}
.verify-form .radio-option input[type="radio"] { display: none; }
.verify-form .radio-option {
  border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm);
  cursor: pointer; transition: all 0.15s;
}
.verify-form .radio-option:has(input:checked) {
  border-color: var(--qn-emerald); background: rgba(var(--qn-emerald-rgb),0.08); color: var(--qn-emerald); font-weight: 500;
}

/* 级联选择器（省/市 两级联动） */
.cascader {
  display: grid; grid-template-columns: 1fr 2fr; gap: 8px;
}
.cascader select {
  padding: 9px 12px; border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm);
  font-size: calc(14px * var(--qn-fs-scale)); font-family: var(--qn-font-body); background: var(--qn-surface); color: var(--qn-ink);
  transition: border-color 0.15s;
}
.cascader select:focus { outline: none; border-color: var(--qn-emerald); }
.cascader select:disabled { background: #f9f9f6; color: var(--qn-ink-3); cursor: not-allowed; }
.city-lng { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-left: 2px; }

/* 常住地标签 + "与出生地相同"按钮 */
.living-label { display: flex; align-items: center; justify-content: space-between; }
.btn-same-as {
  font-size: calc(12px * var(--qn-fs-scale)); font-weight: normal;
  padding: 2px 10px; border-radius: 14px; border: 1px solid var(--qn-line);
  background: transparent; color: var(--qn-ink-2);
  cursor: pointer; transition: all 0.15s; font-family: var(--qn-font-body);
}
.btn-same-as:hover { border-color: var(--qn-emerald); color: var(--qn-emerald); }
.btn-same-as.active { background: var(--qn-emerald); color: #fff; border-color: var(--qn-emerald); }

/* 统一日期选择器（阳历/阴历共用） */
.date-picker {
  display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px;
}
.date-picker select {
  padding: 9px 12px; border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm);
  font-size: calc(14px * var(--qn-fs-scale)); font-family: var(--qn-font-body); background: var(--qn-surface); color: var(--qn-ink);
}
.date-picker select:focus { outline: none; border-color: var(--qn-emerald); }

/* 日主标签颜色（五形对应） */
.dm-tag {
  font-style: normal; font-size: calc(11px * var(--qn-fs-scale)); padding: 1px 6px; border-radius: 10px;
  margin-left: 4px; font-weight: 500;
}
.dm-wood  { background: #e6f4e6; color: #2d7a3a; }
.dm-fire  { background: #fde8e0; color: #c54a1e; }
.dm-earth { background: #fdf5e0; color: #9a7b1c; }
.dm-metal { background: #e8eaed; color: #5a6270; }
.dm-water { background: #e0f0f8; color: #1f6a9a; }

/* 阳历/阴历切换 */
.date-toggle { display: inline-flex; align-items: center; gap: 3px; font-size: calc(12px * var(--qn-fs-scale)); font-weight: normal; margin-left: 8px; cursor: pointer; color: var(--qn-ink-2); }
.date-toggle input { margin: 0; accent-color: var(--qn-emerald); }
.date-toggle span { padding: 1px 6px; border-radius: 4px; }
.date-toggle:has(input:checked) span { background: var(--qingnang-emerald, #5B8A5F); color: #fff; }

/* 八字面板 */
.bazi-panel {
  background: var(--qingnang-paper, #F4F6F4);
  border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm);
  padding: 16px 20px; margin-bottom: 20px;
}
.pillar-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 10px; }
.pillar { text-align: center; }
.pillar-label { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-bottom: 2px; letter-spacing: 0.5px; }
.pillar-value {
  font-size: calc(20px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-emerald);
  font-family: var(--font-mono, monospace); letter-spacing: 2px;
}
.meta-row { display: flex; flex-wrap: wrap; gap: 16px; font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-3); }

/* 雷达图 + 弱项提示 */
.radar-wrap { margin: 0 auto; width: 100%; max-width: 360px; }
.weakness-banner {
  background: var(--qn-banner-warn-bg); border: 1px solid var(--qn-banner-warn-bd); border-radius: var(--qn-r-sm);
  padding: 10px 14px; font-size: calc(12px * var(--qn-fs-scale)); margin-top: 16px;
  display: flex; gap: 10px; line-height: 1.6;
}
.wb-label { font-weight: 600; color: #F57F17; white-space: nowrap; }
.wb-content { color: #5D4037; }

/* 单选组 */
.radio-group { display: flex; flex-wrap: wrap; gap: 8px; }
.radio-option {
  display: flex; align-items: center; gap: 5px;
  padding: 6px 14px; border-radius: var(--qn-r-sm);
  border: 1px solid var(--qn-line); font-size: calc(13px * var(--qn-fs-scale)); cursor: pointer;
  transition: all 0.15s;
}
.radio-option:hover { border-color: var(--qn-emerald); }
.radio-option input { accent-color: var(--qn-emerald); }

/* 按钮 */
.btn {
  padding: 9px 22px; border-radius: var(--qn-r-sm); font-size: calc(14px * var(--qn-fs-scale)); font-weight: 500;
  cursor: pointer; transition: all 0.15s; font-family: var(--qn-font-body);
}
.btn-primary { background: var(--qn-emerald); color: #fff; border: none; }
.btn-primary:hover:not(:disabled) { background: var(--qn-emerald-light); box-shadow: 0 2px 6px rgba(var(--qn-emerald-rgb),0.2); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost { background: transparent; color: var(--qn-emerald); border: 1px solid var(--qn-emerald); }
.btn-ghost:hover { background: var(--qn-paper); box-shadow: none; }

.form-actions { display: flex; justify-content: space-between; margin-top: 12px; }


/* ═══ Step 2: 体质推理报告 ═══ */
/* 体质总纲 hero — 病历级标签 */
.constitution-hero {
  text-align: center; padding: 18px 20px; margin-bottom: 20px;
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.08), rgba(var(--qn-emerald-rgb),0.02));
  border: 1px solid rgba(var(--qn-emerald-rgb),0.25); border-radius: 12px;
}
.ch-bazi {
  font-family: var(--font-mono, monospace); font-size: calc(12px * var(--qn-fs-scale));
  color: var(--qn-ink-3); letter-spacing: 1px; margin-bottom: 8px;
}
.ch-summary {
  font-size: calc(20px * var(--qn-fs-scale)); font-weight: 700;
  color: var(--qn-emerald); letter-spacing: 2px;
}

.report-section { margin: 0 0 28px; }
.report-section h3 {
  font-size: calc(14px * var(--qn-fs-scale)); font-weight: 600;
  color: var(--qn-emerald); margin: 0 0 14px; padding-bottom: 6px;
  border-bottom: 1px solid var(--qn-line);
}

/* 五行基底 */
.radar-row { display: flex; gap: 20px; }
.radar-mini { flex: 2; display: flex; flex-direction: column; gap: 8px; }
.radar-bar { display: grid; grid-template-columns: 48px 1fr 30px; gap: 8px; align-items: center; }
.rb-label { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); font-weight: 500; }
.rb-track { height: 8px; background: var(--qn-paper); border-radius: 4px; overflow: hidden; }
.rb-fill { height: 100%; background: var(--qn-emerald); border-radius: 4px; transition: width 0.4s; }
.rb-fill.weak { background: #d4752a; }
.rb-fill.strong { background: #c54a1e; }
.rb-score { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); text-align: right; font-family: var(--font-mono, monospace); }

.top3-panel { flex: 1; background: var(--qn-paper); border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm); padding: 12px; }
.top3-title { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-bottom: 8px; letter-spacing: 1px; }
.top3-item { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; font-size: calc(12px * var(--qn-fs-scale)); }
.t3-el { color: var(--qn-ink); font-weight: 500; }
.t3-dir { font-size: calc(10px * var(--qn-fs-scale)); padding: 1px 6px; border-radius: 8px; }
.t3-dir.weak { background: rgba(212,117,42,0.12); color: #d4752a; }
.t3-dir.strong { background: rgba(197,74,30,0.12); color: #c54a1e; }
.t3-dir.balanced { background: rgba(var(--qn-emerald-rgb),0.1); color: var(--qn-emerald); }
.t3-pts { font-family: var(--font-mono, monospace); font-weight: 600; }
.weak .t3-pts { color: #d4752a; }
.strong .t3-pts { color: #c54a1e; }

/* 体质解读 */
.dm-highlight {
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.08), rgba(var(--qn-emerald-rgb),0.02));
  border: 1px solid var(--qn-emerald);
  border-radius: var(--qn-r-sm); padding: 12px 16px; margin-bottom: 14px;
  font-size: calc(14px * var(--qn-fs-scale)); font-weight: 500; color: var(--qn-emerald);
}
.dm-note { color: var(--qn-ink-2); font-weight: normal; margin-left: 8px; }

.constitution-tags { display: flex; flex-wrap: wrap; gap: 10px; }
.c-tag {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 14px; border-radius: 20px; border: 1px solid var(--qn-line);
  font-size: calc(13px * var(--qn-fs-scale));
  transition: all .2s;
}
.c-tag .ct-badge {
  font-size: calc(10px * var(--qn-fs-scale));
  padding: 2px 8px; border-radius: 10px;
  background: var(--qn-line); color: var(--qn-ink-2);
  font-weight: 500;
}
/* 亮点标签 — 绿色正向 */
.c-tag.strength { border-color: rgba(var(--qn-emerald-rgb),0.4); background: rgba(var(--qn-emerald-rgb),0.08); }
.c-tag.strength .ct-text { color: var(--qn-emerald); }
.c-tag.strength .ct-badge { background: var(--qn-emerald); color: #fff; }
/* 观察点标签 — 中性偏暖 */
.c-tag.weak { border-color: rgba(212,117,42,0.4); background: rgba(212,117,42,0.06); }
.c-tag.weak .ct-text { color: #b85e1a; }
.c-tag.weak .ct-badge { background: rgba(212,117,42,0.2); color: #a06020; }
.c-tag.strong { border-color: rgba(197,74,30,0.3); background: rgba(197,74,30,0.05); }
.c-tag.strong .ct-text { color: #7a4a2a; }
.c-tag.strong .ct-badge { background: rgba(197,74,30,0.15); color: #8a3a18; }
.c-tag.balanced { border-color: rgba(var(--qn-emerald-rgb),0.25); background: rgba(var(--qn-emerald-rgb),0.04); }

/* ═══════════════ 病历式体质画像样式 ═══════════════ */
.medical-report { padding: 28px 32px 24px; }
.radar-anchor {
  display: grid; grid-template-columns: repeat(5, 1fr);
  gap: 12px; margin: 16px 0 20px; padding: 14px 16px;
  background: var(--qn-paper); border: 1px solid var(--qn-line);
  border-radius: var(--qn-r-sm);
}
.radar-bar-mini { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.r-label { font-size: calc(12px * var(--qn-fs-scale)); color: var(--qn-ink-2); }
.r-track { width: 100%; height: 6px; background: var(--qn-line); border-radius: 3px; overflow: hidden; }
.r-fill { height: 100%; background: var(--qn-emerald); border-radius: 3px; transition: width .6s; }
.r-score { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); font-variant-numeric: tabular-nums; }

.m-section {
  margin: 18px 0 22px; padding: 16px 20px;
  background: var(--qn-paper);
  border: 1px solid var(--qn-line);
  border-left: 3px solid var(--qn-emerald);
  border-radius: var(--qn-r-sm);
}
.m-section-highlight {
  border-left-color: var(--qn-emerald);
  background: linear-gradient(135deg, rgba(var(--qn-emerald-rgb),0.04), rgba(var(--qn-emerald-rgb),0.01));
}
.m-section h4 {
  margin: 0 0 12px; font-size: calc(15px * var(--qn-fs-scale));
  font-weight: 600; color: var(--qn-ink);
  padding-bottom: 8px; border-bottom: 1px dashed var(--qn-line);
}
.m-body { font-size: calc(13.5px * var(--qn-fs-scale)); line-height: 1.85; color: var(--qn-ink); }
.m-body p { margin: 0 0 10px; }
.m-body p:last-child { margin-bottom: 0; }
.m-body strong { color: var(--qn-emerald); font-weight: 600; }
.m-body ul { margin: 6px 0; padding-left: 22px; }
.m-body li { margin: 3px 0; }
.m-body li.li-dash { list-style: none; }
.m-body table {
  width: 100%; border-collapse: collapse; margin: 10px 0;
  font-size: calc(12.5px * var(--qn-fs-scale));
}
.m-body th, .m-body td {
  border: 1px solid var(--qn-line); padding: 6px 10px;
  text-align: left;
}
.m-body th { background: rgba(var(--qn-emerald-rgb),0.08); font-weight: 600; }
.m-body h3, .m-body h4, .m-body h5 { margin: 12px 0 6px; font-weight: 600; color: var(--qn-ink); }
.m-body h3 { font-size: calc(14px * var(--qn-fs-scale)); }
.m-body h4 { font-size: calc(13.5px * var(--qn-fs-scale)); color: var(--qn-emerald); }
.m-body h5 { font-size: calc(12.5px * var(--qn-fs-scale)); color: var(--qn-ink-2); }
.m-body hr { border: none; border-top: 1px dashed var(--qn-line); margin: 12px 0; }
.m-body code {
  background: rgba(var(--qn-emerald-rgb),0.08); padding: 1px 6px;
  border-radius: 3px; font-size: calc(12px * var(--qn-fs-scale));
}
.m-fallback { color: var(--qn-ink-3); font-style: italic; padding: 20px; text-align: center; }
.age-risks { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.age-risk-card {
  background: var(--qn-paper); border: 1px solid var(--qn-line);
  border-radius: var(--qn-r-sm); padding: 12px 14px;
}
.ar-body { margin-top: 6px; }
.ar-llm {
  font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink);
  line-height: 1.65; letter-spacing: 0.3px;
}
.ar-header { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 8px; }
.ar-range { font-size: calc(13px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink); }
.ar-label { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); }
.ar-dayun { display: flex; gap: 4px; flex-wrap: wrap; }
.dayun-pill { font-size: calc(10px * var(--qn-fs-scale)); padding: 1px 6px; border-radius: 8px; background: rgba(var(--qn-emerald-rgb),0.1); color: var(--qn-emerald); }
.ar-items { display: flex; flex-wrap: wrap; gap: 6px; }
.ar-item {
  font-size: calc(12px * var(--qn-fs-scale)); padding: 3px 8px; border-radius: 10px;
  background: rgba(197,74,30,0.08); color: #a03a18;
}
.ar-items.balanced { color: var(--qn-ink-3); font-size: calc(12px * var(--qn-fs-scale)); font-style: italic; }

.report-actions { display: flex; justify-content: space-between; margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--qn-line); }
/* 响应式 — 归并到 480px 档位（原 600px） */
@media (max-width: 480px) {
  .form-grid { grid-template-columns: 1fr; }
  .pillar-row { grid-template-columns: repeat(2, 1fr); }
  .steps { flex-wrap: wrap; }
  .cascader { grid-template-columns: 1fr; }
  .radar-row { flex-direction: column; }
}</style>

