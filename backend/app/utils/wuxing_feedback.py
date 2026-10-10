"""Wuxing-FB 五形生克负反馈模块 — SPUM 体质曲线算法层

版本: v1.0 (2026-10-08 定稿 β 参数)
核心模型: 五节点状态依赖负反馈网络（半隐式离散 · 无条件稳定）

主方程:
  s_i(t+1) = ( s_i(t) + dt·( u_i + Σ_j A_ji·ρ_j·s_j ) ) / ( 1 + dt·κ_i )
  ρ_i      = clamp( ρ₀_i + s_i, RHO_MIN, RHO_MAX )     # 总势能 = 先天基底 + 后天动态
  κ_i      = BETA_S·Σρ_j(生我+我生) + BETA_K·Σρ_j(克我+我克)  # 阻尼强度（其它四维拉力总和）

  A_ji     = 生克耦合矩阵:
             母旺养我 → +BETA_S    (生我者强则养我)
             子旺泄我 → -BETA_S    (我生者强则泄我)
             所不胜乘我 → -BETA_K  (克我者强则乘我)
             所胜耗我 → -BETA_K    (我克者强则耗我)

逆转阈值（动态，分岔式而非程度式）:
  θ_i = THETA₀ · ( 1 − GAMMA · 虚弱度_i )
  虚弱度_i = 1 − (其他四维平均势能) / 中和势能(=1.0)

  zone:  |s_i| <  0.7θ_i → IN    (带内 · 安全)
         0.7θ_i ≤ |s_i| < θ_i → CRIT  (临界 · 接近逆转)
         |s_i| ≥  θ_i → OUT   (带外 · 突破阈值 = 病态)

相对构型化（P0-A 量纲混用的模型层解药）:
  to_relative(v): 中心化 + 尺度归一，消除绝对口径（center=20 或 50 皆可）

参数（2026-10-08 多构型判别复验定稿）:
  BETA_SHENG = 0.60   相生边阻尼（生主克辅）
  BETA_KE    = 0.40   相克边阻尼（病机可见性的代价）
  THETA0     = 1.00   逆转阈值基线
  GAMMA      = 0.60   虚弱度对阈值的折损系数
  RHO_MIN    = 0.05   总势能下限
  RHO_MAX    = 3.00   总势能上限
  DT         = 0.25   离散步长

依赖: 纯标准库（math），零第三方依赖
"""
from __future__ import annotations
import math
from typing import Dict, List, Tuple, Optional

# ═══════════════════════════════════════════════════════
# 五行常量
# ═══════════════════════════════════════════════════════

DIMS = ['wood', 'fire', 'earth', 'metal', 'water']

# 相生 (SHENG): 木→火→土→金→水→木
SHENG = {
    'wood':  'fire',   # 我生
    'fire':  'earth',
    'earth': 'metal',
    'metal': 'water',
    'water': 'wood',
}
# 相克 (KE): 木→土→水→火→金→木
KE = {
    'wood':  'earth',   # 我克
    'earth': 'water',
    'water': 'fire',
    'fire':  'metal',
    'metal': 'wood',
}

# 推导：生我者、克我者
SHENG_BY = {child: parent for parent, child in SHENG.items()}   # child ← parent
KE_BY    = {prey: predator for predator, prey in KE.items()}   # prey ← predator
# 对 i 而言:
#   生我者 = SHENG_BY[i]    (谁生我)
#   我生者 = SHENG[i]       (我生谁)
#   克我者 = KE_BY[i]       (谁克我)
#   我克者 = KE[i]          (我克谁)

# ═══════════════════════════════════════════════════════
# 定稿参数（2026-10-08 多构型判别复验）
# ═══════════════════════════════════════════════════════

BETA_SHENG = 0.60   # β_s: 相生边阻尼
BETA_KE    = 0.40   # β_k: 相克边阻尼
THETA0     = 1.00   # θ₀: 逆转阈值基线
GAMMA      = 0.60   # γ: 虚弱度折损系数
RHO_MIN    = 0.05   # ρ 钳制下限（总势能绝对下限）
RHO_MAX    = 3.00   # ρ 钳制上限
DT         = 0.25   # 离散步长（年粒度 ≈ 1 step/year，节气粒度可换算）

