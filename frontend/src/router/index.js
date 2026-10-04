import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  // ── 登录/注册 (全屏独占 · 未登录可访问 · 已登录自动跳主页) ──
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'),
    meta: { title: '登录', fullScreen: true, noAuthRequired: true, redirectIfLoggedIn: true } },
  { path: '/register', name: 'register', component: () => import('../views/LoginView.vue'),
    meta: { title: '注册', fullScreen: true, noAuthRequired: true, redirectIfLoggedIn: true } },

  // ── 主应用页 (LayoutShell 包裹) ──
  { path: '/', name: 'home', component: () => import('../views/DashboardView.vue'), meta: { title: '主页' } },
  { path: '/case', name: 'case', component: () => import('../views/CaseDetailView.vue'), meta: { title: '体质档案详情' } },
  // onboarding: 全屏独占 · 需登录 · 已建档用户自动跳主页 · 未建档用户访问任意页自动跳这里
  { path: '/onboarding', name: 'onboarding', component: () => import('../views/QuestionnaireView.vue'),
    meta: { title: '用户初始化', hidden: true, fullScreen: true, requireAuth: true } },
  { path: '/collect', name: 'collect', component: () => import('../views/CollectView.vue'), meta: { title: '数据采集' } },
  { path: '/collect/body', name: 'collect-body', component: () => import('../views/BodyPhotoView.vue'), meta: { title: '体态照片' } },
  { path: '/collect/voice', name: 'collect-voice', component: () => import('../views/VoiceSampleView.vue'), meta: { title: '语音样本' } },
  { path: '/collect/ppg', name: 'collect-ppg', component: () => import('../views/PpgCollectView.vue'), meta: { title: '脉搏采集' } },
  { path: '/collect/inquiry', name: 'collect-inquiry', component: () => import('../views/InquiryView.vue'), meta: { title: '问诊采集' } },

  // 发现页（知识 + 商城 合并）
  { path: '/discover', name: 'discover', component: () => import('../views/DiscoverView.vue'), meta: { title: '发现' } },
  { path: '/knowledge-base', redirect: '/discover' },
  { path: '/shop', redirect: '/discover?tab=shop' },
  { path: '/shop/:id', name: 'shop-detail', component: () => import('../views/ShopDetailView.vue'), meta: { title: '商品详情' } },

  { path: '/users', name: 'users', component: () => import('../views/UserManageView.vue'), meta: { title: '我的好友' } },
  { path: '/notifications', name: 'notifications', component: () => import('../views/NotificationsView.vue'), meta: { title: '提醒通知' } },
  { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue'), meta: { title: '设置' } },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// ── 导航守卫 ──
router.beforeEach((to) => {
  const token = localStorage.getItem('qn_token')
  const onboarded = localStorage.getItem('qingnang_onboarded') === 'true'

  // ① 已登录 + 去 login/register → 跳主页（redirectIfLoggedIn）
  if (to.meta.redirectIfLoggedIn && token) {
    return { path: '/' }
  }

  // ② 未登录 + 去需认证页面 → 跳 login
  if (to.meta.requireAuth && !token) {
    return { name: 'login' }
  }

  // ③ 普通业务页也需登录（登录/注册/全屏页除外）
  if (!to.meta.fullScreen && !to.meta.noAuthRequired && !token) {
    return { name: 'login' }
  }

  // ④ 已登录 + 未建档 + 访问非 onboarding 页 → 跳 onboarding
  if (token && !onboarded && to.name !== 'onboarding' && !to.meta.noAuthRequired) {
    return { name: 'onboarding' }
  }

  // ⑤ 已建档 + 去 onboarding → 跳主页
  if (to.name === 'onboarding' && onboarded) {
    return { path: '/' }
  }
})

router.afterEach((to) => {
  document.title = to.meta?.title ? `${to.meta.title} · 青囊生活管家` : '青囊生活管家 · SPUM 引擎'
})

export default router
