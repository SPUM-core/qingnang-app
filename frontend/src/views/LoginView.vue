<template>
  <section class="splash-root">
    <!-- ═══════════════════════════════════════════════════
         舞台一：启动动画（正放 8s，结尾定格青囊 Logo 落版）
         宽屏不裁切：背后海报模糊铺底 + 前景完整海报居中
         ═══════════════════════════════════════════════════ -->
    <div v-if="stage === 'video'" class="video-stage" @click="onVideoEnded">
      <div class="video-backdrop" aria-hidden="true"></div>
      <video
        ref="splashVideo"
        class="video-lead"
        :poster="splashPoster"
        autoplay muted playsinline
        preload="auto"
        @ended="onVideoEnded"
      >
        <source :src="splashVideoSrc" type="video/mp4" />
      </video>
      <span class="skip-hint">点击跳过</span>
    </div>

    <!-- ═══════════════════════════════════════════════════
         舞台二：落版（水墨背景淡入 → Logo + 登录卡片）
         ═══════════════════════════════════════════════════ -->
    <Transition name="stage">
      <div v-if="stage === 'end'" class="end-stage">
        <div class="end-bg" aria-hidden="true"></div>
        <div class="end-wash" aria-hidden="true"></div>

        <div class="end-content">
          <!-- 卡片上方：青囊横标 Logo -->
          <div class="brand-lockup" :class="{ 'lockup-in': showCard }">
            <img src="/assets/logo/icon-green.png" alt="青囊" class="lockup-icon" />
            <img src="/assets/logo/wordmark-green-70.png" alt="" class="lockup-wordmark" />
          </div>

          <!-- 玻璃态登录卡片 -->
          <Transition name="card">
            <div v-if="showCard" class="auth-card">
              <p class="card-title">{{ mode === 'login' ? '欢迎回来' : '开启你的调理旅程' }}</p>

              <!-- 登录表单 -->
              <form v-if="mode === 'login'" class="auth-form" @submit.prevent="doLogin">
                <label class="field">
                  <span>手机号</span>
                  <input v-model="phone" type="tel" placeholder="11 位手机号" maxlength="11"
                         autocomplete="tel" inputmode="numeric" />
                </label>
                <label class="field">
                  <span>密码</span>
                  <input v-model="password" type="password" placeholder="请输入密码"
                         autocomplete="current-password" />
                </label>
                <div v-if="error" class="error-hint">{{ error }}</div>
                <button class="btn btn-primary" :disabled="loading" type="submit">
                  <span v-if="loading">登录中…</span>
                  <span v-else>登 录</span>
                </button>
                <p class="switch-mode">
                  还没有账号？
                  <button type="button" class="link-btn" @click="goRegister">去注册 →</button>
                </p>
              </form>

              <!-- 注册表单 -->
              <form v-else class="auth-form" @submit.prevent="doRegister">
                <label class="field">
                  <span>手机号</span>
                  <input v-model="phone" type="tel" placeholder="11 位手机号" maxlength="11"
                         autocomplete="tel" inputmode="numeric" />
                </label>
                <label class="field">
                  <span>设置密码</span>
                  <input v-model="password" type="password" placeholder="至少 6 位"
                         autocomplete="new-password" />
                </label>
                <label class="field">
                  <span>确认密码</span>
                  <input v-model="password2" type="password" placeholder="再输一次"
                         autocomplete="new-password" />
                </label>
                <div v-if="error" class="error-hint">{{ error }}</div>
                <button class="btn btn-primary" :disabled="loading" type="submit">
                  <span v-if="loading">注册中…</span>
                  <span v-else>注 册</span>
                </button>
                <p class="switch-mode">
                  已有账号？
                  <button type="button" class="link-btn" @click="mode = 'login'">← 去登录</button>
                </p>
              </form>
            </div>
          </Transition>
        </div>

        <footer class="splash-footer">© 青囊 · SPUM 引擎 · 传统命理 × 现代数据</footer>
      </div>
    </Transition>
  </section>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../stores/user'

// 素材路径
const splashVideoSrc = '/splash/splash.mp4'
const splashPoster = '/splash/splash-poster.png'

const router = useRouter()
const route  = useRoute()
const user   = useUserStore()

