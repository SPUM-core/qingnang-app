<template>
  <section class="page">
    <h1>体态照片 / 语音样本 / 脉搏采集</h1>
    <p class="page__desc">原始数据直接采集，时间戳对齐后上传 · 数据仅供漂移拟合参考</p>

    <div class="grid grid-3">
      <!-- 体态照片 -->
      <div class="card">
        <h2>📷 体态照片</h2>
        <label class="file-upload">
          <input type="file" accept="image/*" capture="environment" @change="onTongueFile" hidden />
          <span v-if="!tongueName">点击或拍照上传</span>
          <span v-else class="file-selected">{{ tongueName }} · 重新选择</span>
        </label>
        <p class="hint">自然光照 · 头部放松 · 拍摄后系统自动压缩</p>
      </div>

      <!-- 语音样本 -->
      <div class="card">
        <h2>🎙️ 语音样本</h2>
        <div class="voice-area">
          <div v-if="!recording && !voiceName" class="voice-idle">
            <button class="btn btn-primary" @click="startRecord">
              <span class="mic-icon">●</span> 开始录制
            </button>
            <p class="hint">自然说话 10-20 秒 · 避免嘈杂环境</p>
          </div>
          <div v-else-if="recording" class="voice-recording">
            <div class="rec-pulse"><span class="pulse-dot"></span></div>
            <p class="rec-time">{{ formatTime(recordTime) }}</p>
            <button class="btn btn-ghost" @click="stopRecord">停止录制</button>
          </div>
          <div v-else class="voice-done">
            <p class="done-text">✓ 已录制</p>
            <p class="done-file">{{ voiceName }} · {{ formatTime(voiceDuration) }}</p>
            <audio controls :src="voiceUrl" class="voice-player"></audio>
            <button class="btn btn-ghost btn-small" @click="resetRecord">重新录制</button>
          </div>
          <p v-if="voiceError" class="voice-error">⚠️ {{ voiceError }}</p>
        </div>
      </div>

      <!-- 脉搏采集（PPG） -->
      <div class="card ppg-card">
        <h2>💓 脉搏采集</h2>

        <!-- 服务/硬件状态条（动态分层） -->
        <div class="ppg-backend-bar">
          <span class="dot" :class="backendServiceOk ? 'dot-ok' : 'dot-warn'"></span>
          <span class="be-text">后端服务：{{ backendServiceOk ? '在线' : '离线' }}</span>
          <span class="be-sep">·</span>
          <span class="dot" :class="hardwareConnected ? 'dot-ok' : 'dot-warn'"></span>
          <span class="be-text">
            硬件设备：{{ hardwareConnected
              ? ('已连接 · ' + hardwareInfo)
              : (hardwareSupported
                ? (hardwareInfo || '未连接 · 点击右侧按钮选择串口')
                : 'Web Serial 不可用') }}
          </span>
          <button
            v-if="hardwareSupported && !hardwareConnected"
            class="hw-connect-btn"
            :disabled="hwConnecting"
            @click="connectHardware"
            title="点击选择串口连接硬件"
          >{{ hwConnecting ? '检测中...' : '连接硬件' }}</button>
          <button
            v-if="hardwareConnected"
            class="hw-connect-btn hw-disconnect"
            @click="disconnectHardware"
            title="断开硬件"
          >断开</button>
        </div>

        <!-- 波形 Canvas（ECG 标准网格），不叠加任何覆盖文案 -->
        <div class="ppg-canvas-wrap">
          <canvas ref="ppgCanvas" class="ppg-canvas" width="640" height="180"></canvas>
        </div>

        <!-- 波形提示条：置于 canvas 下方，不遮挡波形（流错误时使用警示色） -->
        <div
          v-if="!ppgCollecting && !ppgDone"
          class="ppg-hint"
          :class="{ 'ppg-hint-error': ppgStreamError }"
        >{{ ppgStreamError || (hardwareConnected ? (ppgPreviewing ? '实时预览中 · 波形稳定后点击开始采集' : '硬件已就绪 · 点击开始采集') : '硬件未连接 · 将生成演示波形（20s）') }}</div>

        <!-- 实时状态条 -->
        <div class="ppg-stats">
          <span class="stat">
            <span class="stat-label">采样率</span>
            <span class="stat-val">125 Hz</span>
          </span>
          <span class="stat">
            <span class="stat-label">心率</span>
            <span class="stat-val">{{ ppgStats.hr.toFixed(0) }} BPM</span>
          </span>
          <span class="stat">
            <span class="stat-label">HRV</span>
            <span class="stat-val">{{ ppgStats.hrv.toFixed(0) }} ms</span>
          </span>
          <span class="stat">
            <span class="stat-label">信号</span>
            <span class="stat-val" :class="signalClass">{{ (ppgStats.signal_bar*100).toFixed(0) }}%</span>
          </span>
        </div>

        <!-- 控制按钮 -->
        <div class="ppg-controls">
          <template v-if="!ppgCollecting && !ppgDone">
            <button class="btn btn-primary btn-block" @click="startPpg">
              <span class="mic-icon">●</span> 开始采集（{{ ppgDuration }}s）
            </button>
          </template>
          <template v-else-if="ppgCollecting">
            <p class="ppg-collecting-time">{{ ppgTimeLeft }}s 后自动停止</p>
            <button class="btn btn-ghost btn-block" @click="stopPpg">立即停止</button>
          </template>
          <template v-else>
            <button class="btn btn-primary btn-block" :disabled="ppgProcessing" @click="processPpg">
              {{ ppgProcessing ? '处理中...' : '分析波形 → 五形 ΔF' }}
            </button>
            <button class="btn btn-ghost btn-small btn-block" @click="resetPpg">重新采集</button>
          </template>
        </div>

        <!-- 分析结果 -->
        <div v-if="ppgResult" class="ppg-result">
          <div class="result-section">
            <p class="result-title">六品质连续谱</p>
            <div class="quality-bars">
              <div v-for="(v, k) in ppgResult.six_qualities" :key="k" class="quality-row">
                <span class="quality-name">{{ qualityLabel(k) }}</span>
                <div class="quality-bar"><div class="quality-fill" :style="{ width: (v*100)+'%' }"></div></div>
                <span class="quality-val">{{ v.toFixed(2) }}</span>
              </div>
            </div>
          </div>

          <div class="result-section">
            <p class="result-title">五形 ΔF 向量</p>
            <div class="deltaf-row">
              <span v-for="(v, i) in ppgResult.delta_F" :key="i" class="deltaf-item">
                <span class="deltaf-name">{{ ['木','火','土','金','水'][i] }}</span>
                <span class="deltaf-val" :class="v > 0.1 ? 'up' : v < -0.1 ? 'down' : ''">{{ v >= 0 ? '+' : '' }}{{ v.toFixed(2) }}</span>
              </span>
            </div>
            <p class="result-summary" v-if="ppgResult.summary">
              <strong>辨证：</strong>{{ ppgResult.syndrome_main || '' }}
              <span v-if="ppgResult.summary">（置信度 {{ extractConfidence(ppgResult.summary) }}）</span>
            </p>
            <p class="result-summary">
              SQI {{ ppgResult.sqi.toFixed(3) }} ({{ ppgResult.sqi_grade }}) ·
              {{ ppgResult.hr_bpm.toFixed(0) }} BPM ·
              {{ ppgResult.descriptions?.join(' · ') }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- 上传 -->
    <div class="upload-bar">
      <button class="btn btn-primary" :disabled="!hasAny" @click="upload">
        上传本次采集
      </button>
      <span v-if="!hasAny" class="upload-hint">请至少采集一项数据</span>
      <span v-else class="upload-hint active">已就绪：{{ collectSummary }}</span>
    </div>
    <p v-if="result" class="result" :class="{ 'result-success': result.startsWith('已') || result.startsWith('（演示'), 'result-error': result.startsWith('上传失败') }">
      {{ result }}
    </p>
  </section>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api/client'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const tongueName = ref('')
const voiceName = ref('')
const voiceUrl = ref('')
const recording = ref(false)
const recordTime = ref(0)
const voiceDuration = ref(0)
const voiceError = ref('')
const result = ref('')

let mediaRecorder = null
let audioChunks = []
let recordTimer = null

// ═══════════════════════════════════════════════════════════
// PPG 脉搏采集 — 硬件检测 + 后端 SSE 桥接
// 后端桥接：Python (ppg_acquisition.py) → 串口 COM3 → FastAPI SSE → 浏览器
// ═══════════════════════════════════════════════════════════
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8767'
const backendServiceOk = ref(false)   // 青囊主后端服务健康

// ── 硬件状态（从后端 /ppg/hardware-status 获取）──
const hardwareSupported = ref(true)   // 后端有桥 = 支持（不再依赖浏览器 Web Serial）
const hardwareConnected = ref(false)  // 后端检测到硬件串口 = 连接
const hardwareInfo = ref('')          // 硬件描述（如 "COM3 · CheezPPG 6ch @ 125Hz"）
const hwConnecting = ref(false)       // 连接按钮 loading 态（防重复点击 + 可见反馈）
let hardwareEventSource = null        // SSE EventSource 实例
const ppgPreviewing = ref(false)      // 连接即预览：实时波形预览中
const ppgStreamError = ref('')        // SSE/后端错误提示（渲染到覆盖层）

const ppgCanvas = ref(null)
const ppgCollecting = ref(false)
const ppgDone = ref(false)
const ppgProcessing = ref(false)
const ppgDuration = 20  // 采集时长（秒）
const ppgTimeLeft = ref(ppgDuration)
const ppgResult = ref(null)

const ppgStats = ref({ hr: 0, hrv: 0, signal_bar: 0 })

let ppgBuffer = []          // PPG 波形点（硬件模式：滚动窗口；离线模式：整段）
let ppgPeakTimes = []       // 固件搏动标记 peak=1 的时间戳（最近 10s，用于信号质量峰值规律性）
let countdownTimer = null
let offlineSecLeft = ppgDuration

const signalClass = computed(() => {
  const v = ppgStats.value.signal_bar
  if (v >= 0.5) return 'sqi-good'
  if (v >= 0.25) return 'sqi-fair'
  return 'sqi-poor'
})

// ═══════════════════════════════════════════════════════════
// ECG 标准网格 + 真实 PPG 波形渲染
// ═══════════════════════════════════════════════════════════
const ECG_SMALL_GRID = 4        // 小格 4px（≈1mm）
const ECG_BIG_GRID   = 20       // 大格 20px（≈5mm）
const GRID_COLOR_SMALL = '#E8E4DA'
const GRID_COLOR_BIG   = '#C8C3B7'

function drawPpg() {
  const canvas = ppgCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const w = canvas.width, h = canvas.height

  // 背景
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, w, h)

  // ── ECG 标准网格 ──
  // 小格（淡色）
  ctx.strokeStyle = GRID_COLOR_SMALL
  ctx.lineWidth = 0.5
  for (let x = 0; x <= w; x += ECG_SMALL_GRID) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke()
  }
  for (let y = 0; y <= h; y += ECG_SMALL_GRID) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke()
  }
  // 大格（稍深色，每 5 小格）
  ctx.strokeStyle = GRID_COLOR_BIG
  ctx.lineWidth = 0.8
  for (let x = 0; x <= w; x += ECG_BIG_GRID) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke()
  }
  for (let y = 0; y <= h; y += ECG_BIG_GRID) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke()
  }

  // 中心基线（横中线）
  ctx.strokeStyle = 'rgba(26,77,69,0.25)'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(0, h * 0.5); ctx.lineTo(w, h * 0.5); ctx.stroke()

  // ── PPG 波形曲线 ──
  const wave = ppgBuffer
  if (wave.length < 2) return

  ctx.strokeStyle = '#1A4D45'
  ctx.lineWidth = 1.8
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.beginPath()
  const step = w / (wave.length - 1)
  for (let i = 0; i < wave.length; i++) {
    const x = i * step
    const y = h * 0.5 - wave[i] * h * 0.38
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
  }
  ctx.stroke()

  // ── 标注：PPG / 采样率 / 时长 ──
  ctx.font = '10px "SF Mono", Consolas, monospace'
  ctx.fillStyle = 'rgba(26,77,69,0.55)'
  ctx.fillText('PPG  125Hz', 8, 14)
  ctx.fillText(`HRV ${ppgStats.value.hrv}ms`, w - 82, 14)
}

