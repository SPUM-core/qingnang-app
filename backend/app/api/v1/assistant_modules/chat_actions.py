"""chat_actions - Action 白名单与引导路由：AI 可执行动作注册 / 执行 / 动态引导"""
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import json

from ....models import User, Case, Observation, TreatmentPlan, ChatMessage, LifeSignal
from ....utils.maturity import compute_maturity
from ....utils.wuxing import graph_diagnose as _graph_diagnose

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
    # 图论守恒链条诊断（不再逐维阈值判弱）
    diag = _graph_diagnose(v)
    weak = diag['weak']
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


def _brief_has_content(brief: dict | None) -> bool:
    """brief 里有东西值得渲染成卡片（不只是一个空 anchor）"""
    if not brief:
        return False
    keys = ["food_good", "food_bad", "cloth", "anchor"]
    for k in keys:
        v = brief.get(k)
        if v:
            if isinstance(v, list) and len(v) > 0:
                return True
            if isinstance(v, dict) and any(v.values()):
                return True
    return False


def _user_asked_about_brief(message: str) -> bool:
    """用户问的是今日宜忌/饮食/穿搭 — 应该渲染 brief 卡片"""
    if not message:
        return False
    msg = message.lower()
    triggers = [
        "吃什么", "饮食", "食物", "早餐", "午餐", "晚餐", "食谱", "推荐吃", "今天吃",
        "颜色", "穿什么", "配饰", "穿搭", "衣服", "好看",
        "宜忌", "宜什么", "忌什么", "今天注意", "今天宜", "今天忌", "今天适合", "今日宜忌",
        "干支", "今天几号", "今天什么日", "今日干支",
    ]
    return any(k in msg for k in triggers)


# ── L3 模板架构：从 app.templates 导入单一信源 ──
from app.templates import (
    AIResponseTemplate, ActionSuggestion, BriefCardFill,
    AddReminderParams, MarkLifeSignalParams, UpdateChiefComplaintParams, NavigateParams,
    _ACTION_PARAMS_MODELS, _ACTION_ICONS,
    build_response_schema_prompt, extract_json, normalize_parsed, validate_action_params,
)


class ExecuteIn(BaseModel):
    """AI 真实执行的 action 请求体 — 从前端 doAction({type:'api_call', action_id, params}) 发来"""
    action_id: str
    params: dict = Field(default_factory=dict)


# ── AI 可执行的白名单 action（严格 Stage 守卫 + 权限验证） ──
_EXECUTE_WHITELIST: dict = {}  # lazy register 下面


def _register_execute(action_id: str, stage_min: int, fn, label: str):
    _EXECUTE_WHITELIST[action_id] = {
        "action_id": action_id,
        "stage_min": stage_min,
        "fn": fn,
        "label": label,
    }


async def _exec_add_reminder(user, db, params, brief, case, **_):
    """创建一条今日生活提醒 — 用 LifeSignal 存（tag=reminder, label=内容）"""
    from ....models import LifeSignal
    content = params.get("content")
    if not content and brief:
        fg = brief.get("food_good")
        if fg and len(fg) > 0:
            first = fg[0]
            title = first.get("title", "") if isinstance(first, dict) else str(first)
            content = f"今日推荐：{title}"
    if not content:
        return {"ok": False, "reason": "无法确定提醒内容"}
    # LifeSignal: tag="reminder", label=内容（全局去重）
    existing = db.query(LifeSignal).filter(
        LifeSignal.user_id == user.id,
        LifeSignal.tag == "reminder",
        LifeSignal.label == content,
    ).first()
    if existing:
        return {"ok": True, "skipped": True, "reason": "已存在相同提醒"}
    ls = LifeSignal(
        user_id=user.id, case_id=case.id if case else None,
        tag="reminder", label=content, source="chat_ai", source_id=None,
    )
    db.add(ls)
    db.commit()
    return {"ok": True, "created": {"tag": "reminder", "label": content}}


