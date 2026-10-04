<template>
  <section class="page">
    <div class="page__header">
      <a class="back-link" @click.prevent="$router.back()" aria-label="返回">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
        返回
      </a>
      <h1>脉搏采集</h1>
    </div>
    <p class="page__desc">硬件连接 → 手指检测 → 信号稳定 → 标记采集 → 上传</p>

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
      <div v-else-if="fingerDetecting && !signalReady" class="canvas-hint hint-monitor">手指检测中 · 请将手指放在传感器上保持不动</div>
      <div v-else-if="fingerDetecting && signalReady && !ppgCollecting" class="canvas-hint hint-ok">✓ 信号稳定 · 可以标记采集</div>
      <div v-else-if="ppgCollecting" class="canvas-hint hint-monitor">采集中 · 保持手指不动 {{ ppgTimeLeft }}s</div>
      <div v-else-if="ppgDone && !ppgBuffer.length" class="canvas-hint hint-error">采集失败：无波形数据</div>
      <div v-else-if="ppgDone" class="canvas-hint hint-ok">采集完成 · 可上传</div>
      <div v-else class="canvas-hint">硬件已就绪 · 请点「手指检测」</div>
      <div v-if="ppgStreamError" class="canvas-hint hint-error">{{ ppgStreamError }}</div>
      <div v-if="uploadMsg" class="canvas-hint" :class="uploadOk ? 'hint-ok' : 'hint-error'">{{ uploadMsg }}</div>

      <!-- 实时状态 -->
      <div v-if="hardwareConnected" class="stats-row">
        <span class="stat"><span class="stat-label">心率</span><span class="stat-val">{{ (ppgStats.hr || 0).toFixed(0) }} BPM</span></span>
        <span class="stat"><span class="stat-label">HRV</span><span class="stat-val">{{ (ppgStats.hrv || 0).toFixed(0) }} ms</span></span>
        <span class="stat"><span class="stat-label">心跳检出</span><span class="stat-val" :class="hbClass">{{ (ppgStats.hb_confidence*100).toFixed(0) }}%</span></span>
      </div>

      <!-- 控制 -->
      <div class="controls">
        <template v-if="!hardwareConnected"></template>
        <template v-else-if="ppgCollecting">
          <p class="collecting-time">{{ ppgTimeLeft }}s</p>
          <button class="btn btn-ghost btn-block" @click="cancelCollect">立即停止</button>
        </template>
        <template v-else-if="ppgDone">
          <button class="btn btn-primary btn-block" :disabled="uploading || analyzing || !captureOk" @click="upload">
            {{ analyzing ? '🩺 引擎解析中...' : (uploading ? '上传中...' : (uploaded ? '再次上传' : '上传')) }}
          </button>
          <button class="btn btn-ghost btn-small btn-block" @click="resetPpg">重新采集</button>
        </template>
        <template v-else-if="fingerDetecting">
          <button class="btn btn-ghost btn-small btn-block" @click="resetPpg">停止检测</button>
          <button
            class="btn btn-primary btn-block"
            :disabled="!signalReady"
            @click="markCollect"
          >
            ● 标记采集起点（60s）
          </button>
        </template>
        <template v-else>
          <button class="btn btn-primary btn-block" @click="startFingerDetect">✓ 手指检测</button>
        </template>
      </div>

      <!-- 解析中 -->
      <div v-if="analyzing" class="analyzing-wrap">
        <div class="analyzing-spinner"></div>
        <span class="analyzing-text">后端正在调用青檬引擎做拓扑诊断，请稍候...</span>
      </div>

      <!-- 采集统计 -->
      <div v-if="ppgDone && ppgBuffer.length" class="result-card">
        <p class="result-title">采集完成</p>
        <div class="capture-stats">
          <div class="cap-row"><span>采集时长</span><span class="cap-val">{{ captureDuration.toFixed(1) }} s</span></div>
          <div class="cap-row"><span>样本数</span><span class="cap-val">{{ captureSampleCount }}</span></div>
          <div class="cap-row"><span>平均心率</span><span class="cap-val">{{ (captureHR || 0).toFixed(0) }} BPM</span></div>
          <div class="cap-row"><span>HRV</span><span class="cap-val">{{ (captureHRV || 0).toFixed(0) }} ms</span></div>
          <div class="cap-row"><span>心跳检出度</span><span class="cap-val" :class="hbClass">{{ (ppgStats.hb_confidence*100).toFixed(0) }}%</span></div>
          <div class="cap-row"><span>判定</span><span class="cap-val" :class="captureOk ? 'ok' : 'bad'">{{ captureOk ? '可上传' : '不达标' }}</span></div>
        </div>
      </div>

      <!-- 引擎诊断报告 -->
      <div v-if="analysisResult && analysisResult.status === 'analyzed'" class="report-card">
        <p class="result-title">脉诊报告 · 青檬引擎</p>
        <div class="wu-xing-bars">
          <div class="bar-row" v-for="(v, key) in (analysisResult.s_graph || {})" :key="key">
            <span class="bar-label">{{ ({wood:'木',fire:'火',earth:'土',metal:'金',water:'水'})[key] || key }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: Math.round((v || 0) * 100) + '%' }"></div>
            </div>
            <span class="bar-val">{{ Math.round((v || 0) * 100) }}</span>
          </div>
          <div v-if="!analysisResult.s_graph && analysisResult.v_obs" class="wu-xing-bars">
            <div class="bar-row" v-for="(v, key) in analysisResult.v_obs" :key="key">
              <span class="bar-label">{{ ({wood:'木',fire:'火',earth:'土',metal:'金',water:'水'})[key] || key }}</span>
              <div class="bar-track"><div class="bar-fill" :style="{ width: Math.round(v || 0) + '%' }"></div></div>
              <span class="bar-val">{{ Math.round(v || 0) }}</span>
            </div>
          </div>
        </div>
        <div v-if="analysisResult.pathologies?.length" class="pathos-row">
          <span class="pathos-label">病理标签</span>
          <span class="pathos-tag" v-for="p in analysisResult.pathologies" :key="p">{{ p }}</span>
        </div>
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

