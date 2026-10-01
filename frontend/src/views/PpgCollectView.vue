<template>
  <section class="page">
    <div class="page__header">
      <a class="back-link" @click.prevent="$router.back()" aria-label="返回">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
        返回
      </a>
      <h1>脉搏采集</h1>
    </div>
    <p class="page__desc">采 20s 原始脉搏波形 · 心跳检出度达标即上传</p>

    <div class="collect-wrap">
      <!-- 硬件状态 -->
      <div class="hw-bar">
        <span class="dot" :class="backendServiceOk ? 'dot-ok' : 'dot-warn'"></span>
        <span class="hw-text">后端：{{ backendServiceOk ? '在线' : '离线' }}</span>
        <span class="hw-sep">·</span>
        <span class="dot" :class="hardwareConnected ? 'dot-ok' : 'dot-warn'"></span>
        <span class="hw-text">{{ hardwareConnected ? ('硬件：已连接 · ' + hardwareInfo) : '硬件：未连接' }}</span>
        <button v-if="!hardwareConnected" class="hw-btn" :disabled="hwConnecting" @click="connectHardware">
          {{ hwConnecting ? '检测中...' : '连接硬件' }}
        </button>
        <button v-else class="hw-btn hw-btn-off" @click="disconnectHardware">断开</button>
      </div>

      <!-- 波形 -->
      <div class="canvas-wrap">
        <canvas ref="ppgCanvas" class="ppg-canvas" width="640" height="180"></canvas>
      </div>
      <div v-if="!hardwareConnected" class="canvas-hint">硬件未连接 · 先点「连接硬件」</div>
      <div v-else-if="!ppgPreviewing && !ppgCollecting && !ppgDone" class="canvas-hint">点「脉象检测」开启实时示波</div>
      <div v-else-if="ppgPreviewing" class="canvas-hint hint-monitor">
        实时示波中 · 手指轻搭传感器 · 波形稳定后点击开始采集
      </div>
      <div v-else-if="ppgCollecting" class="canvas-hint hint-monitor">采集中 · 保持手指不动</div>
      <div v-if="ppgStreamError" class="canvas-hint hint-error">{{ ppgStreamError }}</div>
      <!-- 上传结果提示：在示波框下方，10s 自动消失 -->
      <div v-if="uploadMsg" class="canvas-hint" :class="uploadOk ? 'hint-ok' : 'hint-error'">{{ uploadMsg }}</div>

      <!-- 实时状态（只有在检测中/采集中才显示） -->
      <div v-if="ppgPreviewing || ppgCollecting || ppgDone" class="stats-row">
        <span class="stat"><span class="stat-label">心率</span><span class="stat-val">{{ ppgStats.hr.toFixed(0) }} BPM</span></span>
        <span class="stat"><span class="stat-label">HRV</span><span class="stat-val">{{ ppgStats.hrv.toFixed(0) }} ms</span></span>
        <span class="stat"><span class="stat-label">心跳检出</span><span class="stat-val" :class="hbClass">{{ (ppgStats.hb_confidence*100).toFixed(0) }}%</span></span>
      </div>

      <!-- 控制（三态：未检测 / 检测中 / 采集中 / 采集完成） -->
      <div class="controls">
        <template v-if="!hardwareConnected">
          <!-- 硬件没连，不显示采集相关按钮 -->
        </template>
        <template v-else-if="!ppgPreviewing && !ppgCollecting && !ppgDone">
          <button class="btn btn-primary btn-block" @click="startPreviewMonitor">
            👁 脉象检测（实时示波）
          </button>
        </template>
        <template v-else-if="ppgPreviewing">
          <button class="btn btn-primary btn-block" @click="startPpg">
            ● 开始采集（{{ ppgDuration }}s）
          </button>
          <button class="btn btn-ghost btn-small btn-block" @click="resetPpg">停止检测</button>
        </template>
        <template v-else-if="ppgCollecting">
          <p class="collecting-time">{{ ppgTimeLeft }}s 后自动停止</p>
          <button class="btn btn-ghost btn-block" @click="stopPpg">立即停止</button>
        </template>
        <template v-else>
          <button class="btn btn-primary btn-block" :disabled="uploading || analyzing || !captureOk" @click="upload">
            {{ analyzing ? '🩺 引擎解析中...' : (uploading ? '上传中...' : (uploaded ? '再次上传' : '上传')) }}
          </button>
          <button class="btn btn-ghost btn-small btn-block" @click="resetPpg">重新采集</button>
        </template>
      </div>

      <!-- 解析中加载提示 -->
      <div v-if="analyzing" class="analyzing-wrap">
        <div class="analyzing-spinner"></div>
        <span class="analyzing-text">后端正在调用青檬引擎做拓扑诊断，请稍候...</span>
      </div>

      <!-- 采集统计 -->
      <div v-if="ppgDone" class="result-card">
        <p class="result-title">采集完成</p>
        <div class="capture-stats">
          <div class="cap-row"><span>采集时长</span><span class="cap-val">{{ captureDuration.toFixed(1) }} s</span></div>
          <div class="cap-row"><span>样本数</span><span class="cap-val">{{ captureSampleCount }}</span></div>
          <div class="cap-row"><span>平均心率</span><span class="cap-val">{{ captureHR.toFixed(0) }} BPM</span></div>
          <div class="cap-row"><span>HRV</span><span class="cap-val">{{ captureHRV.toFixed(0) }} ms</span></div>
          <div class="cap-row"><span>心跳检出度</span><span class="cap-val" :class="hbClass">{{ (ppgStats.hb_confidence*100).toFixed(0) }}%</span></div>
          <div class="cap-row"><span>判定</span><span class="cap-val" :class="captureOk ? 'ok' : 'bad'">{{ captureOk ? '可上传' : '不达标' }}</span></div>
        </div>
      </div>

      <!-- 引擎诊断报告（后端返回完整报告后显示） -->
      <div v-if="analysisResult && analysisResult.status === 'analyzed'" class="report-card">
        <p class="result-title">脉诊报告 · 青檬引擎</p>

        <!-- 拓扑层五形雷达（条形图简化版） -->
        <div class="wu-xing-bars">
          <div class="bar-row" v-for="(v, key) in (analysisResult.s_graph || {})" :key="key">
            <span class="bar-label">{{ ({wood:'木',fire:'火',earth:'土',metal:'金',water:'水'})[key] || key }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: Math.round((v || 0) * 100) + '%' }"></div>
            </div>
            <span class="bar-val">{{ Math.round((v || 0) * 100) }}</span>
          </div>
          <!-- fallback: 用 v_obs -->
          <div v-if="!analysisResult.s_graph && analysisResult.v_obs" class="wu-xing-bars">
            <div class="bar-row" v-for="(v, key) in analysisResult.v_obs" :key="key">
              <span class="bar-label">{{ ({wood:'木',fire:'火',earth:'土',metal:'金',water:'水'})[key] || key }}</span>
              <div class="bar-track"><div class="bar-fill" :style="{ width: Math.round(v || 0) + '%' }"></div></div>
              <span class="bar-val">{{ Math.round(v || 0) }}</span>
            </div>
          </div>
        </div>

        <!-- 病理标签 -->
        <div v-if="analysisResult.pathologies?.length" class="pathos-row">
          <span class="pathos-label">病理标签</span>
          <span class="pathos-tag" v-for="p in analysisResult.pathologies" :key="p">{{ p }}</span>
        </div>

        <!-- 一句话诊断 -->
        <p v-if="analysisResult.diagnosis_summary" class="report-summary">{{ analysisResult.diagnosis_summary }}</p>

        <div class="report-actions">
          <router-link to="/case" class="btn btn-ghost btn-small">查看档案详情</router-link>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api/client'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8767'
