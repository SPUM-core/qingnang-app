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


class TopologyStateFill(BaseModel):
    """AI 从 S 向量和对话读出来的拓扑状态（不是"病"，是关系网络状态）"""
    label: str = Field(..., description="拓扑状态标签，如'S_火偏强 0.30（梯度场活跃）'")
    base: Optional[str] = Field(None, description="依据：对应哪个 S 向量偏移或对话细节")


class SuggestionFill(BaseModel):
    """AI 给的拓扑调平建议"""
    category: str = Field(..., description="diet(边界整合饮食)/exercise(边界整合运动)/sleep(帧间恢复)/lifestyle(时辰调制)/avoid(拓扑防护)/herb(深层调平)")
    title: str = Field(..., description="具体可执行的标题，如'戌时泡脚 40℃ 15分钟'")
    detail: Optional[str] = Field(None, description="怎么做 + 为什么（对应哪个五形相位/时辰窗口）")
    priority: Optional[str] = Field(None, description="high=直接纠正 ΔV 主偏移方向 / medium / low")


class SignalFill(BaseModel):
    """AI 从用户自述抽取的边界信号（生活细节 → 未来映射到 G_body 的节点）"""
    tag: str = Field(..., description="sleep/appetite/bowel/mood/energy...")
    label: str = Field(..., description="信号标签，如'入睡困难'、'下午3点后疲惫'")
    confidence: Optional[float] = Field(None, description="0.0-1.0")


