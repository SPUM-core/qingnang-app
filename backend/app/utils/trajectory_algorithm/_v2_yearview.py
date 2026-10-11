"""_v2_yearview - SPUM v2 终身推演：build_year_view_v2"""
from __future__ import annotations
import math
from typing import Optional

from ._constants import DIMS, DV_DT_MAX
from ._ganzhi import (
    ganzhi_to_elems, elems_to_delta, get_liunian, liunian_delta,
    smooth5, ganzhi_main_elem,
)
from ._basic import compute_health_bounds
from ._v2_bounds import compute_health_bounds_v2
from ._year_v1 import _smoothstep

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

    # Phase 2: 流年干支 → 五行增量 → 5年平滑消锯齿
    raw_liunian = []
    for age in range(age_start, age_end + 1):
        year = birth_year + age
        ln = get_liunian(year)
        raw_liunian.append(liunian_delta(ln['g'], ln['z']))
    smooth_liunian = smooth5(raw_liunian)

    # Phase 3: 逐年推演五行向量（注入 dv/dt 约束 + 流年平滑）
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
        # 流年偏移（5年平滑）
        for k in DIMS:
            v[k] += smooth_liunian[i][k]
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
        year = birth_year + age
        ln = get_liunian(year)
        elems.append({
            'age': age,
            'day': age * 365,
            't': f"{year}·{age}岁·{dy_info.get('name', '?')}",
            'dayun': dy_info.get('name', '?'),
            'liunian': ln['g'] + ln['z'],
            'liunian_elem': ganzhi_main_elem(ln['g'], ln['z']),
            **v,
        })

    # v2 完整分析
    bounds_v2 = compute_health_bounds_v2(elems, innate)
    # v1 兼容输出（同时计算 v1 以保持回归基准）
    bounds_v1 = compute_health_bounds(elems, innate)

    return {
        'view_mode': 'year',
        'algorithm': 'spum_computeHealthBounds_v2',
        'theory_source': 'SPUM2611 + 青囊中医总纲 + tizhi-curve沙盒(流年+平滑)',
        'v_innate': innate,
        'dayun': dayun,
        'dayunMarkArea': [
            {'start_age': d['start'], 'end_age': d['end'],
             'name': d.get('name', ''), 'gan': d.get('gan', ''), 'zhi': d.get('zhi', '')}
            for d in dayun
        ],
        'elems': elems,
        # v2 三曲线（统一用 v2 结果，v1 仅作回归基准）
        'driftData': bounds_v2['driftData'],
        'yinTop': bounds_v2['yinTop'],
        'yangBot': bounds_v2['yangBot'],
        'diseaseModes': bounds_v2['diseaseModes'],
        'elArr': bounds_v2['elArr'],
        # v2 新增：三态 + 尖峰 + 自适应参数（tizhi-curve 沙盒核心判定）
        'stateFlags': bounds_v2['stateFlags'],
        'spikeUp': bounds_v2['spikeUp'],
        'spikeDown': bounds_v2['spikeDown'],
        # 2026-10-10 新增：5D 触边尖峰 + 弹回子类型 + 速度/方向 + S₀ 中心化漂移
        'spikeUp5d': bounds_v2['spikeUp5d'],
        'spikeDown5d': bounds_v2['spikeDown5d'],
        'reboundUp': bounds_v2['reboundUp'],
        'reboundDown': bounds_v2['reboundDown'],
        'velocity': bounds_v2['velocity'],
        'direction': bounds_v2['direction'],
        'driftCentered': bounds_v2['driftCentered'],
        'centroidBias': bounds_v2['centroidBias'],
        'adaptiveParams': bounds_v2['adaptiveParams'],
        # v2 深层分析（S 向量 / σ / 凸多面体 margin）
        'S_vectors': bounds_v2['S_vectors'],
        'sigma_trend': bounds_v2['sigma_trend'],
        'polytope_statuses': bounds_v2['polytope_statuses'],
        'violation_depths': bounds_v2['violation_depths'],
        'frame_residues': bounds_v2['frame_residues'],
        'health_score': bounds_v2['health_score'],
    }

