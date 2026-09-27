"""Challenge + Checkin - 挑战打卡"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.sql import func
from ..database import Base

class Challenge(Base):
    __tablename__ = "challenges"

    id            = Column(Integer, primary_key=True)
    creator_id    = Column(Integer, ForeignKey("users.id"), index=True)

    title         = Column(String(100))        # 早睡 30 天
    description   = Column(String(500))
    rule          = Column(JSON)               # {"type": "daily_before", "target": "22:30"}
    category      = Column(String(30))         # sleep / diet / exercise / herb

    start_date    = Column(DateTime)
    end_date      = Column(DateTime)

    participants  = Column(JSON)               # [{user_id, streak, joined_at}]
    status        = Column(String(20))        # active / finished

    created_at    = Column(DateTime, server_default=func.now())

class Checkin(Base):
    __tablename__ = "checkins"

    id            = Column(Integer, primary_key=True)
    challenge_id  = Column(Integer, ForeignKey("challenges.id"), index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), index=True)

    done          = Column(Boolean, default=True)
    note          = Column(String(500))

    checkin_date  = Column(DateTime, server_default=func.now())
