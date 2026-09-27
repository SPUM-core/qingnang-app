---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: e481ad6ee04e2abcc5574a477e9532da_44702becb8c011f1b172525400248c00
    ReservedCode1: +MaV0ttD0okTgxnGr1UmykZfh7qq4ihXnQCyJip6uZnhOee1GYBNdzdcenHY2S7Q/0t5cdB/Kabsm2RChzRWIDxateEejNPGgZujLOk/ItAhuQgFZ956gOEgIlr9yuqabKlbgIkUZOgDGSU310FT5Rrg9ehnJBI9+y6E1b/4Kfka16Mg3BpRDR9O3Ck=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: e481ad6ee04e2abcc5574a477e9532da_44702becb8c011f1b172525400248c00
    ReservedCode2: +MaV0ttD0okTgxnGr1UmykZfh7qq4ihXnQCyJip6uZnhOee1GYBNdzdcenHY2S7Q/0t5cdB/Kabsm2RChzRWIDxateEejNPGgZujLOk/ItAhuQgFZ956gOEgIlr9yuqabKlbgIkUZOgDGSU310FT5Rrg9ehnJBI9+y6E1b/4Kfka16Mg3BpRDR9O3Ck=
---

# 前端开发 Prompt（spum-engine/frontend）

> **用途**：面向 AI 编程助手 / Trae IDE Agent 的前端开发引导文档。加载本文件后，即可在 `E:\工作\spum-engine\frontend` 内进行前端开发、联调与迭代。
> **定位**：与 `docs/04_前端架构设计.md`（架构总纲）配套——04 说明"是什么"，本文件说明"怎么做、守什么红线"。
> **版本**：v1.0 | 2026-09-25
> **适配骨架**：frontend/ 已含可运行骨架（Vue3 + Vite + ECharts + Pinia + Vue Router），本 Prompt 指导在其上继续开发。

---

## 一、项目背景与定位

**青囊生活管家**是 SPUM（空间粒子宇宙模型）五形体质生活推演产品的前端管理端，属于 `spum-engine` 独立项目。

- **定位**：SPUM 体质生活推演参考工具，**不是医疗产品**。
- **产品承诺**：从八字干支 → 五形 S 向量（先天基底 V_base）、多模态观测 → 后天观测向量（V_obs）、ΔV 漂移趋势观察、药膳/药茶/导引等生活化干预记录与个体响应系数校正。
- **🔴 合规红线（最高优先级）**：任何界面文案、tooltip、弹窗、报告，**严禁出现诊断/治疗/疗效/处方/医嘱/证候/疾病/症状缓解/药用/预警/异常**等医疗词汇；一律使用「趋势观察提示」「向量漂移趋势」措辞；全站常驻合规条。
- **数据边界**：原始 PPG 波形、舌象图属敏感个人数据，前端不落本地存储，仅会话内预览；导出/删除走后端隐私令牌接口。

### 硬约束速查（RULES）

| ID | 约束 |
|----|------|
| `RULE-COMPLIANCE` | 非医疗措辞为红线，见 §四 禁词表，任何新增文案必须自查 |
| `RULE-STACK` | 技术栈锁定 Vue3 + Vite + ECharts + Pinia + Vue Router，不引入未约定框架 |
| `RULE-PHASE` | 基础设施按 Phase 0→3 引入：Phase 0 只做 Web 端 + H5 响应式预留，不铺 Flutter/多端并行 |
| `RULE-API` | 端点约定见 §三，参照 qingmeng-engine `inference/server.py` 模式（/health、不可达不崩溃） |
| `RULE-MAPPING` | 五形映射规则只在 spum-core 修订，前端只消费后端结果，禁止前端内置映射逻辑 |
| `RULE-PRIVACY` | 原始波形/舌图不落前端存储；导出/删除必须走 `/api/users/{id}/privacy/export` 令牌接口 |

---

## 二、技术栈与架构约束

### 2.1 技术栈

| 层 | 选型 | 说明 |
|----|------|------|
| 框架 | Vue 3（`<script setup>`） | 组合式 API |
| 构建 | Vite | `npm run dev` / `npm run build` / `npm run preview` |
| 路由 | Vue Router 4 | createWebHistory，7 模块路由 |
| 状态 | Pinia | 三个 store：user / vector / session |
| 图表 | ECharts 5 | radar / line / scatter（3D 可选 echarts-gl，Phase 2+） |
| HTTP | axios | 实例 `src/api/client.js`，baseURL 走 `VITE_API_BASE` |
| 实时 | WebSocket | `src/api/client.js` 内 `wsClient` 封装，指数退避重连 |

### 2.2 架构约束

