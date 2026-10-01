# 三层预测 + 体质曲线 API 契约

> **版本**: v0.1 (可落地)  
> **日期**: 2026-09-29  
> **基准**: PRD Phase 0 "三层预测最小闭环 + 两个核心可视化"  
> **算法来源**: `tizhi-curve/index.html` computeHealthBounds() / buildYearView()  
> **与现有端点关系**: 补充 `cases.get_trajectories`（当前 v0.2），新增三个独立端点

---

## 0. 三层预测定位

| 层级 | 输入 | 时间尺度 | 算法 | 可视化 |
|------|------|---------|------|--------|
| **L1 即时预测** | 单次 PPG（v_obs） | 小时级 | computeYX 实时算 Y/X → 当天饮食/饮酒/寒热倾向 | DriftChart 当前点 Tooltip |
| **L2 短期预测** | PPG v_obs + 八字 v_innate | 天/周级 | v_innate 作基线 + EMA 滞后边界 → 短期寒热趋势 + 风险提醒 | DriftChart 实线 + 健康区间带 |
| **L3 长期预测** | 仅八字 v_innate + 大运排盘 | 年/终身 | ganzhi_to_elems + dayunLiunianDelta + 生克传导 → 终身健康区间带 + 出界节点 | DriftChart 年视图大运色带 |

**核心公理**:
- `Y + X ≈ 100`（阳旺则阴衰守恒）
- `yangBot = -Y_boundary × SCALE`，`yinTop = +X_boundary × SCALE`（边界位置仅由阴阳浓度决定，金属弹性解耦）
- 金属弹性 `el` 仅调制出界判定阈值，不改变边界绝对位置

---

## 1. 端点总览

| 方法 | 路径 | 场景 | 状态 |
|------|------|------|------|
| GET | `/api/v1/cases/trajectories` | 体质曲线核心数据（月视图·真实观测） | ✅ v0.2 已有，需升级 |
| GET | `/api/v1/cases/trajectories/year-view` | 纯八字推演年视图 | 🆕 新增 |
| GET | `/api/v1/cases/radar` | 体质雷达图三层数据 | 🆕 新增 |
| POST | `/api/v1/predict/instant` | L1 即时预测 | 🆕 新增 |
| POST | `/api/v1/predict/short-term` | L2 短期预测 | 🆕 新增 |
| POST | `/api/v1/predict/lifetime` | L3 长期预测 | 🆕 新增 |

---

## 2. /cases/trajectories — 升级契约（月视图·真实观测）

### 现状 vs 目标

当前 v0.2 返回 `health_score(0-100)` + 指数收敛 target 曲线。目标是升级为 **SPUM 三曲线**（Y/X 净阳量 + 滞后边界 + 金属弹性）。

### 请求

```
GET /api/v1/cases/trajectories?view=month
Authorization: Bearer <JWT>
```

### 响应 Schema

```jsonc
{
  // ─── 标识 ───
  "user_id": "uuid",
  "case_id": 1,
  "view_mode": "month",           // "month" = 真实观测月视图

  // ─── 五行基底 ───
  "v_innate": { "wood": 55, "fire": 40, "earth": 50, "metal": 60, "water": 65 },
  "v_current": { ... },           // 最新观测

  // ─── 观测点序列（真实 PPG 数据）───
  "elems": [
    {
      "day": 1,                    // 第 N 天
      "t": "07-18",                // 月日
      "hhmm": "10:00",             // 时分
      "age": 39,
      "observed_at": "2026-07-18T10:00:00",
      "wood": 60, "fire": 58, "earth": 35, "metal": 50, "water": 48,
      "syndromeHint": "脾虚湿困+上热下寒",
      "paradoxFlags": ["earth_false_fullness"],
      "sqi": 0.82
    }
  ],

  // ─── SPUM 三曲线（每行对应 elems[i]）───
  "driftData": [-1.2, 0.8, 1.1, ...],     // (Y-X)×SCALE，实线·净阳量
  "yinTop":    [+5.2, +4.8, +5.0, ...],   // +X_boundary×SCALE，黄线·阴界（上虚线）
  "yangBot":   [-5.8, -5.5, -6.0, ...],   // -Y_boundary×SCALE，红线·阳界（下虚线）
  "diseaseModes": [null, null, "acuteDeviation", ...], // null | "acuteDeviation" | "chronicBoundary"
  "elArr":     [0.72, 0.85, 0.91, ...],   // 金属弹性（0.3~1.0），区间宽度调制器

  // ─── 事件标注 ───
  "events": [
    {
      "day": 1,
      "type": "手术",              // "手术" | "药物" | "窗口期" | "转大运" | "间断" | "波动"
      "label": "右乳腺癌手术+化放疗",
      "direction": "发散",
      "scoreDelta": -6.3,
      "isParadox": false,
      "isMedical": true,           // 前端用这个判断显示红色 rect vs 灰色 pin
      "impact": { "fire": 12, "metal": 10 }  // 伤害量（正数），前端 tooltip 用
    }
  ],

  // ─── 元信息 ───
  "healthyZone": { "min": 40, "max": 60, "label": "健康区带 H" },
  "observationCount": 12,
  "computedAt": "2026-09-29T10:00:00",
  "algorithm": "spum_computeHealthBounds_v1"  // 便于前端判断是否新算法
}
```

