"""L2+ 模板架构 — AI 响应的 Pydantic 模板 + 注册表 + JSON 解析

让 AI 看到填空位 → 输出结构化 JSON → 后端消费。
这是单一信源（single source of truth），assistant.py 只 import 这里。
"""
from __future__ import annotations
import json
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════
# Layer 3: Action Params 模板（每个白名单 action 的 typed params）
# ═══════════════════════════════════════════════════════

class AddReminderParams(BaseModel):
    """创建一条今日生活提醒"""
    content: str = Field(..., min_length=1, max_length=200,
                         description="提醒内容，如'今晚22:30前入睡'")


class MarkLifeSignalParams(BaseModel):
    """快速标记当前饮食/运动/排便信号 → LifeSignal"""
    tag: str = Field(..., description="信号标签：sleep/appetite/bowel/mood/energy/thirst/sweat/skin/breath/other")
    label: str = Field(..., min_length=1, max_length=100,
                       description="具体描述，如'入睡困难'、'大便偏干'")


class UpdateChiefComplaintParams(BaseModel):
    """回填 Case.chief_complaint"""
    chief_complaint: str = Field(..., min_length=1, max_length=200,
                                  description="用户的主要不适主诉")


class NavigateParams(BaseModel):
    """跳转到 App 内某个页面"""
    route: str = Field(..., description="跳转路径：/collect/ppg /notifications /case /discover /shop")


# action_id → params 模板的注册表（单一信源）
_ACTION_PARAMS_MODELS: dict[str, type[BaseModel]] = {
    "add_reminder": AddReminderParams,
    "mark_life_signal": MarkLifeSignalParams,
    "update_chief_complaint": UpdateChiefComplaintParams,
    "navigate": NavigateParams,
}

# action_id → 展示图标（与前端 action-icon 一致）
_ACTION_ICONS: dict[str, str] = {
    "add_reminder": "🔔",
    "mark_life_signal": "✅",
    "update_chief_complaint": "📝",
    "navigate": "→",
}


def validate_action_params(action_id: str, raw_params: dict) -> BaseModel | None:
    """L3 新增：按 action_id 匹配 typed params model 做 Pydantic 验证。

    返回验证通过的 Pydantic 实例（.model_dump() 可拿干净 dict）。
    返回 None 表示 action_id 未知 或 验证失败（静默丢弃，不抛异常）。
    """
    model = _ACTION_PARAMS_MODELS.get(action_id)
    if not model:
        return None
    try:
        return model(**(raw_params or {}))
    except Exception:
        return None


# ═══════════════════════════════════════════════════════
# Layer 2: AI Response 模板（顶层输出模板）
# ═══════════════════════════════════════════════════════

class ActionSuggestion(BaseModel):
    """AI 在回复里建议执行的真实操作 — LLM 看到这个 schema 后自己填"""
    action_id: str = Field(..., description="可用值见 system prompt 里的 action 列表")
    params: dict = Field(default_factory=dict, description="按 action_id 的模板填字段")
    label: Optional[str] = Field(None, description="展示给用户的按钮文案，如留空后端补默认")


class BriefCardFill(BaseModel):
    """AI 对今日宜忌/饮食卡片的解读（LLM 填的人话注释）"""
    show: bool = Field(True, description="是否展示卡片（用户问了宜忌/饮食时为 true）")
    anchor_note: Optional[str] = Field(None, description="干支宜忌的人话解读")
    food_highlight: Optional[str] = Field(None, description="重点推荐的那道菜")


class PathologyFill(BaseModel):
    """AI 从对话反推的病理标签（可选）"""
    label: str = Field(..., description="病理标签，如'寒湿凝结'")
    base: Optional[str] = Field(None, description="病理依据，如'腰膝酸冷痛+阴雨天加重'")


class SuggestionFill(BaseModel):
    """AI 给的调理建议（可选）"""
    category: str = Field(..., description="diet/lifestyle/exercise/sleep/avoid/herb")
    title: str = Field(..., description="建议标题，如'戌时泡脚'")
    detail: Optional[str] = Field(None, description="具体做法，如'40℃ 15分钟'")
    priority: Optional[str] = Field(None, description="high/medium/low")


class SignalFill(BaseModel):
    """AI 从用户自述抽取的生活信号（可选）"""
    tag: str = Field(..., description="sleep/appetite/bowel/mood/energy...")
    label: str = Field(..., description="信号标签，如'入睡困难'")
    confidence: Optional[float] = Field(None, description="0.0-1.0")


class AIResponseTemplate(BaseModel):
    """顶层模板 — LLM 除了 reply 还可以填这些槽位（全部可选）"""
    reply: str = Field(..., description="自然语言回复，必填")
    brief_card: Optional[BriefCardFill] = Field(None, description="想展示今日宜忌卡片时填")
    suggested_actions: Optional[list[ActionSuggestion]] = Field(None, description="建议执行的操作")
    # ── 2026-10-04 P2 新增：让 LLM 一次输出所有结构化数据，省掉第二次 LLM 调用 ──
    pathologies: Optional[list[PathologyFill]] = Field(None, description="病理标签（1-3个）")
    suggestions: Optional[list[SuggestionFill]] = Field(None, description="调理建议（3-5条）")
    chief_complaint: Optional[str] = Field(None, description="一句话主诉")
    signals: Optional[list[SignalFill]] = Field(None, description="用户自述里的生活信号")


