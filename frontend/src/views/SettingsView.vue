<template>
  <section class="page settings" data-page-id="P19">
    <!-- 顶部：个人名片 -->
    <div class="profile-card">
      <div class="avatar">
        <img src="/assets/logo/icon-light.png" alt="" role="presentation" />
      </div>
      <div class="profile-info">
        <h2>{{ user.displayName }}</h2>
        <p class="profile-sub">
          青囊 ID：{{ user.qingnangId || '--' }}
          <span v-if="caseData?.created_at">· 注册 {{ daysSince(caseData.created_at) }} 天</span>
          <span v-if="caseData?.observations?.length">· 观测 {{ caseData.observations.length }} 次</span>
        </p>
        <p class="profile-model" v-if="caseData?.bazi">
          八字：{{ caseData.bazi }}
          <span v-if="caseData?.syndrome"> · {{ caseData.syndrome }}</span>
        </p>
      </div>
    </div>

    <!-- 设置分组 -->
    <div class="setting-group" v-for="group in groups" :key="group.key">
      <h3 class="group-title"><QIcon :name="group.icon" :size="16" /> {{ group.title }}</h3>
      <div class="setting-list">
        <div v-for="item in group.items" :key="item.action || item.key"
             class="setting-row"
             :class="{ danger: item.danger, 'is-select': item.type === 'select' }">
          <div class="row-left">
            <span class="row-icon"><QIcon :name="item.icon" :size="15" /></span>
            <div class="row-text">
              <span class="row-label">{{ item.label }}</span>
              <span v-if="item.desc" class="row-desc">{{ item.desc }}</span>
            </div>
          </div>

          <!-- 开关 -->
          <label v-if="item.type === 'toggle'" class="switch">
            <input type="checkbox" v-model="settings[item.key]" />
            <span class="switch-track"></span>
          </label>

          <!-- 选择 -->
          <select v-else-if="item.type === 'select'" v-model="settings[item.key]" class="select">
            <option v-for="opt in item.options" :key="opt.value" :value="opt.value">
              {{ opt.label }}{{ opt.hint ? '  ' + (typeof opt.hint === 'function' ? opt.hint() : opt.hint) : '' }}
            </option>
          </select>

          <!-- 只读值（动态计算） -->
          <span v-else-if="item.type === 'readonly'" class="row-value">
            {{ typeof item.value === 'function' ? item.value() : item.value }}
          </span>

          <!-- 按钮 -->
          <button v-else-if="item.type === 'button'" class="row-btn" :class="{ danger: item.danger }"
                  :disabled="busy === item.action"
                  @click="handleAction(item.action)">
            <span v-if="busy === item.action">{{ item.btnText || '处理中…' }}</span>
            <span v-else>{{ item.btnText || '前往' }}</span>
          </button>

          <!-- 值显示 -->
          <span v-else class="row-value">{{ settings[item.key] }}</span>
        </div>
      </div>
    </div>

    <!-- 底部 -->
    <!-- ═══ 八字校准：出生地经纬度（真太阳时校正）═══ -->
    <div class="setting-group">
      <h3 class="group-title"><QIcon name="chart" :size="16" /> ⚗️ 八字校准</h3>
      <div class="setting-list">
        <div class="setting-row">
          <div class="row-left">
            <span class="row-icon"><QIcon name="home" :size="15" /></span>
            <div class="row-text">
              <span class="row-label">出生地（真太阳时校正）</span>
              <span class="row-desc">
                出生地经度决定八字时柱：北京时间 120°E 为基准，{{ birthLngDisplay }}
              </span>
            </div>
          </div>
        </div>
        <!-- 省→市 级联 -->
        <div class="setting-row" style="flex-direction:column; gap:10px; align-items:flex-start;">
          <div class="birth-cascader">
            <select v-model="birthProvince" class="select" @change="onBirthProvinceChange">
              <option value="">选择省份</option>
              <option v-for="p in CHINA_PROVINCES" :key="p.code" :value="p.code">{{ p.name }}</option>
            </select>
            <select v-model="birthCity" class="select" :disabled="!birthProvince">
              <option value="">{{ birthProvince ? '选择城市' : '先选省份' }}</option>
              <option v-for="c in birthCities" :key="c.name" :value="c.name">
                {{ c.name }}
              </option>
            </select>
            <button class="row-btn" :disabled="!canSaveBirth" :class="{ disabled: !canSaveBirth }"
                    :style="{ marginLeft: 'auto' }"
                    @click="saveBirthLocation">
              保存校准
            </button>
          </div>
          <!-- 真太阳时预览 -->
          <div v-if="birthLng != null" class="birth-solar-preview">
            <span>🌐 {{ birthLng.toFixed(2) }}°E</span>
            <span class="birth-solar-diff" :class="{ east: birthLng > 120, west: birthLng < 120 }">
              相对标准 120°E：
              {{ birthLng > 120 ? '早' : '晚' }}
              {{ Math.abs(((birthLng - 120) * 4)).toFixed(1) }} 分钟
            </span>
            <span v-if="birthLat != null">· {{ birthLat.toFixed(2) }}°N</span>
          </div>
          <div v-if="savedBirthInfo" class="birth-saved">
            ✅ 已保存：{{ savedBirthInfo.city }} · {{ savedBirthInfo.lng }}°E
          </div>
        </div>
      </div>
    </div>

    <div class="app-info">
      <p class="app-name">青囊生活管家</p>
      <p class="app-ver">Version {{ APP_VERSION }} · SPUM 范式引擎</p>
      <div class="legal-links">
        <a>用户协议</a><span>·</span>
        <a>隐私政策</a><span>·</span>
        <a>免责声明</a>
      </div>
      <button class="logout-btn" :disabled="busy === 'logout'" @click="handleAction('logout')">
        <span v-if="busy === 'logout'">退出中…</span>
        <span v-else>退出登录</span>
      </button>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { useSettingsStore } from '../stores/settings'