### 算法说明（后端实现参考 tizhi-curve）

```python
# 伪代码
def get_trajectories(case: Case, db: Session) -> dict:
    # 1. 取 Observation 序列
    obs = db.query(Observation).filter_by(case_id=case.id)\
            .order_by(Observation.observed_at).all()
    elems = [_observation_to_elem(o, case) for o in obs]

    # 2. computeYX：每点五行 → [0,100] 的 Y/X 浓度
    Y_real = [computeYX(p)['Y'] for p in elems]
    X_real = [computeYX(p)['X'] for p in elems]

    # 3. EMA 滞后 4 年（月视图：tau 调整为样本点数的 1/3）
    Y_boundary = ema(Y_real, tau=max(2, len(elems)//3))
    X_boundary = ema(X_real, tau=max(2, len(elems)//3))

    # 4. 金属弹性（EMA 6 年 / 样本点数 1/2）
    metal_boundary = ema([p['metal'] for p in elems], tau=max(2, len(elems)//2))
    el_arr = [metalElasticity(m) for m in metal_boundary]

    # 5. 边界位置（与 el 解耦！）
    yinTop    = [round(x * SCALE * 10) / 10 for x in X_boundary]
    yangBot   = [round(-y * SCALE * 10) / 10 for y in Y_boundary]
    driftData = [round((y - x) * SCALE * 10) / 10 for y, x in zip(Y_real, X_real)]

    # 6. 出界判定（el 调制有效宽度）
    diseaseModes = detect_disease(driftData, yinTop, yangBot, el_arr)

    # 7. 事件（自动推断 + 预设临床事件 + 后端 events 表）
    events = build_events(case, obs)
```

---

## 3. /cases/trajectories/year-view — 纯八字推演年视图

### 场景
用户在 Dashboard 切换到"终身视图"，想看大运对体质曲线的长期推力。

### 请求

```
GET /api/v1/cases/trajectories/year-view
Query: start_year=1957&end_age=81&include_events=true
Authorization: Bearer <JWT>
```

### 响应 Schema（在 trajectories 基础上 + 大运）

```jsonc
{
  "user_id": "uuid",
  "case_id": 1,
  "view_mode": "year",

  "v_innate": { ... },

  // 大运排盘（来自 Case 的 bazi + ganzhi 字段）
  "dayun": [
    { "gan": "己", "zhi": "酉", "start": 1,  "end": 11,  "name": "己酉" },
    { "gan": "庚", "zhi": "戌", "start": 11, "end": 21,  "name": "庚戌" },
    // ... 8 段
  ],

  // 流年干支（从 start_year 自动生成）
  "liunianStartYear": 1957,

  // 核心序列：age = 0..81，每年 1 个点
  "elems": [
    { "age": 0, "dayun": "己酉", "liunian": "丁酉",
      "wood": 55, "fire": 40, "earth": 50, "metal": 60, "water": 65,
      "t": "1957·0岁·己酉" },
    // ...
  ],

  "driftData": [...],   // (Y-X)×SCALE × 82 个点
  "yinTop": [...],      // +X_boundary×SCALE × 82
  "yangBot": [...],     // -Y_boundary×SCALE × 82
  "diseaseModes": [...],
  "elArr": [...],

  // 大运色带（markArea 用）
  "dayunMarkArea": [
    { "start_age": 0,  "end_age": 11, "elem": "metal", "color": "#90A4AE", "name": "己酉" },
    { "start_age": 11, "end_age": 21, "elem": "earth", "color": "#F9A825", "name": "庚戌" },
    // ...
  ],

  // 大运标签条（graphic 用）
  "dayunLabels": [
    { "name": "己酉", "mainElem": "metal", "dyColor": "#90A4AE",
      "startAge": 0, "endAge": 11, "xStart": 0, "xEnd": 11 },
    // ...
  ],

  // 事件（如果 include_events=true）
  "events": [ ... ]
}
```

### 核心算法

后端复制 `tizhi-curve/index.html` 的 `buildYearView()` + `computeHealthBounds()`：

