<template>
  <!-- 全屏独占页（登录/注册/建档初始化） -->
  <router-view v-if="route.meta.fullScreen" />

  <!-- 主应用页: LayoutShell 包裹 -->
  <div v-else class="app-shell">
    <LayoutShell>
      <router-view />
    </LayoutShell>
    <ComplianceBar />
    <QingnangAssistant />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import LayoutShell from './components/LayoutShell.vue'
import ComplianceBar from './components/ComplianceBar.vue'
import QingnangAssistant from './components/QingnangAssistant.vue'
import { useUserStore } from './stores/user'

const route = useRoute()
const user = useUserStore()

// 启动时从 localStorage 恢复登录态
onMounted(() => {
  user.initFromLocalStorage()
})
</script>

<style>
/* ============== 青囊 QINGNANG · 品牌设计变量 · v2 新中式极简科技风 ==============
   核心思路：去油腻、提层次 —— 背景做减法（变浅变干净），数据配色做加法（增加对比冷暖互补）
*/
:root {
  /* ── 品牌锚点（对齐 UI Kit Design Tokens v1.0） ──
     https://.../ui-kit/tokens/tokens.css
  */
  --qingnang-emerald: #17534C;       /* UI Kit 主色：青囊绿 */
  --qingnang-emerald-dark: #123F3A;  /* UI Kit 按压态 */
  --qingnang-emerald-light: #2E7D6A; /* UI Kit 松烟绿 · 悬浮态 */
  --qingnang-spirit: #A8442F;        /* UI Kit 朱砂 · 点缀（原为生机青，按规范换成朱砂） */
  --qingnang-spirit-soft: #C45A3C;

  /* ── 背景体系 ── */
  --qingnang-paper: #F2EFE7;         /* UI Kit 宣纸米 */
  --qingnang-paper-deep: #E5E1D6;
  --qingnang-card: #FFFFFF;
  --accent: #A8442F;                 /* UI Kit 朱砂点缀 */

  /* ── 中性文字色 ── */
  --ink-primary: #33403B;            /* UI Kit textDark */
  --ink-secondary: #5A6A64;
  --ink-tertiary: #8A9A94;
  --ink-line: #E5E1D6;

  /* ── 五形语义色（业务逻辑色，独立于品牌 token） ── */
  --wuxing-wood: #43A047;
  --wuxing-fire: #D84315;
  --wuxing-earth: #D4A017;
  --wuxing-metal: #90A4AE;
  --wuxing-water: #0288D1;

  /* ── 功能色 ── */
  --trend-up: #D84315;
  --trend-down: #0288D1;

  /* ── 排版（对齐 UI Kit：Source Han Sans / Noto Sans SC） ── */
  --font-title: 'Source Han Sans CN', 'Noto Sans SC', 'PingFang SC', serif;
  --font-body: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;

  /* ── 圆角（UI Kit 规格） ── */
  --radius-sm: 8px;
  --radius-md: 14px;
  --radius-lg: 16px;
  --radius-pill: 28px;               /* UI Kit 胶囊按钮 */

  /* ── 阴影 ── */
  --shadow-card: 0 1px 2px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.06);
  --shadow-card-hover: 0 2px 4px rgba(0,0,0,0.06), 0 6px 16px rgba(0,0,0,0.10);

  /* ── 状态标签色 ── */
  --tag-ok-bg: rgba(67,160,71,0.08);
  --tag-ok-border: rgba(67,160,71,0.35);
  --tag-warn-bg: rgba(212,160,23,0.08);
  --tag-warn-border: rgba(212,160,23,0.40);
  --tag-bad-bg: rgba(216,67,21,0.08);
  --tag-bad-border: rgba(216,67,21,0.40);
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html, body, #app { height: 100%; }

body {
  font-family: var(--font-body);
  background: var(--qingnang-paper);
  color: var(--ink-primary);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  /* 拓扑网格纹理 — 调淡（去油腻） */
  background-image:
    radial-gradient(circle at 1px 1px, rgba(26, 77, 69, 0.025) 1px, transparent 0);
  background-size: 24px 24px;
}

/* 全局页面容器 */
.page { max-width: 1200px; margin: 0 auto; padding: 24px 20px; }
.page h1 { font-family: var(--font-title); color: var(--qingnang-emerald); font-size: 22px; margin-bottom: 4px; letter-spacing: 1px; font-weight: 600; }
.page__desc { color: var(--ink-tertiary); font-size: 13px; margin-bottom: 16px; }

/* 全局卡片样式（纯白浮层 + 淡灰边框 + 轻微阴影 — 层级感 ↑） */
.card {
  background: var(--qingnang-card);
  border: 1px solid var(--ink-line);
  border-radius: var(--radius-md);
  padding: 18px;
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.2s;
}
.card:hover { box-shadow: var(--shadow-card-hover); }
.card h2 {
  font-family: var(--font-title);
  color: var(--qingnang-emerald);
  font-size: 15px;
  border-bottom: 1px solid var(--ink-line);
  padding-bottom: 10px;
  margin-bottom: 14px;
  letter-spacing: 0.5px;
  font-weight: 600;
}

/* 表格全局 */
.table { width: 100%; border-collapse: collapse; font-size: 14px; }
.table th { background: var(--qingnang-paper); color: var(--ink-secondary); font-weight: 500; text-align: left; padding: 8px 10px; border-bottom: 2px solid var(--ink-line); }
.table td { padding: 8px 10px; border-bottom: 1px solid #F0F0EA; }

/* 全局按钮 */
.btn {
  background: var(--qingnang-emerald);
  color: #fff;
  border: none;
  padding: 8px 18px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-family: var(--font-body);
  cursor: pointer;
  transition: background 0.2s, box-shadow 0.2s;
  font-weight: 500;
}
.btn:hover { background: var(--qingnang-emerald-light); box-shadow: 0 2px 6px rgba(26,77,69,0.2); }
.btn-ghost {
  background: transparent;
  color: var(--qingnang-emerald);
  border: 1px solid var(--qingnang-emerald);
}
.btn-ghost:hover { background: var(--qingnang-paper); }

/* ΔV 涨跌色 */
.delta.up { color: var(--trend-up); }
.delta.down { color: var(--trend-down); }

/* 占位文案 */
.placeholder, .empty { color: var(--ink-tertiary); text-align: center; padding: 32px 16px; }

/* 合规警示/提示条 */
.notice {
  background: #FBF8F0;
  border-left: 3px solid var(--wuxing-earth);
  padding: 10px 14px;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: 13px;
  color: var(--ink-secondary);
  line-height: 1.6;
}

/* 状态标签（极浅底色 + 同系深色边框 + 深色文字 — 轻盈克制） */
.tag-ok { background: var(--tag-ok-bg); border: 1px solid var(--tag-ok-border); color: var(--wuxing-wood); border-radius: 4px; padding: 2px 8px; font-size: 12px; font-weight: 500; }
.tag-warn { background: var(--tag-warn-bg); border: 1px solid var(--tag-warn-border); color: var(--wuxing-earth); border-radius: 4px; padding: 2px 8px; font-size: 12px; font-weight: 500; }
.tag-bad { background: var(--tag-bad-bg); border: 1px solid var(--tag-bad-border); color: var(--wuxing-fire); border-radius: 4px; padding: 2px 8px; font-size: 12px; font-weight: 500; }
</style>
