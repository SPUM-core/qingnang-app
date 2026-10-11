"""_v2_bounds - SPUM v2 主入口：compute_health_bounds_v2（S + σ + margin + 帧动力学 + dv/dt）"""
from __future__ import annotations
import math
from typing import Optional

from ._constants import (
    DIMS, HEALTH_POLYTOPE, HEALTH_CENTROID, SCALE,
    EMA_TAU_BOUNDARY, EMA_TAU_METAL,
    DV_DT_MAX, DV_DT_MAX_SIGMA,
    IMPERFECT_RESIDUE_MIN, PERFECT_HEALTH_LIMIT,
    SPUM_TOPOLOGICAL_CONST_12, SPUM_SURFACE_CAPACITY, SPUM_D_MAX, SPUM_FIVE_RATIO,
)
from ._basic import metal_elasticity, ema, norm
from ._v2_core import (
    build_S_vector, normalize_S_effective, health_polytope_margin,
    discrete_frame_5step, clamp_dv_dt,
)

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

    # ══════════════════════════════════════════════════
    # Phase 2.5: 尖峰三条件判定（L1 投影层 · 2D 阴阳平面）
    #
    # ⚠️ 显式标注：以下尖峰判定在 L1 投影层进行。
    #    原始五形本体是闭环耦合关系链条，塌缩为 2D（driftData）后丢失耦合细节。
    #    判定结果对应体质曲线形态，不声称对应 L0 本体层的五形状态。
    #
    # 三条件全部锚定已有变量：
    #   ① 快：|Δh| > SPIKE_BASIC_THRESH × el_factor(el[t-1])
    #   ② 顶：触有效边界 ± TOUCH_EPS
    #   ③ 弹：下一帧朝反方向运动
    #
    # viewMode 自适应（根据 elems 结构推断）：
    #   年视图：每帧=1年，driftData 幅度 ±5~10
    #   月视图：每帧≈几天，EMA 压缩后幅度 ±0.5~2
    # ══════════════════════════════════════════════════
    is_year_view = (n > 30 and all(p.get('age') is not None for p in elems))
    SPIKE_BASIC_THRESH = 2.0 if is_year_view else 0.4
    TOUCH_EPS = 0.5 if is_year_view else 0.1
    WINDOW_HALF = 2 if is_year_view else 1

    el_factor = lambda el: 0.4 + 0.6 * el

    # Phase 2.5a: 尖峰扫描
    spike_up = [False] * n    # 撞 yinTop（上边界）
    spike_down = [False] * n  # 撞 yangBot（下边界）

    for i in range(1, n - 1):
        h_prev = drift_data[i - 1]
        h_cur = drift_data[i]
        h_next = drift_data[i + 1]

        el_prev = el_arr[i - 1]
        thresh = SPIKE_BASIC_THRESH * el_factor(el_prev)
        delta = h_cur - h_prev

        if abs(delta) <= thresh:
            continue  # 条件①不满足 → 跳过

        if delta > 0:
            # 向上冲 → 撞 yinTop（正边界）
            eff_top = yin_top[i] * el_factor(el_arr[i])
            if eff_top - TOUCH_EPS <= h_cur <= eff_top + TOUCH_EPS:  # 条件②
                if h_next < h_cur:  # 条件③弹回
                    spike_up[i] = True
        else:
            # 向下冲 → 撞 yangBot（负边界）
            eff_bot = yang_bot[i] * el_factor(el_arr[i])
            if eff_bot - TOUCH_EPS <= h_cur <= eff_bot + TOUCH_EPS:  # 条件②
                if h_next > h_cur:  # 条件③弹回
                    spike_down[i] = True

    # Phase 2.5c: 5D 根判定增强尖峰（S₀ 中心化 · 2026-10-10 新增）
    #
    # 设计意图（algorithm.md 尖峰触边判定核实结论）：
    #   ① 快   = |Δh| ≥ spikeThresh（与 2.5a 相同，2D 投影层速度）
    # ① 快   = |Δ drift| > 基础阈值（SPIKE_BASIC_THRESH）
    # ② 顶   = 5D 健康多面体 H 触边（margin ≤ TOUCH_EPS）或首次越界
    #            （S_effective 根判定层，替代 EMA 滞后边界）
    # ③ 弹   = 下一帧 drift 反向且回落幅度 ≥ 30% 当前速度（子类型，非必要条件）
    #
    # 2026-10-10 按《尖峰触边判定_核实结论》4.1 落地：弹回从必要条件降为子类型。
    #   - 尖峰 + 弹回（rebound=True） = 弹性尚可（金形仍在工作）
    #   - 尖峰 + 不回（rebound=False）= 弹性失效（金形修剪不足，需干预）
    # 若仍把弹回当必要条件，穿出后持续恶化的帧永远不会被标为尖峰（acuteDeviation 盲区）。
    #
    # 旧实现仅以 EMA 滞后边界为"顶"，边界随信号漂移 → 实测任何场景
    # （平稳/冲击/终身推演）都撞不上，尖峰判定功能失效（P1-01）。
    spike_up_5d = [False] * n
    spike_down_5d = [False] * n
    rebound_up = [False] * n
    rebound_down = [False] * n
    for i in range(1, n - 1):
        h_prev = drift_data[i - 1]
        h_cur = drift_data[i]
        h_next = drift_data[i + 1]
        delta = h_cur - h_prev
        if abs(delta) <= SPIKE_BASIC_THRESH:
            continue  # ① 不快 → 跳过

        m = S_vectors[i]['margin']
        m_prev_status = S_vectors[i - 1]['margin']['status'] if i >= 1 else 'IN'
        touch_up = any(m['margins'][d]['hi'] is not None and
                       m['margins'][d]['hi'] <= TOUCH_EPS for d in DIMS)
        touch_dn = any(m['margins'][d]['lo'] is not None and
                       m['margins'][d]['lo'] <= TOUCH_EPS for d in DIMS)
        first_viol_up = (m['status'] == 'OUT' and m_prev_status != 'OUT' and
                         any(b == 'hi' for _, b, _ in m['violations']))
        first_viol_dn = (m['status'] == 'OUT' and m_prev_status != 'OUT' and
                         any(b == 'lo' for _, b, _ in m['violations']))

        if delta > 0:
            # 上冲触上边界 / 首越上界 → 尖峰（弹回为子类型标记）
            if touch_up or first_viol_up:
                spike_up_5d[i] = True
                rebound_up[i] = h_next < h_cur
        else:
            # 下冲触下边界 / 首越下界 → 尖峰（弹回为子类型标记）
            if touch_dn or first_viol_dn:
                spike_down_5d[i] = True
                rebound_down[i] = h_next > h_cur

    # 合并 EMA 路径与 5D 路径（保留原有判定 + 新增根判定，互不覆盖）
    spike_up = [a or b for a, b in zip(spike_up, spike_up_5d)]
    spike_down = [a or b for a, b in zip(spike_down, spike_down_5d)]

    # 速度 / 方向序列（S₀ 中心化曲线的一阶差分；前端 tooltip 与形态判定用）
    velocity = [0.0] * n
    direction = ['flat'] * n
    for i in range(1, n):
        _v = drift_data[i] - drift_data[i - 1]
        velocity[i] = round(_v, 3)
        direction[i] = 'up' if _v > 1e-9 else ('down' if _v < -1e-9 else 'flat')

    # S₀ 中心化后的漂移（去均值，均值回归到 0 轴；旧 driftData 以 EMA 中心为参考）
    _mean = sum(drift_data) / n if n else 0.0
    drift_centered = [round(h - _mean, 3) for h in drift_data]

    # 先天偏置向量（S₀ 中心化设计：S_effective = S_current − (S₀ − C)）
    centroid_bias = {d: round((innate.get(d, 50) or 50) - HEALTH_CENTROID[d], 2)
                     for d in DIMS}

    # Phase 2.5b: 三态 + 原有疾病模式联合判定
    state_flags = ['healthy'] * n  # healthy / subhealthy / disease
    disease_modes = [None] * n

    for i in range(n):
        h = drift_data[i]
        eff_top = yin_top[i] * el_factor(el_arr[i])
        eff_bot = yang_bot[i] * el_factor(el_arr[i])

        # v2 越界判定（保留 5D 凸多面体 OUT，更精确）
        v2_status = S_vectors[i]['margin']['status']
        v2_out = v2_status == 'OUT'
        v2_on = v2_status == 'ON'
        v2_touch = S_vectors[i]['margin']['touch']
        v2_depth = S_vectors[i]['margin']['violation_depth']
        v2_dim = S_vectors[i]['margin']['violation_dim']

        # ── 状态 3：疾病 ──
        if h > eff_top or h < eff_bot or v2_out:
            state_flags[i] = 'disease'
            if v2_depth > 5 or v2_dim in ('water', 'fire'):
                disease_modes[i] = 'acuteDeviation'
            else:
                disease_modes[i] = 'subtleDeviation'
            continue

        # ── 状态 2：亚健康（窗口内同方向尖峰 ≥ 2）──
        win_lo = max(0, i - WINDOW_HALF)
        win_hi = min(n, i + WINDOW_HALF + 1)
        up_spikes = sum(1 for j in range(win_lo, win_hi) if spike_up[j])
        dn_spikes = sum(1 for j in range(win_lo, win_hi) if spike_down[j])

        # 也用 v2 Touch≥2 辅助（5D 层 ON 状态反复触边）
        if up_spikes >= 2 or dn_spikes >= 2:
            state_flags[i] = 'subhealthy'
            disease_modes[i] = 'chronicBoundary'
            continue
        if v2_on and len(v2_touch) >= 2:
            state_flags[i] = 'subhealthy'
            disease_modes[i] = 'subtleDeviation'
            continue

        # 状态 1：健康（留在 default 初始化）

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
        # Phase 2.5 三态判定新增输出
        'stateFlags': state_flags,        # ['healthy'|'subhealthy'|'disease'] * n
        'spikeUp': spike_up,              # [bool] * n — 撞上边界（yinTop）尖峰
        'spikeDown': spike_down,          # [bool] * n — 撞下边界（yangBot）尖峰
        'spikeUp5d': spike_up_5d,         # [bool] * n — 5D 根判定触边尖峰（2026-10-10）
        'spikeDown5d': spike_down_5d,     # [bool] * n — 5D 根判定触边尖峰
        'reboundUp': rebound_up,          # [bool] * n — 上冲尖峰弹回子类型（金形弹性尚可）
        'reboundDown': rebound_down,      # [bool] * n — 下冲尖峰弹回子类型（金形弹性尚可）
        'velocity': velocity,             # [float] * n — 漂移速度（一阶差分）
        'direction': direction,           # ['up'|'down'|'flat'] * n — 漂移方向
        'driftCentered': drift_centered,  # [float] * n — S₀ 中心化漂移（去均值）
        'centroidBias': centroid_bias,    # {dim: float} — 先天偏置向量（S₀ − C）
        'adaptiveParams': {               # viewMode 自适应参数（前端调试用）
            'isYearView': is_year_view,
            'spikeThresh': SPIKE_BASIC_THRESH,
            'touchEps': TOUCH_EPS,
            'windowHalf': WINDOW_HALF,
        },
    }


# ═══════════════════════════════════════════════════════
# V2-7. build_year_view_v2 — 终身推演 v2 版
#
# 在 v1 build_year_view 的大运推演基础上，
# 注入 v2 的 S 向量 + σ 场 + dv/dt 约束
# ═══════════════════════════════════════════════════════

