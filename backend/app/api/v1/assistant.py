"""assistant - 青囊管家 AI 对话代理（转发到本地 qingmeng-engine）"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
import httpx
import json
import time

from ...database import get_db
from ...models import User, Case, Observation, TreatmentPlan, ChatMessage, LifeSignal
from ...config import settings
from ..deps import get_current_user
from ...utils.life_signal_extractor import extract_signals, signals_to_dict_list
from ...utils.conversation_analyzer import analyze_conversation
from ...utils.maturity import compute_maturity, STAGE_DEFS

router = APIRouter()


# ═══════════════════════════════════════════════════════
# 合规词表 — 消费级非医疗定位
# ═══════════════════════════════════════════════════════
# 禁止输出的医疗词汇 → 安全替换（去医疗化）
PROHIBITED_WORDS = {
    # 诊断类
    "诊断": "生活观察", "确诊": "初步判断", "辨证": "梳理",
    # 治疗类
    "治疗": "调理", "治愈": "改善", "根治": "持续调养", "疗效": "体感变化",
    "药到病除": "调理有进展", "疗效显著": "体感有变化",
    # 处方/药疗类
    "处方": "方案", "脉诊": "脉搏采集", "问诊": "聊聊你的情况",
    # 中医专业术语（对 C 端用户也替换）
    "舌诊": "舌象观察", "望闻问切": "日常观察",
    "黄连": "苦寒药材", "黄芩": "苦寒药材", "大黄": "苦寒药材",
    "附子": "大补药材", "肉桂": "温热药材",
}
# 额外禁止（直接屏蔽整词出现）
STRIP_WORDS = [
    "中医诊断", "治疗方案", "药物治疗", "医学建议",
]


def compliance_filter(text: str, stage: int = 3) -> str:
    """LLM 输出合规后处理 — 替换禁用词 + 去重相邻重复

    Args:
        text: LLM 原始输出
        stage: 用户数字模型成熟度 1-4
               Stage 1-3 时自动 strip 方剂/处方/药材名（合规硬约束）
               Stage 4 时放行（会员深层调平）
    """
    import re
    if not text:
        return text
    # 1. 整词替换
    for bad, good in PROHIBITED_WORDS.items():
        text = text.replace(bad, good)
    # 2. 直接剔除的短语
    for bad in STRIP_WORDS:
        text = text.replace(bad, "")

    # ── Stage 合规硬约束：Stage < 4 时屏蔽方剂/处方/药材名 ──
    if stage < 4:
        # 屏蔽方剂/处方/药材相关（合规红线）
        STAGE_STRIP = [
            "方剂", "处方", "药材", "药味",
            "参苓白术散", "苓桂术甘汤", "柴胡疏肝散", "四物汤",
            "桂枝汤", "麻黄汤", "补中益气汤",
            "黄芪", "党参", "当归", "川芎", "白术", "茯苓", "桂枝",
            "白芍", "甘草", "陈皮", "半夏", "柴胡", "黄芩",
            "黄连", "附子", "肉桂", "干姜", "生姜", "大枣",
            "熟地", "生地", "山药", "枸杞子", "菊花", "茯苓皮",
        ]
        for term in STAGE_STRIP:
            text = text.replace(term, "")

    # 3. 去重相邻重复替换词
    text = re.sub(r'([^/\s]+)[\s]*[\/、][\s]*\1', r'\1', text)
    return text


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)  # [{role, content}] 最近 N 轮
    provider: str = "spum"  # "spum"=青檬引擎(本地), "deepseek"=云端, 未来可扩展


# ═══════════════════════════════════════════════════════
# System Prompt 构建器 - 注入用户完整数字模型 + 成熟度阶段约束
# ═══════════════════════════════════════════════════════
def build_system_prompt(user: User, db: Session, maturity: dict | None = None) -> str:
    """构建青囊管家 AI 的 System Prompt（2000+ 字完整上下文）

    maturity 预计算可避免重复查询——assistant/chat 路由已预先算好。
    传 None 时内部重新计算。
    """
    if maturity is None:
        maturity = compute_maturity(user, db)

    # 基础约束 — 合规 + 语气
    parts = [
        "你是青囊管家，基于 SPUM（结构化五行统一模型）的健康生活顾问。",
        "请记住以下关于用户的完整信息，所有回答必须基于这些数据。",
        "",
        "【重要约束】",
        "- 去医疗化术语：用气结、湿遏、土枯等生活化表达，不要用脉弦、苔腻等专业术语",
        "- 所有建议必须具体可执行（比如'戌时泡脚40℃15分钟'，不是'注意养生'）",
        "- 回答至少 150 字，分 2-4 段",
        "- 不要说'建议您去看医生'——青囊管家就是陪伴式的健康顾问",
        "- 禁止说'治愈'、'治疗'、'根治'、'药到病除'等疗效性表述",
        "- 语气温暖、像朋友，不是机器",
        "",
        f"【数字模型成熟度：Stage {maturity['stage']} {maturity['name']}】",
        maturity["llm_constraint"],
        "",
        f"【用户基本信息】",
        f"姓名：{user.nickname}",
        f"性别：{user.gender}",
        f"出生日期：{user.birth_date}（{user.birth_hour}）",
        f"身高体重：{user.height}cm / {user.weight}kg",
    ]

    case = db.query(Case).filter(Case.user_id == user.id).first()
    if case:
        vi = case.v_innate or {}
        vb = case.v_baseline or {}
        vc = case.v_current or {}
        parts += [
            "",
            "【八字】",
            f"{case.ganzhi_year}年 {case.ganzhi_month}月 {case.ganzhi_day}日",
            f"完整八字：{case.bazi}",
            "",
            "【五形先天基底】（出生时推导）",
            f"木:{vi.get('wood','')} 火:{vi.get('fire','')} "
            f"土:{vi.get('earth','')} 金:{vi.get('metal','')} "
            f"水:{vi.get('water','')}",
            "",
            "【调理前观测基线】",
            f"木:{vb.get('wood','')} 火:{vb.get('fire','')} "
            f"土:{vb.get('earth','')} 金:{vb.get('metal','')} "
            f"水:{vb.get('water','')}",
            "",
            "【当前最新观测】",
            f"木:{vc.get('wood','')} 火:{vc.get('fire','')} "
            f"土:{vc.get('earth','')} 金:{vc.get('metal','')} "
            f"水:{vc.get('water','')}",
            "",
            "【状态提示】",
            case.syndrome or "（暂无）",
            f"主要诉求：{case.chief_complaint or '（暂无）'}",
        ]

        # 最新 3 次 PPG 观测
        obs_list = db.query(Observation).filter(
            Observation.case_id == case.id
        ).order_by(Observation.observed_at.desc()).limit(3).all()
        if obs_list:
            parts.append("")
            parts.append("【最近 PPG 脉诊观测】")
            for i, ob in enumerate(obs_list):
                parts.append(f"{i+1}. SQI={ob.sqi} 五形ΔF: " +
                            f"木{ob.delta_f.get('wood',0):+.2f} 火{ob.delta_f.get('fire',0):+.2f} "
                            f"土{ob.delta_f.get('earth',0):+.2f} 金{ob.delta_f.get('metal',0):+.2f} "
                            f"水{ob.delta_f.get('water',0):+.2f}")
                if ob.syndrome_hint:
                    parts.append(f"   诊断提示：{ob.syndrome_hint}")

        # 当前方案
        if case.current_plan_id:
            plan = db.query(TreatmentPlan).filter(TreatmentPlan.id == case.current_plan_id).first()
            if plan:
                parts += [
                    "",
                    f"【当前调理方案 {plan.version}】",
                    f"策略：{plan.strategy}",
                    f"处方：{plan.prescription}",
                    "药材：" + "、".join(plan.herbs or []),
                    "生活指导：" + "；".join(
                        [f"{la['time']}→{la['action']}" for la in (plan.life_advice or [])]
                    ),
                    "绝对禁忌：" + "、".join(plan.avoidances or []),
                ]

    # ── 根据 v_current / v_baseline 动态生成用户特征摘要（通用 SPUM 逻辑）─
    vc = (case.v_current or case.v_baseline or {}) if case else {}
    vb = (case.v_baseline or {}) if case else {}
    wuxing_labels = {"wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"}

    weak = [w for w, val in vc.items() if isinstance(val, (int, float)) and val < 45]
    strong = [w for w, val in vc.items() if isinstance(val, (int, float)) and val > 65]
    drift = []
    for k in ["wood", "fire", "earth", "metal", "water"]:
        cv = vc.get(k); bv = vb.get(k)
        if isinstance(cv, (int, float)) and isinstance(bv, (int, float)) and cv != bv:
            drift.append(f"{wuxing_labels[k]}{cv-bv:+.0f}")

    parts += [
        "",
        "【当前特征摘要】（基于观测向量自动生成）",
        f"偏弱形: {'、'.join(wuxing_labels[w] for w in weak) if weak else '五形调和'}",
        f"偏强形: {'、'.join(wuxing_labels[w] for w in strong) if strong else '五形调和'}",
        f"基线→当前漂移: {' '.join(drift) if drift else '无显著漂移'}",
        "",
        "现在，请根据以上用户数据，用温暖的口吻回答用户的问题。",
    ]

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════
# 本地规则引擎 fallback（qingmeng-engine 不可达时，通用回答）
# 不再硬编码胡运涛案例
# ═══════════════════════════════════════════════════════
def _generate_generic_reply(user: User, db: Session, keyword: str) -> str:
    """基于用户 v_base 动态生成通用回答"""
    case = db.query(Case).filter(Case.user_id == user.id).first()
    v = {}
    if case:
        v = case.v_current or case.v_baseline or {}
    weak = [w for w, val in v.items() if isinstance(val, (int, float)) and val < 45]
    w_name = {"wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"}
    weak_names = [w_name[w] for w in weak] if weak else ["整体"]

    if "睡" in keyword or "失眠" in keyword:
        return (f"早睡是你调理的基础——晚上22:30前尽量躺下。"
                f"你的{weak_names[0]}形偏弱，睡眠是补它最直接的方式。"
                f"睡前1小时放下手机，避免蓝光抑制松果体。")
    if "吃" in keyword or "饮食" in keyword or "早餐" in keyword:
        return (f"饮食核心原则：温{weak_names[0]}、避寒、避燥。"
                f"推荐：早餐小米粥+蒸蛋（温润补中）；午餐绿色蔬菜+优质蛋白；"
                f"晚餐山药粥+少量瘦肉（健脾不助湿）。"
                f"避免冷饮、辛辣、晚餐后进食。")
    if "运动" in keyword or "锻炼" in keyword:
        return (f"推荐：申时（15-17点）散步30分钟，这个时辰气活跃，最适合疏通气机。"
                f"卯时（5-7点）搓腰1分钟——{weak_names[0]}形水化的关键窗口。"
                f"八段锦每天15分钟，配合呼吸，整体调和五形。")
    if "泡脚" in keyword:
        return (f"泡脚是你{weak_names[0]}形调理的好方法——戌时（19-21点）泡脚，"
                f"水温40℃左右，15分钟即可。微微出汗就好，不要大汗淋漓。"
                f"泡完脚擦干立刻躺下，趁暖入睡效果最好。")
    return (f"让我根据你的数字模型来分析——你{weak_names[0]}形偏弱，"
            f"这是当前调理的核心方向。"
            f"你想深入聊哪一方面？睡眠、饮食、还是运动？")


# ═══════════════════════════════════════════════════════
# Action Router — AI 调用应用功能的路由表
#
# 核心设计：AI 在对话回复后，根据用户数据状态和本轮对话内容，
# 动态决定要不要引导用户执行某个 App 内操作。
# 返回的 actions 是一组 {label, route, reason, priority}，
# 前端渲染成可点击按钮（RouterLink to=route）。
# ═══════════════════════════════════════════════════════

def _generate_actions(user: User, db: Session, user_message: str,
                      analysis: dict | None, extracted_signals: list,
                      maturity: dict | None = None) -> list:
    """根据用户状态 + 成熟度阶段 → 决定青囊管家应该引导哪些 App 功能。

    路由表（前端 Router path）：
      /collect/ppg       → 脉象采集
      /notifications     → 生活提醒
      /case       → 体质档案（先天基底 + 时间线）
      /onboarding     → 建档（如果没建档）
      /discover → 医生咨询
      /discover    → 知识卡片
      /shop              → 商城

    成熟度过滤（关键）：
      Stage 1 娱乐级 — 无 /shop /treatment 路由；/onboarding /collect/ppg 强引导
      Stage 2 食疗级 — 可引导 /shop（食疗食材）；无 /treatment 路由
      Stage 3 调理级 — 可引导完整生活提醒；无 /treatment 路由
      Stage 4 方剂级 — 全部开放（含 /treatment）

    返回 list[dict]，每条 = {"label": str, "route": str, "icon": str, "priority": "high"/"medium"/"low"}
    """
    if maturity is None:
        maturity = compute_maturity(user, db)
    stage = maturity["stage"]

    actions = []
    case = db.query(Case).filter(Case.user_id == user.id).first()
    obs_count = db.query(Observation).filter(
        Observation.case_id == case.id if case else None
    ).count() if case else 0

    msg = (user_message or "").lower()

    # 规则 1：没建档 → 强引导建档
    if not case or not case.v_baseline:
        actions.append({"label": "先完成数字模型建档", "route": "/onboarding",
                        "icon": "📋", "priority": "high"})
        return actions  # 建档是 P0，其他都等建档后再说

    # 规则 2：没脉诊数据 → 强引导采集
    if obs_count == 0:
        actions.append({"label": "去做第一次脉搏采集", "route": "/collect/ppg",
                        "icon": "💓", "priority": "high"})

    # 规则 3：提到"脉诊/脉搏/采集/PPG" → 引导采集
    if any(kw in msg for kw in ["脉诊", "脉搏", "采集", "ppg", "测一测", "量一下"]):
        actions.append({"label": "立即做脉搏采集", "route": "/collect/ppg",
                        "icon": "💓", "priority": "high"})

    # ── Stage 过滤：Stage 1 不给饮食/穿搭以外的建议 ──
    if stage >= 2:
        # 规则 4：提到"吃/饮食/早餐/午餐/晚餐/忌口" → 引导生活提醒的饮食 tab
        if any(kw in msg for kw in ["吃", "饮食", "早餐", "午餐", "晚餐", "忌口", "宜", "食谱"]):
            actions.append({"label": "今日饮食宜忌速查", "route": "/notifications",
                            "icon": "🍜", "priority": "medium"})

        # 规则 5：AI 给了 suggestions → 有 "diet/herb" 类建议 → Stage≥2 可引导商城（食疗食材）
        if analysis:
            for s in analysis.get("suggestions", []):
                cat = s.get("category", "")
                if cat in ("diet", "herb") and len(actions) < 3:
                    if stage >= 4 or cat != "herb":  # Stage 1-3 不给药材商城入口
                        actions.append({"label": f"看看相关调养物品", "route": "/shop",
                                        "icon": "🛒", "priority": "low"})
                        break

    # ── Stage 过滤：Stage 1-2 不给作息/家居方位建议 ──
    if stage >= 3:
        # 规则 6：提到"睡眠/失眠/睡/熬夜" → 引导知识卡片（睡眠类）
        if any(kw in msg for kw in ["睡", "失眠", "熬夜", "入睡", "多梦", "早醒"]):
            actions.append({"label": "看看睡眠改善方法", "route": "/discover",
                            "icon": "🌙", "priority": "medium"})

    # 规则 7：提到"方案/调理/档案/模型" → 引导体质档案（全阶段开放）
    if any(kw in msg for kw in ["方案", "调理", "档案", "模型", "体质", "先天"]):
        actions.append({"label": "查看我的体质档案", "route": "/case",
                        "icon": "📋", "priority": "medium"})

    # 规则 8：有 extracted_signals → 引导生活提醒（Stage≥2 才给生活建议入口）
    if extracted_signals and stage >= 2 and len(actions) < 3:
        actions.append({"label": "把这些信号加到我的生活提醒", "route": "/notifications",
                        "icon": "🔔", "priority": "low"})

    # Stage 4 专属：方剂方案入口（隐藏——不进公开路由表，仅通过 /treatment 端点间接访问）
    # 注意：不主动给 Stage < 4 的用户展示任何 treatment 相关入口

    # 去重 + 最多 3 条（避免按钮过载）
    seen_routes = set()
    deduped = []
    priority_order = {"high": 0, "medium": 1, "low": 2}
    for a in sorted(actions, key=lambda x: priority_order.get(x["priority"], 9)):
        if a["route"] not in seen_routes:
            seen_routes.add(a["route"])
            deduped.append(a)
        if len(deduped) >= 3:
            break

    return deduped


# ═══════════════════════════════════════════════════════
# 高频结构化问题 — 引擎直接返回，绕过 LLM
# ═══════════════════════════════════════════════════════

def _intent_shortcut(message: str, brief: dict | None, stage: int = 1) -> str | None:
    """检测高频结构化问题，用 daily_brief 数据直接拼自然语言回答。

    Stage 守卫（关键）：
      Stage 1 → 只放行日期/干支类（节气宜忌），屏蔽食物/颜色/宜忌
      Stage 2+ → 全部放行

    返回 None = 不是高频问题 OR 阶段不允许（走 LLM 路径，那里有 stage constraint 注入）
    返回 str = 引擎直接生成的回答（零延迟，确定性）
    """
    if not brief or not message:
        return None

    msg = message.lower()

    # ── Stage 1 守卫：只放节气/干支/日期，屏蔽食物/颜色/宜忌 ──
    if stage == 1:
        # 仅干支/日期/节气类关键词放行
        if not any(k in msg for k in ("干支", "今天几号", "今天什么日", "今日干支", "节气")):
            return None  # 走 LLM，那里有 stage 约束注入
        # 但也要检查 stage 1 禁止的类别
        if any(k in msg for k in ("吃什么", "饮食", "食物", "颜色", "穿什么", "宜忌", "宜什么", "宜")):
            return None

    # ── Stage 2+：正常处理所有类别 ──

    # ── 颜色/穿搭类 ──
    if any(k in msg for k in ("颜色", "穿什么", "配饰", "穿搭", "衣服", "好看")):
        cloth = brief.get("cloth", [])
        if not cloth:
            return None
        lines = []
        cloth_ok = [c for c in cloth if "宜穿" in c["title"]]
        cloth_bad = [c for c in cloth if c["title"].startswith("避免") or "忌" in c["title"]]
        accessories = [c for c in cloth if "配饰" in c["title"]]

        if cloth_ok:
            colors = [c["title"].replace("宜穿：", "").replace("色系", "") for c in cloth_ok]
            lines.append("根据你的 SPUM 状态，推荐你试试 %s。" % "、".join(colors))
            for c in cloth_ok[:2]:
                lines.append("  · %s —— %s" % (c["title"], c["desc"]))
        if accessories:
            for a in accessories:
                lines.append("另外，%s。" % a["desc"])
        if cloth_bad:
            lines.append("要注意 %s。" % "、".join(c["title"] for c in cloth_bad[:2]))
        return "\n".join(lines)

    # ── 食物/饮食类 ──
    if any(k in msg for k in ("吃什么", "饮食", "食物", "推荐吃", "今天吃", "食谱", "早餐", "午餐", "晚餐")):
        fg = brief.get("food_good", [])
        fb = brief.get("food_bad", [])
        if not fg and not fb:
            return None
        lines = []
        anchor = brief.get("anchor", {})
        state = anchor.get("state", "")
        if state and state != "调和":
            lines.append("你当前状态偏 %s，" % state)

        if fg:
            lines.append("今天推荐 %s。" % "、".join(f["title"] for f in fg))
            for f in fg[:3]:
                lines.append("  · %s —— %s" % (f["title"], f["desc"]))
        if fb:
            lines.append("这些尽量别碰：%s。" % "、".join(f["title"] for f in fb))
        return "\n".join(lines)

    # ── 宜忌/今日类 ──
    if any(k in msg for k in ("宜忌", "宜什么", "忌什么", "今天注意", "今天宜", "今天忌", "今天适合", "今日宜忌")):
        anchor = brief.get("anchor", {})
        if not anchor:
            return None
        lines = []
        gz = anchor.get("ganzhi", "")
        if gz:
            line = "今天是 %s 日" % gz
            if anchor.get("chong"):
                line += "，冲 %s" % anchor["chong"]
            lines.append(line + "。")
        if anchor.get("yi"):
            lines.append("宜：%s。" % anchor["yi"])
        if anchor.get("ji"):
            lines.append("忌：%s。" % anchor["ji"])
        state = anchor.get("state", "")
        if state and state != "调和":
            lines.append("你当前状态：%s。" % state)
        return "\n".join(lines)

    # ── 干支/日期类 ──
    if any(k in msg for k in ("干支", "今天几号", "今天什么日", "今日干支")):
        anchor = brief.get("anchor", {})
        if not anchor or not anchor.get("ganzhi"):
            return None
        gz = anchor["ganzhi"]
        line = "今天是 %s" % gz
        if anchor.get("chong"):
            line += "，冲 %s" % anchor["chong"]
        line += "。"
        return line

    return None  # 不匹配任何高频 intent → 走 LLM


# ═══════════════════════════════════════════════════════
# 主路由 - /v1/assistant/chat
# ═══════════════════════════════════════════════════════
@router.post("/chat")
async def chat(body: ChatIn,
               db: Session = Depends(get_db),
               current: User = Depends(get_current_user)):
    """青囊管家 AI 对话（Phase 4 — 全链路确定性产出物注入）

    完整管线:
      1. 构建 System Prompt（DB 查询用户上下文）
      2. httpx.POST /v1/reasoning/daily_brief — 拿一揽子确定性产出物
         （真干支 + 病理标签 + 食物宜忌 + 时辰养生 + 家居/穿搭建议 + 禁忌）
      3. 把全量确定性产出物注入 system prompt
      4. 调 qingmeng-engine chat completions（LLM 只做语言转述）
      5. 合规后处理

    LLM 职责降级：用温暖的口吻转述确定性产出物，不得编造日期/宜忌/食物。
    """
    # ── 0. 预计算成熟度（build_system_prompt + 合规过滤 + actions 都要用）──
    maturity = compute_maturity(current, db)

    # ── 1. 构建 System Prompt ──
    system_prompt = build_system_prompt(current, db, maturity=maturity)

    # ── 2. 拿 daily_brief 确定性产出物（3s timeout，失败静默）──
    brief = None
    case = db.query(Case).filter(Case.user_id == current.id).first()
    v_for_engine = None
    if case:
        v_for_engine = case.v_current or case.v_baseline or case.v_innate
    if v_for_engine:
        try:
            async with httpx.AsyncClient(timeout=3.0) as tc:
                tr = await tc.post(
                    f"{settings.QINGMENG_URL}/v1/reasoning/daily_brief",
                    json={"v_base": v_for_engine},
                )
                if tr.status_code == 200:
                    brief = tr.json()
        except Exception:
            brief = None

    # ── 3. NEW: 高频结构化问题 → 引擎直接返回自然语言（绕过 LLM）──
    shortcut_reply = _intent_shortcut(body.message, brief, stage=maturity["stage"])
    if shortcut_reply is not None:
        shortcut_reply = compliance_filter(shortcut_reply, stage=maturity["stage"])
        # shortcut 路径也需要持久化对话 + 抽信号
        case = db.query(Case).filter(Case.user_id == current.id).first()
        signals_now = []
        try:
            user_msg = ChatMessage(
                user_id=current.id, case_id=case.id if case else None,
                role="user", content=body.message, provider="engine_direct",
            )
            db.add(user_msg)
            db.flush()
            db.add(ChatMessage(
                user_id=current.id, case_id=case.id if case else None,
                role="assistant", content=shortcut_reply, provider="engine_direct",
            ))
            hits = extract_signals(body.message)
            if hits:
                signal_dicts = signals_to_dict_list(hits)
                for sd in signal_dicts:
                    existing = db.query(LifeSignal).filter(
                        LifeSignal.user_id == current.id,
                        LifeSignal.tag == sd["tag"],
                        LifeSignal.label == sd["label"],
                    ).first()
                    if not existing:
                        db.add(LifeSignal(
                            user_id=current.id, case_id=case.id if case else None,
                            source="chat", source_id=user_msg.id, **sd,
                        ))
                signals_now = signal_dicts
                user_msg.signals = signal_dicts
            db.commit()
        except Exception:
            db.rollback()

        # shortcut 路径也生成 actions（无 analysis，传 None）
        try:
            shortcut_actions = _generate_actions(
                user=current, db=db,
                user_message=body.message,
                analysis=None,
                extracted_signals=signals_now or [],
                maturity=maturity,
            )
        except Exception:
            shortcut_actions = []

        return {
            "reply": shortcut_reply,
            "engine": "engine_direct",
            "latency_ms": 0,
            "qingmeng_online": True,
            "brief_context": brief,
            "extracted_signals": signals_now,
            "actions": shortcut_actions,
            "analysis": None,
            "maturity": {
                "stage": maturity["stage"],
                "name": maturity["name"],
                "icon": maturity["icon"],
                "next_target": maturity["next_target"],
            },
        }

    # ── 4. 把 daily_brief 浓缩后注入 system prompt ──
    if brief:
        a = brief.get("anchor", {})
        brief_sections = [
            "",
            "【今日背景数据 — 引擎生成，供你参考】",
        ]

        # ── 高频用户问题的数据优先放前面 ──

        # 食物（"今天吃什么" 最高频）
        fg = brief.get("food_good", [])
        fb = brief.get("food_bad", [])
        if fg:
            brief_sections.append("推荐吃：" + "、".join(f['title'] for f in fg))
        if fb:
            brief_sections.append("避免吃：" + "、".join(f['title'] for f in fb))

        # 颜色（"我适合什么颜色" 次高频）
        cloth = brief.get("cloth", [])
        if cloth:
            cloth_items = []
            for c in cloth:
                if c["title"].startswith("宜穿"):
                    cloth_items.append(c["title"].replace("宜穿：", ""))
                elif "配饰" in c["title"]:
                    cloth_items.append(c["title"])
            if cloth_items:
                brief_sections.append("适合颜色/配饰：" + "、".join(cloth_items))

        # 宜忌（"今天宜忌什么"）
        if a:
            if a.get("yi"):
                brief_sections.append("宜：" + a["yi"])
            if a.get("ji"):
                brief_sections.append("忌：" + a["ji"])

        # 干支日期
        if a:
            line = "今日干支：" + a.get("ganzhi", "")
            if a.get("chong"):
                line += "，冲 " + a["chong"]
            brief_sections.append(line)

        # 诊断（放最后，因为容易让 LLM 陷入理论推演）
        diag_sum = brief.get("diagnose_summary", "")
        pathologies = brief.get("pathologies", [])
        if diag_sum or pathologies:
            brief_sections.append("用户状态：" + (a.get("state", "") + " · " + diag_sum if a.get("state") else diag_sum))
            for p in pathologies[:2]:
                brief_sections.append("  · " + p)

        # 约束（软语气）
        brief_sections += [
            "",
            "回答要求：",
            "- 先看【今日背景数据】里的具体内容（推荐食物、适合颜色等），自然融入回答",
            "- 用温暖的口吻，像朋友聊天一样，不要逐条罗列数据",
            "- 可以补充生活化的解释",
            "- 用户问'吃什么'优先用推荐食物，问'颜色'优先用适合颜色，不要长篇理论",
            "",
        ]

        system_prompt = "\n".join(brief_sections) + "\n" + system_prompt

    # ── 4. 组装 messages ──
    messages = [{"role": "system", "content": system_prompt}]
    for h in (body.history or [])[-10:]:
        if h.get("role") in ("user", "assistant"):
            messages.append({"role": h["role"], "content": h.get("content", "")})
    messages.append({"role": "user", "content": body.message})

    # ── 5. 按用户选择的 provider 调 LLM ──
    llm_ok = False
    latency_ms = 0
    reply_text = ""
    provider_used = body.provider or "spum"

    if provider_used == "deepseek":
        # ── DeepSeek 云端 ──
        if settings.DEEPSEEK_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    start = time.time()
                    r = await client.post(
                        f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": settings.DEEPSEEK_MODEL,
                            "messages": messages,
                            "max_tokens": 800,
                        }
                    )
                    latency_ms = int((time.time() - start) * 1000)
                    if r.status_code == 200:
                        data = r.json()
                        reply_text = data["choices"][0]["message"]["content"]
                        llm_ok = True
            except Exception:
                llm_ok = False
        # 没有 API KEY 就 fallback
        if not settings.DEEPSEEK_API_KEY:
            llm_ok = False
    else:
        # ── SPUM 本地模型（青檬引擎） ──
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                h = await client.get(f"{settings.QINGMENG_URL}/health")
                if h.status_code == 200:
                    llm_ok = True
                    start = time.time()
                    r = await client.post(
                        f"{settings.QINGMENG_URL}/v1/chat/completions",
                        json={
                            "model": settings.QINGMENG_MODEL,
                            "messages": messages,
                            "max_tokens": 800,
                        }
                    )
                    latency_ms = int((time.time() - start) * 1000)
                    if r.status_code == 200:
                        data = r.json()
                        reply_text = data["choices"][0]["message"]["content"]
        except Exception:
            llm_ok = False

    # ── 6. Fallback：规则引擎 ──
    if not llm_ok:
        reply_text = _generate_generic_reply(current, db, body.message)
        latency_ms = 0

    # ── 7. 合规后处理 ──
    reply_text = compliance_filter(reply_text, stage=maturity["stage"])

    # engine 标签反映真实执行路径
    engine_tag = {
        "deepseek": "deepseek" if llm_ok else "local_fallback",
        "spum": "qingmeng" if llm_ok else "local_fallback",
    }.get(provider_used, "qingmeng" if llm_ok else "local_fallback")

    # ── 8. 持久化对话 + 抽取生活信号（青囊生活管家的数据化核心）──
    case = db.query(Case).filter(Case.user_id == current.id).first()
    signals_user_msg = []        # 返回给前端的本轮信号（规则引擎快速命中）
    analysis_result: dict = {}   # LLM 解析出的完整结构化数据（异步落库）
    try:
        # 8a. 落 user message
        user_msg = ChatMessage(
            user_id=current.id, case_id=case.id if case else None,
            role="user", content=body.message,
            provider=engine_tag, latency_ms=latency_ms,
        )
        db.add(user_msg)
        db.flush()
        user_msg_id = user_msg.id

        # 8b. 落 assistant reply
        ai_msg = ChatMessage(
            user_id=current.id, case_id=case.id if case else None,
            role="assistant", content=reply_text,
            provider=engine_tag, latency_ms=latency_ms,
        )
        db.add(ai_msg)
        db.flush()
        ai_msg_id = ai_msg.id

        # 8c. 快速规则引擎抽取 → 立即返回给前端（低延迟）
        hits = extract_signals(body.message)
        if hits:
            signal_dicts = signals_to_dict_list(hits)
            for sd in signal_dicts:
                # 全局去重（同用户同 tag 同 label 只存一次）
                existing = db.query(LifeSignal).filter(
                    LifeSignal.user_id == current.id,
                    LifeSignal.tag == sd["tag"],
                    LifeSignal.label == sd["label"],
                ).first()
                if not existing:
                    db.add(LifeSignal(
                        user_id=current.id, case_id=case.id if case else None,
                        source="chat", source_id=user_msg.id, **sd,
                    ))
            signals_user_msg = signal_dicts
            user_msg.signals = signal_dicts

        # 8d. LLM 深度解析（主力，10s timeout）
        #    输出 signals（补充规则没覆盖的）+ pathologies + suggestions + chief_complaint
        analysis_result = await analyze_conversation(
            user_message=body.message,
            assistant_reply=reply_text,
            history=body.history,
            provider=provider_used,
        )

        # 8e. LLM signals 写 DB（去重）
        llm_sigs = analysis_result.get("signals", []) if analysis_result else []
        for s in llm_sigs:
            tag = s.get("tag")
            label = s.get("label")
            if not tag or not label:
                continue
            existing = db.query(LifeSignal).filter(
                LifeSignal.user_id == current.id,
                LifeSignal.tag == tag,
                LifeSignal.label == label,
            ).first()
            if not existing:
                from datetime import datetime
                db.add(LifeSignal(
                    user_id=current.id, case_id=case.id if case else None,
                    tag=tag, label=label,
                    raw_text=f"[llm] {body.message[:80]}",
                    confidence=s.get("confidence"),
                    source="chat_llm", source_id=user_msg.id,
                ))

        # 8f. AI 回复的 signals 快照也存回 user_msg（规则+LLM 合并）
        if llm_sigs:
            # 合并规则信号 + LLM 信号 → 给前端
            seen_tags = {h.tag for h in hits}
            for s in llm_sigs:
                if s.get("tag") not in seen_tags:
                    signals_user_msg.append({
                        "tag": s["tag"], "label": s["label"],
                        "confidence": s.get("confidence"),
                    })

        # 8g. 把完整 LLM 分析结果挂到 assistant message.signals 字段（复用 signals 字段存复杂 JSON）
        #     前端以后可以直接从 ChatMessage.signals 读到 pathologies / suggestions / chief_complaint
        if analysis_result:
            ai_msg.signals = analysis_result

        db.commit()
    except Exception:
        db.rollback()  # 持久化失败不影响返回对话结果

    # ── 9. Action Router：决定青囊管家应该引导用户做什么 ──
    try:
        actions = _generate_actions(
            user=current, db=db,
            user_message=body.message,
            analysis=analysis_result or None,
            extracted_signals=signals_user_msg or [],
            maturity=maturity,
        )
    except Exception:
        actions = []

    # ── 10. 如果 analysis 里有 chief_complaint 且 Case.chief_complaint 为空 → 自动回填 ──
    if analysis_result and analysis_result.get("chief_complaint"):
        cc = analysis_result["chief_complaint"]
        if case and not case.chief_complaint:
            case.chief_complaint = cc
            try:
                db.commit()
            except Exception:
                db.rollback()

    return {
        "reply": reply_text,
        "engine": engine_tag,
        "provider": provider_used,
        "latency_ms": latency_ms,
        "llm_online": llm_ok,
        "brief_context": brief,
        "extracted_signals": signals_user_msg,
        # ── AI 调用应用功能（Tool Calling）──
        "actions": actions,
        # ── LLM 深度解析结果（结构化给前端直接消费）──
        "analysis": {
            "pathologies": (analysis_result or {}).get("pathologies", []),
            "suggestions": (analysis_result or {}).get("suggestions", []),
            "chief_complaint": (analysis_result or {}).get("chief_complaint", ""),
        } if analysis_result else None,
        # ── 用户数字模型成熟度（阶段徽章 + 下次引导目标）──
        "maturity": {
            "stage": maturity["stage"],
            "name": maturity["name"],
            "icon": maturity["icon"],
            "next_target": maturity["next_target"],
            "is_member": maturity["is_member"],
        },
    }


# ═══════════════════════════════════════════════════════
# Chat 历史 + LifeSignal 存档查询
# ═══════════════════════════════════════════════════════

@router.get("/chat/messages")
async def list_chat_messages(
    limit: int = 100,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """当前用户的所有聊天记录（user + assistant 交替），返回时间升序"""
    msgs = db.query(ChatMessage).filter(
        ChatMessage.user_id == current.id,
    ).order_by(ChatMessage.created_at.asc()).limit(limit).all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "provider": m.provider,
            "latency_ms": m.latency_ms,
            "signals": m.signals,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]


@router.get("/chat/signals")
async def list_life_signals(
    tag: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """当前用户的所有 LifeSignal 存档（最近在前）

    可按 tag 过滤：bowel/sweat/sleep/appetite/menses/mood/energy/thirst/skin/breath/other
    """
    q = db.query(LifeSignal).filter(LifeSignal.user_id == current.id)
    if tag:
        q = q.filter(LifeSignal.tag == tag)
    signals = q.order_by(LifeSignal.created_at.desc()).limit(limit).all()
    return [
        {
            "id": s.id,
            "tag": s.tag,
            "label": s.label,
            "raw_text": s.raw_text,
            "confidence": s.confidence,
            "source": s.source,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in signals
    ]


@router.get("/chat/signals/summary")
async def life_signals_summary(
    days: int = 30,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """摘要：按 tag 聚合最近 N 天的信号频次 + 最新 label

    前端展示用：一个小卡片告诉用户"最近 30 天你提到过 3 次排便异常、2 次多汗..."
    """
    from datetime import datetime, timedelta
    since = func.now() - timedelta(days=days)
    rows = db.query(
        LifeSignal.tag,
        LifeSignal.label,
        func.count(LifeSignal.id).label("cnt"),
    ).filter(
        LifeSignal.user_id == current.id,
        LifeSignal.created_at >= since,
    ).group_by(LifeSignal.tag, LifeSignal.label).order_by(
        func.count(LifeSignal.id).desc()
    ).all()

    # 按 tag 聚合
    by_tag: dict[str, list] = {}
    for tag, label, cnt in rows:
        by_tag.setdefault(tag, []).append({"label": label, "count": cnt})

    return {
        "days": days,
        "total_signals": sum(r.cnt for r in rows),
        "tags": by_tag,
    }


@router.get("/maturity")
async def get_maturity(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """查询当前用户的数字模型成熟度阶段 — 前端据此显示徽章、过滤功能入口。

    返回：{ stage: 1-4, name, label, icon, score, missing_signals, next_target, is_member, details }
    注意：is_member 为 False 时即使 score ≥ 8 也锁在 Stage 3。
    """
    m = compute_maturity(current, db)
    # 把 details 展开给前端展示（profile 各项 true/false、obs_count 等）
    # 但隐藏 llm_constraint（这是给 LLM 看的 system prompt 片段，不需要暴露给前端）
    return {
        "stage": m["stage"],
        "name": m["name"],
        "label": m["label"],
        "icon": m["icon"],
        "desc": m["desc"],
        "score": m["score"],
        "max_score": 11,  # 理论满分：4+2+3+2+2
        "missing_signals": m["missing_signals"],
        "next_target": m["next_target"],
        "is_member": m["is_member"],
        "allowed_content": m["allowed_content"],
        "forbidden_content": m["forbidden_content"],
        # 展开 details 给前端做进度条
        "progress": {
            "profile_complete": m["details"].get("profile_score", 0),  # 0-4
            "has_case": m["details"].get("case_exists", False),
            "has_baseline": m["details"].get("has_baseline", False),
            "observation_count": m["details"].get("observation_count", 0),
            "inquiry_done": m["details"].get("inquiry_completed", False),
            "signal_tag_count": m["details"].get("signal_tag_count", 0),
        },
    }


@router.get("/health")
async def health():
    """检查各 provider 可用性 — 前端设置页据此显示哪些选项可用。"""
    # SPUM 本地
    spum_online = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.QINGMENG_URL}/health")
            spum_online = r.status_code == 200
    except Exception:
        pass

    # DeepSeek：只要配了 API KEY 就算可用（实际连通性在调用时检测）
    deepseek_configured = bool(settings.DEEPSEEK_API_KEY)

    return {
        "providers": {
            "spum": {
                "label": "SPUM 本地模型",
                "online": spum_online,
                "model": settings.QINGMENG_MODEL,
                "url": settings.QINGMENG_URL,
            },
            "deepseek": {
                "label": "DeepSeek 云端",
                "online": deepseek_configured,
                "model": settings.DEEPSEEK_MODEL,
                "url": settings.DEEPSEEK_BASE_URL,
            },
        },
        "default_provider": "spum",
    }


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
    """qingmeng-engine 不可达时的最小兜底。"""
    v = payload.get("v_base", {})
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
        return {
            "anchor": {"state": "离线模式", "yi": "养生", "ji": "辛辣"},
            "timeline": [], "cloth_reminders": [], "food_good": [],
            "food_bad": [], "home_reminders": [],
            "absolute_avoid": [], "relative_avoid": [],
            "engine": "backend_fallback",
        }
    if "treatment" in path:
        return {
            "current_assessment": "离线模式",
            "version_suggestion": "",
            "adjustments": [], "new_herbs": [], "remove_herbs": [],
            "updated_guidance": [], "engine": "backend_fallback",
        }
    return {"engine": "backend_fallback", "note": "unknown path"}


class DiagnoseIn(BaseModel):
    v_base: dict | None = None
    v_current: dict | None = None
    user_meta: dict | None = None


class LifestyleIn(BaseModel):
    v_base: dict | None = None
    v_current: dict | None = None


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
    """今日生活提醒 — v_base → 宜忌/衣食住行/时辰养生 JSON（青檬引擎推理）。"""
    return await _forward_reasoning(
        "/v1/reasoning/lifestyle",
        body.model_dump(exclude_none=True),
        db, current,
    )


# ═══════════════════════════════════════════════════════
# Lifestyle 流式 SSE 代理 — 透传 qingmeng-engine 的流
# ═══════════════════════════════════════════════════════

async def _inject_user_context(payload: dict, db: Session, current: User) -> dict:
    """注入用户五形向量上下文。无建档时用健康默认值优雅降级。"""
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
            # 优雅降级：健康五形调和默认值（SPUM 拓扑常数 12 附近）
            _DEFAULT_HEALTHY_V = {"wood": 50, "fire": 50, "earth": 50, "metal": 50, "water": 50}
            payload["v_base"] = _DEFAULT_HEALTHY_V
            payload["v_current"] = _DEFAULT_HEALTHY_V
            payload["user_meta"] = payload.get("user_meta") or {
                "nickname": current.nickname,
                "gender": current.gender,
                "syndrome": "未建档",
                "chief_complaint": "",
                "fallback": True,  # 标记：未建档，使用默认值
            }
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
    """今日生活提醒 — SSE 流式代理。透传青檬引擎 generating/complete 事件。"""
    payload = body.model_dump(exclude_none=True)
    payload = await _inject_user_context(payload, db, current)
    return StreamingResponse(
        _proxy_lifestyle_stream(payload),
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


def _local_bazi_fallback(body: BaziIn) -> dict:
    """lunar_python 本地八字推演 — 青檬引擎不可达时兜底。"""
    from lunar_python import Solar, Lunar

    birth_date = body.birth_date                    # "1986-08-02" 或 "1986-06-27"（阴历）
    birth_hour = body.birth_hour                    # "寅时（3-5点）" 或 None
    birth_date_type = body.birth_date_type or 'solar'

    # 解析日期
    parts = birth_date.split('-')
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])

    # 时辰映射 → 小时
    SHICHEN_HOUR = {
        '子时': 23, '丑时': 1, '寅时': 3, '卯时': 5, '辰时': 7, '巳时': 9,
        '午时': 11, '未时': 13, '申时': 15, '酉时': 17, '戌时': 19, '亥时': 21,
    }
    hour = 14  # 默认下午2点
    if birth_hour:
        for sc, h in SHICHEN_HOUR.items():
            if sc in birth_hour:
                hour = h
                break

    try:
        if birth_date_type == 'lunar':
            # 用户给的是阴历 → 先 Lunar → 再 getSolar 转成阳历真太阳时基准
            lunar = Lunar.fromYmdHms(y, m, d, hour, 0, 0)
            solar = lunar.getSolar()
        else:
            # 阳历（默认）
            solar = Solar.fromYmdHms(y, m, d, hour, 0, 0)
            lunar = solar.getLunar()
    except Exception as e:
        return {
            "bazi": "未知", "pillars": ["?", "?", "?", "?"],
            "lunar_display": "", "true_solar_time": "", "longitude": 120.0,
            "v_innate": _DEFAULT_V_INNATE, "engine": "local_fallback_error",
            "message": f"日期解析失败: {e}",
            "day_master": None, "health_index": None,
        }

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

    # ── 五行分布（直接计数法: 天干 1.0 + 地支藏干加权）──
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
        raw[TIANGAN_WXING.get(gan_list[i], 'earth')] += 1.0   # 天干各 1.0
        for wx, pct in DIZHI_HIDDEN.get(zhi_list[i], [('earth', 1.0)]):
            raw[wx] += pct                                     # 地支藏干加权

    total = sum(raw.values()) or 1.0  # 恒 ≈ 8.0（4天+4支藏干和各1.0）
    v_innate = {k: round(v / total * 100, 1) for k, v in raw.items()}

    # ── 日主旺衰分析 ──
    DAY_GAN = gan_list[2]            # 日干 = 日主
    DAY_MASTER = TIANGAN_WXING.get(DAY_GAN, 'earth')
    # 简化版旺衰: 日主五形得分 vs 月令 + 其他干支同帮
    day_master_score = raw[DAY_MASTER]
    # 月令旺度（月支同五形 = 旺 +1.0，生我 = 相 +0.5，我生/我克/克我 = 休囚 -0.3）
    MONTH_ZHI_WXING = DIZHI_HIDDEN[zhi_list[1]][0][0] if zhi_list[1] in DIZHI_HIDDEN else 'earth'

    # ── 农历精简呈现（只留核心字段）──
    try:
        lunar_cn = lunar.toString()   # "一九八七年七月二十"
        zodiac_year = lunar.getYearShengXiao()  # "兔"
        # 纳音（只取年柱+日柱）
        na_yin_year = lunar.getYearNaYin()
        na_yin_day = lunar.getDayNaYin()
    except Exception:
        lunar_cn = ""
        zodiac_year = ""
        na_yin_year = ""
        na_yin_day = ""

    return {
        "bazi": "/".join(pillars),
        "pillars": pillars,
        "ganzhi_year": pillars[0],
        "ganzhi_month": pillars[1],
        "ganzhi_day": pillars[2],
        "ganzhi_hour": pillars[3],
        # ── 精简农历呈现 ──
        "lunar_display": lunar_cn,                          # "一九八七年七月二十"
        "zodiac_year": zodiac_year,                         # "兔"
        "nayin_year": na_yin_year,                          # "炉中火"
        "nayin_day": na_yin_day,                            # "海中金"
        # ── 日主旺衰 ──
        "day_master": DAY_GAN,                              # "甲"
        "day_master_element": DAY_MASTER,                   # "wood"
        "day_master_score": round(day_master_score, 2),     # 原始计数
        # ── 其他 ──
        "lunar_raw": lunar.toFullString(),                  # 完整农历（保留可选）
        "true_solar_time": "",
        "longitude": 120.0,
        "v_innate": v_innate,
        "engine": "local_fallback",
        "message": "青檬引擎不可达，使用本地 lunar_python 推演",
    }


_DEFAULT_V_INNATE = {'wood': 50, 'fire': 50, 'earth': 50, 'metal': 50, 'water': 50}


# ═══════════════════════════════════════════════════════
# 多阶段问诊引擎（新）
# ═══════════════════════════════════════════════════════

INQUIRY_STAGES = ["initial", "deepen", "expand", "finalize", "done"]

# SPUM 范式的四个问诊阶段中文标签 + 职责
STAGE_LABELS = {
    "initial":  {"label": "主诉与核心症状", "desc": "你现在最困扰的感受是什么？"},
    "deepen":   {"label": "症状深化",     "desc": "什么时候开始的？在什么情况下加重/缓解？"},
    "expand":   {"label": "整体状态",     "desc": "饮食、睡眠、二便、精神状态怎么样？"},
    "finalize": {"label": "关键判别点",   "desc": "确认几个关键问题以锁定你的状态倾向"},
}


# ══ 1. LLM JSON 防御层 ══

def _parse_llm_json(raw: str) -> dict | None:
    """三级防御：直接 parse → 正则提取 → 预设清单。永不返回 None（最低级返回通用问题）。"""
    import re

    if not raw:
        return None

    # Level 1: 直接 json.loads
    try:
        return json.loads(raw.strip())
    except Exception:
        pass

    # Level 2: 正则提取最外层 {...}
    try:
        start = raw.index('{')
        end = raw.rindex('}') + 1
        extracted = raw[start:end]
        return json.loads(extracted)
    except Exception:
        pass

    # Level 3: 尝试 ```json ... ``` 代码块
    try:
        m = re.search(r'```json?\s*\n(.*?)```', raw, re.DOTALL)
        if m:
            return json.loads(m.group(1).strip())
    except Exception:
        pass

    return None


# ══ 2. 预设问诊清单（三级防御的最后兜底层）══

_PRESET_QUESTIONS = {
    "initial": [
        {
            "id": "q1", "text": "你现在最困扰的感受或不适是什么？",
            "type": "text", "allow_note": True, "note_hint": "简短描述即可",
        },
        {
            "id": "q2", "text": "这种困扰主要体现在哪些方面？",
            "type": "multi", "allow_note": True,
            "options": [
                {"id": "sleep",    "label": "睡眠问题"},
                {"id": "energy",   "label": "精力/疲劳"},
                {"id": "digest",   "label": "消化/胃口"},
                {"id": "mood",     "label": "情绪/压力"},
                {"id": "body",     "label": "身体疼痛/不适"},
                {"id": "other",    "label": "其他"},
            ],
        },
    ],
    "deepen": [
        {
            "id": "q3", "text": "这种情况多久了？",
            "type": "single", "allow_note": True,
            "options": [
                {"id": "days",   "label": "几天内"},
                {"id": "weeks",  "label": "一两周"},
                {"id": "months", "label": "几个月"},
                {"id": "years",  "label": "一年以上"},
            ],
        },
        {
            "id": "q4", "text": "下面哪些情况会让你感觉加重？",
            "type": "multi", "allow_note": True,
            "options": [
                {"id": "night",    "label": "熬夜/睡眠不足"},
                {"id": "stress",   "label": "紧张/压力大"},
                {"id": "cold",     "label": "受凉"},
                {"id": "food",     "label": "吃了生冷/油腻"},
                {"id": "overwork", "label": "劳累后"},
                {"id": "none",     "label": "好像没有明显规律"},
            ],
        },
    ],
    "expand": [
        {
            "id": "q5", "text": "你的食欲怎么样？",
            "type": "single",
            "options": [
                {"id": "good",     "label": "正常挺好"},
                {"id": "decreased","label": "吃不下/容易饱"},
                {"id": "increased","label": "容易饿/吃得多"},
                {"id": "irregular","label": "时好时坏不规律"},
            ],
        },
        {
            "id": "q6", "text": "睡眠情况如何？",
            "type": "multi", "allow_note": True,
            "options": [
                {"id": "early",    "label": "入睡困难"},
                {"id": "wake",     "label": "容易醒/多梦"},
                {"id": "late",     "label": "醒得早/醒后睡不着"},
                {"id": "quality",  "label": "睡得浅/不解乏"},
                {"id": "good",     "label": "睡眠挺好"},
            ],
        },
        {
            "id": "q7", "text": "精神状态总体如何？",
            "type": "single",
            "options": [
                {"id": "ok",       "label": "挺好的"},
                {"id": "tired",    "label": "容易累"},
                {"id": "low",      "label": "情绪偏消沉"},
                {"id": "anxious",  "label": "容易焦虑/心烦"},
            ],
        },
    ],
    "finalize": [
        {
            "id": "q8", "text": "手心脚心平时偏热还是偏凉？",
            "type": "single",
            "options": [
                {"id": "warm",   "label": "偏热/怕热"},
                {"id": "cool",   "label": "偏凉/怕冷"},
                {"id": "normal", "label": "正常，没特别感觉"},
            ],
        },
        {
            "id": "q9", "text": "出汗情况？",
            "type": "single",
            "options": [
                {"id": "normal",  "label": "正常"},
                {"id": "little",  "label": "不太出汗"},
                {"id": "much",    "label": "容易出汗"},
                {"id": "night",   "label": "睡着后出汗多（盗汗）"},
            ],
        },
    ],
}


def _preset_questions(stage: str) -> list:
    """返回该阶段的预设问题（三级防御的最低级兜底）。"""
    return _PRESET_QUESTIONS.get(stage, [])


# ══ 3. System Prompt 模板 ══

INQUIRY_SYSTEM_PROMPT = """你是青囊管家的问诊引擎。你的任务是基于用户的 SPUM 数字模型，在四个阶段中逐个生成结构化的选择题清单。

