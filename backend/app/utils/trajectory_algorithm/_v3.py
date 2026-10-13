"""_v3 - SPUM v3 Wuxing-FB 旁路：wuxing_frame_analysis / 阴阳投影 / build_year_view_v3 / build_jieqi_view_v3"""
from __future__ import annotations
import math
import logging
from typing import Optional

from ._constants import DIMS, U_PEAK_FIXED, INJECT_SIDE, YY_W_YANG, YY_W_YIN
from ._basic import get_wu_thresholds, metal_elasticity
from ._ganzhi import ganzhi_to_elems, get_liunian, liunian_delta
from ._jieqi import build_jieqi_view_v2
from ._v2_yearview import build_year_view_v2

# Wuxing-FB 可选导入（独立模块，零依赖，导入失败不影响 v2）
try:
    from app.utils.wuxing_feedback import (
        DIMS as WX_DIMS,
        build_coupling_matrix as wx_build_A,
        compute_frame as wx_compute_frame,
        steady_state as wx_steady_state,
        to_relative as wx_to_relative,
        rho_from_relative as wx_rho0_from_rel,
        compute_thresholds as wx_theta,
        BETA_SHENG as wx_BS,
        BETA_KE as wx_BK,
        RHO_MAX as wx_RHO_MAX,
        _compute_tolerance as wx_tol,
    )
    WUXING_FB_AVAILABLE = True
except Exception:
    WUXING_FB_AVAILABLE = False


def _normalize_injection(raw_inj: dict, u_peak: float,
                         dims: list) -> dict:
    """将原始注入向量归一化为主维主导结构（峰值维保持 u_peak，其余维弱化）

    用于 year-view / jieqi-view 的天时注入标定：
    旧实现整体归一 + 硬帽 ±2.0 → 多维注入互相牵制（水涨船高），zone 全 IN。
    新实现：峰值维保持 u_peak 本征强度，其余维按 INJECT_SIDE 弱化 →
            行为接近单维扫描，判别窗口（u* 单维定义）得以重现。

    Args:
        raw_inj: 原始注入向量 {dim: float}
        u_peak: 峰值维本征强度（固定值 U_PEAK_FIXED）
        dims: 维度列表
    Returns:
        归一化后的注入向量
    """
    max_abs = max(abs(x) for x in raw_inj.values()) if raw_inj else 0.0
    if max_abs <= 1e-9:
        return {d: 0.0 for d in dims}
    return {
        d: raw_inj[d] / max_abs * u_peak * (
            1.0 if abs(raw_inj[d]) >= max_abs - 1e-9 else INJECT_SIDE
        )
        for d in dims
    }


def wuxing_frame_analysis(innate: dict,
                          injection: dict,
                          n_steps: int = 12) -> Optional[dict]:
    """单帧 Wuxing-FB 分析（旁路 · 不替换 v2）

    Args:
        innate: 先天五行向量（任意口径，center=20 或 50 都行，会过 to_relative）
        injection: 注入向量（dayun + liunian + jieqi bias 之和）
        n_steps: 弛豫步数（默认 12，稳态）

    Returns:
        {
            's':        五维动态偏移 s_i（稳态）
            'rho':      五维总势能 ρ_i = ρ₀_i + s_i
            'theta':    五维逆转阈值 θ_i（动态）
            'zone':     每维 IN/CRIT/OUT 带状态
            'weak_virtual': {虚:[], 实:[], 临界:[], 带内:[]}
            'tolerance_u':   各维耐受强度 u*（使该维破阈值的最小注入）
            'min_tolerance': 最弱方向 (dim, u*) — 邪之所凑其气必虚
            'gap':       当前注入 vs 耐受强度的裕度 gap_i = u*_i - |s_i|
        }
        或 None（Wuxing-FB 模块不可用时）
    """
    if not WUXING_FB_AVAILABLE:
        return None

    try:
        result = wx_compute_frame(innate, injection, n_steps=n_steps)

        # 最弱方向
        tol = result['tolerance_u']
        min_dim = min(tol, key=lambda d: tol[d])
        min_u = tol[min_dim]

        # 裕度 gap = u* - |s| 越大越安全
        gap = {d: round(tol[d] - abs(result['s'][d]), 3) for d in WX_DIMS}

        # weak_virtual dict keys 里加带内
        wv = result['weak_virtual']
        # normalize keys（2026-10-10：zone 标签体系为 IN/CRIT/实/虚，
        # 旧写法把 CRIT 也计入带内、'临界' 恒空 —— 修正为精确语义）
        zone_map = result['zone']
        in_zone = [d for d, z in zone_map.items() if z == 'IN']

        return {
            's': {d: round(result['s'][d], 4) for d in WX_DIMS},
            'rho': {d: round(result['rho'][d], 4) for d in WX_DIMS},
            'theta': {d: round(result['theta'][d], 4) for d in WX_DIMS},
            'zone': zone_map,
            'weak_virtual': {
                '虚': wv.get('虚', []),
                '实': wv.get('实', []),
                '临界': [d for d, z in zone_map.items() if z == 'CRIT'],
                '带内': in_zone,
            },
            'tolerance_u': tol,
            'min_tolerance': {'dim': min_dim, 'u_star': round(min_u, 3)},
            'gap': gap,
        }
    except Exception as e:
        logging.getLogger(__name__).warning(f"Wuxing-FB frame analysis failed: {e}")
        return None