const backendServiceOk = ref(false)
const hardwareConnected = ref(false)
const hardwareInfo = ref('')
const hwConnecting = ref(false)
let hardwareEventSource = null
const ppgPreviewing = ref(false)
const ppgStreamError = ref('')

const ppgCanvas = ref(null)
const ppgCollecting = ref(false)
const ppgDone = ref(false)
const ppgDuration = 20
const ppgTimeLeft = ref(ppgDuration)
let countdownTimer = null

// 采集统计（只在 stopPpg 时写入，upload 时作为 payload）
const captureDuration = ref(0)
const captureSampleCount = ref(0)
const captureHR = ref(0)
const captureHRV = ref(0)

const ppgStats = ref({ hr: 0, hrv: 0, hb_confidence: 0 })
let ppgBuffer = []
let ppgPeakTimes = []
let HW_WINDOW = 188   // 1.5s × 125Hz，init 帧会按实际 fs 覆盖

const uploading = ref(false)
const uploaded = ref(false)    // 本次采集是否已上传过（控制按钮显示"上传"/"再次上传"）
const analyzing = ref(false)   // 后端正在解析（同步等待）
const analysisResult = ref(null)  // 后端返回的完整报告
const uploadMsg = ref('')
const uploadOk = ref(false)
let _msgTimer = null           // 上传结果 10s 自动消失定时器

