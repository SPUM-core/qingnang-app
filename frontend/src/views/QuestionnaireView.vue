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

    <!-- ═══ Step 1: 基础信息 → 推演先天八字 ═══ -->
    <div v-if="currentStep === 1" class="card">
      <h2>先让青囊认识你</h2>
      <p class="step-desc">你的出生时刻蕴含先天节律，青囊会据此推导你的五形基底。</p>

      <div class="form">
        <div class="form-grid">
          <label class="field">
            <span>怎么称呼你 <em>*</em></span>
            <input v-model="form.nickname" placeholder="如：胡运涛" />
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
            <input v-if="form.birth_date_type === 'solar'" v-model="form.birth_date" type="date" />
            <input v-else v-model="form.birth_date" placeholder="阴历 YYYY-MM-DD（如 1986-06-27）" />
            <span v-if="form.birth_date_type === 'lunar'" class="field-hint">青囊会将你的阴历生日换算为真太阳时对应的阳历，再据此排八字</span>
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
          <label class="field field-full">
            <span>出生地 <em>*</em></span>
            <select v-model="form.birthplace">
              <option disabled value="">请选择你出生的城市</option>
              <option v-for="c in CITIES" :key="c" :value="c">{{ c }}</option>
            </select>
            <span class="field-hint">用于真太阳时经度修正（广州 113.26°E / 北京 116.40°E / 上海 121.47°E …）</span>
          </label>
        </div>
        <button class="btn btn-primary" @click="calcBazi" :disabled="calculating || !canCalcBazi">
          <span v-if="calculating">🧠 青檬引擎推演中…（约 5s）</span>
          <span v-else>✨ 推演我的先天基底</span>
        </button>
      </div>
    </div>

    <!-- ═══ Step 2: 先天画像预览 ═══ -->
    <div v-else-if="currentStep === 2 && baziResult" class="card">
      <h2>你的先天五形基底</h2>
      <p class="step-desc">以下画像完全由你的出生时刻通过 SPUM 真太阳时推演得出，是后续所有调理分析的锚点。</p>

      <!-- 八字四柱 + 真太阳时 -->
      <div class="bazi-panel">
        <div class="pillar-row">
          <div v-for="(p, i) in baziResult.pillars" :key="i" class="pillar">
            <div class="pillar-label">{{ pillarLabels[i] }}</div>
            <div class="pillar-value">{{ p }}</div>
          </div>
        </div>
        <div class="meta-row">
          <span>农历：{{ baziResult.lunar || '—' }}</span>
          <span v-if="baziResult.true_solar_time">真太阳时：{{ baziResult.true_solar_time }}</span>
          <span v-if="baziResult.engine">引擎：{{ baziResult.engine }}</span>
        </div>
      </div>

      <!-- 五形雷达图 -->
      <div class="radar-wrap">
        <RadarChart :vBase="baziResult.v_innate" height="280px" />
      </div>

      <!-- 弱项高亮 -->
      <div class="weakness-banner">
        <span class="wb-label">先天弱项提示</span>
        <span class="wb-content">{{ weaknessAdvice }}</span>
      </div>

      <div class="form-actions">
        <button class="btn btn-ghost" @click="currentStep = 1">← 修改出生信息</button>
        <button class="btn btn-primary" @click="nextToQuestionnaire">✓ 确认这个画像，继续问诊</button>
      </div>
    </div>

    <!-- ═══ Step 3: 问诊题（基于弱项动态生成） ═══ -->
    <div v-else-if="currentStep === 3" class="card">
      <h2>当前身体状态</h2>
      <p class="step-desc">这些问题将作为你的第一次生活观测向量，青囊会用它和你的先天基底做对比，识别漂移趋势。</p>

      <form class="form" @submit.prevent="submitAll">
        <label v-for="q in questions" :key="q.key" class="field">
          <span>{{ q.label }}</span>
          <div class="radio-group">
            <label v-for="opt in q.options" :key="opt" class="radio-option">
              <input type="radio" v-model="form.answers[q.key]" :value="opt" />
              <span>{{ opt }}</span>
            </label>
          </div>
        </label>

        <div class="form-actions">
          <button type="button" class="btn btn-ghost" @click="currentStep = 2">← 回到画像</button>
          <button type="submit" class="btn btn-primary" :disabled="submitting">
            {{ submitting ? '✓ 正在创建数字模型…' : '✓ 确认创建我的数字模型' }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { assistant as assistantApi, cases as casesApi } from '../api/client'
import { useUserStore } from '../stores/user'
import RadarChart from '../components/charts/RadarChart.vue'

const router = useRouter()
const userStore = useUserStore()

// ── 状态 ──
const currentStep = ref(1)
const calculating = ref(false)
const submitting = ref(false)
const baziResult = ref(null)  // 后端返回的完整八字推演结果

const steps = [
  { idx: 1, title: '基础信息' },
  { idx: 2, title: '先天画像' },
  { idx: 3, title: '问诊确认' },
]

const pillarLabels = ['年柱', '月柱', '日柱', '时柱']

// ── 城市列表（精简覆盖主要城市） ──
const CITIES = [
  '北京', '天津', '上海', '重庆',
  '石家庄', '太原', '呼和浩特',
  '沈阳', '大连', '长春', '哈尔滨',
  '南京', '苏州', '杭州', '宁波',
  '合肥', '福州', '厦门',
  '南昌', '济南', '青岛',
  '郑州', '武汉', '长沙',
  '广州', '深圳', '南宁', '海口',
  '成都', '贵阳', '昆明',
  '拉萨', '西安', '兰州', '西宁',
  '银川', '乌鲁木齐',
  '香港', '澳门', '台北',
]

const form = reactive({
  nickname: '',
  gender: '',
  birth_date: '',
  birth_date_type: 'solar',   // 'solar' (阳历) | 'lunar' (阴历)
  birth_hour: '',
  birthplace: '',
  answers: {},
})

// ── Step 1 校验 ──
const canCalcBazi = computed(() => {
  return form.nickname.trim() && form.gender && form.birth_date && form.birthplace
})

// ── 弱项提示 ──
const weaknessAdvice = computed(() => {
  if (!baziResult.value?.v_innate) return ''
  const v = baziResult.value.v_innate
  const weak = []
  if (v.water < 40) weak.push('💧 水形偏弱：注意作息/保暖，忌熬夜')
  if (v.fire < 40) weak.push('🔥 火形偏弱：注意防寒/温补，忌寒凉')
  if (v.earth < 40) weak.push('🏭 土形偏弱：注意饮食/脾胃，忌生冷')
  if (v.metal < 40) weak.push('⚙️ 金形偏弱：注意皮肤/呼吸，忌干燥')
  if (v.wood < 40) weak.push('🌲 木形偏弱：注意情绪/疏泄，忌压抑')
  return weak.join(' · ') || '五形较均衡，继续保持'
})

// ── 问诊题（基于弱项动态生成） ──
const questions = computed(() => {
  const base = [
    { key: 'fatigue', label: '近期整体精力感受', options: ['充沛', '一般', '易疲乏'] },
    { key: 'sleep', label: '睡眠情况', options: ['好', '一般', '眠浅/难入睡'] },
  ]
  if (!baziResult.value?.v_innate) return base
  const v = baziResult.value.v_innate
  const extra = []
  if (v.earth < 40) {
    extra.push({ key: 'appetite', label: '食欲/消化', options: ['好', '一般', '食欲不振/腹胀'] })
    extra.push({ key: 'bowel', label: '二便情况', options: ['正常', '偏稀/黏', '偏干'] })
  }
  if (v.water < 40) {
    extra.push({ key: 'cold', label: '怕冷/腰膝', options: ['不怕', '偶有', '明显怕冷/腰膝酸'] })
  }
  if (v.fire < 40) {
    extra.push({ key: 'heart', label: '心悸/手心', options: ['无', '偶有', '明显'] })
  }
  if (v.wood < 40) {
    extra.push({ key: 'mood', label: '情志状态', options: ['平和', '易急躁/胸闷', '低落/叹气'] })
    extra.push({ key: 'eye', label: '眼睛/干燥', options: ['无', '眼干/酸涩', '明显'] })
  }
  if (v.metal < 40) {
    extra.push({ key: 'skin', label: '皮肤/呼吸', options: ['正常', '偏干/易敏', '明显'] })
  }
  // 合并：基础 2 题 + 弱项题，去重后取前 5-6 题
  const all = [...base, ...extra]
  const seen = new Set()
  return all.filter(q => {
    if (seen.has(q.key)) return false
    seen.add(q.key)
    return true
  }).slice(0, 6)
})

// ── Step 1 → 调 bazi 端点 ──
async function calcBazi() {
  if (!canCalcBazi.value) return
  calculating.value = true
  try {
    const resp = await assistantApi.bazi(
      form.birth_date,
      form.birth_hour || null,
      form.birthplace,
      form.birth_date_type,
    )
    baziResult.value = resp.data || resp
    currentStep.value = 2
  } catch (e) {
    alert('八字推演失败：' + (e.message || e))
  } finally {
    calculating.value = false
  }
}

function nextToQuestionnaire() {
  currentStep.value = 3
}

// ── Step 3 → 提交 onboarding ──
async function submitAll() {
  submitting.value = true
  try {
    const v = baziResult.value
    const onboardingBody = {
      nickname: form.nickname,
      gender: form.gender,
      birth_date: form.birth_date,
      birth_hour: form.birth_hour || null,
      birthplace: form.birthplace,
      engine: v?.engine || 'spum_bazi',
      v_innate: v?.v_innate,
      bazi_result: v,  // 让后端可直接复用所有推演结果
      chief_complaint: '',
    }

    const resp = await casesApi.onboarding(onboardingBody)
    userStore.is_onboarded = true
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
.field-hint { font-size: 11px; color: var(--ink-tertiary); }

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
}
</style>
