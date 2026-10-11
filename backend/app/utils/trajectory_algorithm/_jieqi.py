"""_jieqi - 24 节气视图 v2：节气五行 bias 合成大运流年注入"""
from __future__ import annotations

from ._constants import JIEQI_NAMES, JIEQI_WUXING_BIAS, JIEQI_MAIN_WX, DIMS
from ._ganzhi import ganzhi_to_elems, elems_to_delta

def build_jieqi_view_v2(calendar_year: int, dayun_active_gz: dict, liunian_gz: dict,
                        jieqi_dates: list) -> dict:
    """某年 × 24 节气 的五行属性视图（SPUM 逐帧注入中层）

    Args:
        calendar_year: 公历年份（如 2020）
        dayun_active_gz: 该年所在大运干支 {'gan':'己', 'zhi':'卯'}
        liunian_gz: 该年流年干支 {'g':'庚', 'z':'午'}
        jieqi_dates: 24 节气日期列表 [YYYY-MM-DD, ...]（lunar_python 精确计算）

    Returns:
        { jieqi: [{idx, name, date, month_day, wuxing_main, wuxing_bias, liunian_impact, dayun_impact}, ...],
          liunian_delta: {wood,fire,earth,metal,water},
          dayun_delta:   {wood,fire,earth,metal,water} }
    """
    # ⭐ 大运 impact：strength=22（十年层，天时推力大）
    dayun_delta_obj = elems_to_delta(
        ganzhi_to_elems(dayun_active_gz.get('gan','?'), dayun_active_gz.get('zhi','?'), wg=0.3, wz=0.7),
        strength=22,
    )
    # ⭐ 流年 impact：strength=6（年层，中等扰动）
    liunian_delta_obj = elems_to_delta(
        ganzhi_to_elems(liunian_gz.get('g','?'), liunian_gz.get('z','?'), wg=0.3, wz=0.7),
        strength=6,
    )

    jieqi = []
    for i, name in enumerate(JIEQI_NAMES):
        bias = JIEQI_WUXING_BIAS.get(name, {k:0 for k in DIMS})
        jieqi.append({
            'idx': i,
            'name': name,
            'date': jieqi_dates[i] if i < len(jieqi_dates) else f"{calendar_year}-01-01",
            'month_day': jieqi_dates[i][5:] if i < len(jieqi_dates) else '01-01',
            'wuxing_main': JIEQI_MAIN_WX.get(name, 'wood'),
            'wuxing_bias': bias,
            'liunian_impact': {k: round(liunian_delta_obj.get(k, 0), 2) for k in DIMS},
            'dayun_impact': {k: round(dayun_delta_obj.get(k, 0), 2) for k in DIMS},
        })

    return {
        'jieqi': jieqi,
        'liunian_delta': {k: round(liunian_delta_obj.get(k, 0), 2) for k in DIMS},
        'dayun_delta':   {k: round(dayun_delta_obj.get(k, 0), 2) for k in DIMS},
    }