function _clearMsgTimer() {
  if (_msgTimer) { clearTimeout(_msgTimer); _msgTimer = null }
}
function _showUploadMsg(msg, ok) {
  uploadMsg.value = msg
  uploadOk.value = ok
  _clearMsgTimer()
  _msgTimer = setTimeout(() => { uploadMsg.value = ''; _msgTimer = null }, 10000)
}

// 心跳检出度 >= 0.65 即认为采集可靠，可上传
const HB_THRESHOLD = 0.65

const hbClass = computed(() => {
  const v = ppgStats.value.hb_confidence
  if (v >= 0.65) return 'sqi-good'
  if (v >= 0.40) return 'sqi-fair'
  return 'sqi-poor'
})
const captureOk = computed(() => ppgStats.value.hb_confidence >= HB_THRESHOLD)

// ═══ DPR 适配 + 静态网格预渲染 + rAF 合帧 ═══
let _bgCanvas = null, _bgCtx = null
let _drawDirty = false, _rafScheduled = false

function _ensureBgCanvas() {
  const canvas = ppgCanvas.value; if (!canvas) return null
  const dpr = window.devicePixelRatio || 1
  const cssW = canvas.clientWidth || canvas.width
  const cssH = canvas.clientHeight || canvas.height
  canvas.width = Math.round(cssW * dpr)
  canvas.height = Math.round(cssH * dpr)
  _bgCanvas = document.createElement('canvas')
  _bgCanvas.width = canvas.width; _bgCanvas.height = canvas.height
  _bgCtx = _bgCanvas.getContext('2d')
  const ctx = _bgCtx; const w = canvas.width; const h = canvas.height
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, w, h)
  ctx.strokeStyle = '#E8E4DA'; ctx.lineWidth = 0.5 * dpr
  ctx.beginPath()
  for (let x = 0; x <= w; x += 4 * dpr) { ctx.moveTo(x, 0); ctx.lineTo(x, h) }
  for (let y = 0; y <= h; y += 4 * dpr) { ctx.moveTo(0, y); ctx.lineTo(w, y) }
  ctx.stroke()
  ctx.strokeStyle = '#C8C3B7'; ctx.lineWidth = 0.8 * dpr
  ctx.beginPath()
  for (let x = 0; x <= w; x += 20 * dpr) { ctx.moveTo(x, 0); ctx.lineTo(x, h) }
  for (let y = 0; y <= h; y += 20 * dpr) { ctx.moveTo(0, y); ctx.lineTo(w, y) }
  ctx.stroke()
  ctx.strokeStyle = 'rgba(26,77,69,0.25)'; ctx.lineWidth = 1 * dpr
  ctx.beginPath(); ctx.moveTo(0, h * 0.5); ctx.lineTo(w, h * 0.5); ctx.stroke()
  return canvas
}

function _rafDraw() {
  _rafScheduled = false; if (!_drawDirty) return
  _drawDirty = false
  const canvas = ppgCanvas.value; if (!canvas) return
  const ctx = canvas.getContext('2d')
  const dpr = window.devicePixelRatio || 1
  const w = canvas.width, h = canvas.height
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  if (_bgCanvas) ctx.drawImage(_bgCanvas, 0, 0)
  else { ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, w, h) }
  const wave = ppgBuffer
  if (wave.length < 2) return
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.strokeStyle = '#1A4D45'; ctx.lineWidth = 1.8 * dpr; ctx.lineJoin = 'round'; ctx.lineCap = 'round'
  ctx.beginPath()
  const step = w / (wave.length - 1)
  const midY = h * 0.5, amp = h * 0.38
  for (let i = 0; i < wave.length; i++) {
    const x = i * step; const y = midY - wave[i] * amp
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
  }
  ctx.stroke()
}
function drawPpg() {
  _drawDirty = true
  if (!_rafScheduled) { _rafScheduled = true; requestAnimationFrame(_rafDraw) }
}