## 问诊流程（四阶段）

1. **initial** — 主诉与核心症状：用户现在最困扰的感受是什么
2. **deepen** — 深化：症状细节、诱因、加重/缓解因素
3. **expand** — 扩展：饮食、睡眠、二便、精神状态
4. **finalize** — 收束：关键判别点，锁定状态倾向

## 输出要求（严格 JSON）

每个阶段返回一个 JSON 对象，格式如下：

```json
{{
  "stage": "initial",
  "stage_label": "主诉与核心症状",
  "is_final": false,
  "questions": [
    {{
      "id": "q1",
      "text": "问题文本",
      "type": "single",
      "options": [
        {{"id": "a", "label": "选项A"}},
        {{"id": "b", "label": "选项B"}}
      ],
      "allow_note": true,
      "note_hint": "备注提示（可选）"
    }}
  ],
  "next_hint": "下一阶段简述"
}}
```

## 规则

- 每个阶段 2-4 题，不要太多
- type: "single"（单选）/ "multi"（多选）/ "text"（纯文本）
- 选项必须 2-6 个
- 最后一个阶段（finalize）返回 "is_final": true
- 问题必须基于用户的 v_base 五形向量——比如土形偏弱的用户多问饮食/消化相关
- 语气温暖、像朋友，不是医生
- 严禁使用"诊断""治疗""处方"等医疗术语"""


# ══ 4. 端点 ══

@router.post("/inquiry/start")
async def inquiry_start(
    body: dict,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """启动新的问诊会话 → 返回第一阶段问题清单。"""
    from ...models import InquirySession

    # 1. 注入用户上下文（含身高体重 + LLM provider）
    provider = (body.get("provider") if body else None) or "spum"
    case = db.query(Case).filter(Case.user_id == current.id).first()
    v_base = case.v_baseline if case else _DEFAULT_V_INNATE
    v_innate = case.v_innate if case else _DEFAULT_V_INNATE

    # 检查基础信息缺失 → 构造补问问题
    # 条件：None / 0 / 明显不合理（height<120 或 weight<30）都算没填
    missing = []
    if not current.height or current.height < 120:
        missing.append({
            "id": "info_height", "text": "方便告诉我你的身高吗？（cm）",
            "type": "number", "allow_note": False,
        })
    if not current.weight or current.weight < 30:
        missing.append({
            "id": "info_weight", "text": "方便告诉我你的体重吗？（kg）",
            "type": "number", "allow_note": False,
        })

    user_context = {
        "qingnang_id": current.qingnang_id,
        "nickname": current.nickname,
        "gender": current.gender,
        "height": current.height,
        "weight": current.weight,
        "v_innate": v_innate,
        "v_base": v_base,
        "bazi": case.bazi if case else None,
        "syndrome": case.syndrome if case else None,
        "llm_provider": provider,
    }

    # 2. 创建 session
    session = InquirySession(
        user_id=current.id,
        case_id=case.id if case else None,
        stage="initial",
        status="active",
        user_context=user_context,
        history=[],
        answer_bank={},
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # 3. LLM 生成第一阶段问题 → prepend 补问
    questions = await _generate_stage_questions("initial", user_context, [], current)
    if missing:
        questions = missing + questions

    return {
        "session_id": session.id,
        "stage": "initial",
        "stage_label": STAGE_LABELS["initial"]["label"],
        "stage_desc": STAGE_LABELS["initial"]["desc"],
        "questions": questions,
        "base_info_missing": [q["id"] for q in missing],  # 告诉前端要自动存
        "is_final": False,
        "total_stages": 4,
    }


@router.post("/inquiry/{session_id}/answer")
async def inquiry_answer(
    session_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """提交一阶段答案 → 返回下一阶段问题（或完成）。

    body = {"stage": "initial", "answers": {"q1": {...}, "q2": {...}}, "note": "..."}
    """
    from ...models import InquirySession

    session = db.query(InquirySession).filter(
        InquirySession.id == session_id,
        InquirySession.user_id == current.id,
    ).first()
    if not session:
        raise HTTPException(404, "会话不存在")
    if session.status != "active":
        raise HTTPException(400, "会话已结束")

    # 1. 记录本轮答案到 history + 累计到 answer_bank
    answer_payload = body.get("answers", {})
    stage = session.stage

    # 1b. 自动存基础信息补填（info_height / info_weight）
    patch_user = {}
    if "info_height" in answer_payload:
        v = answer_payload["info_height"]
        if isinstance(v, dict):
            num = v.get("number") or v.get("value") or v.get("text")
        else:
            num = v
        try:
            patch_user["height"] = int(float(num))
        except (ValueError, TypeError):
            pass
    if "info_weight" in answer_payload:
        v = answer_payload["info_weight"]
        if isinstance(v, dict):
            num = v.get("number") or v.get("value") or v.get("text")
        else:
            num = v
        try:
            patch_user["weight"] = float(num)
        except (ValueError, TypeError):
            pass
    if patch_user:
        for k, v in patch_user.items():
            setattr(current, k, v)
        # 同步到 user_context 里，LLM 后续轮就能用

        session.user_context = {**session.user_context, **patch_user}

    history = session.history or []
    history.append({
        "stage": stage,
        "answers": answer_payload,
        "note": body.get("note", ""),
    })
    session.history = history

    # 扁平化答案（方便 LLM 下轮用）
    bank = session.answer_bank or {}
    for qid, ans in answer_payload.items():
        bank[qid] = ans
    session.answer_bank = bank

    # 2. 推进到下一阶段
    idx = INQUIRY_STAGES.index(stage) if stage in INQUIRY_STAGES else 0
    next_stage = INQUIRY_STAGES[idx + 1] if idx + 1 < len(INQUIRY_STAGES) else "done"

    if next_stage == "done":
        # 完成 → 写 summary
        summary = await _generate_summary(session.user_context, history, bank, current)
        session.stage = "done"
        session.status = "completed"
        session.summary = summary
        session.completed_at = func.now()
        db.commit()
        return {
            "session_id": session.id,
            "stage": "done",
            "is_final": True,
            "summary": summary,
            "total_stages": 4,
        }

    # 3. LLM 生成下一阶段问题
    session.stage = next_stage
    db.commit()

    questions = await _generate_stage_questions(next_stage, session.user_context, history, current)
    return {
        "session_id": session.id,
        "stage": next_stage,
        "stage_label": STAGE_LABELS.get(next_stage, {}).get("label", next_stage),
        "stage_desc": STAGE_LABELS.get(next_stage, {}).get("desc", ""),
        "questions": questions,
        "is_final": next_stage == "finalize",
        "total_stages": 4,
        "progress": idx + 2,  # 已完成 N 个阶段（当前 + 之前）
    }


@router.get("/inquiry/{session_id}")
async def inquiry_get(
    session_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """查询会话当前状态（刷新页面续上）。"""
    from ...models import InquirySession

    session = db.query(InquirySession).filter(
        InquirySession.id == session_id,
        InquirySession.user_id == current.id,
    ).first()
    if not session:
        raise HTTPException(404, "会话不存在")

    idx = INQUIRY_STAGES.index(session.stage) if session.stage in INQUIRY_STAGES else 0
    questions = []
    if session.status == "active":
        # LLM 重新生成当前阶段问题（简化——预设兜底）
        questions = await _generate_stage_questions(
            session.stage, session.user_context, session.history or [], current
        )

    return {
        "session_id": session.id,
        "stage": session.stage,
        "stage_label": STAGE_LABELS.get(session.stage, {}).get("label", session.stage),
        "stage_desc": STAGE_LABELS.get(session.stage, {}).get("desc", ""),
        "status": session.status,
        "history": session.history or [],
        "answer_bank": session.answer_bank or {},
        "questions": questions,
        "is_final": session.stage == "finalize",
        "progress": idx + 1,
        "summary": session.summary,
        "total_stages": 4,
    }


# ══ 5. LLM 调用器（问诊专用，带 JSON 防御 + fallback）══

async def _generate_stage_questions(
    stage: str,
    user_context: dict,
    history: list,
    current: User,
) -> list:
    """生成某阶段的问题清单。LLM 失败时回退到预设清单。"""
    # provider 现在从 user_context.llm_provider 读（下面 LLM 调用段）

    # 组装 messages
    stage_label = STAGE_LABELS.get(stage, {}).get("label", stage)
    history_text = json.dumps(history, ensure_ascii=False) if history else "（首次问诊）"
    ctx_text = json.dumps(user_context, ensure_ascii=False, indent=2)

    messages = [
        {"role": "system", "content": INQUIRY_SYSTEM_PROMPT},
        {"role": "user", "content": f"""