import { api } from '../api/client'
import * as storage from '../utils/storage'
import QIcon from '../components/ui/QIcon.vue'
import { CHINA_PROVINCES, CHINA_CITIES } from '../constants/china-cities.js'
import { APP_VERSION } from '../utils/appUpdater'

const router = useRouter()
const user   = useUserStore()
const settings = useSettingsStore()   // ← 替换原来的本地 reactive

// ⭐ 2026-10-05：城市变化 → 保存到后端 + 清缓存触发重新推理
watch(() => settings.city, async (newCity, oldCity) => {
  if (oldCity === undefined) return  // 初始化加载时跳过
  try {
    await api.patch('/api/v1/auth/me', { city: newCity })
    // 清今日 lifestyle 缓存标记 → 下次 Dashboard 进页面重新推理
    storage.remove('qingnang_today_lifestyle_md5')
  } catch (e) {
    console.warn('保存城市到后端失败:', e)
  }
})

// settings 已在 stores/settings.js 初始化 + watch persist，这里不需要再配 defaults 和 watch

// ── 状态 ──
const busy     = ref(null)
const caseData = ref(null)
// providerInfo / refreshHealth / llm_provider watch 已删除（全局 DeepSeek）

// ── 出生地经纬度编辑（八字校准）──
const birthProvince = ref('')      // 省 code
const birthCity = ref('')          // 市 name
const savedBirthInfo = ref(null)   // { city, lng } 已保存状态

const birthCities = computed(() => CHINA_CITIES[birthProvince.value] || [])

const birthLng = computed(() => {
  if (!birthProvince.value || !birthCity.value) return null
  const c = birthCities.value.find(x => x.name === birthCity.value)
  return c?.lng ?? null
})
const birthLat = computed(() => {
  if (!birthProvince.value || !birthCity.value) return null
  const c = birthCities.value.find(x => x.name === birthCity.value)
  return c?.lat ?? null
})
const birthLngDisplay = computed(() => {
  if (birthLng.value == null) return '请选择'
  return `${birthLng.value.toFixed(2)}°E → ${((birthLng.value - 120) * 4).toFixed(1)} min 时差`
})
const canSaveBirth = computed(() => !!(birthProvince.value && birthCity.value))

function onBirthProvinceChange() { birthCity.value = '' }

