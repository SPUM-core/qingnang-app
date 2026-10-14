"""spacetime — 青囊时空引擎 API

核心理念：生活建议必须结合时空变量
  - 不能只说"你土形弱→补土"
  - 要说"今日卯月卯日木旺克土，此时猛补土虚不受补，宜疏肝为先，申时金旺时再健脾"

三个端点：
  GET  /spacetime/context          — 时空上下文（四柱/旺相/建除/节气）
  POST /spacetime/tiao-hou         — 调候引擎（时空×体质→动态建议）
  GET  /spacetime/daily-brief      — 一站式 daily_brief（推荐接入点）
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from ...database import get_db
from ...models import User, Case
from ...utils.spacetime_engine import (
    spacetime_context, tiao_hou_engine, spacetime_advice, spacetime_daily_brief,
    WUXING_CN, TIANGAN, DIZHI,
)
from ..deps import get_current_user

router = APIRouter()


# ═══════════════════════════════════════════════════════════
# 三元五腊圣诞 —— 农历固定日期的道教/民俗节日
# 键: (农历月, 农历日)  值: 节日名
# 来源: 《云笈七签》卷三十七 + 《协纪辨方》 + 民间岁时传统
# ═══════════════════════════════════════════════════════════
LUNAR_FESTIVALS: dict[tuple[int, int], str] = {
    # ── 正月 ──
    (1, 1):  "天腊·春节",
    (1, 2):  "天孙诞",
    (1, 3):  "天庆节",
    (1, 5):  "迎财神",
    (1, 6):  "定光佛诞",
    (1, 7):  "人日",
    (1, 8):  "谷日·五殿阎王诞",
    (1, 9):  "玉皇大帝圣诞",
    (1, 10): "地日",
    (1, 11): "天仓节",
    (1, 15): "上元节·三官大帝圣诞",       # 三元之上元
    (1, 16): "伏龙登山",
    (1, 19): "丘处机诞",
    (1, 20): "女真诞",
    (1, 25): "填仓节",
    (1, 27): "九毒日",
    (1, 28): "诸星下界",
    (1, 29): "蛇节",
    (1, 30): "天妃升天",
    # ── 二月 ──
    (2, 1):  "太阳升日",
    (2, 2):  "龙抬头·土地公诞",
    (2, 8):  "芳春节·四明王诞",
    (2, 9):  "中春会",
    (2, 10): "花朝节·牡丹花诞",
    (2, 12): "花朝节",
    (2, 14): "春龙节",
    (2, 15): "太上老君圣诞",
    (2, 18): "四圣诞",
    (2, 19): "观世音菩萨圣诞",
    (2, 21): "普贤菩萨诞",
    (2, 25): "花朝节",
    (2, 28): "老会",
    # ── 三月 ──
    (3, 1):  "二殿楚江王诞",
    (3, 3):  "上巳节·真武大帝圣诞",
    (3, 4):  "二殿楚江王诞",
    (3, 5):  "大禹诞",
    (3, 7):  "建星生日",
    (3, 8):  "六殿卞城王诞",
    (3, 12): "五殿阎罗王诞",
    (3, 13): "白龙会",
    (3, 15): "五方财神诞",
    (3, 16): "准提菩萨诞",
    (3, 18): "中岳大帝诞·后土娘娘诞",
    (3, 19): "太阳神君诞",
    (3, 20): "子孙娘娘诞",
    (3, 23): "妈祖·天后娘娘圣诞",
    (3, 27): "七殿泰山王诞",
    (3, 28): "东岳大帝诞辰",
    # ── 四月 ──
    (4, 1):  "八殿都市王诞",
    (4, 3):  "九天玄女诞",
    (4, 4):  "北斗星神诞",
    (4, 8):  "浴佛节·释迦牟尼圣诞",
    (4, 10): "狄梁公诞",
    (4, 12): "八殿都市王诞",
    (4, 14): "吕洞宾纯阳祖师圣诞",
    (4, 16): "神诞",
    (4, 17): "金花诞",
    (4, 18): "华佗祖师圣诞",
    (4, 20): "山东天齐诞",
    (4, 25): "武安王诞",
    (4, 28): "药王诞",
    # ── 五月 ──
    (5, 1):  "南极长生大帝诞",
    (5, 2):  "十二殿转轮王诞",
    (5, 5):  "地腊·端午节",
    (5, 8):  "北方五道诞",
    (5, 11): "天下都城隍诞",
    (5, 12): "丙戌日",
    (5, 13): "关帝圣诞",
    (5, 16): "九毒日",
    (5, 17): "九毒日",
    (5, 18): "张天师诞",
    (5, 20): "九毒日",
    (5, 22): "九毒日",
    (5, 27): "九毒日",
    (5, 28): "九毒日",
    (5, 30): "九毒日",
    # ── 六月 ──
    (6, 1):  "南赡部洲转大法轮",
    (6, 2):  "护国灵王诞",
    (6, 3):  "韦驮菩萨诞",
    (6, 4):  "南帝诞",
    (6, 6):  "晒衣节·天贶节",
    (6, 10): "海蟾诞",
    (6, 11): "田都元帅诞",
    (6, 13): "井泉龙王诞",
    (6, 15): "王灵官诞",
    (6, 19): "观音菩萨成道",
    (6, 20): "天地水三官圣诞",
    (6, 23): "火神诞",
    (6, 24): "关帝显圣·二郎神诞",
    (6, 26): "土地公诞",
    (6, 29): "彭祖祖诞",
    # ── 七月 ──
    (7, 1):  "七星娘娘诞",
    (7, 3):  "太阴星君诞",
    (7, 7):  "道德腊·七夕",
    (7, 8):  "将军诞",
    (7, 10): "十殿转轮王诞",
    (7, 13): "大势至菩萨诞",
    (7, 15): "中元节·中元地官赦罪",      # 三元之中元
    (7, 18): "西王母·王母娘娘圣诞",
    (7, 22): "财帛星君诞·增福财神诞",
    (7, 23): "天昌诞",
    (7, 25): "二郎真君诞",
    (7, 29): "地藏菩萨诞",
    # ── 八月 ──
    (8, 1):  "天医诞·许真君诞",
    (8, 5):  "雷声大帝诞",
    (8, 10): "北斗星君诞",
    (8, 15): "中秋节·太阴星君诞",
    (8, 16): "钟馗诞",
    (8, 18): "九天玄女诞",
    (8, 22): "燃灯佛诞",
    (8, 23): "汉钟离诞",
    # ── 九月 ──
    (9, 1):  "南斗星君诞",
    (9, 3):  "五瘟神诞",
    (9, 9):  "重阳节·斗姆元君圣诞",
    (9, 11): "土地公诞",
    (9, 15): "至圣先师诞",
    (9, 16): "伯益诞",
    (9, 17): "金龙四大王诞",
    (9, 18): "仓圣诞",
    (9, 19): "观音菩萨出家日",
    (9, 28): "马王爷诞",
    (9, 30): "药师佛诞",
    # ── 十月 ──
    (10, 1): "民岁腊·寒衣节",
    (10, 5): "达摩祖师诞",
    (10, 8): "桓景诞",
    (10, 10): "张果老诞",
    (10, 11): "四天王巡行",
    (10, 15): "下元节·下元水官解厄",     # 三元之下元
    (10, 24): "送寒衣",
    (10, 27): "北极紫微大帝诞",
    # ── 十一月 ──
    (11, 11): "太乙救苦天尊圣诞",
    (11, 17): "阿弥陀佛诞",
    (11, 19): "九华山金乔觉圣诞",
    # ── 十二月 ──
    (12, 1): "新下界",
    (12, 4): "北斗星下降",
    (12, 5): "西岳大帝诞",
    (12, 7): "真武牙将诞",
    (12, 8): "侯王腊·腊八节",
    (12, 16): "南岳大帝诞",
    (12, 19): "太阳星君诞",
    (12, 20): "鲁班诞",
    (12, 22): "冬至·玉清元始天尊诞",
    (12, 23): "祭灶（北方）",
    (12, 24): "祭灶（南方）",
    (12, 25): "玉帝巡天·孙真人诞",
    (12, 29): "华严菩萨诞",
    (12, 30): "除夕·紫姑神诞",
}


class TiaoHouIn(BaseModel):
    v_base: dict[str, float]
    datetime: Optional[str] = None       # ISO 格式，不传用当前时间
    birthplace: Optional[str] = None


# ═══════════════════════════════════════════════════════════
# 1. 时空上下文（公开接口，不鉴权也能算）
# ═══════════════════════════════════════════════════════════
@router.get("/context")
def get_spacetime_context(
    ts: Optional[str] = Query(None, description="ISO 格式时间，不传用当前时间"),
    birthplace: Optional[str] = Query(None),
    longitude: Optional[float] = Query(None, description="出生地经度（东经为正；None=北京时间）"),
):
    """返回指定时间点的完整时空上下文"""
    try:
        dt = datetime.fromisoformat(ts) if ts else datetime.now()
    except ValueError:
        raise HTTPException(400, "ts 必须是 ISO 格式时间")

    ctx = spacetime_context(dt, birthplace)

    # 真太阳时校正：经度 → 分钟偏移
    offset_min = (longitude - 120.0) * 4.0 if longitude is not None else 0.0
    dt_solar = dt + timedelta(minutes=offset_min) if offset_min else dt

    # 农历月日 + 时辰名（用真太阳时）
    try:
        try:
            import lunar_python
            Solar = lunar_python.Solar
        except ImportError:
            from qingmeng_engine._vendor.lunar_python import Solar
        _s = Solar.fromYmdHms(dt_solar.year, dt_solar.month, dt_solar.day, dt_solar.hour, dt_solar.minute, dt_solar.second)
        _l = _s.getLunar()
        lunar_month = _l.getMonthInChinese()
        lunar_day = _l.getDayInChinese()
        # 时辰名：真太阳时对应的时柱地支
        hour_name = _l.getTimeInGanZhi()[-1] + '时'
    except Exception:
        lunar_month = lunar_day = hour_name = None

    return {
        "datetime": dt.isoformat(),
        "sizhu": ctx['sizhu'],
        "lingshou": {
            "ganzhi": ctx['lingshou_gz'],
            "wuxing": ctx['lingshou'],
            "cn": WUXING_CN.get(ctx['lingshou'], ctx['lingshou']),
        },
        "wuxing_status": ctx['wuxing_status'],
        "wuxing_weight": ctx['wuxing_weight'],
        "jianchu": ctx['jianchu'],
        "jianchu_advice": ctx['jianchu_advice'],
        "jieqi": ctx['jieqi'],
        "day": {"gan": ctx['day_gan'], "zhi": ctx['day_zhi'], "gz": ctx['day_gz']},
        "hour_gz": ctx['sizhu']['hour'],
        "lunar_month": lunar_month,
        "lunar_day": lunar_day,
        "hour_name": hour_name,
        "solar_offset_min": round(offset_min, 1),   # 真太阳时校正偏移量（分钟）
        "is_degraded": ctx.get('is_degraded', False),
    }


# ═══════════════════════════════════════════════════════════
# 2. 调候引擎（需要 v_base）
# ═══════════════════════════════════════════════════════════
@router.post("/tiao-hou")
def run_tiao_hou(body: TiaoHouIn):
    """纯调候引擎 — 给定 v_base + 时间 → 返回动态调候建议
    
    不依赖后端用户数据，前端也可以自己算。
    """
    try:
        dt = datetime.fromisoformat(body.datetime) if body.datetime else datetime.now()
    except ValueError:
        raise HTTPException(400, "datetime 必须是 ISO 格式")

    ctx = spacetime_context(dt, body.birthplace)
    th = tiao_hou_engine(body.v_base, ctx)
    return {
        "context": {
            "lingshou": WUXING_CN.get(ctx['lingshou'], ctx['lingshou']),
            "wuxing_status": ctx['wuxing_status'],
            "jianchu": ctx['jianchu'],
            "jieqi": ctx['jieqi'].get('current_term', ''),
        },
        "priorities": th['priorities'],
        "avoid_now": th['avoid_now'],
        "opportunities": th['opportunities'],
        "window_tips": th['window_tips'],
        "summary": th['summary'],
    }


# ═══════════════════════════════════════════════════════════
# 3. ⭐ 一站式 daily_brief（推荐接入点，带鉴权自动拉 v_base）
# ═══════════════════════════════════════════════════════════
@router.get("/daily-brief")
def spacetime_daily_brief_endpoint(
    ts: Optional[str] = Query(None, description="ISO 格式时间，不传用当前时间"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """时空调候版 daily_brief — 替换原有的"静态补偏"建议
    
    调用链：
      1. 从用户档案拉 v_base
      2. 计算时空上下文（四柱/旺相/建除/节气）
      3. 调候引擎（时空 × 体质 → 动态建议）
      4. 返回完整建议 + 时空上下文（供前端渲染）
    
    Returns:
      {
        ctx: { sizhu, lingshou, wuxing_status, jianchu, jieqi },
        tiao_hou: { priorities, avoid_now, opportunities, summary },
        advice: { todos, avoidances, spacetime_summary },
      }
    """
    # 1. 拉用户 v_base
    case = db.query(Case).filter(Case.user_id == current.id).first()
    v_base = case.v_baseline if case else {"wood": 50, "fire": 50, "earth": 50, "metal": 50, "water": 50}

    # 2. 算时间
    try:
        dt = datetime.fromisoformat(ts) if ts else datetime.now()
    except ValueError:
        raise HTTPException(400, "ts 必须是 ISO 格式")

    # 3. 一站式调候
    result = spacetime_daily_brief(v_base, dt, birthplace=None)

    # 3.5 补上农历月日 + 时辰名（真太阳时校正 HeroCard/Dashboard 用）
    try:
        try:
            import lunar_python
            Solar = lunar_python.Solar
        except ImportError:
            from qingmeng_engine._vendor.lunar_python import Solar
        # 真太阳时校正
        _lon = getattr(current, 'birth_longitude', None)
        _off = (_lon - 120.0) * 4.0 if _lon else 0.0
        _dt_solar = dt + timedelta(minutes=_off) if _off else dt
        _s = Solar.fromYmdHms(_dt_solar.year, _dt_solar.month, _dt_solar.day, _dt_solar.hour, _dt_solar.minute, _dt_solar.second)
        _l = _s.getLunar()
        result['ctx']['lunar_month'] = _l.getMonthInChinese()
        result['ctx']['lunar_day'] = _l.getDayInChinese()
        result['ctx']['hour_name'] = _l.getTimeInGanZhi()[-1] + '时'
        result['ctx']['solar_offset_min'] = round(_off, 1)
    except Exception:
        pass

    # 4. 补上用户信息
    result['user'] = {
        'qingnang_id': current.qingnang_id,
        'nickname': current.nickname,
        'has_case': case is not None,
    }
    result['datetime'] = dt.isoformat()

    return result


# ═══════════════════════════════════════════════════════════
# 4. 静态参考表（前端渲染用，纯元数据）
# ═══════════════════════════════════════════════════════════
@router.get("/reference")
def spacetime_reference():
    """返回时空引擎的静态参考表（前端渲染用）"""
    return {
        "tiangan": TIANGAN,
        "dizhi": DIZHI,
        "wuxing_names": WUXING_CN,
        "shengsheng": {
            "木": "火", "火": "土", "土": "金", "金": "水", "水": "木",
        },
        "ke克": {
            "木": "土", "土": "水", "水": "火", "火": "金", "金": "木",
        },
        "status_wuxing": {
            "旺": "当令", "相": "我生", "休": "生我", "囚": "我克", "死": "克我",
        },
        "jianchu_good": {
            "除": "除旧迎新", "满": "祭祀祈福", "定": "安床",
            "执": "捕捉", "成": "开市", "开": "出行求财",
        },
        "jianchu_bad": {
            "建": "动土", "破": "诸事不宜", "危": "登高",
            "收": "出行", "闭": "开市",
        },
    }


# ═══════════════════════════════════════════════════════════
# 5. ⭐ 月历数据（前端日历渲染用）
# ═══════════════════════════════════════════════════════════
@router.get("/monthly")
def spacetime_monthly(
    year: int = Query(..., description="阳历年，如 2026"),
    month: int = Query(..., description="阳历月 1-12"),
):
    """返回某月每天的农历日、节气、建除——给前端日历格子渲染
    
    每月缓存友好：同一天返回的农历/节气/建除永远一样。
    Fallback: lunar_python 不可用时返回空 lunar/jieqi 字段。
    """
    try:
        import lunar_python
        Solar, Lunar = lunar_python.Solar, lunar_python.Lunar
    except ImportError:
        try:
            from qingmeng_engine._vendor.lunar_python import Solar, Lunar
        except ImportError:
            return {"year": year, "month": month, "days": [], "source": "fallback"}

    try:
        # 构造月内每一天
        first = Solar.fromYmd(year, month, 1)
        # 下个月第一天
        if month == 12:
            next_first = Solar.fromYmd(year + 1, 1, 1)
        else:
            next_first = Solar.fromYmd(year, month + 1, 1)

        days = []
        cur = first
        while cur.getYear() < next_first.getYear() or cur.getMonth() < next_first.getMonth() or cur.getDay() < next_first.getDay():
            l = cur.getLunar()
            # 农历显示：初一显示月份（如"九月"），十五显示"十五"，其余显示日期（如"初四"）
            lunar_day_cn = l.getDayInChinese()    # 初四 / 初一 / 十五
            if lunar_day_cn == '初一':
                lunar_display = l.getMonthInChinese() + '月'   # 九月
            else:
                lunar_display = lunar_day_cn
            # 节气：getNextJieQi() / getPrevJieQi() 返回 JieQi 对象，内部 Solar 用 .getSolar()
            jieqi = None
            for qname, qobj in [('next', l.getNextJieQi()), ('prev', l.getPrevJieQi())]:
                try:
                    if qobj and qobj.getSolar():
                        qs = qobj.getSolar()
                        if qs.getYear() == year and qs.getMonth() == month and qs.getDay() == cur.getDay():
                            jieqi = qobj.getName()
                            break
                except Exception:
                    pass

            # 三元五腊/圣诞（查农历月日字典）
            festival = LUNAR_FESTIVALS.get((l.getMonth(), l.getDay()))

            days.append({
                "day": cur.getDay(),
                "lunar": lunar_display,
                "lunar_month": l.getMonthInChinese(),
                "lunar_day": lunar_day_cn,
                "jieqi": jieqi,
                "festival": festival,
                "jianchu": l.getZhiXing(),  # 建除十二神
                "ganzhi_day": l.getDayInGanZhi(),
                "ganzhi_year": l.getYearInGanZhi(),
                "ganzhi_month": l.getMonthInGanZhi(),
            })
            # 下一天
            from datetime import date, timedelta
            y, m, d = cur.getYear(), cur.getMonth(), cur.getDay()
            next_date = date(y, m, d) + timedelta(days=1)
            cur = Solar.fromYmd(next_date.year, next_date.month, next_date.day)

        return {"year": year, "month": month, "days": days, "source": "lunar_python"}
    except Exception as e:
        import logging
        logging.getLogger("qingnang.spacetime").warning(f"spacetime_monthly 失败: {e}")
        return {"year": year, "month": month, "days": [], "source": "error", "error": str(e)}


# ═══════════════════════════════════════════════════════════
# 6. ⭐ 单日完整黄历详情（选中日期展开用）
# ═══════════════════════════════════════════════════════════
@router.get("/day-detail")
def spacetime_day_detail(
    date: str = Query(..., description="YYYY-MM-DD"),
):
    """某天完整黄历详情——宜忌/建除/二十八宿/冲煞/吉神/十二时辰吉凶
    
    参考《协纪辨方》老黄历格式。数据全部来自 lunar_python。
    """
    try:
        import lunar_python
        Solar, Lunar = lunar_python.Solar, lunar_python.Lunar
    except ImportError:
        try:
            from qingmeng_engine._vendor.lunar_python import Solar, Lunar
        except ImportError:
            raise HTTPException(503, "lunar_python not available")

    try:
        y, m, d = map(int, date.split('-'))
    except ValueError:
        raise HTTPException(400, "date 必须是 YYYY-MM-DD 格式")

    try:
        s = Solar.fromYmd(y, m, d)
        l = s.getLunar()

        # 彭祖百忌（pip 版拆成 Gan + Zhi，vendor 版合成一个）
        try:
            pengzu = l.getPengZuBaiJi()
        except AttributeError:
            try:
                pengzu = (l.getPengZuGan() or '') + '；' + (l.getPengZuZhi() or '')
            except Exception:
                pengzu = ''

        # 十二时辰数据
        times = []
        for t in l.getTimes():
            times.append({
                "zhi": t.getZhi(),
                "yi": t.getYi(),
                "ji": t.getJi(),
                "tianshen": t.getTianShen(),
                "tianshen_luck": t.getTianShenLuck(),
                "chong_desc": t.getChongDesc(),
                "sha": t.getSha(),
                "xun": t.getXun(),
                "xun_kong": t.getXunKong(),
            })

        return {
            "date": date,
            "ganzhi_year": l.getYearInGanZhi(),
            "ganzhi_month": l.getMonthInGanZhi(),
            "ganzhi_day": l.getDayInGanZhi(),
            "lunar_month": l.getMonthInChinese(),
            "lunar_day": l.getDayInChinese(),
            "shengxiao": l.getYearShengXiao(),
            # 节气
            "prev_jieqi": l.getPrevJieQi() and l.getPrevJieQi().getName(),
            "next_jieqi": l.getNextJieQi() and l.getNextJieQi().getName(),
            # 建除
            "jianchu": l.getZhiXing(),
            # 二十八宿
            "xiu": l.getXiu(),
            "xiu_luck": l.getXiuLuck(),
            "xiu_song": l.getXiuSong(),
            # 黄道/黑道
            "tianshen_type": l.getDayTianShenType(),
            "tianshen_luck": l.getDayTianShenLuck(),
            # 宜忌
            "yi": l.getDayYi(),
            "ji": l.getDayJi(),
            # 冲煞
            "chong": l.getChongDesc(),
            "sha": l.getSha(),
            # 吉神
            "ji_shen": l.getDayJiShen(),
            # 彭祖百忌
            "pengzu": pengzu,
            # 十二时辰
            "times": times,
            # 三元五腊/圣诞（查农历月日字典）
            "festival": LUNAR_FESTIVALS.get((l.getMonth(), l.getDay())),
            "source": "lunar_python",
        }
    except Exception as e:
        import logging
        logging.getLogger("qingnang.spacetime").warning(f"spacetime_day_detail 失败: {e}")
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════════
# 7. ⭐ 玄空飞星·一站式排盘+化解
# ═══════════════════════════════════════════════════════════
class FlyingStarIn(BaseModel):
    shan: str                                    # 坐山（如 "子"）
    xiang: Optional[str] = None                   # 向首（不传自动推对宫）
    yun: Optional[int] = None                     # 运号（不传按年份推）
    year: Optional[int] = None                    # 用于推运的年份
    palace_functions: Optional[dict[str, str]] = None  # {"坎": "卧室", "兑": "厨房", ...}


@router.post("/flying-star")
def flying_star_resolve(body: FlyingStarIn):
    """
    玄空飞星·一站式排盘+卦组合化解

    输入：坐山（必选）+ 向首/运号/年份（可选）+ 宫位功能（可选）
    输出：三盘（运/山/向）+ 九宫山向组合 + 每宫化解建议

    治理策略：本引擎只有宫级 2 个星（山星+向星），
    不能做完整五边形凸多面体力学检测——用秘术反推的该两星组合最优化解。
    完整五形向量的场景（tiao_hou_engine）由 wuxing_chain 动态选择策略。
    """
    try:
        from ...utils.flying_star_engine import make_complete_pan
        from ...utils.gua_resolution_engine import resolve_pan
    except ImportError as e:
        raise HTTPException(500, f"飞星引擎加载失败: {e}")

    try:
        pan = make_complete_pan(body.shan, body.xiang, body.yun, body.year)
    except ValueError as e:
        raise HTTPException(400, str(e))

    resolutions = resolve_pan(pan, body.palace_functions)

    return {
        "ok": True,
        "engine": "spum_flying_star_v1",
        "meta": {
            "yun": pan['yun'],
            "yun_dynasty": pan['yun_dynasty'],
            "shan": pan['shan'],
            "xiang": pan['xiang'],
            "shan_yin_yang": pan['shan_yin_yang'],
            "xiang_yin_yang": pan['xiang_yin_yang'],
            "shan_direction": pan['shan_direction'],
            "xiang_direction": pan['xiang_direction'],
            "source": "spum-core/五行/地元/spum-玄空飞星.md + spum-卦组合化解.md",
        },
        "yun_pan": pan['yun_pan'],
        "shan_pan": pan['shan_pan'],
        "xiang_pan": pan['xiang_pan'],
        "palaces": resolutions,
        "summary": {
            "total_palaces": 9,
            "key_shen_palaces": [r['palace'] for r in resolutions if r['is_key_shen']],
            "sha_palaces": [r['palace'] for r in resolutions if r['is_gua_sha']],
            "jiehua_palaces": [r['palace'] for r in resolutions if r['mediator_node']],
        },
    }
