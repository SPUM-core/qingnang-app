"""Observation - PPG 脉诊观测记录"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, ForeignKey
from sqlalchemy.sql import func
from ..database import Base

class Observation(Base):
    __tablename__ = "observations"

    id            = Column(Integer, primary_key=True)
    case_id       = Column(Integer, ForeignKey("cases.id"), index=True)

    source        = Column(String(20))       # cheezPPG / manual / upload
    sqi           = Column(Float)             # 信号质量指数 0-100

    # PPG 原始波形（简化存采样点 - 实际可存文件路径）
    ppg_wave      = Column(JSON)              # [点1, 点2, ...] 或文件路径

    # SPUM 五形观测 ΔF
    delta_f       = Column(JSON)              # {"wood": -0.06, "fire": -0.41, ...}
    v_obs         = Column(JSON)              # {"wood": 47.6, "fire": 33.6, ...} 分量

    # 定性诊断（从 SPUM 引擎输出）
    syndrome_hint = Column(String(200))       # 气结状态 74% 特征匹配

    observed_at   = Column(DateTime, server_default=func.now())
