"""Feedback - 体感反馈（用户执行调理方案后的真实感受）"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, ForeignKey, Boolean
from sqlalchemy.sql import func
from ..database import Base

class Feedback(Base):
    __tablename__ = "feedbacks"

    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"), index=True)
    plan_id       = Column(Integer, ForeignKey("treatment_plans.id"), index=True)

    # 反馈类型
    fb_type       = Column(String(30))        # plan_effect / ppg_feel / shop_item / challenge

    # 结构化字段
    rating        = Column(Integer)            # 1-5
    tags          = Column(JSON)               # ["温润", "上火", "肠胃适应"]
    wuxing_effect = Column(JSON)               # {"wood": "疏解", "fire": "略旺"}

    # 开放文本
    text          = Column(Text)

    # SPUM 后端自动标注（反馈语义解析）
    ai_annotated  = Column(Boolean, default=False)
    ai_tags       = Column(JSON)               # SPUM 引擎自动抽取的标签

    # 风险检测
    flagged       = Column(Boolean, default=False)   # 含"治愈/治好"等功效词
    flagged_reason = Column(String(200))

    created_at    = Column(DateTime, server_default=func.now())