请生成 **{stage_label}** 阶段的问题清单（stage="{stage}"）。

## 用户上下文
{ctx_text}

## 已完成的阶段历史
{history_text}

## 要求
- stage="{stage}", stage_label="{stage_label}"
- 返回 JSON 对象，questions 数组 2-4 题
- 严禁使用医疗术语，语气温暖像朋友
- 选项里避免"以上都对"这种偷懒选项
- 如果前一阶段用户没答或答得模糊，可以重复相关问题换个角度问
""".strip()},
    ]

    # 调 LLM（尊重 user_context 里的 llm_provider）
    raw_text = None
    provider = user_context.get("llm_provider", "spum")
    if provider == "deepseek" and settings.DEEPSEEK_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(
                    f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
                    json={
                        "model": settings.DEEPSEEK_MODEL,
                        "messages": messages,
                        "max_tokens": 1200,
                        "response_format": {"type": "json_object"},
                    }
                )
                if r.status_code == 200:
                    raw_text = r.json()["choices"][0]["message"]["content"]
        except Exception:
            pass
    else:
        # SPUM 本地
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                h = await client.get(f"{settings.QINGMENG_URL}/health")
                if h.status_code == 200:
                    r = await client.post(
                        f"{settings.QINGMENG_URL}/v1/chat/completions",
                        json={
                            "model": settings.QINGMENG_MODEL,
                            "messages": messages,
                            "max_tokens": 1200,
                        }
                    )
                    if r.status_code == 200:
                        raw_text = r.json()["choices"][0]["message"]["content"]
        except Exception:
            pass

    # 解析 + 提取 questions
    if raw_text:
        parsed = _parse_llm_json(raw_text)
        if parsed:
            questions = parsed.get("questions", [])
            # 校验：必须是 list，每项必须有 id/text/type
            if isinstance(questions, list) and all(
                isinstance(q, dict) and q.get("id") and q.get("text") and q.get("type")
                for q in questions
            ):
                return questions[:4]  # 最多 4 题

    # Fallback：预设清单
    return _preset_questions(stage)


async def _generate_summary(
    user_context: dict,
    history: list,
    answer_bank: dict,
    current: User,
) -> dict:
    """问诊完成后——生成状态摘要 JSON。失败返回最小摘要。"""
    ctx_text = json.dumps(user_context, ensure_ascii=False, indent=2)
    ans_text = json.dumps(answer_bank, ensure_ascii=False, indent=2)
    history_text = json.dumps(history, ensure_ascii=False)

    messages = [
        {"role": "system", "content": """你是 SPUM 问诊引擎。基于用户回答生成结构化状态摘要 JSON。