// ═══ 心跳检出度（唯一质量判据）═══
// 基于最近 10 秒硬件检出的 peak 事件：实际检出数 vs 期望数 + RR 间期一致性
function computeHeartbeatConfidence() {
  const now = Date.now()
  const recent = ppgPeakTimes.filter(t => now - t <= 10000)
  const n = recent.length

  if (n < 3) return 0                 // 少于 3 次 peak，无法评估
  if (n < 6) return Math.min(0.3, n / 6 * 0.3)   // 起步阶段只给到 0.3

  // RR 间期
  const ivs = []
  for (let i = 1; i < n; i++) ivs.push(recent[i] - recent[i-1])
  const meanRR = ivs.reduce((a, b) => a + b, 0) / ivs.length
  const avgHR = Math.round(60000 / meanRR)

  // 期望 peak 数（按实测 HR 推算 10s 窗口内应有多少次心跳）
  const expected = Math.max(4, Math.min(25, Math.round(avgHR / 60 * 10)))
  const detected = Math.min(n, expected + 2)
  const detectionRate = Math.min(1, detected / expected)

  // RR 间期变异系数（CV = σ/μ）—— 越小越稳定
  let variance = 0
  for (const iv of ivs) variance += (iv - meanRR) ** 2
  const cv = Math.sqrt(variance / ivs.length) / meanRR
  const consistency = Math.max(0, 1 - cv / 0.3)   // CV=0.3 → 一致性=0

  // HR 是否在生理范围内（40-180）
  const hrOk = avgHR >= 40 && avgHR <= 180 ? 1 : avgHR > 0 ? 0.5 : 0

  // 合成：检出率 50% + 稳定性 30% + HR 有效性 20%
  return Math.max(0, Math.min(1, 0.50 * detectionRate + 0.30 * consistency + 0.20 * hrOk))
}

// ═══ 后端通信 ═══
async function checkServices() {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) })
    backendServiceOk.value = res.ok
  } catch { backendServiceOk.value = false }
  await checkHardwareStatus()
}

