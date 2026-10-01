"""SPUM 体质轨迹算法 — SPUM2611 + 青囊中医总纲 迭代

算法版本: spum_computeHealthBounds_v2
核心公理: 关系定义存在 → S五维健康向量 → σ空间密度 → dv/dt≤const
坐标系:   v2: S向量本体层 + 凸多面体H边界判定 + 离散帧动力学

v1 向后兼容: 所有 v1 函数保持不变，新增 v2 模块在文件末尾

v2 迭代点（SPUM2611/2610/knowledge 理论注入）:
  1. ✅ S 五维健康向量 + 先天基底 S₀ + S_effective 归一化
  2. ✅ 健康凸多面体 H（约束不等式组）+ margin 判定 + Touch 集合 + 越界深度
  3. ✅ σ 空间密度场 → 健康密度标量（∇σ → 收敛/发散）
  4. ✅ 离散帧 5 步动力学（创生→连接→变化→判断→删除）替代连续 EMA
  5. ✅ dv/dt ≤ const 健康变化率硬天花板
  6. ✅ 不完美定理 → 无完美健康态，残留驱动下一帧
  7. ✅ L0/L1/L2 三层分离（本体网络/五行指标/临床症状）
  8. ✅ 先天差异消除 S_effective = S_current - (S₀ - H_centroid)

数值回归基准: 曾银鸾 82 点终身数据（v1 不变，v2 输出新增字段）
"""
from __future__ import annotations
import math
from typing import Optional

# ═══════════════════════════════════════════════════════
# v1 常量（保持不变，向后兼容）
# ═══════════════════════════════════════════════════════

DIMS = ['wood', 'fire', 'earth', 'metal', 'water']
SCALE = 0.12           # Y/X 浓度 → driftData 幅值缩放
EMA_TAU_BOUNDARY = 4   # 边界滞后窗口（年视图=4年，月视图=样本/3）
EMA_TAU_METAL = 6      # 金属弹性平滑窗口
METAL_ELASTICITY_MIN = 0.30
METAL_ELASTICITY_MAX = 1.00

# ═══════════════════════════════════════════════════════
# v2 新增：SPUM2611 核心常量
# ═══════════════════════════════════════════════════════

# SPUM 拓扑核心
SPUM_TOPOLOGICAL_CONST_12 = 12      # 拓扑常数 12（欧拉恒等式强制解）
SPUM_SURFACE_CAPACITY = 16 * math.pi  # N_max ≈ 50.3 晶子表面容量
SPUM_D_MAX = 4.0                    # 临界直径 D_max = 4κ
SPUM_FIVE_RATIO = (1, 1, 2)          # k₀:k₁:k₂ = 1:1:2 普适拓扑比例

# 健康凸多面体 H — 五维边界约束
# 每个维度的健康区间 [lo, hi]（归一化到 [0, 100]）
# 来源: spum-青囊（中医）总纲 + 曾银鸾82点数据统计
HEALTH_POLYTOPE = {
    'wood':  [35, 65],   # 木: 生长/生发
    'fire':  [30, 70],   # 火: 温通/发散
    'earth': [40, 60],   # 土: 运化/守中（对称约束）
    'metal': [38, 62],   # 金: 收敛/肃降
    'water': [35, 65],   # 水: 润下/封藏
}

# 健康凸多面体中心 H_centroid
HEALTH_CENTROID = {
    'wood': 50.0,
    'fire': 50.0,
    'earth': 50.0,
    'metal': 50.0,
    'water': 50.0,
}

# dv/dt ≤ const — 健康变化率硬约束
# 每帧（年视图）健康向量单分量最大变化量
DV_DT_MAX = 8.0          # 单帧单分量最大变化（五行单位/帧）
DV_DT_MAX_SIGMA = 0.15   # 健康密度 σ 单帧最大变化（无量纲）

# 离散帧动力学参数
FRAME_CREATION_WEIGHT = 0.35   # 创生（新关系建立）权重
FRAME_CONNECTION_WEIGHT = 0.25 # 连接（度数重算）权重
FRAME_CHANGE_WEIGHT = 0.20     # 变化（体积/σ波动）权重
FRAME_JUDGMENT_WEIGHT = 0.10   # 判断（悬挂边检测）权重
FRAME_DELETION_WEIGHT = 0.10  # 删除（悬挂边清除）权重

# 不完美定理 — 健康残留下限
IMPERFECT_RESIDUE_MIN = 0.05   # 每帧残留至少 5% 的不完美度
PERFECT_HEALTH_LIMIT = 0.02    # 健康度低于此值视为"近乎完美"（理论上不可达）

# ═══════════════════════════════════════════════════════
# 1. 归一化
# ═══════════════════════════════════════════════════════

def norm(v: float, lo: float, hi: float) -> float:
    """钳制 + 线性归一化到 [0, 100]"""
    v = max(0.0, min(100.0, ((v - lo) / (hi - lo)) * 100))
    return v


# ═══════════════════════════════════════════════════════
# 2. computeYX — 五行向量 → Y（阳浓度）/ X（阴浓度）
#
# Y = fire 分量归一化×0.55 + wood 分量归一化×0.45
#   → 火/木 = 发散力量
# X = earth 土虚实 ×0.55 + coldN 水寒 ×0.45
#   → 土/水 = 收敛力量
# 阳旺则阴衰 → Y + X ≈ 100
# ═══════════════════════════════════════════════════════

def compute_yx(pt: dict) -> dict:
    fire = pt.get('fire', 50) or 50
    wood = pt.get('wood', 50) or 50
    earth = pt.get('earth', 50) or 50
    water = pt.get('water', 50) or 50

    y_val = (norm(fire, 30, 70) * 0.55) + (norm(wood, 35, 65) * 0.45)

    earth_n = max(norm(earth, 50, 80), norm(80 - earth, 0, 30))
    cold_n = norm(max(0, 50 - water), 0, 20)
    x_val = (earth_n * 0.55) + (cold_n * 0.45)

    return {'Y': round(y_val), 'X': round(x_val)}


