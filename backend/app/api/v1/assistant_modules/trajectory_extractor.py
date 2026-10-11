"""人生轨迹信息提取 — 数字模型自修正闭环（2026-10-11）

从 AI 日常对话中提取用户提到的关键健康/生活事件（如"25岁做过阑尾手术"），
经 LLM 提问确认 + 置信度标注后记录到 TrajectoryEvent 对应年龄节点，
确认后才把 damage/boost 五行增量应用到 Case.v_current（数字模型修正）。

闭环：
  extract_trajectory_events  (LLM 提取候选事件 → 全部落 pending + 低置信)
    → 对话内 question 提示 → 用户下次回答
  confirm_trajectory_event   (LLM 批量判定 确认/否认/无关 → 状态机转移)
    → confirmed → apply_to_case (幂等修正 v_current)
"""
import json as _json
import logging
from typing import Optional

import httpx

from ....config import settings
from ....models import Case, TrajectoryEvent

logger = logging.getLogger(__name__)

# 允许的事件类型（对齐 trajectory_events.event_type）
_EVENT_TYPES = {"手术", "药物", "窗口期", "转大运", "外力", "间断", "波动"}
# 方向枚举
_DIRECTIONS = {"发散", "收敛", "注意"}
# 五行维度
_WUXING = ["wood", "fire", "earth", "metal", "water"]


async def _deepseek_json(messages: list[dict], max_tokens: int = 900) -> Optional[dict]:
    """调 DeepSeek 并返回 json object；失败返回 None。"""
    if not settings.DEEPSEEK_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.DEEPSEEK_MODEL,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                }
            )
            if r.status_code != 200:
                logger.warning(f"[trajectory] DeepSeek HTTP {r.status_code}")
                return None
            content = r.json()["choices"][0]["message"]["content"]
            return _json.loads(content) if content else None
    except Exception as e:
        logger.warning(f"[trajectory] DeepSeek 不可达: {e}")
        return None


# ═══════════════════════════════════════════════════════
# 1. 提取候选事件（LLM）
# ═══════════════════════════════════════════════════════
async def extract_trajectory_events(user_text: str) -> list[dict]:
    """从用户消息中提取带年龄的关键健康/生活事件（不回填补脑）。"""
    if not user_text or not user_text.strip():
        return []

    system_prompt = (
        "你是青囊的数字档案员，从用户的自述中提取带有明确年龄/年份的关键人生事件。\n"
        "提取范围（健康+生活）：手术、外伤、重大疾病确诊、长期用药、住院、生育、"
        "升学、结婚、换城市、职业重大变动等。\n"
        "硬规则：\n"
        "1. 只提取用户【明确提到年龄或年份】的事件；没有明确时间的不要编造年龄。\n"
        "2. 不回填补脑、不推断不存在的信息；拿不准的事件也提出，但 confidence 标低。\n"
        "3. 每条事件给一个自然、温和的确认问句 question，用于向用户确认（语气像朋友，不带审判）。\n"
        "4. 事件类型从集合中选：手术/药物/窗口期/转大运/外力/间断/波动。\n"
        "5. damage/boost 为五行损伤/增益量（可选，空对象即可），键限：wood/fire/earth/metal/water。\n"
        "输出 JSON：{\"events\":[{\"event_type\":str,\"age\":int,\"label\":str,\n"
        "  \"direction\":str,\"damage\":{},\"boost\":{},\"confidence\":float,\n"
        "  \"question\":str}]}。无事件时 events 为空数组。"
    )
    user_prompt = f"用户说：{user_text}"

    data = await _deepseek_json([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])
    if not data or not isinstance(data.get("events"), list):
        return []

    cleaned = []
    for ev in data["events"]:
        if not isinstance(ev, dict):
            continue
        et = str(ev.get("event_type", ""))
        if et not in _EVENT_TYPES:
            continue
        age = ev.get("age")
        if not isinstance(age, int) or age < 0 or age > 120:
            continue
        # needs_confirm=true 时置信度压到 0.4 封顶（不直接采信）
        conf = float(ev.get("confidence", 0.5) or 0.5)
        conf = max(0.0, min(conf, 1.0))
        if ev.get("needs_confirm", True):
            conf = min(conf, 0.4)
        cleaned.append({
            "event_type": et,
            "age": age,
            "label": str(ev.get("label", "")).strip()[:200],
            "direction": str(ev.get("direction", "注意")) if str(ev.get("direction", "")) in _DIRECTIONS else "注意",
            "damage": {k: float(v) for k, v in (ev.get("damage") or {}).items() if k in _WUXING},
            "boost": {k: float(v) for k, v in (ev.get("boost") or {}).items() if k in _WUXING},
            "confidence": conf,
            "question": str(ev.get("question", "")).strip()[:200],
        })
    return cleaned


