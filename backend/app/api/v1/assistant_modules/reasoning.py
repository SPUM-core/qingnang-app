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

# 二十八宿名
_XIU = ["角", "亢", "氐", "房", "心", "尾", "箕", "斗", "牛", "女", "虚", "危",
        "室", "壁", "奎", "娄", "胃", "昴", "毕", "觜", "参", "井", "鬼", "柳",
        "星", "张", "翼", "轸"]
# 值日星宿宜忌（简化）
_XIU_YI = {
    "角": ["嫁娶", "出行", "冠笄", "祭祀"],
    "亢": ["破屋", "坏垣", "除服", "解除"],
    "氐": ["嫁娶", "订盟", "开市", "祭祀"],
    "房": ["祭祀", "祈福", "出行", "冠笄"],
    "心": ["祭祀", "祈福", "斋醮", "安床"],
    "尾": ["嫁娶", "出行", "移徙", "入宅"],
    "箕": ["祭祀", "祈福", "出行", "移徙"],
    "斗": ["祭祀", "祈福", "安床", "开光"],
    "牛": ["祭祀", "祈福", "出行", "移徙"],
    "女": ["祭祀", "祈福", "安床", "移徙"],
    "虚": ["祭祀", "祈福", "安床", "移徙"],
    "危": ["祭祀", "祈福", "安床", "移徙"],
    "室": ["祭祀", "祈福", "出行", "移徙", "嫁娶"],
    "壁": ["祭祀", "祈福", "出行", "移徙", "嫁娶"],
    "奎": ["祭祀", "祈福", "出行", "移徙"],
    "娄": ["祭祀", "祈福", "出行", "移徙"],
    "胃": ["祭祀", "祈福", "出行", "移徙"],
    "昴": ["祭祀", "祈福", "出行", "移徙"],
    "毕": ["祭祀", "祈福", "出行", "移徙", "嫁娶"],
    "觜": ["祭祀", "祈福", "出行", "移徙"],
    "参": ["祭祀", "祈福", "出行", "移徙"],
    "井": ["祭祀", "祈福", "出行", "移徙", "嫁娶"],
    "鬼": ["祭祀", "祈福", "出行", "移徙"],
    "柳": ["祭祀", "祈福", "出行", "移徙"],
    "星": ["祭祀", "祈福", "出行", "移徙"],
    "张": ["祭祀", "祈福", "出行", "移徙", "嫁娶"],
    "翼": ["祭祀", "祈福", "出行", "移徙"],
    "轸": ["祭祀", "祈福", "出行", "移徙"],
}

# 天干地支索引 → 建除神推算（简化）
_TIAN_GAN_IDX = {c: i for i, c in enumerate("甲乙丙丁戊己庚辛壬癸")}
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
    feixing_day = l.getDayNineStar()    # 日飞星
    feixing_year = l.getYearNineStar()  # 年飞星
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
    
    # ════ 二十八宿（从角开始，按日支 + 日干推算）════
    # 传统算法：从"角"开始，甲子日为"角"，按六十甲子顺序排
    day_zhi_idx = _DI_ZHI_IDX.get(day_zhi, 0)
    day_gan_idx = _TIAN_GAN_IDX.get(day_gan, 0)
    xiu_idx = (day_zhi_idx * 2 + day_gan_idx) % 28  # 简化算法
    xiu = _XIU[xiu_idx]
    xiu_yi = _XIU_YI.get(xiu, [])
    
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
        "xiu": xiu, "xiu_yi": xiu_yi,
        "pengzu": pengzu,
        # 其他
        "na_yin": {"year": na_yin_year, "month": l.getMonthNaYin(), "day": na_yin_day},
        "feixing": {"year": feixing_year, "day": feixing_day},
        "tianshen": tianshen,
        # 时辰
        "timeline": timeline,
        # 玉匣记
        "yuxiaji": yuxiaji,
    }


