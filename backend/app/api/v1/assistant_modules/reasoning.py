"""reasoning - 结构化推理代理：转发 qingmeng-engine 推理端点 + 本地规则兜底"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx
import json

from ....database import get_db
from ....models import User, Case
from ....config import settings
from ...deps import get_current_user
from ....utils.maturity import compute_maturity

router = APIRouter()

# ═══════════════════════════════════════════════════════
# 结构化推理代理 — 转发到 qingmeng-engine 的推理端点
# ═══════════════════════════════════════════════════════

async def _forward_reasoning(path: str, payload: dict, db: Session, current: User) -> dict:
    """通用推理代理（Phase 4 升级）。

    完整管线:
      1. 注入用户上下文（v_base 等）
      2. 先调 /v1/reasoning/daily_brief 拿一揽子确定性产出物（base）
      3. 再调 qingmeng-engine 对应推理端点拿 LLM 增强
      4. LLM 可用 → merge（engine="daily_brief+llm"）
         LLM 不可用 → daily_brief 直接返回（engine="daily_brief_only"）
    """
    # 1. 注入用户上下文（无建档时用健康默认值优雅降级）
    if not payload.get("v_base"):
        case = db.query(Case).filter(Case.user_id == current.id).first()
        if case:
            payload["v_base"] = case.v_baseline
            payload["v_current"] = case.v_current or case.v_baseline
            payload["user_meta"] = payload.get("user_meta") or {
                "nickname": current.nickname,
                "gender": current.gender,
                "syndrome": case.syndrome,
                "chief_complaint": case.chief_complaint,
            }
        else:
            _DEFAULT_HEALTHY_V = {"wood": 50, "fire": 50, "earth": 50, "metal": 50, "water": 50}
            payload["v_base"] = _DEFAULT_HEALTHY_V
            payload["v_current"] = _DEFAULT_HEALTHY_V
            payload["user_meta"] = payload.get("user_meta") or {
                "nickname": current.nickname,
                "gender": current.gender,
                "syndrome": "未建档",
                "chief_complaint": "",
                "fallback": True,
            }

    v_base = payload.get("v_base")

    # ── 2. 先拿 daily_brief 全量确定性产出物（3s timeout）──
    brief_base = None
    if v_base:
        try:
            async with httpx.AsyncClient(timeout=3.0) as tc:
                tr = await tc.post(
                    f"{settings.QINGMENG_URL}/v1/reasoning/daily_brief",
                    json={"v_base": v_base},
                )
                if tr.status_code == 200:
                    brief_base = tr.json()
        except Exception:
            brief_base = None

    # ── 3. 调 qingmeng-engine LLM 推理端点 ──
    llm_result = None
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(
                f"{settings.QINGMENG_URL}{path}",
                json=payload,
            )
            if r.status_code == 200:
                llm_result = r.json()
    except Exception:
        pass

    # ── 4. 组合结果 ──
    if brief_base and llm_result:
        llm_result["brief_base"] = brief_base
        llm_result["engine"] = "daily_brief+llm"
        llm_result["proxied_from"] = settings.QINGMENG_URL
        return llm_result

    if brief_base:
        brief_base["engine"] = "daily_brief_only"
        brief_base["path"] = path
        return brief_base

    return _simple_fallback(path, payload)


def _simple_fallback(path: str, payload: dict) -> dict:
    """qingmeng-engine 不可达时的 rule-based 兜底（不再返回空壳）。"""
    v = payload.get("v_base") or payload.get("v_current") or {}
    if "diagnose" in path:
        return {
            "summary": "·".join(
                [p for p in [
                    "土形枯竭" if v.get("earth", 50) < 50 else None,
                    "水形不足" if v.get("water", 50) < 50 else None,
                    "火形妄动" if v.get("fire", 50) > 70 else None,
                ] if p]
            ) or "五形调和",
            "core_patterns": [],
            "daily_guidance": [],
            "contraindications": [],
            "engine": "backend_fallback",
        }
    if "lifestyle" in path:
        return _fallback_lifestyle(v, payload)
    if "treatment" in path:
        return {
            "current_assessment": "离线模式",
            "version_suggestion": "",
            "adjustments": [], "new_herbs": [], "remove_herbs": [],
            "updated_guidance": [], "engine": "backend_fallback",
        }
    return {"engine": "backend_fallback", "note": "unknown path"}


# ═══════════════════════════════════════════════════════════
# 黄历推演：协纪辨方 + 玉匣记 + 干支算法
# ═══════════════════════════════════════════════════════════

_JIAN_CHU = ["建", "除", "满", "平", "定", "执", "破", "危", "成", "收", "开", "闭"]
_SHICHEN_NAMES = ["子时", "丑时", "寅时", "卯时", "辰时", "巳时", "午时", "未时", "申时", "酉时", "戌时", "亥时"]
_SHICHEN_RANGE = ["23-01", "01-03", "03-05", "05-07", "07-09", "09-11", "11-13", "13-15", "15-17", "17-19", "19-21", "21-23"]
_SHICHEN_ELEM = ["水", "土", "木", "木", "土", "火", "火", "土", "金", "金", "土", "水"]

# 十二建除宜忌（简化版）
_JIAN_CHU_YI = {
    "建": ["出行", "上任", "临政", "祭祀"],
    "除": ["除服", "成服", "求医", "解除"],
    "满": ["祭祀", "祈福", "开光", "出行"],
    "平": ["修造", "动土", "平道", "修桥"],
    "定": ["安床", "安葬", "定盟", "冠笄"],
    "执": ["捕捉", "畋猎", "修造", "祭祀"],
    "破": ["坏垣", "破屋", "求医", "破贼"],
    "危": ["祭祀", "祈福", "安床", "移徙"],
    "成": ["嫁娶", "入学", "开市", "立券"],
    "收": ["纳财", "入仓", "修造", "移徙"],
    "开": ["祭祀", "祈福", "出行", "开市", "立券"],
    "闭": ["筑堤", "修园", "安葬", "塞穴"],
}
_JIAN_CHU_JI = {
    "建": ["动土", "开仓", "掘井", "乘船"],
    "除": ["嫁娶", "出行", "移徙", "栽种"],
    "满": ["移徙", "赴任", "嫁娶", "服药"],
    "平": ["嫁娶", "移徙", "安葬", "入学"],
    "定": ["出行", "词讼", "诉讼", "上书"],
    "执": ["开市", "移徙", "出行", "入宅"],
    "破": ["诸事不宜", "嫁娶", "出行", "移徙"],
    "危": ["登山", "远行", "乘船", "冒险"],
    "成": ["诉讼", "争讼", "动土", "求医"],
    "收": ["出行", "嫁娶", "安葬", "词讼"],
    "开": ["安葬", "伐木", "取鱼", "破土"],
    "闭": ["出行", "嫁娶", "开市", "动土"],
}

# 彭祖百忌（玉匣记核心 · 精简版）
_PENGZU_BAIJI = {
    "甲": "甲不开仓财物耗散",
    "乙": "乙不栽植千株不长",
    "丙": "丙不修灶必见灾殃",
    "丁": "丁不剃头头必生疮",
    "戊": "戊不受田田主不祥",
    "己": "己不破券二比并亡",
    "庚": "庚不经络织机虚张",
    "辛": "辛不合酱主人不尝",
    "壬": "壬不汲水更难提防",
    "癸": "癸不词讼理弱敌强",
}
_PENGZU_DIZHI_BAD = {
    "子": "子不问卜自惹祸殃",
    "丑": "丑不冠带主不还乡",
    "寅": "寅不祭祀神鬼不尝",
    "卯": "卯不穿井水泉不香",
    "辰": "辰不哭泣必主重丧",
    "巳": "巳不远行财物耗散",
    "午": "午不苫盖屋主更张",
    "未": "不服药毒气入肠",
    "申": "申不安床鬼祟入房",
    "酉": "酉不会客醉坐颠狂",
    "戌": "戌不吃犬作怪上床",
    "亥": "亥不嫁娶不利新郎",
}

# 二十八宿相关常量已删除（_XIU / _XIU_YI）。
# 原因：手写表既算不准（值日是连续日循环，非日干支函数），
# 吉凶也不准。现统一取lunar_python 的 getXiu() / getXiuLuck() / getXiuSong()。

# 天干地支索引 → 建除神推算
_DI_ZHI_IDX = {c: i for i, c in enumerate("子丑寅卯辰巳午未申酉戌亥")}

# ════ 飞星 → 落宫 → 八方位映射 ════
# 飞星号 1-9 对应：一白、二黑、三碧、四绿、五黄、六白、七赤、八白、九紫
# 洛书九宫：戴九履一，左三右七，二四为肩，六八为足，五在中央
# 落宫 → 方位: 坎=北, 坤=西南, 震=东, 巽=东南, 乾=西北, 兑=西, 艮=东北, 离=南
# 五黄居中 → 寄坤(西南)
_FEIXING_MAP = {
    1: {"name": "一白水天枢", "gong": "坎",  "dir": "正北",   "elem": "water"},
    2: {"name": "二黑土天璇", "gong": "坤",  "dir": "西南",   "elem": "earth"},
    3: {"name": "三碧木天玑", "gong": "震",  "dir": "正东",   "elem": "wood"},
    4: {"name": "四绿木天权", "gong": "巽",  "dir": "东南",   "elem": "wood"},
    5: {"name": "五黄土天玉", "gong": "坤",  "dir": "西南",   "elem": "earth", "note": "五黄居中寄坤"},
    6: {"name": "六白金开阳", "gong": "乾",  "dir": "西北",   "elem": "metal"},
    7: {"name": "七赤金摇光", "gong": "兑",  "dir": "正西",   "elem": "metal"},
    8: {"name": "八白土天辅", "gong": "艮",  "dir": "东北",   "elem": "earth"},
    9: {"name": "九紫火天英", "gong": "离",  "dir": "正南",   "elem": "fire"},
}

# ════ 五行生克判定（SPUM 交叉工具）════
# 生: 我生为泄（助我），生我为补
# 克: 我克为耗，克我为伤
_WX_SHENG = {"wood": "fire", "fire": "earth", "earth": "metal", "metal": "water", "water": "wood"}
_WX_KE    = {"wood": "earth", "earth": "water", "water": "fire", "fire": "metal", "metal": "wood"}

_OPPOSITE_DIR = {
    "正北": "正南", "正南": "正北", "正东": "正西", "正西": "正东",
    "东北": "西南", "西南": "东北", "西北": "东南", "东南": "西北",
}


def _opposite_dir(d: str) -> str:
    """方位对冲。查不到时返回空串——不再默认落到「正南」，
    避免把未知方位伪装成一个具体结论。"""
    return _OPPOSITE_DIR.get(d, "")


def _nine_star_num(ns) -> int | None:
    """NineStar 对象 → 星号 1-9。

    lunar_python 的 NineStar.getIndex() 是 **0 基**（0→一白, 8→九紫），
    直接当星号用会全表错位一位，必须 +1。
    兼容传入字符串或None。
    """
    if ns is None:
        return None
    if isinstance(ns, int):
        return ns + 1 if 0 <= ns <= 8 else None
    idx = getattr(ns, "getIndex", None)
    if callable(idx):
        try:
            i = idx()
            return i + 1 if 0 <= i <= 8 else None
        except Exception:
            return None
    # 字符串兜底：中文数字映射
    cn = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "九紫": 9}
    s = str(ns)
    for k, v in cn.items():
        if k in s:
            return v
    return None


def _wx_relation(a: str, b: str) -> str:
    """a 和 b 的五行关系（用于时辰/方位 vs v_base）:
    'generate_me' = b 生 a → 助我（好）
    'generated_by_me' = a 生 b → 耗我（平/微耗）
    'overcome_me' = b 克 a → 伤我（坏）
    'overcome_by_me' = a 克 b → 平
    'same' = 同五行 → 看强弱（强则平，弱则助）
    """
    if a == b: return "same"
    if _WX_SHENG.get(b) == a: return "generate_me"      # b 生 a
    if _WX_SHENG.get(a) == b: return "generated_by_me"  # a 生 b
    if _WX_KE.get(b) == a: return "overcome_me"          # b 克 a
    if _WX_KE.get(a) == b: return "overcome_by_me"       # a 克 b
    return "neutral"


def _almanac_today(year: int, month: int, day: int) -> dict:
    """完整今日黄历推演 — 协纪辨方 + 玉匣记 + 传统算法。
    
    优先用 lunar_python 能直接给的数据，缺失的自己用传统历法算法补。
    """
    from lunar_python import Solar
    
    s = Solar.fromYmd(year, month, day)
    l = s.getLunar()
    
    # 干支
    gz_year = l.getYearInGanZhiExact()
    gz_month = l.getMonthInGanZhiExact()
    gz_day = l.getDayInGanZhiExact()
    day_gan = gz_day[0]   # 日干
    day_zhi = gz_day[1]   # 日支
    month_zhi = gz_month[1]  # 月支
    
    # lunar_python 直接给
    chong = l.getDayChongDesc()        # 冲煞 (癸丑)牛
    sha = l.getDaySha()                # 煞方 西
    na_yin_day = l.getDayNaYin()       # 纳音
    na_yin_year = l.getYearNaYin()
    feixing_day_obj = l.getDayNineStar()    # 日飞星（NineStar 对象）
    feixing_year_obj = l.getYearNineStar()  # 年飞星（NineStar 对象）
    feixing_day = str(feixing_day_obj)      # 展示用字符串，如「一白水天枢」
    feixing_year = str(feixing_year_obj)
    tianshen = l.getDayTianShen()       # 值日天神
    yi_list = l.getDayYi()              # 宜
    ji_list = l.getDayJi()              # 忌
    
    # ════ 十二建除（从月支 → 日支推算）════
    # 月建 = 月支对应的建除位置；从月建开始数到日支
    jianchu_start = _DI_ZHI_IDX.get(month_zhi, 0)  # 月支在建除中的位置
    jianchu_day_idx = _DI_ZHI_IDX.get(day_zhi, 0)
    jianchu_offset = (jianchu_day_idx - jianchu_start) % 12
    jianchu = _JIAN_CHU[jianchu_offset]
    jianchu_yi = _JIAN_CHU_YI.get(jianchu, [])
    jianchu_ji = _JIAN_CHU_JI.get(jianchu, [])
    
    # ════ 二十八宿（用lunar_python 现成实现）════
    # ⚠️ 旧实现曾用 (日支*2 + 天干) % 28 自研公式，实测 20 天中 18 天算错
    #    （二十八宿值日是连续日循环、每日进一宿，不是日干支的函数）。
    #    现直接取库的正确实现，三者一一对应：
    #    getXiu()     → 宿名
    #    getXiuLuck() → 吉/凶（替代原手写 _XIU_YI 表）
    #    getXiuSong() → 宿歌
    xiu = l.getXiu()
    xiu_luck = l.getXiuLuck()      # '吉' / '凶'
    xiu_song = l.getXiuSong()      # 宿歌
    xiu_yi: list[str] = []          # 库未直接给宜事项，保留空列表供前端兼容
    
    # ════ 彭祖百忌（玉匣记）════
    pengzu_gan = _PENGZU_BAIJI.get(day_gan, "")
    pengzu_zhi = _PENGZU_DIZHI_BAD.get(day_zhi, "")
    pengzu = "；".join(filter(None, [pengzu_gan, pengzu_zhi])) or "本日无彭祖百忌"
    
    # ════ 时辰宜忌（12 时辰 × 建除神 × 五行）════
    timeline = []
    for i in range(12):
        period_name = _SHICHEN_NAMES[i]
        hour_start = (23 + i * 2) % 24
        hour_end = (hour_start + 2) % 24
        elem = _SHICHEN_ELEM[i]
        
        # 时辰建除（继承日建除的循环）
        sc_jianchu = _JIAN_CHU[(jianchu_offset + i) % 12]
        sc_yi = _JIAN_CHU_YI.get(sc_jianchu, [])[:3]
        sc_ji = _JIAN_CHU_JI.get(sc_jianchu, [])[:3]
        
        # 时辰吉凶判定
        if sc_jianchu in ("建", "开", "成", "满"):
            sc_type = "good"
        elif sc_jianchu in ("破", "闭", "平"):
            sc_type = "critical"
        elif sc_jianchu in ("危", "收"):
            sc_type = "warn"
        else:
            sc_type = "personal"
        
        timeline.append({
            "period": period_name,
            "range": f"{hour_start:02d}-{hour_end:02d}",
            "elem": elem,
            "jianchu": sc_jianchu,
            "yi": sc_yi,
            "ji": sc_ji,
            "type": sc_type,
            "desc": f"{elem}时 · {sc_jianchu}日 · 宜{'、'.join(sc_yi[:2]) if sc_yi else '诸事'}",
        })
    
    # ════ 玉匣记摘录（简化版）════
    # 基于今日建除 + 星宿 + 彭祖组合
    jianchu_str = f"{jianchu}日"
    xiu_str = f"{xiu}宿"
    yuxiaji_lines = [
        f"【玉匣记·值日】{gz_day} {jianchu_str} {xiu_str}",
        f"宜：{'、'.join(yi_list[:6]) if yi_list else '诸事不宜'}；忌：{'、'.join(ji_list[:6]) if ji_list else '无'}",
        f"彭祖百忌：{pengzu}",
        f"冲煞：{chong}，煞{sha}方",
    ]
    yuxiaji = "\n".join(yuxiaji_lines)
    
    return {
        # 干支
        "ganzhi_year": gz_year, "ganzhi_month": gz_month, "ganzhi_day": gz_day,
        "day_gan": day_gan, "day_zhi": day_zhi,
        # 黄历核心
        "yi": yi_list, "ji": ji_list,
        "chong": chong, "sha": sha,
        "jianchu": jianchu, "jianchu_yi": jianchu_yi, "jianchu_ji": jianchu_ji,
        "xiu": xiu, "xiu_yi": xiu_yi, "xiu_luck": xiu_luck, "xiu_song": xiu_song,
        "pengzu": pengzu,
        # 其他
        "na_yin": {"year": na_yin_year, "month": l.getMonthNaYin(), "day": na_yin_day},
        "feixing": {"year": feixing_year, "day": feixing_day},
        # 保留NineStar 原始对象，供方位推理取星号（避免从中文名反解）
        "_nine_star_day": feixing_day_obj,
        "_nine_star_year": feixing_year_obj,
        "tianshen": tianshen,
        # 时辰
        "timeline": timeline,
        # 玉匣记
        "yuxiaji": yuxiaji,
    }


# ═══════════════════════════════════════════════════════════
# Rule-based lifestyle fallback（v2 增益中庸范式）
# —— 使用 spacetime_engine.tiao_hou_engine 找 SHENG 链断链点 → 增益链条
# —— 经典 home/travel/solutions 处方保留，但触发条件从"最弱"改为"断链点"
# ═══════════════════════════════════════════════════════════
def _fallback_lifestyle(v: dict, payload: dict) -> dict:
    from datetime import datetime
    from ....utils.trajectory_algorithm import get_liunian, ganzhi_main_elem
    from ....utils.spacetime_engine import tiao_hou_engine, spacetime_context, WUXING_CN

    # 1. 今日干支 + 黄历（保留，这是择吉层，与治理范式无关）
    today = datetime.today()
    almanac = _almanac_today(today.year, today.month, today.day)
    ln = get_liunian(today.year)
    day_elem = ganzhi_main_elem(ln["g"], ln["z"])

    WX_COLOR = {"wood": "青绿", "fire": "赤红", "earth": "黄褐", "metal": "白灰", "water": "黑蓝"}
    
    # 2. 🆕 用 tiao_hou_engine 找断链点（增益中庸范式）
    ctx = spacetime_context(today, payload.get("birthplace") or "上海")
    th = tiao_hou_engine(v, ctx)
    broken_chain = th['broken_chain']
    broken = broken_chain.get('broken_node')  # 断链点
    peaks = broken_chain.get('peaks', [])     # 尖峰
    valleys = broken_chain.get('valleys', []) # 凹谷

    # 如果链条自洽 → 不干预
    if not broken:
        return {
            "cloth_good": [], "cloth_bad": [],
            "food_good": [], "food_bad": [],
            "yi_text": f"今日{WUXING_CN[day_elem]}日·五形链条自洽·顺其自然",
            "ji_text": "",
            "home": [], "absolute": [], "relative": [],
            "travel": almanac.get("timeline", []),
            "solutions": [],
            "chain_desc": "五形链条自洽",
        }

    broken_cn = WUXING_CN[broken]
    broken_color = WX_COLOR[broken]
    chain_from = broken_chain.get('prev')
    chain_to = broken_chain.get('next')
    chain_desc = f"{WUXING_CN[chain_from]}→{broken_cn}→{WUXING_CN[chain_to]}链断于{broken_cn}形"

    # 3. 穿衣建议（增益断链点，而非补最弱）
    cloth_good = [{
        "id": "cloth-1",
        "title": f"多穿{broken_color}系 · 增益{broken_cn}形链条",
        "desc": f"链条断于{broken_cn}形，增益{broken_cn}让链条通 → "
                f"{WUXING_CN[chain_from]}形堆积尖峰自消、{WUXING_CN[chain_to]}形凹谷自填",
        "reason": chain_desc + (f"（尖峰：{'、'.join(WUXING_CN[p] for p in peaks)}）" if peaks else "")
                  + (f"（凹谷：{'、'.join(WUXING_CN[v] for v in valleys)}）" if valleys else ""),
        "detail": f"以{broken_color}色的上衣、围巾或配饰为主，贴身层优先{broken_color}色；"
                  f"链条通了，尖峰凹谷自然平复，不需直接压制。",
        "source_ref": "《黄帝内经·素问》——五色入五脏",
        "governance": "增益中庸",
    }]
    cloth_bad = []
    if day_elem == peaks[0] if peaks else None:
        cloth_bad.append({
            "id": "cloth-avoid-day",
            "title": f"今日穿同尖峰色系会加剧堆积",
            "desc": f"今日{WUXING_CN[day_elem]}主气（恰为尖峰），穿同色会加重堆积",
            "reason": f"今日干支 {ln['g']}{ln['z']} 主气 {WUXING_CN[day_elem]}，与{broken_cn}形断链耦合",
            "detail": f"今日避免{WX_COLOR[day_elem]}色整体穿搭；可用{broken_color}色配饰中和。",
            "source_ref": "《千金要方》——随四时五行调节起居服色",
        })

    # 4. 饮食建议（增益断链点的经典食材，保留五形属性）
    WEAK_FOOD = {
        "wood": ["菠菜", "芹菜", "韭菜", "青梅", "枸杞"],
        "fire": ["红枣", "桂圆", "樱桃", "番茄"],
        "earth": ["山药", "薏米", "南瓜", "红薯"],
        "metal": ["雪梨", "银耳", "百合", "莲藕"],
        "water": ["黑豆", "黑芝麻", "海带", "栗子"],
    }
    # 不宜：尖峰的所生会继续推高尖峰
    STRONG_AVOID = {
        "wood": ["辛辣", "茴香", "花椒"],
        "fire": ["煎炸", "烧烤", "辣椒"],
        "earth": ["油腻", "甜品", "蜂蜜"],
        "metal": ["生冷", "冰饮", "生菜"],
        "water": ["咸腌", "酱菜", "盐"],
    }
    
    food_good = [{
        "id": "food-1",
        "title": f"宜吃{WEAK_FOOD[broken][0]}等 · 增益{broken_cn}形链条",
        "desc": "、".join(WEAK_FOOD[broken]) + f" — 增益{broken_cn}形让{chain_desc}链条通",
        "reason": chain_desc + f"。食材经典五形属性为{broken_cn}形，增益链条断链点",
        "detail": f"选其中1-2样，少量多次、细嚼慢咽；以煮、蒸、炖为主。"
                  f"建议安排在断链节点活跃的时辰（{broken_cn}形旺相时效果加倍）。",
        "source_ref": f"《本草纲目》——{broken_cn}类食材补益说明",
        "governance": "增益中庸",
    }]
    
    food_bad = []
    if peaks:
        peak_main = peaks[0]
        food_bad.append({
            "id": "food-bad-1",
            "title": f"忌{STRONG_AVOID[peak_main][0]}等助尖峰堆积",
            "desc": "、".join(STRONG_AVOID[peak_main]) + f" — 避免助{WUXING_CN[peak_main]}形尖峰继续堆积",
            "reason": f"{WUXING_CN[peak_main]}形堆积为尖峰（因{broken_cn}形断链没人接），"
                      f"尖峰越堆越难通链条",
            "detail": f"今日少吃或不吃上述食物；等{broken_cn}形增益、链条通了自然放开。",
            "source_ref": f"《黄帝内经·素问》——五味入五脏，过食则伤",
        })

    # 5. 今日宜忌
    yi_text = f"今日{WUXING_CN[day_elem]}日·宜{broken_color}系·增益{broken_cn}形·通{chain_desc}链"
    ji_text = f"忌穿{'、'.join(WX_COLOR[p] for p in peaks)}系·忌助尖峰堆积食物" if peaks else ""

    # 6. 住房/作息提醒（经典处方保留，触发条件从 weak== 改为 broken==）
    home = []
    if broken == "fire":
        home.append({"id": "home-1", "title": "增益火形 · 上午晒太阳活动", "desc": "链条断于火形（木→土衔接断），上午补火效佳",
                     "detail": "上午9-11点适度晒太阳、轻度活动（散步/拉伸），增益火形让木→土衔接通。",
                     "source_ref": "《黄帝内经·素问》——阳气者，一日而主外",
                     "governance": "增益中庸"})
    if broken == "water":
        home.append({"id": "home-2", "title": "增益水形 · 亥时泡脚", "desc": "21:00-23:00 肾经主时，泡脚增益水形",
                     "detail": "用40℃左右温水，水位没过踝关节，泡15分钟微微出汗；增益水形让金→水→木承接通。",
                     "source_ref": "《千金要方》——以冷水暖足浴，以肾经相应",
                     "governance": "增益中庸"})
    if broken == "earth":
        home.append({"id": "home-3", "title": "增益土形 · 辰时养胃", "desc": "7:00-9:00 辰时脾经旺，增益土形通金→水→土→火链",
                     "detail": "辰时（7-9点）吃温热早餐，以小米粥、山药、南瓜等增益土形为主；忌空腹冰饮。",
                     "source_ref": "《伤寒杂病论》——脾胃为后天之本",
                     "governance": "增益中庸"})
    if broken == "metal":
        home.append({"id": "home-4", "title": "增益金形 · 酉时收敛", "desc": "17:00-19:00 酉时肺经旺，增益金形让土→水桥通",
                     "detail": "酉时深呼吸/八段锦调息，润肺收敛（梨/百合/银耳）；增益金形让土→水桥节点恢复。",
                     "source_ref": "《本草纲目》——润肺收敛",
                     "governance": "增益中庸"})
    if broken == "wood":
        home.append({"id": "home-5", "title": "增益木形 · 晨间舒展", "desc": "辰时前（7点前）晨间拉伸步散，增益木形疏水→火衔接",
                     "detail": "晨间先深呼吸三次，做拉伸/瑜伽或散步15分钟；增益木形让水→火衔接通。",
                     "source_ref": "《黄帝内经·素问》——木主生发调达",
                     "governance": "增益中庸"})

    # 7. 禁忌（相对禁忌：尖峰差大时慎助尖峰）
    absolute = []
    relative = []
    if peaks and valleys:
        # 尖峰+凹谷差距大 → 链条断得严重
        broken_dev = 50 - v.get(broken, 50)
        if broken_dev > 20:
            relative.append({
                "id": "rel-1",
                "title": f"链条断得较重，不宜猛增益",
                "desc": f"增益{broken_cn}形让链条通，过程中会牵动尖峰/凹谷自然调整",
                "reason": chain_desc + f"（断链偏离 {broken_dev:.0f}）",
                "governance": "增益中庸",
            })

    # 8. 时辰出行提醒（保留黄历+建除，治理提示改为链条增益）
    travel = []
    for item in almanac["timeline"]:
        sc_elem_cn = item["elem"]
        sc_elem_map = {"木": "wood", "火": "fire", "土": "earth", "金": "metal", "水": "water"}
        sc_elem_en = sc_elem_map.get(sc_elem_cn, "wood")
        
        # 🆕 治理提示：此时辰五行是否是断链节点？是的话→天赐良机
        if sc_elem_en == broken:
            personal_hint = f"✨ 此时辰{sc_elem_cn}形是断链节点活跃时，增益效倍！"
        elif sc_elem_en in peaks:
            personal_hint = f"⚠️ 此时辰{sc_elem_cn}形是尖峰堆积，不宜助益"
        else:
            personal_hint = f"此时辰与你的链条增益方向平和"
        
        jianchu = item.get("jianchu", "")
        if jianchu in ("破", "闭"):
            travel_hint = f"【{jianchu}日】今日此辰宜静不宜动，大事不举"
        elif jianchu in ("建", "开"):
            travel_hint = f"【{jianchu}日】宜出行、赴任、开市"
        elif jianchu in ("成", "满"):
            travel_hint = f"【{jianchu}日】宜订婚、嫁娶、签约"
        else:
            travel_hint = f"【{jianchu}日】平日常即可"
        
        travel.append({
            "id": f"travel-{item['period']}",
            "period": item["period"],
            "range": item["range"],
            "elem": sc_elem_cn,
            "jianchu": jianchu,
            "title": f"{item['period']}({item['range']}) · {sc_elem_cn}时",
            "desc": travel_hint + "；" + personal_hint,
            "detail": f"时辰宜忌：宜{'、'.join(item['yi'][:3]) if item['yi'] else '诸事'}；"
                      f"忌{'、'.join(item['ji'][:3]) if item['ji'] else '无'}。"
                      f"治理提示：{personal_hint}。",
            "source_ref": "《协纪辨方书》· 十二建除 + 《玉匣记》· 彭祖百忌",
        })
    
    # 9. 破煞方案（保留黄历破煞，治理提示改为链条增益）
    solutions = []
    if almanac["jianchu"] in ("破", "危"):
        solutions.append({
            "id": "sol-jianchu",
            "title": f"今日{almanac['jianchu']}日化解方案",
            "desc": f"黄历{almanac['jianchu']}日主冲克，增益链条断链点同时避凶就吉",
            "target": almanac["jianchu"],
            "steps": [
                f"第一步：避开{almanac['jianchu_ji'][:3]}等不宜事项",
                f"第二步：增益{broken_cn}形（穿{broken_color}系、吃{WEAK_FOOD[broken][0]}等）让链条通",
                "第三步：遇事三思而后行，避免冲动决策",
            ],
            "reason": chain_desc + "。链条通了自然有缓冲力抵御冲克",
            "governance": "增益中庸",
        })
    
    if almanac["chong"]:
        solutions.append({
            "id": "sol-chong",
            "title": f"冲煞日 · 增益链条自然通关",
            "desc": f"今日{almanac['chong']}，增益{broken_cn}形让链条通，五形自洽则冲煞化",
            "target": f"冲{almanac['chong']}",
            "steps": [
                f"第一步：多穿{broken_color}色衣物配饰 · 增益{broken_cn}形",
                f"第二步：饮食侧重{WEAK_FOOD[broken][:3]}等增益{broken_cn}食材",
                f"第三步：避开{WUXING_CN.get(almanac['chong'])}形同系大面积穿搭助尖峰堆积",
            ],
            "reason": "冲煞日 + 五形偏弱 → 双压叠加，需主动调和",
        })
    
    if broken_dev > 20:
        diff = broken_dev
        solutions.append({
            "id": "sol-vbase",
            "title": f"链条断链修正方案（偏离 {diff:.0f}）",
            "desc": chain_desc + f"，增益{broken_cn}形让链条通",
            "target": f"增益{broken_cn}形",
            "steps": [
                f"第一步：连续3天多穿{broken_color}系",
                f"第二步：每天吃1-2样增益{broken_cn}食材（{'、'.join(WEAK_FOOD[broken])}）",
                f"第三步：避开{'、'.join(STRONG_AVOID[peaks[0]] if peaks else [])}助尖峰堆积",
                f"第四步：每天15分钟静坐调息，配合增益{broken_cn}形",
            ],
            "reason": chain_desc + f"（偏离 {diff:.0f}），增益链条让尖峰凹谷自然平复",
            "governance": "增益中庸",
        })
    
    # 10. 矿物避忌（经典五色石映射 + 链条增益治理）
    stone_map = {
        "wood": {"good": ["绿幽灵", "孔雀石", "翡翠"], "bad": ["白水晶"]},
        "fire": {"good": ["红玛瑙", "石榴石", "碧玺"], "bad": ["黑玛瑙", "黑曜石"]},
        "earth": {"good": ["黄水晶", "琥珀", "蜜蜡"], "bad": ["青金石"]},
        "metal": {"good": ["白水晶", "银饰", "白金"], "bad": ["红玛瑙"]},
        "water": {"good": ["蓝水晶", "黑曜石", "海蓝宝"], "bad": ["黄水晶"]},
    }
    stone_good = stone_map.get(broken, {}).get("good", [])
    stone_bad = stone_map.get(peaks[0] if peaks else None, {}).get("bad", [])
    stone = []
    if stone_good:
        stone.append({
            "id": "stone-good",
            "title": f"宜佩戴{'、'.join(stone_good)}",
            "desc": f"增益{broken_cn}形链条断链点，选其中1-2件贴身佩戴",
            "reason": f"五色入五脏——{broken_color}色矿物增益{broken_cn}形",
            "governance": "增益中庸",
        })
    if stone_bad:
        stone.append({
            "id": "stone-bad",
            "title": f"暂避{'、'.join(stone_bad)}",
            "desc": f"可能助尖峰堆积，今日不戴为宜",
            "reason": f"同类相感——尖峰色系矿物助旺已堆积之形",
        })
    
    # 11. 绝对禁忌（结合建除 + 彭祖 + v_base）
    if almanac["jianchu"] in ("破", "闭"):
        absolute.append({
            "id": "abs-jianchu",
            "title": f"【{almanac['jianchu']}日】诸事不宜",
            "desc": f"今日建除神为{almanac['jianchu']}，黄历主诸事不宜",
            "reason": "《协纪辨方书》· 建除十二神",
        })
    if almanac["pengzu"] and "不宜" in almanac["pengzu"]:
        absolute.append({
            "id": "abs-pengzu",
            "title": f"彭祖百忌：{almanac['pengzu']}",
            "desc": f"今日彭祖百忌条应验，需格外注意",
            "reason": "《玉匣记》· 彭祖百忌",
        })
    
    # ════ 12. 时辰 × 断链点 → 助我/平/耗我（吉时轴三态 · 链条增益版）════
    SHICHEN_ELEM_EN = {"木": "wood", "火": "fire", "土": "earth", "金": "metal", "水": "water"}
    for item in almanac["timeline"]:
        sc_elem = SHICHEN_ELEM_EN.get(item["elem"], "wood")
        base_el = broken  # 🆕 以断链点为参照（增益断链点为助我）
        rel = _wx_relation(base_el, sc_elem)
        sc_score = v.get(sc_elem, 50)
        
        if rel == "generate_me":      # 时辰生断链点 → 助我（吉）
            ptype, plabel = "good", "助我"
        elif rel == "overcome_me":    # 时辰克断链点 → 耗我（凶）
            ptype, plabel = "bad", "耗我"
        elif rel == "same" and sc_score < 45:  # 同断链点且此时辰弱 → 助我补
            ptype, plabel = "good", "助我"
        elif rel == "same" and sc_score > 65:  # 同断链点且此时辰旺 → 天赐良机
            ptype, plabel = "good", "✨增益效倍"
        elif rel == "generated_by_me":  # 断链点生时辰 → 微耗
            ptype, plabel = "neutral", "平"
        else:
            ptype, plabel = "neutral", "平"
        
        item["personal_type"] = ptype
        item["personal_label"] = plabel

    # ════ 13. 飞星落宫 → 今日方位（以断链点为参照）════
    ns_day = almanac.get("_nine_star_day")
    ns_year = almanac.get("_nine_star_year")
    feixing_day_num = _nine_star_num(ns_day)
    feixing_year_num = _nine_star_num(ns_year)
    fx_num = feixing_day_num or 1
    fx = _FEIXING_MAP.get(fx_num, _FEIXING_MAP[1])
    fx_el = fx["elem"]
    fx_dir = fx["dir"]
    fx_gong = fx["gong"]
    
    peak_main = peaks[0] if peaks else None
    fx_rel_broken = _wx_relation(broken, fx_el)
    fx_rel_peak = _wx_relation(peak_main, fx_el) if peak_main else None
    
    # 宜取 = 飞星生断链点 / 同断链点
    if fx_rel_broken in ("generate_me",) or (fx_rel_broken == "same" and v.get(broken, 50) < 45):
        good_dir, good_reason = fx_dir, f"日飞星{fx['name']}落{fx_gong}宫（{fx_dir}），生我断链点{broken_cn}形"
        bad_dir = _opposite_dir(fx_dir)
        bad_reason = f"与{fx_dir}对冲，与断链增益方向不合"
    elif peak_main and (fx_rel_peak in ("overcome_me",) or fx_rel_peak == "same"):
        good_dir, good_reason = fx_dir, f"日飞星{fx['name']}落{fx_gong}宫（{fx_dir}），避开尖峰叠加"
        bad_dir, bad_reason = fx_dir, f"飞星与尖峰{WUXING_CN[peak_main]}形同相，今日避免叠加"
    else:
        good_dir, good_reason = fx_dir, f"日飞星{fx['name']}落{fx_gong}宫（{fx_dir}），平和之气"
        bad_dir = _opposite_dir(fx_dir)
        bad_reason = f"对冲方位，与断链增益方向不合"
    
    orientation = {
        "feixing_num": fx_num,
        "feixing_name": fx["name"],
        "gong": fx_gong,
        "element": fx_el,
        "good_dir": good_dir,
        "good_reason": good_reason,
        "good_advice": f"睡床宜偏{good_dir}{'，或朝'+good_dir+'开窗纳气' if fx_dir in ('正北','正东') else ''}",
        "bad_dir": bad_dir,
        "bad_reason": bad_reason,
        "bad_advice": f"办公尽量避开{bad_dir}背门位",
    }

    # ════ 14. 替换表（以断链偏离为参照）════
    swaps = []
    if broken_dev > 15:
        swap_map = {
            "wood":  {"bad": "久坐不动 · 肝木郁结", "good": "每坐 1 小时起身 3 分钟舒展"},
            "fire":  {"bad": "午后急躁易怒 · 心火上炎", "good": "午后闭目养神 10 分钟静坐"},
            "earth": {"bad": "思虑过度 · 脾土湿困", "good": "每 2 小时抬头远眺 30 秒"},
            "metal": {"bad": "说话急促 · 肺气耗散", "good": "说话放慢半拍，每句之间留 1 秒"},
            "water": {"bad": "熬夜过 23 点 · 肾水亏虚", "good": "22:30 前放下手机准备入睡"},
        }
        swaps.append({
            "bad": swap_map.get(broken, {}).get("bad", "无"),
            "good": swap_map.get(broken, {}).get("good", "无"),
            "reason": chain_desc,
        })
    
    today_elem_main = day_elem
    if today_elem_main in ("wood",):
        swaps.append({"bad": "寅卯时 3-7 点剧烈运动", "good": "移至申酉时 15-19 点", "reason": "肝木当令忌泄"})
    if almanac["jianchu"] in ("破", "危", "闭"):
        swaps.append({"bad": "今日大事冲动决策", "good": "遇事三思，暂缓签约/出行", "reason": f"{almanac['jianchu']}日宜静不宜动"})
    if broken == "water":
        swaps.append({"bad": "午后饮浓茶/咖啡", "good": "13-15 时改饮温水或淡枸杞茶", "reason": "链条断于水形，忌浓茶夺水"})
    
    swaps = swaps[:3]
    
    # ════ 组装完整返回 ════
    anchor = almanac
    anchor["ganzhi"] = f"{almanac['ganzhi_year']}{almanac['ganzhi_month']}{almanac['ganzhi_day']}"
    anchor["dangling_elem"] = broken_cn
    anchor["state"] = chain_desc
    anchor["engine"] = "rule_almanac_v4"
    anchor["governance"] = "增益中庸"
    
    return {
        "anchor": anchor,
        "timeline": almanac["timeline"],
        "orientation": orientation,
        "swaps": swaps,
        "cloth_reminders": cloth_good + cloth_bad,
        "food_good": food_good,
        "food_bad": food_bad,
        "home_reminders": home,
        "absolute_avoid": absolute,
        "relative_avoid": relative,
        "stone": stone,
        "travel": travel,
        "solutions": solutions,
        "chain_desc": chain_desc,
        "broken_node": broken,
        "peaks": peaks,
        "valleys": valleys,
        "engine": "rule_almanac_v4",
        "governance": "增益中庸",
        "note": "协纪辨方 + 玉匣记 + SPUM 链条增益治理（v4: 增益中庸范式，替代 v3 补缺抑强）",
    }


class DiagnoseIn(BaseModel):
    v_base: dict | None = None
    v_current: dict | None = None
    user_meta: dict | None = None


class LifestyleIn(BaseModel):
    v_base: dict | None = None
    v_current: dict | None = None
    city: str | None = None        # ⭐ 用户所在城市（天气查询）
    provider: str | None = None    # ⭐ "ollama"(本地) / "deepseek"(云端)


class TreatmentIn(BaseModel):
    current_plan: dict | None = None
    latest_observation: dict | None = None


@router.post("/reasoning/diagnose")
async def reasoning_diagnose(body: DiagnoseIn,
                             db: Session = Depends(get_db),
                             current: User = Depends(get_current_user)):
    """SPUM 结构化诊断 — 五形向量 → 病理+建议 JSON（青檬引擎推理）。"""
    return await _forward_reasoning(
        "/v1/reasoning/diagnose",
        body.model_dump(exclude_none=True),
        db, current,
    )


@router.post("/reasoning/lifestyle")
async def reasoning_lifestyle(body: LifestyleIn,
                              db: Session = Depends(get_db),
                              current: User = Depends(get_current_user)):
    """今日生活提醒 — v_base → 宜忌/衣食住行/时辰养生 JSON（青檬引擎推理 + 按日缓存）。

    ⭐ 2026-10-05：支持每次请求传 provider（ollama/deepseek），缓存 key 自动区分。
    """
    from ..notifications import _call_qingmeng_lifestyle
    payload = body.model_dump(exclude_none=True)
    payload = await _inject_user_context(payload, db, current)
    # ⭐ 把 body 里的 provider 也传给 qingmeng-engine
    provider = payload.get("provider") or body.provider or None
    city = payload.get("city") or current.city or None
    data = await _call_qingmeng_lifestyle(
        v_base=payload.get("v_base") or {},
        v_current=payload.get("v_current") or payload.get("v_base"),
        qingnang_id=current.qingnang_id or f"user_{current.id}",
        city=city,
        provider=provider,
        user_meta=payload.get("user_meta"),  # ⭐ 2026-10-06 传年龄/慢性病/过敏
    )
    return data


# ═══════════════════════════════════════════════════════
# Lifestyle 流式 SSE 代理 — 透传 qingmeng-engine 的流
# ═══════════════════════════════════════════════════════

async def _inject_user_context(payload: dict, db: Session, current: User) -> dict:
    """注入用户五形向量 + 年龄 + 健康标签上下文。无建档时用健康默认值优雅降级。"""
    from ..notifications import build_user_meta

    # ⭐ 注入用户城市（用于真实天气查询）
    if current.city and not payload.get("city"):
        payload["city"] = current.city

    if not payload.get("v_base"):
        case = db.query(Case).filter(Case.user_id == current.id).first()
        if case:
            payload["v_base"] = case.v_baseline
            payload["v_current"] = case.v_current or case.v_baseline
            payload["user_meta"] = payload.get("user_meta") or build_user_meta(current, case)
        else:
            # 优雅降级：健康五形调和默认值（SPUM 拓扑常数 12 附近）
            _DEFAULT_HEALTHY_V = {"wood": 50, "fire": 50, "earth": 50, "metal": 50, "water": 50}
            payload["v_base"] = _DEFAULT_HEALTHY_V
            payload["v_current"] = _DEFAULT_HEALTHY_V
            meta = build_user_meta(current)
            meta["syndrome"] = "未建档"
            meta["chief_complaint"] = ""
            meta["fallback"] = True  # 标记：未建档，使用默认值
            payload["user_meta"] = payload.get("user_meta") or meta
    else:
        # v_base 已有（前端传的）—— 补年龄/健康标签
        existing = payload.get("user_meta") or {}
        payload["user_meta"] = {**build_user_meta(current), **existing}

    return payload


async def _proxy_lifestyle_stream(payload: dict):
    """SSE 生成器：透传 qingmeng-engine 的流式响应。"""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            async with client.stream(
                "POST",
                f"{settings.QINGMENG_URL}/v1/reasoning/lifestyle/stream",
                json=payload,
            ) as r:
                if r.status_code != 200:
                    yield f"event: note\ndata: {json.dumps({'text': f'青檬引擎 HTTP {r.status_code}'}, ensure_ascii=False)}\n\n"
                    fallback = _simple_fallback("/reasoning/lifestyle", payload)
                    yield f"event: complete\ndata: {json.dumps(fallback, ensure_ascii=False)}\n\n"
                    return
                async for line in r.aiter_lines():
                    yield line + "\n"
    except Exception as e:
        yield f"event: note\ndata: {json.dumps({'text': f'青檬引擎不可达: {e}'}, ensure_ascii=False)}\n\n"
        fallback = _simple_fallback("/reasoning/lifestyle", payload)
        yield f"event: complete\ndata: {json.dumps(fallback, ensure_ascii=False)}\n\n"


@router.post("/reasoning/lifestyle/stream")
async def reasoning_lifestyle_stream(body: LifestyleIn,
                                     db: Session = Depends(get_db),
                                     current: User = Depends(get_current_user)):
    """今日生活提醒 — SSE 流式代理。透传青檬引擎 generating/complete 事件。
    
    ⚠️ Stage 1（刚建档 0 观测）不生成生活提醒 — v_base 只有先天基底，
       此时给建议无临床意义，直接返回空 complete。
    
    ⭐ 2026-10-05 缓存增强：
       先调用 notifications._call_qingmeng_lifestyle（内部有按日缓存），
       缓存命中时直接发 complete 事件，不再调 qingmeng-engine SSE。
       缓存未命中时走原 SSE 代理路径。
    """
    from ....utils.maturity import compute_maturity
    mat = compute_maturity(current, db)
    if mat["stage"] < 2:
        # Stage 1 → 直接返回空 complete 事件，不调青檬引擎
        empty_payload = {
            "anchor": None, "timeline": [], "cloth_reminders": [],
            "food_good": [], "food_bad": [], "home_reminders": [],
            "absolute_avoid": [], "relative_avoid": [],
            "engine": "spum_stage1_skip",
            "note": "Stage 1 刚建档，采集首次 PPG 观测后启用生活建议",
        }
        import json
        async def _empty_stream():
            yield f"event: note\ndata: {json.dumps({'text': 'Stage 1 跳过：采集首次 PPG 后启用'})}\n\n"
            yield f"event: complete\ndata: {json.dumps(empty_payload, ensure_ascii=False)}\n\n"
        return StreamingResponse(
            _empty_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── ⭐ 先查缓存（走统一入口 _call_qingmeng_lifestyle）──
    from ..notifications import _call_qingmeng_lifestyle
    import json as _json
    payload = body.model_dump(exclude_none=True)
    payload = await _inject_user_context(payload, db, current)
    qingnang_id = current.qingnang_id or f"user_{current.id}"

    # 从 payload 取 v_base / v_current
    v_base = payload.get("v_base") or {}
    v_current = payload.get("v_current") or v_base

    cached_data = await _call_qingmeng_lifestyle(
        v_base=v_base,
        v_current=v_current,
        qingnang_id=qingnang_id,
        city=payload.get("city") or current.city or None,
        provider=payload.get("provider") or body.provider or None,
    )

    # ── 缓存命中 → 直接发 complete 事件（不调 qingmeng-engine SSE）──
    # _call_qingmeng_lifestyle 成功时 data 里 engine='llm'，
    # 不可达时 engine='backend_fallback'（空结构，交给前端优雅降级）
    async def _cached_stream():
        # 先发一个 note 让前端知道是缓存加载
        yield f"event: note\ndata: {_json.dumps({'text': '从今日缓存加载...'}, ensure_ascii=False)}\n\n"
        # 直接发 complete 事件，带上完整 JSON
        yield f"event: complete\ndata: {_json.dumps(cached_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _cached_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/reasoning/treatment")
async def reasoning_treatment(body: TreatmentIn,
                              db: Session = Depends(get_db),
                              current: User = Depends(get_current_user)):
    """方案调整建议 — 当前方案+观测 → 调整建议 JSON（青檬引擎推理）。

    ⚠️ 双门控：stage≥4 且 is_member=True 才允许访问。
    Stage 4 方剂级是会员隐藏功能，不在公开说明中提及。
    """
    m = compute_maturity(current, db)
    if m["stage"] < 4 or not m["is_member"]:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STAGE_TOO_LOW",
                "message": "此功能需要更成熟的数字模型和会员权限。先完成更多脉搏采集和问诊吧～",
                "maturity": {
                    "stage": m["stage"],
                    "name": m["name"],
                    "next_target": m["next_target"],
                    "missing_signals": m["missing_signals"],
                },
            },
        )
    return await _forward_reasoning(
        "/v1/reasoning/treatment",
        body.model_dump(exclude_none=True),
        db, current,
    )


class AnchorExplainIn(BaseModel):
    """时空锚点大白话解读 — 用户点卡片触发
    
    兼容两套字段名：
      旧字段（前端 AnchorTimelineCard）：ganzhi, dangling, feixing, jianchu, chong...
      新字段（时空调候引擎）：lingshou, wuxing_status, jianchu_advice, tiao_hou, spacetime_ctx
    """
    ganzhi: str | None = None
    dangling: str | None = None
    feixing: str | None = None
    jianchu: str | None = None
    chong: str | None = None
    shaxiang: str | None = None
    richuxing: str | None = None
    pengzu: str | None = None
    su: str | None = None
    yuxiaji: str | None = None
    yi: str | None = None
    ji: str | None = None
    # —— 新时空引擎字段 ——
    lingshou: str | None = None
    lingshou_gz: str | None = None
    lingshou_cn: str | None = None
    wuxing_status: dict | None = None
    jianchu_advice: dict | None = None
    tiao_hou: dict | None = None
    spacetime_ctx: dict | None = None
    jieqi: str | None = None
    sizhu: dict | None = None


@router.post("/reasoning/anchor-explain")
async def reasoning_anchor_explain(body: AnchorExplainIn,
                                   current: User = Depends(get_current_user)):
    """今日时空锚点 AI 大白话解读 — 用户点卡片触发。
    
    自动补全时空数据：如果前端没传新时空引擎字段，服务端自己算。
    兼容两套字段名，都能正常工作。
    """
    import json as _json
    
    # ⭐ 自动补全时空数据：前端没传新字段就服务端算
    body_dict = body.model_dump(exclude_none=True)
    
    # 如果只有旧字段没新时空数据，调用 spacetime_engine 补齐
    has_new = body_dict.get('wuxing_status') or body_dict.get('lingshou') or body_dict.get('tiao_hou')
    if not has_new:
        try:
            from ...utils.spacetime_engine import spacetime_context, tiao_hou_engine
            from datetime import datetime
            ctx = spacetime_context(datetime.now())
            me_v = current.v_base or {'wood': 50, 'fire': 50, 'earth': 50, 'metal': 50, 'water': 50}
            th = tiao_hou_engine(me_v, ctx)
            body_dict.update({
                'sizhu': ctx['sizhu'],
                'lingshou_gz': ctx['lingshou_gz'],
                'lingshou_cn': {'wood':'木','fire':'火','earth':'土','metal':'金','water':'水'}.get(ctx['lingshou'], ctx['lingshou']),
                'wuxing_status': ctx['wuxing_status'],
                'jianchu': ctx['jianchu'],
                'jianchu_advice': ctx['jianchu_advice'],
                'jieqi': ctx['jieqi'].get('current_term', ''),
                'tiao_hou': th,
            })
            # 旧字段也补一下（兜底）
            if not body_dict.get('ganzhi'):
                body_dict['ganzhi'] = f"{ctx['sizhu']['year']} {ctx['sizhu']['month']} {ctx['sizhu']['day']} {ctx['sizhu']['hour']}"
            if not body_dict.get('dangling'):
                body_dict['dangling'] = ctx['lingshou_gz']
            if not body_dict.get('yi') and ctx['jianchu_advice'].get('good'):
                body_dict['yi'] = ctx['jianchu_advice']['good']
            if not body_dict.get('ji') and ctx['jianchu_advice'].get('bad'):
                body_dict['ji'] = ctx['jianchu_advice']['bad']
        except Exception as _e:
            print(f"[anchor-explain] auto spacetime fill failed: {_e}")
    
    if not body_dict:
        return {"ok": False, "message": "无锚点数据", "explain": ""}

    # 1. 组 prompt — 新字段也纳入
    fields_label = {
        "ganzhi": "四柱干支", "dangling": "当令", "feixing": "流飞星",
        "jianchu": "十二建除", "chong": "冲煞", "shaxiang": "煞方",
        "richuxing": "值日星辰", "pengzu": "彭祖百忌", "su": "二十八宿",
        "yuxiaji": "玉匣记摘录", "yi": "宜", "ji": "忌",
        "lingshou_gz": "当令干支", "lingshou_cn": "当令五行",
        "jieqi": "节气",
    }
    # wuxing_status 单独处理
    wuxing_status = body_dict.get('wuxing_status', {})
    wuxing_status_text = "、".join(
        f"{'木火土金水'[i]}形{v}" for i, v in enumerate([
            wuxing_status.get('wood',''), wuxing_status.get('fire',''),
            wuxing_status.get('earth',''), wuxing_status.get('metal',''),
            wuxing_status.get('water',''),
        ]) if v
    )
    jc_advice = body_dict.get('jianchu_advice', {})
    jc_text = ""
    if isinstance(jc_advice, dict):
        if jc_advice.get('good'): jc_text += f"宜：{jc_advice['good']} "
        if jc_advice.get('bad'): jc_text += f"忌：{jc_advice['bad']}"
    
    anchor_lines = []
    for k, v in body_dict.items():
        if k in ('wuxing_status', 'jianchu_advice', 'tiao_hou', 'spacetime_ctx', 'sizhu'):
            continue
        if v and k in fields_label:
            anchor_lines.append(f"  {fields_label[k]}：{v}")
    if wuxing_status_text:
        anchor_lines.append(f"  旺相休囚：{wuxing_status_text}")
    if jc_text:
        anchor_lines.append(f"  建除宜忌：{jc_text}")
    
    # tiao_hou 摘要
    th = body_dict.get('tiao_hou', {})
    th_summary = th.get('summary', '') if isinstance(th, dict) else ''
    
    anchor_text = "\n".join(anchor_lines)
    me_v_base = current.v_base or {}
    profile_text = "、".join(
        f"{['木','火','土','金','水'][i]}形" for i, v in enumerate([
            me_v_base.get(k, 50) for k in ['wood','fire','earth','metal','water']
        ]) if v >= 60
    ) or "各形均平"

    system_prompt = (
        "你是青囊生活管家的 AI 助手，擅长把中华传统历法（干支、旺相休囚、十二建除、冲煞、煞方、彭祖百忌等）"
        "和中医五形调候（当令五行 × 体质偏缺 = 动态建议）"
        "用现代中国人听得懂的大白话解释。\n"
        "要求：\n"
        "1. 逐行解读：把每个术语翻译成'这件事是什么意思'，用比喻或生活场景\n"
        "2. 重点解读'旺相休囚死'—— 这是今天最重要的节律标记，告诉你什么形当令旺、什么形当令死\n"
        "3. 个性化结合用户的数字模型（五形向量）—— 告诉用户'今天对你来说要特别注意什么'\n"
        "4. 如果有调候总结，优先按调候总结来解释（它是时空×体质的动态结论）\n"
        "5. 行动建议：给 2-3 条非常具体的、10 分钟内能做的小事\n"
        "6. 不要用'宜忌'之外的生僻术语，假设读者对古历法零知识\n"
        "7. 整体语气：像一个懂中医又懂生活的朋友在跟你聊天"
    )
    user_prompt = (
        f"今天的时空锚点数据：\n{anchor_text}\n"
        + (f"\n调候引擎结论（时空×体质动态推演）：{th_summary}\n" if th_summary else "")
        + f"\n我的体质数字模型（五形向量）：{me_v_base}\n"
        + f"我的主要体质倾向：{profile_text}\n\n"
        + "请逐行用大白话解读以上术语，并告诉我今天有什么要注意的。"
    )

    # 2. 调 LLM：优先 DeepSeek，其次 qingmeng-engine，最后本地 fallback
    #    —— 不走不存在的 qingmeng-engine /v1/chat；DeepSeek 直接打云端最稳
    raw_content = None

    if settings.DEEPSEEK_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(
                    f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
                    json={
                        "model": settings.DEEPSEEK_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 1400,
                    }
                )
                if r.status_code == 200:
                    raw_content = r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[anchor-explain] DeepSeek failed: {e}")

    if raw_content:
        return {"ok": True, "explain": raw_content, "engine": "deepseek"}

    # qingmeng-engine 也试一下（它有自己的推理端点但路径不同）
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{settings.QINGMENG_URL}/v1/reasoning/lifestyle",
                json={"anchor": anchor_data, "explain_mode": True},
            )
            if r.status_code == 200:
                d = r.json()
                if isinstance(d, dict) and d.get("explanation"):
                    return {"ok": True, "explain": d["explanation"], "engine": "qingmeng"}
    except Exception:
        pass

    # 3. fallback —— 本地 rule-based 大白话（无 LLM 但有固定话术 + 术语词典）
    return {
        "ok": True,
        "explain": _local_anchor_fallback(anchor_data),
        "engine": "local_fallback",
        "note": "青檬引擎暂不可用，以下为固定术语解读",
    }


def _local_anchor_fallback(anchor: dict) -> str:
    """本地 fallback：把术语翻译成大白话词典 + 基础建议
    
    兼容新旧两套字段：
      旧字段：dangling, feixing, jianchu, chong, shaxiang, pengzu, su, ganzhi
      新字段：wuxing_status, jianchu_advice, tiao_hou, lingshou_gz, lingshou_cn, jieqi
    """
    glossary = {
        "dangling": ("当令时辰",
                     "就是今天值班的时辰，相当于'今天的小时长'。"
                     "这个时段里身体节律会按这个走。"),
        "feixing": ("流飞星",
                    "九宫飞星图里今天转到的那颗星，对应不同方位和气场。"
                    "比如吉星在你卧室方向，适合打扫；凶星在书房，今天别熬夜。"),
        "jianchu": ("十二建除",
                    "古代把每天分成'建除满平定执破危成收开闭'十二种状态。"
                    "比如'破'日不适合开新事物，'成'日适合签合同/领证。"),
        "chong": ("冲煞",
                  "今天和什么生肖/地支相冲——古代说'冲'就是容易惹不愉快，"
                  "比如冲狗，属狗的朋友今天说话做事注意点就行，不是什么大事。"),
        "shaxiang": ("煞方",
                     "这个方向今天气场不太好，能避开就避开。"
                     "比如煞东，今天尽量别往东边跑太远。"),
        "richuxing": ("值日星辰",
                      "今天值班的那颗星。吉星值班心情好办事顺，凶星值班别做重大决定。"),
        "pengzu": ("彭祖百忌",
                   "彭祖（传说活了 800 岁的寿星）总结的'这一天别做什么'。"
                   "比如'丙不修灶'就是丙日别修灶台，老祖宗的经验谈。"),
        "su": ("二十八宿",
               "天上 28 颗值班的星星。每颗有不同性格——角宿适合出行，亢宿适合聚会。"),
        "ganzhi": ("干支",
                   "天干地支组合起来记日子的方法，比如'甲辰'就是第 41 天。"
                   "它是古代历法的骨架，所有宜忌都从它推出来。"),
        "lingshou_gz": ("当令干支",
                        "就是当令五行的干支表达——比如戊戌就是当令土。"
                        "当令的意思是今天这个五行'值班'，它的气场最强。"),
        "lingshou_cn": ("当令五行",
                        "今天的主角五行。当令的气场最强，其他五行围绕它转。"
                        "比如当令土——今天脾胃经最活跃，健脾的效果比平时好。"),
        "jieqi": ("节气",
                  "二十四节气之一，标示季节转换的节点。"
                  "每个节气后天地气场切换，饮食作息要跟着调整。"),
    }

    # 旺相休囚死 —— 新时空引擎核心
    wuxing_status = anchor.get('wuxing_status', {})
    if wuxing_status:
        wx_text = "、".join(
            f"{'木火土金水'[i]}形{v}" for i, v in enumerate([
                wuxing_status.get('wood',''), wuxing_status.get('fire',''),
                wuxing_status.get('earth',''), wuxing_status.get('metal',''),
                wuxing_status.get('water',''),
            ]) if v
        )
        glossary['wuxing_status'] = ("旺相休囚死",
                                     f"今天的五形节律状态：{wx_text}。"
                                     "旺=当令气场最强（今天补这个形效果最好）；"
                                     "死=被当令之气克制（今天别碰这个形的调理，换时辰）；"
                                     "相=当令所生（顺风顺水）；"
                                     "休=生当令之气（低调收敛）；"
                                     "囚=被当令所克（能不碰就不碰）。")

    # 建除宜忌
    jc_advice = anchor.get('jianchu_advice', {})
    if isinstance(jc_advice, dict):
        jc_parts = []
        if jc_advice.get('good'): jc_parts.append(f"宜：{jc_advice['good']}")
        if jc_advice.get('bad'): jc_parts.append(f"忌：{jc_advice['bad']}")
        if jc_parts:
            glossary['jianchu_advice'] = ("建除宜忌", "、".join(jc_parts))

    # 调候引擎总结 —— 最有价值的新数据
    th = anchor.get('tiao_hou', {})
    if isinstance(th, dict) and th.get('summary'):
        glossary['tiao_hou'] = ("时空调候结论",
                                 th['summary'] + "\n\n"
                                 "——这是青囊调候引擎用'当下时空 × 你的体质'动态算出的结论。"
                                 "不是简单的'缺土补土'，而是考虑了'今天土旺可以借势补、木死别碰木形调理'等节律。")

    lines = []
    # 先放调候结论（最重要）
    if 'tiao_hou' in glossary:
        label, tip = glossary.pop('tiao_hou')
        lines.append(f"**{label}**：{tip}")
        lines.append("")

    # 再放旺相休囚
    if 'wuxing_status' in glossary:
        label, tip = glossary.pop('wuxing_status')
        lines.append(f"**{label}**：{tip}")
        lines.append("")

    # 再放其他术语
    for k, v in anchor.items():
        if k in ("yi", "ji", "wuxing_status", "jianchu_advice", "tiao_hou",
                 "spacetime_ctx", "sizhu", "jianchu_yi", "jianchu_ji",
                 "yi_list", "ji_list"):
            continue
        if k in glossary and v:
            label, tip = glossary[k]
            lines.append(f"**{label}**（{v}）：{tip}")

    # 建除宜忌
    if 'jianchu_advice' in glossary:
        label, tip = glossary.pop('jianchu_advice')
        lines.append(f"**{label}**：{tip}")

    # 宜忌单独
    if anchor.get("yi"):
        lines.append(f"\n✅ **今天宜**：{anchor['yi']}")
    if anchor.get("ji"):
        lines.append(f"⚠️ **今天忌**：{anchor['ji']}")

    lines.append(
        "\n---\n💡 这是青囊的本地术语词典解读。"
        "等青檬引擎恢复后，会给你更个性化的大白话解释（结合你的体质数字模型）。"
    )
    return "\n".join(lines)


