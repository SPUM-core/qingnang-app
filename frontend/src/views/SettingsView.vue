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
          <span v-if="caseData?.observations">· 观测 {{ caseData.observations.length }} 次</span>
        </p>
        <p class="profile-model" v-if="caseData?.bazi">
          八字：{{ caseData.bazi }}
          <span v-if="caseData?.syndrome"> · {{ caseData.syndrome }}</span>
        </p>
      </div>
      <button class="logout-btn" :disabled="busy === 'logout'" @click="handleAction('logout')">
        <span v-if="busy === 'logout'">退出中…</span>
        <span v-else>退出</span>
      </button>
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

          <!-- 选择 → QSelect（纯 Vue 渲染，Android WebView 原生 select 有白屏 bug） -->
          <QSelect v-else-if="item.type === 'select'"
                   v-model="settings[item.key]"
                   :options="item.options"
                   :placeholder="'请选择'"
                   :title="item.label" />

          <!-- 只读值（动态计算） -->
          <span v-else-if="item.type === 'readonly'" class="row-value">
            {{ typeof item.value === 'function' ? item.value() : item.value }}
          </span>

          <!-- 只读值 + 按钮（如版本号+检查更新） -->
          <div v-else-if="item.type === 'readonly_button'" class="row-readonly-btn">
            <span class="row-value">{{ typeof item.value === 'function' ? item.value() : item.value }}</span>
            <button class="row-btn" :class="{ danger: item.danger }"
                    :disabled="busy === item.action || updateState === 'checking'"
                    @click="handleAction(item.action)">
              <span v-if="busy === item.action || updateState === 'checking'">{{ item.btnTextLoading || '检查中…' }}</span>
              <span v-else>{{ item.btnText || '前往' }}</span>
            </button>
          </div>

          <!-- 位置同步（显示城市名 + 同步按钮） -->
          <div v-else-if="item.type === 'location'" class="row-readonly-btn">
            <span class="row-value">{{ locationLabel }}</span>
            <button class="row-btn"
                    :disabled="busy === 'sync_location'"
                    @click="syncLocation">
              {{ busy === 'sync_location' ? '定位中…' : '同步' }}
            </button>
          </div>

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
      <!-- ⚠️ 通用确认/提示弹窗（替换原生 confirm/alert — Android WebView 原生 dialog 白屏） -->
      <div v-if="dialog.visible" class="update-modal-backdrop" @click.self="dialog.reject?.()">
        <div class="update-modal">
          <h3>{{ dialog.title || '提示' }}</h3>
          <p class="update-note" style="white-space: pre-wrap;">{{ dialog.message }}</p>
          <div class="update-actions">
            <button v-if="dialog.type === 'confirm'" class="row-btn" @click="dialog.reject?.()">{{ dialog.cancelText || '取消' }}</button>
            <button class="row-btn primary" @click="dialog.resolve?.()">{{ dialog.confirmText || '确定' }}</button>
          </div>
        </div>
      </div>

      <div class="legal-links">
        <a>用户协议</a><span>·</span>
        <a>隐私政策</a><span>·</span>
        <a>免责声明</a>
      </div>
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
import QSelect from '../components/ui/QSelect.vue'
import { checkForUpdate, getAppVersion } from '../utils/appUpdater'

const router = useRouter()
const user   = useUserStore()
const settings = useSettingsStore()   // ← 替换原来的本地 reactive

// ⭐ 2026-10-05：城市变化 → 保存到后端 + 清缓存触发重新推理
// 2026-10-13：城市改为定位自动同步，保留 watch 做后端同步
watch(() => settings.city, async (newCity, oldCity) => {
  if (oldCity === undefined) return  // 初始化加载时跳过
  if (newCity === oldCity) return
  try {
    await api.patch('/api/v1/auth/me', { city: newCity })
    // 清今日 lifestyle 缓存标记 → 下次 Dashboard 进页面重新推理
    storage.remove('qingnang_today_lifestyle_md5')
  } catch (e) {
    console.warn('保存城市到后端失败:', e)
  }
})

// ── 位置定位 + 自动同步 ──
const locationLabel = computed(() => settings.city || '未定位')

