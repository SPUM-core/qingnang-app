# 青囊生活管家（qingnang-APP）｜落地项目

> **最后更新：2026-09-26 | 版本：v0.1.0（可运行原型）**
> **角色定位**：青囊生活管家可穿戴硬件产品的后端落地项目——消费 qingmeng-engine 的 SPUM 五形向量推演 API，将先天八字 → 真太阳时 → 藏干版五形向量 → 用户端健康趋势观察、食疗建议、穿搭搭配和作息指导贯通。

---

## 目录结构

```
qingnang-APP/
├─ README.md
├─ backend/                              ← FastAPI 业务后端（2026-09-26 补齐）
│   ├─ app/
│   │   ├─ api/v1/
│   │   │   ├─ auth.py                   ← /api/v1/auth/login|register|me
│   │   │   ├─ cases.py                  ← /cases/mine, /cases/onboarding（八字 + 建档）
│   │   │   ├─ assistant.py              ← /reasoning/bazi（代理 qingmeng-engine）
│   │   │   ├─ ppg.py                    ← PPG 观测采集
│   │   │   ├─ treatment.py              ← 调理方案
│   │   │   ├─ shop.py                   ← 商城
│   │   │   ├─ notifications.py          ← 提醒
│   │   │   └─ ...
│   │   ├─ models/                       ← SQLAlchemy (User/Case/Observation/TreatmentPlan/...)
│   │   ├─ utils/
│   │   │   ├─ security.py               ← bcrypt password hash + JWT
│   │   │   └─ wuxing.py                 ← 五形向量工具
│   │   ├─ config.py, database.py, main.py
│   ├─ seed/seed_data.py                 ← 种子用户 + 商城数据
│   ├─ data/qingnang.db                  ← SQLite（Phase 2 换 PostgreSQL）
│   └─ requirements.txt
├─ frontend/                             ← Vue3 Web 前端（Vite + Pinia + ECharts）
│   ├─ src/
│   │   ├─ api/client.js                 ← axios + 所有 API（auth/bazi/cases/...）
│   │   ├─ components/
│   │   │   ├─ charts/RadarChart.vue     ← 五形雷达（v_innate 可视化）
│   │   │   ├─ charts/DriftChart.vue     ← ΔV 漂移趋势
│   │   │   ├─ LayoutShell.vue           ← 主应用壳（Banner + Nav + Main）
│   │   │   ├─ QingnangAssistant.vue     ← 右下角 AI 助手浮窗
│   │   │   ├─ TodoCard.vue              ← 今日提醒卡片
│   │   │   └─ ComplianceBar.vue         ← 合规提示条
│   │   ├─ stores/
│   │   │   ├─ user.js                   ← Pinia store（login/register/logout/fetchMe）
│   │   │   ├─ session.js
│   │   │   └─ vector.js
│   │   ├─ router/index.js               ← 路由守卫：login 跳转 / onboarding 守卫
│   │   ├─ views/
│   │   │   ├─ LoginView.vue             ← 登录/注册独立页面（无 LayoutShell）
│   │   │   ├─ DashboardView.vue         ← 主页：问候 + 雷达 + ΔV + 今日提醒
│   │   │   ├─ QuestionnaireView.vue     ← 渐进式建档（基础信息→先天画像→问诊）
│   │   │   ├─ SettingsView.vue          ← 设置（已修复：退出登录 + 真实数据）
│   │   │   ├─ CollectView.vue           ← PPG 采集入口
│   │   │   ├─ CaseDetailView.vue        ← 体质档案详情
│   │   │   ├─ KnowledgeBaseView.vue
│   │   │   ├─ ShopView.vue / ShopDetailView.vue
│   │   │   ├─ UserManageView.vue
│   │   │   └─ NotificationsView.vue
│   │   ├─ App.vue, main.js
│   ├─ package.json                      ← Vue 3.5 + ECharts 5.5 + Pinia 2.3
│   └─ vite.config.js
├─ docs/                                 ← 设计文档
└─ .trae/                                ← Agent 规则 / 技能
```

---

## 生态关系

| 项目 | 关系 |
|------|------|
| **qingmeng-engine** | 上游推理引擎——`/v1/reasoning/bazi` 真太阳时 + 四柱八字 + 藏干版五形向量，本仓通过 `assistant.py` httpx 代理调用 |
| **spum-core** | 理论权威（SPUM 公理来源），五形向量、藏干权重、真太阳时公式均对齐此项目 |
| **SPUM-PROJECT** | 总控协调层 |

**合规硬约束**：全部输出均为"体质趋势观察提示"，不构成医疗诊断、诊疗建议。禁用诊断/治疗/疗效/处方等医疗词汇。

---

## 青囊核心规则（八字推演）

> **无论输入阳历还是阴历，都先换算真太阳时（TST），再以真太阳时对应的节气/时辰排四柱八字。**

```
输入 (阳历 or 阴历) + 时辰 + 出生地
   │
   ├─ 阴历 ──→ Lunar.fromYmdHms → getSolar() ──┐
   │                                            ▼
   │                               统一阳历 datetime
   │                                            │
   │                               出生地 → 经度（35 城市字典 + 模糊匹配）
   │                                            │
   │                               平太阳时 + 经度修正 ±(lng-120)*4min + 均时差 (NOAA 简化公式)
   │                                            │
   │                               真太阳时 (TST) — 阳历 datetime
   │                                            │
   │                               Solar.fromYmdHms(TST) → lunar_python.getEightChar()
   │                                            │
   │                               四柱八字 + 藏干版五形向量 SPUM v_innate
```

