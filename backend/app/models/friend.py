"""Friend - 好友关系 + 医生绑定 + 家庭代际"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.sql import func
from ..database import Base

KINSHIP_TYPES = [
    None,           # 非家人
    "spouse",       # 夫妻
    "parent",       # 父/母
    "child",        # 子/女
    "sibling",      # 兄/弟/姐/妹
    "grandparent",  # 祖父/祖母/外祖父/外祖母
    "grandchild",   # 孙/外孙
    "other",        # 其他亲属
]

class Friend(Base):
    __tablename__ = "friends"

    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"), index=True)
    friend_id     = Column(Integer, ForeignKey("users.id"), index=True)

    relation      = Column(String(20))        # family / friend / doctor / other

    # ⭐ 家人代际字段 —— 家庭合并数据推算 / 代际遗传分析的前提
    kinship_type  = Column(String(20))        # spouse / parent / child / sibling / grandparent / grandchild / other
    generation_level = Column(Integer)        # 0=同代(夫妻/兄弟) / 1=上一代(父母) / -1=下一代(子女) / 2=祖辈 / -2=孙辈

    # 医生绑定专属
    is_doctor_bind = Column(Boolean, default=False)
    invite_code    = Column(String(32))        # 医生邀请码

    # 数据共享权限（默认值在应用层定义）
    permissions   = Column(JSON)               # {"ppg": true, "feedback": false, "family": false}

    # 状态
    status        = Column(String(20))        # pending / accepted / blocked
    bind_date     = Column(DateTime)

    created_at    = Column(DateTime, server_default=func.now())
