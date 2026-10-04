"""inquiry - 多阶段问诊会话

模型设计：一个表搞定 v1，context_json 存全量问答历史 + LLM 上下文。
不拆 5 张子表——结构在 JSON 里，需要时再规范化。
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Enum
from sqlalchemy.sql import func
import enum
from ..database import Base


class InquiryStatus(str, enum.Enum):
    ACTIVE = "active"         # 进行中
    COMPLETED = "completed"   # 完成（LLM 判 is_final=true）
    ABANDONED = "abandoned"   # 用户放弃/超时


class InquiryStage(str, enum.Enum):
    INITIAL = "initial"       # 第一阶段：主诉 + 核心症状
    DEEPEN = "deepen"         # 第二阶段：深化——症状细节 + 诱发因素
    EXPAND = "expand"         # 第三阶段：扩展——饮食/睡眠/二便/体质倾向
    FINALIZE = "finalize"     # 第四阶段：收束——总结 + 关键判别点
    DONE = "done"             # 全部完成


class InquirySession(Base):
    __tablename__ = "inquiry_sessions"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, nullable=False, index=True)
    case_id     = Column(Integer, index=True)   # 关联的数字模型（onboarding 前可空）

    stage       = Column(String(20), default=InquiryStage.INITIAL.value)
    status      = Column(String(20), default=InquiryStatus.ACTIVE.value)

    # ══ 全量上下文 ══
    # LLM prompt 输入（v_innate + v_baseline + 用户画像）
    user_context = Column(JSON)

    # 分阶段问答历史：[{"stage": "initial", "questions": [...], "answers": {...}}, ...]
    history     = Column(JSON, default=list)

    # 累计答案（扁平 key→value，跨阶段累积）
    answer_bank = Column(JSON, default=dict)

    # 最终 LLM 输出的状态摘要（完成时写）
    summary     = Column(JSON)

    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime)