// ═══ 常量 ═══
const SIGNAL_THRESHOLD = 0.40      // 放宽：后端自检测峰值后检出率更准
const STABLE_SECONDS = 2           // 放宽：2 秒够了
const HB_THRESHOLD = 0.40          // 采集达标也放宽到 40%
const BUFFER_MAX = 750            // 前端滑动窗口上限（6s @125Hz）
const MONITOR_POLL_MS = 200       // monitor result 轮询频率

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8767'
const backendServiceOk = ref(false)
const hardwareConnected = ref(false)
const hardwareInfo = ref('')
const hwConnecting = ref(false)

const ppgCanvas = ref(null)
const fingerDetecting = ref(false)
const ppgCollecting = ref(false)
const ppgDone = ref(false)
const ppgTimeLeft = ref(60)
let _stableSince = 0
let monitorPollTimer = null
let countdownTimer = null

const captureDuration = ref(0)
const captureSampleCount = ref(0)
const captureHR = ref(0)
const captureHRV = ref(0)

const ppgStats = ref({ hr: 0, hrv: 0, hb_confidence: 0 })
const signalReady = ref(false)     // 由 pollMonitor 实时更新

const ppgBuffer = []
const ppgStreamError = ref('')

const uploading = ref(false)
const uploaded = ref(false)
const analyzing = ref(false)
const analysisResult = ref(null)
const uploadMsg = ref('')
const uploadOk = ref(false)
let _msgTimer = null

function _clearMsgTimer() {
  if (_msgTimer) { clearTimeout(_msgTimer); _msgTimer = null }
}
function _showUploadMsg(msg, ok) {
  uploadMsg.value = msg; uploadOk.value = ok
  _clearMsgTimer()
  _msgTimer = setTimeout(() => { uploadMsg.value = ''; _msgTimer = null }, 10000)
}

const hbClass = computed(() => {
  const v = ppgStats.value.hb_confidence
  if (v >= 0.55) return 'sqi-good'
  if (v >= 0.35) return 'sqi-fair'
  return 'sqi-poor'
})
const captureOk = computed(() => ppgStats.value.hb_confidence >= HB_THRESHOLD)

// ═══ Canvas 绘制（SerialPlot 风格：黑底 + 原始值 + 固定 y 轴 + 心跳节拍条）═══
let _bgCanvas = null, _bgCtx = null
let _drawDirty = false, _rafScheduled = false

