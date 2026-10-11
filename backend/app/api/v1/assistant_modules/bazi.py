"""bazi - 八字推演：转发 qingmeng-engine + lunar_python 本地双规则兜底"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import httpx

from ....config import settings
from ....models import User
from ...deps import get_current_user

router = APIRouter()

class BaziIn(BaseModel):
    birth_date: str                              # "YYYY-MM-DD"
    birth_hour: str | None = None                # "寅时（3-5点）" / None
    birthplace: str | None = None                # 城市名
    birth_date_type: str | None = None           # "solar"(默认)/"lunar" — 前端阳历/阴历标识


@router.post("/reasoning/bazi")
async def reasoning_bazi(body: BaziIn,
                         current: User = Depends(get_current_user)):
    """八字推演 — 前端 onboarding 第一阶段用。
    优先调 qingmeng-engine，不可达时用 lunar_python 本地 fallback。"""
    # 1. 先调青檬引擎
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{settings.QINGMENG_URL}/v1/reasoning/bazi",
                json=body.model_dump(exclude_none=True),
            )
            if r.status_code == 200:
                data = r.json()
                data["proxied_from"] = settings.QINGMENG_URL
                return data
    except Exception:
        pass
    # 2. fallback: lunar_python 本地推演
    return _local_bazi_fallback(body)


def _compute_one_bazi_variant(solar) -> dict:
    """从 Solar 对象算一套八字 + v_innate（内部函数，供 fallback 双规则调用）。"""
    lunar = solar.getLunar()

    pillars = [
        lunar.getYearInGanZhiExact(),
        lunar.getMonthInGanZhiExact(),
        lunar.getDayInGanZhiExact(),
        lunar.getTimeInGanZhi(),
    ]
    gan_list = [
        lunar.getYearGanExact(),
        lunar.getMonthGanExact(),
        lunar.getDayGanExact(),
        lunar.getTimeGan(),
    ]
    zhi_list = [
        lunar.getYearZhiExact(),
        lunar.getMonthZhiExact(),
        lunar.getDayZhiExact(),
        lunar.getTimeZhi(),
    ]

    TIANGAN_WXING = {'甲': 'wood', '乙': 'wood', '丙': 'fire', '丁': 'fire',
                    '戊': 'earth', '己': 'earth', '庚': 'metal', '辛': 'metal',
                    '壬': 'water', '癸': 'water'}
    DIZHI_HIDDEN = {
        '子': [('water', 1.0)],
        '丑': [('earth', 0.6), ('metal', 0.3), ('water', 0.1)],
        '寅': [('wood', 0.6), ('fire', 0.3), ('earth', 0.1)],
        '卯': [('wood', 1.0)],
        '辰': [('earth', 0.5), ('wood', 0.3), ('water', 0.2)],
        '巳': [('fire', 0.6), ('metal', 0.3), ('earth', 0.1)],
        '午': [('fire', 0.7), ('earth', 0.3)],
        '未': [('earth', 0.6), ('fire', 0.3), ('wood', 0.1)],
        '申': [('metal', 0.5), ('water', 0.3), ('earth', 0.2)],
        '酉': [('metal', 1.0)],
        '戌': [('earth', 0.5), ('metal', 0.3), ('fire', 0.2)],
        '亥': [('water', 0.7), ('wood', 0.3)],
    }

    raw = {'wood': 0.0, 'fire': 0.0, 'earth': 0.0, 'metal': 0.0, 'water': 0.0}
    for i in range(4):
        raw[TIANGAN_WXING.get(gan_list[i], 'earth')] += 1.0
        for wx, pct in DIZHI_HIDDEN.get(zhi_list[i], [('earth', 1.0)]):
            raw[wx] += pct

    total = sum(raw.values()) or 1.0
    v_innate = {k: round(v / total * 100, 1) for k, v in raw.items()}

    DAY_GAN = gan_list[2]
    DAY_MASTER = TIANGAN_WXING.get(DAY_GAN, 'earth')

    try:
        lunar_cn = lunar.toString()
    except Exception:
        lunar_cn = ""

    return {
        "bazi": "/".join(pillars),
        "pillars": pillars,
        "ganzhi_day": pillars[2],
        "ganzhi_hour": pillars[3],
        "ganzhi_year": pillars[0],
        "ganzhi_month": pillars[1],
        "day_master": DAY_GAN,
        "day_master_element": DAY_MASTER,
        "v_innate": v_innate,
        "lunar_display": lunar_cn,
    }


def _local_bazi_fallback(body: BaziIn) -> dict:
    """lunar_python 本地八字推演 — 青檬引擎不可达时兜底。

    2026-10-04: 子时双规则同时保留，留作后期数据收敛：
      - default: lunar_python 默认（23:00 起算第二天，"现代排盘工具常用法"）
      - zi_same_day: 子时归当天（"传统子平法，多用于命理实战"）
    """
    from lunar_python import Solar, Lunar

    birth_date = body.birth_date
    birth_hour = body.birth_hour
    birth_date_type = body.birth_date_type or 'solar'

    parts = birth_date.split('-')
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])

    SHICHEN_HOUR = {
        '子时': 23, '丑时': 1, '寅时': 3, '卯时': 5, '辰时': 7, '巳时': 9,
        '午时': 11, '未时': 13, '申时': 15, '酉时': 17, '戌时': 19, '亥时': 21,
    }
    hour = 14
    is_zishi = False
    if birth_hour:
        for sc, h in SHICHEN_HOUR.items():
            if sc in birth_hour:
                hour = h
                is_zishi = (sc == '子时')
                break

    try:
        if birth_date_type == 'lunar':
            lunar = Lunar.fromYmdHms(y, m, d, hour, 0, 0)
            solar = lunar.getSolar()
        else:
            solar = Solar.fromYmdHms(y, m, d, hour, 0, 0)
    except Exception as e:
        return {
            "bazi": "未知", "pillars": ["?", "?", "?", "?"],
            "lunar_display": "", "true_solar_time": "", "longitude": 120.0,
            "v_innate": _DEFAULT_V_INNATE, "engine": "local_fallback_error",
            "message": f"日期解析失败: {e}",
            "day_master": None, "health_index": None,
        }

    # ── 默认规则（lunar_python 行为）──
    default = _compute_one_bazi_variant(solar)

    # ── 如果是子时，再算一套"子时归当天"规则 ──
    zi_same_day = None
    if is_zishi:
        # 子时归当天: 用当天 22:59 作为替代时辰点
        # lunar_python 里 22:59 仍属于当天的"亥时"日柱 → 日柱不变
        # 时柱会变成子时吗？不，22:59 是亥时。所以真正的"子时归当天"
        # 应该是: 把 hour 从 23 改成 0（当天的 0:00 是子时，日柱归当天）
        solar_same_day = Solar.fromYmdHms(y, m, d, 0, 0, 0)
        # 但这对于本来就是 birth_hour=子时(23) 的人来说，
        # solar_same_day 的日柱 = solar（子时归当天的当天），时柱 = 子时
        zi_same_day = _compute_one_bazi_variant(solar_same_day)

    # ── 其他辅助字段（只算一次就行）──
    try:
        lunar = default.get("_lunar_obj") or solar.getLunar()
        zodiac_year = lunar.getYearShengXiao()
        na_yin_year = lunar.getYearNaYin()
        na_yin_day = lunar.getDayNaYin()
    except Exception:
        zodiac_year = ""
        na_yin_year = ""
        na_yin_day = ""

    variants = {
        "default": {
            "desc": "子时归次日（现代排盘工具常用，lunar_python 默认）",
            **default,
        },
    }
    if zi_same_day:
        variants["zi_same_day"] = {
            "desc": "子时归当天（传统子平法，多用于命理实战）",
            **zi_same_day,
        }

    return {
        "bazi": default["bazi"],
        "pillars": default["pillars"],
        "ganzhi_year": default["ganzhi_year"],
        "ganzhi_month": default["ganzhi_month"],
        "ganzhi_day": default["ganzhi_day"],
        "ganzhi_hour": default["ganzhi_hour"],
        "lunar_display": default["lunar_display"],
        "zodiac_year": zodiac_year,
        "nayin_year": na_yin_year,
        "nayin_day": na_yin_day,
        "day_master": default["day_master"],
        "day_master_element": default["day_master_element"],
        "true_solar_time": "",
        "longitude": 120.0,
        "v_innate": default["v_innate"],
        "engine": "local_fallback",
        "message": "青檬引擎不可达，使用本地 lunar_python 推演",
        # ═══ 2026-10-04 新增：子时双规则变体（非子时则只有 default）═══
        "is_zishi": is_zishi,
        "bazi_variants": variants,
        "active_variant": "default",   # 当前使用默认规则，后期可切
    }


_DEFAULT_V_INNATE = {'wood': 20, 'fire': 20, 'earth': 20, 'metal': 20, 'water': 20}  # center=20 概率分布口径（总和=100）

