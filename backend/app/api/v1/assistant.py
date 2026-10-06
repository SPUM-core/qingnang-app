"""assistant - 青囊管家 AI 对话代理（转发到本地 qingmeng-engine）"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
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
# 进程内轻量缓存（daily_brief 纯函数，T=24h 足够）
# key = (user_id, date_str) → value = brief dict + expire_ts
# ═══════════════════════════════════════════════════════
_daily_brief_cache: dict[tuple[int, str], tuple[dict, float]] = {}


def _cached_daily_brief(user_id: int, v_for_engine: dict | None) -> dict | None:
    """按 user_id + 今日日期缓存 daily_brief 结果，省掉每次聊天的 3s 调用。"""
    if not v_for_engine:
        return None
    today = time.strftime("%Y-%m-%d")
    key = (user_id, today)
    now = time.time()
    hit = _daily_brief_cache.get(key)
    if hit and hit[1] > now:
        return hit[0]
    return None


def _set_daily_brief_cache(user_id: int, v_for_engine: dict | None, brief: dict):
    """写入缓存，TTL=24h（次日自动过期）。"""
    if not v_for_engine or not brief:
        return
    today = time.strftime("%Y-%m-%d")
    key = (user_id, today)
    _daily_brief_cache[key] = (brief, time.time() + 86400)


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
    message: str = Field("", max_length=2000)
    history: list[dict] = Field(default_factory=list)  # [{role, content}] 最近 N 轮
    provider: str = "spum"  # "spum"=青檬引擎(本地), "deepseek"=云端, 未来可扩展

    # ── 语音输入（可选）──
    voice_base64: str | None = None      # base64 编码的音频数据
    voice_format: str = "webm"           # webm / mp3 / wav / m4a
    voice_duration: float | None = None   # 秒（前端估算，可选）

    @model_validator(mode="after")
    def _check_not_empty(self):
        """message 和 voice_base64 不能同时为空"""
        if not (self.message or self.message.strip()) and not self.voice_base64:
            raise ValueError("message 和 voice_base64 不能同时为空")
        return self


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
        # 2026-10-04: 成熟度卡片对用户隐藏，但 AI 要主动引导用户完善采集
        f"【引导策略】你知道用户当前处于 Stage {maturity['stage']}，请在对话中自然地引导他完善数字模型。",
        f"  next_target: {maturity.get('next_target', '无')}",
        f"  missing_signals: {', '.join(maturity.get('missing_signals', [])) or '无'}",
        "  引导方式：不要直接说'请完善你的数字模型'，而是用自然语言问，比如'你平时几点吃饭呀？帮你记进身体档案里'。",
        "  采集优先级：建档 > 脉搏采集 > 深度问诊 > 生活信号。Stage 1 用户没有档案，先引导建档。Stage 2+ 用户有档案但数据不足，引导补采集。",
        "  ⚠️ 内部术语禁止：绝不要对用户说'娱乐级/食疗级/调理级/方剂级'这些 Stage 名称——这些是内部术语。",
        "    如果你要表达数据完整度，说'我对你的了解越来越深了'这种自然语言。",
        "  ⚠️ 会员推销禁令：missing_signals 里如果有'开通会员'或类似字样，绝对不要主动提会员。",
        "    会员是用户自己决定的事，引导补采集即可。",
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

    # ── 长期记忆（分层：permanent 永不过期，episodic 30 天 TTL）──
    try:
        from ...models.chat import ChatMemoryNode
        permanent_nodes = db.query(ChatMemoryNode).filter(
            ChatMemoryNode.user_id == user.id,
            ChatMemoryNode.tier == "permanent",
        ).order_by(ChatMemoryNode.compressed_at.desc()).limit(20).all()

        from datetime import datetime as _dt
        episodic_nodes = db.query(ChatMemoryNode).filter(
            ChatMemoryNode.user_id == user.id,
            ChatMemoryNode.tier == "episodic",
            ChatMemoryNode.expires_at > _dt.utcnow(),
        ).order_by(ChatMemoryNode.compressed_at.desc()).limit(5).all()

        if permanent_nodes or episodic_nodes:
            parts.append("")
            if permanent_nodes:
                parts.append("【长期记忆·核心事实】（永不过期，你必须牢记这些）")
                for n in permanent_nodes:
                    parts.append(f"- {n.summary}")
            if episodic_nodes:
                parts.append("")
                parts.append("【近期记忆·时效性】（仅供参考，可能已变化）")
                for n in episodic_nodes:
                    parts.append(f"- {n.summary}")
    except Exception as _e:
        print(f"[build_system_prompt] ChatMemoryNode skip: {_e}")

    # ── 闻诊摘要（VoiceAnalysis）──
    try:
        from ...utils.voice_service import get_latest_voice_analysis
        latest_voice = get_latest_voice_analysis(db, user.id)
        if latest_voice and latest_voice.confidence in ("high", "medium"):
            parts.append("")
            parts.append(f"【闻诊·五音】（置信度 {latest_voice.confidence}）")
            parts.append(f"  {latest_voice.summary_text}")
    except Exception as _e:
        print(f"[build_system_prompt] voice skip: {_e}")

    # ── 舌诊摘要（望诊）──
    try:
        from app.models.chat import TonguePhoto
        latest_tongue = db.query(TonguePhoto).filter(TonguePhoto.user_id == user.id) \
                        .order_by(TonguePhoto.created_at.desc()).first()
        if latest_tongue and latest_tongue.confidence in ("high", "medium"):
            parts.append("")
            parts.append(f"【望诊·舌象】（置信度 {latest_tongue.confidence}）")
            parts.append(f"  舌象: {latest_tongue.tongue_type}")
            if latest_tongue.s_vector:
                sv = ", ".join(f"_{k}{v}" for k, v in latest_tongue.s_vector.items())
                parts.append(f"  S修正: {sv}")
            if latest_tongue.rationale:
                parts.append(f"  依据: {'; '.join(latest_tongue.rationale)}")
    except Exception as _e:
        print(f"[build_system_prompt] TonguePhoto skip: {_e}")

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

    # ── L2+ 模板架构：注入 schema 描述，告诉 LLM 它有填空位可填 ──
    # L3: 从 _EXECUTE_WHITELIST 读 stage_min（单一信源，消除 _STAGE_MIN_MAP 重复）
    parts.append(build_response_schema_prompt(whitelist=_EXECUTE_WHITELIST))

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
    from ...models import LifeSignal
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
    from ...models import LifeSignal
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
    from ...models import InquirySession
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
# 历史容量阈值压缩（512K 触发 → LLM 提炼 → 删原消息）
# ═══════════════════════════════════════════════════════

CHAT_HISTORY_MAX_BYTES = 512 * 1024      # 512K
CHAT_HISTORY_BATCH_PAIRS = 8             # 每轮压缩 8 对 user+assistant
CHAT_HISTORY_KEEP_RECENT = 20            # 永远保留最近 20 条（10 对）不压缩
EPISODIC_TTL_DAYS = 30                   # episodic 记忆默认过期天数
PERMANENT_PER_USER_LIMIT = 50            # 单用户 permanent 节点上限（防无限增长）

# 进程内锁：防止同一用户并发压缩
_compressing_users: set = set()


async def _compress_old_messages(user_id: int):
    """历史容量阈值压缩（异步，chat 端点 commit 后后台触发）

    逻辑：
      1. 算总容量 SUM(OCTET_LENGTH(content))
      2. 超限 → 取最早 N 轮 → LLM 压缩提炼 → 写 ChatMemoryNode → 删原消息
      3. 循环直到低于阈值
    """
    global _compressing_users
    if user_id in _compressing_users:
        return  # 已在压缩，跳过
    _compressing_users.add(user_id)

    try:
        from datetime import datetime, timedelta
        from ...database import SessionLocal
        from ...models.chat import ChatMemoryNode

        db = SessionLocal()
        try:
            # 0. 清理过期 episodic 节点（顺便降低 prompt 注入噪音）
            db.query(ChatMemoryNode).filter(
                ChatMemoryNode.user_id == user_id,
                ChatMemoryNode.tier == "episodic",
                ChatMemoryNode.expires_at < datetime.utcnow(),
            ).delete(synchronize_session=False)
            db.commit()

            # 1. 算总容量
            total_bytes = db.query(
                func.coalesce(func.sum(func.length(ChatMessage.content)), 0)
            ).filter(ChatMessage.user_id == user_id).scalar()

            if total_bytes <= CHAT_HISTORY_MAX_BYTES:
                return  # 没超限

            # 2. 排除最近 KEEP_RECENT 条
            recent_ids = [r[0] for r in db.query(ChatMessage.id)
                          .filter(ChatMessage.user_id == user_id)
                          .order_by(ChatMessage.id.desc())
                          .limit(CHAT_HISTORY_KEEP_RECENT).all()]
            if not recent_ids:
                return

            # 3. 取最早消息（压缩对象）
            oldest_msgs = db.query(ChatMessage).filter(
                ChatMessage.user_id == user_id,
                ChatMessage.id.notin_(recent_ids),
            ).order_by(ChatMessage.id.asc()).limit(CHAT_HISTORY_BATCH_PAIRS * 2).all()

            if len(oldest_msgs) < 4:
                return

            # 4. 拼对话文本
            dialogue_lines = []
            for m in oldest_msgs:
                role_label = "用户" if m.role == "user" else "青囊管家"
                dialogue_lines.append(f"[{role_label}] {m.content}")
            dialogue_text = "\n".join(dialogue_lines)

            first_ts = str(oldest_msgs[0].created_at)[:19]
            last_ts = str(oldest_msgs[-1].created_at)[:19]
            source_ids = [m.id for m in oldest_msgs]
            source_range = {"from": first_ts, "to": last_ts, "count": len(source_ids)}

            # 5. 调 LLM 压缩 → list[dict]
            nodes_data = await _llm_compress_dialogue(dialogue_text, first_ts, last_ts)
            permanent_count = sum(1 for n in nodes_data if n["tier"] == "permanent")

            # 6. 安全检查：如果 LLM 完全没识别到 permanent，补跑一次只抓 permanent 的检查
            if permanent_count == 0 and any(kw in dialogue_text for kw in ["年", "长期", "一直", "30岁", "岁以"]):
                try:
                    extra = await _llm_safety_check_permanent(dialogue_text, first_ts, last_ts)
                    if extra:
                        nodes_data.extend(extra)
                        permanent_count += len(extra)
                except Exception:
                    pass  # 安全检查失败不阻塞主流程

            # 7. 写节点（每条事实一个 ChatMemoryNode）
            now = datetime.utcnow()
            for n in nodes_data:
                tier = n["tier"]
                node = ChatMemoryNode(
                    user_id=user_id,
                    summary=n["summary"],
                    category=n.get("category", "other"),
                    tier=tier,
                    source_msg_ids=source_ids,
                    source_range=source_range,
                    expires_at=(now + timedelta(days=EPISODIC_TTL_DAYS)) if tier == "episodic" else None,
                )
                db.add(node)

            # 8. 删除原消息
            db.query(ChatMessage).filter(ChatMessage.id.in_(source_ids)).delete(synchronize_session=False)
            db.query(LifeSignal).filter(
                LifeSignal.source_id.in_(source_ids),
                LifeSignal.source.in_(["chat", "chat_llm"]),
            ).update({LifeSignal.source_id: None}, synchronize_session=False)

            db.commit()

            # 9. 递归（如果还超限）
            await _compress_old_messages(user_id)

        finally:
            db.close()

    except Exception as e:
        print(f"[compress] user={user_id} error: {e}")
    finally:
        _compressing_users.discard(user_id)


async def _llm_compress_dialogue(dialogue_text: str, first_ts: str, last_ts: str) -> list[dict]:
    """调 LLM 把一段历史对话压缩成带 tier 的记忆节点列表

    返回: [{"summary": "...", "category": "...", "tier": "permanent" | "episodic"}, ...]
    """
    import httpx, json as _json

    prompt = f"""你是青囊管家的"长期记忆压缩器"。下面是一段你和用户的早期对话（{first_ts} ~ {last_ts}）。