**时辰中点策略**：用户输入"寅时" → 取 04:00（中点），给 ±30 min 真太阳时修正留缓冲。西部极端城市（乌鲁木齐 `-130 min`）仍可能跨时辰——这是正确的天文行为，通过 `tst_shichen` 字段暴露差异。

**藏干权重**：天干 1.0 + 地支藏干本气 0.7 / 中气 0.2 / 余气 0.1（传统子平简化）。

**时柱边界**：lunar_python 内部按地支时辰边界（01-03丑、03-05寅...）自动切换，23:00 换日柱，年柱以立春切换（太阳节气）而非农历正月初一。

---

## 当前进度

### ✅ 已完成

| 模块 | 说明 |
|------|------|
| **登录/注册流** | `/login` + `/register` 独立页面，Pinia `user.logout()` 清 token + 路由跳登录，守卫拦截未登录 |
| **渐进式建档** | QuestionnaireView 三步：表单（阳历/阴历切换）→ 真太阳时八字面板 + RadarChart 雷达 + 弱项提示 → 弱项动态生成问诊题 → onboarding 存 DB |
| **真太阳时八字推演** | qingmeng-engine `bazi.py`：NOAA 均时差公式（RMS < 0.5 min）+ 35 城市经度字典 + lunar_python 排四柱 |
| **后端桥接** | `assistant.py` 代理 `/reasoning/bazi`；`cases.py` onboarding 支持前端预推演结果复用（跳过重算）|
| **设置页修复** | 退出登录真实调 store + router；profile 用 user store + cases/mine 真实数据；补 `created_at` + `observations` 返回字段 |
| **端到端验证** | 注册 → 自动登录 → onboarding 三步 → cases/mine → 主页建档完成；阳历 ↔ 阴历输入结果一致 |

### 🔨 进行中 / 待办

- PPG 真实采集入口（当前为 mock 数据）
- 后端 cases/mine 补 `pillars` / `true_solar_time`（需 Case 模型加 Column）
- 调理方案自动生成（当前为静态模板）
- PostgreSQL 迁移（Phase 2）

---

## 快速启动

### 1. 启动 qingmeng-engine（八字推演）

```bash
cd e:/工作/qingmeng-engine
python -m uvicorn qingmeng_engine.inference.server:app --port 8000 --reload
```

验证：`POST /v1/reasoning/bazi`

```json
{"birth_date": "1986-08-02", "birth_hour": "寅时", "birthplace": "广州"}
→ bazi: 丙寅/乙未/戊寅/甲寅, TST: 1986-08-02 03:26:35, v_innate: {water:0, wood:52, fire:22, earth:25, metal:0}
```

### 2. 启动 backend（业务 API）

```bash
cd e:/工作/qingnang-APP/backend
python -m uvicorn app.main:app --port 8767 --reload
```

种子账号：`138******00` / `qingnang2026`

### 3. 启动 frontend（Vite dev）

```bash
cd e:/工作/qingnang-APP/frontend
npm run dev
# → http://localhost:5173
```

### 端口一览

| 服务 | 端口 | 说明 |
|------|------|------|
| qingmeng-engine | `8000` | 真太阳时 + 四柱八字 + 藏干版 v_innate |
| qingnang backend | `8767` | 认证 / cases / onboarding / treatment / shop |
| vite dev server | `5173` | Vue3 前端，HMR 自动刷新 |
| Ollama + spum-coder | `11434` | LLM 推理 |

---

## API 速查

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/v1/auth/login` | POST | `{phone, password}` → `{token, qingnang_id, nickname, is_onboarded}` |
| `/api/v1/auth/register` | POST | `{phone, password, nickname}` → 自动登录 |
| `/api/v1/auth/me` | GET | 当前用户完整信息（v_base, phone 等）|
| `/api/v1/assistant/reasoning/bazi` | POST | 代理 qingmeng-engine；`{birth_date, birth_hour?, birthplace?, birth_date_type?}` |
| `/api/v1/cases/mine` | GET | 当前用户完整案例（bazi/v_innate/syndrome/observations/plan）|
| `/api/v1/cases/onboarding` | POST | 初始化建档（前端预推演带 v_innate + bazi_result 可跳过重算）|
| `/v1/reasoning/bazi` (qingmeng-engine) | POST | 真太阳时八字推演：返回 pillars/lunar/true_solar_time/v_innate/S/S_hide |

### bazi 响应字段

```json
{
  "bazi": "丙寅/乙未/戊寅/甲寅",
  "pillars": ["丙寅", "乙未", "戊寅", "甲寅"],
  "lunar": "一九八六年六月廿七",
  "true_solar_time": "1986-08-02 03:26:35",
  "tst_shichen": "寅",
  "longitude": 113.26,
  "city_input": "广州",
  "v_innate": {"water": 0, "wood": 52, "fire": 22, "earth": 25, "metal": 0},
  "engine": "spum_bazi"
}
```

---

## 设计基准

| 维度 | 基准文档 |
|------|---------|
| 全生态架构 | SPUM-PROJECT/01_研发中心/青囊产品开发文档 |
| 向量计算 | `docs/01_核心向量计算伪代码.md` |
| 前端架构 | `docs/04_前端架构设计.md` |
| 数据库 | `docs/02_数据库表结构设计.md` |
| 真太阳时公式 | NOAA Solar Calculator 简化版（RMS < 0.5 min）|

*（内容由AI生成，仅供参考）*