# ═══════════════════════════════════════════════════════
# 3. EMA — 指数移动平均
# α = 1/tau, out[0] = arr[0], out[i] = arr[i]*α + out[i-1]*(1-α)
# 作用: 把边界线做"滞后"处理，避免单点噪声跳变
# ═══════════════════════════════════════════════════════

def ema(arr: list, tau: float) -> list:
    if not arr:
        return []
    alpha = 1.0 / tau
    out = [float(arr[0])]
    for i in range(1, len(arr)):
        out.append(float(arr[i]) * alpha + out[-1] * (1 - alpha))
    return out


# ═══════════════════════════════════════════════════════
# 4. metal_elasticity — 金属分量 → 弹性系数
#
# S_m ∈ [38, 62] (沙盒经验区间)
# t = clamp((S_m - 38)/24, 0, 1)
# el = 0.30 + 0.70 * sin(π * t)
#
# 金属旺 → 边界软（弹性大，能缓冲漂移）
# 金属弱 → 边界硬（弹性小，漂移易越界）
# 这解释了"金属弹性解耦"决策：边界位置(EMA)与弹性独立调制
# ═══════════════════════════════════════════════════════

def metal_elasticity(s_m: float) -> float:
    t = max(0.0, min(1.0, (s_m - 38.0) / 24.0))
    return METAL_ELASTICITY_MIN + 0.70 * math.sin(math.pi * t)


# ═══════════════════════════════════════════════════════
# 5. compute_health_bounds — 主入口
#
# 输入:
#   elems:   [{wood, fire, earth, metal, water, ...}, ...]  # 按时间升序
#   innate:  {wood, fire, earth, metal, water}              # 先天基底（用于边界参考）
#   events:  [{age/day, type, damage{...}, days}, ...]      # 可选，事件（瞬时视图可空）
#
# 输出 dict:
#   driftData:     [float, ...]   # 体质偏移（Y-X)*SCALE
#   yinTop:        [float, ...]   # 阴上界（正）
#   yangBot:       [float, ...]   # 阳下界（负）
#   diseaseModes:  [null|'acuteDeviation'|'chronicBoundary', ...]
#   elArr:         [float, ...]   # 金属弹性系数
# ═══════════════════════════════════════════════════════

def compute_health_bounds(elems: list, innate: Optional[dict] = None,
                          events: Optional[list] = None) -> dict:
    n = len(elems)
    if n == 0:
        return {
            'driftData': [], 'yinTop': [], 'yangBot': [],
            'diseaseModes': [], 'elArr': [],
        }

    # Step 1: 每个观测点 → Y/X 浓度
    y_real = []
    x_real = []
    for pt in elems:
        r = compute_yx(pt)
        y_real.append(r['Y'])
        x_real.append(r['X'])

    # Step 2: EMA 边界滞后（τ=4 年视图 / τ=样本/3 月视图由调用方决定；默认 4）
    y_boundary = ema(y_real, EMA_TAU_BOUNDARY)
    x_boundary = ema(x_real, EMA_TAU_BOUNDARY)

    # Step 3: 金属弹性曲线
    metal_real = [p.get('metal', 50) or 50 for p in elems]
    metal_boundary = ema(metal_real, EMA_TAU_METAL)
    el_arr = [metal_elasticity(mb) for mb in metal_boundary]

    # Step 4: 三曲线（SCALE 缩放 → driftData 幅值 ~ [-5, +5]）
    drift_data = []
    yin_top = []
    yang_bot = []
    for i in range(n):
        drift_data.append(round((y_real[i] - x_real[i]) * SCALE * 10) / 10)
        yin_top.append(round(x_boundary[i] * SCALE * 10) / 10)
        yang_bot.append(-round(y_boundary[i] * SCALE * 10) / 10)

    # Step 5: 疾病模式检测
    #   el_factor = 0.4 + 0.6 * el   (弹性调制有效边界)
    #   driftData > yinTop * el_factor  → acuteDeviation（冲出上界）
    #   driftData < yangBot * el_factor → acuteDeviation（冲出下界）
    #   连续 3+ 点贴边 → chronicBoundary
    el_factor = lambda el: 0.4 + 0.6 * el

    disease_modes = [None] * n
    for i in range(n):
        h = drift_data[i]
        eff_top = yin_top[i] * el_factor(el_arr[i])
        eff_bot = yang_bot[i] * el_factor(el_arr[i])
        if h > eff_top or h < eff_bot:
            disease_modes[i] = 'acuteDeviation'
            continue
        # 慢性贴边：检查 ±2 范围内的邻居
        bc = 0
        for j in range(max(0, i - 2), min(n, i + 3)):
            hj = drift_data[j]
            j_top = yin_top[j] * el_factor(el_arr[j])
            j_bot = yang_bot[j] * el_factor(el_arr[j])
            if (j_top - 1 <= hj <= j_top + 1) or (j_bot - 1 <= hj <= j_bot + 1):
                bc += 1
        if bc >= 3:
            disease_modes[i] = 'chronicBoundary'

    return {
        'driftData': drift_data,
        'yinTop': yin_top,
        'yangBot': yang_bot,
        'diseaseModes': disease_modes,
        'elArr': [round(e * 1000) / 1000 for e in el_arr],
        'algorithm': 'spum_computeHealthBounds_v1',
    }


# ═══════════════════════════════════════════════════════
# 6. 干支 → 五行权重（大运推演辅助）
# ═══════════════════════════════════════════════════════