请从对话里提炼出**有价值的记忆条目**，按置信度/时效性分成两档：

## tier 判定规则

### permanent（永久记忆，高置信度，永不过期）
以下情况归 permanent：
- 用户明确陈述的**长期/慢性**事实（>3个月），如"腰膝酸软30年"、"长期失眠靠安眠药"
- 用户**核心体质倾向**（木形偏旺、土形偏弱等 SPUM 五形判定）
- 用户**强烈的偏好/禁忌**（"不吃辣"、"讨厌运动"、"坚持每天泡脚"）
- 用户**重要的健康事件**（"去年做了手术"、"多次治疗无果"）
- 用户**长期坚持的习惯**（"每天2点睡"、"烟龄20年"）

### episodic（时效记忆，低置信度，默认 30 天过期）
以下情况归 episodic：
- 用户**近期饮食**（"今天吃了火锅"、"这几天没胃口"）
- 用户**一过性情绪/疲劳**（"今早有点累"、"昨天压力大"）
- 用户**短期调理进展**（"上周泡了药浴睡得好"、"这两天睡眠改善了"）
- 用户**近期观测数据**（"昨天测了 PPG"、"今天脉搏快"）
- 用户**临时计划**（"这周要出差"、"下周去体检"）

## category 取值
constitution | symptom | preference | progress | diet | mood | habit | event | other

## 输出格式（严格 JSON）
```json
{{
  "permanent": [
    {{"summary": "腰膝酸软30年，阴雨天加重", "category": "symptom"}},
    {{"summary": "核心体质：土形37.5最高，木形25.0偏弱", "category": "constitution"}}
  ],
  "episodic": [
    {{"summary": "今天吃了火锅后胃有点胀", "category": "diet"}},
    {{"summary": "这三天睡得比之前好", "category": "progress"}}
  ]
}}
```

## 严格约束
- 只输出 JSON，不要任何解释文字
- permanent 条目**必须**满足 >3个月 / 核心体质 / 强烈偏好 其中之一
- 如果对话里没有某一档的内容，那一档就输出空数组
- 每个 summary 不超过 40 字，保留具体数字
- 严禁医疗术语

原始对话：
{dialogue_text[:4000]}"""

    # 优先 deepseek（JSON mode）
    api_key = getattr(settings, 'DEEPSEEK_API_KEY', '') or getattr(settings, 'deepseek_api_key', '')
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 800,
                    },
                )
                if r.status_code == 200:
                    raw = r.json()["choices"][0]["message"]["content"].strip()
                    return _parse_memory_json(raw, dialogue_text[:300])
        except Exception as e:
            print(f"[compress-llm] deepseek error: {e}")

    # 兜底：本地青檬引擎
    try:
        qingmeng_url = getattr(settings, 'QINGMENG_URL', 'http://localhost:11434')
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{qingmeng_url}/api/generate", json={
                "model": "qwen2.5:7b",
                "prompt": prompt,
                "stream": False,
            })
            if r.status_code == 200:
                return _parse_memory_json(r.json().get("response", ""), dialogue_text[:300])
    except Exception as e:
        print(f"[compress-llm] qingmeng error: {e}")

    # 终极兜底：单条 permanent（截断前 150 字）
    return [{"summary": dialogue_text[:150], "category": "other", "tier": "permanent"}]


def _parse_memory_json(raw: str, fallback_text: str) -> list[dict]:
    """从 LLM 返回里抽 JSON，解析成记忆条目列表"""
    import json as _json, re

    # 去掉 markdown code fence
    text = raw.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    try:
        obj = _json.loads(text)
    except Exception:
        # 尝试找第一个 { ... } 片段
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                obj = _json.loads(m.group())
            except Exception:
                return [{"summary": fallback_text, "category": "other", "tier": "permanent"}]
        else:
            return [{"summary": fallback_text, "category": "other", "tier": "permanent"}]

    nodes = []
    for item in obj.get("permanent", []) or []:
        nodes.append({
            "summary": str(item.get("summary", "")).strip(),
            "category": item.get("category", "other"),
            "tier": "permanent",
        })
    for item in obj.get("episodic", []) or []:
        nodes.append({
            "summary": str(item.get("summary", "")).strip(),
            "category": item.get("category", "other"),
            "tier": "episodic",
        })

    # 过滤空 summary
    return [n for n in nodes if n["summary"] and len(n["summary"]) > 3]


async def _llm_safety_check_permanent(dialogue_text: str, first_ts: str, last_ts: str) -> list[dict]:
    """压缩安全检查：如果主压缩没识别到 permanent，但对话里疑似有，二次只抓 permanent 事实"""
    import httpx, json as _json, re

    prompt = f"""你是青囊管家的"永久记忆安全审计器"。下面是一段早期对话（{first_ts} ~ {last_ts}）。

请扫描对话，**只**找出**绝对应该保留的永久事实**（必须满足 >3个月 / 核心体质 / 强烈偏好 之一）。
如果你认为对话里确实没有这些内容，返回空数组即可。

判定标准（满足任一）：
- 有明确时长的长期/慢性事实："腰膝酸软30年"、"长期失眠"、"坚持X年"
- 用户核心体质判定：SPUM 五形明确倾向（"土形最高"、"木形偏旺"）
- 用户强烈表达的偏好/禁忌："不吃辣"、"讨厌运动"、"烟瘾"
- 重要健康事件：手术/重大病史/多次治疗无果

输出（严格 JSON）：
```json
{{"permanent": [
  {{"summary": "...", "category": "symptom"}},
  {{"summary": "...", "category": "constitution"}}
]}}
```
如无：`{{"permanent": []}}`
每个 summary 不超 40 字，保留具体数字。