# ── 落地修复参数（2026-10-08 主链路接入诊断） ──
ALPHA_RHO   = 0.25   # 相对形状 → 势能的柔和缩放系数（旧 1.0 线性放大导致 0.05/2.11 极端钳制）
RHO_SOFT_MIN = 0.40  # 柔和势能下限（形状映射的软钳制，避免 RHO_MIN=0.05 压平差异）
RHO_SOFT_MAX = 1.60  # 柔和势能上限
LEVEL_LO    = 0.60   # 绝对水平系数下限（观测均值/中心 50）
LEVEL_HI    = 1.40   # 绝对水平系数上限

# ═══════════════════════════════════════════════════════
# 耦合矩阵 A_ji
# ═══════════════════════════════════════════════════════

def build_coupling_matrix(beta_s: float = BETA_SHENG,
                          beta_k: float = BETA_KE) -> Dict[str, Dict[str, float]]:
    """构造 5×5 生克耦合矩阵 A_ji (行=受影响维 i, 列=作用源 j)

    A[i][j] = 从 j 到 i 的耦合强度
      - j 生 i (生我): +β_s   母旺养我
      - j 被 i 生 (我生): -β_s  子旺泄我 (j 旺则我被泄)
      - j 克 i (克我): -β_k   所不胜乘我
      - j 被 i 克 (我克): -β_k  所胜耗我 (j 旺则我耗)
    """
    A: Dict[str, Dict[str, float]] = {i: {j: 0.0 for j in DIMS} for i in DIMS}
    for i in DIMS:
        for j in DIMS:
            if i == j:
                continue
            # 判断 j 与 i 的关系
            if SHENG_BY[i] == j:    # j 生 i (生我)
                A[i][j] += beta_s
            if SHENG[i] == j:       # i 生 j (我生 → j 旺泄我)
                A[i][j] -= beta_s
            if KE_BY[i] == j:       # j 克 i (克我)
                A[i][j] -= beta_k
            if KE[i] == j:          # i 克 j (我克 → j 旺耗我)
                A[i][j] -= beta_k
    return A


# ═══════════════════════════════════════════════════════
# 阻尼 κ_i
# ═══════════════════════════════════════════════════════

def compute_damping(rho: Dict[str, float],
                    beta_s: float = BETA_SHENG,
                    beta_k: float = BETA_KE) -> Dict[str, float]:
    """κ_i = β_s·Σρ_j(生我+我生) + β_k·Σρ_j(克我+我克)"""
    kappa = {}
    for i in DIMS:
        # 生我 + 我生 的 ρ_j 之和
        sheng_rho = rho[SHENG_BY[i]] + rho[SHENG[i]]
        # 克我 + 我克 的 ρ_j 之和
        ke_rho = rho[KE_BY[i]] + rho[KE[i]]
        kappa[i] = beta_s * sheng_rho + beta_k * ke_rho
    return kappa


# ═══════════════════════════════════════════════════════
# 相对构型化（P0-A 量纲混用解药）
# ═══════════════════════════════════════════════════════

def to_relative(v: Dict[str, float]) -> Dict[str, float]:
    """把任意五行向量转相对构型：中心化 + 尺度归一

    消除绝对口径（v_innate center=20, 观测 center=50 皆可），
    输出以 0 为中心、标准差 = 1 的相对形状。
    """
    vals = [v.get(d, 0.0) for d in DIMS]
    n = len(vals)
    mean = sum(vals) / n
    centered = [x - mean for x in vals]
    # 尺度归一：用平均绝对偏差做 robust scale
    abs_dev = sum(abs(x) for x in centered) / n
    if abs_dev < 1e-9:
        abs_dev = 1.0
    scaled = {DIMS[i]: centered[i] / abs_dev for i in range(n)}
    return scaled