# ═══════════════════════════════════════════════════════════
# Rule-based lifestyle fallback — 根据 v_base 五形向量 + 今日干支 + 协纪辨方生成建议
# ═══════════════════════════════════════════════════════════
def _fallback_lifestyle(v: dict, payload: dict) -> dict:
    from datetime import date
    from ....utils.trajectory_algorithm import get_liunian, ganzhi_main_elem

    # 1. 今日干支 + 黄历
    today = date.today()
    almanac = _almanac_today(today.year, today.month, today.day)
    ln = get_liunian(today.year)
    day_elem = ganzhi_main_elem(ln["g"], ln["z"])  # 今日五行主气

    # 2. v_base 五形 → 找最弱/最旺
    WUXING = ["wood", "fire", "earth", "metal", "water"]
    WX_CN = {"wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"}
    WX_COLOR = {"wood": "青绿", "fire": "赤红", "earth": "黄褐", "metal": "白灰", "water": "黑蓝"}
    WEAK_FOOD = {
        "wood": ["菠菜", "芹菜", "韭菜", "青梅", "枸杞"],
        "fire": ["红枣", "桂圆", "樱桃", "番茄"],
        "earth": ["山药", "薏米", "南瓜", "红薯"],
        "metal": ["雪梨", "银耳", "百合", "莲藕"],
        "water": ["黑豆", "黑芝麻", "海带", "栗子"],
    }
    STRONG_AVOID = {
        "wood": ["辛辣", "茴香", "花椒"],  # 木旺火 → 火过旺需忌
        "fire": ["煎炸", "烧烤", "辣椒"],   # 火生土 → 土过旺需忌
        "earth": ["油腻", "甜品", "蜂蜜"],   # 土生金 → 金过旺需忌
        "metal": ["生冷", "冰饮", "生菜"],   # 金生水 → 水过旺需忌
        "water": ["咸腌", "酱菜", "盐"],     # 水生木 → 木过旺需忌
    }

    scores = {w: v.get(w, 50) for w in WUXING}
    weak = min(scores, key=scores.get)   # 最弱
    strong = max(scores, key=scores.get)  # 最旺

    # 3. 穿衣建议（补最弱）
    cloth_good = [{
        "id": "cloth-1",
        "title": f"多穿{WX_COLOR[weak]}系",
        "desc": f"补{WX_CN[weak]}形，抑制{WX_CN[strong]}形过旺",
        "reason": f"v_base {WX_CN[weak]}={scores[weak]:.0f}（最低），{WX_CN[strong]}={scores[strong]:.0f}（最高）",
        "detail": f"以{WX_COLOR[weak]}色的上衣、围巾或配饰为主，贴身层优先{WX_COLOR[weak]}色；"
                  f"避开{WX_COLOR[strong]}系大面积穿搭。",
        "source_ref": "《黄帝内经·素问》——五色入五脏",
    }]
    cloth_bad = []
    if day_elem == strong:
        cloth_bad.append({
            "id": "cloth-avoid-day",
            "title": f"忌穿{WX_COLOR[day_elem]}系",
            "desc": f"今日{WX_CN[day_elem]}主气，穿同色助旺过甚",
            "reason": f"今日干支 {ln['g']}{ln['z']} 主气 {WX_CN[day_elem]}",
            "detail": f"今日避免{WX_COLOR[day_elem]}色整体穿搭；若衣柜所限，可用其他颜色配饰做中和。",
            "source_ref": "《千金要方》——随四时五行调节起居服色",
        })

    # 4. 饮食建议
    food_good = [{
        "id": "food-1",
        "title": f"宜吃{WEAK_FOOD[weak][0]}等补{WX_CN[weak]}食物",
        "desc": "、".join(WEAK_FOOD[weak]) + f" — 按相生律补{WX_CN[weak]}形",
        "reason": f"五形相生：弱{WX_CN[weak]}需要滋养",
        "detail": f"选其中1-2样，少量多次、细嚼慢咽；以煮、蒸、炖为主，避免煎炸油腻；"
                  f"建议安排在辰时（7-9点）或午时（11-13点）食用。",
        "source_ref": f"《本草纲目》——{WX_CN[weak]}类食材补益说明",
    }]
    food_bad = [{
        "id": "food-bad-1",
        "title": f"忌{STRONG_AVOID[strong][0]}",
        "desc": "、".join(STRONG_AVOID[strong]) + f" — 避免助{WX_CN[strong]}形过旺",
        "reason": f"{WX_CN[strong]}形分数 {scores[strong]:.0f} 最高",
        "detail": f"今日少吃或不吃上述食物；若偶尔摄入，注意控制分量，一次不超过一拳体积；"
                  f"出现腹胀、口干等不适立即停止。",
        "source_ref": f"《黄帝内经·素问》——五味入五脏，过食则伤",
    }]

    # 5. 今日宜忌（干支 + v_base 综合）
    yi_text = f"今日{WX_CN[day_elem]}日·宜{WX_COLOR[weak]}系·养{WX_CN[weak]}形"
    ji_text = f"忌穿{WX_COLOR[strong]}系·忌{STRONG_AVOID[strong][0]}等助{WX_CN[strong]}食物"

    # 6. 住房/作息提醒
    home = []
    if strong == "fire":
        home.append({"id": "home-1", "title": "午后宜独处静养", "desc": "火形旺易焦躁，避开午后阳气盛时段",
                     "detail": "13:00-15:00 尽量安排安静活动，避免高强度社交与争论；可闭目养神10分钟。",
                     "source_ref": "《黄帝内经·素问》——阳气者，一日而主外，日中而阳气隆"})
    if weak == "water":
        home.append({"id": "home-2", "title": "亥时泡脚养肾", "desc": "21:00-23:00 是肾经主时，泡脚 40℃/15min",
                     "detail": "用40℃左右温水，水位没过踝关节，泡15分钟微微出汗即可；"
                               "泡后注意保暖，忌立即吹风；有糖尿病足或静脉曲张者慎泡。",
                     "source_ref": "《千金要方》——以冷水暖足浴，以肾经相应"})
    if weak == "earth":
        home.append({"id": "home-3", "title": "辰时养胃", "desc": "7:00-9:00 辰时脾经旺，宜温热早餐",
                     "detail": "辰时（7-9点）吃温热早餐，以小米粥、山药、南瓜等易消化为主；"
                               "忌空腹冰饮、忌过量。",
                     "source_ref": "《伤寒杂病论》——脾胃为后天之本"})

    # 7. 禁忌
    absolute = []
    relative = []
    if scores[strong] - scores[weak] > 25:
        relative.append({
            "id": "rel-1",
            "title": f"慎用过{WX_CN[strong]}类事物",
            "desc": f"避免{WX_CN[strong]}形进一步过旺（差值 {scores[strong]-scores[weak]:.0f}）",
            "reason": "五形差 > 25 触发警示",
        })

    # 8. 时辰出行提醒（SPUM × 时辰五行 × 黄历建除）
    travel = []
    for item in almanac["timeline"]:
        # 时辰五行与 v_base 的生克关系
        sc_elem_cn = item["elem"]
        sc_elem_map = {"木": "wood", "火": "fire", "土": "earth", "金": "metal", "水": "water"}
        sc_elem_en = sc_elem_map.get(sc_elem_cn, "wood")
        # 该时辰五行在 v_base 中是旺还是弱
        sc_score = v.get(sc_elem_en, 50)
        if sc_score < 40:
            personal_hint = f"此时辰{sc_elem_cn}形弱，宜补{['木','火','土','金','水'][(list(sc_elem_map.values()).index(sc_elem_en) + 1) % 5]}形活动"
        elif sc_score > 65:
            personal_hint = f"此时辰{sc_elem_cn}形旺，宜舒缓{sc_elem_cn}形过旺"
        else:
            personal_hint = f"此时辰与你的体质平和"
        
        # 时辰建除黄历宜忌
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
                      f"SPUM 提示：{personal_hint}。",
            "source_ref": "《协纪辨方书》· 十二建除 + 《玉匣记》· 彭祖百忌",
        })
    
    # 9. 破煞方案（SPUM × 黄历交叉）
    solutions = []
    if almanac["jianchu"] in ("破", "危"):
        solutions.append({
            "id": "sol-jianchu",
            "title": f"今日{almanac['jianchu']}日化解方案",
            "desc": f"黄历{almanac['jianchu']}日主冲克，建议用五行通关法化解",
            "target": almanac["jianchu"],
            "steps": [
                f"第一步：避开{almanac['jianchu_ji'][:3]}等不宜事项",
                f"第二步：多做{almanac['jianchu_yi'][:3]}等合宜之事",
                "第三步：遇事三思而后行，避免冲动决策",
            ],
            "reason": "建除神煞化解原则：避凶就吉，五行通关",
        })
    
    if almanac["chong"] and weak in ("wood", "water"):
        solutions.append({
            "id": "sol-chong",
            "title": f"冲煞日五行通关",
            "desc": f"今日{almanac['chong']}，你的{WX_CN[weak]}形偏弱，需主动通关",
            "target": f"冲{almanac['chong']}",
            "steps": [
                f"第一步：多穿{WX_COLOR[weak]}色衣物配饰",
                f"第二步：饮食侧重{WEAK_FOOD[weak][:3]}等补{WX_CN[weak]}食材",
                f"第三步：避开{WX_COLOR[strong]}色大面积穿搭",
            ],
            "reason": "冲煞日 + 五形偏弱 → 双压叠加，需主动调和",
        })
    
    if scores[strong] - scores[weak] > 25:
        diff = scores[strong] - scores[weak]
        solutions.append({
            "id": "sol-vbase",
            "title": f"五形偏胜修正方案（差值 {diff:.0f}）",
            "desc": f"你的{WX_CN[strong]}形明显过旺，{WX_CN[weak]}形明显偏弱",
            "target": f"补{WX_CN[weak]}抑{WX_CN[strong]}",
            "steps": [
                f"第一步：连续3天多穿{WX_COLOR[weak]}系",
                f"第二步：每天吃1-2样{WEAK_FOOD[weak]}",
                f"第三步：暂时减少{STRONG_AVOID[strong]}摄入",
                f"第四步：每天15分钟静坐，调息养{WX_CN[weak]}形",
            ],
            "reason": f"五形差 {diff:.0f} > 25 阈值，触发修正方案",
        })
    
    # 10. 矿物避忌（简化 SPUM 五色石对应）
    stone_map = {
        "wood": {"good": ["绿幽灵", "孔雀石", "翡翠"], "bad": ["白水晶"]},
        "fire": {"good": ["红玛瑙", "石榴石", "碧玺"], "bad": ["黑玛瑙", "黑曜石"]},
        "earth": {"good": ["黄水晶", "琥珀", "蜜蜡"], "bad": ["青金石"]},
        "metal": {"good": ["白水晶", "银饰", "白金"], "bad": ["红玛瑙"]},
        "water": {"good": ["蓝水晶", "黑曜石", "海蓝宝"], "bad": ["黄水晶"]},
    }
    stone_good = stone_map.get(weak, {}).get("good", [])
    stone_bad = stone_map.get(strong, {}).get("bad", [])
    stone = []
    if stone_good:
        stone.append({
            "id": "stone-good",
            "title": f"宜佩戴{'、'.join(stone_good)}",
            "desc": f"补{WX_CN[weak]}形，选其中1-2件贴身佩戴",
            "reason": f"五色入五脏——{WX_COLOR[weak]}色矿物补益{WX_CN[weak]}形",
        })
    if stone_bad:
        stone.append({
            "id": "stone-bad",
            "title": f"暂避{'、'.join(stone_bad)}",
            "desc": f"可能助{WX_CN[strong]}形过旺，今日不戴为宜",
            "reason": f"同类相感——{WX_COLOR[strong]}色矿物助旺已过旺之形",
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
    
    # ════ 12. 时辰 × v_base 生克 → 助我/平/耗我（吉时轴三态）════
    SHICHEN_ELEM_EN = {"木": "wood", "火": "fire", "土": "earth", "金": "metal", "水": "water"}
    for item in almanac["timeline"]:
        sc_elem = SHICHEN_ELEM_EN.get(item["elem"], "wood")
        base_el = weak  # 以最弱之形为参照（补弱为助我）
        rel = _wx_relation(base_el, sc_elem)  # 弱形 vs 时辰五行
        sc_score = v.get(sc_elem, 50)
        
        # 三态判定（SPUM × 时辰）
        if rel == "generate_me":      # 时辰生我 → 助我（吉）
            ptype, plabel = "good", "助我"
        elif rel == "overcome_me":    # 时辰克我 → 耗我（凶）
            ptype, plabel = "bad", "耗我"
        elif rel == "same" and sc_score < 45:  # 同五行但弱 → 助我
            ptype, plabel = "good", "助我"
        elif rel == "same" and sc_score > 65:  # 同五行但过旺 → 平
            ptype, plabel = "neutral", "平"
        elif rel == "generated_by_me":  # 我生时辰 → 微耗
            ptype, plabel = "neutral", "平"
        else:
            ptype, plabel = "neutral", "平"
        
        item["personal_type"] = ptype
        item["personal_label"] = plabel

    # ════ 13. 飞星落宫 → 今日方位（宜取/宜避）════
    feixing_day_str = almanac["feixing"]["day"]  # "一白水天枢"
    # 从字符串里提取数字（飞星号）
    import re as _re
    m = _re.search(r'(\d)', feixing_day_str)
    fx_num = int(m.group(1)) if m else 1
    fx = _FEIXING_MAP.get(fx_num, _FEIXING_MAP[1])
    fx_el = fx["elem"]
    fx_dir = fx["dir"]
    fx_gong = fx["gong"]
    
    # 宜取 = 飞星生我 / 同我（飞星五行 × v_base 最弱之形）
    fx_rel_weak = _wx_relation(weak, fx_el)
    fx_rel_strong = _wx_relation(strong, fx_el)
    
    # 宜取方: 飞星生弱形 或 飞星同弱形（弱形分数低 → 同形补之）
    if fx_rel_weak in ("generate_me",) or (fx_rel_weak == "same" and scores[weak] < 45):
        good_dir, good_reason = fx_dir, f"日飞星{fx['name']}落{fx_gong}宫（{fx_dir}），生我{WX_CN[weak]}形"
        # 宜避方 = 对冲宫
        bad_dir = {"正北": "正南", "正南": "正北", "正东": "正西", "正西": "正东",
                   "东北": "西南", "西南": "东北", "西北": "东南", "东南": "西北"}.get(fx_dir, "正南")
        bad_reason = f"对冲{fx_dir}，九星叠位火气重，易上火"
    elif fx_rel_strong in ("overcome_me",) or (fx_rel_strong == "same" and scores[strong] > 65):
        good_dir, good_reason = fx_dir, f"日飞星{fx['name']}落{fx_gong}宫（{fx_dir}），宜纳气"
        bad_dir, bad_reason = fx_dir, f"飞星同{WX_CN[strong]}形，今日{WX_CN[strong]}已过旺，避免叠加"
    else:
        good_dir, good_reason = fx_dir, f"日飞星{fx['name']}落{fx_gong}宫（{fx_dir}），平和之气，宜居中"
        bad_dir = {"正北": "正南", "正南": "正北", "正东": "正西", "正西": "正东",
                   "东北": "西南", "西南": "东北", "西北": "东南", "东南": "西北"}.get(fx_dir, "正南")
        bad_reason = f"对冲方位，九星叠位火气重"
    
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

    # ════ 14. 替换表（不要 A → 改做 B）════
    swaps = []
    # 基于 v_base 偏胜
    if scores[strong] - scores[weak] > 15:
        # 过旺之形对应的典型"坏事"
        swap_map = {
            "wood":  {"bad": "久坐不动 · 肝木郁结", "good": "每坐 1 小时起身 3 分钟舒展"},
            "fire":  {"bad": "午后急躁易怒 · 心火上炎", "good": "午后闭目养神 10 分钟静坐"},
            "earth": {"bad": "思虑过度 · 脾土湿困", "good": "每 2 小时抬头远眺 30 秒"},
            "metal": {"bad": "说话急促 · 肺气耗散", "good": "说话放慢半拍，每句之间留 1 秒"},
            "water": {"bad": "熬夜过 23 点 · 肾水亏虚", "good": "22:30 前放下手机准备入睡"},
        }
        swaps.append({
            "bad": swap_map.get(strong, {}).get("bad", "无"),
            "good": swap_map.get(strong, {}).get("good", "无"),
            "reason": f"{WX_CN[strong]}形分数 {scores[strong]:.0f} 偏旺",
        })
    
    # 时辰宜忌
    today_elem = {"木": "wood", "火": "fire", "土": "earth", "金": "metal", "水": "water"}.get(
        ln["g"][1] if len(ln["g"]) > 1 else "木", "wood")
    if today_elem in ("wood",):
        swaps.append({"bad": "寅卯时 3-7 点剧烈运动", "good": "移至申酉时 15-19 点", "reason": "肝木当令忌泄"})
    if almanac["jianchu"] in ("破", "危", "闭"):
        swaps.append({"bad": "今日大事冲动决策", "good": "遇事三思，暂缓签约/出行", "reason": f"{almanac['jianchu']}日宜静不宜动"})
    if weak == "water":
        swaps.append({"bad": "午后饮浓茶/咖啡", "good": "13-15 时改饮温水或淡枸杞茶", "reason": "肾形偏弱，忌浓茶夺肾"})
    
    # 最多 3 条
    swaps = swaps[:3]
    
    # ════ 组装完整返回 ════
    anchor = almanac  # 整个黄历对象作为 anchor
    anchor["ganzhi"] = f"{almanac['ganzhi_year']}{almanac['ganzhi_month']}{almanac['ganzhi_day']}"
    anchor["dangling_elem"] = WX_CN[weak]
    anchor["state"] = f"补{WX_CN[weak]}抑{WX_CN[strong]}"
    anchor["engine"] = "rule_almanac_v2"
    
    return {
        "anchor": anchor,
        "timeline": almanac["timeline"],  # ✅ 12 时辰 + personal_type(助我/平/耗我)
        "orientation": orientation,       # ✅ 今日方位（飞星落宫 → 宜取/宜避）
        "swaps": swaps,                   # ✅ 替换表（不要 A → 改做 B）
        "cloth_reminders": cloth_good + cloth_bad,
        "food_good": food_good,
        "food_bad": food_bad,
        "home_reminders": home,
        "absolute_avoid": absolute,      # ✅ 有内容了
        "relative_avoid": relative,      # ✅ 可能有
        "stone": stone,                  # ✅ 新增：矿物避忌
        "travel": travel,                # ✅ 新增：时辰出行
        "solutions": solutions,          # ✅ 新增：破煞方案
        "engine": "rule_almanac_v3",
        "note": "协纪辨方 + 玉匣记 + SPUM 五行交叉推演（v3: 加 personal_type/方位/替换）",
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
    """时空锚点大白话解读 — 前端点"今日时空锚点"卡片弹 modal 调用"""
    ganzhi: str | None = None           # 干支：甲辰年 甲戌月 ...
    dangling: str | None = None         # 当令时辰
    feixing: str | None = None          # 流飞星
    jianchu: str | None = None          # 十二建除
    chong: str | None = None            # 冲煞
    shaxiang: str | None = None         # 煞方
    richuxing: str | None = None        # 值日星辰
    pengzu: str | None = None           # 彭祖百忌
    su: str | None = None               # 二十八宿
    yuxiaji: str | None = None          # 玉匣记摘录
    yi: str | None = None               # 宜
    ji: str | None = None               # 忌


@router.post("/reasoning/anchor-explain")
async def reasoning_anchor_explain(body: AnchorExplainIn,
                                   current: User = Depends(get_current_user)):
    """今日时空锚点 AI 大白话解读 — 用户点卡片触发。
    
    调 qingmeng-engine 的 chat 流式，让 SPUM 引擎用通俗语言解释：
    - 每个术语是什么意思（当令时辰、流飞星、十二建除、冲煞...）
    - 今天对你的体质有什么实际影响
    - 给 2-3 条马上能做的生活建议
    
    qingmeng-engine 不可达时返回本地 rule-based 解读（无 LLM 但有固定话术）。
    """
    import json as _json
    anchor_data = body.model_dump(exclude_none=True)
    if not anchor_data:
        return {"ok": False, "message": "无锚点数据", "explain": ""}

    # 1. 组 prompt
    fields_label = {
        "ganzhi": "干支", "dangling": "当令时辰", "feixing": "流飞星",
        "jianchu": "十二建除", "chong": "冲煞", "shaxiang": "煞方",
        "richuxing": "值日星辰", "pengzu": "彭祖百忌", "su": "二十八宿",
        "yuxiaji": "玉匣记摘录", "yi": "宜", "ji": "忌",
    }
    anchor_text = "\n".join(
        f"  {fields_label.get(k, k)}：{v}" for k, v in anchor_data.items()
    )
    me_v_base = current.v_base or {}
    profile_text = "、".join(
        f"{['木','火','土','金','水'][i]}形" for i, v in enumerate([
            me_v_base.get(k, 50) for k in ['wood','fire','earth','metal','water']
        ]) if v >= 60
    ) or "各形均平"

    system_prompt = (
        "你是青囊生活管家的 AI 助手，擅长把中华传统历法（干支、流飞星、十二建除、冲煞、煞方、彭祖百忌等）"
        "用现代中国人听得懂的大白话解释。\n"
        "要求：\n"
        "1. 逐行解读：把每个术语翻译成'这件事是什么意思'，用比喻或生活场景\n"
        "2. 个性化结合用户的数字模型（五形向量）—— 告诉用户'今天对你来说要特别注意什么'\n"
        "3. 行动建议：给 2-3 条非常具体的、10 分钟内能做的小事\n"
        "4. 不要用'宜忌'之外的生僻术语，假设读者对古历法零知识\n"
        "5. 整体语气：像一个懂中医又懂生活的朋友在跟你聊天"
    )
    user_prompt = (
        f"今天的时空锚点数据：\n{anchor_text}\n\n"
        f"我的体质数字模型（五形向量）：{me_v_base}\n"
        f"我的主要体质倾向：{profile_text}\n\n"
        "请逐行用大白话解读以上术语，并告诉我今天有什么要注意的。"
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
    """本地 fallback：把术语翻译成大白话词典 + 基础建议"""
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
    }

    lines = []
    for k, v in anchor.items():
        if k in ("yi", "ji"):
            continue
        if k in glossary:
            label, tip = glossary[k]
            lines.append(f"**{label}**（{v}）：{tip}")

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


