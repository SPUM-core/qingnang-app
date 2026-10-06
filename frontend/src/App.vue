<template>
  <div class="app-root">
    <!-- ═══ 主应用壳（始终挂载，避免路由切换时 LayoutShell 被销毁重建导致 double-render） ═══ -->
    <div class="app-shell" :style="{ display: route.meta.fullScreen ? 'none' : null }">
      <LayoutShell>
        <router-view v-if="!route.meta.fullScreen" />
      </LayoutShell>
      <ComplianceBar v-if="!route.meta.fullScreen" />
      <QingnangAssistant v-if="!route.meta.fullScreen" />
    </div>

    <!-- ═══ 全屏独占页（登录/注册/建档初始化） ═══ -->
    <router-view v-if="route.meta.fullScreen" />

    <!-- ═══ 引导（始终挂载，让从 fullScreen 页跳回主应用时 onMounted/watch 都能触发） ═══ -->
    <GuideOverlay />
  </div>
</template>

<script setup>
import { watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import LayoutShell from './components/LayoutShell.vue'
import ComplianceBar from './components/ComplianceBar.vue'
import QingnangAssistant from './components/QingnangAssistant.vue'
import GuideOverlay from './components/GuideOverlay.vue'
import { useUserStore } from './stores/user'
import { useSettingsStore } from './stores/settings'

const route = useRoute()
const user = useUserStore()
const settings = useSettingsStore()

// ── 监听设置变化 → 实时应用到 DOM ──
watch(
  () => [settings.theme, settings.font_size, settings.elder_mode, settings.reduce_motion],
  () => {
    settings.applyDisplay()
    settings.persist()
  },
  { deep: true }
)

// 监听系统主题变化（auto 模式下跟随）
let darkMedia = null
function onSystemThemeChange() { settings.applyDisplay() }

onMounted(() => {
  user.initFromLocalStorage()
  settings.applyDisplay()
  if (window.matchMedia) {
    darkMedia = window.matchMedia('(prefers-color-scheme: dark)')
    darkMedia.addEventListener('change', onSystemThemeChange)
  }
})

onUnmounted(() => {
  if (darkMedia) darkMedia.removeEventListener('change', onSystemThemeChange)
})
</script>

<style>
/* ═══════════════════════════════════════════════════════════════
   ⚠️ 全局变量、reset、排版、主题切换代码已迁移到：
     - src/styles/tokens.css  —— --qn-* 变量 + 暗色/老年/字体/减少动画
     - src/styles/base.css    —— reset + 排版 + 原子类 .btn/.card/.tag/.back-link
   
   本文件只保留 App 组件特有的、base.css 里没有或版本不同的样式块。
   ═══════════════════════════════════════════════════════════════ */

/* 纵向屏：页面 padding 减小，让 grid 占更多宽度 */
@media (orientation: portrait) {
  .page { padding: 16px 14px; }
}

/* ═══════════════════════════════════════════════════════
   🚧 以下全局原子类待逐页迁移至 base.css（版本不同，暂保留）
   
   迁移原则：
   - .btn / .btn-ghost  → base.css 里已经有新版胶囊样式；
     旧组件引用 .btn 的逐页替换为 .btn--primary / .btn--ghost
   - .card / .card h2   → base.css 里已有新版（box-shadow）；
     旧版是 border + padding 不同
   - .table             → base.css 里没有，保留
   - .tag-ok/warn/bad   → base.css 里用了新名 .tag--ok；旧名暂保留兼容
   ═══════════════════════════════════════════════════════ */

/* 全局卡片样式（纯白浮层 + 淡灰边框 + 轻微阴影 — 层级感 ↑）
   ⚠️ 已与 base.css 同步，新版值以 UI Kit 为准（圆角 16、无 border 纯 shadow） */
.card {
  background: var(--qn-surface);
  border-radius: var(--qn-r-lg);      /* 16px */
  padding: var(--qn-s4);              /* 16px */
  box-shadow: var(--qn-shadow-1);
  transition: box-shadow var(--qn-dur) var(--qn-ease);
}
.card:hover { box-shadow: var(--qn-shadow-2); }
.card h2 {
  font-family: var(--qn-font-title);
  color: var(--qn-emerald);
  font-size: calc(15px * var(--qn-fs-scale));
  border-bottom: 1px solid var(--qn-line);
  padding-bottom: 10px;
  margin-bottom: 14px;
  letter-spacing: 0.5px;
  font-weight: 600;
}

/* 表格全局 */
.table { width: 100%; border-collapse: collapse; font-size: calc(14px * var(--qn-fs-scale)); }
.table th { background: var(--qn-paper); color: var(--qn-ink-2); font-weight: 500; text-align: left; padding: 8px 10px; border-bottom: 2px solid var(--qn-line); }
.table td { padding: 8px 10px; border-bottom: 1px solid #F0F0EA; }

/* 全局按钮（已同步 UI Kit：胶囊 28px、min-height 44）
   ⚠️ 旧版是小方角 8px，新版是胶囊 28px；视觉差异大，逐页验证 */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  min-height: 44px;
  background: var(--qn-emerald);
  color: #fff;
  border: none;
  padding: 0 var(--qn-s5);             /* 20px */
  border-radius: var(--qn-r-pill);     /* 28px 胶囊 */
  font-size: calc(15px * var(--qn-fs-scale));
  font-family: var(--qn-font-body);
  font-weight: 500; letter-spacing: .5px;
  cursor: pointer; white-space: nowrap;
  transition: background var(--qn-dur) var(--qn-ease),
              transform var(--qn-dur) var(--qn-ease);
}
.btn:active { transform: scale(.97); }   /* 触摸反馈 */
.btn:hover { background: var(--qn-emerald-light); }
.btn-ghost {
  background: none;
  color: var(--qn-emerald);
  box-shadow: inset 0 0 0 1px var(--qn-emerald-light);
}
.btn-ghost:hover { background: var(--qn-surface); }
.btn:disabled { opacity: .45; cursor: not-allowed; }

/* ΔV 涨跌色 */
.delta.up { color: var(--trend-up); }
.delta.down { color: var(--trend-down); }

/* 占位文案 */
.placeholder, .empty { color: var(--qn-ink-3); text-align: center; padding: 32px 16px; }

/* 合规警示/提示条 */
.notice {
  background: #FBF8F0;
  border-left: 3px solid var(--wuxing-earth);
  padding: 10px 14px;
  border-radius: 0 var(--qn-r-sm) var(--qn-r-sm) 0;
  font-size: calc(13px * var(--qn-fs-scale));
  color: var(--qn-ink-2);
  line-height: 1.6;
}

/* 状态标签（旧名兼容，值已同步 .tag--ok/warn/bad）
   新版是 .tag--ok / .tag--warn / .tag--bad（前缀双横线区分修饰类） */
.tag-ok   { background: var(--qn-ok-bg);   box-shadow: inset 0 0 0 1px var(--qn-ok-bd);   color: var(--qn-wood);    border-radius: var(--qn-r-sm); padding: 2px 8px; font-size: calc(12px * var(--qn-fs-scale)); font-weight: 500; display: inline-block; }
.tag-warn { background: var(--qn-warn-bg); box-shadow: inset 0 0 0 1px var(--qn-warn-bd); color: var(--qn-earth);   border-radius: var(--qn-r-sm); padding: 2px 8px; font-size: calc(12px * var(--qn-fs-scale)); font-weight: 500; display: inline-block; }
.tag-bad  { background: var(--qn-bad-bg);  box-shadow: inset 0 0 0 1px var(--qn-bad-bd);  color: var(--qn-fire);    border-radius: var(--qn-r-sm); padding: 2px 8px; font-size: calc(12px * var(--qn-fs-scale)); font-weight: 500; display: inline-block; }
</style>