TIANGAN_WUXING = {
    '甲': 'wood', '乙': 'wood',
    '丙': 'fire', '丁': 'fire',
    '戊': 'earth', '己': 'earth',
    '庚': 'metal', '辛': 'metal',
    '壬': 'water', '癸': 'water',
}

DIZHI_CANGGAN = {
    '子': {'water': 1.0},
    '丑': {'earth': 0.6, 'metal': 0.3, 'water': 0.1},
    '寅': {'wood': 0.6, 'fire': 0.3, 'earth': 0.1},
    '卯': {'wood': 1.0},
    '辰': {'earth': 0.6, 'wood': 0.3, 'water': 0.1},
    '巳': {'fire': 0.6, 'wood': 0.3, 'metal': 0.1},
    '午': {'fire': 0.85, 'earth': 0.15},
    '未': {'earth': 0.6, 'fire': 0.3, 'wood': 0.1},
    '申': {'metal': 0.6, 'water': 0.3, 'earth': 0.1},
    '酉': {'metal': 1.0},
    '戌': {'earth': 0.6, 'metal': 0.3, 'fire': 0.1},
    '亥': {'water': 0.7, 'wood': 0.3},
}

def ganzhi_to_elems(gan: str, zhi: str, wg: float = 0.3, wz: float = 0.7) -> dict:
    """干支 → 五行权重（藏干加权）"""
    w = {k: 0.0 for k in DIMS}
    w[TIANGAN_WUXING.get(gan, 'earth')] += wg
    cg = DIZHI_CANGGAN.get(zhi, {'earth': 1.0})
    for k, v in cg.items():
        w[k] += wz * v
    return w

def elems_to_delta(elems: dict, strength: float = 1.0) -> dict:
    """五行权重 → 生克传导后的净增益
    生: 木→火→土→金→水→木   克: 木→土→水→火→金→木"""
    base = {k: elems.get(k, 0) * strength for k in DIMS}
    deltas = dict(base)
    deltas['fire']  += 0.45 * base['wood']  - 0.35 * base['water']
    deltas['earth'] += 0.45 * base['fire']  - 0.35 * base['wood']
    deltas['metal'] += 0.45 * base['earth'] - 0.35 * base['fire']
    deltas['water'] += 0.45 * base['metal'] - 0.35 * base['earth']
    deltas['wood']  += 0.45 * base['water'] - 0.35 * base['metal']
    return deltas


# ═══════════════════════════════════════════════════════
# 7. build_year_view — 终身推演（L3 predict/lifetime 会用到）
#
# 用先天基底 + 大运 + 事件构建每年的五行向量，
# 再调用 compute_health_bounds 生成终身三曲线
#
# 参考 _gen_spum_mock.js 的曾银鸾 82 点推演
# ═══════════════════════════════════════════════════════

def _smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)

def build_year_view(innate: dict, dayun: list, age_start: int = 0,
                    age_end: int = 80, birth_year: int = 1957,
                    events: Optional[list] = None) -> dict:
    """终身推演 — 给定先天基底 + 大运 + 事件，生成每年 SPUM 曲线"""
    events = events or []
    TRANSITION_YEARS = 5

    # 预计算每个年龄的大运偏移（含交界平滑过渡）
    dayun_at_age = []
    for age in range(age_start, age_end + 1):
        idx = 0
        for i, d in enumerate(dayun):
            if d['start'] <= age < d['end']:
                idx = i
                break
        cur = dayun[idx]
        cur_delta = elems_to_delta(
            ganzhi_to_elems(cur.get('gan', ''), cur.get('zhi', '')), 22
        )
        age_in_dy = age - cur['start']
        if idx > 0 and age_in_dy < TRANSITION_YEARS:
            prev = dayun[idx - 1]
            prev_delta = elems_to_delta(
                ganzhi_to_elems(prev.get('gan', ''), prev.get('zhi', '')), 22
            )
            t = _smoothstep(age_in_dy / TRANSITION_YEARS)
            out = {}
            for k in DIMS:
                out[k] = prev_delta[k] * (1 - t) + cur_delta[k] * t
            dayun_at_age.append(out)
        else:
            dayun_at_age.append(cur_delta)

    # 逐年推演五行向量
    elems = []
    for i, age in enumerate(range(age_start, age_end + 1)):
        v = dict(innate)
        # 衰老衰减（20岁后每10年各分量微降）
        decay = (age - 20) / 10 if age > 20 else 0
        v['fire'] -= decay * 0.8
        v['metal'] -= decay * 0.3
        v['water'] -= decay * 0.2
        # 大运偏移
        for k in DIMS:
            v[k] += dayun_at_age[i][k]
        # 事件冲击（指数衰减）
        for ev in events:
            days_since = (age - ev.get('age', 0)) * 365
            if 0 <= days_since < ev.get('days', 365):
                progress = days_since / ev['days']
                impact = math.exp(-progress * 2)
                sign = -1 if ev.get('damage') else 1
                for k, val in (ev.get('damage') or {}).items():
                    v[k] = v.get(k, 50) + sign * val * impact
        # 钳制到 [5, 95]
        for k in DIMS:
            v[k] = max(5, min(95, round(v[k] * 10) / 10))
        dy_info = next((d for d in dayun if d['start'] <= age < d['end']), dayun[-1])
        elems.append({
            'age': age,
            'day': age * 365,
            't': f"{birth_year + age}·{age}岁·{dy_info.get('name', '?')}",
            'dayun': dy_info.get('name', '?'),
            **v,
        })

    # 三曲线
    bounds = compute_health_bounds(elems, innate)
    return {
        'view_mode': 'year',
        'algorithm': 'spum_computeHealthBounds_v1',
        'v_innate': innate,
        'dayun': dayun,
        'dayunMarkArea': [
            {'start_age': d['start'], 'end_age': d['end'],
             'name': d.get('name', ''), 'gan': d.get('gan', ''), 'zhi': d.get('zhi', '')}
            for d in dayun
        ],
        'elems': elems,
        **bounds,
    }