# ════════════════════════════════════════════════════════════════
# V3.1 · 阴阳投影层（tizhi-curve 借鉴 · 2026-10-09）
#
# 把 Wuxing-FB 五维相对偏移 s 翻译成旧版"人生曲线"的直观形态：
#   阳偏 = 火/木发散力（s_fire, s_wood 加权）—— 阳化气
#   阴偏 = 土/水收敛力（s_earth, s_water 加权）—— 阴成形
#   金   = 边界调节器，不投影（SPUM 本体：金决定区间弹性，algorithm.md:51）
#   实线 = 有符号阴阳偏移 drift_yy（正=阳偏↑ 负=阴偏↓）
#   区间 = 逆转阈值 θ 投影 × 金弹性 × 生命周期包络（2D 呈现层）
#
# ⚠️ 判定仍在 5D（zone_series / 逆转阈值分岔）；本层只作可视化
#    （tizhi-curve 核实结论 4.2 约定：2D 只呈现，不承担判定）
# ════════════════════════════════════════════════════════════════

# 阴阳投影权重（沿用 tizhi-curve computeYX 的 SPUM 五行归属：
# 阳 = 火(∇σ 创生驱动)0.55 + 木(创生产物)0.45
# 阴 = 土(储备池)0.55 + 水(储能链)0.45）
YY_W_YANG = {'fire': 0.55, 'wood': 0.45}
YY_W_YIN = {'earth': 0.55, 'water': 0.45}


def yang_growth_factor(age: float) -> float:
    """阳生命周期包络（tizhi-curve yangAgeFactor 移植）：
    0-16 幼儿阳气充盛（sigmoid→2.5）；16-35 壮年峰值线性降；35+ 高斯衰退"""
    if not age or age <= 0:
        return 0.05
    if age <= 16:
        return (1 - math.exp(-age / 5)) * 2.5
    if age <= 35:
        return 2.5 - (age - 16) * (0.7 / 19)
    return max(0.15, 1.8 * math.exp(-((age - 35) ** 2) / (2 * 28 * 28)))


def yin_growth_factor(age: float) -> float:
    """阴生命周期包络（tizhi-curve yinAgeFactor 移植）：
    0-16 阴基本不动；16-35 壮年；35+ 同步衰退"""
    if not age or age <= 0:
        return 0.1
    if age <= 16:
        return 0.1 + (age / 16) * 0.6
    if age <= 35:
        return 0.7 + (age - 16) * (0.3 / 19)
    return max(0.15, 1.0 * math.exp(-((age - 35) ** 2) / (2 * 28 * 28)))