async function syncLocation() {
  busy.value = 'sync_location'
  try {
    if (!navigator.geolocation) {
      await showAlert('当前设备不支持定位功能')
      return
    }
    // 申请定位权限 → 获取经纬度
    const pos = await new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: false,
        timeout: 10000,
        maximumAge: 300000,  // 5 分钟缓存
      })
    })
    const { latitude, longitude } = pos.coords

    // 反查城市名（使用 OpenStreetMap Nominatim 免费服务）
    const r = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json&zoom=10&accept-language=zh-CN`,
      { headers: { 'Accept': 'application/json' } }
    )
    if (!r.ok) throw new Error('反查城市失败')
    const data = await r.json()
    // Nominatim 返回 address 对象，提取城市名
    const addr = data.address || {}
    const cityName = addr.city || addr.town || addr.county || addr.province || addr.state || ''
    if (!cityName) throw new Error('无法识别城市名')

    // 保存到 settings（watch 会自动同步到后端）
    settings.city = cityName
    await showAlert(`已定位：${cityName}`)
  } catch (e) {
    if (e.code === 1) {
      await showAlert('定位权限被拒绝，请在系统设置中允许定位权限')
    } else {
      await showAlert('定位失败：' + (e.message || '请稍后重试'))
    }
  } finally {
    busy.value = null
  }
}

// settings 已在 stores/settings.js 初始化 + watch persist，这里不需要再配 defaults 和 watch

// ── 状态 ──
const busy     = ref(null)
const caseData = ref(null)
const currentVersion = ref('0.0.0')   // 动态从原生 APK 读

// 启动时异步获取真实版本号（原生读 AndroidManifest）
getAppVersion().then(v => { currentVersion.value = v }).catch(() => {})

// ⚠️ 自定义 dialog（替换原生 confirm/alert — Android WebView 原生 dialog 白屏）
const dialog = reactive({
  visible: false, type: 'confirm', title: '', message: '',
  confirmText: '确定', cancelText: '取消',
  resolve: null, reject: null,
})
function showConfirm(message, title = '提示') {
  return new Promise((resolve) => {
    dialog.visible = true; dialog.type = 'confirm'
    dialog.title = title; dialog.message = message
    dialog.confirmText = '确定'; dialog.cancelText = '取消'
    dialog.resolve = () => { dialog.visible = false; resolve(true) }
    dialog.reject  = () => { dialog.visible = false; resolve(false) }
  })
}
function showAlert(message, title = '提示') {
  return new Promise((resolve) => {
    dialog.visible = true; dialog.type = 'alert'
    dialog.title = title; dialog.message = message
    dialog.confirmText = '知道了'
    dialog.resolve = () => { dialog.visible = false; resolve() }
    dialog.reject  = null
  })
}

// ── 版本更新状态（仅 Settings 底部 badge 展示）──
const updateState    = ref('idle')       // idle | checking | has_update | latest | error
const updateInfo     = ref(null)         // 仅存储版本信息供 badge 展示

// App.vue 启动时已经全局静默检查过一次，SettingsView 只在手动点"检查更新"时再查
// onMounted 里不再自动调用 checkUpdate()

// ── 检查更新（走 appUpdater.js 共享的 checkForUpdate，版本号从原生 APK 读）──
async function checkUpdate() {
  updateState.value = 'checking'
  try {
    const info = await checkForUpdate()
    if (info.has_update) {
      updateInfo.value = info
      updateState.value = 'has_update'
      // ⚠️ 有更新时，App.vue 的 UpdateDialog 会自动弹
      // SettingsView 只负责底部 badge 状态提示，不再自己弹 modal
    } else {
      updateState.value = 'latest'
      updateInfo.value = null
    }
  } catch (e) {
    console.warn('[Settings] 版本检查失败:', e?.message)
    updateState.value = 'error'
    updateInfo.value = null
  }
}

// closeUpdateModal / downloadUpdate 已删除 —— 统一由 App.vue 的 UpdateDialog 处理

// ── onMounted：后端可达性探测 + 加载用户档案 ──
const _serverStatusText = ref('检测中…')
onMounted(async () => {
  // App.vue 已全局静默检查过更新，这里不再重复

  // 后端可达性探测（ping version 端点 — 轻量）
  try {
    const r = await api.get('/api/v1/version/manifest', { timeout: 4000 })
    _serverStatusText.value = '● 正常'
  } catch (e) {
    _serverStatusText.value = '⚠️ ' + (e?.response?.status === 403 ? '自动更新已关闭' : '离线')
  }

  // 拉取用户档案（名片卡需要注册天数、观测次数、八字）
  try {
    const r = await api.get('/api/v1/cases/mine', { timeout: 6000 })
    caseData.value = r.data?.case || null
  } catch (e) {
    console.warn('[Settings] 拉取档案失败:', e?.message)
  }
})

// ── 分组定义（图标使用品牌线性 QIcon）──
const groups = [
  {
    key: 'notify', icon: 'bell', title: '通知与提醒',
    items: [
      // 2026-10-13：城市改为定位自动同步（去掉手动城市下拉框）
      { key: 'city', type: 'location', icon: 'home', label: '所在位置',
        desc: '自动获取定位，用于天气查询与五形推理' },
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
  // ai section 已删除（全局 DeepSeek 云端，无模型切换）
  // 调理目标模块已删除（2026-10-13）
  {
    key: 'privacy', icon: 'lock', title: '隐私与数据',
    items: [
      { key: 'share_family', type: 'toggle', icon: 'user', label: '与家人共享' },
      { key: 'share_data_anonymous', type: 'toggle', icon: 'chart', label: '匿名数据用于研究' },
      { type: 'button', icon: 'doc', label: '导出我的数据', btnText: '导出 JSON', action: 'export' },
      { type: 'button', icon: 'warn', label: '清除本地缓存', btnText: '清除', danger: true, action: 'clear_cache' },
      // 2026-10-13：重新初始化建档从"账号与社交"移到"隐私与数据"
      { type: 'button', icon: 'warn', label: '重新初始化建档', btnText: '重新开始', action: 'reinit', danger: true },
    ]
  },
  {
    key: 'about', icon: 'info', title: '关于与更新',
    items: [
      // 2026-10-13：检查更新按钮放到版本号后方
      { key: 'app_version', type: 'readonly_button', icon: 'info', label: '当前版本',
        value: () => currentVersion.value,
        btnText: '检查更新', btnTextLoading: '检查中…', action: 'check_update' },
      { key: 'server_status', type: 'readonly', icon: 'chart', label: '服务状态',
        value: () => _serverStatusText }
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
    case 'check_update': {
      await checkUpdate()
      break
    }

    case 'test_llm': {
      busy.value = 'test_llm'
      try {
        await refreshHealth()
      } finally { busy.value = null }
      break
    }

    case 'logout': {
      if (!(await showConfirm('确定退出登录？'))) return
      busy.value = 'logout'
      try {
        user.logout()
        window.location.href = '/login?skip_splash=1'
      } finally { busy.value = null }
      break
    }

    case 'reinit': {
      if (!(await showConfirm('重新开始将清除你的数字模型（体质档案、观测记录、调理方案），仅保留账号。继续？'))) return
      busy.value = 'reinit'
      try {
        await api.post('/api/v1/cases/reset')
        storage.setOnboarded(false)
        const u = storage.get('qn_user', {}) || {}
        u.is_onboarded = false
        storage.set('qn_user', u)
        user.isOnboarded = false
        caseData.value = null
        ;['qingnang_today', 'qingnang_archive', 'qingnang_feedbacks', 'qingnang_settings']
          .forEach(k => storage.remove(k))
        window.location.href = '/onboarding'
      } catch (e) {
        await showAlert('重置失败：' + (e.response?.data?.detail || e.message))
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
        await showAlert('导出失败：' + (e.response?.data?.detail || e.message))
      } finally { busy.value = null }
      break
    }

    case 'clear_cache': {
      if (!(await showConfirm('清除本地缓存？这会重置通知偏好、今日待办等，云端数据不受影响。'))) return
      ;['qingnang_settings', 'qingnang_today', 'qingnang_archive', 'qingnang_feedbacks']
        .forEach(k => storage.remove(k))
      await showAlert('已清除，页面将刷新')
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

/* 退出按钮（名片卡内右侧） */
.profile-card .logout-btn {
  flex-shrink: 0; z-index: 2;
  font-size: calc(12px * var(--qn-fs-scale)); padding: 6px 16px; border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.3); background: rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.85); cursor: pointer; transition: all 0.15s;
  align-self: center;
}
.profile-card .logout-btn:hover:not(:disabled) { background: rgba(255,255,255,0.2); border-color: rgba(255,255,255,0.5); }
.profile-card .logout-btn:disabled { opacity: 0.5; cursor: not-allowed; }

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

/* 只读值 + 按钮行（版本号+检查更新、位置+同步） */
.row-readonly-btn { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }

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

/* 选择 — Android WebView 必须显式给 option 加颜色（option 不继承父级 CSS 变量） */
.select {
  font-size: calc(13px * var(--qn-fs-scale)); padding: 6px 28px 6px 10px;
  border: 1px solid var(--qn-line); border-radius: var(--qn-r-sm);
  background: var(--qn-surface) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236B7277' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E") no-repeat right 8px center;
  appearance: none; cursor: pointer; color: var(--qn-ink);
  flex-shrink: 0; max-width: 60%;
}
.select:focus { outline: none; border-color: var(--qn-emerald); }
/* ⚠️ 关键：Android WebView 下 <option> 不继承父级颜色，必须显式声明 */
.select option {
  background-color: #FFFFFF;
  color: #33403B;
}
html[data-theme="dark"] .select option {
  background-color: #242826;
  color: #E8E5DD;
}

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
.app-ver { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin: 0 0 14px; display: flex; align-items: center; justify-content: center; gap: 8px; flex-wrap: wrap; }

/* 版本状态 badge */
.update-badge {
  display: inline-block; font-size: calc(10px * var(--qn-fs-scale));
  padding: 2px 8px; border-radius: 10px; font-weight: 500;
  background: rgba(var(--qn-emerald-rgb), 0.1); color: var(--qn-emerald);
  cursor: pointer; transition: background 0.15s;
}
.update-badge:hover { background: var(--qn-emerald); color: #fff; }
.update-badge.checking { background: var(--qn-bg-2); color: var(--qn-ink-3); cursor: default; }
.update-badge.latest   { background: rgba(76,175,80,0.1); color: #4CAF50; cursor: default; }
.update-badge.error    { background: rgba(216,67,21,0.1); color: var(--wuxing-fire); cursor: pointer; }

/* 更新弹窗 */
.update-modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 9999; padding: 20px;
}
.update-modal {
  background: var(--qn-surface); border-radius: var(--qn-r-lg);
  padding: 24px; max-width: 360px; width: 100%;
  border: 1px solid var(--qn-line);
  box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}
.update-modal h3 { margin: 0 0 12px; font-size: calc(16px * var(--qn-fs-scale)); color: var(--qn-emerald); }
.update-note { font-size: calc(13px * var(--qn-fs-scale)); color: var(--qn-ink); margin: 0 0 12px; line-height: 1.5; }
.update-meta { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-bottom: 18px; }
.force-tag { color: var(--wuxing-fire); font-weight: 500; }
.update-actions { display: flex; gap: 10px; justify-content: flex-end; }
.row-btn.primary { background: var(--qn-emerald); color: #fff; border-color: var(--qn-emerald); }
.row-btn.primary:hover:not(:disabled) { background: #2A6B60; }
.legal-links { font-size: calc(11px * var(--qn-fs-scale)); color: var(--qn-ink-3); margin-bottom: 16px; }
.legal-links a { color: var(--qn-ink-2); margin: 0 6px; cursor: pointer; }
.legal-links a:hover { color: var(--qn-emerald); }
.legal-links span { color: var(--qn-line); }

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

  /* select 类型行：上下布局，label 在上 select 在下，触发按钮满宽 */
  .setting-row.is-select {
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 8px;
  }
  .setting-row.is-select .row-left {
    flex-basis: 100%;
  }
  /* ⚠️ :deep() 穿透 scoped 到子组件 QSelect 内部 */
  .setting-row.is-select :deep(.qselect-trigger) {
    flex-basis: 100%;
    width: 100%;
    max-width: none;
    box-sizing: border-box;
  }
}
</style>
