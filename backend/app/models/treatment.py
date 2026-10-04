"""TreatmentPlan - 调理方案版本链"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, ForeignKey, Boolean
from sqlalchemy.sql import func
from ..database import Base

class TreatmentPlan(Base):
    __tablename__ = "treatment_plans"

    id            = Column(Integer, primary_key=True)
    case_id       = Column(Integer, ForeignKey("cases.id"), index=True)
    doctor_id     = Column(Integer, ForeignKey("users.id"))   # 医生（可为空=用户端 AI 草稿）

    version       = Column(String(20))        # v7.0, v6.0.1
    plan_type     = Column(String(20))        # initial / iteration / validation

    # 方案核心
    strategy      = Column(Text)              # 策略：温土疏木、化气利水
    prescription  = Column(Text)              # 处方：苓桂术甘汤 + 白芍 10g
    herbs         = Column(JSON)              # ["茯苓 15g", "桂枝 10g", ...]
    life_advice   = Column(JSON)              # [{"time": "戌时", "action": "泡脚15min"}]
    avoidances    = Column(JSON)              # ["苦寒直折", "安眠药"]

    # SPUM 推导上下文
    from_obs_id   = Column(Integer)           # 基于哪次观测
    reasoning     = Column(Text)              # 推导原理（可存 AI 输出）

    # 2026-10-02 新增：T3 撤方回弹验证所需的 ΔS 向量
    expected_delta_S = Column(JSON)           # 干预前 SPUM 预期位移 {"wood": +5, "fire": -3, ...}
    outcome_delta_S  = Column(JSON)           # 停药后实际观测位移（护栏四：区分根因vs压制）

    # 审核 / 推送状态
    doctor_signed = Column(Boolean, default=False)   # 医生已签字
    pushed_at     = Column(DateTime)                 # 推送到用户时间
    user_confirmed = Column(Boolean, default=False)  # 用户确认采纳

    # 效果追踪
    effectiveness = Column(JSON)              # {"v_delta": {"earth": "+30%"}, "feedback_count": 12}

    created_at    = Column(DateTime, server_default=func.now())
    next_review   = Column(DateTime)
