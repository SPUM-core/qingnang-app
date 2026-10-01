<template>
  <div class="layout">
    <!-- ═══ 顶部 Header（仅桌面端） ═══ -->
    <header class="layout__header">
      <div class="meridian-glow" aria-hidden="true"></div>

      <!-- 桌面端品牌 Logo -->
      <RouterLink to="/" class="layout__brand">
        <img src="/assets/logo/icon-light.png" alt="" class="brand-icon" />
        <img src="/assets/logo/wordmark-light-70.png" alt="青囊" class="brand-wordmark" />
      </RouterLink>

      <!-- 桌面端导航 -->
      <nav class="layout__nav">
        <RouterLink v-for="item in navs" :key="item.path" :to="item.path">
          {{ item.title }}
        </RouterLink>
      </nav>

      <!-- 右侧操作区 -->
      <div class="layout__actions">
        <RouterLink to="/notifications" class="action-bell" title="提醒通知">
          <QIcon name="bell" :size="19" />
        </RouterLink>
        <RouterLink to="/settings" class="action-me" title="我的">
          <span class="me-avatar"><QIcon name="user" :size="15" /></span>
          <span class="me-text">我的</span>
        </RouterLink>
      </div>
    </header>

    <!-- ═══ 主内容区 ═══ -->
    <main class="layout__main">
      <slot />
    </main>

    <!-- ═══ 桌面端 Footer ═══ -->
    <footer class="layout__footer">
      <div class="footer-topology" aria-hidden="true"></div>
      <p class="footer-sub">把健康的主动权，交还给你自己</p>
    </footer>

    <!-- ═══ 移动端底部 Tab Bar（6 项：主导航 4 + 通知 + 我的） ═══ -->
    <nav class="mobile-tabbar">
      <RouterLink v-for="item in mobileNavs" :key="item.path" :to="item.path"
                  class="tab-item" active-class="tab-active">
        <QIcon :name="item.icon" :size="22" />
        <span class="tab-label">{{ item.title }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import QIcon from './ui/QIcon.vue'

// 桌面端顶部导航（3 项 + 采集已合并到体质页 CTA）
const navs = [
  { path: '/', title: '主页' },
  { path: '/case', title: '体质' },
  { path: '/discover', title: '发现' },
]

// 移动端 Tab Bar（5 项：主页/体质/通知/发现/我的）
const mobileNavs = [
  { path: '/', title: '主页', icon: 'home' },
  { path: '/case', title: '体质', icon: 'body' },
  { path: '/notifications', title: '通知', icon: 'bell' },
  { path: '/discover', title: '发现', icon: 'spark' },
  { path: '/settings', title: '我的', icon: 'user' },
]
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════
   桌面端（> 720px）
   ═══════════════════════════════════════════════════════ */
.layout { display: flex; flex-direction: column; min-height: 100vh; }

/* Header */
.layout__header {
  display: flex; align-items: center; gap: 24px; padding: 0 24px; height: 60px;
  background: linear-gradient(135deg, var(--qingnang-emerald) 0%, var(--qingnang-emerald-dark) 100%);
  color: #fff; position: sticky; top: 0; z-index: 100;
  box-shadow: 0 2px 8px rgba(26, 77, 69, 0.2); overflow: hidden;
}
.meridian-glow { position: absolute; inset: 0; pointer-events: none; z-index: 0; }

/* 品牌 Logo */
.layout__brand { display: flex; align-items: center; gap: 10px; z-index: 2; flex-shrink: 0; }
.brand-icon { height: 30px; width: auto; transition: transform 0.2s; }
.layout__brand:hover .brand-icon { transform: scale(1.08); }
.brand-wordmark { height: 22px; width: auto; opacity: 0.95; transition: opacity 0.2s; }
.layout__brand:hover .brand-wordmark { opacity: 1; }

/* 导航：绝对居中 */
.layout__nav {
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  display: flex; gap: 2px; z-index: 2;
}
.layout__nav a {
  color: rgba(255,255,255,0.72); text-decoration: none; font-size: 15px;
  padding: 7px 18px; border-radius: 20px; transition: all 0.2s;
  letter-spacing: 2px; display: inline-flex; align-items: center; font-weight: 400;
}
.layout__nav a:hover { color: #fff; background: rgba(255,255,255,0.1); }
.layout__nav a.router-link-active {
  color: #fff; background: rgba(255,255,255,0.18);
  font-weight: 500; box-shadow: 0 1px 6px rgba(0,0,0,0.15);
}

/* 右侧操作区 */
.layout__actions { display: flex; align-items: center; gap: 16px; z-index: 2; margin-left: auto; padding-left: 8px; }
.action-bell { color: rgba(255,255,255,0.8); display: inline-flex; transition: color 0.2s; }
.action-bell:hover { color: #fff; }
.action-me {
  display: inline-flex; align-items: center; gap: 7px;
  color: rgba(255,255,255,0.85); text-decoration: none; font-size: 14px; transition: color 0.2s;
}
.action-me:hover { color: #fff; }
.me-avatar {
  width: 28px; height: 28px; border-radius: 50%;
  background: var(--qingnang-emerald-light);
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--qingnang-paper);
}

.layout__main { flex: 1; padding: 0; max-width: 100%; }

/* Footer */
.layout__footer {
  position: relative; padding: 24px 20px 16px; text-align: center;
  background: linear-gradient(180deg, var(--qingnang-paper) 0%, var(--qingnang-paper-deep) 100%);
  border-top: 1px solid var(--ink-line); overflow: hidden;
}
.footer-topology {
  position: absolute; top: 0; left: 50%; transform: translateX(-50%);
  width: 400px; height: 2px;
  background:
    repeating-linear-gradient(90deg, var(--qingnang-emerald) 0, var(--qingnang-emerald) 2px, transparent 2px, transparent 24px),
    linear-gradient(90deg, transparent, var(--qingnang-emerald) 50%, transparent);
  opacity: 0.2;
}
.footer-sub { font-size: 12px; color: var(--ink-tertiary); letter-spacing: 2px; }

/* 移动端 Tab Bar — 桌面端默认隐藏 */
.mobile-tabbar { display: none; }


/* ═══════════════════════════════════════════════════════
   窄屏过渡（721px ~ 960px）
   ═══════════════════════════════════════════════════════ */
@media (max-width: 960px), (max-height: 700px), (orientation: portrait) {
  .layout__header { gap: 12px; padding: 0 14px; }
  .layout__nav {
    position: static; transform: none; margin-left: auto;
    overflow-x: auto; scrollbar-width: none; flex-shrink: 1;
  }
  .layout__nav::-webkit-scrollbar { display: none; }
  .layout__nav a { padding: 6px 10px; font-size: 13px; white-space: nowrap; letter-spacing: 1px; }
  .layout__actions { gap: 10px; padding-left: 0; }
  .action-me { font-size: 13px; }
}

@media (max-width: 860px) {
  .me-text { display: none; }
  .action-me { font-size: 0; gap: 0; }
  .me-avatar { width: 30px; height: 30px; }
}


/* ═══════════════════════════════════════════════════════
   移动端 —— 完全切换为 APP 布局
   触发条件（任一满足）：
     1. max-width: 720px       — 常规手机竖屏
     2. max-height: 600px      — 扁屏（特殊比例屏幕 F11 全屏等）
     3. orientation: portrait  — 纵向屏（无论绝对尺寸，height > width 就切移动端）
   ═══════════════════════════════════════════════════════ */
@media (max-width: 720px), (max-height: 600px), (orientation: portrait) {
  /* Header 完全隐藏 */
  .layout__header { display: none; }

  /* Main 预留 Tab Bar 高度 */
  .layout__main {
    padding-bottom: calc(64px + env(safe-area-inset-bottom));
  }

  /* Footer 隐藏 */
  .layout__footer { display: none; }

  /* 启用底部 Tab Bar（6 项） */
  .mobile-tabbar {
    display: flex; position: fixed; bottom: 0; left: 0; right: 0;
    height: calc(64px + env(safe-area-inset-bottom));
    padding-bottom: env(safe-area-inset-bottom);
    background: #fff;
    border-top: 1px solid var(--ink-line, #E8E4DA);
    box-shadow: 0 -2px 10px rgba(0,0,0,0.06);
    z-index: 200;
    justify-content: space-around; align-items: stretch;
  }
  .tab-item {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 3px;
    text-decoration: none; color: var(--ink-tertiary, #9E9E9E);
    transition: color 0.2s, transform 0.15s;
    -webkit-tap-highlight-color: transparent;
    user-select: none; min-width: 0;
  }
  .tab-item:active:not(.tab-icon-only) { transform: scale(0.96); }
  .tab-item :deep(.q-icon) { transition: transform 0.2s; }
  .tab-label { font-size: 10px; letter-spacing: 0.5px; font-weight: 400; }

  /* Active 态 */
  .tab-item.tab-active {
    color: var(--qingnang-emerald, #1A4D45);
  }
  .tab-item.tab-active :deep(.q-icon) {
    transform: translateY(-2px);
  }
}

/* 极窄屏再压一下 */
@media (max-width: 420px) {
  .tab-label { font-size: 9px; letter-spacing: 0; }
  .mobile-tabbar { height: calc(60px + env(safe-area-inset-bottom)); }
  .tab-item :deep(.q-icon) { font-size: 20px !important; }
}
</style>
