"""大运排盘 — 封装 qingmeng_engine._vendor.lunar_python

为什么不是调 qingmeng-engine /reasoning/bazi：
  bazi 端点不返回 dayun，且大运顺逆需要 gender 参数。
  直接 import qingmeng_engine._vendor.lunar_python 排盘更干净。

Fallback: lunar_python 不可用（ImportError）时返回 []，
  让 trajectories/year-view 端点只走大运推演（无 dayun 也不 crash）。
"""
from __future__ import annotations
import sys
import logging
from typing import Optional

logger = logging.getLogger("qingnang.lunar_helper")

# ── 1. sys.path hack（一次性，模块级）──
LUNAR_PYTHON_LOADED = False
try:
    import os as _os
    # 尝试多种 qingmeng-engine 路径
    _candidates = [
        r'e:\工作\qingmeng-engine',                          # 绝对路径
        _os.path.join(_os.path.dirname(__file__), '..', '..', '..', 'qingmeng-engine'),
    ]
    for _c in _candidates:
        _c_norm = _os.path.abspath(_c)
        if _c_norm not in sys.path and _os.path.isdir(_c_norm):
            sys.path.insert(0, _c_norm)
            break
    # import
    from qingmeng_engine._vendor.lunar_python import Solar  # noqa: F401
    from qingmeng_engine._vendor.lunar_python.eightchar.DaYun import DaYun  # noqa: F401
    LUNAR_PYTHON_LOADED = True
    logger.info("lunar_python loaded OK")
except ImportError as e:
    logger.warning(f"lunar_python not available: {e}")


def compute_dayun(birth_date: str, birth_hour: Optional[str],
                  gender: str, n_da_yun: int = 10) -> list:
    """排大运 → [{gan, zhi, start, end, name}, ...]

    Args:
        birth_date: "1986-08-02" 阳历
        birth_hour: "寅时" | "03" | "3" | None
        gender: "male" | "female"
        n_da_yun: 返回几段大运（默认 10）

    Returns:
        list[dict]  每段包含 gan/zhi/start/end/name/elem
        []          lunar_python 不可用时
    """
    if not LUNAR_PYTHON_LOADED:
        return []
    try:
        from qingmeng_engine._vendor.lunar_python import Solar

        # birth_date: YYYY-MM-DD
        y, m, d = map(int, birth_date.split('-'))

        # birth_hour → hour
        hour = _parse_hour(birth_hour)

        # gender → lunar_python 1=男 0=女
        g_code = 1 if gender == 'male' else 0

        solar = Solar.fromYmdHms(y, m, d, hour, 0, 0)
        lunar = solar.getLunar()
        ec = lunar.getEightChar()
        yun = ec.getYun(n_da_yun, g_code)
        dys = yun.getDaYun()

        result = []
        for dy in dys[:n_da_yun]:
            ganzhi = dy.getGanZhi() or ''
            gan = ganzhi[0] if len(ganzhi) > 0 else ''
            zhi = ganzhi[1] if len(ganzhi) > 1 else ''
            result.append({
                'gan': gan or '?',
                'zhi': zhi or '?',
                'name': ganzhi or f'起运',
                'start': dy.getStartAge(),
                'end': dy.getEndAge(),
                'start_year': dy.getStartYear(),
                'end_year': dy.getEndYear(),
            })
        return result
    except Exception as e:
        import traceback
        logger.warning(f"compute_dayun 失败: {e}\n{traceback.format_exc()}")
        return []


def _parse_hour(h) -> int:
    """birth_hour → 0-23"""
    if not h:
        return 12  # 正午 fallback
    h = str(h).strip()
    # 数字直给
    if h.isdigit():
        n = int(h)
        return max(0, min(23, n))
    # "寅时" / "寅"
    SHICHEN_MAP = {
        '子': 0, '丑': 2, '寅': 4, '卯': 6,
        '辰': 8, '巳': 10, '午': 12, '未': 14,
        '申': 16, '酉': 18, '戌': 20, '亥': 22,
    }
    for key, val in SHICHEN_MAP.items():
        if key in h:
            return val
    return 12
