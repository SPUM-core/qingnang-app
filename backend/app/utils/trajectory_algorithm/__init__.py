"""SPUM 体质轨迹算法 — SPUM2611 + 青囊中医总纲 迭代

门面模块：聚合 _constants/_basic/_ganzhi/_jieqi/_year_v1/_v2_core/
_v2_bounds/_v2_yearview/_v3 各子模块并 re-export 全部公共符号。

外部引用统一 `from ...utils.trajectory_algorithm import X`，保持兼容。
子模块均以 `_` 开头，为内部实现，外部请勿直接 import。

算法版本: spum_computeHealthBounds_v2
核心公理: 关系定义存在 → S五维健康向量 → σ空间密度 → dv/dt≤const
"""
from __future__ import annotations

# ── 常量（v1/v2/v3）─────────────────────────────
from ._constants import (
    DIMS, SCALE, EMA_TAU_BOUNDARY, EMA_TAU_METAL,
    METAL_ELASTICITY_MIN, METAL_ELASTICITY_MAX,
    SPUM_TOPOLOGICAL_CONST_12, SPUM_SURFACE_CAPACITY, SPUM_D_MAX, SPUM_FIVE_RATIO,
    HEALTH_POLYTOPE, HEALTH_CENTROID,
    DV_DT_MAX, DV_DT_MAX_SIGMA,
    FRAME_CREATION_WEIGHT, FRAME_CONNECTION_WEIGHT, FRAME_CHANGE_WEIGHT,
    FRAME_JUDGMENT_WEIGHT, FRAME_DELETION_WEIGHT,
    IMPERFECT_RESIDUE_MIN, PERFECT_HEALTH_LIMIT,
    TIANGAN_WUXING, DIZHI_CANGGAN, _GAN_CHARS, _ZHI_CHARS,
    JIEQI_NAMES, JIEQI_WUXING_BIAS, JIEQI_MAIN_WX,
    U_PEAK_FIXED, INJECT_SIDE,
    YY_W_YANG, YY_W_YIN,
)

# ── v1 基础 ─────────────────────────────────────
from ._basic import (
    detect_vector_scale, get_wu_thresholds,
    norm, compute_yx, ema, metal_elasticity, compute_health_bounds,
)

# ── 干支 / 节气 / 年视图 v1 ─────────────────────
from ._ganzhi import (
    ganzhi_to_elems, elems_to_delta, get_liunian, liunian_delta,
    dayun_delta, smooth3, smooth5, ganzhi_main_elem,
)
from ._jieqi import build_jieqi_view_v2
from ._year_v1 import _smoothstep, build_year_view

# ── v2（S 向量 / margin / 帧动力学 / 主入口 / 终身推演）──
from ._v2_core import (
    build_S_vector, normalize_S_effective, health_polytope_margin,
    discrete_frame_5step, clamp_dv_dt,
)
from ._v2_bounds import compute_health_bounds_v2
from ._v2_yearview import build_year_view_v2

# ── v3（Wuxing-FB 旁路 + 阴阳投影）──────────────
from ._v3 import (
    WUXING_FB_AVAILABLE, wuxing_frame_analysis,
    yang_growth_factor, yin_growth_factor, build_yin_yang_projection,
    build_year_view_v3, build_jieqi_view_v3,
)