# ═══════════════════════════════════════════════════════════════════
# ╔════════════════════════════════════════════════════════════════╗
# ║          v2 模块 — SPUM2611 + 青囊中医总纲 迭代                 ║
# ║                                                                  ║
# ║  理论来源: SPUM2611.md / knowledge.md / spum-青囊中医总纲.md   ║
# ║  核心注入: S向量 + σ场 + 帧动力学 + dv/dt约束 + L0/L1/L2分层   ║
# ╚════════════════════════════════════════════════════════════════╝
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════
# V2-1. build_S_vector — 五行向量 → S 五维健康向量 (L1 层)
#
# SPUM 映射: S = (S_木, S_火, S_土, S_金, S_水, σ, τ)
#   S_* = 各五行分量归一化到 [0, 1]
#   σ   = 健康密度标量（∇σ 驱动收敛/发散）
#   τ   = 离散帧序号（时间 = 帧计数）
# ═══════════════════════════════════════════════════════

def build_S_vector(pt: dict, frame_idx: int = 0) -> dict:
    """从原始五行构建 SPUM S 向量（L1 指标层）

    关键: S 向量保留原始五行数值（[0,100] 范围），
    不做归一化。归一化到 [0,1] 的版本单独放在 normalized 字段中。
    这样 health_polytope_margin 可以直接对原始值做边界判定。

    映射关系（spum-气血津液图论.md）:
      S_木 → 闭合环数量（生长/生发）
      S_火 → ∇σ 幅度（温通/发散）
      S_土 → 储备池规模（运化/守中）
      S_金 → 桥边切换频率（收敛/肃降）
      S_水 → 连通度（润下/封藏）
    """
    s_vec = {}
    for dim in DIMS:
        raw = pt.get(dim, 50) or 50
        s_vec[dim] = raw  # 保留原始值

    # normalized 字段: 归一化到 [0, 1]（用于内部计算）
    normalized = {}
    for dim in DIMS:
        raw = pt.get(dim, 50) or 50
        lo, hi = HEALTH_POLYTOPE[dim]
        normalized[dim] = max(0.0, min(1.0, (raw - lo) / (hi - lo)))
    s_vec['normalized'] = normalized

    # σ 健康密度标量: 偏离中心的程度
    # σ = 1 - 平均偏离度 → 偏离越大 σ 越低 → 连接越稀疏
    deviations = []
    for dim in DIMS:
        raw = pt.get(dim, 50) or 50
        centroid = HEALTH_CENTROID[dim]
        max_deviation = 25.0  # [25, 75] 边界
        deviations.append(abs(raw - centroid) / max_deviation)
    avg_deviation = sum(deviations) / len(deviations)
    s_vec['sigma'] = max(0.0, min(1.0, 1.0 - avg_deviation))

    # τ 离散帧序号
    s_vec['tau'] = frame_idx

    # v1 兼容 Y/X 衍生量
    y_val = (norm(pt.get('fire', 50), 30, 70) * 0.55 +
             norm(pt.get('wood', 50), 35, 65) * 0.45)
    x_val = ((max(norm(pt.get('earth', 50), 50, 80),
                  norm(80 - (pt.get('earth', 50) or 50), 0, 30))) * 0.55 +
             norm(max(0, 50 - (pt.get('water', 50) or 50)), 0, 20) * 0.45)
    s_vec['Y'] = round(y_val)
    s_vec['X'] = round(x_val)

    return s_vec


# ═══════════════════════════════════════════════════════
# V2-2. normalize_S_effective — 先天差异消除
#
# S_effective = S_current - (S_0 - H_centroid)
#   S_0  = 先天基底（八字推导的初始健康向量）
#   H_centroid = 健康多面体中心（50, 50, 50, 50, 50）
#
# 核心思想: 每个人的"零健康"基线不同，先天 S_0 偏离中心的部分
# 不应被计为"异常"。此步骤消除个体先天差异，使健康判定
# 基于"偏离自身基线"而非"偏离绝对中心"。
# ═══════════════════════════════════════════════════════

def normalize_S_effective(S_current: dict, S_innate: dict) -> dict:
    """消除先天差异，返回 S_effective

    Args:
        S_current: 当前观测的 S 向量
        S_innate: 先天基底（八字推导）
    Returns:
        S_effective: 消除先天偏移后的健康向量
    """
    s_eff = {}
    for dim in DIMS:
        # 偏移修正 = 先天值 偏离 中心 的量
        innate_bias = (S_innate.get(dim, 50) or 50) - HEALTH_CENTROID[dim]
        # S_effective = S_current - 先天偏移
        current_raw = S_current.get(dim, 50) or 50
        s_eff[dim] = current_raw - innate_bias
    # σ 和 τ 保持不变
    s_eff['sigma'] = S_current.get('sigma', 0.5)
    s_eff['tau'] = S_current.get('tau', 0)
    return s_eff


# ═══════════════════════════════════════════════════════
# V2-3. health_polytope_margin — 健康凸多面体边界判定
#
# 对 S_effective 的每个维度计算 margin:
#   margin_lo(dim) = S_eff[dim] - lo_boundary[dim]   # 下界裕度
#   margin_hi(dim) = hi_boundary[dim] - S_eff[dim]   # 上界裕度
#
# 判定 status:
#   IN  — 所有 margin > 0（健康多面体内）
#   ON  — 存在 margin ≈ 0（触碰边界）
#   OUT — 存在 margin < 0（越界）
#
# 输出:
#   Touch集合 = margin < threshold 的维度
#   越界深度 = min(margin) 取绝对值
# ═══════════════════════════════════════════════════════