async function saveBirthLocation() {
  if (!canSaveBirth.value) return
  busy.value = 'save_birth'
  try {
    await api.patch('/api/v1/auth/me', {
      birth_city: birthCity.value,
      birth_longitude: birthLng.value,
      birth_latitude: birthLat.value,
    })
    savedBirthInfo.value = {
      city: birthCity.value,
      lng: birthLng.value.toFixed(2),
    }
    // 刷新 userStore 让 user.birthLongitude 同步
    await user.fetchMe()
    setTimeout(() => { savedBirthInfo.value = null }, 3000)
  } catch (e) {
    alert('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    busy.value = null
  }
}

// ── 设置 (storage 持久化 + App.vue 全局应用) ──
// 设置已全部迁到 stores/settings.js (Pinia store)
// 这里直接使用 settings.theme / settings.font_size / settings.reduce_motion 等
// UI 改值 → store state 变化 → store.watch persist() → App.vue watch applyDisplay()

// ── 分组定义（图标使用品牌线性 QIcon）──
const groups = [
  {
    key: 'notify', icon: 'bell', title: '通知与提醒',
    items: [
      // ⭐ 2026-10-05 新增：城市选择（真实天气查询）
      { key: 'city', type: 'select', icon: 'home', label: '所在城市',
        desc: '用于查询真实天气，结合五形推理今日宜忌',
        options: [
          { value: '', label: '未设置（节气模拟）' },
          { value: '北京', label: '北京' }, { value: '上海', label: '上海' },
          { value: '天津', label: '天津' }, { value: '重庆', label: '重庆' },
          { value: '广州', label: '广州' }, { value: '深圳', label: '深圳' },
          { value: '杭州', label: '杭州' }, { value: '南京', label: '南京' },
          { value: '成都', label: '成都' }, { value: '武汉', label: '武汉' },
          { value: '西安', label: '西安' }, { value: '长沙', label: '长沙' },
          { value: '郑州', label: '郑州' }, { value: '济南', label: '济南' },
          { value: '青岛', label: '青岛' }, { value: '大连', label: '大连' },
          { value: '沈阳', label: '沈阳' }, { value: '哈尔滨', label: '哈尔滨' },
          { value: '昆明', label: '昆明' }, { value: '贵阳', label: '贵阳' },
          { value: '福州', label: '福州' }, { value: '厦门', label: '厦门' },
          { value: '合肥', label: '合肥' }, { value: '南昌', label: '南昌' },
          { value: '太原', label: '太原' }, { value: '石家庄', label: '石家庄' },
          { value: '呼和浩特', label: '呼和浩特' }, { value: '乌鲁木齐', label: '乌鲁木齐' },
          { value: '苏州', label: '苏州' }, { value: '无锡', label: '无锡' },
          { value: '宁波', label: '宁波' }, { value: '佛山', label: '佛山' },
          { value: '东莞', label: '东莞' }, { value: '珠海', label: '珠海' },
          { value: '三亚', label: '三亚' }, { value: '海口', label: '海口' },
        ] },
      { key: 'notify_push', type: 'toggle', icon: 'bell', label: '推送通知', desc: '接收生活建议、时辰节律等提醒' },
      { key: 'notify_time_morning', type: 'select', icon: 'spark', label: '晨间提醒时间',
        options: [
          { value: '06:00', label: '06:00' }, { value: '07:00', label: '07:00' },
          { value: '08:00', label: '08:00' }, { value: '09:00', label: '09:00' }
        ] },
      { key: 'notify_time_evening', type: 'select', icon: 'moon', label: '晚间提醒时间',
        options: [
          { value: '20:00', label: '20:00' }, { value: '21:00', label: '21:00' },
          { value: '22:00', label: '22:00' }, { value: '23:00', label: '23:00' }
        ] },
      { key: 'notify_cloth', type: 'toggle', icon: 'leaf', label: '穿搭建议提醒' },
      { key: 'notify_food', type: 'toggle', icon: 'doc', label: '饮食宜忌提醒' },
      { key: 'notify_home', type: 'toggle', icon: 'home', label: '住房改造建议' },
      { key: 'notify_hourly', type: 'toggle', icon: 'clock', label: '时辰节律提醒' },
    ]
  },
  {
    key: 'display', icon: 'sliders', title: '显示与外观',
    items: [
      { key: 'theme', type: 'select', icon: 'moon', label: '主题',
        options: [
          { value: 'auto', label: '跟随系统' },
          { value: 'light', label: '月白（浅色）' },
          { value: 'dark', label: '松烟（深色）' }
        ] },
      { key: 'font_size', type: 'select', icon: 'doc', label: '字体大小',
        options: [
          { value: 'small', label: '小' }, { value: 'medium', label: '中' }, { value: 'large', label: '大' }
        ] },
      { key: 'reduce_motion', type: 'toggle', icon: 'spark', label: '减少动画' },
      { key: 'elder_mode', type: 'toggle', icon: 'heart', label: '老年关怀模式', desc: '字号放大 35%，按钮更易点击' },
    ]
  },
  {
    key: 'collect', icon: 'chart', title: '数据采集',
    items: [
      { key: 'auto_collect', type: 'toggle', icon: 'arrow', label: '自动采集', desc: '按设定频率自动发起 PPG 采集请求' },
      { key: 'collect_freq', type: 'select', icon: 'calendar', label: '采集频率',
        options: [
          { value: 'twice_daily', label: '每日 2 次（卯/酉时）' },
          { value: 'daily', label: '每日 1 次（卯时）' },
          { value: 'every_3days', label: '每 3 日 1 次' },
          { value: 'weekly', label: '每周 1 次' }
        ] },
      { key: 'collect_remind', type: 'toggle', icon: 'clock', label: '采集前提醒' },
    ]
  },
  {
    key: 'goal', icon: 'anchor', title: '调理目标',
    items: [
      { key: 'primary_goal', type: 'select', icon: 'anchor', label: '首要目标',
        options: [
          { value: 'dispatch_qi', label: '疏解气结' },
          { value: 'warm_earth', label: '温土化湿' },
          { value: 'calm_fire', label: '潜镇相火' },
          { value: 'nourish_water', label: '滋水护阴' }
        ] },
      { key: 'secondary_goal', type: 'select', icon: 'spark', label: '次要目标',
        options: [
          { value: 'warm_earth', label: '温土化湿' },
          { value: 'dispatch_qi', label: '疏解气结' },
          { value: 'calm_fire', label: '潜镇相火' },
          { value: 'nourish_water', label: '滋水护阴' },
          { value: 'none', label: '暂无' }
        ] }
    ]
  },
  // ai section 已删除（全局 DeepSeek 云端，无模型切换）
  {
    key: 'privacy', icon: 'lock', title: '隐私与数据',
    items: [
      { key: 'share_family', type: 'toggle', icon: 'user', label: '与家人共享' },
      { key: 'share_data_anonymous', type: 'toggle', icon: 'chart', label: '匿名数据用于研究' },
      { type: 'button', icon: 'doc', label: '导出我的数据', btnText: '导出 JSON', action: 'export' },
      { type: 'button', icon: 'warn', label: '清除本地缓存', btnText: '清除', danger: true, action: 'clear_cache' }
    ]
  },
  {
    key: 'account', icon: 'user', title: '账号与社交',
    items: [
      { type: 'button', icon: 'user', label: '我的好友', btnText: '前往', action: 'friends' },
      { type: 'button', icon: 'warn', label: '重新初始化建档', btnText: '重新开始', action: 'reinit', danger: true },
    ]
  }
]

// ── 工具 ──
function daysSince(iso) {
  if (!iso) return '--'
  const ms = Date.now() - new Date(iso).getTime()
  return Math.max(1, Math.floor(ms / 86400000))
}

// ── 动作处理 ──
async function handleAction(action) {
  switch (action) {
    case 'test_llm': {
      busy.value = 'test_llm'
      try {
        await refreshHealth()
      } finally { busy.value = null }
      break
    }

    case 'friends':
      router.push({ name: 'users' })
      break

    case 'logout': {
      if (!confirm('确定退出登录？')) return
      busy.value = 'logout'
      try {
        user.logout()
        // 硬跳转：彻底重置 Pinia/Vue 状态，避免组件残留
        window.location.href = '/login?skip_splash=1'
      } finally { busy.value = null }
      break
    }

    case 'reinit': {
      if (!confirm('重新开始将清除你的数字模型（体质档案、观测记录、调理方案），仅保留账号。继续？')) return
      busy.value = 'reinit'
      try {
        // 1. 清后端数据
        await api.post('/api/v1/cases/reset')
        // 2. 清前端 Pinia 状态
        storage.setOnboarded(false)
        const u = storage.get('qn_user', {}) || {}
        u.is_onboarded = false
        storage.set('qn_user', u)
        user.isOnboarded = false
        caseData.value = null
        // 3. 清前端 localStorage 缓存（今日建议、归档、反馈等）
        ;['qingnang_today', 'qingnang_archive', 'qingnang_feedbacks', 'qingnang_settings']
          .forEach(k => storage.remove(k))
        // 4. 跳 onboarding
        window.location.href = '/onboarding'
      } catch (e) {
        alert('重置失败：' + (e.response?.data?.detail || e.message))
      } finally { busy.value = null }
      break
    }

    case 'export': {
      busy.value = 'export'
      try {
        const r = await api.get('/api/v1/cases/mine')
        const payload = {
          exported_at: new Date().toISOString(),
          user: { qingnang_id: user.qingnangId, nickname: user.nickname },
          case: r.data?.case || caseData.value,
          settings: { ...settings },
        }
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `qingnang-${user.qingnangId || 'user'}-${new Date().toISOString().slice(0,10)}.json`
        a.click()
      } catch (e) {
        alert('导出失败：' + (e.response?.data?.detail || e.message))
      } finally { busy.value = null }
      break
    }

    case 'clear_cache': {
      if (!confirm('清除本地缓存？这会重置通知偏好、今日待办等，云端数据不受影响。')) return
      ;['qingnang_settings', 'qingnang_today', 'qingnang_archive', 'qingnang_feedbacks']
        .forEach(k => storage.remove(k))
      alert('已清除，页面将刷新')
      location.reload()
      break
    }
  }
}
</script>

<style scoped>
.settings { max-width: 760px; }

/* 个人名片 */
.profile-card {
  display: flex; align-items: center; gap: 16px;
  background: linear-gradient(135deg, var(--qn-emerald) 0%, #2A6B60 100%);
  color: #fff; border-radius: var(--qn-r-lg); padding: 20px 24px;
  margin-bottom: 24px; position: relative; overflow: hidden;
}
.profile-card::after {
  content: ''; position: absolute; top: -50%; right: -20%; width: 200px; height: 200px;
  background: radial-gradient(circle, rgba(var(--qn-emerald-light-rgb),0.4), transparent 70%);
  pointer-events: none;
}
.avatar {
  width: 56px; height: 56px; border-radius: 50%;
  background: rgba(255,255,255,0.15);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; overflow: hidden;
}
.avatar img { width: 34px; height: auto; }
.profile-info { flex: 1; position: relative; z-index: 2; }
.profile-info h2 { margin: 0 0 4px; font-size: calc(18px * var(--qn-fs-scale)); font-weight: 600; }
.profile-sub { font-size: calc(12px * var(--qn-fs-scale)); color: rgba(255,255,255,0.7); margin: 0 0 2px; }
.profile-model { font-size: calc(11px * var(--qn-fs-scale)); color: rgba(var(--qn-emerald-light-rgb),0.9); margin: 0; }

/* 分组 */
.setting-group { margin-bottom: 28px; }
.group-title {
  font-size: calc(13px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-ink-3);
  text-transform: uppercase; letter-spacing: 1px; margin: 0 0 10px;
  padding-left: 4px;
}
.setting-list {
  background: var(--qn-surface); border: 1px solid var(--qn-line); border-radius: var(--qn-r-lg);
  overflow: hidden;
}

/* 行 */
.setting-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px; border-bottom: 1px solid var(--qn-line);
  transition: background 0.1s;
}
.setting-row:last-child { border-bottom: none; }
.setting-row:hover { background: rgba(var(--qn-emerald-rgb),0.02); }
.setting-row.danger:hover { background: rgba(216,67,21,0.04); }

.row-left { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
.row-icon { width: 28px; text-align: center; color: var(--qn-emerald); display: inline-flex; justify-content: center; flex-shrink: 0; }
.row-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; overflow-wrap: break-word; }
.row-label { font-size: calc(14px * var(--qn-fs-scale)); color: var(--qn-ink); font-weight: 500; white-space: nowrap; }
.row-desc { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); line-height: 1.4; overflow-wrap: break-word; }
.row-value { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink-2); font-family: var(--font-mono); }

