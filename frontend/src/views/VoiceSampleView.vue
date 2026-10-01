<template>
  <section class="page">
    <div class="page__header">
      <a class="back-link" @click.prevent="$router.back()" aria-label="返回">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
        返回
      </a>
      <h1>语音样本</h1>
    </div>
    <p class="page__desc">自然说话 10-20 秒 · 避免嘈杂环境</p>

    <div class="collect-wrap">
      <!-- 空闲态 -->
      <div v-if="!recording && !voiceName" class="voice-idle">
        <button class="btn btn-primary btn-big" @click="startRecord">
          <span class="mic-icon">●</span> 开始录制
        </button>
        <p class="hint">自然说话 10-20 秒 · 避免嘈杂环境</p>
      </div>

      <!-- 录制中 -->
      <div v-else-if="recording" class="voice-recording">
        <div class="rec-pulse"><span class="pulse-dot"></span></div>
        <p class="rec-time">{{ formatTime(recordTime) }}</p>
        <button class="btn btn-ghost" @click="stopRecord">停止录制</button>
      </div>

      <!-- 已录制 -->
      <div v-else class="voice-done">
        <p class="done-text">✓ 已录制</p>
        <p class="done-file">{{ voiceName }} · {{ formatTime(voiceDuration) }}</p>
        <audio controls :src="voiceUrl" class="voice-player"></audio>
        <div class="done-actions">
          <button class="btn btn-primary" @click="upload" :disabled="uploading">{{ uploading ? '上传中...' : '上传语音样本' }}</button>
          <button class="btn btn-ghost" @click="resetRecord">重新录制</button>
        </div>
      </div>

      <p v-if="voiceError" class="voice-error">⚠️ {{ voiceError }}</p>
      <p v-if="result" class="result" :class="resultOk ? 'result-success' : 'result-error'">{{ result }}</p>
    </div>
  </section>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'

const voiceName = ref('')
const voiceUrl = ref('')
const recording = ref(false)
const recordTime = ref(0)
const voiceDuration = ref(0)
const voiceError = ref('')
const uploading = ref(false)
const result = ref('')
const resultOk = ref(false)

let mediaRecorder = null
let audioChunks = []
let recordTimer = null

const startRecord = async () => {
  voiceError.value = ''
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioChunks = []
    mediaRecorder = new MediaRecorder(stream)
    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data) }
    mediaRecorder.onstop = () => {
      const blob = new Blob(audioChunks, { type: 'audio/webm' })
      voiceUrl.value = URL.createObjectURL(blob)
      voiceName.value = `voice_demo.${MediaRecorder.isTypeSupported('audio/webm') ? 'webm' : 'ogg'}`
      voiceDuration.value = recordTime.value
      stream.getTracks().forEach(t => t.stop())
      mediaRecorder = null
    }
    mediaRecorder.start()
    recording.value = true
    recordTime.value = 0
    recordTimer = setInterval(() => { recordTime.value++ }, 1000)
  } catch (err) {
    voiceError.value = err.name === 'NotAllowedError' ? '麦克风权限被拒绝' : `无法启动录音：${err.message}`
    voiceName.value = 'voice_demo.webm（演示）'
  }
}

const stopRecord = () => {
  if (mediaRecorder && recording.value) mediaRecorder.stop()
  recording.value = false
  clearInterval(recordTimer)
  recordTimer = null
}

const resetRecord = () => {
  stopRecord()
  voiceName.value = ''
  voiceUrl.value = ''
  voiceDuration.value = 0
  recordTime.value = 0
  voiceError.value = ''
  result.value = ''
}

const upload = async () => {
  if (!voiceName.value) return
  uploading.value = true
  result.value = ''
  try {
    localStorage.setItem('qn_voice_sample', JSON.stringify({ name: voiceName.value, duration: voiceDuration.value, ts: Date.now() }))
    result.value = `✓ ${voiceName.value} 已暂存本地`
    resultOk.value = true
  } catch (e) {
    result.value = `上传失败：${e.message}`
    resultOk.value = false
  } finally {
    uploading.value = false
  }
}

const formatTime = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

onBeforeUnmount(() => {
  stopRecord()
  if (voiceUrl.value) URL.revokeObjectURL(voiceUrl.value)
})
</script>

<style scoped>
.page__header { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
.collect-wrap { } /* 内容铺满 .page */

.voice-idle, .voice-recording, .voice-done {
  display: flex; flex-direction: column; align-items: center; gap: 14px;
  padding: 40px 20px; background: var(--qingnang-paper); border: 1px solid var(--ink-line); border-radius: var(--radius-md);
}
.voice-recording { padding: 50px 20px; }

.mic-icon { margin-right: 6px; color: var(--trend-up); font-size: 12px; }
.hint { font-size: 12px; color: var(--ink-tertiary); margin: 0; }

.btn { padding: 10px 20px; border-radius: var(--radius-sm); border: none; cursor: pointer; font-size: 14px; font-family: var(--font-body); transition: all 0.2s; }
.btn-big { padding: 16px 36px; font-size: 16px; }
.btn-primary { background: var(--qingnang-emerald); color: #fff; }
.btn-primary:hover { background: var(--qingnang-emerald-light); }
.btn-primary:disabled { background: var(--ink-line); cursor: not-allowed; opacity: 0.6; }
.btn-ghost { background: transparent; color: var(--qingnang-emerald); border: 1px solid var(--qingnang-emerald); }
.btn-ghost:hover { background: var(--qingnang-paper); }
.btn-block { width: 100%; }

.rec-pulse { width: 72px; height: 72px; border-radius: 50%; background: rgba(201,79,58,0.15); display: flex; align-items: center; justify-content: center; }
.pulse-dot { width: 20px; height: 20px; background: var(--trend-up); border-radius: 50%; animation: pulse 1s ease-in-out infinite; }
@keyframes pulse { 0%,100%{transform:scale(1);box-shadow:0 0 0 0 rgba(201,79,58,0.5);} 50%{transform:scale(1.3);box-shadow:0 0 0 12px rgba(201,79,58,0);} }
.rec-time { font-size: 36px; font-weight: 600; font-family: var(--font-mono); color: var(--qingnang-emerald); letter-spacing: 2px; margin: 0; }

.done-text { font-size: 18px; color: var(--qingnang-spirit); font-weight: 500; margin: 0; }
.done-file { font-size: 12px; color: var(--ink-tertiary); margin: -4px 0 0 0; }
.voice-player { width: 100%; max-width: 320px; height: 36px; }
.done-actions { display: flex; gap: 12px; margin-top: 4px; }

.voice-error { color: var(--trend-up); font-size: 13px; text-align: center; margin-top: 10px; }
.result { margin-top: 12px; font-size: 13px; padding: 8px 12px; border-radius: var(--radius-sm); }
.result-success { background: rgba(46, 134, 126, 0.1); color: var(--qingnang-emerald); }
.result-error { background: rgba(201, 79, 58, 0.1); color: var(--trend-up); }
</style>