对话：
{dialogue_text[:3000]}"""

    api_key = getattr(settings, 'DEEPSEEK_API_KEY', '')
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                          "temperature": 0.1, "max_tokens": 400},
                )
                if r.status_code == 200:
                    raw = r.json()["choices"][0]["message"]["content"].strip()
                    m = re.search(r'\{[\s\S]*\}', raw)
                    if m:
                        obj = _json.loads(m.group())
                        return [{"summary": str(i.get("summary","")).strip(),
                                 "category": i.get("category","other"), "tier": "permanent"}
                                for i in (obj.get("permanent") or [])
                                if i.get("summary") and len(str(i.get("summary","")).strip()) > 3]
        except Exception:
            pass

    return []


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

    # ── 2. 拿 daily_brief 确定性产出物（3s timeout，失败静默，进程内缓存 24h）──
    brief = None
    case = db.query(Case).filter(Case.user_id == current.id).first()
    v_for_engine = None
    if case:
        v_for_engine = case.v_current or case.v_baseline or case.v_innate

    # 先查缓存
    brief = _cached_daily_brief(current.id, v_for_engine)
    if brief is None and v_for_engine:
        # 缓存 miss → HTTP 调用
        try:
            async with httpx.AsyncClient(timeout=3.0) as tc:
                tr = await tc.post(
                    f"{settings.QINGMENG_URL}/v1/reasoning/daily_brief",
                    json={"v_base": v_for_engine},
                )
                if tr.status_code == 200:
                    brief = tr.json()
                    _set_daily_brief_cache(current.id, v_for_engine, brief)
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
                brief=brief,
            )
        except Exception:
            shortcut_actions = []

        return {
            "reply": shortcut_reply,
            "engine": "engine_direct",
            "latency_ms": 0,
            "qingmeng_online": True,
            "brief_context": brief,
            "render_brief_card": _brief_has_content(brief),
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

    # ── 5. 按用户选择的 provider 调 LLM（L2+: 用 JSON mode 拿结构化输出）──
    llm_ok = False
    latency_ms = 0
    reply_text = ""
    parsed_template: AIResponseTemplate | None = None  # LLM 填的槽位
    provider_used = body.provider or "spum"

    if provider_used == "deepseek":
        # ── DeepSeek 云端：用 response_format: json_object ──
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
                            "max_tokens": 1200,  # 多留空间给 JSON 槽位
                            "response_format": {"type": "json_object"},
                        }
                    )
                    latency_ms = int((time.time() - start) * 1000)
                    if r.status_code == 200:
                        raw = r.json()["choices"][0]["message"]["content"]
                        parsed_template = normalize_parsed(extract_json(raw) or {})
                        # 兜底：parse 失败就把 raw 当纯文本
                        reply_text = parsed_template.reply if parsed_template else raw
                        llm_ok = True
            except Exception:
                llm_ok = False
        if not settings.DEEPSEEK_API_KEY:
            llm_ok = False
    else:
        # ── SPUM 本地模型（青檬引擎/Ollama）：format: json ──
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
                            "max_tokens": 1200,
                            "format": "json",  # Ollama 的 JSON mode
                        }
                    )
                    latency_ms = int((time.time() - start) * 1000)
                    if r.status_code == 200:
                        raw = r.json()["choices"][0]["message"]["content"]
                        parsed_template = normalize_parsed(extract_json(raw) or {})
                        reply_text = parsed_template.reply if parsed_template else raw
        except Exception:
            llm_ok = False

    # ── 6. Fallback：规则引擎（加空回复安全网）──
    if not llm_ok or not reply_text or not reply_text.strip():
        if llm_ok and raw and raw.strip() and (not parsed_template or not parsed_template.reply.strip()):
            # LLM OK 但 parsed_template.reply 是空/白 → 用 raw 兜底
            reply_text = raw.strip()
        else:
            reply_text = _generate_generic_reply(current, db, body.message)
        latency_ms = latency_ms if latency_ms else 0

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

    # ── 8a. 语音样本持久化 + 触发闻诊 ──
    voice_saved = None
    if body.voice_base64 and len(body.voice_base64) > 500:
        try:
            import base64 as _b64
            from ...utils.voice_service import save_voice_sample, trigger_voice_analysis
            audio_bytes = _b64.b64decode(body.voice_base64)
            voice_saved = save_voice_sample(
                db=db, user_id=current.id,
                audio_bytes=audio_bytes,
                file_format=body.voice_format,
                duration=body.voice_duration,
                asr_text=body.message if body.message else None,
                source="chat",
            )
            # 异步触发闻诊（收满 5 条自动跑）
            import asyncio as _asyncio2
            _asyncio2.create_task(trigger_voice_analysis(current.id))
        except Exception as e:
            print(f"[voice-save] error: {e}")

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

        # 8d. LLM 结构化解析（优先用 parsed_template，省掉第二次 LLM 调用）
        #     L2+: 模板扩展了 pathologies/suggestions/chief_complaint/signals
        analysis_result = None
        try:
            # ── 优先：从 parsed_template（第一次 LLM 调用的 JSON 槽位）取 ──
            if parsed_template and parsed_template.pathologies:
                analysis_result = {
                    "pathologies": [p.model_dump() if hasattr(p, 'model_dump') else p for p in parsed_template.pathologies],
                    "suggestions": [s.model_dump() if hasattr(s, 'model_dump') else s for s in (parsed_template.suggestions or [])],
                    "signals": [sg.model_dump() if hasattr(sg, 'model_dump') else sg for sg in (parsed_template.signals or [])],
                    "chief_complaint": parsed_template.chief_complaint,
                    "engine": "template_merge",  # 标记：来自第一次 LLM 调用的槽位
                }
            else:
                # ── 兜底：单独调一次 analyze_conversation（10s timeout）──
                analysis_result = await analyze_conversation(
                    user_message=body.message,
                    assistant_reply=reply_text,
                    history=body.history,
                    provider=provider_used,
                )
        except Exception:
            analysis_result = None

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

    # ── 8h. 历史容量阈值压缩（异步后台触发，不阻塞 chat 响应）──
    import asyncio as _asyncio
    try:
        _asyncio.create_task(_compress_old_messages(current.id))
    except Exception:
        pass  # 后台任务创建失败不影响主流程

    # ── 9. Action Router + L2+ 模板合并 ──
    # 9a. 规则生成的 actions（兜底）
    try:
        rule_actions = _generate_actions(
            user=current, db=db,
            user_message=body.message,
            analysis=analysis_result or None,
            extracted_signals=signals_user_msg or [],
            maturity=maturity,
            brief=brief,
        )
    except Exception:
        rule_actions = []

    # 9b. L2+: parsed_template.suggested_actions 白名单验证
    llm_valid_actions: list[dict] = []
    current_stage = maturity["stage"]
    if parsed_template and parsed_template.suggested_actions:
        for sa in parsed_template.suggested_actions:
            spec = _EXECUTE_WHITELIST.get(sa.action_id)
            if spec and current_stage >= spec["stage_min"]:
                act = {"type": "api_call" if sa.action_id != "navigate" else "navigate",
                       "action_id": sa.action_id, "params": sa.params,
                       "icon": _ACTION_ICONS.get(sa.action_id, "✨"),
                       "priority": "medium"}
                # label：LLM 填的优先，否则从白名单取默认
                act["label"] = sa.label or spec["label"]
                # navigate 需要 route
                if sa.action_id == "navigate":
                    act["route"] = sa.params.get("route", "/")
                    act.pop("action_id", None)
                llm_valid_actions.append(act)
            # 不在白名单 或 Stage 不够 → 静默丢弃

    # 9c. 合并：LLM 填的优先，规则补位（统一 dedup key）
    def _dedup_key(a):
        return a.get("route") or a.get("action_id") or a.get("label")
    llm_seen = {_dedup_key(a) for a in llm_valid_actions}
    merged_actions = llm_valid_actions[:3]  # LLM 建议最多 3 条
    for ra in rule_actions:
        rk = _dedup_key(ra)
        if rk not in llm_seen and rk and len(merged_actions) < 4:
            merged_actions.append(ra)
            llm_seen.add(rk)
    actions = merged_actions

    # ── brief 卡片渲染（合并 LLM 槽位 + 后端启发式）──
    # L2+: AI 可以自己决定要不要展示（brief_card.show），同时填人话注释
    llm_wants_brief = bool(parsed_template and parsed_template.brief_card and parsed_template.brief_card.show)
    # 后端启发式兜底
    rule_wants_brief = _brief_has_content(brief) and (
        _user_asked_about_brief(body.message)
        or any(k in reply_text for k in ["推荐吃", "宜穿", "今日宜", "今日忌", "干支"])
    )
    render_brief = llm_wants_brief or rule_wants_brief

    # L2+: LLM 填的 brief_card 解读（anchor_note / food_highlight）透传给前端
    brief_card_fill = None
    if parsed_template and parsed_template.brief_card:
        bc = parsed_template.brief_card
        brief_card_fill = {
            "anchor_note": bc.anchor_note,
            "food_highlight": bc.food_highlight,
        }

    # ── chief_complaint 自动回填（analysis_result 优先，parsed_template 兜底）──
    cc_to_fill = None
    if analysis_result and analysis_result.get("chief_complaint"):
        cc_to_fill = analysis_result["chief_complaint"]
    elif parsed_template and parsed_template.suggested_actions:
        for sa in parsed_template.suggested_actions:
            if sa.action_id == "update_chief_complaint" and sa.params.get("chief_complaint"):
                cc_to_fill = sa.params["chief_complaint"]
                break
    if cc_to_fill and case and not case.chief_complaint:
        case.chief_complaint = cc_to_fill[:200]
        try:
            db.commit()
        except Exception:
            db.rollback()

    return {
        "reply": reply_text,
        "engine": engine_tag + ("+template" if parsed_template else ""),
        "provider": provider_used,
        "latency_ms": latency_ms,
        "llm_online": llm_ok,
        "brief_context": brief,
        "brief_card_fill": brief_card_fill,  # L2+: LLM 填的人话注释
        "render_brief_card": render_brief,
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

@router.get("/voice/samples")
async def list_voice_samples(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """当前用户的语音样本列表（元数据，不含音频二进制）"""
    from ...models.chat import VoiceSample
    samples = db.query(VoiceSample).filter(VoiceSample.user_id == current.id) \
              .order_by(VoiceSample.created_at.desc()).limit(10).all()
    return {
        "samples": [
            {
                "id": s.id,
                "duration": s.duration,
                "file_format": s.file_format,
                "file_size": s.file_size,
                "quality_score": s.quality_score,
                "asr_text": s.asr_text,
                "source": s.source,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            } for s in samples
        ],
        "count": len(samples),
        "storage_used": sum(s.file_size or 0 for s in samples),
        "storage_threshold": 10 * 1024 * 1024,
        "max_per_user": 5,
    }


@router.post("/voice/upload")
async def upload_voice_sample(
    body: dict,  # {audio_base64, format, duration}
    force_analyze: bool = False,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """手动上传一条语音样本（VoiceSampleView 用）"""
    import base64 as _b64
    from ...utils.voice_service import save_voice_sample, trigger_voice_analysis

    audio_b64 = body.get("audio_base64") or body.get("voice_base64")
    if not audio_b64:
        raise HTTPException(status_code=400, detail="缺少 audio_base64")

    audio_bytes = _b64.b64decode(audio_b64)
    sample = save_voice_sample(
        db=db, user_id=current.id,
        audio_bytes=audio_bytes,
        file_format=body.get("format", body.get("voice_format", "webm")),
        duration=body.get("duration") or body.get("voice_duration"),
        asr_text=body.get("asr_text"),
        source=body.get("source", "voice_sample_view"),
    )

    # 触发闻诊分析
    import asyncio as _asyncio3
    _asyncio3.create_task(trigger_voice_analysis(current.id, force=force_analyze))

    return {"id": sample.id, "quality_score": sample.quality_score, "ok": True}


@router.get("/voice/latest-analysis")
async def get_latest_voice_analysis(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """最新闻诊分析结果"""
    from ...utils.voice_service import get_latest_voice_analysis
    va = get_latest_voice_analysis(db, current.id)
    if not va:
        return {"found": False, "message": "暂无闻诊数据"}
    return {
        "found": True,
        "id": va.id,
        "confidence": va.confidence,
        "summary_text": va.summary_text,
        "basic": va.basic,
        "wuyin": va.wuyin,
        "virtual_yang": va.virtual_yang,
        "s_vector": va.s_vector,
        "aggregated": va.aggregated,
        "analyzed_at": va.analyzed_at.isoformat() if va.analyzed_at else None,
        "warnings": va.warnings,
    }


@router.post("/voice/force-analyze")
async def force_voice_analysis(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """手动触发闻诊分析（不管样本数量）"""
    import asyncio as _asyncio4
    from ...utils.voice_service import trigger_voice_analysis
    _asyncio4.create_task(trigger_voice_analysis(current.id, force=True))
    return {"ok": True, "message": "闻诊分析已触发"}


# ═══════════════════════════════════════════════════════
# 舌诊（望诊）
# ═══════════════════════════════════════════════════════

@router.post("/tongue/upload")
async def upload_tongue_photo(
    body: dict,  # {image_base64, format}
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """上传舌部照片 → OpenCV HSV 分析 → SPUM 舌象判定"""
    import base64 as _b64, tempfile, os
    from app.models.chat import TonguePhoto
    from app.utils.tongue_analyzer import analyze_tongue as _analyze

    img_b64 = body.get("image_base64")
    if not img_b64:
        raise HTTPException(status_code=400, detail="缺少 image_base64")

    img_bytes = _b64.b64decode(img_b64)
    file_format = body.get("format", "jpeg").lower().replace("image/", "")
    if file_format not in ("jpeg", "jpg", "png", "webp"):
        file_format = "jpeg"

    # 临时文件 → 调 OpenCV 分析
    suffix = ".jpg" if file_format in ("jpeg", "jpg") else f".{file_format}"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(img_bytes); tmp.close()

    try:
        result = _analyze(tmp.name)
    finally:
        try: os.remove(tmp.name)
        except Exception: pass

    file_size = len(img_bytes)
    # 质量分：面积占比 + 置信度
    quality = 50.0
    if "tongue_ratio" in result: quality += min(result["tongue_ratio"] * 200, 30)
    if result.get("confidence") == "high": quality += 20
    elif result.get("confidence") == "medium": quality += 10
    quality = min(100, quality)

    # 循环覆盖：每用户最多 3 张 + 20MB 总阈值
    MAX_PHOTOS = 3
    MAX_BYTES = 20 * 1024 * 1024

    tp = TonguePhoto(
        user_id=current.id,
        file_format=file_format,
        file_size=file_size,
        image_data=img_bytes,
        quality_score=quality,
        confidence=result.get("confidence", "low"),
        tongue_type=result.get("spum_mapping", {}).get("tongue_type") or result.get("tongue_type"),
        s_vector=result.get("spum_mapping", {}).get("s_vector"),
        bgr_mean=result.get("bgr_mean"),
        coating_pct=result.get("coating"),
        rationale=result.get("spum_mapping", {}).get("rationale") or result.get("rationale"),
        warnings=result.get("warnings"),
    )
    db.add(tp); db.flush()

    # 循环覆盖
    count = db.query(TonguePhoto).filter(TonguePhoto.user_id == current.id).count()
    total = db.query(func.coalesce(func.sum(TonguePhoto.file_size), 0)).filter(
        TonguePhoto.user_id == current.id).scalar() or 0

    while count > MAX_PHOTOS or total > MAX_BYTES:
        victim = db.query(TonguePhoto).filter(TonguePhoto.user_id == current.id) \
                 .order_by(TonguePhoto.quality_score.asc(), TonguePhoto.created_at.asc()).first()
        if not victim: break
        total -= victim.file_size or 0; count -= 1
        db.delete(victim)

    db.commit()

    return {
        "ok": True,
        "id": tp.id,
        "confidence": tp.confidence,
        "tongue_type": tp.tongue_type,
        "s_vector": tp.s_vector,
        "rationale": tp.rationale,
        "warnings": tp.warnings,
        "quality_score": tp.quality_score,
    }


@router.get("/tongue/latest")
async def get_latest_tongue(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """最新闻诊舌象"""
    from app.models.chat import TonguePhoto
    tp = db.query(TonguePhoto).filter(TonguePhoto.user_id == current.id) \
         .order_by(TonguePhoto.created_at.desc()).first()
    if not tp:
        return {"found": False}
    return {
        "found": True,
        "id": tp.id,
        "confidence": tp.confidence,
        "tongue_type": tp.tongue_type,
        "s_vector": tp.s_vector,
        "rationale": tp.rationale,
        "coating_pct": tp.coating_pct,
        "bgr_mean": tp.bgr_mean,
        "created_at": tp.created_at.isoformat() if tp.created_at else None,
    }


# ═══════════════════════════════════════════════════════
# 检查报告（归档）
# ═══════════════════════════════════════════════════════

@router.post("/report/upload")
async def upload_medical_report(
    body: dict,  # {image_base64, format, report_title?, report_type?}
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """上传检查报告 → 存图 → 可选 LLM 结构化提取（有 vision 时自动）

    注：当前项目只有 DeepSeek（非 vision），所以默认只存图 + metadata。
    有 vision LLM API 时自动启用结构化识别。
    """
    import base64 as _b64
    from app.models.chat import MedicalReport
    from datetime import datetime

    img_b64 = body.get("image_base64")
    if not img_b64:
        raise HTTPException(status_code=400, detail="缺少 image_base64")

    img_bytes = _b64.b64decode(img_b64)
    file_format = body.get("format", "jpeg").lower().replace("image/", "")
    if file_format not in ("jpeg", "jpg", "png", "webp"):
        file_format = "jpeg"

    # 尝试 LLM 识别（检查是否有 vision API）
    structured = None
    raw_text = None
    provider = "manual"

    # DeepSeek JSON mode 不能看图，但可以做结构化文本提取
    # 这里留入口：有 vision API（如 qwen-vl）时自动启用
    # 当前先只存图，用户可手动填写 metadata

    MAX_REPORTS = 20
    MAX_BYTES = 50 * 1024 * 1024

    mr = MedicalReport(
        user_id=current.id,
        file_format=file_format,
        file_size=len(img_bytes),
        image_data=img_bytes,
        report_title=body.get("report_title"),
        report_type=body.get("report_type", "other"),
        report_date=body.get("report_date"),
        recognized=structured is not None,
        provider=provider,
        raw_text=raw_text,
        structured=structured,
        manual_notes=body.get("manual_notes"),
    )
    db.add(mr); db.flush()

    # 循环覆盖
    count = db.query(MedicalReport).filter(MedicalReport.user_id == current.id).count()
    total = db.query(func.coalesce(func.sum(MedicalReport.file_size), 0)).filter(
        MedicalReport.user_id == current.id).scalar() or 0

    while count > MAX_REPORTS or total > MAX_BYTES:
        victim = db.query(MedicalReport).filter(MedicalReport.user_id == current.id) \
                 .order_by(MedicalReport.created_at.asc()).first()
        if not victim: break
        total -= victim.file_size or 0; count -= 1
        db.delete(victim)

    db.commit()
    return {"ok": True, "id": mr.id, "message": "报告已上传（可稍后手动填写标题和类型）"}


@router.get("/report/list")
async def list_medical_reports(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    limit: int = 20,
):
    """用户报告列表（不含图片二进制，前端按需单条调取）"""
    from app.models.chat import MedicalReport
    reports = db.query(MedicalReport).filter(MedicalReport.user_id == current.id) \
              .order_by(MedicalReport.created_at.desc()).limit(limit).all()
    return {
        "reports": [
            {
                "id": r.id,
                "report_title": r.report_title,
                "report_type": r.report_type,
                "report_date": r.report_date.isoformat() if r.report_date else None,
                "recognized": r.recognized,
                "summary": r.summary,
                "file_size": r.file_size,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            } for r in reports
        ],
    }


@router.get("/report/{report_id}")
async def get_medical_report(
    report_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """单条报告详情（含图片二进制 base64，供前端查看）"""
    import base64 as _b64
    from app.models.chat import MedicalReport
    mr = db.query(MedicalReport).filter(
        MedicalReport.id == report_id,
        MedicalReport.user_id == current.id,
    ).first()
    if not mr:
        raise HTTPException(status_code=404, detail="报告不存在")
    return {
        "id": mr.id,
        "report_title": mr.report_title,
        "report_type": mr.report_type,
        "report_date": mr.report_date.isoformat() if mr.report_date else None,
        "recognized": mr.recognized,
        "provider": mr.provider,
        "raw_text": mr.raw_text,
        "structured": mr.structured,
        "summary": mr.summary,
        "spum_note": mr.spum_note,
        "manual_notes": mr.manual_notes,
        "file_format": mr.file_format,
        "image_base64": _b64.b64encode(mr.image_data or b"").decode() if mr.image_data else None,
        "created_at": mr.created_at.isoformat() if mr.created_at else None,
    }


@router.put("/report/{report_id}")
async def update_medical_report(
    report_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """手动更新报告 metadata（填标题、类型、备注等）"""
    from app.models.chat import MedicalReport
    from datetime import datetime

    mr = db.query(MedicalReport).filter(
        MedicalReport.id == report_id,
        MedicalReport.user_id == current.id,
    ).first()
    if not mr:
        raise HTTPException(status_code=404, detail="报告不存在")

    for field in ["report_title", "report_type", "report_date", "manual_notes", "spum_note", "summary"]:
        if field in body:
            setattr(mr, field, body[field])
    mr.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": mr.id}


@router.delete("/report/{report_id}")
async def delete_medical_report(
    report_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """删除一条报告"""
    from app.models.chat import MedicalReport
    mr = db.query(MedicalReport).filter(
        MedicalReport.id == report_id,
        MedicalReport.user_id == current.id,
    ).first()
    if not mr:
        raise HTTPException(status_code=404, detail="报告不存在")
    db.delete(mr); db.commit()
    return {"ok": True}


@router.get("/chat/messages")
async def list_chat_messages(
    limit: int = 100,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """当前用户的所有聊天记录（user + assistant 交替），返回时间升序。

    注意：同一次 chat 请求里落的 user + assistant 两条消息 created_at 相同
    （func.now() 是事务开始时间），所以必须 ORDER BY created_at ASC, id ASC
    保证 user 永远在 assistant 前面。
    """
    msgs = db.query(ChatMessage).filter(
        ChatMessage.user_id == current.id,
    ).order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).limit(limit).all()
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


# ═══════════════════════════════════════════════════════
# AI 真实执行端点 — 让 AI 不只是建议，而是能真实改变 APP 状态
# ═══════════════════════════════════════════════════════

@router.post("/execute")
async def execute_action(
    body: ExecuteIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """前端 doAction({type:'api_call', action_id, params}) 发来 — 后端按白名单执行。

    L3: params 先过 Pydantic 模板验证（validate_action_params），再执行。
    白名单 + Stage 守卫在 _EXECUTE_WHITELIST 里注册。
    """
    action_spec = _EXECUTE_WHITELIST.get(body.action_id)
    if not action_spec:
        raise HTTPException(status_code=404, detail=f"未知 action_id: {body.action_id}")

    # L3: 按 action_id 匹配 typed params model 做 Pydantic 验证
    validated = validate_action_params(body.action_id, body.params)
    if validated is None:
        raise HTTPException(
            status_code=422,
            detail=f"action_id='{body.action_id}' 的 params 不符合模板: {body.params}",
        )
    clean_params = validated.model_dump()

    maturity = compute_maturity(current, db)
    stage = maturity["stage"]
    if stage < action_spec["stage_min"]:
        raise HTTPException(
            status_code=403,
            detail=f"当前 Stage {stage} 不允许执行「{action_spec['label']}」，需 Stage {action_spec['stage_min']}",
        )

    case = db.query(Case).filter(Case.user_id == current.id).first()

    try:
        result = await action_spec["fn"](
            user=current, db=db, params=clean_params, case=case,
            brief=None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行失败: {e}")

    return {
        "ok": result.get("ok", True),
        "action_id": body.action_id,
        "label": action_spec["label"],
        "result": result,
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
    from .notifications import _call_qingmeng_lifestyle
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
    from .notifications import build_user_meta

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
    from ...utils.maturity import compute_maturity
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
    from .notifications import _call_qingmeng_lifestyle
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
            "type": "text", "allow_note": True, "allow_skip": True, "note_hint": "简短描述即可",
        },
        {
            "id": "q2", "text": "这种困扰主要体现在哪些方面？",
            "type": "multi", "allow_note": True, "allow_skip": True,
            "options": [
                {"id": "sleep",    "label": "睡眠问题"},
                {"id": "energy",   "label": "精力/疲劳"},
                {"id": "digest",   "label": "消化/胃口"},
                {"id": "mood",     "label": "情绪/压力"},
                {"id": "body",     "label": "身体疼痛/不适"},
                {"id": "other",    "label": "其他（可在备注里写）"},
            ],
        },
    ],
    "deepen": [
        {
            "id": "q3", "text": "这种情况多久了？",
            "type": "single", "allow_note": True, "allow_skip": True,
            "options": [
                {"id": "days",   "label": "几天内"},
                {"id": "weeks",  "label": "一两周"},
                {"id": "months", "label": "几个月"},
                {"id": "years",  "label": "一年以上"},
            ],
        },
        {
            "id": "q4", "text": "下面哪些情况会让你感觉加重？（可多选）",
            "type": "multi", "allow_note": True, "allow_skip": True,
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
            "type": "single", "allow_skip": True, "allow_note": True,
            "options": [
                {"id": "good",     "label": "正常挺好"},
                {"id": "decreased","label": "吃不下/容易饱"},
                {"id": "increased","label": "容易饿/吃得多"},
                {"id": "irregular","label": "时好时坏不规律"},
            ],
        },
        {
            "id": "q6", "text": "睡眠情况如何？（可多选）",
            "type": "multi", "allow_note": True, "allow_skip": True,
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
            "type": "single", "allow_skip": True, "allow_note": True,
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
            "type": "single", "allow_skip": True, "allow_note": True,
            "options": [
                {"id": "warm",   "label": "偏热/怕热"},
                {"id": "cool",   "label": "偏凉/怕冷"},
                {"id": "normal", "label": "正常，没特别感觉"},
            ],
        },
        {
            "id": "q9", "text": "出汗情况？",
            "type": "single", "allow_skip": True, "allow_note": True,
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
      "allow_skip": true,
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
- **灵活选 type**：根据问题性质决定单选还是多选——如果症状可能多个同时存在，选 "multi"；如果是唯一状态（如食欲总体好/不好），选 "single"
- 每题都要设 `"allow_skip": true`，用户可以跳过不想答的题
- 每题都建议设 `"allow_note": true`，让用户可以用自由备注替代选项
- 选项必须 2-6 个
- 最后一个阶段（finalize）返回 "is_final": true
- 问题必须基于用户的 v_base 五形向量——比如土形偏弱的用户多问饮食/消化相关
- 语气温暖、像朋友，不是医生
- 严禁使用"诊断""治疗""处方"等医疗术语"""


