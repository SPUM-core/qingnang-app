import { defineStore } from 'pinia'
import * as storage from '../utils/storage'

const DEFAULTS = {
  city: '',                    // ⭐ 2026-10-05 新增：用户所在城市（用于查真实天气）
  notify_push: true,
  notify_time_morning: '07:00',
  notify_time_evening: '21:00',
  notify_cloth: true,
  notify_food: true,
  notify_home: false,
  notify_hourly: false,
  theme: 'auto',
  font_size: 'medium',
  elder_mode: false,
  reduce_motion: false,
  auto_collect: true,
  collect_freq: 'daily',
  collect_remind: true,
  share_family: true,
  share_data_anonymous: true,
  primary_goal: 'dispatch_qi',
  secondary_goal: 'warm_earth',
  llm_provider: 'deepseek',
}

export const useSettingsStore = defineStore('settings', {
  state: () => {
    const persisted = storage.get('qingnang_settings', {})
    return { ...DEFAULTS, ...persisted }
  },

  actions: {
    /** 应用显示设置（主题 / 字体 / 减少动画）到 document.documentElement */
    applyDisplay() {
      let actualTheme = this.theme
      if (actualTheme === 'auto') {
        actualTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
      }
      document.documentElement.setAttribute('data-theme', actualTheme)
      document.documentElement.setAttribute('data-font', this.font_size)
      if (this.elder_mode) {
        document.documentElement.classList.add('elder-mode')
      } else {
        document.documentElement.classList.remove('elder-mode')
      }
      if (this.reduce_motion) {
        document.documentElement.classList.add('reduce-motion')
      } else {
        document.documentElement.classList.remove('reduce-motion')
      }
    },

    persist() {
      storage.set('qingnang_settings', { ...this.$state })
    },
  },
})