1. `ganzhi_to_elems(gan, zhi)` — 干支 → 五行分量（天干30% + 地支藏干70%）
2. `dayunDelta(gan, zhi)` — 大运增量（strength=22，含生克传导）
3. `dayunAtAge[age]` — 大运 smoothstep 过渡（TRANSITION_YEARS=5）
4. `smooth5(rawLiunian)` — 流年 5 年滑动平均消锯齿
5. `base = innate + dayunAtAge[age] + smoothLiunian[age] + decay + eventImpact`
6. 事件叠加 `impact = exp(-progress * 2)`，`progress = daysSinceEv / ev.days`

---

## 4. /cases/radar — 体质雷达图三层

### 请求

```
GET /api/v1/cases/radar
Query: layer=all  // "innate" | "current" | "all"
Authorization: Bearer <JWT>
```

### 响应 Schema

```jsonc
{
  "user_id": "uuid",
  "case_id": 1,

  "v_innate": { "wood": 55, "fire": 40, "earth": 50, "metal": 60, "water": 65 },
  "v_current": { "wood": 48, "fire": 52, "earth": 42, "metal": 58, "water": 55 },
  "v_health_center": { "wood": 50, "fire": 50, "earth": 50, "metal": 50, "water": 50 },

  // SPUM 每维健康区间（H_RANGE，投影到阴阳平面用）
  "h_range": {
    "wood":  30,   // 健康区间半宽
    "fire":  40,
    "earth": 30,
    "metal": 24,
    "water": 30
  },

  // 偏离度：(v_current - v_innate) / H_RANGE — 归一化后再投影
  "delta_normalized": {
    "wood": 0.2, "fire": -0.25, "earth": -0.27, "metal": -0.08, "water": -0.17
  },

  "layers": [
    { "name": "健康区带 H",   "type": "center", "value": [50,50,50,50,50],
      "color": "#7BC4A9", "style": "dashed" },
    { "name": "先天基底 S₀⁰", "type": "innate", "value": [55,40,50,60,65],
      "color": "#1A4D45", "style": "solid" },
    { "name": "当前观测 V_obs","type": "current", "value": [48,52,42,58,55],
      "color": "#A8442F", "style": "solid" }
  ],

  "computedAt": "2026-09-29T10:00:00"
}
```

---

## 5. 三层预测端点

### L1 /predict/instant（即时预测）

```
POST /api/v1/predict/instant
Authorization: Bearer <JWT>

Request body:
{
  "v_obs": { "wood": 48, "fire": 52, "earth": 42, "metal": 58, "water": 55 },
  "notes": "患者主诉喝酒后第二天脉诊"
}

Response:
{
  "user_id": "uuid",
  "layer": "instant",
  "prediction_time": "2026-09-29T10:00:00",

  // 实时 Y/X 浓度
  "Y": 45,           // 阳浓度（norm fire×0.55 + norm wood×0.45）
  "X": 42,           // 阴浓度
  "drift": 0.36,     // (Y-X)×SCALE

  // 即时倾向（5 个维度，每个 0-10 分）
  "tendencies": {
    "drink_alcohol": 8,    // 喝酒可能性
    "heat_up": 3,          // 上火可能性
    "cold_down": 2,        // 受寒可能性
    "food_heavy": 7,       // 油腻饮食可能性
    "fatigue": 5           // 疲劳程度
  },

  // 依据（从 V_obs 反推）
  "evidence": [
    { "name": "火形", "value": 52, "hint": "fire 偏高 + alcohol 后 wood 活跃" },
    { "name": "土形", "value": 42, "hint": "earth 偏低 → 湿可能还留着" }
  ],

  "confidence": 0.62,      // 置信度（0-1）
  "engine": "rule_engine"  // "rule_engine" | "llm_enhanced"
}
```

### L2 /predict/short-term（短期预测）

```
POST /api/v1/predict/short-term
Authorization: Bearer <JWT>

Request body:
{
  "v_obs": { ... },
  "horizon_days": 14
}

Response:
{
  "user_id": "uuid",
  "layer": "short_term",
  "horizon_days": 14,

  // 短期趋势（EMA 滞后边界 + 当前状态）
  "trend": "阴偏收敛中",     // "阳偏收敛中" | "阴偏收敛中" | "发散风险"
  "confidence": 0.58,

  // 关键时间点（未来 7-14 天出界概率最高点）
  "risk_windows": [
    { "day_offset": 5, "probability": 0.42, "reason": "下一次 PPG 可能跌破阳界" }
  ],

  // 与 v_innate 对比
  "deviation_from_innate": {
    "fire": -5, "water": +8, ...
  }
}
```

### L3 /predict/lifetime（长期预测）

