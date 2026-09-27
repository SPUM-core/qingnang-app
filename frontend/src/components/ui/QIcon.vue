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
