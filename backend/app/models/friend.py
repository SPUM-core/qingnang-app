"""Friend - 好友关系 + 医生绑定"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.sql import func
from ..database import Base

class Friend(Base):
    __tablename__ = "friends"

    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"), index=True)
    friend_id     = Column(Integer, ForeignKey("users.id"), index=True)

    relation      = Column(String(20))        # family / friend / doctor / other

    # 医生绑定专属
    is_doctor_bind = Column(Boolean, default=False)
    invite_code    = Column(String(32))        # 医生邀请码

    # 数据共享权限（默认值在应用层定义）
    permissions   = Column(JSON)               # {"ppg": true, "feedback": false, "family": false}

    # 状态
    status        = Column(String(20))        # pending / accepted / blocked
    bind_date     = Column(DateTime)

    created_at    = Column(DateTime, server_default=func.now())