def rho_from_relative(v_rel: Dict[str, float],
                       equilibrium: float = 1.0,
                       alpha: float = ALPHA_RHO,
                       level: float = 1.0) -> Dict[str, float]:
    """相对构型 → 势能基底 ρ₀（柔和映射 + 绝对水平）

    修复（2026-10-08 主链路接入诊断）:
      旧实现 ρ₀=1+v_rel 线性放大 + RHO_MIN 钳制 → 火土 0.05 / 金水 2.11 极端化，
      且中心化抹掉绝对虚弱度（v_innate 均值恒 20 → ρ₀ 均值恒 1.0 → 虚弱度≈0）。
      新实现:
        ρ₀_i = clamp( equilibrium + alpha·v_rel_i , RHO_SOFT_MIN, RHO_SOFT_MAX ) × level
      - alpha 柔和缩放（默认 0.25）：形状差异映射到 [0.4, 1.6]，保留相对虚实但不过度钳制
      - level 绝对水平（观测均值/日主强弱）：整体虚则 ρ₀ 下移 → θ 收窄 → 区间变窄
        无观测数据时 level=1.0（仅形状模式）
    """
    rho = {}
    for d in DIMS:
        r = equilibrium + alpha * v_rel.get(d, 0.0)
        r = max(RHO_SOFT_MIN, min(RHO_SOFT_MAX, r))
        rho[d] = max(RHO_MIN, min(RHO_MAX, r * level))
    return rho


def rho_level_from_observation(obs: Dict[str, float],
                               center: float = 50.0,
                               lo: float = LEVEL_LO,
                               hi: float = LEVEL_HI) -> float:
    """观测向量 → 绝对水平系数 level = clamp( mean(obs)/center, lo, hi )

    观测口径 center=50：五维均值 45 → level 0.9（整体偏虚，ρ₀ 整体下移，θ 收窄）。
    仅先天形状信号（v_innate center=20 无绝对水平）时调用方传 level=1.0。
    """
    if not obs:
        return 1.0
    vals = [obs.get(d, center) for d in DIMS]
    m = sum(vals) / len(vals)
    if m <= 1e-9:
        return 1.0
    return max(lo, min(hi, m / center))


# ═══════════════════════════════════════════════════════
# 逆转阈值 & 带判定
# ═══════════════════════════════════════════════════════

def compute_thresholds(rho: Dict[str, float],
                       theta0: float = THETA0,
                       gamma: float = GAMMA) -> Dict[str, float]:
    """θ_i = θ₀ · ( 1 − γ · 虚弱度_i )
    虚弱度_i = 1 − (其他四维平均势能) / 中和势能(=1.0)
    """
    theta = {}
    for i in DIMS:
        others = [rho[d] for d in DIMS if d != i]
        avg_other = sum(others) / len(others)
        weakness = 1.0 - avg_other   # avg_other=1.0 → weakness=0 (健康); avg_other=0.5 → weakness=0.5
        theta[i] = theta0 * (1.0 - gamma * weakness)
    return theta


def zone_of(s_i: float, theta_i: float) -> str:
    """判定单维带状态: IN / CRIT / OUT"""
    a = abs(s_i)
    if a < 0.7 * theta_i:
        return 'IN'
    elif a < theta_i:
        return 'CRIT'
    else:
        return 'OUT'


def classify_virtual(s_dict: Dict[str, float], theta: Dict[str, float]) -> Dict[str, str]:
    """五维虚实判定: 每维 zone + 虚实标签"""
    result = {}
    for d in DIMS:
        z = zone_of(s_dict.get(d, 0.0), theta[d])
        # OUT 且 s>0 → 实; OUT 且 s<0 → 虚
        tag = z
        if z == 'OUT':
            tag = '实' if s_dict.get(d, 0.0) > 0 else '虚'
        result[d] = tag
    return result


# ═══════════════════════════════════════════════════════
# 网络演化（半隐式 · 无条件稳定）
# ═══════════════════════════════════════════════════════

def step(s: Dict[str, float],
         rho0: Dict[str, float],
         u: Dict[str, float],
         A: Dict[str, Dict[str, float]],
         dt: float = DT) -> Tuple[Dict[str, float], Dict[str, float]]:
    """单步演化: s(t) → s(t+1)

    返回 (s_next, rho_next)
    """
    # 先算当前 rho
    rho_curr = {}
    for i in DIMS:
        r = rho0[i] + s[i]
        rho_curr[i] = max(RHO_MIN, min(RHO_MAX, r))

    # 阻尼
    kappa = compute_damping(rho_curr)

    # 耦合项 Σ_j A_ji·ρ_j·s_j
    coupling = {}
    for i in DIMS:
        acc = 0.0
        for j in DIMS:
            if j == i:
                continue
            acc += A[i][j] * rho_curr[j] * s[j]
        coupling[i] = acc

    # 半隐式更新
    s_next = {}
    for i in DIMS:
        numerator = s[i] + dt * (u.get(i, 0.0) + coupling[i])
        denominator = 1.0 + dt * kappa[i]
        s_next[i] = numerator / denominator

    rho_next = {}
    for i in DIMS:
        r = rho0[i] + s_next[i]
        rho_next[i] = max(RHO_MIN, min(RHO_MAX, r))

    return s_next, rho_next


