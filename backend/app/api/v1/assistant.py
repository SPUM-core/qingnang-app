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
    """LLM 输出合规后处理 — 替换禁用词 + 去重相邻重复"""
    import re
    if not text:
        return text
    # 1. 整词替换
    for bad, good in PROHIBITED_WORDS.items():
        text = text.replace(bad, good)
    # 2. 直接剔除的短语
    for bad in STRIP_WORDS:
        text = text.replace(bad, "")
    # 3. 去重相邻重复替换词（如 "苦寒药材/苦寒药材" → "苦寒药材"）
    text = re.sub(r'([^/\s]+)[\s]*[\/、][\s]*\1', r'\1', text)
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
# 高频结构化问题 — 引擎直接返回，绕过 LLM
# ═══════════════════════════════════════════════════════

def _intent_shortcut(message: str, brief: dict | None) -> str | None:
    """检测高频结构化问题，用 daily_brief 数据直接拼自然语言回答。

    返回 None = 不是高频问题（走 LLM 路径）
    返回 str = 引擎直接生成的回答（零延迟，确定性）
    """
    if not brief or not message:
        return None

    msg = message.lower()

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
    # ── 1. 构建 System Prompt ──
    system_prompt = build_system_prompt(current, db)

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
    shortcut_reply = _intent_shortcut(body.message, brief)
    if shortcut_reply is not None:
        shortcut_reply = compliance_filter(shortcut_reply)
        return {
            "reply": shortcut_reply,
            "engine": "engine_direct",
            "latency_ms": 0,
            "qingmeng_online": True,
            "brief_context": brief,
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

    # ── 5. 调用 qingmeng-engine chat completions ──
    qingmeng_ok = False
    latency_ms = 0
    reply_text = ""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            h = await client.get(f"{settings.QINGMENG_URL}/health")
            if h.status_code == 200:
                qingmeng_ok = True
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

    # ── 6. Fallback：规则引擎 ──
    if not qingmeng_ok:
        reply_text = _generate_generic_reply(current, db, body.message)
        latency_ms = 0

    # ── 7. 合规后处理 ──
    reply_text = compliance_filter(reply_text)

    return {
        "reply": reply_text,
        "engine": "qingmeng" if qingmeng_ok else "local_fallback",
        "latency_ms": latency_ms,
        "qingmeng_online": qingmeng_ok,
        "brief_context": brief,
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
    from lunar_python import Solar

    birth_date = body.birth_date                    # "1986-08-02"
    birth_hour = body.birth_hour                    # "寅时（3-5点）" 或 None

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