async function checkHardwareStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/ppg/hardware-status`, { signal: AbortSignal.timeout(25000) })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const d = await res.json()
    hardwareConnected.value = !!d.ok && !!d.connect_ok && !!d.stream_ok
    if (hardwareConnected.value) {
      const mode = d.stream_mode === 'cheez' ? 'CheezPPG 6ch' : d.stream_mode === 'adc' ? 'Pulsesensor 1ch' : 'PPG'
      const fs = d.stream_rate ? Math.round(d.stream_rate) : 125
      hardwareInfo.value = `${d.default_port || 'COM?'} · ${mode} @ ${fs}Hz`
    } else if (d.ok && d.port_count > 0) hardwareInfo.value = `${d.default_port} · 检测中`
    else if (d.ok) hardwareInfo.value = '未检测到串口设备'
    else hardwareInfo.value = ''
    // 不再自动开 preview——必须用户显式点「脉象检测」按钮
    return hardwareConnected.value
  } catch (e) {
    hardwareConnected.value = false
    hardwareInfo.value = '检测失败'
    ppgStreamError.value = '无法连接后端服务'
    return false
  }
}

async function connectHardware() {
  if (hwConnecting.value) return
  hwConnecting.value = true
  hardwareInfo.value = '检测中...'
  ppgStreamError.value = ''
  try { await checkHardwareStatus() } finally { hwConnecting.value = false }
}

async function disconnectHardware() {
  closePpgStream()
  try { await fetch(`${API_BASE}/api/v1/ppg/disconnect`, { method: 'POST', signal: AbortSignal.timeout(5000) }) } catch {}
  clearInterval(countdownTimer); countdownTimer = null
  hardwareConnected.value = false; hardwareInfo.value = ''; ppgPreviewing.value = false
  ppgCollecting.value = false; ppgDone.value = false
  captureDuration.value = 0; captureSampleCount.value = 0; captureHR.value = 0; captureHRV.value = 0
  ppgBuffer = []; ppgPeakTimes = []
  ppgStats.value = { hr: 0, hrv: 0, hb_confidence: 0 }; ppgStreamError.value = ''
  drawPpg()
}

function closePpgStream() {
  if (hardwareEventSource) { hardwareEventSource.close(); hardwareEventSource = null }
}

function bindStreamHandlers() {
  const es = hardwareEventSource
  es.onmessage = (ev) => {
    try {
      const d = JSON.parse(ev.data)
      if (d.type === 'init') {
        HW_WINDOW = Math.max(100, Math.round((d.fs || 125) * 1.5))
        return
      }
      if (d.type === 'data') {
        ppgBuffer.push(d.wave)
        if (ppgBuffer.length > HW_WINDOW) ppgBuffer.shift()
        if (d.hr !== undefined) ppgStats.value.hr = d.hr
        if (d.hrv !== undefined) ppgStats.value.hrv = d.hrv
        if (d.peak === 1) {
          ppgPeakTimes.push(Date.now())
          // 只留最近 10 秒的 peak（心跳检出度窗口）
          while (ppgPeakTimes.length && Date.now() - ppgPeakTimes[0] > 10000) ppgPeakTimes.shift()
        }
        ppgStats.value.hb_confidence = computeHeartbeatConfidence()
        drawPpg()
      }
      if (d.type === 'done' && ppgCollecting.value) stopPpg()
      if (d.error) ppgStreamError.value = d.error
    } catch {}
  }
  es.onerror = () => { if (ppgCollecting.value) stopPpg() }
}

function startPreviewStream() {
  closePpgStream()
  // preview=1 无限流，不缓存 raw 波形（用户可能随时断开）
  hardwareEventSource = new EventSource(`${API_BASE}/api/v1/ppg/stream?preview=1`)
  ppgPreviewing.value = true
  ppgBuffer = []; ppgPeakTimes = []
  ppgStats.value = { hr: 0, hrv: 0, hb_confidence: 0 }
  drawPpg()
  bindStreamHandlers()
}

// 显式入口：用户点「脉象检测」
function startPreviewMonitor() {
  ppgStreamError.value = ''
  startPreviewStream()
}

// 用户点「开始采集」：关掉 preview，开 collect stream（preview=0），后端缓存完整 raw 波形
async function startPpg() {
  if (!hardwareConnected.value) return
  ppgDone.value = false
  ppgCollecting.value = true
  ppgPreviewing.value = false

  // 关掉 preview stream → 确保后端释放串口后立刻开 collect stream
  closePpgStream()
  await new Promise(r => setTimeout(r, 100))

  // preview=0 + duration=20  → collect 模式，后端缓存 raw filtered 波形
  hardwareEventSource = new EventSource(`${API_BASE}/api/v1/ppg/stream?preview=0&duration=${ppgDuration}`)
  ppgBuffer = []; ppgPeakTimes = []
  ppgStats.value = { hr: 0, hrv: 0, hb_confidence: 0 }
  drawPpg()
  bindStreamHandlers()

  let secLeft = ppgDuration; ppgTimeLeft.value = secLeft
  countdownTimer = setInterval(() => {
    secLeft--; ppgTimeLeft.value = Math.max(0, secLeft)
    captureDuration.value = ppgDuration - secLeft
    if (secLeft <= 0) stopPpg()
  }, 1000)
}

async function stopPpg() {
  clearInterval(countdownTimer); countdownTimer = null
  closePpgStream()
  ppgCollecting.value = false; ppgPreviewing.value = false
  ppgDone.value = true
  // 收尾：冻结采集统计（用 capture 期间的最新值）
  captureSampleCount.value = ppgBuffer.length
  captureHR.value = ppgStats.value.hr
  captureHRV.value = ppgStats.value.hrv
  drawPpg()
}

function resetPpg() {
  clearInterval(countdownTimer); countdownTimer = null
  closePpgStream()
  ppgCollecting.value = false; ppgPreviewing.value = false; ppgDone.value = false
  captureDuration.value = 0; captureSampleCount.value = 0; captureHR.value = 0; captureHRV.value = 0
  ppgBuffer = []; ppgPeakTimes = []
  ppgStats.value = { hr: 0, hrv: 0, hb_confidence: 0 }
  ppgStreamError.value = ''
  uploaded.value = false; analyzing.value = false
  analysisResult.value = null
  _clearMsgTimer(); uploadMsg.value = ''; uploadOk.value = false
  drawPpg()
}

// 上传：只传原始波形 + 采集统计，不传任何分析推断
// 后端负责调 qingmeng-engine 做五形分析
async function upload() {
  if (uploading.value) return
  if (!ppgBuffer.length) { _showUploadMsg('无波形数据，无法上传', false); return }
  uploading.value = true; analyzing.value = true
  _clearMsgTimer(); uploadMsg.value = ''; analysisResult.value = null
  try {
    const waveCopy = ppgBuffer.slice()
    const r = await api.post('/api/v1/ppg/upload', {
      sqi: Math.round(ppgStats.value.hb_confidence * 100),
      ppg_wave: waveCopy,
      hr_bpm: ppgStats.value.hr,
      hrv_ms: ppgStats.value.hrv,
      peak_count: ppgPeakTimes.length,
      sample_count: waveCopy.length,
      capture_duration_s: captureDuration.value,
    })
    const d = r?.data ?? r
    analysisResult.value = d
    const recId = d?.observation_id ?? d?.id
    const summary = d?.diagnosis_summary || ''
    const pathos = d?.pathologies?.length ? d.pathologies.join('·') : ''
    const suffix = recId ? ` · 记录 ${recId}` : ''
    const extra = summary ? `\n${summary}` : (pathos ? `\n病理标签：${pathos}` : '')
    _showUploadMsg(`✓ 解析完成${suffix}${extra}`, true)
    uploaded.value = true
  } catch (e) {
    analysisResult.value = null
    if (e?.response?.status === 401) {
      _showUploadMsg('上传失败：登录已失效，请重新登录', false)
    } else {
      const detail = e?.response?.data?.detail || e?.message || '请求失败'
      _showUploadMsg(`上传失败：${detail}`, false)
    }
    console.error('[ppg upload] failed:', e)
  } finally {
    uploading.value = false; analyzing.value = false
  }
}

onMounted(() => { _ensureBgCanvas(); drawPpg(); checkServices() })
onBeforeUnmount(() => { stopPpg(); resetPpg() })
</script>

<style scoped>
.page__header { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
.collect-wrap { }

.hw-bar { display: flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: var(--radius-sm); font-size: 11px; margin-bottom: 10px; background: var(--qingnang-paper); flex-wrap: wrap; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-ok { background: #2F8B57; }
.dot-warn { background: #A87B3A; }
.hw-text { color: var(--ink-secondary); }
.hw-sep { color: var(--ink-line); }
.hw-btn { margin-left: auto; font-size: 11px; padding: 3px 10px; border-radius: 4px; border: 1px solid #2F8B57; background: #2F8B57; color: #fff; cursor: pointer; }
.hw-btn:disabled { opacity: 0.65; cursor: wait; }
.hw-btn-off { border-color: #A87B3A; background: transparent; color: #A87B3A; }

.canvas-wrap { border-radius: var(--radius-sm); overflow: hidden; border: 1px solid var(--ink-line); background: #fff; margin-bottom: 4px; }
.ppg-canvas { display: block; width: 100%; height: auto; }
.canvas-hint { display: flex; align-items: center; justify-content: center; padding: 6px 10px; margin: 0 0 12px; color: var(--ink-tertiary); font-size: 13px; text-align: center; }
.hint-error { color: var(--trend-up); font-weight: 600; }
.hint-ok { color: var(--qingnang-emerald); font-weight: 600; }
.hint-monitor { color: var(--qingnang-emerald); font-weight: 500; animation: pulse-hint 2s ease-in-out infinite; }
@keyframes pulse-hint {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}

.stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; padding: 10px; background: var(--qingnang-paper); border-radius: var(--radius-sm); margin-bottom: 12px; }
.stat { display: flex; flex-direction: column; align-items: center; }
.stat-label { font-size: 11px; color: var(--ink-tertiary); }
.stat-val { font-size: 15px; font-weight: 600; color: var(--qingnang-emerald); font-family: var(--font-mono); }
.sqi-good { color: #2F8B57 !important; }
.sqi-fair { color: #A87B3A !important; }
.sqi-poor { color: var(--trend-up) !important; }

.controls { display: flex; flex-direction: column; gap: 8px; }
.collecting-time { text-align: center; font-size: 20px; font-weight: 600; color: var(--qingnang-emerald); font-family: var(--font-mono); letter-spacing: 2px; margin: 4px 0; }

.btn { padding: 10px 20px; border-radius: var(--radius-sm); border: none; cursor: pointer; font-size: 14px; font-family: var(--font-body); transition: all 0.2s; }
.btn-primary { background: var(--qingnang-emerald); color: #fff; }
.btn-primary:hover { background: var(--qingnang-emerald-light); }
.btn-primary:disabled { background: var(--ink-line); cursor: not-allowed; opacity: 0.6; }
.btn-ghost { background: transparent; color: var(--qingnang-emerald); border: 1px solid var(--qingnang-emerald); }
.btn-ghost:hover { background: var(--qingnang-paper); }
.btn-small { padding: 6px 14px; font-size: 13px; }
.btn-block { width: 100%; }

.result-card { margin-top: 16px; padding: 14px 16px; background: var(--qingnang-paper); border-radius: var(--radius-md); border: 1px solid var(--ink-line); }
.result-title { font-size: 12px; color: var(--ink-tertiary); margin: 0 0 10px; letter-spacing: 1px; }
.capture-stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 16px; margin-bottom: 10px; }
.cap-row { display: flex; justify-content: space-between; font-size: 13px; color: var(--ink-secondary); }
.cap-val { font-family: var(--font-mono); font-weight: 600; color: var(--ink-primary); }
.cap-val.ok { color: var(--qingnang-emerald); }
.cap-val.bad { color: var(--trend-up); }
.result-note { font-size: 11px; color: var(--ink-tertiary); margin: 8px 0 0; font-style: italic; }

.result { margin-top: 12px; font-size: 13px; padding: 8px 12px; border-radius: var(--radius-sm); }
.result-success { background: rgba(46, 134, 126, 0.1); color: var(--qingnang-emerald); }
.result-error { background: rgba(201, 79, 58, 0.1); color: var(--trend-up); }

/* ── 解析中 spinner ── */
.analyzing-wrap { display: flex; align-items: center; gap: 12px; padding: 14px 16px; margin: 12px 0; background: rgba(46,139,126,0.08); border-radius: var(--radius-md); border: 1px solid rgba(46,139,126,0.25); }
.analyzing-spinner { width: 18px; height: 18px; border: 2px solid rgba(46,139,126,0.25); border-top-color: var(--qingnang-emerald); border-radius: 50%; animation: spin 0.8s linear infinite; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }
.analyzing-text { font-size: 13px; color: var(--qingnang-emerald); font-weight: 500; }

/* ── 报告卡片 ── */
.report-card { margin-top: 12px; padding: 14px 16px; background: linear-gradient(135deg, #fff 0%, #f0f7f5 100%); border-radius: var(--radius-md); border: 1px solid rgba(46,139,126,0.3); }
.wu-xing-bars { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.bar-row { display: grid; grid-template-columns: 24px 1fr 36px; gap: 8px; align-items: center; }
.bar-label { font-size: 14px; font-weight: 600; color: var(--ink-primary); text-align: center; }
.bar-track { height: 10px; background: var(--ink-line); border-radius: 5px; overflow: hidden; }
.bar-fill { height: 100%; background: linear-gradient(90deg, var(--qingnang-emerald) 0%, #3FA585 100%); border-radius: 5px; transition: width 0.4s ease; }
.bar-val { font-size: 12px; font-family: var(--font-mono); color: var(--ink-secondary); text-align: right; }
.pathos-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 10px; }
.pathos-label { font-size: 11px; color: var(--ink-tertiary); margin-right: 4px; }
.pathos-tag { font-size: 11px; padding: 2px 8px; border-radius: 10px; background: rgba(201,79,58,0.1); color: var(--trend-up); border: 1px solid rgba(201,79,58,0.3); }
.report-summary { font-size: 13px; line-height: 1.6; color: var(--ink-primary); background: rgba(46,139,126,0.06); padding: 10px 12px; border-radius: 6px; border-left: 3px solid var(--qingnang-emerald); margin: 0 0 12px; }
.report-actions { display: flex; gap: 8px; }
</style>