# ══ 4. 端点 ══

@router.get("/inquiry/latest")
async def inquiry_latest(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """返回当前用户最新完成的问诊 summary — 供 Dashboard 展示。"""
    from ...models import InquirySession
    sess = db.query(InquirySession).filter(
        InquirySession.user_id == current.id,
        InquirySession.status == "completed",
        InquirySession.summary.isnot(None),
    ).order_by(InquirySession.completed_at.desc()).first()
    if not sess:
        return {"has_summary": False}
    return {
        "has_summary": True,
        "session_id": sess.id,
        "completed_at": sess.completed_at.isoformat() if sess.completed_at else None,
        "summary": sess.summary,
    }


@router.get("/inquiry/list")
async def inquiry_list(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    limit: int = 20,
):
    """返回当前用户所有已完成的问诊会话（含 summary） — 供体质时间线展示。"""
    from ...models import InquirySession
    sessions = db.query(InquirySession).filter(
        InquirySession.user_id == current.id,
        InquirySession.status == "completed",
        InquirySession.summary.isnot(None),
    ).order_by(InquirySession.completed_at.desc()).limit(limit).all()

    return {
        "items": [
            {
                "session_id": s.id,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "summary": s.summary,
            }
            for s in sessions
        ],
        "total": len(sessions),
    }


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
                # 兜底：allow_skip / allow_note 缺省补 true
                for q in questions:
                    q.setdefault("allow_skip", True)
                    q.setdefault("allow_note", True)
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

⚠️ 核心原则（必须遵守）：
  v_innate 是这个用户的五行时空锚点（基于八字推演的先天基底），它是客观数值。
  问诊回答是用户自述的主观症状。
  → 五行判定（dominant_pattern）必须优先参考 v_innate 数值，症状只是验证和补充。
  → 例如：v_innate 显示土 37.5（最高），即使用户说"我怕冷"，dominant_pattern 里也要包含"土形"相关判断。
  → 症状和 v_innate 矛盾时，在 note 里标注，但 dominant_pattern 仍以 v_innate 为准。

⚠️ 灵活处理不完整回答：
  answer_bank 里可能出现：
  - {skipped: true} → 用户跳过了这道题，**忽略**
  - 只有 {note: '...'} 没有 value/values → 用户用自由备注替代了选择，**把 note 当答案读**
  - 空对象 {} → 用户没答也没跳过，**忽略**
  **只基于有效回答生成 summary，不要因为部分题跳过就降低 confidence 或显得信息不足。**

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


# ═══════════════════════════════════════════════════════════
# 体质推理接口 — onboarding 第二步用
# 输入: v_innate (五行百分比) + day_master_element + dayun大运
# 输出: constitution 类型 + 体质解读 + 年龄段风险
# ═══════════════════════════════════════════════════════════

# 五行 → 脏腑 → 常见病映射（SPUM 简化版）
_ELEMENT_ZANGFU = {
    'wood':  {'zangfu': '肝',  'sens': '眼、筋、情绪'},
    'fire':  {'zangfu': '心',  'sens': '舌、脉、睡眠'},
    'earth': {'zangfu': '脾',  'sens': '口、肉、食欲'},
    'metal': {'zangfu': '肺',  'sens': '鼻、皮、呼吸'},
    'water': {'zangfu': '肾',  'sens': '耳、骨、精力'},
}

# ════════════════════════════════════════════════════════════════
# SPUM v2 体质推理 — 先天禀赋（v_innate）独立于临床健康区间
# ════════════════════════════════════════════════════════════════
# v_innate：和=100 的五行概率分布，均值 20/维（先天基底强弱相对关系）
# HEALTH_POLYTOPE：临床观测健康区间 35-65（用于 v_current / 大运推演）
# → 两者量纲不同！v_innate 用相对均值偏离，不用 HEALTH_POLYTOPE！
_V_INNATE_MEAN = 20.0          # 每维均值（5维等分 100）
_V_INNATE_DEVIATION_PCT = 0.25 # 偏离均值 ±25%（即 <15 或 >25）才算"显著"

# ── 正面模板（先天禀赋亮点） ──
_CONSTITUTION_STRENGTH_TEMPLATES = {
    'wood':  '🌲 木气禀赋突出 — 直觉敏锐、善于规划、适应变化',
    'fire':  '🔥 火气禀赋突出 — 热情外向、感染力强、行动力充沛',
    'earth': '🪨 土气禀赋突出 — 稳重踏实、共情力强、值得信赖',
    'metal': '⚙️ 金气禀赋突出 — 理性清晰、追求品质、自律性高',
    'water': '💧 水气禀赋突出 — 聪明内省、感知力强、善抓本质',
}

# ── 平衡模板（先天禀赋均衡） ──
_CONSTITUTION_BALANCED_TEMPLATES = {
    'wood':  '🌲 木气调和 — 情绪弹性好，张弛有度',
    'fire':  '🔥 火气调和 — 精力稳当，不亢不疲',
    'earth': '🪨 土气调和 — 消化吸收好，胃口稳',
    'metal': '⚙️ 金气调和 — 皮肤呼吸顺畅，耐寒热',
    'water': '💧 水气调和 — 睡眠质量好，恢复力强',
}

# ── 需要关注的模板（偏离明显） ──
_CONSTITUTION_TEMPLATES = {
    ('wood', 'weak'):  '🌲 木气偏弱 — 情志易郁、眼干易倦',
    ('wood', 'strong'):'🌲 木气偏旺 — 急躁易怒、胁肋发胀',
    ('fire', 'weak'):  '🔥 火气偏弱 — 易悸怕冷、说话气短',
    ('fire', 'strong'):'🔥 火气偏旺 — 口舌易生疮、心烦失眠',
    ('earth','weak'):  '🪨 土气偏弱 — 食欲欠佳、吃一点就胀',
    ('earth','strong'):'🪨 土气偏旺 — 脘腹胀满、舌苔偏厚',
    ('metal','weak'):  '⚙️ 金气偏弱 — 皮肤偏干、偶尔咳嗽',
    ('metal','strong'):'⚙️ 金气偏旺 — 咳痰偏黄、鼻子干热',
    ('water','weak'):  '💧 水气偏弱 — 腰膝易酸、容易疲劳',
    ('water','strong'):'💧 水气偏旺 — 畏寒肢冷、精力过盛',
}

# 年龄段风险锚点（简化版，后续可用大运 refine）
_AGE_RISK_RANGES = [
    (0,  18,  '先天体质形成期'),
    (19, 35,  '青年期 · 创业承压'),
    (36, 50,  '中年期 · 脏腑代偿拐点'),
    (51, 65,  '过渡期 · 旧疾易显'),
    (66, 120, '老年期 · 气血衰减'),
]


@router.get("/lunar-days")
async def get_lunar_days(year: int, month: int, is_leap: bool = False):
    """给定阴历年+月（含闰月），返回该月实际天数（29或30）。
    
    用 Solar 日期差法：本月初一 Solar → 下月初一 Solar 的间隔天数 = 本月天数。
    闰月同理：闰月初一 Solar → 下月（非闰月）初一 Solar 的间隔。
    """
    try:
        from datetime import date
        from qingmeng_engine._vendor.lunar_python import Lunar
        
        def _solar_of_lunar_ym(y, m, leap=False):
            """返回给定阴历年月（含闰月标记）的初一对应的阳历 date 对象。"""
            # lunar_python 闰月用 month+100 表示（尝试法，失败则 fallback）
            if leap:
                try:
                    lm = Lunar.fromYmd(y, m + 100, 1)
                except Exception:
                    # fallback：直接用下月初一减闰月跨度
                    lm = None
            else:
                lm = Lunar.fromYmd(y, m, 1)
            
            if lm is None:
                return None
            s = lm.getSolar()
            return date(s.getYear(), s.getMonth(), s.getDay())
        
        if is_leap:
            # 闰月天数 = 闰月初一 → 下一个非闰月初一 的间隔
            d1 = _solar_of_lunar_ym(year, month, leap=True)
            if d1 is None:
                return {"days": 29}
            # 闰月的"下一个月"就是普通 month+1（如果 month=12 则下一年 1 月）
            nm = month + 1 if month < 12 else 1
            ny = year if month < 12 else year + 1
            d2 = _solar_of_lunar_ym(ny, nm, leap=False)
            if d2 is None:
                d2 = _solar_of_lunar_ym(year, month, leap=False)
            days = (d2 - d1).days
        else:
            # 普通月天数 = 本月初一 → 下月初一（不含闰月）
            # 但如果本年有闰月，且闰月在本月之后，需要跳过闰月跨度
            d1 = _solar_of_lunar_ym(year, month, leap=False)
            nm = month + 1 if month < 12 else 1
            ny = year if month < 12 else year + 1
            d2 = _solar_of_lunar_ym(ny, nm, leap=False)
            if d1 and d2:
                days = (d2 - d1).days
            else:
                days = 29
        
        return {"days": max(28, min(days, 31)), "year": year, "month": month, "is_leap": is_leap}
    except Exception:
        return {"days": 29, "year": year, "month": month, "is_leap": is_leap}


@router.get("/lunar-months")
async def get_lunar_months(year: int):
    """给定阴历年，返回该年所有月份（含闰月标记）及每月天数。"""
    try:
        from datetime import date
        from qingmeng_engine._vendor.lunar_python import Lunar
        
        def _solar_of_lunar_ym(y, m):
            lm = Lunar.fromYmd(y, m, 1)
            s = lm.getSolar()
            return date(s.getYear(), s.getMonth(), s.getDay())
        
        # 判断是否有闰月：全年天数 > 360
        d1 = _solar_of_lunar_ym(year, 1)
        d2 = _solar_of_lunar_ym(year + 1, 1)
        total_days = (d2 - d1).days
        has_leap = total_days > 360
        
        # 先算 12 个普通月的天数
        normal_months = []
        for m in range(1, 13):
            d_a = _solar_of_lunar_ym(year, m)
            if m < 12:
                d_b = _solar_of_lunar_ym(year, m + 1)
            else:
                d_b = _solar_of_lunar_ym(year + 1, 1)
            days = (d_b - d_a).days
            normal_months.append({"month": m, "is_leap": False, "days": days})
        
        result = normal_months
        # 如果有闰月，找出来（通过逐日累加对比 Solar 差）
        if has_leap:
            # 闰月天数 = 全年天数 - 12 个月天数之和（但这不准，因为普通月天数里可能已经包含了闰月跨度）
            # 简单做法：闰月天数固定 29 或 30（大多数 29）
            # 找闰月位置：检查普通月天数是否特别大（比如 >32 天）
            leap_m = None
            for m_info in normal_months:
                if m_info["days"] > 32:  # 正常月 29-30，跨度 35+ 说明包含了闰月
                    leap_m = m_info["month"]
                    # 把这个月拆成 普通月 + 闰月
                    # 普通月天数 = 30（假设），闰月天数 = total_days - sum(other_normal_months)
                    # 简化处理：闰月天数直接 29
                    leap_days = m_info["days"] - 30  # 30 是普通月天数（大致）
                    leap_days = max(28, min(leap_days, 30))
                    m_info["days"] = 30  # 修正普通月
                    break
            
            if leap_m is None:
                # 找闰月的另一个方法：Lunar 对象可能有标记
                # 简化：直接返回闰月在 4 月（1982 年的实际情况，多数年份闰月在 4-8 月）
                leap_m = 4
                leap_days = 29
            
            result.append({"month": leap_m, "is_leap": True, "days": leap_days})
        
        return {"months": result, "has_leap": has_leap, "leap_month": leap_m if has_leap else None}
    except Exception:
        return {"months": [], "has_leap": False, "leap_month": None}


@router.post("/constitution/analysis")
async def constitution_analysis(body: dict,
                                db: Session = Depends(get_db),
                                current: User = Depends(get_current_user)):
    """SPUM v3 先天体质推理 — 八字结构化 + v_innate + 大运 + LLM 病历级可验证预测。
    
    v3 核心升级：
    1. 完整八字上下文（四柱、藏干、日主）喂给 LLM，生成病历级回溯性预测
    2. 自动用 lunar_helper.compute_dayun() 排大运，每个年龄段命中的大运真正生效
    3. LLM prompt 要求"你是不是从小就..."式的具体可验证预测
    4. 先生成体质总纲标签（5-10字，如"水木通明·寒水无火"），抓住用户注意力
    """
    v_innate = body.get("v_innate") or {}
    day_master_el = body.get("day_master_element") or "earth"
    day_master_gan = body.get("day_master") or ""
    gender = body.get("gender") or "男"
    nickname = body.get("nickname") or ""
    
    # ── 八字完整上下文 ──
    bazi_str = body.get("bazi") or ""
    pillars = body.get("pillars") or []
    gz_y = body.get("ganzhi_year", "")
    gz_m = body.get("ganzhi_month", "")
    gz_d = body.get("ganzhi_day", "")
    gz_h = body.get("ganzhi_hour", "")
    
    # ── 自动排大运（如果前端没传） ──
    dayun = body.get("dayun") or []
    if not dayun and body.get("birth_date"):
        try:
            from ...utils.lunar_helper import compute_dayun
            dayun = compute_dayun(
                birth_date=body["birth_date"],
                birth_hour=body.get("birth_hour"),
                gender=gender,
                birth_city=body.get("birth_city"),
            ) or []
        except Exception:
            dayun = []

    if not v_innate:
        raise HTTPException(400, "需要 v_innate (五行百分比)")

    from ...utils.trajectory_algorithm import DIMS

    # ── 1. 偏离计算：用相对均值 20 的偏离率（不是 HEALTH_POLYTOPE） ──
    # threshold：偏离均值 ±25% 才算"显著"，否则视为"均衡"
    threshold = _V_INNATE_MEAN * _V_INNATE_DEVIATION_PCT   # 5
    deviations = []
    for el in DIMS:
        score = v_innate.get(el, 20)
        dev = score - _V_INNATE_MEAN   # 偏离均值
        if abs(dev) <= threshold:
            polarity = 'balanced'
        elif dev < -threshold:
            polarity = 'weak'
        else:
            polarity = 'strong'
        deviations.append({
            'el': el, 'score': score,
            'mean': _V_INNATE_MEAN, 'dev': dev,
            'delta': abs(dev), 'polarity': polarity,
        })

    # 按偏离绝对值排序 → 偏离最大的（不管方向）排前面
    deviations.sort(key=lambda d: d['delta'], reverse=True)
    top3 = deviations[:3]

    # ── 2. 体质标签（含亮点 + 注意点） ──
    constitution_tags = []
    # 先找亮点：偏离均值最大的 "strong" 维度（先天禀赋突出）
    strong_els = [d for d in deviations if d['polarity'] == 'strong']
    balanced_els = [d for d in deviations if d['polarity'] == 'balanced']
    weak_els = [d for d in deviations if d['polarity'] == 'weak']

    # 最多 2 个亮点（偏离最大的 strong 或 balanced 也行）
    highlights = strong_els[:2] if strong_els else balanced_els[:1]
    for d in highlights:
        if d['polarity'] == 'strong':
            tmpl = _CONSTITUTION_STRENGTH_TEMPLATES[d['el']]
            constitution_tags.append({
                'element': d['el'], 'polarity': 'strong',
                'score': d['score'], 'text': tmpl, 'is_strength': True,
            })
        elif d['polarity'] == 'balanced':
            tmpl = _CONSTITUTION_BALANCED_TEMPLATES[d['el']]
            constitution_tags.append({
                'element': d['el'], 'polarity': 'balanced',
                'score': d['score'], 'text': tmpl, 'is_strength': True,
            })

    # 最多 2 个注意点（偏离最大的 weak/strong，但排除已作为亮点的）
    seen_hl = {h['el'] for h in highlights}
    concerns = [d for d in deviations
                if d['polarity'] != 'balanced' and d['el'] not in seen_hl][:2]
    for d in concerns:
        tmpl = _CONSTITUTION_TEMPLATES.get((d['el'], d['polarity']), '')
        constitution_tags.append({
            'element': d['el'], 'polarity': d['polarity'],
            'score': d['score'], 'text': tmpl, 'is_strength': False,
        })

    # ── 3. 日主分析 ──
    day_master_score = v_innate.get(day_master_el, 20)
    dm_dev = day_master_score - _V_INNATE_MEAN
    if abs(dm_dev) <= threshold:
        dm_note = f"日主{day_master_el} — 先天基底均衡，稳扎稳打"
    elif dm_dev < -threshold:
        dm_note = f"日主{day_master_el}偏弱 — 基底不够厚实，需要额外关注恢复力"
    else:
        dm_note = f"日主{day_master_el}偏旺 — 先天禀赋充沛，精力旺盛"

    # ── 4. 分年龄段：不是"风险提示"，是"你可能经历过/正在经历的身体特征" ──
    age_risks = []
    # 观察点 = 所有非 balanced + 亮点维度（这些是先天显著的）
    obs_eles = highlights + concerns
    if not obs_eles:
        # 五行全均衡 → 找偏离最小的（也是一种观察点）
        obs_eles = deviations[:2]

    for age_start, age_end, label in _AGE_RISK_RANGES:
        observe_items = []
        for d in obs_eles[:3]:   # 最多 3 个观察维度
            el_info = _ELEMENT_ZANGFU.get(d['el'], {})
            zf = el_info.get('zangfu', d['el'])
            if d['polarity'] == 'strong':
                observe_items.append(f"{zf}先天偏盛（{d['score']:.0f}分）")
            elif d['polarity'] == 'weak':
                observe_items.append(f"{zf}先天偏弱（{d['score']:.0f}分）")
            else:
                observe_items.append(f"{zf}先天均衡")

        # 大运 refine：命中的大运五行叠加
        dayun_hit = []
        for dy in dayun:
            gan = dy.get('gan', '')
            zhi = dy.get('zhi', '')
            ds = dy.get('start', dy.get('start_age', 0))
            de = dy.get('end', dy.get('end_age', 999))
            if ds <= age_end and de >= age_start:
                from ...utils.trajectory_algorithm import TIANGAN_WUXING, DIZHI_CANGGAN
                gan_el = TIANGAN_WUXING.get(gan, '')
                if gan_el:
                    dayun_hit.append(f"{dy.get('name','')}运·{gan_el}")

        age_risks.append({
            'age_range': f"{age_start}-{age_end}",
            'age_label': label,
            'primary_gender_hint': '' if gender == '男' else '（女性需关注月经/带脉与各脏腑联动）',
            'risk_items': observe_items,   # 改名但兼容旧前端，语义已变"观察点"
            'dayun_hit': dayun_hit,
        })

    # ── 5. 地缘因子规则计算（出生地省份 → 五行微修正） ──
    birth_province = body.get("birth_province", "")
    birth_city = body.get("birth_city", "")
    geo_hint = _compute_geo_factor(birth_province, birth_city)

    # ── 6. 当前大运规则计算 ──
    current_dayun = _find_current_dayun(dayun)

    # ── 7. LLM 润色：病历式 6 段生成 ──
    llm_result = None
    if settings.DEEPSEEK_API_KEY:
        try:
            llm_result = await _polish_constitution_medical(
                deviations, v_innate, day_master_el, day_master_gan,
                dayun, current_dayun, age_risks,
                bazi_str, pillars, gz_y, gz_m, gz_d, gz_h,
                gender, nickname, geo_hint, birth_province, birth_city,
            )
        except Exception:
            llm_result = None

    if llm_result:
        constitution_summary = llm_result.get("constitution_summary", "")
    else:
        constitution_summary = ""

    # ── 如果 LLM 没返回，用规则拼一个可读的 6 段 markdown ──
    if not llm_result:
        llm_result = _build_rule_sections(
            bazi_str, pillars, gz_y, gz_m, gz_d, gz_h,
            day_master_el, day_master_gan, deviations, v_innate,
            dayun, current_dayun, age_risks, geo_hint,
            birth_province, birth_city, gender, nickname,
        )
        constitution_summary = llm_result.get("constitution_summary", "")

    return {
        "constitution_summary": constitution_summary,
        "llm_sections": llm_result,
        "rule_data": {
            "v_innate": v_innate,
            "deviations": deviations,
            "day_master_el": day_master_el,
            "day_master_gan": day_master_gan,
            "dayun": dayun,
            "current_dayun": current_dayun,
            "bazi": bazi_str,
            "pillars": pillars,
            "geo_factor": geo_hint,
            "birth_province": birth_province,
            "birth_city": birth_city,
            "gender": gender,
        },
        "algorithm": "spum_constitution_v4_medical" if llm_result else "spum_constitution_v4_rule",
    }


def _build_rule_sections(
    bazi_str, pillars, gz_y, gz_m, gz_d, gz_h,
    day_master_el, day_master_gan, deviations, v_innate,
    dayun, current_dayun, age_risks, geo_hint,
    birth_province, birth_city, gender, nickname,
) -> dict:
    """规则版 6 段 markdown — 无 LLM 时的保底输出。"""
    
    # 五行中文名
    _EL_CN = {"wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"}
    _EL_EMOJI = {"wood": "🌲", "fire": "🔥", "earth": "🪨", "metal": "⚙️", "water": "💧"}

    # ── ① 八字排盘 ──
    bazi_md = f"""### 公农历转换

| 项目 | 内容 |
|------|------|
| 八字 | **{bazi_str or '（未推演）'}** |
| 四柱 | 年柱 **{gz_y}** · 月柱 **{gz_m}** · 日柱 **{gz_d}** · 时柱 **{gz_h}** |

### 五行分布

| 五行 | SPUM 值 | 偏离均值 | 状态 |
|------|:-------:|:-------:|:----:|
"""
    for d in deviations:
        el_cn = _EL_CN.get(d['el'], d['el'])
        arrow = "↑" if d['polarity'] == 'strong' else "↓" if d['polarity'] == 'weak' else "→"
        state = "偏旺" if d['polarity'] == 'strong' else "偏弱" if d['polarity'] == 'weak' else "均衡"
        bazi_md += f"| {_EL_EMOJI.get(d['el'],'')} {el_cn} | {d['score']:.0f} | {d['dev']:+.0f}{arrow} | {state} |\n"
    bazi_md += f"""
### 日主

日干 **{day_master_gan}**（{_EL_CN.get(day_master_el, day_master_el)}形）——先天基底的核心。
"""

    # ── ② 先天基底推估 ──
    innate_md = "### 五形先天基底\n\n"
    # 先列亮点
    strengths = [d for d in deviations if d['polarity'] == 'strong']
    weaknesses = [d for d in deviations if d['polarity'] == 'weak']
    balanced = [d for d in deviations if d['polarity'] == 'balanced']
    
    if strengths:
        innate_md += "**✨ 天生优势（先天偏旺）：**\n\n"
        for s in strengths:
            el_cn = _EL_CN.get(s['el'], s['el'])
            innate_md += f"- **{el_cn}形偏旺**（{s['score']:.0f}分）——{_STRENGTH_DESC.get(s['el'], '先天禀赋充沛')}\n"
        innate_md += "\n"
    
    if balanced:
        innate_md += "**⚖️ 先天均衡：**\n\n"
        for b in balanced:
            el_cn = _EL_CN.get(b['el'], b['el'])
            innate_md += f"- **{el_cn}形均衡**（{b['score']:.0f}分）——先天禀赋平衡稳定\n"
        innate_md += "\n"
    
    if weaknesses:
        innate_md += "**👀 先天观察点（先天偏弱）：**\n\n"
        for w in weaknesses:
            el_cn = _EL_CN.get(w['el'], w['el'])
            innate_md += f"- **{el_cn}形偏弱**（{w['score']:.0f}分）——{_WEAK_DESC.get(w['el'], '先天禀赋相对不足')}\n"
    
    # ── ③ 地缘因子修正 ──
    geo_md = f"### 出生地：{birth_province or '（未填）'}{' ' + birth_city if birth_city else ''}\n\n"
    geo_md += f"{geo_hint.get('note', '地缘因子未计算')}\n\n"
    correction = geo_hint.get('correction', {})
    if correction:
        geo_md += "**外环境五行修正方向：**\n\n"
        for el, sign in correction.items():
            arrow = "↑ 天然加强" if sign == "+" else "↓ 天然减弱"
            geo_md += f"- {el}形：{arrow}\n"
    geo_md += "\n地缘修正效应：出生地的气候、水土、饮食会对先天八字格局产生长期微调。\n"

    # ── ④ 姓名与职业因子（规则版简版） ──
    name_md = f"### 昵称：{nickname or '（未填）'}\n\n"
    name_md += "姓名用字的五行属性会对先天体质产生微弱但长期的微调效应。"
    name_md += "当前为规则版输出，姓名五行修正需结合用字康熙字典笔画与偏旁部首综合判断。\n\n"
    # 从格局推断适合的方向
    if strengths:
        top_el = strengths[0]['el']
        name_md += f"### 天然适合的方向（基于最强五行 {_EL_CN.get(top_el, top_el)} 形）\n\n"
        career = _CAREER_HINT.get(top_el, "")
        if career:
            name_md += f"- {career}\n"

    # ── ⑤ 大运排盘与当前大运 ──
    dayun_md = "### 大运排盘\n\n"
    if dayun:
        dayun_md += "| 大运 | 年龄段 |\n|------|--------|\n"
        for dy in dayun[:10]:
            ds = dy.get('start', dy.get('start_age', '?'))
            de = dy.get('end', dy.get('end_age', '?'))
            ganzhi = dy.get('gan', '') + dy.get('zhi', '')
            marker = " ◀ **当前**" if dy.get('gan','') + dy.get('zhi','') == (current_dayun.get('gan','') + current_dayun.get('zhi','')) else ""
            dayun_md += f"| {ganzhi}{marker} | {ds}-{de}岁 |\n"
    else:
        dayun_md += "大运排盘数据未生成。\n"
    
    if current_dayun:
        dayun_md += f"\n### 当前大运分析\n\n"
        gz = current_dayun.get('gan','') + current_dayun.get('zhi','')
        ds = current_dayun.get('start', current_dayun.get('start_age', '?'))
        de = current_dayun.get('end', current_dayun.get('end_age', '?'))
        dayun_md += f"当前年龄段命中 **{gz}** 大运（{ds}-{de}岁）。\n"
        el = TIANGAN_WUXING.get(current_dayun.get('gan', ''), '') if current_dayun else ''
        if el:
            dayun_md += f"大运天干 {current_dayun.get('gan','')} 属 **{_EL_CN.get(el, el)}形**，"
            if el in [s['el'] for s in strengths]:
                dayun_md += "与先天偏旺之形叠加，该形力量进一步增强。\n"
            elif el in [w['el'] for w in weaknesses]:
                dayun_md += "对先天偏弱之形有天然补益。\n"
            else:
                dayun_md += "与先天格局形成稳定调和。\n"

    # ── ⑥ 先天体质倾向 ──
    summary = ""
    if strengths and weaknesses:
        top_s = _EL_CN.get(strengths[0]['el'], strengths[0]['el'])
        top_w = _EL_CN.get(weaknesses[0]['el'], weaknesses[0]['el'])
        summary = f"{top_s}{top_s}通明 · {top_w}弱格局"
    elif strengths:
        summary = f"{_EL_CN.get(strengths[0]['el'], '')}形偏旺格局"
    elif weaknesses:
        summary = f"{_EL_CN.get(weaknesses[0]['el'], '')}形偏弱格局"
    else:
        summary = "五行均衡格局"

    constitution_md = f"### 体质总纲\n\n**{summary}**\n\n"
    constitution_md += "### 核心体质特征\n\n"
    
    constitution_md += "**✨ 先天优势：**\n\n"
    if strengths:
        for s in strengths[:2]:
            el_cn = _EL_CN.get(s['el'], s['el'])
            constitution_md += f"- {el_cn}形先天偏旺 → {_STRENGTH_DESC.get(s['el'], '')}\n"
    if balanced:
        constitution_md += f"- 五行有均衡之形 → 先天禀赋中有稳定的恢复力与适应力\n"
    
    constitution_md += "\n**👀 先天倾向：**\n\n"
    if weaknesses:
        for w in weaknesses[:3]:
            el_cn = _EL_CN.get(w['el'], w['el'])
            constitution_md += f"- {el_cn}形先天偏弱 → {_WEAK_DESC.get(w['el'], '')}\n"
    if not weaknesses:
        constitution_md += "- 五行先天无明显偏衰，整体禀赋稳定\n"

    return {
        "constitution_summary": summary,
        "sections": {
            "bazi_analysis": bazi_md,
            "innate_base": innate_md,
            "geo_factor": geo_md,
            "name_career": name_md,
            "dayun_current": dayun_md,
            "constitution_summary_detail": constitution_md,
        }
    }


# ── 规则版描述表 ──
_STRENGTH_DESC = {
    "wood": "思维架构能力强，能快速构建复杂思想体系，思虑深邃有远见",
    "fire": "行动力充沛，热情有感染力，做事有冲劲，精力恢复快",
    "earth": "承载能力强，稳定可靠，消化与储备系统功能扎实",
    "metal": "决断力强，执行效率高，收敛与肃降功能顺畅",
    "water": "智慧深邃，内省能力强，精神层面恢复力好，思维有穿透力",
}
_WEAK_DESC = {
    "wood": "思虑能力相对弱，复杂思维架构需要更多后天训练，情绪弹性偏弱",
    "fire": "行动力与驱动力偏弱，怕冷，末梢循环可能不足，需要更多温暖",
    "earth": "消化功能易受影响，承载能力偏弱，压力大时先影响胃口",
    "metal": "收敛与执行能力偏弱，决断有时犹豫不决，肺气与皮肤屏障功能需要关注",
    "water": "智慧深度与内省能力偏弱，精神层面恢复力需要更多时间，精力易累",
}
_CAREER_HINT = {
    "wood": "天然适合思想建构、教育、写作、策划类工作",
    "fire": "天然适合创意表达、销售、领导、表演类工作",
    "earth": "天然适合管理、建筑、农业、稳定运营类工作",
    "metal": "天然适合金融、法律、机械、精密执行类工作",
    "water": "天然适合研究、哲学、心理、深度分析类工作",
}


def _compute_geo_factor(province: str, city: str = "") -> dict:
    """规则算地缘因子 — 出生地经纬度→气候→对五行的微调方向。
    
    简化版：按省份划分气候带，给出五行修正方向。
    例：陕西(西北) → 土厚金重 → 对木旺格局有天然制衡
    """
    if not province:
        return {"note": "未填写出生地，地缘因子暂未计算", "correction": {}}
    
    # 简化气候-五行映射（规则版）
    _REGION_WUXING = {
        # 西北：黄土高原 → 土金厚
        "陕西": {"土": "+", "金": "+", "水": "-"},
        "甘肃": {"土": "+", "金": "+", "水": "-"},
        "宁夏": {"土": "+", "金": "+"},
        "青海": {"土": "+", "水": "+"},
        "新疆": {"金": "+", "水": "-"},
        # 华北：平原 → 土厚
        "北京": {"土": "+", "金": "+"},
        "天津": {"土": "+", "水": "+"},
        "河北": {"土": "+"},
        "山西": {"土": "+", "金": "+"},
        "山东": {"土": "+", "水": "+"},
        "河南": {"土": "+"},
        # 东北：寒冷 → 水重
        "辽宁": {"水": "+", "土": "+"},
        "吉林": {"水": "+"},
        "黑龙江": {"水": "+"},
        # 华东：水网 → 水木重
        "上海": {"水": "+", "木": "+"},
        "江苏": {"水": "+", "木": "+"},
        "浙江": {"水": "+", "木": "+"},
        "安徽": {"土": "+", "木": "+"},
        "江西": {"木": "+"},
        "福建": {"木": "+", "火": "+"},
        # 华中：过渡带
        "湖北": {"水": "+", "土": "+"},
        "湖南": {"木": "+", "火": "+"},
        # 华南：湿热 → 火土重
        "广东": {"火": "+", "土": "+", "水": "+"},
        "广西": {"土": "+", "火": "+"},
        "海南": {"火": "+", "土": "+"},
        # 西南：复杂地貌
        "四川": {"土": "+", "水": "+", "木": "+"},
        "贵州": {"土": "+"},
        "云南": {"木": "+", "火": "+"},
        "西藏": {"金": "+", "土": "+"},
        # 直辖市/特别行政区 fallback
        "重庆": {"土": "+", "水": "+"},
    }
    correction = _REGION_WUXING.get(province, {})
    
    if correction:
        hint = f"{province}"
        if city:
            hint += f"（{city}）"
        hint += " — "
        parts = []
        for el, sign in correction.items():
            arrow = "↑" if sign == "+" else "↓"
            parts.append(f"{el}形{arrow}")
        hint += "外环境" + "、".join(parts)
    else:
        hint = f"{province}"
        if city:
            hint += f"（{city}）"
    
    return {"note": hint, "correction": correction}


def _find_current_dayun(dayun_list: list) -> dict:
    """从大运排盘找当前命中的大运（基于当前年龄）。"""
    import datetime
    now = datetime.datetime.now()
    current_year = now.year
    
    for dy in dayun_list:
        ds = dy.get('start', dy.get('start_age', 0))
        de = dy.get('end', dy.get('end_age', 999))
        # 如果大运用 start_year/end_year
        sy = dy.get('start_year', 0)
        ey = dy.get('end_year', 0)
        
        if sy and ey and sy <= current_year <= ey:
            return dy
        if ds and de and ds <= current_year <= de:
            return dy
    
    return dayun_list[0] if dayun_list else {}


async def _polish_constitution_medical(
    deviations, v_innate, day_master_el, day_master_gan,
    dayun, current_dayun, age_risks,
    bazi_str, pillars, gz_y, gz_m, gz_d, gz_h,
    gender, nickname, geo_hint, birth_province, birth_city,
) -> dict:
    """病历式 6 段体质画像生成 — 禁建议词，只描述不指导。"""
    import httpx

    # ── 大运格式化 ──
    dayun_lines = []
    for dy in dayun[:12]:
        ds = dy.get('start', dy.get('start_age', '?'))
        de = dy.get('end', dy.get('end_age', '?'))
        ganzhi = dy.get('gan', '') + dy.get('zhi', '')
        name = dy.get('name', '')
        year_range = dy.get('year_range', '')
        marker = " ◀ 当前大运" if dy.get('gan','') + dy.get('zhi','') == (current_dayun.get('gan','') + current_dayun.get('zhi','')) else ""
        dayun_lines.append(f"  {ganzhi} ({ds}-{de}岁 {year_range}) {name}{marker}")

    # ── 五行偏离格式化 ──
    dev_lines = []
    for d in deviations:
        dev_lines.append(f"  {d['el']}: {d['score']:.0f}分 (偏离均值{d['dev']:+.0f} → {d['polarity']})")

    # ── pillars 格式化 ──
    pillar_lines = []
    for p in pillars:
        if isinstance(p, dict):
            gan = p.get('gan', '') or p.get('tian_gan', '')
            zhi = p.get('zhi', '') or p.get('di_zhi', '')
            hidden = p.get('hidden', '') or p.get('cang_gan', '')
            label = p.get('label', '')
            pillar_lines.append(f"  {label}: {gan}({zhi}) 藏干[{hidden}]")
    
    prompt_lines = [
        "你是一位中医体质分析师，正在为一位用户撰写「先天体质画像」——",
        "要求达到专业病历的深度（参考：青囊中医病历雷苗苗版本）。",
        "",
        "═══════════════════════════════════════════════════════════",
        "## 输出结构：严格 6 段病历式",
        "═══════════════════════════════════════════════════════════",
        "",
        "你必须按以下 6 段结构返回，每段用 markdown 写：",
        "",
        "### 第一段：八字排盘",
        "  - 公农历转换（农历→公历→节气边界→年/月/日/时柱干支推导）",
        "  - 四柱明细（天干/地支/藏干/纳音）",
        "  - 五行分布统计（天干+地支主气+藏干余气→总加权→旺衰判定）",
        "  - 格局判定（日干旺衰→格局名称→用神/忌神→特殊组合标注）",
        "",
        "### 第二段：先天基底推估",
        "  - 八字 → 五形 S 向量映射（SPUM 术语：S_木↑↑ 表示木形极度亢进）",
        "  - S_0^(0) 先天基底（五形各自的强度 + 先天影响描述）",
        "  - 日干五形人格倾向（先天体质倾向 + 易偏亢/易偏衰之形 + 人格特征）",
        "",
        "### 第三段：地缘因子修正",
        "  - 出生地省份 + 外环境对八字格局的修正效应",
        "  - 气候/水土/饮食对五行的微调",
        "  - 地缘修正结论",
        "",
        "### 第四段：姓名与职业因子修正",
        "  - 姓名用字的五行属性修正（如果能从名字推断的话）",
        "  - 职业/生活环境对体质的影响（从八字格局推断天然适合的方向）",
        "  - 修正结论",
        "",
        "### 第五段：大运流年排盘与当前大运分析",
        "  - 大运排布表（逆排/顺排 + 起运年龄 + 各运年龄段）",
        "  - 当前大运分析（当前年龄段命中的大运干支 + 对格局的影响）",
        "  - 流年参考（如果今年有特殊五行叠加）",
        "",
        "### 第六段：先天体质倾向与核心体质特征",
        "  - 体质总纲标签（如：水木通明·寒水无火格局）",
        "  - 核心体质特征（先夸 2-3 条天生优势，再写 2-3 条需要注意的先天倾向）",
        "  - 各系统的先天倾向（神经系统/心循环/脾消化/肺呼吸/肝胆/肾生殖 — 每项给先天倾向 + 风险等级 ★）",
        "",
        "═══════════════════════════════════════════════════════════",
        "## 严禁事项（违反任何一条即降级）",
        "═══════════════════════════════════════════════════════════",
        "❌ 严禁给建议（禁止词：应该、要、必须、多、少、注意、别、避免、建议、推荐）",
        "❌ 严禁说将来（禁止词：将来、以后、要小心、预防）",
        "❌ 严禁用医生口吻（禁止词：诊断、治疗、处方、开药、就医）",
        "❌ 严禁恐吓（禁止词：容易得、高发、风险很大、危险）",
        "❌ 每段必须夸至少 1 条天生的优势（格局亮点、禀赋优点、人格长处）",
        "❌ 不要说'你容易...'，要说'你是不是从小就...'或'这个阶段你有没有...'",
        "",
        "═══════════════════════════════════════════════════════════",
        "## 写作指南（每段必须遵守）",
        "═══════════════════════════════════════════════════════════",
        "",
        "### 语气",
        "- 像一位懂中医体质的老朋友在聊「你是不是从小就...」",
        "- 用回溯性问句或陈述句（过去/现在），不用将来时",
        "- 每段至少 1 条正向描述（天生优势、格局亮点）",
        "",
        "### 段落深度（参考专业病历标准）",
        "- 八字排盘：不能只列干支，要推导——谁当令、谁透出、谁被克、格局叫什么、用神忌神是谁",
        "- 先天基底：每个五行形要有「强度词」（极度亢进/偏旺/均衡/偏弱/严重不足）+「先天影响描述」（这个形旺/弱意味着什么）",
        "- 地缘因子：不能只说「广东→火↑」，要说具体效应——广东湿热对八字火弱的人是天然补偿，但对火旺的人是加剧",
        "- 大运分析：不能只列干支，要说这个运的五行与先天格局的关系——是补益？是加剧？是调和？",
        "- 核心特征：要写出具体的「生活场景」而不是抽象术语。不说「木形偏旺」，说「脑子里好像有个停不下来的建筑师」",
        "",
        "### 禁止事项（违反任何一条即降级）",
        "❌ 禁止复制或模仿任何具体人名、具体八字特征、具体格局名称（水木通明、寒水无火等）——那些只属于原始病历",
        "❌ 禁止说将来（禁止词：将来、以后、要小心、预防）",
        "❌ 禁止给建议（禁止词：应该、要、多、少、注意、别、避免、建议、推荐）",
        "❌ 禁止医生口吻（禁止词：诊断、治疗、处方、开药、就医）",
        "❌ 禁止恐吓（禁止词：容易得、高发、风险很大、危险）",
        "",
        "### 参考句式（仅供语气参考，内容必须来自当前用户数据）",
        "- 八字排盘：「[日干]在[月令]处[旺衰]，但天干[藏干]透出，身[旺衰]——[五行相生相克关系]为用，[五行不足]为忌」",
        "- 先天基底：「[五行]↑↑（极度亢进）——[地支组合]当令，先天[对应人格特征]极强，但[对应副作用]」",
        "- 地缘因子：「[省份]出生的[地貌特征]环境，是[八字格局]的天然[制衡/补偿/加剧]」",
        "- 大运分析：「[干支]运（[起运]-[止运]岁）[五行生克]——[对当前格局的影响]」",
        "- 核心特征：「你是不是从小就[具体生活感受1]？但同时又[具体生活感受2]——这就是[格局总纲]的典型表现」",
        "",
        "═══════════════════════════════════════════════════════════",
        "## 用户原始数据",
        "═══════════════════════════════════════════════════════════",
        f"昵称: {nickname or '(未填)'}  |  性别: {gender}",
        f"八字: {bazi_str or '(未推演)'}",
        f"四柱: 年[{gz_y}] 月[{gz_m}] 日[{gz_d}] 时[{gz_h}]",
        f"日主: {day_master_gan}({day_master_el})",
        f"",
        f"四柱明细:",
        *(pillar_lines or ["  (无)"]),
        f"",
        f"v_innate(五行分布,和=100): {v_innate}",
        f"SPUM 五行偏离(均值20):",
        *dev_lines,
        f"",
        f"大运排盘:",
        *(dayun_lines or ["  (无大运数据)"]),
        f"",
        f"当前大运: {current_dayun.get('gan','')}{current_dayun.get('zhi','') or '(无)'}",
        f"",
        f"出生地: {birth_province or '(未填)'}{' ' + birth_city if birth_city else ''}",
        f"地缘因子: {geo_hint.get('note', '未填')}",
        f"地缘修正方向: {geo_hint.get('correction', {})}",
    ]

    prompt_lines += [
        "",
        "═══════════════════════════════════════════════════════════",
        "## 输出格式：严格 JSON，每段一个 markdown 字符串",
        "═══════════════════════════════════════════════════════════",
        "",
        "输出 JSON（每段是完整的 markdown 文本，不是标签数组）：",
        '{',
        '  "constitution_summary": "5-10字体质总纲（如：水木通明·寒水无火）",',
        '  "sections": {',
        '    "bazi_analysis": "第一段完整 markdown 文本（八字排盘+四柱+五行统计+格局判定）",',
        '    "innate_base": "第二段完整 markdown 文本（先天基底推估）",',
        '    "geo_factor": "第三段完整 markdown 文本（地缘因子修正）",',
        '    "name_career": "第四段完整 markdown 文本（姓名与职业因子）",',
        '    "dayun_current": "第五段完整 markdown 文本（大运排盘+当前大运分析）",',
        '    "constitution_summary_detail": "第六段完整 markdown 文本（体质总纲+核心特征+各系统倾向）"',
        '  }',
        '}',
        "",
        "⚠️ 注意：每个 section 的值是完整的 markdown 段落，里面可以包含表格、列表、加粗等格式。",
        "⚠️ 每个 section 长度建议 150-300 字（第六段可以更长 300-500 字）。",
    ]

    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.post(
            f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": settings.DEEPSEEK_MODEL or "deepseek-chat",
                "messages": [{"role": "system", "content": "你是青囊健康的中医体质分析师，输出专业、深刻、有洞察力。禁止建议、禁止恐吓、禁止将来时。每段必须包含至少 1 条天生优势的正向描述。"},
                            {"role": "user", "content": "\n".join(prompt_lines)}],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            },
        )
        if r.status_code != 200:
            return None
        try:
            content = r.json()["choices"][0]["message"]["content"]
            result = json.loads(content)
            # 兼容：如果返回的是旧格式（tag_texts/age_desc），降级处理
            if "sections" not in result and "constitution_summary" in result:
                return {
                    "constitution_summary": result["constitution_summary"],
                    "sections": {
                        "bazi_analysis": "",
                        "innate_base": result.get("day_master_note", ""),
                        "geo_factor": "",
                        "name_career": "",
                        "dayun_current": "",
                        "constitution_summary_detail": "",
                    }
                }
            return result
        except Exception:
            return None