class AIResponseTemplate(BaseModel):
    """顶层模板 — LLM 除了 reply 还可以填这些槽位（全部可选）"""
    reply: str = Field(..., description="自然语言回复，必填")
    brief_card: Optional[BriefCardFill] = Field(None, description="想展示今日宜忌卡片时填")
    suggested_actions: Optional[list[ActionSuggestion]] = Field(None, description="建议执行的操作")
    # ── 2026-10-04 P2 新增：让 LLM 一次输出所有结构化数据，省掉第二次 LLM 调用 ──
    topology_states: Optional[list[TopologyStateFill]] = Field(None, description="拓扑状态标签（1-3个）")
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
        reply="你的火形梯度偏强（能量流有点急），睡眠是补水形链的最好方式——水形链通了，火形的急就能被缓冲下来。今晚早点睡吧，睡前1小时放下手机让 σ 场降下来...",
        brief_card=BriefCardFill(
            show=True,
            anchor_note="今天乙亥日，木旺土弱——土形储备被木形环挤压，饮食上适合引入低冲突的土性外来边",
            food_highlight="小米粥最适合你——它的五形属性是土+水，温养储备池同时疏通传输链",
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
                label="把入睡困难标记到我的数字模型",
            ),
        ],
        topology_states=[
            TopologyStateFill(label="S_火偏强 0.30（梯度场活跃，能量流偏急）", base="脉搏采集 fire:32 高于健康区间"),
        ],
        suggestions=[
            SuggestionFill(category="lifestyle", title="戌时泡脚 40℃ 15分钟", detail="顺应戌时心包经开阖窗口，帮助火形梯度降下来", priority="high"),
            SuggestionFill(category="sleep", title="今晚22:30前入睡", detail="让水形链在低 V⁺ 密度态下自主扩展", priority="high"),
        ],
        chief_complaint="入睡困难 + 下午3点后疲惫",
        signals=[
            SignalFill(tag="sleep", label="入睡困难", confidence=0.9),
            SignalFill(tag="energy", label="下午3点后疲惫", confidence=0.85),
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
═══ 结构化输出说明（填你觉得对用户有价值的槽位，不确定就省略）═══

```json
{json.dumps(example, ensure_ascii=False, indent=2)}
```

SPUM 对齐的卡片语义（帮你判断什么时候填什么）：

【topology_states — 当前拓扑状态】
  从用户的 S 向量和对话里读出来的拓扑状态。
  说的是关系网络的状态，不是"病"。例：
    "S_火 偏强 0.30（梯度场活跃，能量流偏急）"
    "S_土 储备偏低（可动员的低度节点池不足）"
    "基线→当前漂移 S_水 +0.20（传输链在延伸，但关键边可能还在）"

【suggestions — 拓扑调平建议】
  纠正 ΔV 偏移的具体操作。category 可选值对应 SPUM 操作语义：
    diet      = 边界整合：给 G_body 引入正确 ΔS 方向的外来边（饮食）
    exercise  = 边界整合：发起 V⁺/V⁻ 事件改变局部 σ 地形（运动）
    sleep     = 帧间恢复：让 G_body 在正确时辰进入低 V⁺ 密度态（睡眠）
    lifestyle = 时辰调制：顺应子午流注在正确时辰执行正确动作
    avoid     = 拓扑防护：避免触发特定 ΔS 方向的边界冲突
    herb      = 深层调平（方剂级，需会员 Stage 4+）
  title 要具体可执行（"戌时泡脚 40℃ 15分钟"，不是"注意养生"）
  detail 补充怎么做、为什么（对应哪个五形相位、哪个时辰窗口）
  priority 高优先 = 直接纠正 ΔV 主偏移方向的动作

【brief_card — 今日拓扑窗口】
  当用户问今日宜忌、节气影响、天时建议时填。
  anchor_note  = 今日干支/节气对五形的调制（SPUM 时间帧：S(t) = S_base + ΔS_节气 + ΔS_日干支）
  food_highlight = 今日边界整合最优窗口对应的饮食方向

【suggested_actions — 可执行操作按钮】
  把一段对话里最重要的那个下一步变成可点击按钮。一次最多 1-2 个。
  什么时候出现：
    · 用户主动问 "我该怎么帮你收集数据？" → 引导采集（navigate collect）
    · 用户自己说了症状 → 标记到数字模型（mark_life_signal）
    · 用户明确说"我最近睡不好" → 创建生活提醒（add_reminder）
    · 用户给了主诉 → 回填 chief_complaint
  什么时候不要：用户只是闲聊或提问时，不要强行推。

可用的 action_id 列表：
{action_list_text}

tag 可选值（mark_life_signal 用）：sleep / appetite / bowel / mood / energy / thirst / sweat / skin / breath / other

【signals — 自动抽取的生活信号】
  用户对话里提到的生活细节。例：
    tag=sleep label="入睡困难"
    tag=energy label="下午3点后疲惫"
    tag=appetite label="午饭后犯困"
  confidence 是你对这个信号准确性的信心（0.0-1.0）。

请根据对话内容和用户数据，决定哪些槽位值得填写。

【reply 格式要求 —— 必须用 Markdown】
reply 字段请使用标准 Markdown 格式，让前端能渲染出漂亮的排版：
  • 小节标题用 ### 三级标题 / ## 二级标题
  • 数据对比用表格：
    | 五行 | 当旺 | 失运 |
    |------|------|------|
    | 火   | 高潮 | 火衰 |
  • 重要术语和结论用 **加粗**
  • 数学/公式用 LaTeX：行内 $S(t) = S_{{base}} + \\Delta S$，块级用 $$...$$
  • 建议列表用 - 开头
  • 格式示例：
    ### 今日饮食宜忌
    **宜**：小米粥、山药、绿色蔬菜
    **忌**：冷饮、辛辣、晚餐过饱
"""


# ═══════════════════════════════════════════════════════
# Layer 4: JSON 解析 + normalize（LLM 可能输出不完美 JSON）
# ═══════════════════════════════════════════════════════

def extract_json(text: str) -> dict | None:
    """从 LLM 输出里提取 JSON 对象。

    LLM 可能在 JSON 外面包了解释文本，或没严格按 JSON 格式输出：
    1. 先尝试直接 json.loads
    2. 失败则找第一个 { 和最后一个 } 之间的子串再 parse
    3. 都失败 → 尝试从截断的 JSON 里手动提取 reply 字段（LLM max_tokens 不够时 JSON 会被截断，但 reply 通常在前半部分完整）
    4. 都不行返回 None
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
            pass
    # 最后兜底：尝试从截断 JSON 里正则提取 reply 字段
    # reply 通常是第一个 key，值是字符串，即使后面槽位被截断，reply 值大概率完整
    reply_match = re.search(r'"reply"\s*:\s*"(.*?)"\s*[,}]', text, re.DOTALL)
    if reply_match:
        reply_val = reply_match.group(1).encode('utf-8').decode('unicode_escape')
        return {"reply": reply_val}
    return None


def normalize_parsed(data: dict) -> AIResponseTemplate | None:
    """字段级 normalize：对 LLM 返回的 dict 做最小纠正，确保能塞进 Pydantic 模型。

    失败返回 None（调用方走 fallback）。
    """
    if not data or not isinstance(data, dict):
        return None
    normalized = {}
    # reply 必须是字符串 —— 防御：LLM 偶尔把 reply 写成 dict/list
    raw_reply = data.get("reply", "")
    if isinstance(raw_reply, str):
        normalized["reply"] = raw_reply
    elif isinstance(raw_reply, (dict, list)):
        normalized["reply"] = json.dumps(raw_reply, ensure_ascii=False)
    else:
        normalized["reply"] = str(raw_reply or "")
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
    # topology_states：防御性修复（label 必须 str）
    # 2026-10-11：兼容旧键 pathologies（历史消息/旧模板缓存），新键为 topology_states
    p = data.get("topology_states")
    if not isinstance(p, list):
        p = data.get("pathologies")  # 兼容旧契约
    if isinstance(p, list):
        normalized["topology_states"] = [
            x for x in p
            if isinstance(x, dict) and isinstance(x.get("label"), str) and x["label"].strip()
        ]
    # suggestions：防御性修复（category/title 必填 str）
    sg = data.get("suggestions")
    if isinstance(sg, list):
        normalized["suggestions"] = [
            x for x in sg
            if isinstance(x, dict)
            and isinstance(x.get("category"), str) and x["category"].strip()
            and isinstance(x.get("title"), str) and x["title"].strip()
        ]
    # chief_complaint：可选 str
    cc = data.get("chief_complaint")
    if isinstance(cc, str) and cc.strip():
        normalized["chief_complaint"] = cc
    # signals：防御性修复
    sig = data.get("signals")
    if isinstance(sig, list):
        normalized["signals"] = [
            x for x in sig
            if isinstance(x, dict)
            and isinstance(x.get("tag"), str) and x["tag"].strip()
            and isinstance(x.get("label"), str) and x["label"].strip()
        ]
    try:
        return AIResponseTemplate(**normalized)
    except Exception as e:
        # Pydantic 验证失败 —— 记录日志但不抛
        print(f"[normalize_parsed] Pydantic validation failed: {e}")
        return None
