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
              <select v-model.number="form.lunar_year">
                <option disabled :value="null">年</option>
                <option v-for="y in LUNAR_YEARS" :key="y" :value="y">{{ y }}年</option>
              </select>
              <select v-model.number="form.lunar_month">
                <option disabled :value="null">月</option>
                <option v-for="m in 12" :key="m" :value="m">{{ m }}月</option>
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
            <span class="field-hint" v-if="form.birthCityLng">
              真太阳时经度修正：当前 {{ form.birthCityLng.toFixed(2) }}°E（北京时间以 120°E 为基准，{{ (form.birthCityLng - 120).toFixed(2) }}° → {{ ((form.birthCityLng - 120) * 4).toFixed(1) }} 分钟时差）
            </span>

          </label>
        </div>
        <button class="btn btn-primary" @click="doOnboardAndInquiry" :disabled="calculating || !canCalcBazi">
          <span v-if="calculating">🧠 推演中…</span>
          <span v-else>下一步</span>
        </button>
      </div>
    </div>

    <!-- ═══ Step 2: 体质倾向验证（基于八字 v_innate 规则化生成） ═══ -->
    <div v-else-if="currentStep === 2" class="card">
      <h2>体质倾向验证</h2>
      <p class="step-desc">根据你的先天八字推演，青囊列出了以下体质特征。请勾选你平时最常有的感受——这是在帮我们校验推演的准确度。</p>

      <!-- 推演摘要 -->
      <div class="verify-summary" v-if="baziResult?.v_innate">
        <div class="vs-item" v-for="it in deviationTop3" :key="it.el">
          <span class="vs-emoji">{{ it.emoji }}</span>
          <span class="vs-name">{{ it.cn }}</span>
          <span class="vs-score" :class="it.polarity">{{ it.score.toFixed(0) }}</span>
          <span class="vs-tag" :class="it.polarity">{{ it.polarity === 'weak' ? '偏弱' : '偏旺' }}</span>
        </div>
      </div>

      <form v-if="verifyQuestions.length" class="form verify-form" @submit.prevent="submitAll">
        <label v-for="(q, idx) in verifyQuestions" :key="q.id" class="field">
          <span class="q-num">{{ idx + 1 }}.</span>
          <span class="q-text">{{ q.text }}</span>
          <div class="radio-group" :class="{ wider: q.options.length <= 3 }">
            <label v-for="opt in q.options" :key="opt.value" class="radio-option">
              <input type="radio" v-model="form.answers[q.id]" :value="opt.value" />
              <span>{{ opt.label }}</span>
            </label>
          </div>
        </label>

        <div class="form-actions">
          <button type="button" class="btn btn-ghost" @click="currentStep = 1">← 修改基础信息</button>
          <button type="submit" class="btn btn-primary" :disabled="submitting">
            {{ submitting ? '✓ 正在创建数字模型…' : '✓ 确认创建我的数字模型' }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { assistant as assistantApi, auth as authApi, cases as casesApi } from '../api/client'
import { useUserStore } from '../stores/user'
import { CHINA_PROVINCES, CHINA_CITIES } from '../constants/china-cities.js'

const router = useRouter()
const userStore = useUserStore()

// ── 状态 ──
const currentStep = ref(1)           // 1: 基础信息 → 2: 体质验证
const calculating = ref(false)
const submitting = ref(false)
const baziResult = ref(null)         // 八字推演结果
const verifyQuestions = ref([])       // 规则化生成的验证题

const steps = [
  { idx: 1, title: '基础信息' },
  { idx: 2, title: '体质验证' },
]

const PROVINCES = CHINA_PROVINCES

// ── 阳历/阴历年份常量 ──
const SOLAR_YEARS = Array.from({ length: 120 }, (_, i) => 2025 - i)   // 1906~2025
const LUNAR_YEARS = Array.from({ length: 120 }, (_, i) => 2025 - i)   // 同范围
const LUNAR_DAYS_BIG = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30]
const LUNAR_DAYS_SMALL = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29]

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
  answers: {},
  // 选择器中间态（不直接提交，watch 拼 birth_date）
  solar_year: null,
  solar_month: null,
  solar_day: null,
  lunar_year: null,
  lunar_month: null,
  lunar_day: null,
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