- **Web 端为主入口**：Phase 0 即主入口，PC 管理 + 可视化。
- **H5 响应式适配预留**：`index.html` 已含 `viewport-fit=cover`；组件样式优先流式布局、`min-height: 100vh`，避免固定像素宽。
- **目录结构固定**（不得随意新增顶层目录，模块内新增需说明）：

```
frontend/
├─ index.html / package.json / vite.config.js / .gitignore
└─ src/
   ├─ main.js / App.vue
   ├─ router/index.js          # 7 模块路由
   ├─ stores/                  # user.js / vector.js / session.js
   ├─ api/                     # client.js / endpoints.js
   ├─ views/                   # 7 个核心页面
   ├─ components/              # LayoutShell / ComplianceBar / charts/*
   └─ constants/compliance.js  # 合规文案常量（唯一文案来源）
```

### 2.3 7 大模块（路由与视图）

| 模块 | 路由 | 视图 | 职责 |
|------|------|------|------|
| 向量可视化 | `/` | DashboardView | 三区布局：雷达图 + 漂移矢量图 + 时序趋势 |
| 问诊录入 | `/questionnaire` | QuestionnaireView | 结构化问诊 → 观测向量 |
| 舌象/声纹采集上传 | `/collect` | CollectView | 采集压缩上传（前端不做识别） |
| 报告查看 | `/report` | ReportView | 推演报告 + 趋势观察提示 |
| 知识库管理 | `/knowledge-base` | KnowledgeBaseView | 药膳/药茶/导引/衣物/时辰条目 |
| 用户管理 | `/users` | UserManageView | 档案、生辰干支、隐私导出/删除 |
| 提醒通知 | `/notifications` | NotificationsView | 时辰/药茶提醒、趋势提示列表 |

**新增路由规范**：路由 `meta.title` 必填；页面挂载后由 `router.afterEach` 自动设置 `document.title`；所有页面由 `App.vue` 统一包 `LayoutShell` + `ComplianceBar`，**单个视图不得自绘顶栏/合规条**。

---

## 三、核心实现指引

### 3.1 向量可视化三区布局（DashboardView 核心）

按 `docs/03_前端拓扑可视化页面设计.md` 实现：

```
顶栏：用户选择 | 时间范围 | 对比模式
├─ 左区：五形雷达图（RadarChart：V_base 实线 + V_obs 虚线）
├─ 中区：漂移矢量图（V_base 锚点 → V_obs 观测点，箭头 ΔV，健康凸多面体参考）
├─ 右区：时序趋势曲线（DriftChart：ΔV 五分量 line + 趋势状态色带 + 干预节点 scatter）
└─ 底栏：时间轴回放 + 常驻合规条
```

- **三区联动**：中区点击观测点 → 右区高亮定位；底栏时间轴拖动 → 中区 V_obs 点与箭头随时间片移动。
- **对比模式**：存在 `intervention_results` 时可用，叠加干预前后 ΔV 对比。
- 现状：`RadarChart.vue` / `DriftChart.vue` 已实现基础渲染（雷达叠加、五分量折线），后续在此之上补齐中区矢量图与联动。

### 3.2 ΔV 计算（前端侧约定）

后端返回 `delta_v` 时直接消费；前端仅做展示层派生（`vector.deltaV` getter）：

```
ΔV = 最新 V_obs − V_base
每个分量：ΔV[k] = latestObs.values[k] − vBase[k]   (k ∈ wood/fire/earth/metal/water)
```

- **禁止前端实现映射逻辑**（八字→S 向量、PPG→脉象等均在 spum-core，`RULE-MAPPING`）。
- 趋势状态四态（`trend_state`）：`slow_drift` / `abrupt` / `periodic` / `stable`，展示文案必须走 `constants/compliance.js` 的 `TREND_STATE_LABELS`。

### 3.3 API 层对接（端点约定）

后端基础地址 `http://localhost:8000`（`VITE_API_BASE` 可覆盖），`vite.config.js` 已配 `/api`、`/health`、`/ws` 代理。