// SerialPlot 风格：原始 ADC 值范围（根据硬件实测）
const Y_MIN = 150
const Y_MAX = 750
const Y_MID = (Y_MIN + Y_MAX) / 2   // 450

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
  // SerialPlot 黑底
  ctx.fillStyle = '#1a1a1e'; ctx.fillRect(0, 0, w, h)
  // 细网格（暗色）
  ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 0.4 * dpr
  ctx.beginPath()
  for (let x = 0; x <= w; x += 4 * dpr) { ctx.moveTo(x, 0); ctx.lineTo(x, h) }
  for (let y = 0; y <= h; y += 4 * dpr) { ctx.moveTo(0, y); ctx.lineTo(w, y) }
  ctx.stroke()
  // 粗网格
  ctx.strokeStyle = 'rgba(255,255,255,0.10)'; ctx.lineWidth = 0.6 * dpr
  ctx.beginPath()
  for (let x = 0; x <= w; x += 20 * dpr) { ctx.moveTo(x, 0); ctx.lineTo(x, h) }
  for (let y = 0; y <= h; y += 20 * dpr) { ctx.moveTo(0, y); ctx.lineTo(w, y) }
  ctx.stroke()
  // y 轴刻度标签（SerialPlot 显示实际 ADC 值）
  ctx.fillStyle = 'rgba(255,255,255,0.35)'; ctx.font = `${10 * dpr}px monospace`; ctx.textAlign = 'right'
  const yTicks = [Y_MIN, Y_MIN + (Y_MAX-Y_MIN)*0.25, Y_MID, Y_MIN + (Y_MAX-Y_MIN)*0.75, Y_MAX]
  for (const tv of yTicks) {
    const py = ((Y_MAX - tv) / (Y_MAX - Y_MIN)) * h
    ctx.fillText(String(Math.round(tv)), 36 * dpr, py + 3 * dpr)
    ctx.strokeStyle = 'rgba(255,255,255,0.18)'; ctx.lineWidth = 0.6 * dpr
    ctx.beginPath(); ctx.moveTo(40 * dpr, py); ctx.lineTo(w, py); ctx.stroke()
  }
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
  else { ctx.fillStyle = '#1a1a1e'; ctx.fillRect(0, 0, w, h) }

  const wave = ppgBuffer
  if (wave.length < 3) return

  // —— 降采样到 canvas 宽度 ——
  const maxPoints = Math.floor(w / dpr)
  let src = wave
  if (wave.length > maxPoints) {
    const ratio = wave.length / maxPoints
    src = new Array(maxPoints)
    for (let j = 0; j < maxPoints; j++) {
      src[j] = wave[Math.min(Math.floor(j * ratio), wave.length - 1)]
    }
  }

  // SerialPlot 映射：y = (adc - Y_MIN) / (Y_MAX - Y_MIN) * h  （注意 ADC 越大 y 越小）
  const toY = adc => ((Y_MAX - Math.max(Y_MIN, Math.min(Y_MAX, adc))) / (Y_MAX - Y_MIN)) * h
  const xStep = w / (src.length - 1)

  // —— 折线（SerialPlot 用折线，不是贝塞尔）——
  ctx.strokeStyle = '#e04b8a'                       // SerialPlot 第一条通道的洋红色
  ctx.lineWidth = 1.8 * dpr
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.beginPath()
  ctx.moveTo(0, toY(src[0]))
  for (let i = 1; i < src.length; i++) {
    ctx.lineTo(i * xStep, toY(src[i]))
  }
  ctx.stroke()

  // —— 心跳节拍条（SerialPlot 风格：底部绿色小刻度）——
  ctx.fillStyle = '#2f8b57'
  for (let i = 2; i < src.length - 2; i++) {
    const v = src[i]
    // 找局部最大值（脉搏波峰）
    if (v > src[i-1] && v > src[i-2] && v > src[i+1] && v > src[i+2] && v > Y_MID) {
      const px = i * xStep
      // 底部节拍条：从 h-8 到 h
      ctx.fillRect(px - 1 * dpr, h - 10 * dpr, 2 * dpr, 8 * dpr)
    }
  }
}

function drawPpg() {
  _drawDirty = true
  if (!_rafScheduled) { _rafScheduled = true; requestAnimationFrame(_rafDraw) }
}

// ═══ 硬件检测 ═══
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
  hwConnecting.value = true; hardwareInfo.value = '检测中...'; ppgStreamError.value = ''
  try { await checkHardwareStatus() } finally { hwConnecting.value = false }
}
async function disconnectHardware() {
  stopAllTimers()
  try { await api.post('/api/v1/ppg/collect/monitor/stop') } catch {}
  try { await fetch(`${API_BASE}/api/v1/ppg/disconnect`, { method: 'POST', signal: AbortSignal.timeout(5000) }) } catch {}
  hardwareConnected.value = false; hardwareInfo.value = ''
  resetPpg()
}

