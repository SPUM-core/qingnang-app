# Phase 0 差距清单 — docs/01-07 + 08 对照代码现状

> **盘点日期**：2026-09-26 | **基准代码**：qingnang-APP (backend FastAPI + frontend Vite 5173)
> **状态符号**：✅ 已实现 / ⚠️ 部分实现 / ❌ 未实现 / 🔴 架构偏差

---

## 文档 01: 核心向量计算伪代码

| 模块 | 状态 | 代码位置 / 差距说明 |
|------|------|---------------------|
| V_base 先天基底生成（八字干支 → 五形 S 向量） | ⚠️ 部分 | `cases.onboarding()` 接收 v_innate 硬编码存入 Case，无 bridge/exchange 边车校验，无 spum-core 映射版本追踪 |
| V_obs 后天观测向量（PPG → 脉象观测） | ⚠️ 部分 | `ppg.upload` 接收原始波形后调 qingmeng-engine `/ppg` 端点解析出 v_obs，存入 Observation.v_obs(JSONB)，但融合链（舌象/声纹+PPG）未接 |
| ΔV 漂移向量计算 | ⚠️ 部分 | `computeYinYangModel()` 在 DriftChart.vue 前端实现（旧权重法：fire*0.35+...），**沙盒 SPUM 算法 computeHealthBounds() 未迁入后端** |
| SPUM 引擎映射（bridge/exchange/inbox + sha256 边车） | ❌ 未实现 | 整个 bridge/exchange 架构不存在，所有映射在 qingmeng-engine 内部，无版本化投递机制 |
| 时空扰动向量 V_time-space（子午流注 + 玄空飞星） | ❌ 未实现 | Phase 2 接入，无占位代码 |

---

## 文档 02: 数据库表结构设计

### 表 vs 实现对照

| 设计表 | Phase | 状态 | 替代 / 差距说明 |
|--------|-------|------|-----------------|
| `users` | 0 | ✅ 已实现 | 基础字段到位，缺 privacy_export_token UUID |
| `wuxing_base_vectors` | 0 | 🔴 架构偏差 | **不存在**，用 `cases.v_innate(JSONB)` 替代，无版本化 |
| `wuxing_obs_vectors` | 0 | ⚠️ 部分 | 用 `observations.v_obs(JSONB)` 替代，语义一致但表名不同 |
| `vector_drift_series` | 0 | ❌ 未实现 | 漂移时序在前端动态计算，无持久化存储 |
| `ppg_sessions` | 0 | ❌ 未实现 | PPG 采集元数据存在内存/API 层，无表 |
| `ppg_samples` | 0 | ❌ 未实现 | 原始 50Hz 波形未持久化（流式上传后丢弃） |
| `interventions` | 1 | 🔴 架构偏差 | 用 `treatment_plans` 替代，字段不兼容（治疗方案 vs 药膳/药茶干预） |
| `intervention_results` | 1 | ❌ 未实现 | 干预前后对比无表 |
| `response_coefficients` | 1 | ❌ 未实现 | 个体响应系数 α_user 无存储 |
| `knowledge_base` | 0 | ❌ 未实现 | `knowledge.py` API 返回 hardcode mock 数据，无表 |
| **docs/08 新增** `trajectory_events` | 0 | ❌ 未实现 | 事件（手术/药物/大运/窗口期）无持久化表，内存推断 |

### 数据库引擎

| 项目 | 状态 |
|------|------|
| PostgreSQL | ✅ 已配置（DATABASE_URL，表名小写 snake_case） |
| JSONB | ✅ 已用（v_obs, v_innate, syndrome_hint） |
| 敏感数据加密 | ❌ 未实现 |
| 一键导出/删除 | ❌ 未实现（users.privacy_export_token 字段缺失） |

---

## 文档 03: 前端拓扑可视化页面设计

| 区域 | 设计要求 | 状态 | 实现说明 |
|------|----------|------|----------|
| **左区：五形雷达图** | V_base vs 最新 V_obs 叠加对比 + 分量数值表 | ✅ 已实现 | `RadarChart.vue` 支持先天基底 + 当前观测 + 健康区带三层叠加 |
| **中区：漂移矢量图** | 先天基底点 + 后天观测点 + 漂移箭头（2D/3D） | ⚠️ 简化 | `DriftChart.vue` 是时序曲线非矢量图，无 3D 切换，漂移用 signedDrift 标量代替矢量 |
| **右区：时序趋势曲线** | ΔV 五分量演化 + 趋势状态着色 + 干预节点 | ✅ 已实现 | DriftChart.vue 完整实现，含事件 markLine/markPoint |
| **底部时间轴回放** | 可拖动回放历史观测点 + 干预节点前后对比 | ⚠️ 部分 | `dataZoom` slider 有，但无"干预节点点击查看前后对比"交互 |
| **常驻合规条** | 全站固定 | ⚠️ 部分 | `ComplianceBar` 组件存在，但 App.vue 集成需确认覆盖所有页面 |
| **健康凸多面体参考范围** | 中区矢量图的健康空间参考 | ❌ 未实现 | 旧 computeYinYangModel 用线性 sigmoid，新 SPUM 用 EMA 滞后边界 |

---

## 文档 04: 前端架构设计

### stores（3/3 ✅）
| Store | 状态 | 备注 |
|-------|------|------|
| `user.js` | ✅ | 用户态/生辰/时区 |
| `vector.js` | ✅ | V_base/V_obs/ΔV/ fetchTrajectory() |
| `session.js` | ✅ | PPG 采集态/上传队列 |

