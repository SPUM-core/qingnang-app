"""archive - 对话存档与生活信号：聊天记录 / LifeSignal 查询 / 健康探针"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from ....database import get_db
from ....models import User, Case, ChatMessage, LifeSignal
from ....config import settings
from ....utils.maturity import compute_maturity
from ...deps import get_current_user
from .chat_actions import ExecuteIn, _EXECUTE_WHITELIST
from app.templates import validate_action_params

router = APIRouter()


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
    """LLM 可用性（全局 DeepSeek）。"""
    return {
        "llm": {
            "provider": "deepseek",
            "model": settings.DEEPSEEK_MODEL,
            "configured": bool(settings.DEEPSEEK_API_KEY),
            "base_url": settings.DEEPSEEK_BASE_URL,
        },
    }