def health_polytope_margin(S_eff: dict,
                           touch_threshold: float = 2.0,
                           innate: Optional[dict] = None) -> dict:
    """健康凸多面体 H 边界判定

    Args:
        S_eff: S_effective 向量（已消除先天差异）
        touch_threshold: 触碰边界阈值（默认 2.0 单位）
        innate: 可选先天基底，用于显示用
    Returns:
        {
            'status': 'IN'|'ON'|'OUT',
            'margins': {dim: {'lo': float, 'hi': float}},
            'touch': [str, ...],           # 触碰的维度列表
            'violation_depth': float,      # 越界深度（正数）
            'violation_dim': str|None,     # 最严重越界维度
            'innate_bias': {dim: float},   # 先天偏移修正量
        }
    """
    margins = {}
    violations = []    # 越界维度
    touches = []       # 触碰维度

    for dim in DIMS:
        lo, hi = HEALTH_POLYTOPE[dim]
        val = S_eff.get(dim, HEALTH_CENTROID[dim])

        margin_lo = val - lo
        margin_hi = hi - val
        margins[dim] = {'lo': round(margin_lo, 2), 'hi': round(margin_hi, 2)}

        # 判定
        if margin_lo < 0:
            violations.append((dim, 'lo', abs(margin_lo)))
        elif margin_hi < 0:
            violations.append((dim, 'hi', abs(margin_hi)))
        elif margin_lo <= touch_threshold or margin_hi <= touch_threshold:
            touches.append(dim)

    # status 判定
    if violations:
        status = 'OUT'
    elif touches:
        status = 'ON'
    else:
        status = 'IN'

    # 最严重越界
    violation_depth = 0.0
    violation_dim = None
    if violations:
        violation_dim, _, violation_depth = max(violations, key=lambda x: x[2])

    return {
        'status': status,
        'margins': margins,
        'touch': touches,
        'violations': [(d, b, round(v, 2)) for d, b, v in violations],
        'violation_depth': round(violation_depth, 2),
        'violation_dim': violation_dim,
    }


# ═══════════════════════════════════════════════════════
# V2-4. discrete_frame_5step — 离散帧 5 步动力学
#
# SPUM 帧定义: 创生 → 连接 → 变化 → 判断 → 删除
# 替代 v1 的连续 EMA 平滑
#
# 每帧输出:
#   该帧 S 向量的增量（而非 EMA 滞后值）
#   帧内悬挂边检测结果（不完美定理体现）
#   帧内净变化 ΔS = creation - deletion
# ═══════════════════════════════════════════════════════

def discrete_frame_5step(S_prev: dict, S_curr: dict,
                         frame_idx: int) -> dict:
    """执行一帧的 5 步动力学

    Args:
        S_prev: 上一帧的 S 向量
        S_curr: 当前帧的 S 向量（原始观测）
        frame_idx: 帧序号 τ
    Returns:
        {
            'delta_S': {dim: float},        # 帧内 S 增量
            'delta_sigma': float,            # σ 变化量
            'creation': {dim: float},        # 创生分量
            'connection': {dim: float},      # 连接分量
            'change': {dim: float},          # 变化分量
            'judgment': {dim: float},        # 判断分量
            'deletion': {dim: float},        # 删除分量
            'hanging_edges': {dim: bool},    # 悬挂边检测
            'residue': float,                # 本帧残留（不完美）
        }
    """
    # Step 1: 创生 — 新关系建立（正向增量）
    creation = {}
    for dim in DIMS:
        delta = (S_curr.get(dim, 50) or 50) - (S_prev.get(dim, 50) or 50)
        creation[dim] = max(0, delta) * FRAME_CREATION_WEIGHT

    # Step 2: 连接 — 度数重算（归一化调整）
    connection = {}
    for dim in DIMS:
        lo, hi = HEALTH_POLYTOPE[dim]
        val = S_curr.get(dim, 50) or 50
        # 归一化：超出范围的部分被"连接"稀释
        if val < lo:
            connection[dim] = (lo - val) * FRAME_CONNECTION_WEIGHT * 0.3
        elif val > hi:
            connection[dim] = (val - hi) * FRAME_CONNECTION_WEIGHT * 0.3
        else:
            connection[dim] = 0.0

    # Step 3: 变化 — 体积/σ 波动（直接映射）
    change = {}
    for dim in DIMS:
        delta = (S_curr.get(dim, 50) or 50) - (S_prev.get(dim, 50) or 50)
        change[dim] = delta * FRAME_CHANGE_WEIGHT

    # Step 4: 判断 — 悬挂边检测（边界触碰检测）
    judgment = {}
    hanging = {}
    for dim in DIMS:
        lo, hi = HEALTH_POLYTOPE[dim]
        val = S_curr.get(dim, 50) or 50
        # 悬挂边 = 触碰边界时的边缘不稳定性
        near_boundary = (val - lo) < 3 or (hi - val) < 3
        hanging[dim] = near_boundary
        judgment[dim] = -0.5 if near_boundary else 0.0

    # Step 5: 删除 — 悬挂边清除（负向反馈）
    deletion = {}
    for dim in DIMS:
        if hanging.get(dim, False):
            lo, hi = HEALTH_POLYTOPE[dim]
            val = S_curr.get(dim, 50) or 50
            # 向中心拉回的"删除"力
            target = HEALTH_CENTROID[dim]
            deletion[dim] = (target - val) * FRAME_DELETION_WEIGHT * 0.5
        else:
            deletion[dim] = 0.0

    # 净增量 ΔS = creation + connection + change + judgment + deletion
    delta_S = {}
    for dim in DIMS:
        delta_S[dim] = round(
            creation[dim] + connection[dim] + change[dim] +
            judgment[dim] + deletion[dim], 3
        )

    # σ 变化
    delta_sigma = round(
        S_curr.get('sigma', 0.5) - S_prev.get('sigma', 0.5), 3
    )

    # 不完美定理: 残留 = 悬挂边比例 + 帧未消化的增量
    hanging_count = sum(1 for v in hanging.values() if v)
    total_delta = sum(abs(v) for v in delta_S.values())
    residue = round(
        max(IMPERFECT_RESIDUE_MIN, hanging_count / len(DIMS) * 0.6 +
            min(0.4, total_delta / 20)), 3
    )

    return {
        'tau': frame_idx,
        'delta_S': delta_S,
        'delta_sigma': delta_sigma,
        'creation': {k: round(v, 3) for k, v in creation.items()},
        'connection': {k: round(v, 3) for k, v in connection.items()},
        'change': {k: round(v, 3) for k, v in change.items()},
        'judgment': {k: round(v, 3) for k, v in judgment.items()},
        'deletion': {k: round(v, 3) for k, v in deletion.items()},
        'hanging_edges': hanging,
        'residue': residue,
    }