/* 开关 */
.switch { position: relative; width: 44px; height: 24px; flex-shrink: 0; }
.switch input { opacity: 0; width: 0; height: 0; }
.switch-track {
  position: absolute; cursor: pointer; inset: 0;
  background: var(--qn-line); border-radius: 24px;
  transition: background 0.2s;
}
.switch-track::before {
  content: ''; position: absolute;
  width: 18px; height: 18px; border-radius: 50%;
  left: 3px; top: 3px; background: var(--qn-surface);
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  transition: transform 0.2s;
}
.switch input:checked + .switch-track { background: var(--qn-emerald); }
.switch input:checked + .switch-track::before { transform: translateX(20px); }

/* 选择 */
.select {
  font-size: calc(13px * var(--qn-fs-scale)); padding: 6px 28px 6px 10px;
  border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm);
  background: var(--qn-surface) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236B7277' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E") no-repeat right 8px center;
  appearance: none; cursor: pointer; color: var(--qn-ink);
  flex-shrink: 0; max-width: 60%;
}
.select:focus { outline: none; border-color: var(--qn-emerald); }

/* 按钮行 */
.row-btn {
  font-size: calc(12px * var(--qn-fs-scale)); padding: 5px 14px; border-radius: var(--qn-r-sm);
  border: 1px solid var(--qn-emerald); background: var(--qn-surface);
  color: var(--qn-emerald); cursor: pointer; transition: all 0.15s;
}
.row-btn:hover:not(:disabled) { background: var(--qn-emerald); color: #fff; }
.row-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.row-btn.danger { border-color: var(--wuxing-fire); color: var(--wuxing-fire); }
.row-btn.danger:hover:not(:disabled) { background: var(--wuxing-fire); color: #fff; }

/* 底部 */
.app-info { text-align: center; padding: 30px 20px; margin-top: 20px; }
.app-name { font-size: calc(16px * var(--qn-fs-scale)); font-weight: 600; color: var(--qn-emerald); margin: 0 0 6px; }
.app-ver { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 0 0 14px; }
.legal-links { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-bottom: 16px; }
.legal-links a { color: var(--qn-ink-2); margin: 0 6px; cursor: pointer; }
.legal-links a:hover { color: var(--qn-emerald); }
.legal-links span { color: var(--qn-line); }
.logout-btn {
  font-size: calc(13px * var(--qn-fs-scale)); padding: 8px 32px; border-radius: 20px;
  border: 1px solid var(--qn-line); background: var(--qn-surface);
  color: var(--qn-ink-3); cursor: pointer; transition: all 0.15s;
}
.logout-btn:hover:not(:disabled) { border-color: var(--wuxing-fire); color: var(--wuxing-fire); }
.logout-btn:disabled { opacity: 0.6; cursor: not-allowed; }

/* ═══ 八字校准 ═══ */
.birth-cascader {
  display: flex; gap: 10px; flex-wrap: wrap;
}
.birth-solar-preview {
  font-size: calc(11px * var(--qn-fs-scale));
  color: var(--qn-ink-2);
  display: flex; gap: 10px; flex-wrap: wrap;
  background: var(--qn-bg-2); border-radius: 6px;
  padding: 6px 10px; width: 100%;
}
.birth-solar-diff.east { color: #4CAF50; }   /* 东经 >120 早 */
.birth-solar-diff.west { color: #F9A825; }   /* 东经 <120 晚 */
.birth-saved {
  font-size: calc(11px * var(--qn-fs-scale));
  color: #4CAF50; font-weight: 500;
  padding: 4px 10px; background: rgba(76,175,80,0.1); border-radius: 6px;
  width: 100%;
}
.row-btn.disabled { opacity: 0.5; cursor: not-allowed; }

/* ═══ 移动端自适应 ═══ */
@media (max-width: 720px) {
  .setting-row { padding: 12px 14px; gap: 12px; }
  .row-icon { width: 22px; }
  .row-label { font-size: calc(13px * var(--qn-fs-scale)); }
  .row-desc { font-size: calc(10px * var(--qn-fs-scale)); }

  /* select 类型行：上下布局，label 在上 select 在下 */
  .setting-row.is-select {
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 8px;
  }
  .setting-row.is-select .row-left {
    flex-basis: 100%;
  }
  .setting-row.is-select .select {
    flex-basis: 100%;
    max-width: none;
    width: 100%;
    box-sizing: border-box;
  }
}
</style>
