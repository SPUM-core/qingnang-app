// 端点约定：与后端 spum-engine FastAPI（docs/02_数据库表结构设计.md）对应
// 参照 qingmeng-engine inference/server.py：/health、REST、不可达不崩溃

export const ENDPOINTS = {
  health: '/health',

  users: '/api/users',                       // POST 创建 / GET 列表
  userDetail: (id) => `/api/users/${id}`,    // GET 档案
  privacyExport: (id) => `/api/users/${id}/privacy/export`, // POST 导出令牌
  userRemove: (id) => `/api/users/${id}`,    // DELETE 一键删除

  vectors: (id) => `/api/users/${id}/vectors`,           // GET V_base + V_obs
  driftSeries: (id) => `/api/users/${id}/drift/series`,  // GET 漂移时序
  questionnaire: '/api/obs/questionnaire',    // POST 问诊向量
  multimodal: '/api/obs/multimodal',          // POST 舌象/声纹原样上传

  ppgSessions: '/api/ppg/sessions',                         // POST 创建
  ppgSamples: (sid) => `/api/ppg/sessions/${sid}/samples`,  // POST 批量波形

  interventions: '/api/interventions',          // POST 创建
  interventionsByUser: (id) => `/api/interventions/${id}`, // GET 记录

  knowledgeItems: '/api/knowledge-base/items',  // GET / POST

  reports: (id) => `/api/users/${id}/reports`,           // GET 报告列表
  notifications: (id) => `/api/users/${id}/notifications`, // GET 提醒列表

  wsLive: (id) => `/ws/live?user_id=${id}`       // WS 实时刷新
}