| 方法 | 路径 | 用途 | 对应表 |
|------|------|------|--------|
| GET | `/health` | 健康检查（启动探测） | — |
| POST | `/api/users` | 创建用户 | users |
| GET | `/api/users/{user_id}` | 用户档案 | users |
| POST | `/api/users/{user_id}/privacy/export` | 隐私导出令牌 | users |
| DELETE | `/api/users/{user_id}` | 一键删除 | users + 关联 |
| GET | `/api/users/{user_id}/vectors` | V_base + 最近 V_obs | wuxing_base_vectors / wuxing_obs_vectors |
| GET | `/api/users/{user_id}/drift/series?range=` | 漂移时序 | vector_drift_series |
| POST | `/api/obs/questionnaire` | 问诊向量（source_flags.questionnaire） | wuxing_obs_vectors |
| POST | `/api/obs/multimodal` | 舌象/声纹采集上传（source_flags.tongue/voice） | wuxing_obs_vectors |
| POST | `/api/ppg/sessions` | 创建 PPG 会话 | ppg_sessions |
| POST | `/api/ppg/sessions/{session_id}/samples` | 批量上传波形（50Hz 采样点） | ppg_samples |
| POST | `/api/interventions` | 创建干预方案 | interventions |
| GET | `/api/interventions/{user_id}` | 干预记录 + 前后对比 | interventions / intervention_results |
| GET/POST | `/api/knowledge-base/items` | 知识库条目查询/维护 | knowledge_base |
| GET | `/api/users/{user_id}/reports` | 推演报告列表 | 聚合 |
| GET | `/api/users/{user_id}/notifications` | 提醒通知列表 | 聚合 |

**编码规范**：端点路径一律集中定义在 `src/api/endpoints.js`，视图内禁止硬编码 URL；数据获取统一走 store action（`user` / `vector` / `session`），视图组件不直接散落 axios 调用（上传、表单提交等一次性动作可例外）。

### 3.4 WebSocket 实时刷新

- 端点：`ws://host/ws/live?user_id={id}`（vite proxy 已配 `/ws`）。
- 消息：`{type:"sample", session_id, t_ms, ppg_raw}`（PPG 实时波形）/ `{type:"vector_update", v_obs, delta_v}`（向量更新）。
- 客户端：使用 `src/api/client.js` 的 `wsClient`，**自带指数退避重连（1s→15s）与手动关闭标记**，禁止自行 new WebSocket 裸接。
- 状态管理：`session.connectWs(userId)` / `disconnectWs()`，`wsStatus` 反映连接态并在界面显示（连接中/已连接/已断开）。
- **降级**：断线不崩溃，显示「实时连接已断开，正在重连…」。

### 3.5 上传流程（舌象/声纹 + PPG）

**舌象/声纹（CollectView）**：
1. 前端采集 → 压缩（舌象图片限制 ≤ 2MB，压缩为 JPEG；声纹录制为 webm）→ 时间戳对齐；
2. `POST /api/obs/multimodal`，携带 `source_flags: {tongue, voice}` 与文件引用；
3. **前端不做识别**，识别在 Phase 1 后端完成。

**PPG（Phase 1 联调项）**：
1. `POST /api/ppg/sessions` 创建会话；
2. 采集端按 50Hz 攒批（如每 2s 一批）→ `POST /api/ppg/sessions/{sid}/samples`，`session.uploadQueue` 暂存、`sampleProgress` 展示进度；
3. 原始波形仅会话内预览，**不落前端本地存储**（`RULE-PRIVACY`）。

---

## 四、合规强制要求（红线）

### 4.1 禁词表（展示层禁止出现）

| 禁用 | 替换 |
|------|------|
| 诊断 / 诊疗建议 | SPUM 体质生活推演参考 |
| 治疗 / 疗效 | 向量漂移趋势观察 |
| 处方 / 医嘱 / 药用 | 生活化干预记录（药膳/药茶/导引/衣物/时辰） |
| 证候 / 疾病 / 症状缓解 | 五形状态描述 |
| 预警 / 异常 | 趋势观察提示（需观察记录） |

> 禁词表唯一权威源：`src/constants/compliance.js` 的 `FORBIDDEN_TERMS`。新增文案先自查再提交。

### 4.2 常驻合规条

- 组件：`src/components/ComplianceBar.vue`，由 `App.vue` 根级固定渲染（`position: fixed; bottom: 0`），**所有路由共享，禁止移除或条件隐藏**。
- 文案（不可改动）：**本内容仅为 SPUM 体质生活推演参考，不构成医疗诊断、诊疗建议**。

### 4.3 趋势观察提示措辞

- 趋势状态展示：必须使用 `TREND_STATE_LABELS`（平缓漂移（观察）/ 近期漂移幅度较大（建议观察记录）/ 呈周期性变化 / 整体平稳）。
- 干预对比弹窗模板：`该次药茶/药膳干预的向量修正增益为 X（方向一致性评分），仅用于个体模型校正参考`（`docs/03` §5）。
- 报告页 notice 走 `TREND_NOTICE_TEMPLATE` 模板，禁止疾病类表述。

### 4.4 数据隐私

- 原始 PPG 波形 / 舌象图仅会话内预览，前端不持久化；
- 用户导出/删除必须经 `privacy_export_token` 令牌接口（`/api/users/{id}/privacy/export`），前端不得自行拼接下载路径。

---

## 五、分阶段开发任务清单

### Phase 0（当前骨架已就绪，优先完成）