输出格式：
```json
{
  "dominant_pattern": "最多出现的 1-2 个核心状态标签（如 '土形偏弱' 或 '木形郁结+火形偏旺'）",
  "confidence": 0.0-1.0,
  "key_findings": ["发现1", "发现2", ...],
  "lifestyle_tips": ["生活建议1", "生活建议2", ...],
  "next_action": "建议下一步（如 '建议采集一次 PPG 观测' 或 '建议开始体质调理'）",
  "note": "给调理师的内部提示（可选）"
}
```
语气温暖，严禁医疗术语，不要写诊断/治疗建议。"""},
        {"role": "user", "content": f"""
## 用户
{ctx_text}

## 问诊历史
{history_text}

## 累计答案
{ans_text}

请输出状态摘要 JSON。""".strip()},
    ]

    raw_text = None
    provider = user_context.get("llm_provider", "spum")
    if provider == "deepseek" and settings.DEEPSEEK_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(
                    f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
                    json={
                        "model": settings.DEEPSEEK_MODEL,
                        "messages": messages,
                        "max_tokens": 800,
                        "response_format": {"type": "json_object"},
                    }
                )
                if r.status_code == 200:
                    raw_text = r.json()["choices"][0]["message"]["content"]
        except Exception:
            pass
    else:
        # SPUM 本地
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                h = await client.get(f"{settings.QINGMENG_URL}/health")
                if h.status_code == 200:
                    r = await client.post(
                        f"{settings.QINGMENG_URL}/v1/chat/completions",
                        json={"model": settings.QINGMENG_MODEL, "messages": messages, "max_tokens": 800}
                    )
                    if r.status_code == 200:
                        raw_text = r.json()["choices"][0]["message"]["content"]
        except Exception:
            pass

    if raw_text:
        parsed = _parse_llm_json(raw_text)
        if parsed:
            return parsed

    # Fallback：从 answer_bank 推最小摘要
    v_base = user_context.get("v_base", {})
    weak = [w for w, val in v_base.items() if isinstance(val, (int, float)) and val < 45]
    strong = [w for w, val in v_base.items() if isinstance(val, (int, float)) and val > 65]
    w_name = {"wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"}
    return {
        "dominant_pattern": f"{'、'.join(w_name[w]+'形偏弱' for w in weak)}" if weak else "五形暂无明显偏失",
        "confidence": 0.3,
        "key_findings": ["使用预设问诊摘要（LLM 暂不可用）"],
        "lifestyle_tips": ["建议先完成一次 PPG 观测建立基线", "规律作息，避免熬夜"],
        "next_action": "建议采集脉搏观测（PPG），或直接进入调理建议查看生活指南",
        "note": "LLM fallback — 摘要由本地规则生成，非个性化",
        "fallback": True,
    }