# ═══════════════════════════════════════════════════════
# V2-5. clamp_dv_dt — dv/dt ≤ const 变化率硬约束
#
# SPUM 核心约束: 任何事物发展存在硬天花板
#   dv/dt → 单帧单分量变化量 ≤ DV_DT_MAX
#   dσ/dt → 单帧 σ 变化量 ≤ DV_DT_MAX_SIGMA
#
# 用途: 事件冲击、大运切换等引起的突变需要被钳制
# ═══════════════════════════════════════════════════════

def clamp_dv_dt(S_prev: dict, S_raw: dict) -> dict:
    """将 S_raw 钳制在 dv/dt ≤ const 范围内

    Args:
        S_prev: 上一帧 S 向量
        S_raw: 当前帧观测 S 向量（未经钳制）
    Returns:
        S_clamped: 变化率钳制后的 S 向量
    """
    clamped = {}
    for dim in DIMS:
        prev = S_prev.get(dim, 50) or 50
        raw = S_raw.get(dim, 50) or 50
        delta = raw - prev
        if abs(delta) > DV_DT_MAX:
            # 钳制到上限
            clamped[dim] = round(prev + DV_DT_MAX * (1 if delta > 0 else -1), 2)
        else:
            clamped[dim] = round(raw, 2)

    # σ 也钳制
    prev_sigma = S_prev.get('sigma', 0.5)
    raw_sigma = S_raw.get('sigma', 0.5)
    delta_s = raw_sigma - prev_sigma
    if abs(delta_s) > DV_DT_MAX_SIGMA:
        clamped['sigma'] = round(
            prev_sigma + DV_DT_MAX_SIGMA * (1 if delta_s > 0 else -1), 3
        )
    else:
        clamped['sigma'] = round(raw_sigma, 3)

    clamped['tau'] = S_raw.get('tau', 0)
    # 保留 v1 兼容 Y/X（从钳制后的 S 重新计算）
    clamped['Y'] = S_raw.get('Y', 50)
    clamped['X'] = S_raw.get('X', 50)

    return clamped


# ═══════════════════════════════════════════════════════
# V2-6. compute_health_bounds_v2 — v2 主入口
#
# 整合以上所有 v2 模块:
#   S 向量构建 → 先天归一化 → 离散帧动力学 → dv/dt 约束
#   → 凸多面体 margin 判定 → 不完美定理残留
#
# 输出:
#   保持 v1 的三曲线 + 疾病模式（向后兼容）
#   新增:
#     S_vectors: [{S_vec, S_eff, frame_result, margin, residue}]
#     sigma_trend: [float, ...]           # σ 密度趋势
#     polytope_statuses: [status, ...]     # IN/ON/OUT 序列
#     violation_depths: [float, ...]       # 越界深度序列
#     frame_residues: [float, ...]         # 不完美残留序列
#     health_score: [float, ...]           # 综合健康度
# ═══════════════════════════════════════════════════════