function stopAllTimers() {
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
  if (monitorPollTimer) { clearInterval(monitorPollTimer); monitorPollTimer = null }
}

// ═══ 增量波形合并 ═══
let _lastSampleCount = 0

function appendWaveIncremental(sampleCount, partialWave) {
  if (!partialWave || partialWave.length < 2) return

  if (sampleCount !== undefined && sampleCount > _lastSampleCount) {
    const delta = sampleCount - _lastSampleCount
    if (delta >= partialWave.length) {
      // 首次或丢了几次 → 全量
      ppgBuffer.length = 0
      for (let i = 0; i < partialWave.length; i++) ppgBuffer.push(partialWave[i])
    } else {
      const tail = partialWave.slice(partialWave.length - delta)
      for (let i = 0; i < tail.length; i++) ppgBuffer.push(tail[i])
      while (ppgBuffer.length > BUFFER_MAX) ppgBuffer.shift()
    }
    _lastSampleCount = sampleCount
    drawPpg()
  } else if (sampleCount === undefined) {
    ppgBuffer.length = 0
    for (let i = 0; i < partialWave.length; i++) ppgBuffer.push(partialWave[i])
    drawPpg()
  }
}

// ═══ Finger Detect → Monitor Start ═══
async function startFingerDetect() {
  if (!hardwareConnected.value || fingerDetecting.value) return
  ppgStreamError.value = ''
  try {
    const r = await api.post('/api/v1/ppg/collect/monitor/start')
    if (!r.data?.ok) { ppgStreamError.value = r.data?.error || '启动示波失败'; return }
  } catch (e) {
    ppgStreamError.value = e.response?.data?.detail || '无法启动示波'; return
  }

  fingerDetecting.value = true
  ppgCollecting.value = false; ppgDone.value = false
  _stableSince = 0
  ppgBuffer.length = 0; _lastSampleCount = 0
  ppgStats.value = { hr: 0, hrv: 0, hb_confidence: 0 }

  monitorPollTimer = setInterval(pollMonitor, MONITOR_POLL_MS)
}

// ═══ Mark Collect ═══
async function markCollect() {
  if (!fingerDetecting.value || ppgCollecting.value) return
  ppgStreamError.value = ''
  try {
    const r = await api.post('/api/v1/ppg/collect/monitor/mark')
    if (!r.data?.ok) { ppgStreamError.value = r.data?.error || '标记失败'; return }
  } catch (e) {
    ppgStreamError.value = e.response?.data?.detail || '无法标记'; return
  }
  ppgCollecting.value = true
  ppgDone.value = false
  ppgTimeLeft.value = 60
  let secLeft = 60
  countdownTimer = setInterval(() => {
    secLeft--
    ppgTimeLeft.value = Math.max(0, secLeft)
  }, 1000)
  // monitorPollTimer 继续跑（同一个 monitor，流没断！）
}

// ═══ Poll Monitor Result ═══
async function pollMonitor() {
  try {
    const res = await api.get('/api/v1/ppg/collect/monitor/result')
    const d = res.data

    if (d.status === 'error') {
      stopAllTimers()
      fingerDetecting.value = false; ppgCollecting.value = false
      ppgStreamError.value = d.error || '示波异常'
      return
    }

    // 更新 stats
    if (d.hr !== undefined && d.hr !== null) ppgStats.value.hr = d.hr
    if (d.hrv !== undefined && d.hrv !== null) ppgStats.value.hrv = d.hrv
    if (d.hb_confidence !== undefined) ppgStats.value.hb_confidence = d.hb_confidence || 0

    // 波形增量
    appendWaveIncremental(d.sample_count, d.partial_wave)

    // 信号稳定判定（仅检测阶段）
    if (fingerDetecting.value && !ppgCollecting.value) {
      const hb = ppgStats.value.hb_confidence
      const hr = ppgStats.value.hr || 0
      if (hb >= SIGNAL_THRESHOLD && hr > 30) {
        if (_stableSince === 0) _stableSince = Date.now()
        signalReady.value = (Date.now() - _stableSince) >= STABLE_SECONDS * 1000
      } else {
        _stableSince = 0
        signalReady.value = false
      }
    }

    // 采集进度
    if (ppgCollecting.value && d.collect_elapsed !== undefined) {
      ppgTimeLeft.value = Math.max(0, Math.round(60 - d.collect_elapsed))
    }

    // ready → 停止 monitor + 填完整波形 + 停轮询
    if (d.status === 'ready') {
      stopAllTimers()
      ppgCollecting.value = false
      ppgDone.value = true

      // 用 collect_wave_norm 作为采集结果
      const fullWave = d.collect_wave_norm || []
      ppgBuffer.length = 0
      for (let i = 0; i < fullWave.length; i++) ppgBuffer.push(fullWave[i])
      drawPpg()

      captureDuration.value = d.collect_elapsed || 60
      captureSampleCount.value = fullWave.length
      captureHR.value = d.hr || 0
      captureHRV.value = d.hrv || 0
      ppgStats.value = {
        hr: d.hr || 0,
        hrv: d.hrv || 0,
        hb_confidence: d.hb_confidence || 0,
      }
      // 停 monitor 释放硬件，但保留波形
      try { await api.post('/api/v1/ppg/collect/monitor/stop') } catch {}
      return
    }
  } catch (e) {
    // 网络抖动继续轮询
  }
}