### views（设计 7 / 实际 16）
| 设计 View | 状态 | 备注 |
|-----------|------|------|
| DashboardView | ✅ | 核心主视图 |
| QuestionnaireView | ✅ | 问诊录入 |
| CollectView | ✅ | 多模态采集（含舌象/声纹子路由） |
| ReportView | ✅ | 趋势观察报告 |
| KnowledgeBaseView | ✅ | 知识库管理 |
| UserManageView | ✅ | 用户管理 |
| NotificationsView | ✅ | 提醒通知 |
| ShopView / ShopDetailView | 🆕 超纲实现 | 商城（非设计文档范围） |
| LoginView | 🆕 合理补充 | 鉴权入口 |
| SettingsView | 🆕 合理补充 | 设置页 |
| CaseDetailView | 🆕 合理补充 | 病历详情 |
| DiscoverView / VoiceSampleView / BodyPhotoView / PpgCollectView | 🆕 补充 | 子视图 |

### 组件
| 组件 | 状态 | 备注 |
|------|------|------|
| `RadarChart.vue` | ✅ | 五形雷达图 |
| `DriftChart.vue` | ✅ | 漂移时序曲线（含新算法旁路） |
| `ComplianceBar.vue` | ✅ | 合规条 |
| `LayoutShell.vue` | ✅ | 布局壳 |
| **SPUM 算法前端模块** | ❌ 缺失 | `spumCurves.js`（computeYX/computeHealthBounds/ema/metalElasticity）未独立成模块 |

---

## 文档 05: 前端开发 Prompt

> 此文档为 Prompt 工程指南，无直接可执行的差距项。核心要点已体现在 03/04 的实现中。

---

## 文档 06: PPG 脉搏采集开发日志

| 环节 | 状态 | 说明 |
|------|------|------|
| PPG 硬件流式接入 | ✅ | `ppg.py /stream` SSE endpoint |
| PPG → v_obs 解析 | ✅ | 调 qingmeng-engine `/ppg` 端点 |
| 波形持久化 | ❌ | 原始 50Hz 波形上传后丢弃，无 ppg_samples 表 |
| 采集会话管理 | ⚠️ | 有 hardware-status/disconnect，但无 ppg_sessions 表 |

---

## 文档 07: 脉诊算法迭代方向

| 迭代方向 | 状态 | 说明 |
|----------|------|------|
| v0.1 health_score 指数收敛 | ✅ 已实现 | `_health_score()` + 目标 72 |
| v0.2 三曲线 yin-yang model | ✅ 前端实现 | DriftChart.vue `computeYinYangModel()` |
| **v0.3 SPUM computeHealthBounds** | ⚠️ 沙盒有/前端旁路/后端无 | tizhi-curve/index.html 有完整算法，前端 mock 旁路已接，**后端未迁移** |
| 时空扰动融合 | ❌ | Phase 2 |
| 干预响应系数 α_user | ❌ | Phase 1 |

---

## 🆕 docs/08 API 契约差距（三层预测）

### 端点对照表

| 契约端点 | HTTP | 状态 | 现有端点 | 差距 |
|----------|------|------|----------|------|
| `/api/v1/cases/trajectories` | GET | ⚠️ 需升级 | 已有 v0.2 | 需加入 `driftData/yinTop/yangBot/diseaseModes/elArr/algorithm` 字段 |
| `/api/v1/cases/trajectories/year-view` | GET | ❌ 未实现 | — | 后端需建 `buildYearView()` 翻沙盒逻辑 |
| `/api/v1/cases/radar` | GET | ❌ 未实现 | — | 后端需返回 `v_innate + v_current + health_zone` |
| `/api/v1/predict/instant` | POST | ❌ 未实现 | — | L1 瞬时预测（单观测→即时体质偏移） |
| `/api/v1/predict/short-term` | POST | ❌ 未实现 | — | L2 短期预测（30天趋势推演） |
| `/api/v1/predict/lifetime` | POST | ❌ 未实现 | — | L3 终身预测（八字大运推演） |

### 后端还需要补的
1. **SPUM 算法后端模块**：`backend/app/utils/trajectory_algorithm.py`（computeYX/computeHealthBounds/buildYearView/metalElasticity/ema/ganzhi_to_elems）
2. **trajectory_events 表 DDL**：`docs/08` L416-435 的 DDL 未执行
3. **events 自动推断**：当前 trajectories 端点返回 `events: []`（注释说"暂时返回空数组"）
4. **大运 markArea 支持**：前端 DriftChart.vue 有 dayunMarkArea 字段处理能力，但后端没算

### 前端还需要补的
1. **SPUM 算法独立模块**：`src/utils/spumCurves.js`（让前端能本地算三曲线，不依赖后端）
2. **vectorStore.fetchTrajectory() 升级**：当前 L235-268 只映射 v0.2 字段，需兼容 v0.3 新字段
3. **year-view 视图**：Dashboard 切换到终身视图时，需带 `?view_mode=year` 参数请求后端新端点

---

## 架构决策记录

| 决策 | 内容 |
|------|------|
| ✅ 位置与弹性解耦 | SPUM 边界位置（EMA）与金属弹性（metalElasticity）独立调制，不再耦合 |
| ✅ 坐标系对齐 | 前端 DriftChart.vue 加 algorithm 旁路，检测到新算法时翻转 driftData 符号 |
| ✅ 算法迁移优先级 | 先让沙盒算法在前端独立跑通（mockup 已验证），再迁入后端 |
| ⏳ bridge/exchange 推迟 | Phase 0 暂不引入 spum-core 边车投递，直接本地映射 |
| ⏳ PostgreSQL 表名兼容 | 用 `cases` 代替 `wuxing_base_vectors`，`observations` 代替 `wuxing_obs_vectors`，Phase 2 再标准化 |
