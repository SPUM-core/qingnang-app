"""_basic - SPUM v1 基础算法：量纲检测 / norm / compute_yx / EMA 平滑 / 健康区间 v1"""
from __future__ import annotations
import math
from typing import Optional

from ._constants import (
    DIMS, SCALE, EMA_TAU_BOUNDARY, EMA_TAU_METAL,
    METAL_ELASTICITY_MIN, METAL_ELASTICITY_MAX,
    HEALTH_POLYTOPE, HEALTH_CENTROID,
)

# ════════════════════════════════════════════════════════════════
# 向量量纲检测工具 — P0-1 修复
# 同一个 v_current / v_baseline 可能属于两种口径：
#   - 'prob':  v_innate 概率分布，center=20，Σ=100（cases.py 建档写入的先天基底）
#   - 'scalar': 健康标量空间，center=50（trajectory_algorithm.normalize_S_effective 输出）
# 消费端（assistant.py / knowledge.py / cases.py）之前不知道自己拿的是哪种口径，
# 把 center=20 的数据套 center=50 的 45/65 阈值 → earth:43（土壅！）被判为偏弱
# ════════════════════════════════════════════════════════════════
def detect_vector_scale(v: dict) -> str:
    """检测向量 v 的量纲口径：'prob'(center=20) 或 'scalar'(center=50)"""
    vals = [v[k] for k in DIMS if isinstance(v.get(k), (int, float))]
    if len(vals) < 3:
        return 'scalar'  # 默认健康标量口径（保守：缺少数据时不做 prob 判定）
    avg = sum(vals) / len(vals)
    # 概率分布均值在 20 附近，健康标量均值在 50 附近 → 用 30 作分界
    if avg < 30:
        return 'prob'
    return 'scalar'

def get_wu_thresholds(v: dict) -> tuple:
    """返回 (weak_threshold, strong_threshold) 基于检测到的量纲口径"""
    if detect_vector_scale(v) == 'prob':
        # v_innate 概率分布：体质推理用 ±25%（_V_INNATE_DEVIATION_PCT = 0.25）
        mean = 20.0
        return (mean * 0.65, mean * 1.35)  # <13 偏弱, >27 偏强（稍宽避免过判）
    else:
        # 健康标量：45/65（HEALTH_POLYTOPE 边界 35-65 内收缩）
        return (45, 65)

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

