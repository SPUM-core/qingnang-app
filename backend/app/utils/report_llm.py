"""report_llm — 检查报告结构化提取（DeepSeek JSON mode）

流水线：文本 → DeepSeek /chat/completions(response_format=json_object) → 结构化 JSON。
输出 schema 固定，media.py 直接入库 MedicalReport.structured。
"""
from __future__ import annotations
import json
import re
import httpx
from typing import Optional

from ..config import settings


# ── System Prompt：要求严格 JSON 输出 ──
SYSTEM_PROMPT = """你是一名医疗报告结构化归档助手。任务是从用户粘贴的报告原始文字中，
提取关键信息并输出严格符合 schema 的 JSON（不要任何 markdown 包裹、解释或额外文字）。

schema：
{
  "report_title": "报告名称，如 血常规 / 甲状腺功能检查 / 胸部CT",
  "report_type":   "lab | imaging | diagnosis | other",
  "report_date":   "YYYY-MM-DD（从报告里找日期；找不到填 null）",
  "items": [
    {
      "name":     "指标名（如 血红蛋白 / ALT）",
      "value":    "数值（带单位，如 12.5 g/L）",
      "ref_range": "参考范围原文（如 12-16 g/L），找不到填 null",
      "flag":     "normal | high | low | abnormal | unknown"
    }
  ],
  "abnormal_findings": ["异常发现1", "异常发现2…"],
  "diagnosis_summary": "报告结论或医生诊断（一句话；没有则 null）",
  "summary": "把上面所有信息浓缩成 2-3 句大白话摘要，供用户快速浏览",
  "trajectory_proposal": {
    "age": null,
    "event_type": "手术|药物|窗口期|外力|波动（选一个最贴合的）",
    "direction":  "发散|收敛|注意",
    "damage": {"fire": X, "metal": Y, ...} — 五形偏移估值，每项 0-30，找不到就 {}",
    "boost":  {} — 增益项，通常空对象
  }
}

规则：
1. items 数组里每个元素是一项可识别的指标；表格型报告按行拆
2. 识别不出的字段填 null 或空数组，不要编造
3. trajectory_proposal 是给青囊时间轴的参考提案，不确定时 age=null、damage={}
4. 只输出 JSON 对象，不要 ```json 包裹，不要解释"""


async def extract_report(text_content: str) -> dict:
    """调 DeepSeek 做结构化提取。超时 45s。"""
    result = {
        "ok": False,
        "provider": "llm",
        "structured": None,
        "summary": None,
        "trajectory_proposal": None,
        "report_title": None,
        "report_type": None,
        "report_date": None,
        "items": [],
        "abnormal_findings": [],
        "diagnosis_summary": None,
        "note": None,
    }

    if not settings.DEEPSEEK_API_KEY:
        result["note"] = "未配置 DEEPSEEK_API_KEY，跳过 LLM 提取"
        return result

    # 用户 prompt：直接贴原始文本（限制长度防 token 爆炸）
    MAX_CHARS = 12000
    user_prompt = (
        "以下是从用户上传文件中提取的原始文字，请按 system 指令输出 JSON：\n\n"
        f"━━━ 原始文字开始 ━━━\n{text_content[:MAX_CHARS]}\n━━━ 原始文字结束 ━━━"
    )

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(
                f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
                json={
                    "model": settings.DEEPSEEK_MODEL,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": user_prompt},
                    ],
                    "max_tokens": 2500,
                },
            )
    except httpx.TimeoutException:
        result["note"] = "LLM 请求超时（45s），请稍后手动重试"
        result["provider"] = "timeout"
        return result
    except Exception as e:
        result["note"] = f"LLM 调用异常：{e}"
        result["provider"] = "error"
        return result

    if r.status_code != 200:
        result["note"] = f"LLM HTTP {r.status_code}: {r.text[:300]}"
        result["provider"] = "error"
        return result

    raw_content = r.json()["choices"][0]["message"]["content"]

    # 解析 JSON（response_format 已强制，但兜底 strip markdown fence）
    try:
        j = json.loads(_strip_json_fence(raw_content))
    except Exception as e:
        result["note"] = f"LLM 返回不是合法 JSON：{e}"
        result["provider"] = "parse_error"
        result["structured"] = {"_raw": raw_content[:2000]}
        return result

    # 填充
    result["ok"] = True
    result["structured"] = j
    result["report_title"] = j.get("report_title")
    result["report_type"] = j.get("report_type")
    result["report_date"] = j.get("report_date")
    result["items"] = j.get("items", []) or []
    result["abnormal_findings"] = j.get("abnormal_findings", []) or []
    result["diagnosis_summary"] = j.get("diagnosis_summary")
    result["summary"] = j.get("summary")
    result["trajectory_proposal"] = j.get("trajectory_proposal")
    return result


def _strip_json_fence(text: str) -> str:
    """LLM 偶尔会套 ```json ... ```，剥掉。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()