| # | 任务 | 状态 |
|---|------|------|
| P0-1 | 骨架可运行：`npm install && npm run dev` 启动无报错 | ✅ 已具备 |
| P0-2 | Dashboard 中区漂移矢量图（V_base 锚点 → V_obs 箭头 + 健康凸多面体参考） | ⏳ 待实现 |
| P0-3 | 三区联动：观测点点击 → 右区定位；底栏时间轴回放 | ⏳ 待实现 |
| P0-4 | UserManageView 联调：创建用户 → 生辰干支录入 → V_base 生成回显 | ⏳ 后端就绪后 |
| P0-5 | DashboardView 数据接入：`fetchVectors` / `fetchDrift` 真实数据渲染（替换演示占位） | ⏳ 后端就绪后 |
| P0-6 | CollectView 舌象压缩上传真实化（File → Blob 压缩 → multipart） | ⏳ 待实现 |

### 后续联调项（按 Phase 推进）

| # | 任务 | Phase |
|---|------|-------|
| P1-1 | PPG 会话创建 + 50Hz 攒批上传 + 实时波形预览（WebSocket） | 1 |
| P1-2 | 问诊向量提交后漂移曲线即时刷新 | 1 |
| P1-3 | 干预记录闭环：创建干预 → 前后对比 → 个体响应系数回显 | 1 |
| P1-4 | 知识库管理后台完善（分类筛选/合规审核标记） | 2 |
| P1-5 | 3D 漂移矢量图（echarts-gl，PCA 投影） | 2 |
| P1-6 | H5 响应式适配打磨（移动端 H5 主入口验证） | 3 |
| P1-7 | Flutter 客户端接入同一后端（Phase 3 预留，**不在本仓实现**） | 3 |

---

## 六、质量与验收标准

### 6.1 可运行

- `npm install` 无依赖解析错误；`npm run dev` 启动后 `http://localhost:5173` 可访问，7 路由均可跳转；
- 浏览器控制台无未捕获异常；ECharts 图表正常渲染（数据为空时显示占位而非报错）。

### 6.2 /health 降级

- 后端不可达时：页面进入只读演示模式，显示「后端服务不可达」提示，**不得白屏/崩溃/无限 loading**；
- WebSocket 断开：显示重连提示，指数退避自动恢复，恢复后状态回 live。

### 6.3 代码风格

- Vue 组件使用 `<script setup>` 组合式 API；模板不写业务逻辑；
- 数据获取走 store action，端点路径集中 `endpoints.js`；文案统一引用 `compliance.js` 常量，**禁止在视图内硬编码合规文案/URL**；
- 组件命名：视图 `*View.vue`，通用组件 PascalCase，图表组件放 `components/charts/`；
- 不引入未约定的 UI 库/状态库；ECharts 实例在 `onBeforeUnmount` 必须 `dispose()` 并移除 resize 监听；
- 所有新增页面必须包含非医疗措辞自查记录（README 或 PR 说明中注明）。

### 6.4 验收清单

- [ ] 7 模块路由全部可达，页面标题正确
- [ ] 常驻合规条在所有页面可见且文案一致
- [ ] 禁词表扫描：全仓搜索 `FORBIDDEN_TERMS` 词汇，视图/组件内 0 命中（注释除外）
- [ ] /health 不可达时降级提示正常
- [ ] Dashboard 三区联动可用，ΔV 计算与后端 `delta_v` 一致
- [ ] 上传流程时间戳对齐、进度展示正确，原始数据不落本地
- [ ] `npm run build` 通过（无构建告警阻塞）

---

## 附：与本仓文档的对应关系

| 本 Prompt | 对应文档 |
|-----------|---------|
| §三 三区布局 | `docs/03_前端拓扑可视化页面设计.md` |
| §三 ΔV 计算 | `docs/01_核心向量计算伪代码.md` §2 |
| §三 API/DB 对应 | `docs/02_数据库表结构设计.md` |
| §二 目录与模块、§四 合规 | `docs/04_前端架构设计.md` |
| 全生态基准 | `E:\工作\SPUM-PROJECT\01_研发中心\青囊产品开发文档\青囊生活管家全生态架构.md` |
| AI 文档惯例 | `E:\工作\SPUM_AGENT.md` / `E:\工作\PROJECT_AI_PROMPT.md` / `qingnang\AGENT.md` |

> **致阅读此文件的 AI**：你在 `spum-engine/frontend` 中的一切改动，都服务于"青囊生活管家 SPUM 体质生活推演"这一非医疗定位。合规红线优先于一切功能实现；不确定的文案先查 `compliance.js`，不确定的端点先查 `endpoints.js`。
*（内容由AI生成，仅供参考）*
