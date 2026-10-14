"""ReductionState — 归约算法库活状态持久化"""
from sqlalchemy import Column, Integer, Float, JSON, DateTime, Text
from sqlalchemy.sql import func
from ..database import Base


class ReductionStateDB(Base):
    """
    归约算法库的活算子状态（全局唯一，一行记录）

    这些权重可被 L4 回填修正（compare_outcome → apply_correction → 写回此表），
    下次归约自动生效。这就是"活"算子——不是静态查表，是能被持续修正的算子。
    """
    __tablename__ = "reduction_states"

    id = Column(Integer, primary_key=True)
    label = Column(Text, default="default")  # 预留：未来可能支持多套状态

    # R3 增益中庸：断链点增益系数（默认 1.0）
    broken_node_gain = Column(Float, default=1.0)
    # R3 尖峰压制系数（默认 0.3）
    peak_suppress = Column(Float, default=0.3)
    # R3 KE 冲突升级系数（默认 1.5）
    ke_conflict_mult = Column(Float, default=1.5)

    # L0 乘数表覆盖（可被观测数据修正）
    season_corrections = Column(JSON, default=dict)  # {"立春": {"wood": 1.05}, ...}
    hour_corrections = Column(JSON, default=dict)    # {"子": {"water": 1.1}, ...}

    # 元信息
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