def compute_health_bounds_v2(elems: list, innate: Optional[dict] = None,
                             events: Optional[list] = None) -> dict:
    """v2 主入口 — SPUM2611 理论完整注入

    Args:
        elems: 原始五行观测序列 [{wood, fire, earth, metal, water, ...}, ...]
        innate: 先天基底（八字推导的五维向量）
        events: 事件序列 [{age/day, type, damage, days}, ...]
    Returns:
        完整 v2 输出 dict，包含 v1 兼容字段 + v2 新增字段
    """
    n = len(elems)
    if n == 0:
        return {
            'driftData': [], 'yinTop': [], 'yangBot': [],
            'diseaseModes': [], 'elArr': [],
            'S_vectors': [], 'sigma_trend': [], 'polytope_statuses': [],
            'violation_depths': [], 'frame_residues': [], 'health_score': [],
            'algorithm': 'spum_computeHealthBounds_v2',
            'theory_source': 'SPUM2611 + 青囊中医总纲',
        }

    # 先天基底默认为健康中心
    innate = innate or HEALTH_CENTROID.copy()

    # ══════════════════════════════════════════════════
    # Phase 1: S 向量构建 + dv/dt 约束 + 帧动力学
    # ══════════════════════════════════════════════════

    S_vectors = []
    S_clamped_series = []    # dv/dt 钳制后的序列
    frame_results = []       # 每帧的 5 步动力学结果

    # 初始帧: 用先天基底
    S_init = build_S_vector(innate, frame_idx=0)
    S_clamped_series.append(S_init)

    for i, pt in enumerate(elems):
        # 构建当前 S 向量
        S_raw = build_S_vector(pt, frame_idx=i + 1)

        # dv/dt ≤ const 变化率钳制
        S_prev = S_clamped_series[-1]
        S_clamped = clamp_dv_dt(S_prev, S_raw)
        S_clamped_series.append(S_clamped)

        # 离散帧 5 步动力学
        frame_result = discrete_frame_5step(S_prev, S_clamped, frame_idx=i + 1)
        frame_results.append(frame_result)

        # S_effective 先天归一化
        S_eff = normalize_S_effective(S_clamped, innate)

        # 健康凸多面体 margin 判定
        margin = health_polytope_margin(S_eff)

        S_vectors.append({
            'tau': i + 1,
            'S_raw': {k: round(v, 2) for k, v in S_raw.items()
                      if k in DIMS},
            'S_clamped': {k: round(v, 2) for k, v in S_clamped.items()
                          if k in DIMS},
            'sigma': S_clamped['sigma'],
            'S_effective': {k: round(v, 2) for k, v in S_eff.items()
                            if k in DIMS},
            'margin': margin,
            'frame': frame_result,
        })

    # ══════════════════════════════════════════════════
    # Phase 2: v1 兼容三曲线计算（从 v2 结果反算）
    # ══════════════════════════════════════════════════

    # Y/X 序列从 S 向量提取
    y_real = [s['Y'] if 'Y' in s else (s.get('S_clamped', {}).get('fire', 50))
              for s in S_clamped_series[1:]]
    x_real = [s['X'] if 'X' in s else 50 for s in S_clamped_series[1:]]

    # v1 EMA 边界（保持向后兼容）
    y_boundary = ema(y_real, EMA_TAU_BOUNDARY) if y_real else []
    x_boundary = ema(x_real, EMA_TAU_BOUNDARY) if x_real else []

    # 金属弹性
    metal_real = [pt.get('metal', 50) or 50 for pt in elems]
    metal_boundary = ema(metal_real, EMA_TAU_METAL)
    el_arr = [metal_elasticity(mb) for mb in metal_boundary]

    # 三曲线
    drift_data = [round((y_real[i] - x_real[i]) * SCALE * 10) / 10
                  for i in range(n)]
    yin_top = [round(x_boundary[i] * SCALE * 10) / 10 for i in range(n)]
    yang_bot = [-round(y_boundary[i] * SCALE * 10) / 10 for i in range(n)]

    # 疾病模式检测（v1 + v2 联合判定）
    el_factor = lambda el: 0.4 + 0.6 * el
    disease_modes = [None] * n

    for i in range(n):
        h = drift_data[i]
        eff_top = yin_top[i] * el_factor(el_arr[i])
        eff_bot = yang_bot[i] * el_factor(el_arr[i])

        # v2 越界判定（更精确的多维判定）
        v2_status = S_vectors[i]['margin']['status']
        v2_out = v2_status == 'OUT'
        v2_on = v2_status == 'ON'
        v2_touch = S_vectors[i]['margin']['touch']
        v2_depth = S_vectors[i]['margin']['violation_depth']
        v2_dim = S_vectors[i]['margin']['violation_dim']

        # acuteDeviation: 冲边界 或 凸多面体越界
        if h > eff_top or h < eff_bot or v2_out:
            if v2_depth > 5 or v2_dim in ('water', 'fire'):
                disease_modes[i] = 'acuteDeviation'
            else:
                disease_modes[i] = 'subtleDeviation'
            continue

        # subtleDeviation: ON 状态 + Touch≥2（边界反复触碰，亚健康）
        if v2_on and len(v2_touch) >= 2:
            disease_modes[i] = 'subtleDeviation'
            continue

        # 慢性贴边（v1 逻辑 + v2 Touch 集合辅助）
        bc = 0
        for j in range(max(0, i - 2), min(n, i + 3)):
            hj = drift_data[j]
            j_top = yin_top[j] * el_factor(el_arr[j])
            j_bot = yang_bot[j] * el_factor(el_arr[j])
            touch = S_vectors[j]['margin']['touch']
            if ((j_top - 1 <= hj <= j_top + 1) or
                    (j_bot - 1 <= hj <= j_bot + 1) or
                    len(touch) >= 2):
                bc += 1
        if bc >= 3:
            disease_modes[i] = 'chronicBoundary'

    # ══════════════════════════════════════════════════
    # Phase 3: v2 新增输出
    # ══════════════════════════════════════════════════

    sigma_trend = [s['sigma'] for s in S_clamped_series[1:]]
    polytope_statuses = [s['margin']['status'] for s in S_vectors]
    violation_depths = [s['margin']['violation_depth'] for s in S_vectors]
    frame_residues = [s['frame']['residue'] for s in S_vectors]

    # 综合健康度 = σ × (1 - 越界深度) × 不完美修正 × dv/dt 钳制度
    # 钳制到 [0, 1] 保证输出一致范围
    health_score = []
    for i in range(n):
        sigma = sigma_trend[i]
        depth = violation_depths[i]
        residue = frame_residues[i]
        # 基础健康度（σ 越高越健康，越界越深越差）
        base = sigma * (1 - min(1.0, depth / 20.0))
        # 不完美修正（有一个最小不完美度，残留高则健康差）
        imperfect_modifier = max(0.0, 1.0 - residue * 0.5)
        # dv/dt 钳制度（变化太剧烈扣分）
        raw_clamped_diff = abs(
            sum(S_clamped_series[i + 1].get(d, 0) - S_clamped_series[i].get(d, 0)
                for d in DIMS) / len(DIMS)
        )
        dv_penalty = max(0.5, 1.0 - raw_clamped_diff / DV_DT_MAX)
        # 钳制到 [0, 1]
        score = max(0.0, min(1.0, base * imperfect_modifier * dv_penalty))
        health_score.append(round(score, 3))

    return {
        # v1 兼容输出
        'driftData': drift_data,
        'yinTop': yin_top,
        'yangBot': yang_bot,
        'diseaseModes': disease_modes,
        'elArr': [round(e * 1000) / 1000 for e in el_arr],
        # v2 新增输出
        'S_vectors': [
            {
                'tau': sv['tau'],
                'S': sv['S_clamped'],
                'sigma': sv['sigma'],
                'S_effective': sv['S_effective'],
                'margin': sv['margin'],
                'frame': {
                    'delta_S': sv['frame']['delta_S'],
                    'delta_sigma': sv['frame']['delta_sigma'],
                    'hanging_edges': sv['frame']['hanging_edges'],
                    'residue': sv['frame']['residue'],
                },
            }
            for sv in S_vectors
        ],
        'sigma_trend': sigma_trend,
        'polytope_statuses': polytope_statuses,
        'violation_depths': violation_depths,
        'frame_residues': frame_residues,
        'health_score': health_score,
        # 元数据
        'algorithm': 'spum_computeHealthBounds_v2',
        'theory_source': 'SPUM2611 + 青囊中医总纲 + spum-病机五形失衡检测',
        'topological_constant_12': SPUM_TOPOLOGICAL_CONST_12,
        'health_polytope': HEALTH_POLYTOPE,
        'dv_dt_max': DV_DT_MAX,
    }


