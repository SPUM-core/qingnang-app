<template>
  <section class="page settings">
    <!-- 顶部：个人名片 -->
    <div class="profile-card">
      <div class="avatar">
        <img src="/assets/logo/icon-light.png" alt="" />
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
             class="setting-row" :class="{ danger: item.danger }">
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
            <option v-for="opt in item.options" :key="opt.value" :value="opt.value">{{ opt.label }}{{ opt.hint ? '  ' + opt.hint : '' }}</option>
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
    <div class="app-info">
      <p class="app-name">青囊生活管家</p>
      <p class="app-ver">Version 1.0.0 · SPUM 范式引擎</p>
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
import { reactive, ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { api } from '../api/client'
import QIcon from '../components/ui/QIcon.vue'

const router = useRouter()
const user   = useUserStore()

// ── 状态 ──
const busy     = ref(null)
const caseData = ref(null)
const providerInfo = ref({ providers: {}, default_provider: 'spum' })

// 加载后端 provider 配置（哪些可用）
onMounted(async () => {
  try {
    const r = await api.get('/api/v1/cases/mine')
    caseData.value = r.data?.case || null
  } catch {}
  try {
    const h = await api.get('/api/v1/assistant/health')
    providerInfo.value = h.data || providerInfo.value
  } catch {}
})

// ── 设置 (localStorage 持久化) ──
const STORAGE_KEY = 'qingnang_settings'
const defaults = {
  notify_push: true,
  notify_time_morning: '07:00',
  notify_time_evening: '21:00',
  notify_cloth: true,
  notify_food: true,
  notify_home: false,
  notify_hourly: false,
  theme: 'auto',
  font_size: 'medium',
  reduce_motion: false,
  auto_collect: true,
  collect_freq: 'daily',
  collect_remind: true,
  share_family: true,
  share_data_anonymous: true,
  primary_goal: 'dispatch_qi',
  secondary_goal: 'warm_earth',
  llm_provider: 'spum',   // spum=SPUM本地模型(默认), deepseek=云端
}
const settings = reactive({ ...defaults })
try { Object.assign(settings, JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')) } catch {}
watch(settings, v => localStorage.setItem(STORAGE_KEY, JSON.stringify(v)), { deep: true })

// ── 分组定义（图标使用品牌线性 QIcon）──
const groups = [
  {
    key: 'notify', icon: 'bell', title: '通知与提醒',
    items: [
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
  {
    key: 'ai', icon: 'spark', title: '推理模型',
    items: [
      { key: 'llm_provider', type: 'select', icon: 'spark', label: 'AI 助手模型',
        desc: 'SPUM 本地模型（默认·离线可用）或 DeepSeek 云端',
        options: [
          {
            value: 'spum',
            label: 'SPUM 本地模型',
            hint: providerInfo.value.providers?.spum?.online ? '· 在线' : '· 离线（fallback 规则引擎）'
          },
          {
            value: 'deepseek',
            label: 'DeepSeek 云端',
            hint: providerInfo.value.providers?.deepseek?.online ? '· 已配置' : '· 未配置 API KEY'
          },
        ],
      },
      {
        key: 'llm_provider_readonly', type: 'readonly', icon: 'doc',
        get value() {
          const p = providerInfo.value.providers?.[settings.llm_provider]
          return p ? `${p.model}  @ ${p.url?.replace(/^https?:\/\//, '')}` : '--'
        },
      },
    ]
  },
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
        // 2. 清前端状态
        localStorage.removeItem('qingnang_onboarded')
        try {
          const u = JSON.parse(localStorage.getItem('qn_user') || '{}')
          u.is_onboarded = false
          localStorage.setItem('qn_user', JSON.stringify(u))
        } catch {}
        user.isOnboarded = false
        caseData.value = null
        // 3. 跳 onboarding
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
        .forEach(k => localStorage.removeItem(k))
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
  background: linear-gradient(135deg, var(--qingnang-emerald) 0%, #2A6B60 100%);
  color: #fff; border-radius: var(--radius-md); padding: 20px 24px;
  margin-bottom: 24px; position: relative; overflow: hidden;
}
.profile-card::after {
  content: ''; position: absolute; top: -50%; right: -20%; width: 200px; height: 200px;
  background: radial-gradient(circle, rgba(46,125,106,0.4), transparent 70%);
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
.profile-info h2 { margin: 0 0 4px; font-size: 18px; font-weight: 600; }
.profile-sub { font-size: 12px; color: rgba(255,255,255,0.7); margin: 0 0 2px; }
.profile-model { font-size: 11px; color: rgba(46,125,106,0.9); margin: 0; }

/* 分组 */
.setting-group { margin-bottom: 28px; }
.group-title {
  font-size: 13px; font-weight: 600; color: var(--ink-tertiary);
  text-transform: uppercase; letter-spacing: 1px; margin: 0 0 10px;
  padding-left: 4px;
}
.setting-list {
  background: #fff; border: 1px solid var(--ink-line); border-radius: var(--radius-md);
  overflow: hidden;
}

/* 行 */
.setting-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px; border-bottom: 1px solid var(--ink-line);
  transition: background 0.1s;
}
.setting-row:last-child { border-bottom: none; }
.setting-row:hover { background: rgba(26,77,69,0.02); }
.setting-row.danger:hover { background: rgba(216,67,21,0.04); }

.row-left { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
.row-icon { width: 28px; text-align: center; color: var(--qingnang-emerald); display: inline-flex; justify-content: center; }
.row-text { display: flex; flex-direction: column; gap: 2px; }
.row-label { font-size: 14px; color: var(--ink-primary); font-weight: 500; }
.row-desc { font-size: 11px; color: var(--ink-tertiary); line-height: 1.4; }
.row-value { font-size: 13px; color: var(--ink-secondary); font-family: var(--font-mono); }

/* 开关 */
.switch { position: relative; width: 44px; height: 24px; flex-shrink: 0; }
.switch input { opacity: 0; width: 0; height: 0; }
.switch-track {
  position: absolute; cursor: pointer; inset: 0;
  background: var(--ink-line); border-radius: 24px;
  transition: background 0.2s;
}
.switch-track::before {
  content: ''; position: absolute;
  width: 18px; height: 18px; border-radius: 50%;
  left: 3px; top: 3px; background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  transition: transform 0.2s;
}
.switch input:checked + .switch-track { background: var(--qingnang-emerald); }
.switch input:checked + .switch-track::before { transform: translateX(20px); }

/* 选择 */
.select {
  font-size: 13px; padding: 6px 28px 6px 10px;
  border: 1px solid var(--ink-line); border-radius: var(--radius-sm);
  background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236B7277' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E") no-repeat right 8px center;
  appearance: none; cursor: pointer; color: var(--ink-primary);
}
.select:focus { outline: none; border-color: var(--qingnang-emerald); }

/* 按钮行 */
.row-btn {
  font-size: 12px; padding: 5px 14px; border-radius: var(--radius-sm);
  border: 1px solid var(--qingnang-emerald); background: #fff;
  color: var(--qingnang-emerald); cursor: pointer; transition: all 0.15s;
}
.row-btn:hover:not(:disabled) { background: var(--qingnang-emerald); color: #fff; }
.row-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.row-btn.danger { border-color: var(--wuxing-fire); color: var(--wuxing-fire); }
.row-btn.danger:hover:not(:disabled) { background: var(--wuxing-fire); color: #fff; }

/* 底部 */
.app-info { text-align: center; padding: 30px 20px; margin-top: 20px; }
.app-name { font-size: 16px; font-weight: 600; color: var(--qingnang-emerald); margin: 0 0 6px; }
.app-ver { font-size: 11px; color: var(--ink-tertiary); margin: 0 0 14px; }
.legal-links { font-size: 11px; color: var(--ink-tertiary); margin-bottom: 16px; }
.legal-links a { color: var(--ink-secondary); margin: 0 6px; cursor: pointer; }
.legal-links a:hover { color: var(--qingnang-emerald); }
.legal-links span { color: var(--ink-line); }
.logout-btn {
  font-size: 13px; padding: 8px 32px; border-radius: 20px;
  border: 1px solid var(--ink-line); background: #fff;
  color: var(--ink-tertiary); cursor: pointer; transition: all 0.15s;
}
.logout-btn:hover:not(:disabled) { border-color: var(--wuxing-fire); color: var(--wuxing-fire); }
.logout-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