def build_yin_yang_projection(s_series: list, theta_series: list, ages: list,
                              metal_series: Optional[list] = None,
                              el_factor: Optional[callable] = None) -> dict:
    """五维相对偏移 s → 有符号阴阳偏移 + 阴阳健康区间（呈现层）

    Args:
        s_series:     [{wood,fire,earth,metal,water}, ...] 稳态 s（Wuxing-FB 相对空间）
        theta_series: [{wood,fire,earth,metal,water}, ...] 逆转阈值 θ（动态）
        ages:         [age, ...] 每个点年龄（生命周期包络用）
        metal_series: [metal, ...] 金分量原始值（弹性调制，可选）
        el_factor:    el→有效弹性系数，默认 0.4+0.6el（[0.58, 1.0]）

    Returns:
        {drift_yy, yy_top, yy_bot, s_yang, s_yin,
         cap_yang, cap_yin, el_arr, yg_arr, yng_arr}
          drift_yy: 有符号阴阳偏移（正=阳偏↑ 负=阴偏↓）—— 实线
          yy_top:   +阴方向容量 × 弹性 × 阴生命周期（阴界，正值，在上）
          yy_bot:   −阳方向容量 × 弹性 × 阳生命周期（阳界，负值，在下）
          cap_yang/cap_yin: 逆转阈值最弱维容量（邪之所凑其气必虚）
    """
    n = len(s_series)
    if n == 0:
        return {'drift_yy': [], 'yy_top': [], 'yy_bot': [],
                's_yang': [], 's_yin': [], 'cap_yang': [], 'cap_yin': [],
                'el_arr': [], 'yg_arr': [], 'yng_arr': []}
    ef = el_factor or (lambda el: 0.4 + 0.6 * el)

    drift_yy, yy_top, yy_bot = [], [], []
    s_yang_list, s_yin_list = [], []
    cap_yang_list, cap_yin_list = [], []
    el_list, yg_list, yng_list = [], [], []

    for i in range(n):
        s = s_series[i] or {}
        th = theta_series[i] or {}
        age = ages[i] if i < len(ages) else 30

        # 阴阳投影（金不参与，SPUM 本体：金=边界调节器）
        s_yang = sum(w * s.get(d, 0.0) for d, w in YY_W_YANG.items())
        s_yin = sum(w * s.get(d, 0.0) for d, w in YY_W_YIN.items())

        # 区间容量 = 各方向最弱维逆转阈值（邪之所凑其气必虚）
        cap_yang = min(th.get('fire', 1.0), th.get('wood', 1.0))
        cap_yin = min(th.get('earth', 1.0), th.get('water', 1.0))

        # 金弹性（金形状态 → 区间有效宽度，不影响判定）
        if metal_series is not None and i < len(metal_series):
            el = metal_elasticity(float(metal_series[i] or 50.0))
        else:
            el = 1.0
        el_list.append(round(el, 3))

        # 生命周期包络（呈现层调制）
        yg = yang_growth_factor(age)
        yng = yin_growth_factor(age)
        yg_list.append(round(yg, 4))
        yng_list.append(round(yng, 4))

        yy_top.append(round(cap_yin * ef(el) * yng, 4))
        yy_bot.append(round(-cap_yang * ef(el) * yg, 4))
        drift_yy.append(round(s_yang - s_yin, 4))
        s_yang_list.append(round(s_yang, 4))
        s_yin_list.append(round(s_yin, 4))
        cap_yang_list.append(round(cap_yang, 4))
        cap_yin_list.append(round(cap_yin, 4))

    return {'drift_yy': drift_yy, 'yy_top': yy_top, 'yy_bot': yy_bot,
            's_yang': s_yang_list, 's_yin': s_yin_list,
            'cap_yang': cap_yang_list, 'cap_yin': cap_yin_list,
            'el_arr': el_list, 'yg_arr': yg_list, 'yng_arr': yng_list}