# ═══════════════════════════════════════════════════════
# 2. 落库（待确认）+ 去重
# ═══════════════════════════════════════════════════════
def _norm_key(case_id: int, age: int, event_type: str, label: str) -> str:
    return f"{case_id}:{age}:{event_type}:{label[:20]}"


def upsert_pending_events(db, case: Case, events: list[dict]) -> list[str]:
    """把候选事件写入 TrajectoryEvent（全部 pending + 低置信）；返回 question 列表。"""
    questions: list[str] = []
    if not events:
        return questions
    for ev in events:
        key = _norm_key(case.id, ev["age"], ev["event_type"], ev["label"])
        existing = db.query(TrajectoryEvent).filter(
            TrajectoryEvent.proposed_key == key,
            TrajectoryEvent.case_id == case.id,
        ).first()
        if existing:
            # 已存在 → 仅更新置信度（不重复新增）
            if ev["confidence"] > (existing.confidence or 0):
                existing.confidence = ev["confidence"]
                existing.pending = True
                existing.confirmed = False
        else:
            db.add(TrajectoryEvent(
                case_id=case.id,
                age=ev["age"],
                event_type=ev["event_type"],
                label=ev["label"],
                direction=ev["direction"],
                damage=ev["damage"] or None,
                boost=ev["boost"] or None,
                source="llm_proposed",
                confidence=ev["confidence"],
                pending=True,
                confirmed=False,
                proposed_key=key,
            ))
        if ev["question"] and ev["question"] not in questions:
            questions.append(ev["question"])
    return questions


# ═══════════════════════════════════════════════════════
# 3. 确认状态机（LLM 批量判定）
# ═══════════════════════════════════════════════════════
async def confirm_trajectory_event(db, case: Case, user_text: str) -> None:
    """扫描该 case 所有 pending=True 事件，用当前用户消息批量判定 确认/否认/无关。"""
    pending_events = db.query(TrajectoryEvent).filter(
        TrajectoryEvent.case_id == case.id,
        TrajectoryEvent.pending.is_(True),
    ).all()
    if not pending_events:
        return

    events_desc = "\n".join(
        f"[{e.id}] {e.age}岁 {e.event_type}: {e.label}"
        for e in pending_events
    )
    system_prompt = (
        "你是青囊的档案确认员。下面列出一批待确认的人生事件与用户的回复。\n"
        "判断用户回复对每条事件是：confirm（确认）/ deny（否认）/ unrelated（无关）。\n"
        "规则：明确肯定（是/对/做过/当时…）→ confirm；明确否定（没有/不是/记错了）→ deny；"
        "其它回答 → unrelated。\n"
        '输出 JSON：{"decisions":[{"id":int,"verdict":"confirm|deny|unrelated"}]}。'
    )
    user_prompt = f"待确认事件：\n{events_desc}\n\n用户最新回复：{user_text}"

    data = await _deepseek_json([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])
    if not data or not isinstance(data.get("decisions"), list):
        return

    by_id = {e.id: e for e in pending_events}
    for dec in data["decisions"]:
        try:
            ev = by_id[int(dec.get("id"))]
        except (KeyError, TypeError, ValueError):
            continue
        verdict = str(dec.get("verdict", "unrelated"))
        if verdict == "confirm":
            ev.pending = False
            ev.confirmed = True
            ev.confidence = 0.9
            ev.source = "llm_confirmed"
            apply_to_case(case, ev)
        elif verdict == "deny":
            ev.pending = False
            ev.confirmed = False
            ev.confidence = 0.0
            ev.source = "llm_denied"


# ═══════════════════════════════════════════════════════
# 4. 数字模型修正（仅 confirmed，幂等）
# ═══════════════════════════════════════════════════════
# 已应用事件集合（进程内按 case.id 记录，保证同一事件只应用一次）
_APPLIED_EVENTS: dict[int, set[int]] = {}


def apply_to_case(case: Case, event) -> None:
    """把确认事件的 damage/boost 五行增量应用到 Case.v_current（幂等）。"""
    if not event.confirmed:
        return
    applied = _APPLIED_EVENTS.setdefault(case.id, set())
    if event.id in applied:
        return  # 幂等：同一事件只应用一次

    v_cur = dict(case.v_current or case.v_baseline or {})
    for k in _WUXING:
        if k not in v_cur:
            v_cur[k] = 50.0
    for k, v in (event.damage or {}).items():
        v_cur[k] = float(v_cur.get(k, 50.0)) - float(v)  # 损伤：扣减
    for k, v in (event.boost or {}).items():
        v_cur[k] = float(v_cur.get(k, 50.0)) + float(v)  # 增益：加回
    case.v_current = v_cur
    applied.add(event.id)
    logger.info(f"[trajectory] apply_to_case case={case.id} event={event.id} → v_current={v_cur}")
