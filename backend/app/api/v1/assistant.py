"""assistant - 青囊管家 AI 对话代理（门面模块）

职责：
  1. 聚合 assistant_modules 下各子域 router（路由注册顺序与原单文件一致）
  2. re-export 公共符号，保持既有外部引用不变：
     - cases.py  → _local_bazi_fallback, BaziIn
     - notifications.py → _fallback_lifestyle
     - tests     → compliance_filter, PROHIBITED_WORDS, STRIP_WORDS

子域划分（每个可独立优化/排查）：
  chat            主对话链路（缓存 / 合规 / 主 chat 路由 / 本地 fallback）
  chat_prompt     系统提示词构建
  chat_actions    Action 白名单与引导路由
  chat_shortcuts  高频结构化问题捷径
  chat_compress   历史容量阈值压缩
  media           语音 / 舌象 / 检查报告
  archive         聊天记录 / LifeSignal 存档 / 健康探针
  reasoning       结构化推理代理（转发 qingmeng-engine + 本地兜底）
  bazi            八字推演（本地 lunar_python 双规则兜底）
  inquiry         多阶段问诊引擎
  lunar           农历日历
  constitution    先天体质推理（SPUM v3/v4）
  constitution_rules  规则版画像 / LLM 润色
"""
from fastapi import APIRouter

from .assistant_modules.chat import router as _chat_router
from .assistant_modules.media import router as _media_router
from .assistant_modules.archive import router as _archive_router
from .assistant_modules.reasoning import router as _reasoning_router
from .assistant_modules.bazi import router as _bazi_router
from .assistant_modules.inquiry import router as _inquiry_router
from .assistant_modules.lunar import router as _lunar_router
from .assistant_modules.constitution import router as _constitution_router

# 聚合路由（顺序与原单文件注册顺序一致，保证 /report/list 先于 /report/{id} 等匹配）
router = APIRouter()
router.include_router(_chat_router)
router.include_router(_media_router)
router.include_router(_archive_router)
router.include_router(_reasoning_router)
router.include_router(_bazi_router)
router.include_router(_inquiry_router)
router.include_router(_lunar_router)
router.include_router(_constitution_router)

# ── re-export 公共符号（保持外部 import 兼容）──────────────────
from .assistant_modules.chat import (
    compliance_filter, PROHIBITED_WORDS, STRIP_WORDS,
    ChatIn,
    _EXECUTE_WHITELIST, _register_execute,
    _generate_actions, _intent_shortcut,
    _cached_daily_brief, _set_daily_brief_cache,
)
from .assistant_modules.chat_actions import (
    ExecuteIn,
    _exec_add_reminder, _exec_update_chief_complaint, _exec_mark_mentality,
    _brief_has_content, _user_asked_about_brief, _generate_generic_reply,
)
from .assistant_modules.chat_prompt import build_system_prompt
from .assistant_modules.chat_compress import (
    _compress_old_messages,
    CHAT_HISTORY_MAX_BYTES, CHAT_HISTORY_BATCH_PAIRS, CHAT_HISTORY_KEEP_RECENT,
    EPISODIC_TTL_DAYS, PERMANENT_PER_USER_LIMIT,
)
from .assistant_modules.reasoning import (
    _forward_reasoning, _simple_fallback, _fallback_lifestyle, _inject_user_context,
    DiagnoseIn, LifestyleIn, TreatmentIn, AnchorExplainIn,
)
from .assistant_modules.bazi import (
    BaziIn, _local_bazi_fallback, _compute_one_bazi_variant, _DEFAULT_V_INNATE,
)
