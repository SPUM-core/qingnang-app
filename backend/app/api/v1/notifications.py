"""notifications - 生活提醒（从用户 v_base 动态生成）"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import User, Case
from ..deps import get_current_user

router = APIRouter()

# 天干地支表
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI   = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
SHICHEN  = ["子时", "丑时", "寅时", "卯时", "辰时", "巳时", "午时", "未时", "申时", "酉时", "戌时", "亥时"]
SHICHEN_ELEM = ["水", "土", "木", "木", "土", "火", "火", "土", "金", "金", "土", "水"]


def _ganzhi_from_solar(year: int, month: int, day: int) -> tuple[str, str, str]:
    """用 lunar_python 算年/月/日干支"""
    try:
        from lunar_python import Solar
        s = Solar.fromYmd(year, month, day)
        l = s.getLunar()
        y = l.getYearInGanZhiExact()  # 年柱 (含节气切换)
        m = l.getMonthInGanZhiExact() # 月柱
        d = l.getDayInGanZhiExact()   # 日柱
        return y, m, d
    except Exception:
        # 简化 fallback（不精确，仅作兜底）
        def y_ganzhi(y):
            return TIAN_GAN[(y - 4) % 10] + DI_ZHI[(y - 4) % 12]
        return y_ganzhi(year), "", ""


# 从 SPUM 引擎后端动态生成（MVP：返回硬编码 + 用户 v_base 适配）
def _generate_reminders(v_base: dict) -> dict:
    weak = [w for w, val in v_base.items() if val and val < 50]
    hot = [w for w, val in v_base.items() if val and val > 70]

    # 基础宜·忌
    cloth_good, cloth_bad = [], []
    food_good, food_bad = [], []
    home = []
    absolute_avoid = []

    if "earth" in weak:
        food_good += [{"title": "小米粥（早餐）", "desc": "入脾经·温养土形"},
                      {"title": "蒸蛋·红枣莲子芡实", "desc": "温润补中"}]
        home += [{"title": "床头移离窗户 2 米+", "desc": "酉时金旺克木煞", "urgent": True},
                 {"title": "客厅 3-8 盆阔叶绿植", "desc": "空间补木·助气结疏解"}]
        absolute_avoid += [{"title": "苦寒直折（黄连/黄芩/大黄）", "desc": "直接伤土形",
                            "reason": "与湿遏治疗路径完全冲突"}]

    if "water" in weak:
        food_good.append({"title": "温淡盐水（晨起）", "desc": "唤醒载流体循环"})
        home.append({"title": "书房加湿器", "desc": "滋水护印·脑力空间降温"})
        absolute_avoid.append({"title": "岫玉/翡翠/黑曜石", "desc": "寒色矿物·直接抑制火形",
                               "reason": "已活体验证有效"})

    if "wood" in hot:
        cloth_good.append({"title": "今日宜穿：绿色/青色", "desc": "木形补肝 · 疏解气结"})
        cloth_bad.append({"title": "冷色调·深蓝/暗灰", "desc": "加剧水形沉潜·加重湿遏"})
        home.append({"title": "卧室暖黄 2700K 灯光", "desc": "助相火归位·入眠快"})
        absolute_avoid.append({"title": "安眠药（强制关闭木环）", "desc": "绝对禁止",
                               "reason": "与温和重建路径冲突"})

    if "fire" in hot:
        food_bad += [{"title": "浓茶/咖啡", "desc": "提神耗阴·相火更妄"},
                     {"title": "辛辣·生姜过量", "desc": "短期火↑但耗水"}]

    return {
        "cloth_good": cloth_good, "cloth_bad": cloth_bad,
        "food_good": food_good, "food_bad": food_bad,
        "home": home, "absolute_avoid": absolute_avoid,
        "suitable_weak": weak, "suitable_hot": hot,
    }


@router.get("/today")
def today_reminders(db: Session = Depends(get_db),
                    current: User = Depends(get_current_user)):
    """今日生活提醒 - 全部从用户 v_base 动态生成"""
    v = current.v_base or {}
    # 优先用 case.v_baseline（如果有建档）
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if case and case.v_baseline:
        v = case.v_baseline

    r = _generate_reminders(v)

    # 今日时空锚点（动态计算）
    import datetime
    now = datetime.datetime.now()
    shichen_index = (now.hour + 1) // 2 % 12
    gz_year, gz_month, gz_day = _ganzhi_from_solar(now.year, now.month, now.day)

    # 当前状态摘要（基于 v_base 强弱，不再硬编码胡运涛）
    state_parts = []
    if r["suitable_weak"]:
        state_parts.append("偏弱: " + "、".join(r["suitable_weak"]))
    if r["suitable_hot"]:
        state_parts.append("偏旺: " + "、".join(r["suitable_hot"]))
    state = " · ".join(state_parts) if state_parts else "五形调和"

    return {
        "anchor": {
            "ganzhi": f"{gz_year}年 {gz_month}月 {gz_day}日",
            "dangling": SHICHEN[shichen_index],
            "dangling_elem": SHICHEN_ELEM[shichen_index],
            "yi": "养生·调理·静养",
            "ji": "大动·辛辣·冷饮",
            "state": state,
        },
        "timeline": [
            {"period": "子时", "elem": "水", "desc": "😴 必睡", "type": "critical"},
            {"period": "寅时", "elem": "木", "desc": "搓腰·深呼吸", "type": "personal"},
            {"period": "卯时", "elem": "木", "desc": "温淡盐水", "type": "good"},
            {"period": "辰时", "elem": "土", "desc": "小米粥", "type": "good"},
            {"period": "午时", "elem": "火", "desc": "闭目20分", "type": "good"},
            {"period": "未时", "elem": "土", "desc": "八段锦", "type": "personal"},
            {"period": "申时", "elem": "金", "desc": "散步40分", "type": "good"},
            {"period": "酉时", "elem": "金", "desc": "⚠️ 减工作", "type": "warn"},
            {"period": "戌时", "elem": "土", "desc": "泡脚15min", "type": "good"},
            {"period": "亥时", "elem": "水", "desc": "放下手机", "type": "good"},
        ],
        **r,
    }
