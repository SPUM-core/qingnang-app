"""_v2_core - SPUM v2 核心：S 向量构建 / 归一化 / 凸多面体 margin / 帧动力学"""
from __future__ import annotations
import math

from ._constants import (
    DIMS, HEALTH_POLYTOPE, HEALTH_CENTROID,
    DV_DT_MAX, DV_DT_MAX_SIGMA,
    FRAME_CREATION_WEIGHT, FRAME_CONNECTION_WEIGHT, FRAME_CHANGE_WEIGHT,
    FRAME_JUDGMENT_WEIGHT, FRAME_DELETION_WEIGHT,
    IMPERFECT_RESIDUE_MIN, PERFECT_HEALTH_LIMIT,
)
from ._basic import norm

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
        # 2026-10-10 防护：NaN/None/非数值输入按健康中心兜底，避免污染 σ/判定
        _inn = S_innate.get(dim, 50)
        if not isinstance(_inn, (int, float)) or not math.isfinite(_inn):
            _inn = 50.0
        innate_bias = _inn - HEALTH_CENTROID[dim]
        # S_effective = S_current - 先天偏移
        _cur = S_current.get(dim, 50)
        if not isinstance(_cur, (int, float)) or not math.isfinite(_cur):
            _cur = 50.0
        s_eff[dim] = _cur - innate_bias
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
                           touch_threshold: float = 2.0) -> dict:
    """健康凸多面体 H 边界判定

    Args:
        S_eff: S_effective 向量（已消除先天差异）
        touch_threshold: 触碰边界阈值（默认 2.0 单位）
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
    invalid_dims = []  # 非有限数值维度（2026-10-10 防护）

    for dim in DIMS:
        lo, hi = HEALTH_POLYTOPE[dim]
        val = S_eff.get(dim, HEALTH_CENTROID[dim])

        # 2026-10-10 防护：NaN/Inf 等非有限数值 → 标记 INVALID 而非误判 IN/ON/OUT
        if not isinstance(val, (int, float)) or not math.isfinite(val):
            invalid_dims.append(dim)
            margins[dim] = {'lo': None, 'hi': None}
            continue

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
    if invalid_dims:
        status = 'INVALID'
    elif violations:
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
        'invalid_dims': invalid_dims,
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

