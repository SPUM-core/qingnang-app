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
# Rule-based lifestyle fallback — 根据 v_base 五形向量 + 今日干支生成建议
# 不用 LLM，靠中医五行生克硬规则，离线也能给有用建议
# ═══════════════════════════════════════════════════════════
def _fallback_lifestyle(v: dict, payload: dict) -> dict:
    from datetime import date
    from ....utils.trajectory_algorithm import get_liunian, ganzhi_main_elem

    # 1. 今日干支
    today = date.today()
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
    }]
    cloth_bad = []
    if day_elem == strong:
        cloth_bad.append({
            "id": "cloth-avoid-day",
            "title": f"忌穿{WX_COLOR[day_elem]}系",
            "desc": f"今日{WX_CN[day_elem]}主气，穿同色助旺过甚",
            "reason": f"今日干支 {ln['g']}{ln['z']} 主气 {WX_CN[day_elem]}",
        })

    # 4. 饮食建议
    food_good = [{
        "id": "food-1",
        "title": f"宜吃{WEAK_FOOD[weak][0]}等补{WX_CN[weak]}食物",
        "desc": "、".join(WEAK_FOOD[weak]) + f" — 按相生律补{WX_CN[weak]}形",
        "reason": f"五形相生：弱{WX_CN[weak]}需要滋养",
    }]
    food_bad = [{
        "id": "food-bad-1",
        "title": f"忌{STRONG_AVOID[strong][0]}",
        "desc": "、".join(STRONG_AVOID[strong]) + f" — 避免助{WX_CN[strong]}形过旺",
        "reason": f"{WX_CN[strong]}形分数 {scores[strong]:.0f} 最高",
    }]

    # 5. 今日宜忌（干支 + v_base 综合）
    yi_text = f"今日{WX_CN[day_elem]}日·宜{WX_COLOR[weak]}系·养{WX_CN[weak]}形"
    ji_text = f"忌穿{WX_COLOR[strong]}系·忌{STRONG_AVOID[strong][0]}等助{WX_CN[strong]}食物"

    # 6. 住房/作息提醒
    home = []
    if strong == "fire":
        home.append({"id": "home-1", "title": "午后宜独处静养", "desc": "火形旺易焦躁，避开午后阳气盛时段"})
    if weak == "water":
        home.append({"id": "home-2", "title": "亥时泡脚养肾", "desc": "21:00-23:00 是肾经主时，泡脚 40℃/15min"})
    if weak == "earth":
        home.append({"id": "home-3", "title": "辰时养胃", "desc": "7:00-9:00 辰时脾经旺，宜温热早餐"})

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

    return {
        "anchor": {
            "ganzhi": f"{ln['g']}{ln['z']}",
            "state": "rule-based",
            "yi": yi_text,
            "ji": ji_text,
            "dangling_elem": WX_CN[weak],
            "feixing": f"补{WX_CN[weak]}抑{WX_CN[strong]}",
        },
        "timeline": [],
        "cloth_reminders": cloth_good + cloth_bad,
        "food_good": food_good,
        "food_bad": food_bad,
        "home_reminders": home,
        "absolute_avoid": absolute,
        "relative_avoid": relative,
        "engine": "backend_fallback_rule",
        "note": "青檬引擎暂不可用，以下为 rule-based 五行建议",
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