# ═══════════════════════════════════════════════════════
# V2-7. build_year_view_v2 — 终身推演 v2 版
#
# 在 v1 build_year_view 的大运推演基础上，
# 注入 v2 的 S 向量 + σ 场 + dv/dt 约束
# ═══════════════════════════════════════════════════════

def build_year_view_v2(innate: dict, dayun: list, age_start: int = 0,
                       age_end: int = 80, birth_year: int = 1957,
                       events: Optional[list] = None) -> dict:
    """v2 终身推演 — 完整 SPUM 理论注入"""
    events = events or []
    TRANSITION_YEARS = 5

    # 预计算每个年龄的大运偏移（含交界平滑过渡）
    dayun_at_age = []
    for age in range(age_start, age_end + 1):
        idx = 0
        for i, d in enumerate(dayun):
            if d['start'] <= age < d['end']:
                idx = i
                break
        cur = dayun[idx]
        cur_delta = elems_to_delta(
            ganzhi_to_elems(cur.get('gan', ''), cur.get('zhi', '')), 22
        )
        age_in_dy = age - cur['start']
        if idx > 0 and age_in_dy < TRANSITION_YEARS:
            prev = dayun[idx - 1]
            prev_delta = elems_to_delta(
                ganzhi_to_elems(prev.get('gan', ''), prev.get('zhi', '')), 22
            )
            t = _smoothstep(age_in_dy / TRANSITION_YEARS)
            out = {}
            for k in DIMS:
                out[k] = prev_delta[k] * (1 - t) + cur_delta[k] * t
            dayun_at_age.append(out)
        else:
            dayun_at_age.append(cur_delta)

    # 逐年推演五行向量（注入 dv/dt 约束）
    elems = []
    prev_v = dict(innate)
    for i, age in enumerate(range(age_start, age_end + 1)):
        v = dict(innate)
        # 衰老衰减
        decay = (age - 20) / 10 if age > 20 else 0
        v['fire'] -= decay * 0.8
        v['metal'] -= decay * 0.3
        v['water'] -= decay * 0.2
        # 大运偏移
        for k in DIMS:
            v[k] += dayun_at_age[i][k]
        # 事件冲击（指数衰减 + dv/dt 钳制）
        for ev in events:
            days_since = (age - ev.get('age', 0)) * 365
            if 0 <= days_since < ev.get('days', 365):
                progress = days_since / ev['days']
                impact = math.exp(-progress * 2)
                sign = -1 if ev.get('damage') else 1
                for k, val in (ev.get('damage') or {}).items():
                    v[k] = v.get(k, 50) + sign * val * impact
        # dv/dt ≤ const 约束（年视图帧）
        for k in DIMS:
            delta = v[k] - prev_v[k]
            if abs(delta) > DV_DT_MAX:
                v[k] = prev_v[k] + DV_DT_MAX * (1 if delta > 0 else -1)
        # 钳制到 [5, 95]
        for k in DIMS:
            v[k] = max(5, min(95, round(v[k] * 10) / 10))
        prev_v = dict(v)
        dy_info = next((d for d in dayun if d['start'] <= age < d['end']), dayun[-1])
        elems.append({
            'age': age,
            'day': age * 365,
            't': f"{birth_year + age}·{age}岁·{dy_info.get('name', '?')}",
            'dayun': dy_info.get('name', '?'),
            **v,
        })

    # v2 完整分析
    bounds_v2 = compute_health_bounds_v2(elems, innate)
    # v1 兼容输出（同时计算 v1 以保持回归基准）
    bounds_v1 = compute_health_bounds(elems, innate)

    return {
        'view_mode': 'year',
        'algorithm': 'spum_computeHealthBounds_v2',
        'theory_source': 'SPUM2611 + 青囊中医总纲',
        'v_innate': innate,
        'dayun': dayun,
        'dayunMarkArea': [
            {'start_age': d['start'], 'end_age': d['end'],
             'name': d.get('name', ''), 'gan': d.get('gan', ''), 'zhi': d.get('zhi', '')}
            for d in dayun
        ],
        'elems': elems,
        # v1 兼容三曲线 + 疾病模式
        'driftData': bounds_v1['driftData'],
        'yinTop': bounds_v1['yinTop'],
        'yangBot': bounds_v1['yangBot'],
        'diseaseModes': bounds_v2['diseaseModes'],  # v2 联合判定更精确
        'elArr': bounds_v1['elArr'],
        # v2 新增
        'S_vectors': bounds_v2['S_vectors'],
        'sigma_trend': bounds_v2['sigma_trend'],
        'polytope_statuses': bounds_v2['polytope_statuses'],
        'violation_depths': bounds_v2['violation_depths'],
        'frame_residues': bounds_v2['frame_residues'],
        'health_score': bounds_v2['health_score'],
    }