```
POST /api/v1/predict/lifetime
Authorization: Bearer <JWT>

// L3 只需要 v_innate（先天），不需要 v_obs
// 实际从 Case.v_innate + Case.bazi + Dayun 排盘计算

Response:
{
  "user_id": "uuid",
  "layer": "lifetime",

  // 核心：82 个年龄点的终身曲线（同 year-view 的响应但只输出最小集）
  "critical_ages": [
    { "age": 15, "dayun": "癸丑", "risk": "high",
      "reason": "土壅大运推同方向，首次出界",
      "yangBot": -5.8, "yinTop": +5.2, "drift": -4.8 },
    { "age": 34, "dayun": "壬子", "risk": "high",
      "reason": "水寒极重，阴偏持续",
      "yangBot": -4.5, "yinTop": +4.8, "drift": -3.4 },
    { "age": 65, "dayun": "戊申", "risk": "critical",
      "reason": "当前最不利运",
      "yangBot": -3.2, "yinTop": +5.6, "drift": -5.3 }
  ],

  // 疾病类型预测（SPUM 合规转译，避免"发病"措辞）
  "体质趋势风险窗口": [
    { "age_range": "15-24岁", "tendency": "阴偏加深", "severity": "high" },
    { "age_range": "65-74岁", "tendency": "阴阳均弱", "severity": "critical" }
  ],

  // 调理机会窗口（金形最利时）
  "treatment_windows": [
    { "age": 55, "dayun": "己酉", "reason": "金最利，阳可恢复" }
  ]
}
```

---

## 6. 现有 /trajectories 端点升级迁移计划

当前 v0.2 的 `health_score(0-100)` + 指数收敛 target 要升级为 SPUM 三曲线。

| 字段 | v0.2 现状 | v1.0 目标 | 改动 |
|------|----------|----------|------|
| `target` | health_score 指数收敛 | 删除 | 由 yinTop/yangBot 边界替代 |
| `actual` | health_score 序列 | 保留 + 加 driftData 替代 | 前端兼容 |
| `actual_elements` | 五行分量序列 | 保留 | |
| `events` | 自动推断 + 预设 | 保留 + type 字段对齐 | 补 isMedical 标记 |
| **`driftData`** | ❌ 无 | ✅ (Y-X)×SCALE 净阳量 | **新增核心** |
| **`yinTop`** | ❌ 无 | ✅ +X_boundary×SCALE 阴界 | **新增核心** |
| **`yangBot`** | ❌ 无 | ✅ -Y_boundary×SCALE 阳界 | **新增核心** |
| **`diseaseModes`** | ❌ 无 | ✅ null/acuteDeviation/chronicBoundary | **新增核心** |
| **`elArr`** | ❌ 无 | ✅ 金属弹性系数 | **新增核心** |
| `algorithm` | ❌ 无 | ✅ "spum_computeHealthBounds_v1" | 版本标记 |

前端 Dashboard 中的 DriftChart 会根据 `algorithm` 字段判断走新算法还是旧 fallback。

---

## 7. 数据库表结构补充

当前 events 是自动推断的内存数据。Phase 0 后需要持久化到 DB：

```sql
-- events 表（前端事件编辑器写入，后端读取叠加）
CREATE TABLE trajectory_events (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    age INTEGER NOT NULL,                    -- 事件发生年龄（年视图用）
    day INTEGER,                             -- 事件发生天（月视图用，可选）
    event_type VARCHAR(16) NOT NULL,         -- '手术'|'药物'|'窗口期'|'转大运'|'外力'
    label TEXT,
    damage JSONB,                            -- {"fire": 12, "metal": 10} 伤害量(正数)
    boost JSONB,                             -- {"fire": 6} 增益量(正数)
    duration_days INTEGER DEFAULT 540,       -- 冲击持续时间
    source VARCHAR(16) DEFAULT 'manual',     -- 'manual'|'auto_infer'|'preset_clinical'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 8. 与现有端点的关系图

```
qingnang-APP backend (8767)
├── /api/v1/cases/
│   ├── GET  /mine                    — 用户完整案例（已有）
│   ├── POST /onboarding              — 初始化建档（调引擎 bazi）
│   ├── GET  /trajectories            — ⬆️ 升级：SPUM 三曲线
│   ├── GET  /trajectories/year-view  — 🆕 纯八字推演年视图
│   ├── GET  /radar                   — 🆕 雷达图三层
│   └── GET  /reports                 — 历次推演报告（已有）
│
├── /api/v1/predict/
│   ├── POST /instant                 — 🆕 L1 即时
│   ├── POST /short-term              — 🆕 L2 短期
│   └── POST /lifetime                — 🆕 L3 长期（只接 v_innate）
│
├── /api/v1/ppg/
│   └── POST /upload                  — 采集上传 → 触发引擎 bridge pipeline
│
└── 代理到 qingmeng-engine (8000)
    └── /v1/reasoning/
        ├── /bazi     /ppg    /diagnose   /lifestyle   /treatment
        └── 🆕 /trajectory_algorithm — （可选，纯算法端点，后端直接 import）
```