const mode = ref(route.name === 'register' ? 'register' : 'login')
const phone    = ref('')
const password = ref('')
const password2 = ref('')
const loading  = ref(false)
const error    = ref('')

// ── 舞台时序 ──
const stage    = ref('video')  // 'video' → 'end'
const showCard = ref(false)    // 落版后卡片弹出

const splashVideo = ref(null)
let fallbackTimer = null

onMounted(() => {
  // 注销后快速跳转场景：跳过启动动画，直接落版
  if (route.query.skip_splash === '1') {
    stage.value = 'end'
    showCard.value = true
    return
  }
  // 兜底：无论视频是否正常，15s 后必进落版（v3 动画 13s）
  fallbackTimer = setTimeout(onVideoEnded, 15000)
})

onBeforeUnmount(() => {
  if (fallbackTimer) clearTimeout(fallbackTimer)
})

/**
 * 动画结束（播完 / 点击跳过 / 兜底）：
 * 切落版舞台 → 0.6s 后 Logo 与卡片一同浮现
 */
function onVideoEnded() {
  if (fallbackTimer) { clearTimeout(fallbackTimer); fallbackTimer = null }
  if (stage.value === 'end') return
  stage.value = 'end'
  setTimeout(() => { showCard.value = true }, 600)
}

function goRegister() {
  router.replace({ name: 'register' })
  mode.value = 'register'
}

async function doLogin() {
  error.value = ''
  if (!/^\d{11}$/.test(phone.value))    return (error.value = '请输入 11 位手机号')
  if (password.value.length < 6)        return (error.value = '密码至少 6 位')
  loading.value = true
  try {
    await user.login(phone.value, password.value)
    router.replace({ path: '/' })
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败，请检查账号密码'
  } finally { loading.value = false }
}

async function doRegister() {
  error.value = ''
  if (!/^\d{11}$/.test(phone.value))    return (error.value = '请输入 11 位手机号')
  if (password.value.length < 6)        return (error.value = '密码至少 6 位')
  if (password.value !== password2.value) return (error.value = '两次密码不一致')
  loading.value = true
  try {
    await user.register({
      phone: phone.value, password: password.value,
    })
    router.replace({ name: 'onboarding' })
  } catch (e) {
    error.value = e.response?.data?.detail || '注册失败，请稍后重试'
  } finally { loading.value = false }
}
</script>

<style scoped>
.splash-root {
  position: fixed; inset: 0;
  overflow: hidden;
  background: #F2EFE7;   /* 宣纸米，与海报边缘同色 */
}

/* ══════════ 舞台一：启动动画 ══════════ */
.video-stage {
  position: absolute; inset: 0;
  cursor: pointer;
}
/* 宽屏氛围底：同一海报放大模糊铺满，杜绝 cover 硬裁的突兀黑边 */
.video-backdrop {
  position: absolute; inset: -40px;
  background: url('/splash/splash-poster.png') center / cover no-repeat;
  filter: blur(28px) saturate(1.05) brightness(1.02);
  transform: scale(1.1);
}
/* 前景：完整海报 contain 居中，任何比例都不变形不裁切 */
.video-lead {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  object-fit: contain;
}
.skip-hint {
  position: absolute; right: 20px; bottom: 16px;
  z-index: 2;
  font-size: 12px; letter-spacing: 2px;
  color: rgba(11,15,14,0.45);
  border: 1px solid rgba(11,15,14,0.2);
  border-radius: 999px;
  padding: 5px 14px;
  background: rgba(242,239,231,0.55);
  backdrop-filter: blur(6px);
}

/* ══════════ 舞台二：落版 ══════════ */
.end-stage {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
}
.end-bg {
  position: absolute; inset: 0;
  background: url('/assets/splash-bg-layer.png') center / cover no-repeat;
  animation: bg-drift 24s ease-in-out infinite alternate;
}
@keyframes bg-drift {
  from { transform: scale(1); }
  to   { transform: scale(1.06); }
}
/* 中央宣纸提亮，保证卡片可读性 */
.end-wash {
  position: absolute; inset: 0;
  background: radial-gradient(
    ellipse 90% 70% at 50% 55%,
    rgba(242,239,231,0.72) 0%,
    rgba(242,239,231,0.35) 55%,
    rgba(242,239,231,0) 100%
  );
}

.end-content {
  position: relative; z-index: 1;
  flex: 1;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 30px;
  padding: 32px 20px;
  overflow-y: auto;
}

