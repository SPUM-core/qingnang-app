"""chat - 主对话链路：AI 对话 / 系统提示词 / 合规过滤 / 意图捷径 / 历史压缩 / Action 白名单"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
import httpx
import json
import logging
import time

from ....database import get_db
from ....models import User, Case, Observation, TreatmentPlan, ChatMessage, LifeSignal
from ....config import settings
from ...deps import get_current_user
from ....utils.life_signal_extractor import extract_signals, signals_to_dict_list
from ....utils.conversation_analyzer import analyze_conversation
from ....utils.maturity import compute_maturity, STAGE_DEFS
from ....utils.trajectory_algorithm import (
    DIMS as _WU, detect_vector_scale as _detect_vector_scale, get_wu_thresholds as _get_wu_thresholds,
)
from ....utils.wuxing import graph_diagnose as _graph_diagnose

router = APIRouter()
logger = logging.getLogger(__name__)


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
    # provider 字段已删除 — 全局只用 DeepSeek 云端

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



# ── 子域模块（独立演化）──────────────────────────────
# 提示词构建 / Action 白名单与引导 / 意图捷径 / 历史压缩
from .chat_prompt import build_system_prompt
from .chat_actions import (
    _EXECUTE_WHITELIST, _register_execute, _generate_actions,
    _exec_add_reminder, _exec_update_chief_complaint, _exec_mark_mentality,
    _brief_has_content, _user_asked_about_brief, _generate_generic_reply,
)
from .chat_shortcuts import _intent_shortcut
from .chat_compress import (
    _compress_old_messages,
    CHAT_HISTORY_MAX_BYTES, CHAT_HISTORY_BATCH_PAIRS, CHAT_HISTORY_KEEP_RECENT,
    EPISODIC_TTL_DAYS, PERMANENT_PER_USER_LIMIT,
)
# AI 响应模板（单一信源：app/templates 包）
from ....templates import (
    AIResponseTemplate, extract_json, normalize_parsed, _ACTION_ICONS,
)


def _strip_llm_header_noise(text: str) -> str:
    """剥掉 LLM 偶发幻觉混入的 HTTP 响应头 / 状态行片段。

    触发场景：DeepSeek JSON mode 偶发把 API 响应的 header 文本混入 content。
    典型脏东西：Content-Type: application/json / HTTP/1.1 200 OK / date: / etc.
    这些行在正常聊天回复里绝不该出现。
    """
    if not text:
        return text
    import re as _re
    # HTTP 响应头：Xxx-Yyy: zzz 或 Xxx-Yyy:zzz（大小写混合、冒号后可选空格）
    _header_line = _re.compile(r"^\s*[A-Za-z][A-Za-z0-9\-]+:\s*\S.*$")
    # HTTP 状态行：HTTP/1.1 200 OK / HTTP/2 200 OK 等
    _status_line = _re.compile(r"^\s*HTTP/\d\.\d\s+\d{3}\s*.*$")

    cleaned = []
    for line in text.split("\n"):
        if _status_line.match(line):
            continue
        if _header_line.match(line) and not line.startswith(("【", "·", "-", "#", "。", "答", "你", "我", "今", "宜", "忌")):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


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

    # ── 4a. 注入待确认的人生轨迹事件（对话内确认机制）──
    #      从该 case 读取 pending 事件的问题，让主 LLM 在本次回复中自然、温和地提问确认
    try:
        if case is not None:
            from ....models import TrajectoryEvent as _TE2
            _pending_qs = []
            _pend = db.query(_TE2).filter(
                _TE2.case_id == case.id,
                _TE2.pending.is_(True),
            ).all()
            for _ev in _pend[:3]:
                if getattr(_ev, "question", None):
                    _pending_qs.append(f"- {_ev.age}岁{_ev.event_type}：「{_ev.label}」→ {_ev.question}")
            if _pending_qs:
                system_prompt += (
                    "\n\n【待确认的档案信息】用户之前提到过以下事件，但还没确认。"
                    "如果这次对话自然相关，请用轻松、关心的语气向用户确认（不要生硬盘问，一次最多问1条）：\n"
                    + "\n".join(_pending_qs)
                )
    except Exception:
        pass  # 待确认注入失败不影响对话

    # ── 4. 组装 messages ──
    messages = [{"role": "system", "content": system_prompt}]
    for h in (body.history or [])[-10:]:
        if h.get("role") in ("user", "assistant"):
            messages.append({"role": h["role"], "content": h.get("content", "")})
    messages.append({"role": "user", "content": body.message})

    # ── 5. 调 DeepSeek（唯一 LLM，全局 json_object mode）──
    llm_ok = False
    latency_ms = 0
    reply_text = ""
    raw = ""
    json_obj = None
    parsed_template: AIResponseTemplate | None = None

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
                        "max_tokens": 2400,
                        "response_format": {"type": "json_object"},
                    }
                )
                latency_ms = int((time.time() - start) * 1000)
                if r.status_code == 200:
                    raw = r.json()["choices"][0]["message"]["content"]
                    json_obj = extract_json(raw)
                    parsed_template = normalize_parsed(json_obj or {})
                    if parsed_template:
                        reply_text = parsed_template.reply
                    elif json_obj and isinstance(json_obj.get("reply"), str) and json_obj["reply"].strip():
                        reply_text = json_obj["reply"]
                    else:
                        reply_text = raw
                    llm_ok = True
        except Exception:
            llm_ok = False

    # ── 6. Fallback：规则引擎（加空回复安全网）──
    if not llm_ok or not reply_text or not reply_text.strip():
        if llm_ok and raw and raw.strip() and (not parsed_template or not parsed_template.reply.strip()):
            reply_text = raw.strip()
        else:
            reply_text = _generate_generic_reply(current, db, body.message)
        latency_ms = latency_ms if latency_ms else 0

    # ── 6b. 剥掉 LLM 幻觉混入的 HTTP 响应头 ──
    # DeepSeek JSON mode 偶发：模型会在回复文本里混入 Content-Type / HTTP/1.1 / 状态行等
    reply_text = _strip_llm_header_noise(reply_text)

    # ── 7. 合规后处理 ──
    reply_text = compliance_filter(reply_text, stage=maturity["stage"])

    # engine 标签：全局只用 deepseek，失败降级 local_fallback
    engine_tag = "deepseek" if llm_ok else "local_fallback"
    model_name = settings.DEEPSEEK_MODEL if llm_ok else "—（本地 fallback）"

    # ── 8. 持久化对话 + 抽取生活信号（青囊生活管家的数据化核心）──
    case = db.query(Case).filter(Case.user_id == current.id).first()
    signals_user_msg = []        # 返回给前端的本轮信号（规则引擎快速命中）
    analysis_result: dict = {}   # LLM 解析出的完整结构化数据（异步落库）

    # ── 8a. 语音样本持久化 + 触发闻诊 ──
    voice_saved = None
    if body.voice_base64 and len(body.voice_base64) > 500:
        try:
            import base64 as _b64
            from ....utils.voice_service import save_voice_sample, trigger_voice_analysis
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
            if parsed_template and parsed_template.topology_states:
                analysis_result = {
                    "topology_states": [p.model_dump() if hasattr(p, 'model_dump') else p for p in parsed_template.topology_states],
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
                    provider=engine_tag,
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

    # ── 8i. 人生轨迹信息提取（异步，不阻塞对话）──
    #      从用户消息提取关键健康/生活事件 → 落 pending 待确认；
    #      同时用当前消息确认历史 pending 事件 → 确认后修正数字模型。
    try:
        from ....models import TrajectoryEvent as _TE  # noqa: F401
        from .trajectory_extractor import (
            extract_trajectory_events, upsert_pending_events, confirm_trajectory_event,
        )

        async def _trajectory_task(_db_session_factory=get_db, _case_id=case.id if case else None):
            # 独立 session，避免与主请求 session 竞争
            gen = _db_session_factory()
            _db = next(gen) if hasattr(gen, "__next__") else gen
            try:
                evs = await extract_trajectory_events(body.message)
                if _case_id and evs:
                    _case = _db.query(Case).filter(Case.id == _case_id).first()
                    if _case:
                        questions = upsert_pending_events(_db, _case, evs)
                        _db.commit()
                        if questions:
                            logger.info(f"[trajectory] {len(questions)} 条待确认事件入库")
                if _case_id:
                    _case = _db.query(Case).filter(Case.id == _case_id).first()
                    if _case:
                        await confirm_trajectory_event(_db, _case, body.message)
                        _db.commit()
            except Exception as _e:
                logger.warning(f"[trajectory] 后台提取失败: {_e}")
                try:
                    _db.rollback()
                except Exception:
                    pass
            finally:
                try:
                    _db.close()
                except Exception:
                    pass

        _asyncio.create_task(_trajectory_task())
    except Exception:
        pass  # 轨迹提取不可用不影响对话

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
        "provider": engine_tag,
        "model_name": model_name,
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
            "topology_states": (analysis_result or {}).get("topology_states") or (analysis_result or {}).get("pathologies", []),
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