async function cancelCollect() {
  stopAllTimers()
  ppgCollecting.value = false
  try { await api.post('/api/v1/ppg/collect/monitor/stop') } catch {}
  fingerDetecting.value = false
  ppgStreamError.value = '已取消采集'
  ppgBuffer.length = 0
  drawPpg()
}

function resetPpg() {
  stopAllTimers()
  ppgCollecting.value = false; ppgDone.value = false
  fingerDetecting.value = false; _stableSince = 0
  captureDuration.value = 0; captureSampleCount.value = 0; captureHR.value = 0; captureHRV.value = 0
  ppgBuffer.length = 0; _lastSampleCount = 0
  ppgStats.value = { hr: 0, hrv: 0, hb_confidence: 0 }
  ppgStreamError.value = ''
  uploaded.value = false; analyzing.value = false
  analysisResult.value = null
  _clearMsgTimer(); uploadMsg.value = ''; uploadOk.value = false
  drawPpg()
}

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
      peak_count: captureSampleCount.value,
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
onBeforeUnmount(() => { stopAllTimers(); resetPpg() })
</script>

<style scoped>
.page__header { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }

.hw-bar { display: flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: var(--radius-sm); font-size: 11px; margin-bottom: 10px; background: var(--qingnang-paper); flex-wrap: wrap; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-ok { background: #2F8B57; }
.dot-warn { background: #A87B3A; }
.hw-text { color: var(--ink-secondary); }
.hw-sep { color: var(--ink-line); }
.hw-btn { margin-left: auto; font-size: 11px; padding: 3px 10px; border-radius: 4px; border: 1px solid #2F8B57; background: #2F8B57; color: #fff; cursor: pointer; }
.hw-btn:disabled { opacity: 0.65; cursor: wait; }
.hw-btn-off { border-color: #A87B3A; background: transparent; color: #A87B3A; }

.canvas-wrap { border-radius: var(--radius-md); overflow: hidden; border: 1.5px solid #D8D3C7; background: #FAF8F3; margin-bottom: 4px; box-shadow: 0 2px 8px rgba(15,59,52,0.08); }
.ppg-canvas { display: block; width: 100%; height: auto; }
.canvas-hint { display: flex; align-items: center; justify-content: center; padding: 6px 10px; margin: 0 0 12px; color: var(--ink-tertiary); font-size: 13px; text-align: center; }
.hint-error { color: var(--trend-up); font-weight: 600; }
.hint-ok { color: var(--qingnang-emerald); font-weight: 600; }
.hint-monitor { color: var(--qingnang-emerald); font-weight: 500; animation: pulse-hint 2s ease-in-out infinite; }
@keyframes pulse-hint { 0%, 100% { opacity: 1; } 50% { opacity: 0.65; } }

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

.analyzing-wrap { display: flex; align-items: center; gap: 12px; padding: 14px 16px; margin: 12px 0; background: rgba(46,139,126,0.08); border-radius: var(--radius-md); border: 1px solid rgba(46,139,126,0.25); }
.analyzing-spinner { width: 18px; height: 18px; border: 2px solid rgba(46,139,126,0.25); border-top-color: var(--qingnang-emerald); border-radius: 50%; animation: spin 0.8s linear infinite; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }
.analyzing-text { font-size: 13px; color: var(--qingnang-emerald); font-weight: 500; }

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