/* 卡片上方横标：绿药囊 + 扁字标 */
.brand-lockup {
  display: flex; align-items: center; gap: 12px;
  opacity: 0;
  transform: translateY(14px);
  transition: opacity 0.8s ease-out, transform 0.8s ease-out;
}
.brand-lockup.lockup-in { opacity: 1; transform: translateY(0); }
.lockup-icon {
  width: 48px; height: auto;   /* 48x64 */
  filter: drop-shadow(0 2px 10px rgba(23,83,76,0.25));
  user-select: none; -webkit-user-drag: none;
}
.lockup-wordmark {
  height: 84px; width: auto;   /* 汉字区 63px ≈ 图标高，比例对齐 */
  user-select: none; -webkit-user-drag: none;
}

/* 玻璃态登录卡片 */
.auth-card {
  width: min(400px, 100%);
  background: rgba(255,255,255,0.82);
  backdrop-filter: blur(18px) saturate(1.4);
  -webkit-backdrop-filter: blur(18px) saturate(1.4);
  border: 1px solid rgba(255,255,255,0.55);
  border-radius: 18px;
  padding: 28px 28px 22px;
  box-shadow:
    0 1px 0 rgba(255,255,255,0.8) inset,
    0 20px 60px rgba(15,35,30,0.22);
}
.card-enter-active {
  transition: opacity 0.7s ease-out, transform 0.7s cubic-bezier(0.22,1,0.36,1);
}
.card-enter-from {
  opacity: 0;
  transform: translateY(40px) scale(0.96);
}

.card-title {
  margin: 0 0 20px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(26,77,69,0.15);
  font-size: 16px;
  font-weight: 600;
  color: #17534C;
  letter-spacing: 1px;
}

.auth-form { display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-row { display: flex; gap: 10px; }
.field-half { flex: 1; min-width: 0; }
.field span { font-size: 13px; color: #2C3E3C; font-weight: 500; }
.field input, .field select {
  padding: 11px 14px;
  border: 1px solid rgba(26,77,69,0.20);
  border-radius: 10px;
  font-size: 14px;
  font-family: inherit;
  background: rgba(255,255,255,0.92);
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}
.field input:focus, .field select:focus {
  outline: none;
  border-color: #17534C;
  box-shadow: 0 0 0 3px rgba(23,83,76,0.12);
  background: #fff;
}

.btn-primary {
  margin-top: 4px;
  padding: 12px;
  font-size: 15px;
  letter-spacing: 3px;
  background: linear-gradient(135deg, #17534C 0%, #2E7D6A 100%);
  color: #fff;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.2s, filter 0.2s;
  font-weight: 500;
  box-shadow: 0 4px 18px rgba(23,83,76,0.35);
}
.btn-primary:hover:not(:disabled) { filter: brightness(1.05); transform: translateY(-1px); box-shadow: 0 6px 22px rgba(23,83,76,0.45); }
.btn-primary:active:not(:disabled) { transform: translateY(0); }
.btn-primary:disabled { opacity: 0.55; cursor: not-allowed; filter: grayscale(0.3); }

.error-hint {
  background: rgba(168,68,47,0.08);
  border: 1px solid rgba(168,68,47,0.35);
  color: #A8442F;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
}

.switch-mode {
  text-align: center;
  font-size: 13px;
  color: #6B7277;
  margin: 6px 0 0;
}
.link-btn {
  background: none; border: none; padding: 0;
  color: #17534C;
  cursor: pointer; font-size: 13px; font-weight: 600;
  transition: color 0.15s;
}
.link-btn:hover { color: #2E7D6A; text-decoration: underline; }

/* 舞台切换淡入 */
.stage-enter-active { transition: opacity 0.8s ease-out; }
.stage-enter-from { opacity: 0; }

.splash-footer {
  position: relative; z-index: 1;
  text-align: center;
  padding: 0 20px 18px;
  font-size: 11px;
  color: rgba(11,15,14,0.4);
  letter-spacing: 2px;
  user-select: none;
}

@media (max-width: 480px) {
  .lockup-icon { width: 40px; }
  .lockup-wordmark { height: 70px; }
  .auth-card { padding: 22px 20px 18px; }
  .end-content { gap: 24px; }
}
</style>