_register_execute("add_reminder", stage_min=2, fn=_exec_add_reminder,
                  label="添加到今日提醒")


async def _exec_update_chief_complaint(user, db, params, case, **_):
    """回填 Case.chief_complaint（后端 analysis_result 也在做，但 AI 可显式触发）"""
    new_cc = params.get("chief_complaint")
    if not new_cc or not case:
        return {"ok": False, "reason": "无内容或无档案"}
    case.chief_complaint = new_cc[:200]
    db.commit()
    return {"ok": True, "updated": {"chief_complaint": case.chief_complaint}}


_register_execute("update_chief_complaint", stage_min=2, fn=_exec_update_chief_complaint,
                  label="更新我的主诉")


async def _exec_mark_mentality(user, db, params, case, **_):
    """快速标记当前饮食/运动/排便信号 → LifeSignal"""
    from ....models import LifeSignal
    tag = params.get("tag")
    label = params.get("label")
    if not tag or not label:
        return {"ok": False, "reason": "tag/label 必填"}
    existing = db.query(LifeSignal).filter(
        LifeSignal.user_id == user.id, LifeSignal.tag == tag, LifeSignal.label == label
    ).first()
    if existing:
        return {"ok": True, "skipped": True, "reason": "已存在相同信号"}
    ls = LifeSignal(
        user_id=user.id, case_id=case.id if case else None,
        tag=tag, label=label, source="chat_ai", source_id=None,
    )
    db.add(ls)
    db.commit()
    return {"ok": True, "created": {"tag": tag, "label": label}}