def build_year_view_v3(innate: dict, dayun: list, age_start: int = 0,
                       age_end: int = 80, birth_year: int = 1957,
                       events: Optional[list] = None,
                       interventions: Optional[list] = None) -> dict:
    """v3 终身推演 — 在 v2 基础上叠加 Wuxing-FB 旁路分析

    不替换 v2 输出结构，新增:
      - driftData_wuxing: 基于 Wuxing-FB s_i 的体质偏移曲线（平行 driftData）
      - tolerance_u_series: 逐年最弱方向 u*（青囊调平的量化目标）
      - zone_statuses: 逐年五维带状态
      - weak_virtual_series: 逐年虚实演化（用于调节视图 projected/actual 对比）

    interventions（2026-10-08 新增，调节视图 actual 使用）:
      [{'age': 40, 'dim': 'metal', 'strength': 0.8, ...}]
      age ≥ 指定年龄后，每年向 dim 维追加补虚注入 strength（调平干预）：
      虚维被正向拉起 → u* 抬升、CRIT/OUT 减少 → 与 projected（无干预）对比即"调平收益"。

    原 v2 三曲线 + stateFlags + health_score 全部保留（向后兼容）。
    """
    # 先跑 v2（保留全部原有输出）
    v2_result = build_year_view_v2(innate, dayun, age_start, age_end, birth_year, events)

    if not WUXING_FB_AVAILABLE:
        v2_result['algorithm'] = 'spum_computeHealthBounds_v2 (wuxing_fb 未加载)'
        return v2_result

    # Wuxing-FB 耦合矩阵（默认 β_s=0.60, β_k=0.40）
    A_mat = wx_build_A()

    # 先天向量 → 相对构型 → 势能基底（柔和映射，仅形状；无观测绝对水平）
    # 2026-10-10 口径统一：缺省 50.0 与 v2 HEALTH_CENTROID 一致（旧 20.0 使
    # 未传 innate 时 v3 rho0 与 v2 语义不同；to_relative 对中心不敏感但保持一致性）
    v_rel = wx_to_relative({d: float(innate.get(d, 50.0)) for d in WX_DIMS})
    rho0 = wx_rho0_from_rel(v_rel, equilibrium=1.0)

    # ── 注入标定（2026-10-08 修复）──────────────────────────────
    # 旧实现：dayun/liunian 输出 ±4~±10，被硬帽压到 ±2.0，未对标模型口径
    #         （u*≈2.79，u=2.0 已是强邪）→ zone 全 IN、无区分度。
    # 新实现：天时注入本征强度固定（U_PEAK_FIXED=2.0），方向保留、
    #         峰值归一 —— 健康者带内为主、虚弱者 CRIT/OUT 增多（同邪不同命）
    u_peak = U_PEAK_FIXED

    # 逐年注入（大运 + 流年） → 弛豫 → 取稳态
    driftData_wuxing = []
    tol_u_series = []
    zone_series = []
    weak_virtual_series = []
    s_series = []
    max_s_series = []

    # 串联弛豫：s 在逐年间传递（2026-10-09 新增）
    # 旧：每年龄独立弛豫（从 s=0 起）→ 仅反映"该年孤立注入"效果
    # 新：年龄 N 的 s 作为 N+1 的 s_start → 累积偏移 / 调平效应可传递
    #     每步 dt=DT(0.25)，每年龄弛豫 4 步 = 1 年（与 year-view 粒度匹配）
    cur_s = {d: 0.0 for d in WX_DIMS}

    for age in range(age_start, age_end + 1):
        # 获取该年大运偏移
        cur_dy = None
        for d in dayun:
            if d.get('start', 0) <= age < d.get('end', 100):
                cur_dy = d
                break
        if cur_dy is None and dayun:
            cur_dy = dayun[-1]

        # 大运注入
        dy_elems = ganzhi_to_elems(cur_dy.get('gan', '?'), cur_dy.get('zhi', '?'), wg=0.3, wz=0.7)
        # 流年注入
        year = birth_year + age
        ln = get_liunian(year)
        ln_delta = liunian_delta(ln['g'], ln['z'])

        # 合成注入向量 → 主维主导结构（2026-10-08 修复）
        # 旧：整体归一 + 硬帽 ±2.0 → 多维注入互相牵制（水涨船高），zone 全 IN。
        # 新：峰值维（|raw| 最大）保持 u_peak 本征强度，其余维按 0.4 弱化 →
        #     行为接近单维扫描，判别窗口（u* 单维定义）得以重现
        raw_inj = {}
        for d in WX_DIMS:
            raw_inj[d] = dy_elems.get(d, 0.0) * 0.3 + ln_delta.get(d, 0.0) * 0.7
        inj = _normalize_injection(raw_inj, u_peak, WX_DIMS)

        # 调平干预（actual 曲线）：修正 ρ₀ 基底（2026-10-08 v2 设计）
        # 补虚 = 增强虚维势能基底（ρ₀[dim] += strength，持久）→ 该维阻尼升、耐受升，
        # 区间变宽 —— 而非向虚维注入正 u（那只会把虚推成实，不改变 u*）。
        rho0_eff = rho0
        if interventions:
            for iv in interventions:
                if age >= int(iv.get('age', 999)):
                    dim = iv.get('dim')
                    if dim in WX_DIMS:
                        if rho0_eff is rho0:
                            rho0_eff = dict(rho0)
                        rho0_eff[dim] = min(wx_RHO_MAX, rho0_eff.get(dim, 1.0) + float(iv.get('strength', 1.2)))

        # 弛豫（用干预后的 rho0_eff 基底，从上一年 cur_s 串联）
        # 2026-10-09 修复：n_steps 4→12 —— 之前取"1年=4步"的未收敛准稳态，
        #   s 只到瞬态 ≈0.38，永远够不到阈值 0.7θ → zone 全 IN、体质无区分。
        #   steady_state 的语义是"弛豫取稳态"（复核脚本判别窗口即 12 步稳态，
        #   虚弱组 CRIT fin=0.61）；year-view 也应按稳态取，否则 B 修复的
        #   "同邪不同命"（健康带内为主、虚弱 CRIT/OUT 增多）在终身曲线上失效。
        ss = wx_steady_state(rho0_eff, inj, A_mat, n_steps=12, s_start=cur_s)
        cur_s = ss['s']  # 传递给下一年

        # 相对空间体质偏移（去 ×5 魔法数，量纲与 θ=1.0 一致）
        s_abs = [abs(ss['s'][d]) for d in WX_DIMS]
        s_mean = sum(s_abs) / len(WX_DIMS)
        driftData_wuxing.append(round(-s_mean, 3))
        s_series.append({d: round(ss['s'][d], 4) for d in WX_DIMS})
        max_s_series.append(round(-max(s_abs), 3))

        # 最弱方向 u*
        tol = ss['tolerance_u']
        min_d = min(tol, key=lambda k: tol[k])
        tol_u_series.append({
            'age': age,
            'tolerance_u_star': round(tol[min_d], 3),
            'weakest_dim': min_d,
            'all_u_star': {d: round(tol[d], 3) for d in WX_DIMS},
        })

        # zone
        zone_series.append({
            'age': age,
            'zone': ss['zone'],
            'theta': {d: round(ss['theta'][d], 3) for d in WX_DIMS},
        })

        # 虚实
        wv = ss['weak_virtual']
        weak_virtual_series.append({
            'age': age,
            '虚': wv.get('虚', []),
            '实': wv.get('实', []),
            '临界': wv.get('临界', []),
            '带内': wv.get('带内', []),
        })

    # 回写到 v2 结果（扩展而非替换）
    v2_result['algorithm'] = 'spum_computeHealthBounds_v3 + wuxing_fb_v1'
    v2_result['theory_source'] = 'Wuxing-FB 五形生克负反馈网络 β_s=0.60/β_k=0.40 (2026-10-08)'
    v2_result['wuxing_fb'] = {
        'available': True,
        'params': {
            'beta_s': wx_BS, 'beta_k': wx_BK,
            'theta0': 1.0, 'gamma': 0.6, 'dt': 0.25,
            'u_peak': u_peak,
        },
        'rho0': {d: round(rho0[d], 4) for d in WX_DIMS},
        'driftData_wuxing': driftData_wuxing,        # 相对空间 s 均值（−s_mean，量纲与 θ=1.0 一致）
        's_series': s_series,                        # 每维稳态 s（相对空间）
        's_mean_series': driftData_wuxing,           # 别名：五维 |s| 均值（负号=翻转对齐）
        'max_s_series': max_s_series,                # 五维 max|s|（当前最大偏移维，负号对齐）
        'tolerance_u_series': tol_u_series,          # 动态 u*（从当前状态起扫，随调平移动）
        'zone_series': zone_series,
        'weak_virtual_series': weak_virtual_series,
    }

    # ── 阴阳投影层（tizhi-curve 借鉴 · 2026-10-09）────────────────
    # 人生曲线主呈现：有符号阴阳偏移（实线）+ 逆转阈值阴阳区间（黄/红线）
    # 生命周期包络（0-16 阳盛 / 16-35 壮年 / 35+ 衰退）只调 2D 呈现宽度，
    # 不参与 5D 判定（zone_series 是唯一判定源）
    try:
        yy_ages = list(range(age_start, age_end + 1))[:len(s_series)]
        yy_theta = [zs['theta'] for zs in zone_series]
        yy_metal = [s.get('metal', 50.0) for s in s_series]
        v2_result['wuxing_fb']['yin_yang'] = build_yin_yang_projection(
            s_series, yy_theta, yy_ages, metal_series=yy_metal,
        )
    except Exception as _yy_e:
        logging.getLogger(__name__).warning(f"yin_yang projection failed: {_yy_e}")
        v2_result['wuxing_fb']['yin_yang'] = None
    return v2_result