// ═══════════════════════════════════════════════════════════
// 后端服务健康检测 + 硬件状态检测（都从青囊主后端拉）
// ═══════════════════════════════════════════════════════════
async function checkServices() {
  try {
    const res = await fetch(`${API_BASE}/health`, { method: 'GET', signal: AbortSignal.timeout(3000) })
    backendServiceOk.value = res.ok
  } catch {
    backendServiceOk.value = false
  }
  // 顺便拉硬件状态
  await checkHardwareStatus()
}

async function checkHardwareStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/ppg/hardware-status`, {
      signal: AbortSignal.timeout(25000)
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const d = await res.json()
    // 硬件在线 = 后端能枚举串口 + 能连上
    hardwareConnected.value = !!d.ok && !!d.connect_ok && !!d.stream_ok
    if (hardwareConnected.value) {
      const mode = d.stream_mode === 'cheez' ? 'CheezPPG 6ch'
                 : d.stream_mode === 'adc' ? 'Pulsesensor 1ch'
                 : 'PPG'
      const fs = d.stream_rate ? Math.round(d.stream_rate) : (d.stream_mode === 'cheez' ? 125 : 250)
      hardwareInfo.value = `${d.default_port || 'COM?'} · ${mode} @ ${fs}Hz`
    } else if (d.ok && d.port_count > 0) {
      // 串口存在但没数据流 → 提示
      hardwareInfo.value = `${d.default_port} · 检测中（请确保硬件已戴好）`
    } else if (d.ok) {
      // 后端正常但无可用串口 → 明确告知，避免“点击无反应”错觉
      hardwareInfo.value = '未检测到串口设备（请插入硬件后重试）'
    } else {
      hardwareInfo.value = ''
    }
    // 页面加载/连接成功后自动建立预览流：实时展示设备波形（未采集/未完成/未预览时）
    if (hardwareConnected.value && !ppgCollecting.value && !ppgDone.value && !ppgPreviewing.value) {
      startPreviewStream()
    }
    return hardwareConnected.value
  } catch (e) {
    // 后端不可达 / 接口超时 / HTTP 非 200：必须给出可见反馈，否则表现为“点击无反应”
    hardwareConnected.value = false
    hardwareInfo.value = '检测失败（后端服务不可达或超时）'
    ppgStreamError.value = '无法连接后端服务，请确认青囊主后端已启动'
    console.warn('[HW] checkHardwareStatus failed:', e)
    return false
  }
}

// ═══════════════════════════════════════════════════════════
// 手动触发硬件检测按钮（用户想刷新）
// ═══════════════════════════════════════════════════════════
async function connectHardware() {
  if (hwConnecting.value) return   // 防重复点击
  hwConnecting.value = true
  hardwareInfo.value = '⏳ 检测中...'
  ppgStreamError.value = ''
  try {
    // checkHardwareStatus 检测到硬件已连接时会自动建立预览流（未采集/未完成/未预览时）
    const connected = await checkHardwareStatus()
    return connected
  } finally {
    hwConnecting.value = false
  }
}

async function disconnectHardware() {
  // 先关 SSE + 通知后端释放串口，确保用户可安全拔线
  closePpgStream()
  try {
    await fetch(`${API_BASE}/api/v1/ppg/disconnect`, {
      method: 'POST',
      signal: AbortSignal.timeout(5000),
    })
  } catch {
    // 后端不可达时忽略；前端状态仍置为断开
  }
  clearInterval(countdownTimer)
  countdownTimer = null
  hardwareConnected.value = false
  hardwareInfo.value = ''
  ppgPreviewing.value = false
  ppgCollecting.value = false
  ppgDone.value = false
  ppgResult.value = null
  ppgBuffer = []
  ppgPeakTimes = []
  ppgStats.value = { hr: 0, hrv: 0, signal_bar: 0 }
  ppgStreamError.value = ''
  drawPpg()
}

// ═══════════════════════════════════════════════════════════
// 硬件 PPG 归一化（通用：后端 SSE 推的原始值 → -1..1）
// ═══════════════════════════════════════════════════════════
let HW_WINDOW = 1250  // 10s 滚动窗口（init 帧可更新为固件实际 fs×10）

// ═══════════════════════════════════════════════════════════
// 信号质量评估（替代旧"50 点峰谷跨度/200"纯幅度公式）
// 旧公式缺陷：手指活动产生大幅运动伪差 → 跨度大 → 误判 100%；
//             稳定接触幅度小（filtered 典型几十）→ 只有 30% 左右。
// 新公式：以波形周期性为主，峰值规律性/HR 合理性为辅，幅度仅作接触存在性门槛：
//   periodicity  最近 2s 归一化自相关峰值（滞后 0.4~1.5s ≈ 40~150bpm）：稳定波形高、伪差低
//   peakScore    最近 10s 固件 peak=1 帧数（期望 6~15 ≈ 36~90bpm）：稳定规律、活动紊乱/缺失
//   hrScore      HR 40~180bpm 正常，0/异常降权
//   ampFactor    最近 50 点跨度/200：只判断"是否接触"，稳定小幅也给基线分
// ═══════════════════════════════════════════════════════════
function computeSignalQuality() {
  const n = ppgBuffer.length
  if (n < 100) return 0

  // ── 1) 周期性：最近 2s（250 点）归一化自相关峰值 ──
  const fs = Math.round(HW_WINDOW / 10) || 125
  const W = Math.min(250, n)
  const slice = ppgBuffer.slice(-W)
  const mean = slice.reduce((a, b) => a + b, 0) / W
  const x = slice.map(v => v - mean)
  let sxx = 0
  for (let i = 0; i < W; i++) sxx += x[i] * x[i]
  let periodicity = 0
  if (sxx > 1e-6) {
    const tMin = Math.max(2, Math.round(0.4 * fs))
    const tMax = Math.min(Math.round(1.5 * fs), W - 2)
    let best = 0
    for (let tau = tMin; tau <= tMax; tau++) {
      let num = 0, syy = 0
      for (let i = 0; i < W - tau; i++) {
        num += x[i] * x[i + tau]
        syy += x[i + tau] * x[i + tau]
      }
      const r = num / Math.sqrt(sxx * syy + 1e-12)
      if (r > best) best = r
    }
    periodicity = Math.max(0, Math.min(1, (best - 0.15) / 0.55))
  }

  // ── 2) 峰值规律性（最近 10s 内 peak=1 帧数，期望 6~15 ≈ 36~90bpm）──
  const pc = ppgPeakTimes.length
  let peakScore
  if (pc >= 6 && pc <= 15) peakScore = 1
  else if (pc > 15) peakScore = Math.max(0, 1 - (pc - 15) / 15)
  else peakScore = pc / 6

  // ── 3) HR 合理性 ──
  const hr = ppgStats.value.hr
  const hrScore = hr >= 40 && hr <= 180 ? 1 : hr > 0 ? 0.5 : 0

  // ── 4) 幅度存在性（仅作接触门槛）──
  const recent = ppgBuffer.slice(-Math.min(50, n))
  let mn = Infinity, mx = -Infinity
  for (const v of recent) { if (v < mn) mn = v; if (v > mx) mx = v }
  const span = mx - mn
  const ampFactor = span < 10 ? 0 : Math.min(1, span / 200)

  const s = 0.40 * periodicity + 0.30 * peakScore + 0.20 * hrScore + 0.10 * ampFactor
  return Math.max(0, Math.min(1, s))
}

function normalizeHwBuffer(arr) {
  if (!arr.length) return []
  let mn = Infinity, mx = -Infinity
  for (const v of arr) { if (v < mn) mn = v; if (v > mx) mx = v }
  // 全常量缓冲（如后端误推全 0）：画中线，避免整段压在底部造成"空白"观感
  if (mx === mn) return arr.map(() => 0)
  const range = mx - mn
  return arr.map(v => 2 * (v - mn) / range - 1)
}

// ═══════════════════════════════════════════════════════════
// 开始采集（分支：后端检测到硬件 → SSE，否则 → offline）
// ═══════════════════════════════════════════════════════════
async function startPpg() {
  ppgResult.value = null
  ppgDone.value = false

  if (hardwareConnected.value) {
    startSseCollect()   // 复用预览流本地记录：示波不中断
  } else {
    ppgBuffer = []
    ppgPeakTimes = []
    ppgStats.value = { hr: 0, hrv: 0, signal_bar: 0 }
    closePpgStream()   // 确保无残留预览流
    startOfflineCollect()
  }
}

// ═══════════════════════════════════════════════════════════
// SSE 流通用关闭：关闭 EventSource（采集/预览/断开通用）
// ═══════════════════════════════════════════════════════════
function closePpgStream() {
  if (hardwareEventSource) {
    hardwareEventSource.close()
    hardwareEventSource = null
  }
}

// ═══════════════════════════════════════════════════════════
// SSE 事件绑定（采集/预览共用）：数据帧示波 + init 帧更新窗口 + done 帧收尾（仅记录流触发）
// ═══════════════════════════════════════════════════════════
function bindStreamHandlers({ preview }) {
  const es = hardwareEventSource
  let frameCount = 0

  es.onmessage = (ev) => {
    try {
      const d = JSON.parse(ev.data)
      if (d.type === 'init') {
        console.log('[SSE] init:', d.mode, d.fs, d.port)
        HW_WINDOW = d.fs * 10
        return
      }
      if (d.type === 'data') {
        ppgBuffer.push(d.wave)
        if (ppgBuffer.length > HW_WINDOW) ppgBuffer.shift()

        if (d.hr !== undefined && d.hr !== null) ppgStats.value.hr = d.hr
        if (d.hrv !== undefined && d.hrv !== null) ppgStats.value.hrv = d.hrv

        // 记录固件搏动标记（peak=1）时间戳：供信号质量峰值规律性统计（最近 10s）
        if (d.peak === 1) {
          ppgPeakTimes.push(Date.now())
          while (ppgPeakTimes.length && Date.now() - ppgPeakTimes[0] > 10000) ppgPeakTimes.shift()
        }

        // 信号质量：周期性(自相关) + 峰值规律性 + HR 合理性 + 幅度存在性（替代旧纯幅度公式）
        ppgStats.value.signal_bar = computeSignalQuality()

        frameCount++
        if (frameCount % 2 === 0) drawPpgHw()
      }
      if (d.type === 'done') {
        console.log('[SSE] done. total:', d.total)
        // 以后端 done 帧为采集完成基准收尾（倒计时仅作展示）
        if (!preview) finishCollectByDone()
      }
      if (d.error) {
        console.warn('[SSE] error:', d.error)
        ppgStreamError.value = d.error
      }
    } catch (e) {
      console.warn('[SSE] parse fail:', e)
    }
  }

  es.onerror = () => {
    console.warn('[SSE] error/closed')
    // 采集模式异常断开（未收到 done）：兜底收尾，避免卡在采集中
    if (!preview && ppgCollecting.value) finishCollectByDone()
  }
  es.onopen = () => console.log('[SSE] connected')
}

// ═══════════════════════════════════════════════════════════
// 连接即预览：建立无限预览流（?preview=1），实时展示设备波形
// 用户放手指看波形稳定后，点「开始采集」本地记录（复用本流，不中断）
// ═══════════════════════════════════════════════════════════
function startPreviewStream() {
  closePpgStream()
  const url = `${API_BASE}/api/v1/ppg/stream?preview=1`
  console.log('[SSE] preview connecting:', url)
  hardwareEventSource = new EventSource(url)
  ppgPreviewing.value = true
  ppgBuffer = []
  ppgPeakTimes = []
  ppgStats.value = { hr: 0, hrv: 0, signal_bar: 0 }
  drawPpg()   // 先画出 ECG 网格（等首帧数据到达再叠加波形）
  bindStreamHandlers({ preview: true })
}

// ═══════════════════════════════════════════════════════════
// 采集完成收尾（幂等）：由倒计时归零 / 手动停止触发（预览流无 done 帧）
// ═══════════════════════════════════════════════════════════
function finishCollectByDone() {
  if (!ppgCollecting.value) return
  stopPpg()
}

// ═══════════════════════════════════════════════════════════
// 硬件采集：复用当前预览流本地记录（SSE 持续推流，不切换流）
// 后端无需经历 停旧流→嗅探→DTR 复位 的冷启动，示波连续不中断；
// 采集数据 = 预览流累积的 ppgBuffer（10s 滚动窗），倒计时归零/手动停止时关流收尾
// ═══════════════════════════════════════════════════════════
function startSseCollect() {
  // 复用当前预览流（不关流、不清空示波缓冲）；若当前无预览流（如 reset 后）则新建一条 preview 流
  if (!hardwareEventSource) startPreviewStream()

  ppgCollecting.value = true
  ppgPreviewing.value = false

  // 倒计时（预览流无 done 帧，采集收尾由倒计时归零 / 手动停止触发）
  let secLeft = ppgDuration
  ppgTimeLeft.value = secLeft
  countdownTimer = setInterval(() => {
    secLeft--
    ppgTimeLeft.value = Math.max(0, secLeft)
    if (secLeft <= 0) finishCollectByDone()
  }, 1000)
}

/** 硬件模式示波：滚动窗口 + 归一化 + ECG 网格 */
function drawPpgHw() {
  const canvas = ppgCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const w = canvas.width, h = canvas.height

  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, w, h)
  ctx.strokeStyle = '#E8E4DA'; ctx.lineWidth = 0.5
  for (let x = 0; x <= w; x += 4) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke() }
  for (let y = 0; y <= h; y += 4) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke() }
  ctx.strokeStyle = '#C8C3B7'; ctx.lineWidth = 0.8
  for (let x = 0; x <= w; x += 20) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke() }
  for (let y = 0; y <= h; y += 20) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke() }
  ctx.strokeStyle = 'rgba(26,77,69,0.25)'; ctx.lineWidth = 1
  ctx.beginPath(); ctx.moveTo(0, h * 0.5); ctx.lineTo(w, h * 0.5); ctx.stroke()

  if (ppgBuffer.length < 2) return

  // 显示窗口：取最近 2s（而非整个 10s 缓冲），单拍脉搏波形态（上升支/主峰/重搏波）进一步放大；
  // 85bpm 时每拍约 0.7s ≈ 220px，窗口内约 2~3 拍，单拍细节更清晰
  const fs = Math.round(HW_WINDOW / 10) || 125
  const VISIBLE_SEC = 2
  const winLen = Math.min(ppgBuffer.length, fs * VISIBLE_SEC)
  const norm = normalizeHwBuffer(ppgBuffer.slice(-winLen))
  const step = w / (norm.length - 1)
  const baseY = h * 0.52   // 基线略下移，顶部留出峰值标记空间
  const amp = h * 0.40     // 垂直幅度比原 0.38 稍大，波形更饱满

  // 预计算波形坐标（峰值标记复用）
  const xs = new Array(norm.length), ys = new Array(norm.length)
  for (let i = 0; i < norm.length; i++) {
    xs[i] = i * step
    ys[i] = baseY - norm[i] * amp
  }
  const trace = (style, width) => {
    ctx.strokeStyle = style; ctx.lineWidth = width
    ctx.lineJoin = 'round'; ctx.lineCap = 'round'
    ctx.beginPath()
    for (let i = 0; i < norm.length; i++) {
      if (i === 0) ctx.moveTo(xs[i], ys[i]); else ctx.lineTo(xs[i], ys[i])
    }
    ctx.stroke()
  }
  // 双层描边：半透明宽底晕染 + 高对比主线条，增强波形层次与对比度
  trace('rgba(26,77,69,0.16)', 6)
  trace('#1A4D45', 2)

  // 峰值标记 + 心动周期分隔线（自适应阈值 = 窗口最大峰的 50%，最小峰间距 0.3s 防重搏波误判）
  let peakMax = 0
  for (let i = 0; i < norm.length; i++) if (norm[i] > peakMax) peakMax = norm[i]
  const peakTh = peakMax * 0.5
  const minGap = Math.round(fs * 0.3)
  let lastPeak = -minGap
  for (let i = 1; i < norm.length - 1; i++) {
    if (norm[i] > peakTh && norm[i] >= norm[i - 1] && norm[i] > norm[i + 1] && (i - lastPeak) >= minGap) {
      lastPeak = i
      ctx.strokeStyle = 'rgba(224,82,60,0.28)'; ctx.lineWidth = 1
      ctx.setLineDash([3, 4])
      ctx.beginPath(); ctx.moveTo(xs[i], 4); ctx.lineTo(xs[i], h - 4); ctx.stroke()
      ctx.setLineDash([])
      ctx.fillStyle = '#E0523C'
      ctx.beginPath(); ctx.arc(xs[i], ys[i] - 4, 3, 0, Math.PI * 2); ctx.fill()
    }
  }

  ctx.font = '10px "SF Mono", Consolas, monospace'
  ctx.fillStyle = 'rgba(26,77,69,0.55)'
  ctx.fillText('HW · SSE', 8, 14)
  ctx.fillText(`${ppgBuffer.length} pts · ${VISIBLE_SEC}s`, w - 118, 14)
}

// ═══════════════════════════════════════════════════════════
// 采集停止 / 处理 / 重置
// ═══════════════════════════════════════════════════════════
async function stopPpg() {
  clearInterval(countdownTimer)
  countdownTimer = null
  closePpgStream()               // 关闭 SSE（采集/预览通用），通知后端停止推流
  ppgCollecting.value = false
  ppgPreviewing.value = false
  ppgDone.value = true
  drawPpg()
}

async function processPpg() {
  ppgProcessing.value = true

  // 硬件模式：buffer 里是真实 AD 值 → 算 HR/VHRV + 真实波形落库
  if (hardwareConnected.value && ppgBuffer.length > 100) {
    const norm = normalizeHwBuffer(ppgBuffer)
    // 用 init 帧记录的固件实际采样率（HW_WINDOW = fs×10）估算 HR，而非硬编码 125
    const fs = Math.round(HW_WINDOW / 10) || 125
    const hrEst = estimateHrFromWave(norm, fs)
    ppgStats.value.hr = hrEst.hr
    ppgStats.value.hrv = hrEst.hrv
    ppgResult.value = mockPpgPipeline()
    ppgResult.value._hardwareSource = true
    ppgResult.value._sampleCount = ppgBuffer.length
    // 关键：把采集到的真实波形序列化进结果，随 /ppg/upload 提交落库
    ppgResult.value.ppg_wave = ppgBuffer.slice()
  } else {
    ppgResult.value = mockPpgPipeline()
    ppgResult.value._offlineFallback = true
  }
  ppgProcessing.value = false
}

function resetPpg() {
  clearInterval(countdownTimer)
  countdownTimer = null
  closePpgStream()               // 关闭 SSE，释放串口

  ppgCollecting.value = false
  ppgPreviewing.value = false
  ppgDone.value = false
  ppgResult.value = null
  ppgBuffer = []
  ppgPeakTimes = []
  ppgStats.value = { hr: 0, hrv: 0, signal_bar: 0 }
  ppgStreamError.value = ''
  drawPpg()
}

/** 从 PPG 波形估算 HR（自相关法简化版） */
function estimateHrFromWave(arr, sampleRate) {
  // 找峰值间隔 → HRV
  const peaks = []
  const threshold = 0.4
  let lastPeakIdx = -100
  for (let i = 1; i < arr.length - 1; i++) {
    if (arr[i] > threshold && arr[i] > arr[i-1] && arr[i] > arr[i+1] && (i - lastPeakIdx) > sampleRate * 0.3) {
      peaks.push(i)
      lastPeakIdx = i
    }
  }
  if (peaks.length < 2) return { hr: 72, hrv: 0 }
  const intervals = []
  for (let i = 1; i < peaks.length; i++) {
    intervals.push((peaks[i] - peaks[i-1]) / sampleRate * 1000)  // ms
  }
  const avg = intervals.reduce((a,b) => a+b, 0) / intervals.length
  const hrv = Math.round(intervals.reduce((a,b) => a + (b-avg)**2, 0) / intervals.length ** 0.5)
  const hr = Math.round(60000 / avg)
  return { hr, hrv }
}

// ═══════════════════════════════════════════════════════════
// 一次性合成完整 PPG 波形（硬件未连接时的真实曲线模拟）
// ═══════════════════════════════════════════════════════════
const PPG_SAMPLE_RATE = 125   // 采样率 Hz
const PPG_HR = 72             // 心率 bpm

/**
 * 合成一段"看起来像真实 PPG"的波形
 * 每个心动周期：上升支 → 主峰 → 降中峡 → 重搏波
 * 叠加轻微噪声 + 基线漂移，让曲线有真实感
 */
function synthesizePpgWaveform(durationSec, hr = PPG_HR, sampleRate = PPG_SAMPLE_RATE) {
  const totalPoints = durationSec * sampleRate
  const periodSec = 60 / hr                  // 每拍周期（秒）
  const periodPoints = Math.round(periodSec * sampleRate)
  const out = new Float32Array(totalPoints)

  // 基线漂移（非常慢的正弦）
  const drift = new Float32Array(totalPoints)
  for (let i = 0; i < totalPoints; i++) drift[i] = Math.sin(i * 2 * Math.PI / totalPoints * 1.5) * 0.06

  for (let i = 0; i < totalPoints; i++) {
    const phase = ((i % periodPoints) / periodPoints)   // 0..1 每拍内相位
    let v = 0

    // ── PPG 单拍形态（基于 Heusden 模型）──
    // 上升支：陡
    if (phase < 0.15) {
      v = Math.pow(phase / 0.15, 1.8) * 0.82
    }
    // 主峰回落
    else if (phase < 0.32) {
      v = 0.82 - Math.pow((phase - 0.15) / 0.17, 0.9) * 0.55
    }
    // 降中峡（主波结束）
    else if (phase < 0.48) {
      v = 0.27 - Math.pow((phase - 0.32) / 0.16, 1.2) * 0.15
    }
    // 重搏波（后舒张期小峰）
    else if (phase < 0.68) {
      v = 0.12 * Math.sin(Math.PI * (phase - 0.48) / 0.2) - 0.04
    }
    // 后基线
    else {
      v = -0.04 + (phase - 0.68) * 0.05
    }

    // 每拍之间的心率微变（RR 间隔±3%抖动）
    const beatPhase = Math.floor(i / periodPoints)
    const jitter = Math.sin(beatPhase * 0.7) * 0.03
    v += jitter

    // 轻微高频噪声（模拟皮肤-传感器耦合）
    v += (Math.random() - 0.5) * 0.015

    // 叠加基线漂移
    v += drift[i]

    out[i] = v
  }

  // 归一化到 -0.9..0.9（留出网格边界）
  let mn = Infinity, mx = -Infinity
  for (const v of out) { if (v < mn) mn = v; if (v > mx) mx = v }
  const range = mx - mn || 1
  for (let i = 0; i < out.length; i++) {
    out[i] = 1.8 * (out[i] - mn) / range - 0.9
  }

  return Array.from(out)
}

function startOfflineCollect() {
  ppgCollecting.value = true

  // 一次性合成 20s 完整 PPG 波形（不是 RAF 实时滚动）
  ppgBuffer = synthesizePpgWaveform(ppgDuration)

  // 计算统计值
  ppgStats.value = {
    hr: PPG_HR,
    hrv: Math.round(38 + Math.random() * 8),    // ms
    signal_bar: 0.82,                            // 信号质量
  }

  // 倒计时（纯 UX，让用户知道"采集中"）
  offlineSecLeft = ppgDuration
  ppgTimeLeft.value = ppgDuration
  countdownTimer = setInterval(() => {
    offlineSecLeft--
    ppgTimeLeft.value = offlineSecLeft
    if (offlineSecLeft <= 0) stopPpg()
  }, 1000)

  // 直接渲染完整波形（不需要 RAF 动画循环）
  drawPpg()
}

// ═══════════════════════════════════════════════════════════
// 前端 fallback PPG→ΔF 流水线（后端完全不可达时）
// ═══════════════════════════════════════════════════════════
function mockPpgPipeline() {
  const hr = ppgStats.value.hr || 72
  const hrv = ppgStats.value.hrv || 40
  const sqi = 0.55 + ppgStats.value.signal_bar * 0.35

  const six_qualities = {
    coarse_score:   clamp01(0.55 + (hr - 60) * 0.005),
    hard_score:     clamp01(0.48 + Math.sin(Date.now() * 0.001) * 0.08),
    rate_score:     clamp01((hr - 40) / 80),
    smooth_score:   clamp01(0.6 + sqi * 0.25 - hrv / 200),
    depth_score:    clamp01(0.5 + Math.sin(Date.now() * 0.0007) * 0.1),
    strength_score: clamp01(0.55 + sqi * 0.2),
  }
  const W = {
    coarse_score:[0,0.4,0.3,0,0], hard_score:[0.5,0,0,0.4,0],
    rate_score:[0,0.4,0,0,0], smooth_score:[0,0,0,0,0.6],
    depth_score:[0,0.2,0,0,0], strength_score:[0,0.3,0.3,0,0],
  }
  const delta_F = [0,0,0,0,0]
  for (const [k, val] of Object.entries(six_qualities)) {
    const dev = clamp1((val - 0.5) * 2)
    W[k].forEach((w, i) => { delta_F[i] += dev * w })
  }
  delta_F.forEach((_, i) => delta_F[i] = clamp1(delta_F[i]))

  const names = ['木','火','土','金','水']
  const desc = []
  delta_F.forEach((v, i) => {
    if (v > 0.2) desc.push(`${names[i]} ↑ (+${v.toFixed(2)})`)
    else if (v < -0.2) desc.push(`${names[i]} ↓ (${v.toFixed(2)})`)
  })
  if (!desc.length) desc.push('五形均在正常范围')

  return {
    delta_F, six_qualities, descriptions: desc,
    sqi, sqi_grade: sqi >= 0.75 ? '优秀' : sqi >= 0.5 ? '可用' : '差',
    hr_bpm: hr, hrv_ms: hrv,
    syndrome_main: '（演示模式）',
    summary: '演示模式，无真实辨证结果',
  }
}
function clamp01(v) { return Math.min(1, Math.max(0, v)) }
function clamp1(v) { return Math.min(1, Math.max(-1, v)) }

function qualityLabel(k) {
  return {
    coarse_score: '粗↔细', hard_score: '软↔硬', rate_score: '缓↔急',
    smooth_score: '滑↔涩', depth_score: '浮↔沉', strength_score: '有力↔无力',
  }[k] || k
}

function extractConfidence(text) {
  if (!text) return ''
  const m = text.match(/置信度[\s]*(\d+)%/)
  return m ? m[1] + '%' : ''
}

// ═══════════════════════════════════════════════════════════
// 语音采集（不变）
// ═══════════════════════════════════════════════════════════
const onTongueFile = (e) => {
  const file = e.target.files?.[0]; if (file) tongueName.value = file.name
}

const startRecord = async () => {
  voiceError.value = ''
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioChunks = []; mediaRecorder = new MediaRecorder(stream)
    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data) }
    mediaRecorder.onstop = () => {
      const blob = new Blob(audioChunks, { type: 'audio/webm' })
      voiceUrl.value = URL.createObjectURL(blob)
      voiceName.value = `voice_demo.${MediaRecorder.isTypeSupported('audio/webm') ? 'webm' : 'ogg'}`
      voiceDuration.value = recordTime.value
      stream.getTracks().forEach(t => t.stop()); mediaRecorder = null
    }
    mediaRecorder.start(); recording.value = true; recordTime.value = 0
    recordTimer = setInterval(() => { recordTime.value++ }, 1000)
  } catch (err) {
    voiceError.value = err.name === 'NotAllowedError' ? '麦克风权限被拒绝' : `无法启动录音：${err.message}`
    voiceName.value = 'voice_demo.webm（演示）'
  }
}
const stopRecord = () => {
  if (mediaRecorder && recording.value) mediaRecorder.stop()
  recording.value = false; clearInterval(recordTimer); recordTimer = null
}
const resetRecord = () => {
  stopRecord(); voiceName.value = ''; voiceUrl.value = ''
  voiceDuration.value = 0; recordTime.value = 0; voiceError.value = ''
}

// ═══════════════════════════════════════════════════════════
// 上传 / 通用
// ═══════════════════════════════════════════════════════════
const hasAny = computed(() => !!(tongueName.value || voiceName.value || ppgDone.value))
const collectSummary = computed(() => {
  const parts = []
  if (tongueName.value) parts.push('体态照片')
  if (voiceName.value) parts.push(`语音样本(${formatTime(voiceDuration.value)})`)
  if (ppgDone.value) parts.push(`脉搏采集(SQI ${ppgResult.value?.sqi?.toFixed(2) || '—'})`)
  return parts.join(' + ')
})
function formatTime(seconds) {
  const m = Math.floor(seconds / 60), s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
const upload = async () => {
  result.value = ''
  let okCount = 0, failCount = 0
  const errors = []

  // 1. PPG — 调青囊后端 /api/v1/ppg/upload（真实落库）
  if (ppgDone.value && ppgResult.value && !ppgResult.value._offlineFallback) {
    try {
      const r = await api.post('/api/v1/ppg/upload', {
        sqi: ppgResult.value.sqi ?? 75,
        delta_f: ppgResult.value.delta_f ?? ppgResult.value.deltaF ?? {},
        v_obs: ppgResult.value.v_obs ?? {},
        ppg_wave: ppgResult.value.ppg_wave ?? null,
        syndrome_hint: ppgResult.value.syndrome_hint ?? null,
      })
      okCount++
    } catch (e) {
      failCount++; errors.push(`PPG: ${e.response?.data?.detail || e.message}`)
    }
  }

  // 2. 体态/语音 — 当前无后端端点，保留本地（不再调 obs/multimodal）
  const localParts = []
  if (tongueName.value) localParts.push('体态照片')
  if (voiceName.value) localParts.push(`语音样本(${formatTime(voiceDuration.value)})`)

  const msgs = []
  if (okCount) msgs.push(`${okCount} 项已同步后端`)
  if (localParts.length) msgs.push(`${localParts.join('、')} 暂存本地`)
  if (failCount) msgs.push(`${failCount} 项失败: ${errors.join('; ')}`)

  result.value = msgs.join(' · ') || '没有数据可上传'
}

onMounted(() => {
  drawPpg()   // 初始绘制 ECG 网格（硬件未连/未预览时示波区也有标准网格）
  checkServices()
})
onBeforeUnmount(() => {
  stopRecord(); resetPpg()
  if (voiceUrl.value) URL.revokeObjectURL(voiceUrl.value)
})
</script>

<style scoped>
.grid { display: grid; gap: 16px; margin-top: 16px; }
.grid-3 { grid-template-columns: 1fr 1fr 1fr; }

/* ======== 体态照片 ======== */
.file-upload {
  display: block; border: 2px dashed var(--ink-line); border-radius: var(--radius-md);
  padding: 28px 16px; text-align: center; cursor: pointer; color: var(--ink-tertiary);
  font-size: 14px; transition: all 0.2s; background: var(--qingnang-paper);
}
.file-upload:hover { border-color: var(--qingnang-spirit); color: var(--qingnang-emerald); background: rgba(46,125,106,0.06); }
.file-selected { color: var(--qingnang-spirit); font-weight: 500; }

/* ======== 语音 ======== */
.voice-area { text-align: center; padding: 16px 0 8px; min-height: 140px; }
.voice-idle { display: flex; flex-direction: column; align-items: center; gap: 10px; }
.mic-icon { margin-right: 6px; color: var(--trend-up); font-size: 12px; }
.voice-recording { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.rec-pulse { width: 56px; height: 56px; border-radius: 50%; background: rgba(201,79,58,0.15); display: flex; align-items: center; justify-content: center; }
.pulse-dot { width: 16px; height: 16px; background: var(--trend-up); border-radius: 50%; animation: pulse 1s ease-in-out infinite; }
@keyframes pulse { 0%,100%{transform:scale(1);box-shadow:0 0 0 0 rgba(201,79,58,0.5);} 50%{transform:scale(1.3);box-shadow:0 0 0 12px rgba(201,79,58,0);} }
.rec-time { font-size: 28px; font-weight: 600; font-family: var(--font-mono); color: var(--qingnang-emerald); letter-spacing: 2px; }
.voice-done { display: flex; flex-direction: column; align-items: center; gap: 10px; }
.done-text { font-size: 16px; color: var(--qingnang-spirit); font-weight: 500; margin: 0; }
.done-file { font-size: 12px; color: var(--ink-tertiary); margin: -4px 0 0 0; }
.voice-player { width: 100%; max-width: 280px; height: 36px; }
.voice-error { margin-top: 10px; color: var(--trend-up); font-size: 13px; }
.hint { margin-top: 8px; font-size: 12px; color: var(--ink-tertiary); }

/* ======== PPG ======== */
.ppg-card { display: flex; flex-direction: column; }

/* 后端状态条 */
.ppg-backend-bar {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 10px; border-radius: var(--radius-sm);
  font-size: 11px; margin-bottom: 10px;
  background: var(--qingnang-paper);
}
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-ok { background: #2F8B57; box-shadow: 0 0 0 0 rgba(47,139,87,0.5); animation: breath 2s infinite; }
.dot-warn { background: #A87B3A; }
@keyframes breath { 0%,100%{box-shadow:0 0 0 0 rgba(47,139,87,0.4);} 50%{box-shadow:0 0 0 6px rgba(47,139,87,0);} }
.be-text { color: var(--ink-secondary); }
.be-sep { color: var(--ink-line); margin: 0 6px; }

.hw-connect-btn {
  margin-left: auto;
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 4px;
  border: 1px solid #2F8B57;
  background: #2F8B57;
  color: #fff;
  cursor: pointer;
  transition: all .15s;
}
.hw-connect-btn:hover { background: #247247; }
.hw-connect-btn:disabled {
  opacity: .65;
  cursor: wait;
}
.hw-connect-btn.hw-disconnect {
  border-color: #A87B3A;
  background: transparent;
  color: #A87B3A;
}
.hw-connect-btn.hw-disconnect:hover { background: #A87B3A; color: #fff; }

.ppg-canvas-wrap {
  position: relative; border-radius: var(--radius-sm); overflow: hidden;
  border: 1px solid var(--ink-line); background: #fff; margin-bottom: 12px;
}
.ppg-canvas { display: block; width: 100%; height: auto; }
.ppg-hint {
  display: flex; align-items: center; justify-content: center;
  padding: 6px 10px; margin: 0 0 12px;
  color: var(--ink-tertiary); font-size: 13px; letter-spacing: 1px;
  text-align: center; line-height: 1.5;
}
.ppg-hint-error { color: var(--trend-up); font-weight: 600; }

.ppg-stats {
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 6px; padding: 10px; background: var(--qingnang-paper);
  border-radius: var(--radius-sm); margin-bottom: 12px;
}
.ppg-stats .stat { display: flex; flex-direction: column; align-items: center; }
.ppg-stats .stat-label { font-size: 11px; color: var(--ink-tertiary); }
.ppg-stats .stat-val { font-size: 15px; font-weight: 600; color: var(--qingnang-emerald); font-family: var(--font-mono); }
.sqi-good { color: #2F8B57 !important; }
.sqi-fair { color: #A87B3A !important; }
.sqi-poor { color: var(--trend-up) !important; }

.ppg-controls { display: flex; flex-direction: column; gap: 8px; }
.btn-block { width: 100%; }
.ppg-collecting-time { text-align: center; font-size: 20px; font-weight: 600; color: var(--qingnang-emerald); font-family: var(--font-mono); letter-spacing: 2px; }

.ppg-result { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--ink-line); }
.result-section { margin-bottom: 12px; }
.result-section:last-child { margin-bottom: 0; }
.result-title { font-size: 12px; color: var(--ink-tertiary); margin-bottom: 8px; letter-spacing: 1px; text-transform: uppercase; }
.quality-bars { display: flex; flex-direction: column; gap: 5px; }
.quality-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.quality-name { width: 60px; color: var(--ink-secondary); flex-shrink: 0; }
.quality-bar { flex: 1; height: 6px; background: var(--qingnang-paper); border-radius: 3px; overflow: hidden; }
.quality-fill { height: 100%; background: linear-gradient(90deg, var(--qingnang-emerald-light), var(--qingnang-spirit)); border-radius: 3px; transition: width 0.3s; }
.quality-val { width: 36px; text-align: right; color: var(--qingnang-emerald); font-family: var(--font-mono); font-size: 11px; }
.deltaf-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 8px; }
.deltaf-item { display: flex; flex-direction: column; align-items: center; padding: 6px 4px; background: var(--qingnang-paper); border-radius: var(--radius-sm); }
.deltaf-name { font-size: 12px; color: var(--ink-tertiary); }
.deltaf-val { font-size: 14px; font-weight: 600; font-family: var(--font-mono); color: var(--qingnang-emerald); }
.deltaf-val.up { color: var(--trend-up); }
.deltaf-val.down { color: var(--wuxing-water); }
.result-summary { font-size: 12px; color: var(--ink-secondary); line-height: 1.5; }

/* ======== 按钮 ======== */
.btn { padding: 10px 20px; border-radius: var(--radius-sm); border: none; cursor: pointer; font-size: 14px; font-family: var(--font-body); transition: all 0.2s; }
.btn-primary { background: var(--qingnang-emerald); color: #fff; }
.btn-primary:hover { background: var(--qingnang-emerald-light); }
.btn-primary:disabled { background: var(--ink-line); cursor: not-allowed; }
.btn-ghost { background: transparent; color: var(--qingnang-emerald); border: 1px solid var(--qingnang-emerald); }
.btn-ghost:hover { background: var(--qingnang-paper); }
.btn-small { padding: 6px 14px; font-size: 13px; margin-top: 4px; }

/* ======== 上传区 ======== */
.upload-bar { display: flex; align-items: center; gap: 16px; margin-top: 20px; padding: 16px; background: var(--qingnang-paper); border-radius: var(--radius-md); border: 1px solid var(--ink-line); }
.upload-hint { font-size: 13px; color: var(--ink-tertiary); }
.upload-hint.active { color: var(--qingnang-spirit); font-weight: 500; }
.result { margin-top: 12px; font-size: 13px; padding: 8px 12px; border-radius: var(--radius-sm); }
.result-success { background: rgba(46, 134, 126, 0.1); color: var(--qingnang-emerald); }
.result-error { background: rgba(201, 79, 58, 0.1); color: var(--trend-up); }

/* ======== 响应式 ======== */
@media (max-width: 1100px) { .grid-3 { grid-template-columns: 1fr 1fr; } }
@media (max-width: 720px) { .grid-3 { grid-template-columns: 1fr; } }
</style>