_register_execute("mark_life_signal", stage_min=1, fn=_exec_mark_mentality,
                  label="标记我的当前状态")


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
                      maturity: dict | None = None,
                      brief: dict | None = None) -> list:
    """根据用户状态 + 成熟度阶段 → 决定青囊管家应该引导哪些 App 功能。

    扩展 action schema：
      { "type": "navigate", "label": "...", "route": "...", "icon": "...", "priority": "high/medium/low" }
      { "type": "api_call", "label": "...", "action_id": "...", "params": {...}, "icon": "...", "priority": "..." }

    navigate = 跳转页面（以前的伪控制）
    api_call = 直接调用后端 /execute 端点执行真实操作（创建提醒/标记信号/更新主诉）
    """
    if maturity is None:
        maturity = compute_maturity(user, db)
    stage = maturity["stage"]

    actions = []
    case = db.query(Case).filter(Case.user_id == user.id).first()
    obs_count = db.query(Observation).filter(
        Observation.case_id == case.id if case else None
    ).count() if case else 0

    # 查问诊状态（后续规则用）
    from ....models import InquirySession
    has_inquiry_done = db.query(InquirySession).filter(
        InquirySession.user_id == user.id, InquirySession.status == "completed"
    ).count() > 0

    msg = (user_message or "").lower()

    # 规则 1：没建档 → 强引导建档（navigate）
    if not case or not case.v_baseline:
        actions.append({"type": "navigate", "label": "先完成数字模型建档", "route": "/onboarding",
                        "icon": "📋", "priority": "high"})
        return actions

    # 规则 2：没脉诊数据 → 引导采集（降为 medium，避免每次都弹）
    # 只在用户首次对话（近期无观测）时弹，不再 high
    if obs_count == 0:
        actions.append({"type": "navigate", "label": "方便的话可以做一次脉搏采集（可选）", "route": "/collect/ppg",
                        "icon": "💓", "priority": "medium"})

    # 规则 2b：没完成问诊 → 引导问诊（腾出 high 槽位给这个）
    if not has_inquiry_done and len(actions) < 2:
        actions.append({"type": "navigate", "label": "聊聊你的情况，帮你梳理状态", "route": "/inquiry",
                        "icon": "💬", "priority": "high"})

    # 规则 3：用户主动提到"脉诊/脉搏/采集" → 引导采集（仍然 high，因为用户主动问）
    if any(kw in msg for kw in ["脉诊", "脉搏", "采集", "ppg", "测一测", "量一下"]):
        actions.append({"type": "navigate", "label": "立即做脉搏采集", "route": "/collect/ppg",
                        "icon": "💓", "priority": "high"})

    # 规则 3b：用户主动提到"问诊/聊聊/说说情况" → 引导问诊
    if any(kw in msg for kw in ["问诊", "聊聊", "说说", "情况", "症状"]):
        if not any(a.get("route") == "/inquiry" for a in actions):
            actions.append({"type": "navigate", "label": "去做个 AI 引导问诊", "route": "/inquiry",
                            "icon": "💬", "priority": "medium"})

    # ── Stage ≥ 2：真实控制 actions ──
    if stage >= 2:
        # 规则 4：brief 有今日食物数据 → 可以一键"添加到今日提醒"（api_call）
        if brief and brief.get("food_good") and len(actions) < 3:
            fg0 = brief["food_good"][0] if brief["food_good"] else None
            title = fg0.get("title", "") if isinstance(fg0, dict) else str(fg0)
            if title:
                actions.append({"type": "api_call", "label": f"把「{title}」加到今日提醒",
                                "action_id": "add_reminder",
                                "params": {"content": f"今日推荐：{title}"},
                                "icon": "🔔", "priority": "medium"})

        # 规则 5：提到"吃/饮食/宜忌" → 同时给 navigate（看完整列表）
        if any(kw in msg for kw in ["吃", "饮食", "早餐", "午餐", "晚餐", "忌口", "宜", "食谱"]):
            actions.append({"type": "navigate", "label": "查看完整今日宜忌", "route": "/notifications",
                            "icon": "🍜", "priority": "medium"})

        # 规则 6：有 extracted_signals → 可以一键标记为 LifeSignal（api_call）
        if extracted_signals and len(actions) < 4:
            for sig in extracted_signals[:1]:  # 最多 1 条
                actions.append({"type": "api_call",
                                "label": f"标记「{sig.get('label','状态')}」到我的数字模型",
                                "action_id": "mark_life_signal",
                                "params": {"tag": sig.get("tag"), "label": sig.get("label")},
                                "icon": "✅", "priority": "medium"})
                break

        # 规则 7：analysis 有 chief_complaint 但 Case 里空 → 可以一键 update
        if analysis and analysis.get("chief_complaint") and len(actions) < 4:
            cc = analysis["chief_complaint"]
            if case and not case.chief_complaint:
                actions.append({"type": "api_call",
                                "label": f"记录「{cc[:20]}」作为我的主诉",
                                "action_id": "update_chief_complaint",
                                "params": {"chief_complaint": cc},
                                "icon": "📝", "priority": "medium"})

    # ── Stage ≥ 3 ──
    if stage >= 3:
        if any(kw in msg for kw in ["睡", "失眠", "熬夜", "入睡", "多梦", "早醒"]):
            actions.append({"type": "navigate", "label": "看看睡眠改善方法", "route": "/discover",
                            "icon": "🌙", "priority": "medium"})

    # 规则：提到"方案/调理/档案/模型" → 引导体质档案（全阶段）
    if any(kw in msg for kw in ["方案", "调理", "档案", "模型", "体质", "先天"]):
        actions.append({"type": "navigate", "label": "查看我的体质档案", "route": "/case",
                        "icon": "📋", "priority": "medium"})

    # 去重 + 最多 4 条（避免按钮过载）
    seen = set()
    deduped = []
    priority_order = {"high": 0, "medium": 1, "low": 2}
    for a in sorted(actions, key=lambda x: priority_order.get(x.get("priority", "low"), 9)):
        p = a.get("params") or {}
        # params 是 dict，不能直接进 set —— 用 json 序列化
        params_key = json.dumps(p, sort_keys=True, ensure_ascii=False)
        key = (a.get("type"), a.get("route") or a.get("action_id"), params_key)
        if key not in seen:
            seen.add(key)
            deduped.append(a)
        if len(deduped) >= 4:
            break

    return deduped