def build_jieqi_view_v3(calendar_year: int, dayun_active_gz: dict,
                        liunian_gz: dict, jieqi_dates: list,
                        innate: Optional[dict] = None) -> dict:
    """节气视图 v3 — 在 v2 的 24 节气基础上叠加 Wuxing-FB 分析

    每帧节气 = 大运 + 流年 + 节气五行 bias 合成注入 → 弛豫 → 取稳态
    新增字段: tolerance_u*, zone, weak_virtual
    """
    # 先跑 v2（保留全部原有字段）
    v2 = build_jieqi_view_v2(calendar_year, dayun_active_gz, liunian_gz, jieqi_dates)

    if not WUXING_FB_AVAILABLE:
        v2['algorithm'] = 'jieqi_view_v2 (wuxing_fb 未加载)'
        return v2

    # 构造 rho0（如果给了 innate，用它；否则用均匀 1.0 基底）
    # 2026-10-10 口径统一：缺省 50.0 与 v2 HEALTH_CENTROID 一致
    if innate:
        v_rel = wx_to_relative({d: float(innate.get(d, 50.0)) for d in WX_DIMS})
        rho0 = wx_rho0_from_rel(v_rel, equilibrium=1.0)
    else:
        rho0 = {d: 1.0 for d in WX_DIMS}

    A_mat = wx_build_A()

    # ── 注入标定（2026-10-09 修复：节气视图让 bias 主导）─────────────
    # 节气 bias 量级 ±1.5，大运+流年 ±16 — bias 被完全淹没，24 帧无区分度。
    # 合成权重: dy×0.3 + ln×0.3 + bias×3.0 → bias 成为主导差异信号
    # （year-view 用 dy×0.3 + ln×0.7，区别在于 year-view 大运已按年切换）
    u_peak = U_PEAK_FIXED

    # ── 节气视图：串联弛豫（2026-10-09 新增）─────────────────────
    # 立春 → 雨水 → ... 大寒，s 状态在 24 节气间串联传递。
    # dt = 0.25（year-view 标准步长），每帧 4 步弛豫 = 1 年/帧。
    # 模型含义：每个节气节点代表 1 年的体质演化快照（节气注入×大运流年背景）。
    # 24 帧 × 1 年 = 24 年的体质演化浓缩到一个日历年的 24 个状态点。

    cur_s = {d: 0.0 for d in WX_DIMS}  # 初始 s（年初 = 中和）

    # 每帧节气跑 Wuxing-FB
    jieqi_v3 = []
    for jq in v2['jieqi']:
        # 注入 = 大运(弱背景) + 流年(弱背景) + 节气(主导) → 各帧有区分度
        raw_inj = {}
        for d in WX_DIMS:
            raw_inj[d] = (jq['dayun_impact'].get(d, 0) * 0.3 +
                         jq['liunian_impact'].get(d, 0) * 0.3 +
                         jq['wuxing_bias'].get(d, 0) * 3.0)
        inj = _normalize_injection(raw_inj, u_peak, WX_DIMS)

        # 串联弛豫：从上一节气的 s 起弛豫 4 步（dt=0.25 → 1 年/帧）
        ss = wx_steady_state(rho0, inj, A_mat, n_steps=4, s_start=cur_s)
        cur_s = ss['s']  # 传递给下一节气

        tol = ss['tolerance_u']
        min_d = min(tol, key=lambda k: tol[k])

        jq_out = dict(jq)  # copy v2 fields
        jq_out['tolerance_u'] = {d: round(tol[d], 3) for d in WX_DIMS}
        jq_out['min_tolerance'] = {'dim': min_d, 'u_star': round(tol[min_d], 3)}
        jq_out['zone'] = ss['zone']
        jq_out['weak_virtual'] = ss['weak_virtual']
        jq_out['s_wuxing'] = {d: round(ss['s'][d], 4) for d in WX_DIMS}
        jq_out['gap'] = {d: round(tol[d] - abs(ss['s'][d]), 3) for d in WX_DIMS}
        jieqi_v3.append(jq_out)

    v2['algorithm'] = 'jieqi_view_v3 + wuxing_fb_v1'
    v2['theory_source'] = 'Wuxing-FB β_s=0.60/β_k=0.40'
    v2['jieqi'] = jieqi_v3
    v2['rho0'] = {d: round(rho0[d], 4) for d in WX_DIMS}
    return v2