def relax(rho0: Dict[str, float],
          u_sequence: List[Dict[str, float]],
          A: Optional[Dict[str, Dict[str, float]]] = None,
          n_steps: int = 12,
          dt: float = DT,
          s_start: Optional[Dict[str, float]] = None) -> List[Dict]:
    """弛豫演化: 给定期注入序列 u_sequence，演化 n_steps，返回每步记录

    典型用法:
      relax(rho0, [u_dayun + u_liunian] * n_steps)  # 稳态注入弛豫

    s_start: 可选，从指定初始 s 起弛豫（用于节气视图串联 / 调平累积效果）
    """
    if A is None:
        A = build_coupling_matrix()

    # 初始 s=0 或传入值
    s = dict(s_start) if s_start is not None else {d: 0.0 for d in DIMS}
    records = []

    # 把 u_sequence 展平到 n_steps 长度
    if len(u_sequence) < n_steps:
        u_seq = u_sequence + [u_sequence[-1]] * (n_steps - len(u_sequence))
    else:
        u_seq = u_sequence[:n_steps]

    for step_idx in range(n_steps):
        u = u_seq[step_idx]
        s, rho = step(s, rho0, u, A, dt)
        theta = compute_thresholds(rho)
        zones = {d: zone_of(s[d], theta[d]) for d in DIMS}
        records.append({
            'step': step_idx,
            's': {d: round(s[d], 4) for d in DIMS},
            'rho': {d: round(rho[d], 4) for d in DIMS},
            'theta': {d: round(theta[d], 4) for d in DIMS},
            'zone': zones,
        })

    return records


# ═══════════════════════════════════════════════════════
# 稳态取法（接入主链路的核心入口）
# ═══════════════════════════════════════════════════════

def steady_state(rho0: Dict[str, float],
                 u: Dict[str, float],
                 A: Optional[Dict[str, Dict[str, float]]] = None,
                 n_steps: int = 12,
                 s_start: Optional[Dict[str, float]] = None,
                 dt: float = DT) -> Dict:
    """给定期注入 u（大运+流年+节气），弛豫取稳态

    返回: {s, rho, theta, zone, weak_virtual, tolerance_u}
      weak_virtual: {虚: [...], 实: [...], 临界: [...]}
      tolerance_u: 各维耐受强度（使该维破阈值的最小注入强度）

    s_start: 可选初始 s（用于节气视图串联 / 调平累积效应）
    dt: 时间步长（year-view 默认 0.25；节气视图可设 1/24 ≈ 0.042）
    """
    if A is None:
        A = build_coupling_matrix()

    records = relax(rho0, [u] * n_steps, A, n_steps, dt=dt, s_start=s_start)
    last = records[-1]

    s = last['s']
    rho = last['rho']
    theta = last['theta']

    # 虚实分类
    # 2026-10-10 修复：classify_virtual 的标签体系为 IN/CRIT/实/虚，
    # 旧实现按 '临界'/'带内' 消费 → weak_virtual['临界']/['带内'] 恒空，
    # CRIT（临界）状态被静默丢弃。此处按 zone_of 的原始标签 IN/CRIT 归集。
    vtags = classify_virtual(s, theta)
    weak = [d for d, t in vtags.items() if t == '虚']
    strong = [d for d, t in vtags.items() if t == '实']
    critical = [d for d, t in vtags.items() if t == 'CRIT']
    in_band = [d for d, t in vtags.items() if t == 'IN']

    # 动态耐受强度 u*（从当前稳态 s 起扫：u* 随状态/调平移动）
    tolerance_u = _compute_tolerance(rho0, A, theta, n_steps, s_start=s)

    return {
        's': s,
        'rho': rho,
        'theta': theta,
        'zone': vtags,
        'weak_virtual': {'虚': weak, '实': strong, '临界': critical, '带内': in_band},
        'tolerance_u': tolerance_u,
        'records': records,  # 调试用
    }


