"""Case - 一个用户一个案例"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, ForeignKey
from sqlalchemy.sql import func
from ..database import Base

class Case(Base):
    __tablename__ = "cases"

    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"), unique=True, index=True)

    # 八字（初始化建档时自动推导）
    bazi          = Column(String(30))       # 丁卯 己酉 甲子 丙寅
    ganzhi_year   = Column(String(10))       # 丙午
    ganzhi_month  = Column(String(10))       # 丁酉
    ganzhi_day    = Column(String(10))       # 癸酉

    # 先天基底 + 调理前观测基线
    v_innate      = Column(JSON)             # S_0^0 出生基底
    v_baseline    = Column(JSON)             # V_base 调理前第一次观测

    # 当前最新观测（每次 PPG 更新）
    v_current     = Column(JSON)             # V_obs 最新

    # 中医诊断（定性）
    syndrome      = Column(String(100))      # 湿遏·气结74%
    chief_complaint = Column(Text)           # 主诉

    # 关联：当前主方案版本
    current_plan_id = Column(Integer)

    created_at    = Column(DateTime, server_default=func.now())
    updated_at    = Column(DateTime, server_default=func.now(), onupdate=func.now())
