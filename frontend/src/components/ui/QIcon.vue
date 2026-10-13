<template>
  <svg :width="size" :height="size" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg"
       class="q-icon" aria-hidden="true">
    <g stroke="currentColor" :stroke-width="stroke" stroke-linecap="round" stroke-linejoin="round" fill="none">
      <template v-if="name === 'home'">
        <path d="M8 22 L24 8 L40 22 M12 20 V38 a2 2 0 0 0 2 2 H34 a2 2 0 0 0 2 -2 V20 M20 40 V28 H28 V40" />
      </template>
      <template v-else-if="name === 'leaf'">
        <path d="M24 42 C13 33 12 20 17 11 C29 10 37 17 37 26 C37 35 31 41 24 42 Z M18 14 C22 26 28 33 34 37" />
      </template>
      <template v-else-if="name === 'calendar'">
        <rect x="8" y="12" width="32" height="28" rx="4" />
        <path d="M8 20 H40 M16 8 V14 M32 8 V14" />
      </template>
      <template v-else-if="name === 'user'">
        <circle cx="24" cy="16" r="7" />
        <path d="M10 40 C10 31 16 27 24 27 C32 27 38 31 38 40" />
      </template>
      <template v-else-if="name === 'bell'">
        <path d="M14 32 V20 a10 10 0 0 1 20 0 V32 L37 37 H11 Z M20 41 a4 4 0 0 0 8 0" />
      </template>
      <template v-else-if="name === 'sliders'">
        <path d="M10 16 H38 M10 24 H38 M10 32 H38" />
        <circle cx="20" cy="16" r="4" />
        <circle cx="30" cy="24" r="4" />
        <circle cx="17" cy="32" r="4" />
      </template>
      <template v-else-if="name === 'search'">
        <circle cx="21" cy="21" r="10" />
        <path d="M29 29 L40 40" />
      </template>
      <template v-else-if="name === 'arrow'">
        <path d="M10 24 H38 M30 15 L39 24 L30 33" />
      </template>
      <template v-else-if="name === 'cart'">
        <path d="M8 10 H14 L18 32 H38 L42 16 H16" />
        <circle cx="21" cy="40" r="3" />
        <circle cx="35" cy="40" r="3" />
      </template>
      <template v-else-if="name === 'check'">
        <path d="M10 25 L20 35 L38 14" />
      </template>
      <template v-else-if="name === 'warn'">
        <path d="M24 8 L42 40 H6 Z M24 20 V30 M24 35 V35.5" />
      </template>
      <template v-else-if="name === 'forbid'">
        <circle cx="24" cy="24" r="16" />
        <path d="M13 13 L35 35" />
      </template>
      <template v-else-if="name === 'gem'">
        <path d="M14 10 H34 L42 20 L24 40 L6 20 Z M6 20 H42 M24 40 L17 20 L24 10 L31 20 Z" />
      </template>
      <template v-else-if="name === 'book'">
        <path d="M10 8 H36 a2 2 0 0 1 2 2 V40 H12 a2 2 0 0 1 -2 -2 Z M10 34 H38 M16 8 V34" />
      </template>
      <template v-else-if="name === 'doc'">
        <path d="M12 6 H30 L38 14 V42 H12 Z M30 6 V14 H38 M18 24 H32 M18 32 H32" />
      </template>
      <template v-else-if="name === 'moon'">
        <path d="M38 28 A16 16 0 1 1 20 8 A13 13 0 0 0 38 28 Z" />
      </template>
      <template v-else-if="name === 'chat'">
        <path d="M8 10 H40 V34 H22 L12 42 V34 H8 Z" />
      </template>
      <template v-else-if="name === 'clock'">
        <circle cx="24" cy="24" r="16" />
        <path d="M24 14 V24 L31 29" />
      </template>
      <template v-else-if="name === 'anchor'">
        <circle cx="24" cy="12" r="5" />
        <path d="M24 17 V40 M24 40 C15 40 9 33 9 26 M24 40 C33 40 39 33 39 26 M14 26 H9 M34 26 H39" />
      </template>
      <template v-else-if="name === 'spark'">
        <path d="M24 6 L28 20 L42 24 L28 28 L24 42 L20 28 L6 24 L20 20 Z" />
      </template>
      <template v-else-if="name === 'lock'">
        <rect x="12" y="20" width="24" height="18" rx="4" />
        <path d="M16 20 V14 a8 8 0 0 1 16 0 V20" />
      </template>
      <template v-else-if="name === 'chart'">
        <path d="M8 40 H40 M14 32 V22 M24 32 V12 M34 32 V26" />
      </template>
      <template v-else-if="name === 'body'">
        <!-- 正六边形（体质档案）+ 中心五形向量菱形 -->
        <path d="M24 6 L40 14 L40 34 L24 42 L8 34 L8 14 Z" />
        <path d="M24 20 L30 28 L24 34 L18 28 Z" />
        <circle cx="24" cy="27" r="1.5" fill="currentColor" stroke="none" />
      </template>
      <template v-else-if="name === 'settings'">
        <!-- 齿轮 -->
        <circle cx="24" cy="24" r="16" />
        <circle cx="24" cy="24" r="7" />
        <path d="M24 8 V12 M24 36 V40 M8 24 H12 M36 24 H40 M12.7 12.7 L15.5 15.5 M32.5 32.5 L35.3 35.3 M12.7 35.3 L15.5 32.5 M32.5 15.5 L35.3 12.7" />
      </template>

      <!-- ═══ 2026-10-06 扩充：替换 emoji / 系统符号 ═══
           规格：48 viewBox · 3px 圆头线宽· currentColor
           设计约束：全站统一 3px，不混用 2px 细线（与既有 24 枚保持一致） -->

      <!-- 新对话 / 清空重开：环形箭头 + 端点收在框内，避免视觉溢出 -->
      <template v-else-if="name === 'refresh'">
        <path d="M38 24 A14 14 0 1 1 31 12" />
        <path d="M32 8 V14 H26" />
      </template>

      <!-- 全屏展开：四角括号，替代系统 ⛶ -->
      <template v-else-if="name === 'expand'">
        <path d="M14 18 V12 a2 2 0 0 1 2-2 h6 M34 18 V12 a2 2 0 0 0-2-2 h-6 M14 30 v6 a2 2 0 0 0 2 2 h6 M34 30 v6 a2 2 0 0 1-2 2 h-6" />
      </template>

      <!-- 全屏退出：内收括号 -->
      <template v-else-if="name === 'collapse'">
        <path d="M20 14 V20 M28 14 V20 M20 28 v6 M28 28 v6" />
      </template>

      <!-- 收起（抽屉往下）：下箭头 + 底横线，替代系统 — -->
      <template v-else-if="name === 'minimize'">
        <path d="M24 16 V32 M15 25 L24 33 L33 25" />
        <path d="M14 40 H34" />
      </template>

      <!-- 关闭：标准 × -->
      <template v-else-if="name === 'close'">
        <path d="M15 15 L33 33 M33 15 L15 33" />
      </template>

      <!-- 侧栏收起：左尖括号，替代系统 ‹ -->
      <template v-else-if="name === 'chevron-left'">
        <path d="M27 13 L18 24 L27 35" />
      </template>

      <template v-else-if="name === 'chevron-right'">
        <path d="M21 13 L30 24 L21 35" />
      </template>

      <!-- 青囊草本标记：替代 🌿 -->
      <template v-else-if="name === 'sprout'">
        <path d="M24 42 V26" />
        <path d="M24 26 C24 18 18 12 10 12 C10 20 16 26 24 26 Z" />
        <path d="M24 26 C24 19 30 14 38 14 C38 21 32 26 24 26 Z" />
      </template>

      <!-- 加号（新对话入口） -->
      <template v-else-if="name === 'plus'">
        <path d="M24 14 V34 M14 24 H34" />
      </template>

      <!-- 历史记录：书册，替代 📜 -->
      <template v-else-if="name === 'history'">
        <path d="M10 10 H38 V38 H16 a6 6 0 0 1-6-6 Z" />
        <path d="M10 10 V32 a6 6 0 0 0 6 6" />
        <path d="M19 18 H31 M19 25 H29" />
      </template>

      <!-- 上箭头（趋势/升），替代 ↑ -->
      <template v-else-if="name === 'arrow-up'">
        <path d="M24 38 V14 M15 23 L24 14 L33 23" />
      </template>

      <!-- 下箭头（趋势/降），替代 ↓ -->
      <template v-else-if="name === 'arrow-down'">
        <path d="M24 10 V34 M15 25 L24 34 L33 25" />
      </template>

      <!-- 右箭头（横向趋势），替代 → -->
      <template v-else-if="name === 'arrow-right'">
        <path d="M12 24 H36 M27 15 L36 24 L27 33" />
      </template>

      <!-- 提示/警告：三角 + 感叹号，替代 ⚠ -->
      <template v-else-if="name === 'alert'">
        <path d="M24 9 L42 39 H6 Z" />
        <path d="M24 19 V28" />
        <path d="M24 33.5 V34" />
      </template>

      <!-- 提示气泡，替代 💬 -->
      <template v-else-if="name === 'message'">
        <path d="M9 11 H39 V33 H21 L12 41 V33 H9 Z" />
      </template>

      <!-- 灯泡/建议，替代 💡 -->
      <template v-else-if="name === 'idea'">
        <path d="M24 8 A12 12 0 0 1 31 27 V31 H17 V27 A12 12 0 0 1 24 8 Z" />
        <path d="M19 36 H29 M21 41 H27" />
      </template>

      <!-- 靶心/目标，替代 🎯 -->
      <template v-else-if="name === 'target'">
        <circle cx="24" cy="24" r="15" />
        <circle cx="24" cy="24" r="7" />
        <path d="M24 9 V15 M24 33 V39 M9 24 H15 M33 24 H39" />
      </template>

      <!-- 星标，替代 ⭐ -->
      <template v-else-if="name === 'star'">
        <path d="M24 8 L29.5 19 L41 20.5 L33 28 L35 40 L24 34 L13 40 L15 28 L7 20.5 L18.5 19 Z" />
      </template>

      <!-- 五行分布（雷达替代），替代 📊 -->
      <template v-else-if="name === 'radar'">
        <circle cx="24" cy="24" r="16" />
        <circle cx="24" cy="24" r="9" />
        <path d="M24 8 V40 M8 24 H40" />
      </template>

      <!-- 分享/导出，替代 📤 -->
      <template v-else-if="name === 'share'">
        <path d="M24 33 V10 M16 18 L24 10 L32 18" />
        <path d="M12 28 V38 a2 2 0 0 0 2 2 H34 a2 2 0 0 0 2-2 V28" />
      </template>

      <!-- 医章/诊察，替代 🩺 -->
      <template v-else-if="name === 'stethoscope'">
        <path d="M16 8 V20 a8 8 0 0 0 16 0 V8" />
        <path d="M13 8 H19 M29 8 H35" />
        <path d="M24 28 V32 a7 7 0 0 0 14 0 V30" />
        <circle cx="38" cy="28" r="3" />
      </template>

      <!-- 好友/群组：双人轮廓，替代 👥 -->
      <template v-else-if="name === 'user-group'">
        <!-- 后景人（稍小、偏左） -->
        <circle cx="17" cy="15" r="5" />
        <path d="M7 38 C7 30 12 27 17 27 C22 27 27 30 27 38" />
        <!-- 前景人（稍大、偏右） -->
        <circle cx="30" cy="17" r="6.5" />
        <path d="M16 42 C16 32 22 28 30 28 C38 28 44 32 44 42" />
      </template>

      <!-- 信息/关于：i 圆点 + 竖线 -->
      <template v-else-if="name === 'info'">
        <circle cx="24" cy="14" r="3" fill="currentColor" stroke="none" />
        <path d="M24 22 V36" />
      </template>

      <!-- 心脏/关怀：替代 ❤ -->
      <template v-else-if="name === 'heart'">
        <path d="M24 40 C24 40 8 30 8 19 C8 13 13 9 18 9 C21 9 23 11 24 14 C25 11 27 9 30 9 C35 9 40 13 40 19 C40 30 24 40 24 40 Z" />
      </template>
    </g>
  </svg>
</template>

<script setup>
defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 16 },
  stroke: { type: [Number, String], default: 3 }
})
</script>

<style scoped>
.q-icon { display: inline-block; vertical-align: -0.15em; flex-shrink: 0; }
</style>