def _compute_tolerance(rho0, A, theta_target, n_steps=12,
                       s_start: Optional[Dict[str, float]] = None,
                       probe_dims: Optional[List[str]] = None) -> Dict[str, float]:
    """数值扫描各维耐受强度 u*

    修复（2026-10-08）：新增 s_start 支持从「当前状态」起扫 ——
      - s_start=None（旧行为）：从 s=0 起扫 → u* 只由先天 ρ₀ 决定，恒为常数，调平无反馈
      - s_start=当前稳态 s：u* = 在当前偏移下「再注入多少」该维会突破 → 随状态/调平移动

    对每个维度 d，逐步加大 u_d（其余为 0），直到 s_d 突破 θ_d，二分查找。
    """
    if probe_dims is None:
        probe_dims = DIMS

    s0 = s_start if s_start is not None else {d: 0.0 for d in DIMS}

    result = {}
    for d in probe_dims:
        lo, hi = 0.0, 5.0
        for _ in range(20):  # 精度 ≈ 5/2^20 ≈ 5e-6
            mid = (lo + hi) / 2.0
            u_probe = {dd: 0.0 for dd in DIMS}
            u_probe[d] = mid
            # 从 s0 起演化 n_steps（半隐式无条件稳定）
            s = dict(s0)
            rho = {i: max(RHO_MIN, min(RHO_MAX, rho0[i] + s[i])) for i in DIMS}
            for _ in range(n_steps):
                s, rho = step(s, rho0, u_probe, A, dt=DT)
            th = compute_thresholds(rho)[d]
            if abs(s[d]) >= th:
                hi = mid
            else:
                lo = mid
        result[d] = round((lo + hi) / 2.0, 3)
    return result


# ═══════════════════════════════════════════════════════
# 兼容层（2026-10-08 实测复核修复）
# 早期复现脚本（backend/scripts/wuxing_feedback_*.py）导入 reversal_threshold / zone_status
# ═══════════════════════════════════════════════════════

def reversal_threshold(s: Dict[str, float], rho0: Dict[str, float]) -> Dict[str, float]:
    """旧名兼容：逆转阈值 θ（动态势能 ρ = ρ₀ + s）

    早期脚本语义：θ 随当前偏移 s 动态变化（先天基底 + 后天偏移），
    等价于 compute_thresholds({k: rho0[k] + s[k]})。
    """
    rho_dyn = {d: max(RHO_MIN, min(RHO_MAX, rho0.get(d, 1.0) + s.get(d, 0.0))) for d in DIMS}
    return compute_thresholds(rho_dyn)


def zone_status(s_dict: Dict[str, float], theta: Dict[str, float],
                rho0: Optional[Dict[str, float]] = None) -> Dict[str, Dict[str, bool]]:
    """旧名兼容：五维带状态 → {out, crit, xu, shi} 各维 bool dict

    早期脚本结构：zone_status(s, th, rho0)['out'][dim] / ['crit'] / ['xu'] / ['shi']。
    """
    out, crit, xu, shi = {}, {}, {}, {}
    for d in DIMS:
        th = theta.get(d, 1.0)
        a = abs(s_dict.get(d, 0.0))
        z = 'OUT' if a >= th else ('CRIT' if a >= 0.7 * th else 'IN')
        out[d] = z == 'OUT'
        crit[d] = z == 'CRIT'
        xu[d] = z == 'OUT' and s_dict.get(d, 0.0) < 0
        shi[d] = z == 'OUT' and s_dict.get(d, 0.0) > 0
    return {'out': out, 'crit': crit, 'xu': xu, 'shi': shi}


# ═══════════════════════════════════════════════════════
# 快捷入口: 从原始五行字典一路到稳态
# ═══════════════════════════════════════════════════════

