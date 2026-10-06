"""AI 响应模板注册表

单一信源 — 所有 L2+ 模板模型、action params 注册表、JSON 解析工具都从这里导出。
消费端 (assistant.py, execute 端点) 只 import 这个包，不维护自己的副本。
"""
from .ai_response import (
    # Action Params 模板
    AddReminderParams,
    MarkLifeSignalParams,
    UpdateChiefComplaintParams,
    NavigateParams,
    _ACTION_PARAMS_MODELS,
    _ACTION_ICONS,
    # AI Response 模板
    ActionSuggestion,
    BriefCardFill,
    AIResponseTemplate,
    # 工具函数
    build_response_schema_prompt,
    extract_json,
    normalize_parsed,
    validate_action_params,
)

__all__ = [
    "AddReminderParams",
    "MarkLifeSignalParams",
    "UpdateChiefComplaintParams",
    "NavigateParams",
    "_ACTION_PARAMS_MODELS",
    "_ACTION_ICONS",
    "ActionSuggestion",
    "BriefCardFill",
    "AIResponseTemplate",
    "build_response_schema_prompt",
    "extract_json",
    "normalize_parsed",
    "validate_action_params",
]