// ── 阳/阴历日选择：根据月份大小切换 28-30 天 ──
const solarDayOptions = computed(() => {
  const big = [1,3,5,7,8,10,12]
  if (form.solar_month && big.includes(form.solar_month)) return LUNAR_DAYS_BIG       // 31 天
  if (form.solar_month === 2) return [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28]
  return [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30]
})
const lunarDayOptions = computed(() => {
  const big = [1,3,5,7,8,10,12]
  if (form.lunar_month && big.includes(form.lunar_month)) return LUNAR_DAYS_BIG
  return LUNAR_DAYS_SMALL
})

// ── 统一 watch：6 个 select → 自动拼 birth_date ──
watch(
  () => [
    form.birth_date_type,
    form.solar_year, form.solar_month, form.solar_day,
    form.lunar_year, form.lunar_month, form.lunar_day,
  ],
  ([type, sy, sm, sd, ly, lm, ld]) => {
    let y, m, d
    if (type === 'solar') { y = sy; m = sm; d = sd }
    else { y = ly; m = lm; d = ld }
    if (y && m && d) {
      form.birth_date = `${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`
    } else {
      form.birth_date = ''
    }
  },
  { immediate: true }
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

// ── Step 1 → 推演八字 + PATCH /me + 规则化生成验证题 ──
async function doOnboardAndInquiry() {
  if (!canCalcBazi.value) return
  calculating.value = true
  try {
    const resp = await assistantApi.bazi(
      form.birth_date, form.birth_hour || null,
      form.birth_city, form.birth_date_type,
    )
    baziResult.value = resp.data || resp

    // PATCH 用户档案 → 同时同步进 userStore + localStorage（立即生效）
    await authApi.patchMe({
      nickname: form.nickname, gender: form.gender,
      height: form.height, weight: form.weight,
      birth_date: form.birth_date, birth_hour: form.birth_hour || null,
    })
    // 内存态 + localStorage 双写，确保刷新也不丢
    userStore.nickname = form.nickname
    const saved = JSON.parse(localStorage.getItem('qingnang_user') || '{}')
    saved.nickname = form.nickname
    localStorage.setItem('qingnang_user', JSON.stringify(saved))

    // 规则化生成验证题（不调 AI 引擎，纯前端规则）
    verifyQuestions.value = buildVerifyQuestions(baziResult.value?.v_innate)

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

/** v_innate 偏离 Top3（用于推演摘要展示） */
const deviationTop3 = computed(() => {
  const v = baziResult.value?.v_innate
  if (!v) return []
  return Object.entries(v)
    .map(([el, score]) => ({
      el, score,
      cn: _ELEMENT_META[el]?.cn || el,
      emoji: _ELEMENT_META[el]?.emoji || '?',
      polarity: score < 50 ? 'weak' : 'strong',
      absDelta: Math.abs(score - 50),
    }))
    .sort((a, b) => b.absDelta - a.absDelta)
    .slice(0, 3)
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
      longitude: birthCityLng.value,
      engine: v?.engine || 'spum_bazi',
      v_innate: v?.v_innate,
      bazi_result: v,
      verify_questions: verifyQuestions.value,   // 规则化生成的题（含 element/polarity）
      verify_answers: form.answers,              // 用户的频率选择 0-3
    }

    await casesApi.onboarding(onboardingBody)
    userStore.isOnboarded = true   // 修正：state 里是 camelCase isOnboarded，不是 snake_case
    // 关键：onboarding 里用户填了 nickname/身高/体重 → 全量刷新 userStore
    await userStore.fetchMe()
    localStorage.setItem('qingnang_onboarded', 'true')
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
  background: #fff; border: 2px solid var(--ink-line);
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 600; color: var(--ink-tertiary);
  transition: all 0.2s;
}
.step.active .step-num { border-color: var(--qingnang-emerald); color: var(--qingnang-emerald); background: #fff; }
.step.done .step-num { background: var(--qingnang-emerald); border-color: var(--qingnang-emerald); color: #fff; }
.step-label { font-size: 12px; color: var(--ink-tertiary); }
.step.active .step-label { color: var(--qingnang-emerald); font-weight: 500; }
.step.done .step-label { color: var(--ink-secondary); }

.card {
  background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-md);
  padding: 28px; box-shadow: var(--shadow-card);
}
.card h2 { font-size: 17px; color: var(--qingnang-emerald); margin: 0 0 6px; font-weight: 600; letter-spacing: 0.5px; }
.step-desc { font-size: 13px; color: var(--ink-tertiary); margin: 0 0 20px; line-height: 1.6; }

.form { display: flex; flex-direction: column; gap: 16px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field > span { font-size: 13px; color: var(--ink-secondary); font-weight: 500; }
.field em { color: #E57373; font-style: normal; }
.field input, .field select {
  padding: 9px 12px; border: 1px solid var(--ink-line); border-radius: var(--radius-sm);
  font-size: 14px; font-family: var(--font-body); background: #fff; color: var(--ink-primary);
  transition: border-color 0.15s;
}
.field input:focus, .field select:focus { outline: none; border-color: var(--qingnang-emerald); }
.field input::placeholder { color: var(--ink-tertiary); }
.field-full { grid-column: 1 / -1; }
.field-hint { font-size: 11px; color: var(--ink-tertiary); line-height: 1.6; }

/* 推演摘要（五行偏离 Top3） */
.verify-summary {
  display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px;
  padding: 12px 14px; border-radius: 10px;
  background: linear-gradient(135deg, rgba(23,83,76,0.05), rgba(23,83,76,0.02));
  border: 1px solid rgba(23,83,76,0.12);
}
.vs-item {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 10px; border-radius: 20px;
  background: #fff; border: 1px solid var(--ink-line);
  font-size: 12px;
}
.vs-emoji { font-size: 14px; }
.vs-name { color: var(--ink-primary); font-weight: 500; }
.vs-score { font-family: var(--font-mono); font-weight: 600; font-size: 13px; }
.vs-score.weak { color: #d4752a; }
.vs-score.strong { color: #2a8fd4; }
.vs-tag {
  font-size: 10px; padding: 1px 6px; border-radius: 8px; font-weight: 500;
}
.vs-tag.weak { background: rgba(212,117,42,0.12); color: #d4752a; }
.vs-tag.strong { background: rgba(42,143,212,0.12); color: #2a8fd4; }

/* 验证题表单 */
.verify-form .field { gap: 10px; }
.verify-form .field > span:not(.radio-option) {
  display: flex; align-items: flex-start; gap: 6px; font-weight: 500; color: var(--ink-primary);
}
.q-num {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 22px; height: 22px; padding: 0 5px;
  background: var(--qingnang-emerald); color: #fff;
  border-radius: 11px; font-size: 11px; font-weight: 600; flex-shrink: 0; margin-top: 1px;
}
.q-text { line-height: 1.55; }
.verify-form .radio-group {
  grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 4px;
}
.verify-form .radio-group.wider {
  grid-template-columns: repeat(3, 1fr);
}
.verify-form .radio-option {
  padding: 7px 8px; font-size: 13px; justify-content: center; text-align: center;
}
.verify-form .radio-option input[type="radio"] { display: none; }
.verify-form .radio-option {
  border: 1px solid var(--ink-line); border-radius: var(--radius-sm);
  cursor: pointer; transition: all 0.15s;
}
.verify-form .radio-option:has(input:checked) {
  border-color: var(--qingnang-emerald); background: rgba(23,83,76,0.08); color: var(--qingnang-emerald); font-weight: 500;
}

/* 级联选择器（省/市 两级联动） */
.cascader {
  display: grid; grid-template-columns: 1fr 2fr; gap: 8px;
}
.cascader select {
  padding: 9px 12px; border: 1px solid var(--ink-line); border-radius: var(--radius-sm);
  font-size: 14px; font-family: var(--font-body); background: #fff; color: var(--ink-primary);
  transition: border-color 0.15s;
}
.cascader select:focus { outline: none; border-color: var(--qingnang-emerald); }
.cascader select:disabled { background: #f9f9f6; color: var(--ink-tertiary); cursor: not-allowed; }
.city-lng { font-size: 11px; color: var(--ink-tertiary); margin-left: 2px; }

/* 统一日期选择器（阳历/阴历共用） */
.date-picker {
  display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px;
}
.date-picker select {
  padding: 9px 12px; border: 1px solid var(--ink-line); border-radius: var(--radius-sm);
  font-size: 14px; font-family: var(--font-body); background: #fff; color: var(--ink-primary);
}
.date-picker select:focus { outline: none; border-color: var(--qingnang-emerald); }

/* 日主标签颜色（五形对应） */
.dm-tag {
  font-style: normal; font-size: 11px; padding: 1px 6px; border-radius: 10px;
  margin-left: 4px; font-weight: 500;
}
.dm-wood  { background: #e6f4e6; color: #2d7a3a; }
.dm-fire  { background: #fde8e0; color: #c54a1e; }
.dm-earth { background: #fdf5e0; color: #9a7b1c; }
.dm-metal { background: #e8eaed; color: #5a6270; }
.dm-water { background: #e0f0f8; color: #1f6a9a; }

/* 阳历/阴历切换 */
.date-toggle { display: inline-flex; align-items: center; gap: 3px; font-size: 12px; font-weight: normal; margin-left: 8px; cursor: pointer; color: var(--ink-secondary); }
.date-toggle input { margin: 0; accent-color: var(--qingnang-emerald); }
.date-toggle span { padding: 1px 6px; border-radius: 4px; }
.date-toggle:has(input:checked) span { background: var(--qingnang-emerald, #5B8A5F); color: #fff; }

/* 八字面板 */
.bazi-panel {
  background: var(--qingnang-paper, #F4F6F4);
  border: 1px solid var(--ink-line); border-radius: var(--radius-sm);
  padding: 16px 20px; margin-bottom: 20px;
}
.pillar-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 10px; }
.pillar { text-align: center; }
.pillar-label { font-size: 11px; color: var(--ink-tertiary); margin-bottom: 2px; letter-spacing: 0.5px; }
.pillar-value {
  font-size: 20px; font-weight: 600; color: var(--qingnang-emerald);
  font-family: var(--font-mono, monospace); letter-spacing: 2px;
}
.meta-row { display: flex; flex-wrap: wrap; gap: 16px; font-size: 12px; color: var(--ink-tertiary); }

/* 雷达图 + 弱项提示 */
.radar-wrap { margin: 0 auto; width: 100%; max-width: 360px; }
.weakness-banner {
  background: #FFF8E1; border: 1px solid #FFE082; border-radius: var(--radius-sm);
  padding: 10px 14px; font-size: 12px; margin-top: 16px;
  display: flex; gap: 10px; line-height: 1.6;
}
.wb-label { font-weight: 600; color: #F57F17; white-space: nowrap; }
.wb-content { color: #5D4037; }

/* 单选组 */
.radio-group { display: flex; flex-wrap: wrap; gap: 8px; }
.radio-option {
  display: flex; align-items: center; gap: 5px;
  padding: 6px 14px; border-radius: var(--radius-sm);
  border: 1px solid var(--ink-line); font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.radio-option:hover { border-color: var(--qingnang-emerald); }
.radio-option input { accent-color: var(--qingnang-emerald); }

/* 按钮 */
.btn {
  padding: 9px 22px; border-radius: var(--radius-sm); font-size: 14px; font-weight: 500;
  cursor: pointer; transition: all 0.15s; font-family: var(--font-body);
}
.btn-primary { background: var(--qingnang-emerald); color: #fff; border: none; }
.btn-primary:hover:not(:disabled) { background: var(--qingnang-emerald-light); box-shadow: 0 2px 6px rgba(26,77,69,0.2); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost { background: transparent; color: var(--qingnang-emerald); border: 1px solid var(--qingnang-emerald); }
.btn-ghost:hover { background: var(--qingnang-paper); box-shadow: none; }

.form-actions { display: flex; justify-content: space-between; margin-top: 12px; }

/* 响应式 */
@media (max-width: 600px) {
  .form-grid { grid-template-columns: 1fr; }
  .pillar-row { grid-template-columns: repeat(2, 1fr); }
  .steps { flex-wrap: wrap; }
  .cascader { grid-template-columns: 1fr; }
}
</style>
