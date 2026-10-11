"""inquiry - 多阶段问诊引擎：结构化问诊会话 / 问题生成 / 状态摘要"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
import json
import httpx

from ....database import get_db
from ....models import User, Case
from ....config import settings
from ...deps import get_current_user
from ....utils.maturity import compute_maturity, STAGE_DEFS
from ....utils.trajectory_algorithm import (
    DIMS as _WU, get_wu_thresholds as _get_wu_thresholds,
)
from .bazi import _DEFAULT_V_INNATE

router = APIRouter()

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
    from ....models import InquirySession
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
    from ....models import InquirySession
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
    from ....models import InquirySession

    # 1. 注入用户上下文（含身高体重）
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
    from ....models import InquirySession

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
    from ....models import InquirySession

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

    # 调 LLM（全局 DeepSeek）
    raw_text = None
    if settings.DEEPSEEK_API_KEY:
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
    if settings.DEEPSEEK_API_KEY:
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

    if raw_text:
        parsed = _parse_llm_json(raw_text)
        if parsed:
            return parsed

    # Fallback：从 answer_bank 推最小摘要
    v_base = user_context.get("v_base", {})
    _wt, _st = _get_wu_thresholds(v_base)
    weak = [k for k in _WU if isinstance(v_base.get(k), (int, float)) and v_base.get(k) < _wt]
    strong = [k for k in _WU if isinstance(v_base.get(k), (int, float)) and v_base.get(k) > _st]
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


