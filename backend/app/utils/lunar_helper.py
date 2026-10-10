"""大运排盘 — 封装 qingmeng_engine._vendor.lunar_python

为什么不是调 qingmeng-engine /reasoning/bazi：
  bazi 端点不返回 dayun，且大运顺逆需要 gender 参数。
  直接 import qingmeng_engine._vendor.lunar_python 排盘更干净。

Fallback: lunar_python 不可用（ImportError）时返回 []，
  让 trajectories/year-view 端点只走大运推演（无 dayun 也不 crash）。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
真太阳时校正（2026-10-08 新增 · SPUM 逐帧注入模型）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
出生时柱 = 北京时间时辰 + (birth_longitude - 120) × 4 分钟/度

例：乌鲁木齐 87.6°E
  北京时间 15:00 → 真太阳时 15:00 - 129.6 分钟 = 12:50
  时柱可能从「未时」(14-16) 变成「午时」(12-14)
  → 八字第四柱变了 → 起运时间变了 → 整条体质曲线的起点全错！
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
    _candidates = [
        r'e:\工作\qingmeng-engine',
        _os.path.join(_os.path.dirname(__file__), '..', '..', '..', 'qingmeng-engine'),
    ]
    for _c in _candidates:
        _c_norm = _os.path.abspath(_c)
        if _c_norm not in sys.path and _os.path.isdir(_c_norm):
            sys.path.insert(0, _c_norm)
            break
    from qingmeng_engine._vendor.lunar_python import Solar  # noqa: F401
    from qingmeng_engine._vendor.lunar_python.eightchar.DaYun import DaYun  # noqa: F401
    LUNAR_PYTHON_LOADED = True
    logger.info("lunar_python loaded OK")
except ImportError as e:
    logger.warning(f"lunar_python not available: {e}")


# ═══════════════════════════════════════════════════════════
# 真太阳时校正层
# ═══════════════════════════════════════════════════════════

# 时辰起点（24 小时制）：子=0 丑=2 寅=4 ... 亥=22
SHICHEN_STARTS = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]
SHICHEN_NAMES  = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']
# 24 节气名（固定顺序）
JIEQI_24 = [
    '立春','雨水','惊蛰','春分','清明','谷雨',
    '立夏','小满','芒种','夏至','小暑','大暑',
    '立秋','处暑','白露','秋分','寒露','霜降',
    '立冬','小雪','大雪','冬至','小寒','大寒',
]


def true_solar_adjust(birth_hour: Optional[str], birth_longitude: Optional[float]
                      ) -> tuple[int, int, float]:
    """北京时间出生时辰 → 真太阳时校正后的 (hour, day_offset, offset_min)

    Args:
        birth_hour:     "未时" | "未时（13-15点）" | "15" | None
        birth_longitude: 经度（东经为正；None 或 120 = 北京时间，不校正）

    Returns:
        (hour, day_offset, offset_min)
          hour:       真太阳时对应的时辰起点小时（0-23 的偶数）
          day_offset: 日期偏移（真太阳时跨过午夜 → -1 或 +1；正常为 0）
          offset_min: 真太阳时比北京时间早/晚多少分钟
    """
    beijing_hour = _parse_hour(birth_hour)

    if birth_longitude is None or abs(birth_longitude - 120.0) < 0.01:
        return beijing_hour, 0, 0.0  # 正好在 120°E，不校正

    # 经度差 → 时间差：每度 4 分钟
    offset_min = (birth_longitude - 120.0) * 4.0
    ts_hour = beijing_hour + offset_min / 60.0  # 真太阳时的小数值

    # 处理日期边界
    day_offset = 0
    if ts_hour < 0:
        ts_hour += 24
        day_offset = -1
    elif ts_hour >= 24:
        ts_hour -= 24
        day_offset = +1

    # 找到对应的时辰起点（偶数）
    hour = 0
    for s in SHICHEN_STARTS:
        if ts_hour >= s:
            hour = s

    return hour, day_offset, round(offset_min, 1)


def get_true_solar_hour(birth_date: str, birth_hour: Optional[str],
                        birth_longitude: Optional[float]) -> tuple[str, float]:
    """给前端展示用：返回 (真太阳时辰名, offset_min)

    Args:
        birth_date:  原出生日 YYYY-MM-DD（跨午夜时会返回校正后日期）
        birth_hour:  原北京时间出生时辰
        birth_longitude: 出生地经度

    Returns:
        (hour_str, offset_min)
          hour_str:   "午时 12:50+6" 格式（时辰+具体时刻+偏移）
          offset_min: 经度校正偏移量
    """
    beijing_hour = _parse_hour(birth_hour)
    if birth_longitude is None:
        sh_idx = beijing_hour // 2 if beijing_hour < 22 else 11
        return f"{SHICHEN_NAMES[sh_idx]}时", 0.0

    offset_min = round((birth_longitude - 120.0) * 4.0, 1)
    ts_hour = beijing_hour + offset_min / 60.0
    # 校正到 [0, 24)
    ts_hour = ts_hour % 24

    sh_idx = min(int(ts_hour // 2), 11)  # 0-11
    hour_str = f"{SHICHEN_NAMES[sh_idx]}时 {ts_hour:0.2f}"
    if offset_min != 0:
        hour_str += f"({offset_min:+.0f}min)"
    return hour_str, offset_min


def compute_dayun_with_location(birth_date: str, birth_hour: Optional[str],
                                gender: str, birth_longitude: Optional[float] = None,
                                n_da_yun: int = 10) -> list:
    """compute_dayun + 真太阳时校正层

    优先用这个函数（而非 compute_dayun），如果用户提供了 birth_longitude。
    """
    if not LUNAR_PYTHON_LOADED:
        return []
    try:
        from qingmeng_engine._vendor.lunar_python import Solar

        # birth_date: YYYY-MM-DD
        y, m, d = map(int, birth_date.split('-'))

        # ⭐ 关键校正：北京时间 → 真太阳时
        hour, day_offset, _ = true_solar_adjust(birth_hour, birth_longitude)
        if day_offset != 0:
            # 跨日了
            from datetime import date, timedelta
            real_date = date(y, m, d) + timedelta(days=day_offset)
            y, m, d = real_date.year, real_date.month, real_date.day

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
        logger.warning(f"compute_dayun_with_location 失败: {e}\n{traceback.format_exc()}")
        return []


# ═══════════════════════════════════════════════════════════
# 24 节气查询（给定阳历年 → 返回 24 个节气日期）
# ═══════════════════════════════════════════════════════════

def get_jieqi_dates(year: int) -> list:
    """返回某年 24 节气的日期列表 [YYYY-MM-DD, ...]（按 JIEQI_24 固定顺序）"""
    if not LUNAR_PYTHON_LOADED:
        return _fallback_jieqi(year)
    try:
        from qingmeng_engine._vendor.lunar_python import Lunar
        l = Lunar.fromYmd(year, 1, 1)
        table = l.getJieQiTable()
        # table 同时包含中文名和英文键名，中文名对应 Solar 对象
        result = []
        for name in JIEQI_24:
            s = table.get(name)
            if s and hasattr(s, 'toYmd'):
                result.append(s.toYmd())
            else:
                result.append(f"{year}-01-01")
        return result
    except Exception as e:
        logger.warning(f"get_jieqi_dates 失败: {e}")
        return _fallback_jieqi(year)


def _fallback_jieqi(year: int) -> list:
    """lunar_python 不可用时的简化 fallback（近似公历日期）
    用固定日期近似（精确到 ±1-2 天，仅供视觉展示）
    """
    # 简化近似：24 节气在公历上的大致日期
    approx_days = [
        '02-04', '02-19', '03-06', '03-21', '04-05', '04-20',  # 春
        '05-06', '05-21', '06-06', '06-21', '07-07', '07-23',  # 夏
        '08-07', '08-23', '09-08', '09-23', '10-08', '10-23',  # 秋
        '11-07', '11-22', '12-07', '12-22', '01-06', '01-20',  # 冬（最后两个跨到下一年 1 月）
    ]
    result = []
    for i, md in enumerate(approx_days):
        if i >= 22:  # 小寒/大寒是下一年 1 月
            result.append(f"{year + 1}-{md}")
        else:
            result.append(f"{year}-{md}")
    return result


# ═══════════════════════════════════════════════════════════
# 原始 compute_dayun（保留向后兼容，不带真太阳时校正）
# ═══════════════════════════════════════════════════════════

def compute_dayun(birth_date: str, birth_hour: Optional[str],
                  gender: str, n_da_yun: int = 10) -> list:
    """排大运 → [{gan, zhi, start, end, name}, ...]
    ⚠️ 此版本不带真太阳时校正，仅向后兼容。
       新代码请用 compute_dayun_with_location()。
    """
    return compute_dayun_with_location(
        birth_date, birth_hour, birth_longitude=None,
        gender=gender, n_da_yun=n_da_yun
    )


def _parse_hour(h) -> int:
    """birth_hour → 0-23"""
    if not h:
        return 12  # 正午 fallback
    h = str(h).strip()
    # 数字直给
    if h.isdigit():
        n = int(h)
        return max(0, min(23, n))
    # "未时（13-15点）" / "寅时" / "寅"
    for key, val in [('子',0),('丑',2),('寅',4),('卯',6),('辰',8),('巳',10),
                     ('午',12),('未',14),('申',16),('酉',18),('戌',20),('亥',22)]:
        if key in h:
            return val
    return 12