# ═══════════════════════════════════════════════════════
# Layer 1: System prompt 注入（告诉 LLM 它有哪些填空位）
# ═══════════════════════════════════════════════════════

def build_response_schema_prompt(whitelist: dict | None = None) -> str:
    """返回给 LLM 看的 JSON schema 描述 + example JSON

    L3: whitelist 参数 = assistant.py 的 _EXECUTE_WHITELIST。
        stage_min 从这里读 — 单一信源，消除 _STAGE_MIN_MAP 重复。
        如果 whitelist 未传入（单元测试等场景），退回到 _ACTION_PARAMS_MODELS.keys() 列 action_id
        但不带 stage_min 提示。
    """
    example = AIResponseTemplate(
        reply="今晚早点睡吧——你的火形偏弱，睡眠是补火最直接的方式。睡前1小时放下手机...",
        brief_card=BriefCardFill(
            show=True,
            anchor_note="今天乙亥日，木旺土弱",
            food_highlight="小米粥最适合你，温养土形",
        ),
        suggested_actions=[
            ActionSuggestion(
                action_id="add_reminder",
                params={"content": "今晚22:30前入睡"},
                label="帮你加一条今晚入睡提醒",
            ),
            ActionSuggestion(
                action_id="mark_life_signal",
                params={"tag": "sleep", "label": "入睡困难"},
                label="标记「入睡困难」到我的数字模型",
            ),
        ],
        # ── P2: 让 LLM 一次输出所有结构化数据 ──
        pathologies=[
            PathologyFill(label="火形偏弱", base="脉搏采集 fire:32 低于健康区间"),
        ],
        suggestions=[
            SuggestionFill(category="lifestyle", title="戌时泡脚", detail="40℃ 15分钟", priority="high"),
        ],
        chief_complaint="入睡困难 + 易疲乏",
        signals=[
            SignalFill(tag="sleep", label="入睡困难", confidence=0.9),
        ],
    ).model_dump()

    # 可用 action_id 列表（注入 system prompt）
    def _props_for(aid: str) -> str:
        m = _ACTION_PARAMS_MODELS[aid]
        props = m.model_json_schema().get("properties", {})
        req = set(m.model_json_schema().get("required", []))
        lines = []
        for k, v in props.items():
            t = v.get("type", "any")
            r = "*" if k in req else ""
            desc = v.get("description", "")[:30]
            lines.append(f"       {k}{r}: {t}  ({desc})")
        return "\n".join(lines) if lines else "       (无 params)"

    # L3: 从 whitelist 读 stage_min（单一信源）
    if whitelist:
        action_list_text = "\n".join(
            f"  - {aid}  (需 Stage {whitelist[aid]['stage_min']}+)\n{_props_for(aid)}"
            for aid in _ACTION_PARAMS_MODELS
            if aid in whitelist
        )
    else:
        action_list_text = "\n".join(
            f"  - {aid}\n{_props_for(aid)}"
            for aid in _ACTION_PARAMS_MODELS
        )

    return f"""
═══ 可用结构化输出格式 ═══

除了自然语言回复，你还可以填写以下可选槽位（不确定就省略或留 null）：

```json
{json.dumps(example, ensure_ascii=False, indent=2)}
```

可用的 action_id 列表：
{action_list_text}

tag 可选值（mark_life_signal 用）：sleep / appetite / bowel / mood / energy / thirst / sweat / skin / breath / other

请根据对话内容和用户数据，决定哪些槽位值得填写。
注意：reply 是自由文本，brief_card 和 suggested_actions 是结构化槽位。
"""


# ═══════════════════════════════════════════════════════
# Layer 4: JSON 解析 + normalize（LLM 可能输出不完美 JSON）
# ═══════════════════════════════════════════════════════

def extract_json(text: str) -> dict | None:
    """从 LLM 输出里提取 JSON 对象。

    LLM 可能在 JSON 外面包了解释文本，或没严格按 JSON 格式输出：
    1. 先尝试直接 json.loads
    2. 失败则找第一个 { 和最后一个 } 之间的子串再 parse
    3. 都失败返回 None
    """
    if not text:
        return None
    # 先尝试直接 json.loads
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    # 找第一个 { 和最后一个 }
    first = text.find('{')
    last = text.rfind('}')
    if first >= 0 and last > first:
        candidate = text[first:last + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return None
    return None


def normalize_parsed(data: dict) -> AIResponseTemplate | None:
    """字段级 normalize：对 LLM 返回的 dict 做最小纠正，确保能塞进 Pydantic 模型。

    失败返回 None（调用方走 fallback）。
    """
    if not data or not isinstance(data, dict):
        return None
    normalized = {}
    # reply 必须是字符串
    normalized["reply"] = str(data.get("reply", ""))
    # brief_card：要么 dict 要么 None
    bc = data.get("brief_card")
    if isinstance(bc, dict):
        normalized["brief_card"] = bc
    # suggested_actions：list[dict]
    sa = data.get("suggested_actions")
    if isinstance(sa, list):
        normalized["suggested_actions"] = [
            a for a in sa if isinstance(a, dict) and a.get("action_id")
        ]
    try:
        return AIResponseTemplate(**normalized)
    except Exception:
        return None
