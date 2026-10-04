/**
 * 青囊前端 - API 客户端
 * dev 模式走 vite proxy（/api → localhost:8767），同域无 CORS
 * prod 模式用 VITE_API_BASE 环境变量覆盖
 * 前端不感知后端架构
 */
import axios from 'axios'

// dev 默认走相对路径 → vite proxy 代理到 8767（无 CORS）
// prod（独立部署前端）需要设 VITE_API_BASE 指向后端域名
const API_BASE = import.meta.env.VITE_API_BASE || ''

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,  // chat 端点要等 deepseek + analysis，至少 30-60s
})

// 请求拦截器：自动带 JWT
api.interceptors.request.use(config => {
  const token = localStorage.getItem('qn_token')
  if (token && !config.headers['Authorization']) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：401 自动清 token + 跳转登录
api.interceptors.response.use(
  r => r,
  e => {
    if (e.response?.status === 401) {
      localStorage.removeItem('qn_token')
      localStorage.removeItem('qn_user')
    }
    return Promise.reject(e)
  }
)

// ── 通用 ──
export const healthCheck = async () => {
  try {
    const r = await api.get('/health', { timeout: 3000 })
    return { ok: true, ...r.data }
  } catch (e) {
    return { ok: false, error: e.message || 'backend unreachable' }
  }
}

// ── 认证 ──
export const auth = {
  login:     (phone, password) => api.post('/api/v1/auth/login', { phone, password }),
  register:  (data)            => api.post('/api/v1/auth/register', data),
  me:        ()                => api.get('/api/v1/auth/me'),
  patchMe:   (data)            => api.patch('/api/v1/auth/me', data),
}

// ── AI 问诊引擎（动态生成问题清单） ──
export const inquiry = {
  start: () => api.post('/api/v1/assistant/inquiry/start', {}),
}

// ── 案例 ──
export const cases = {
  mine:       () => api.get('/api/v1/cases/mine'),
  onboarding: (data) => api.post('/api/v1/cases/onboarding', data),
}

// ── PPG ──
export const ppg = {
  history: () => api.get('/api/v1/ppg/history'),
  upload:  (data) => api.post('/api/v1/ppg/upload', data),
}

// ── 调理方案 ──
export const treatment = {
  versions: () => api.get('/api/v1/treatment/versions'),
  current:  () => api.get('/api/v1/treatment/current'),
  confirm:  (id) => api.post(`/api/v1/treatment/confirm/${id}`),
}

// ── 好友 ──
export const friends = {
  list:  () => api.get('/api/v1/friends/list'),
  add:   (qingnangId, relation = 'friend') =>
             api.post('/api/v1/friends/add', { friend_qingnang_id: qingnangId, relation }),
  match: (friendId) => api.get(`/api/v1/friends/match/${friendId}`),
  bindDoctor: (friendId) => api.post(`/api/v1/friends/bind-doctor/${friendId}`),
}

// ── 商城 ──
export const shop = {
  items:     (category, keyword) => api.get('/api/v1/shop/items', {
               params: { category, keyword } }),
  detail:    (sku) => api.get(`/api/v1/shop/items/${sku}`),
  recommend: () => api.get('/api/v1/shop/recommend'),
  review:    (data) => api.post('/api/v1/shop/reviews', data),
}

// ── 生活提醒 ──
export const notifications = {
  today: () => api.get('/api/v1/notifications/today'),
}

// ── 青囊管家 AI ──
export const assistant = {
  health:    () => api.get('/api/v1/assistant/health'),
  chat:      (message, history = []) => api.post('/api/v1/assistant/chat', { message, history }),
  // ── 结构化推理（青檬引擎 LLM 推理） ──
  diagnose:  (v_base, v_current) => api.post('/api/v1/assistant/reasoning/diagnose',
                { v_base, v_current }),
  lifestyle: (v_base) => api.post('/api/v1/assistant/reasoning/lifestyle', { v_base }),
  treatment: (current_plan, latest_observation) => api.post('/api/v1/assistant/reasoning/treatment',
                { current_plan, latest_observation }),
  // ── 八字推演（青檬引擎真太阳时 + 四柱 + 五形向量） ──
  // 青囊核心规则: 无论阳历/阴历输入, 都先换算真太阳时再排八字
  bazi: (birth_date, birth_hour, birthplace, birth_date_type = 'solar') =>
    api.post('/api/v1/assistant/reasoning/bazi',
      { birth_date, birth_hour, birthplace, birth_date_type }),
}

// ── SSE 流式生活提醒（fetch ReadableStream，不走 axios） ──
export function lifestyleStream({ onGenerating, onComplete, onNote, onError }) {
  const token = localStorage.getItem('qn_token')
  fetch(`${API_BASE}/api/v1/assistant/reasoning/lifestyle/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({}),
  }).then(async (response) => {
    if (!response.ok || !response.body) {
      // 尝试读取后端返回的 detail 信息（FastAPI 的 HTTPException 会放在 body 里）
      let detail = `HTTP ${response.status}`
      try {
        const errBody = await response.clone().text()
        const j = JSON.parse(errBody)
        if (j?.detail) detail = `HTTP ${response.status}: ${typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)}`
      } catch {}
      throw new Error(detail)
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // SSE 事件以 \n\n 分隔
      let idx
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        parseSSEEvent(rawEvent, { onGenerating, onComplete, onNote })
      }
    }
    if (buffer.trim()) parseSSEEvent(buffer, { onGenerating, onComplete, onNote })
  }).catch((err) => {
    if (onError) onError(err)
  })
}

function parseSSEEvent(raw, { onGenerating, onComplete, onNote }) {
  let eventType = 'message'
  let dataLines = []
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5))
    }
  }
  const dataStr = dataLines.join('\n')
  let data
  try { data = JSON.parse(dataStr) } catch { data = dataStr }

  if (eventType === 'generating' && onGenerating) {
    onGenerating(data.token || '')
  } else if (eventType === 'complete' && onComplete) {
    onComplete(data)
  } else if (eventType === 'note' && onNote) {
    onNote(data.text || data)
  }
}

// ── 挑战打卡 ──
export const challenges = {
  mine:  () => api.get('/api/v1/challenges/mine'),
  join:  (id) => api.post(`/api/v1/challenges/join/${id}`),
  check: (id, note = '') => api.post(`/api/v1/challenges/checkin/${id}`, { note }),
  create:(data) => api.post('/api/v1/challenges/', data),
}
