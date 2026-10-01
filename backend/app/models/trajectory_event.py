"""trajectory_events — 事件持久化表（docs/08 L420-435）

生命周期事件：手术/药物/窗口期/转大运/外力/间断/波动
前端事件编辑器写入，后端 trajectories 端点读取叠加到 SPUM 三曲线。
"""
from sqlalchemy import Column, Integer, String, JSON, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from ..database import Base


class TrajectoryEvent(Base):
    __tablename__ = "trajectory_events"

    id           = Column(Integer, primary_key=True)
    case_id      = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), index=True)

    age          = Column(Integer, nullable=False)          # 事件发生年龄（年视图用）
    day          = Column(Integer)                          # 事件发生天（月视图用，可选）
    event_type   = Column(String(16), nullable=False)       # '手术'|'药物'|'窗口期'|'转大运'|'外力'|'间断'|'波动'
    label        = Column(Text)
    direction    = Column(String(8))                        # '发散'|'收敛'|'注意'
    damage       = Column(JSON)                             # {"fire": 12, "metal": 10} 伤害量(正数)
    boost        = Column(JSON)                             # {"fire": 6} 增益量(正数)
    duration_days = Column(Integer, default=540)            # 冲击持续时间
    source       = Column(String(16), default='manual')      # 'manual'|'auto_infer'|'preset_clinical'

    created_at   = Column(DateTime, server_default=func.now())
    updated_at   = Column(DateTime, server_default=func.now(), onupdate=func.now())
