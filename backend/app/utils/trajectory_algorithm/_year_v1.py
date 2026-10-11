"""_year_v1 - 终身推演 v1：build_year_view（先天 + 大运 + 流年 + 事件 → 三曲线）"""
from __future__ import annotations
import math
from typing import Optional

from ._constants import DIMS
from ._ganzhi import ganzhi_to_elems, elems_to_delta, get_liunian, liunian_delta, smooth5
from ._basic import compute_health_bounds

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

    # Phase 2: 流年干支 → 五行增量 → 5年平滑消锯齿
    raw_liunian = []
    for age in range(age_start, age_end + 1):
        year = birth_year + age
        ln = get_liunian(year)
        raw_liunian.append(liunian_delta(ln['g'], ln['z']))
    smooth_liunian = smooth5(raw_liunian)

    # Phase 3: 合成五行向量（先天 + 大运 + 流年 + 衰老 + 事件）
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
        # 流年偏移（5年平滑，消锯齿）
        for k in DIMS:
            v[k] += smooth_liunian[i][k]
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