def compute_frame(rho0_raw: Dict[str, float],
                  injection: Dict[str, float],
                  n_steps: int = 12) -> Dict:
    """一站式接口: 原始先天向量 + 注入 → 稳态

    rho0_raw: 任意口径五行向量 (e.g. v_innate center=20 或观测 center=50)
    injection: 注入向量 (dayun + liunian + jieqi bias)，u 的绝对值是相对口径
    """
    # 1. 先天向量 → 相对构型 → 势能基底
    v_rel = to_relative(rho0_raw)
    rho0 = rho_from_relative(v_rel, equilibrium=1.0)

    # 2. 注入 → 相对口径（同样过 to_relative，然后映射到 [-2, +2]）
    if injection:
        # 把 injection 映射成小量级 u（strength=22 → 归一化到 ±2）
        u_raw = {d: float(injection.get(d, 0.0)) for d in DIMS}
        # 简单归一：如果 max(|u|) > 2，压缩；否则保持
        max_abs = max(abs(x) for x in u_raw.values()) if u_raw else 0.0
        if max_abs > 0.0:
            # 报告 EXP2 中 u=1.0 能让虚弱组破阈值，所以 ±2 是极值
            u = {d: u_raw[d] / max_abs * min(max_abs, 2.0) for d in DIMS}
        else:
            u = {d: 0.0 for d in DIMS}
    else:
        u = {d: 0.0 for d in DIMS}

    return steady_state(rho0, u, n_steps=n_steps)


# ═══════════════════════════════════════════════════════
# 模块自检
# ═══════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 60)
    print("Wuxing-FB 模块自检 (β_s=0.60, β_k=0.40)")
    print("=" * 60)

    # 1. 均匀构型自愈
    rho0_uniform = {d: 1.0 for d in DIMS}
    A_mat = build_coupling_matrix()

    # 脉冲注入: 木 +2.0 只在第 0 步，后续 29 步撤去
    pulse_sequence = [{'wood': 2.0, 'fire': 0, 'earth': 0, 'metal': 0, 'water': 0}] + \
                     [{'wood': 0, 'fire': 0, 'earth': 0, 'metal': 0, 'water': 0}] * 29
    records = relax(rho0_uniform, pulse_sequence, A_mat, n_steps=30)
    last_s = records[-1]['s']
    max_residual = max(abs(v) for v in last_s.values())
    print(f"\nEXP1 自愈 (木脉冲2.0后撤去): 30步后 |s|max = {max_residual:.4f} (期望 < 0.01 回落中和)")
    print(f"  末态 s: wood={last_s['wood']:+.4f} fire={last_s['fire']:+.4f} "
          f"earth={last_s['earth']:+.4f} metal={last_s['metal']:+.4f} water={last_s['water']:+.4f}")
    # 峰值位置
    peak_step = max(range(30), key=lambda k: abs(records[k]['s']['wood']))
    peak_val = abs(records[peak_step]['s']['wood'])
    print(f"  峰值: 第 {peak_step} 步, |s_木| = {peak_val:.4f}")

    # 2. 健康 vs 虚弱判别
    print(f"\nEXP2 判别 (持续 u_木=1.0):")
    # 健康组: rho0 全 1.0
    ss_healthy = steady_state(rho0_uniform, {'wood': 1.0, 'fire': 0, 'earth': 0, 'metal': 0, 'water': 0}, A_mat)
    print(f"  健康组木稳态 s={ss_healthy['s']['wood']:.3f}, "
          f"θ={ss_healthy['theta']['wood']:.3f}, zone={ss_healthy['zone']['wood']}")

    # 虚弱组: 火土虚 (ρ₀=火0.5·土0.5·金0.8·水0.8)
    rho0_weak = {'wood': 1.0, 'fire': 0.5, 'earth': 0.5, 'metal': 0.8, 'water': 0.8}
    ss_weak = steady_state(rho0_weak, {'wood': 1.0, 'fire': 0, 'earth': 0, 'metal': 0, 'water': 0}, A_mat)
    print(f"  虚弱组木稳态 s={ss_weak['s']['wood']:.3f}, "
          f"θ={ss_weak['theta']['wood']:.3f}, zone={ss_weak['zone']['wood']}")
    print(f"  虚弱组虚证={ss_weak['weak_virtual']['虚']}, 实证={ss_weak['weak_virtual']['实']}")

    # 3. 耦合矩阵检查
    print(f"\n耦合矩阵 A (检查):")
    for i in DIMS:
        row = [f"A[{i}][{j}]={A_mat[i][j]:+.2f}" for j in DIMS if A_mat[i][j] != 0]
        print(f"  {i}: {', '.join(row)}")

    print(f"\n✅ 模块就绪，β_s={BETA_SHENG}, β_k={BETA_KE}")
