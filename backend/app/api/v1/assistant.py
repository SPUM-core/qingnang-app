"""assistant - 青囊管家 AI 对话代理（转发到本地 qingmeng-engine）"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import httpx
import json
import time

from ...database import get_db
from ...models import User, Case, Observation, TreatmentPlan
from ...config import settings
from ..deps import get_current_user

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


def compliance_filter(text: str) -> str:
    """LLM 输出合规后处理 — 替换禁用词，添加合规声明"""
    if not text:
        return text
    # 1. 整词替换
    for bad, good in PROHIBITED_WORDS.items():
        text = text.replace(bad, good)
    # 2. 直接剔除的短语
    for bad in STRIP_WORDS:
        text = text.replace(bad, "")
    return text


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)  # [{role, content}] 最近 N 轮


# ═══════════════════════════════════════════════════════
# System Prompt 构建器 - 注入用户完整数字模型
# ═══════════════════════════════════════════════════════
def build_system_prompt(user: User, db: Session) -> str:
    """构建青囊管家 AI 的 System Prompt（2000+ 字完整上下文）"""
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
# 主路由 - /v1/assistant/chat
# ═══════════════════════════════════════════════════════
@router.post("/chat")
async def chat(body: ChatIn,
               db: Session = Depends(get_db),
               current: User = Depends(get_current_user)):
    """青囊管家 AI 对话"""
    # 1. 构建 System Prompt
    system_prompt = build_system_prompt(current, db)

    # 2. 组装 messages
    messages = [{"role": "system", "content": system_prompt}]
    # 历史对话（最多 10 轮）
    for h in (body.history or [])[-10:]:
        if h.get("role") in ("user", "assistant"):
            messages.append({"role": h["role"], "content": h.get("content", "")})
    messages.append({"role": "user", "content": body.message})

    # 3. 尝试调用 qingmeng-engine
    qingmeng_ok = False
    latency_ms = 0
    reply_text = ""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 先测 health
            h = await client.get(f"{settings.QINGMENG_URL}/health")
            if h.status_code == 200:
                qingmeng_ok = True
                # 调用 chat
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
    except Exception as e:
        qingmeng_ok = False

    # 4. Fallback：通用规则引擎（基于用户 v_base 动态生成）
    if not qingmeng_ok:
        reply_text = _generate_generic_reply(current, db, body.message)
        latency_ms = 0

    # 5. 合规后处理 — 消费级非医疗定位
    reply_text = compliance_filter(reply_text)

    return {
        "reply": reply_text,
        "engine": "qingmeng" if qingmeng_ok else "local_fallback",
        "latency_ms": latency_ms,
        "qingmeng_online": qingmeng_ok,
    }


@router.get("/health")
async def health():
    """检查青檬引擎是否可达"""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.QINGMENG_URL}/health")
            return {
                "qingmeng_online": r.status_code == 200,
                "qingmeng_url": settings.QINGMENG_URL,
                "model": settings.QINGMENG_MODEL,
            }
    except Exception:
        return {"qingmeng_online": False, "qingmeng_url": settings.QINGMENG_URL}


# ═══════════════════════════════════════════════════════
# 结构化推理代理 — 转发到 qingmeng-engine 的推理端点
# ═══════════════════════════════════════════════════════

async def _forward_reasoning(path: str, payload: dict, db: Session, current: User) -> dict:
    """通用推理代理：构造用户完整上下文 → 转发到 qingmeng-engine。"""
    # 1. 注入用户上下文（如果 payload 里没给 v_base）
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
            raise HTTPException(status_code=400, detail="请先完成初始化建档")

    # 2. 尝试转发 qingmeng-engine
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(
                f"{settings.QINGMENG_URL}{path}",
                json=payload,
            )
            if r.status_code == 200:
                data = r.json()
                data["proxied_from"] = settings.QINGMENG_URL
                return data
    except Exception:
        pass

    # 3. Fallback：简单规则（最少保证有输出）
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
    """与 _forward_reasoning 同样的上下文注入逻辑。"""
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
            raise HTTPException(status_code=400, detail="请先完成初始化建档")
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
    """方案调整建议 — 当前方案+观测 → 调整建议 JSON（青檬引擎推理）。"""
    return await _forward_reasoning(
        "/v1/reasoning/treatment",
        body.model_dump(exclude_none=True),
        db, current,
    )


class BaziIn(BaseModel):
    birth_date: str                              # "YYYY-MM-DD"
    birth_hour: str | None = None                # "寅时" / None
    birthplace: str | None = None                # 城市名


@router.post("/reasoning/bazi")
async def reasoning_bazi(body: BaziIn,
                         current: User = Depends(get_current_user)):
    """八字推演 — 前端 onboarding 第一阶段用。"""
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
    raise HTTPException(status_code=502, detail="青檬引擎不可达，请稍后重试")
