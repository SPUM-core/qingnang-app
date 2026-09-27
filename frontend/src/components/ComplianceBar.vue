<template>
  <div class="compliance-bar" role="note">
    <span class="compliance-bar__dot" aria-hidden="true"><QIcon name="leaf" :size="13" /></span>
    <span class="compliance-bar__text">{{ text }}</span>
  </div>
</template>

<script setup>
import { COMPLIANCE_BAR_TEXT } from '../constants/compliance'
import QIcon from './ui/QIcon.vue'
const text = COMPLIANCE_BAR_TEXT
</script>

<style scoped>
.compliance-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 10px 20px;
  background: linear-gradient(135deg, var(--qingnang-emerald) 0%, var(--qingnang-emerald-dark) 100%);
  color: rgba(255,255,255,0.85);
  font-size: 12px;
  letter-spacing: 0.5px;
  border-top: 1px solid rgba(46, 125, 106, 0.4);
  box-shadow: 0 -2px 8px rgba(26, 77, 69, 0.15);
}
.compliance-bar__dot {
  font-size: 14px;
  filter: drop-shadow(0 1px 2px rgba(0,0,0,0.2));
}
.compliance-bar__text {
  font-family: var(--font-body);
}
</style>
