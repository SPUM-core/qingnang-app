"""conversation_analyzer — LLM 把用户对话解析成结构化数据

核心职责：给一段用户和青囊的对话 → 返回程序直接能用的 JSON：
  {
    "signals": [          # 用户自述里的生活信号
      {"tag": "bowel", "label": "无便意", "confidence": 0.95},
      {"tag": "sweat", "label": "动则多汗", "confidence": 0.9},
      ...
    ],
    "pathologies": [     # AI 从信号里反推的病理标签
      {"label": "卫气不固", "base": "脾肺偏弱"},
      {"label": "湿遏肠腑", "base": "水行不化"},
      ...
    ],
    "suggestions": [     # AI 给的调理/生活建议（青囊管家的核心产出）
      {"category": "diet", "title": "山药小米红枣粥", "detail": "每周 3 次，早餐", "priority": "medium"},
      {"category": "lifestyle", "title": "戌时泡脚", "detail": "40℃ 15 分钟", "priority": "high"},
      ...
    ],
    "chief_complaint": "排便减少 + 汗多 + 月经不调",  # 一句话主诉（Case.chief_complaint 可以用）
  }
"""
import json
import time
import httpx
from ..config import settings
from .life_signal_extractor import extract_signals as _rule_extract


# ── System Prompt（专用抽取 prompt，不用大模型，短输出）──
_ANALYSIS_SYSTEM = """你是结构化数据抽取器。下面是一段用户和青囊管家的对话。
请从中提取以下三类信息，严格按 JSON 输出，不要额外文字：

## 1. 生活信号 signals
从用户自述里找：
  bowel（二便：便秘/便稀/无便意/腹泻/便血）
  sweat（汗液：汗多/盗汗/自汗/动则多汗）
  sleep（睡眠：难入睡/易醒/多梦/失眠/早醒）
  appetite（食欲：食欲不振/易饿/反酸/腹胀）
  menses（月经：量少/推迟/提前/痛经/闭经）
  mood（情绪：焦虑/易怒/低落/紧张/叹气）
  energy（体力：易疲乏/精力充沛/腰膝酸软）
  thirst（饮水：口渴/不喜水/喜热饮/喜冷饮）
  skin（皮肤：干燥/出油/长痘/发黄）
  breath（呼吸：气短/咳嗽/鼻塞）
  lifestyle（作息/运动/饮食/压力/睡眠时长）
  other（其他）
每条格式 {"tag": "...", "label": "...", "confidence": 0.0-1.0}

## 2. 病理标签 pathologies
从信号反推的中医病理，用生活化表达：
  {"label": "卫气不固", "base": "脾肺偏弱"}
  {"label": "湿遏肠腑", "base": "水行不化"}
标签控制在 1-3 个，base 写依据。

## 3. 调理建议 suggestions
从 AI 回复里提取具体可执行的建议，按 category 分类：
  category: diet(饮食) / lifestyle(生活方式) / herb(食疗方) / exercise(运动) / avoid(禁忌)
  每条 {"category": "...", "title": "...", "detail": "...", "priority": "high/medium/low"}

## 4. 主诉 chief_complaint
用一句话（15 字内）概括用户当前最困扰的问题。

## 约束
- 严格 JSON 格式，不要 markdown
- 没有的字段给空数组 [] 或空字符串 ""
- signals 置信度 ≥ 0.7 才输出
"""


async def analyze_conversation(
    user_message: str,
    assistant_reply: str,
    history: list[dict] | None = None,
    provider: str = "deepseek",
    timeout: float = 10.0,
) -> dict:
    """调 LLM 解析对话，返回结构化数据。

    失败返回空 dict（不抛异常）。
    """
    # 组装历史上下文（最近 3 轮 + 本轮）
    history_text = ""
    if history:
        for h in history[-6:]:  # 最近 3 轮 = 6 条
            role = h.get("role", "")
            content = h.get("content", "")
            history_text += f"{role}: {content}\n"

    user_prompt = f"""## 历史对话\n{history_text}\n## 本轮\nuser: {user_message}\nassistant: {assistant_reply}\n"""

    messages = [
        {"role": "system", "content": _ANALYSIS_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if provider == "deepseek" and settings.DEEPSEEK_API_KEY:
                r = await client.post(
                    f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": settings.DEEPSEEK_MODEL,
                        "messages": messages,
                        "max_tokens": 600,
                        "temperature": 0.1,
                    },
                )
                if r.status_code != 200:
                    return {}
                raw = r.json()["choices"][0]["message"]["content"]
            else:
                # 本地 qingmeng-engine
                r = await client.get(f"{settings.QINGMENG_URL}/health")
                if r.status_code != 200:
                    return {}
                r = await client.post(
                    f"{settings.QINGMENG_URL}/v1/chat/completions",
                    json={
                        "model": settings.QINGMENG_MODEL,
                        "messages": messages,
                        "max_tokens": 600,
                        "temperature": 0.1,
                    },
                )
                if r.status_code != 200:
                    return {}
                raw = r.json()["choices"][0]["message"]["content"]

        # 解析 JSON
        raw = raw.strip()
        # 处理 LLM 可能的 ```json ... ``` 包裹
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0] if "```" in raw[3:] else raw[3:]
        data = json.loads(raw)
        return {
            "signals": data.get("signals", []) or [],
            "pathologies": data.get("pathologies", []) or [],
            "suggestions": data.get("suggestions", []) or [],
            "chief_complaint": data.get("chief_complaint", "") or "",
            "_llm_parsed_at": int(time.time()),
        }
    except Exception:
        # 2026-10-02 修复：LLM 失败时 fallback 到规则引擎，保证 signals 字段不丢失
        try:
            rule_signals = _rule_extract(user_message)
            return {
                "signals": [
                    {"tag": s.tag, "label": s.label,
                     "matched_keywords": s.matched_keywords}
                    for s in rule_signals
                ],
                "pathologies": [],
                "suggestions": [],
                "chief_complaint": "",
                "_llm_parsed_at": None,
                "_fallback": "rule_engine",
            }
        except Exception:
            return {}
