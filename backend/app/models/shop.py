"""ShopItem / ShopReview / ShopOrder"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Text, ForeignKey, Boolean
from sqlalchemy.sql import func
from ..database import Base

class ShopItem(Base):
    __tablename__ = "shop_items"

    id            = Column(Integer, primary_key=True)
    sku           = Column(String(32), unique=True, index=True)   # shop-001
    title         = Column(String(200))
    category      = Column(String(50))         # herb / clothing / home / daily
    price         = Column(Float)
    cover_url     = Column(String(500))
    provider_url  = Column(String(500))        # 供货商/分销跳转链接

    # SPUM 体质适配标签（青囊自建）
    spum_tags     = Column(JSON)               # {"suitable": ["wood", "earth"], "avoid": ["fire"], "wuxing_elem": "earth"}
    description   = Column(Text)

    review_count  = Column(Integer, default=0)
    avg_rating    = Column(Float, default=0)

    active        = Column(Boolean, default=True)
    created_at    = Column(DateTime, server_default=func.now())

class ShopReview(Base):
    __tablename__ = "shop_reviews"

    id            = Column(Integer, primary_key=True)
    item_id       = Column(Integer, ForeignKey("shop_items.id"), index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), index=True)

    order_id      = Column(String(64))          # 关联分销订单（准入校验）
    rating        = Column(Integer)              # 1-5
    tags          = Column(JSON)                 # 普通电商标签 + SPUM 体感标签
    wuxing_feel   = Column(JSON)                 # {"earth": "温润", "fire": "不上火"}
    text          = Column(Text)

    # AI 自动聚合标注
    ai_annotated  = Column(Boolean, default=False)
    ai_tags       = Column(JSON)

    flagged       = Column(Boolean, default=False)
    flagged_reason = Column(String(200))

    created_at    = Column(DateTime, server_default=func.now())

class ShopOrder(Base):
    """分销订单回传（第三方供货商 → 青囊）"""
    __tablename__ = "shop_orders"

    id            = Column(Integer, primary_key=True)
    external_id   = Column(String(64), unique=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), index=True)
    item_id       = Column(Integer, ForeignKey("shop_items.id"))

    provider      = Column(String(50))          # 淘宝联盟 / 京东联盟 / 微店
    amount        = Column(Float)
    commission    = Column(Float)

    status        = Column(String(20))        # paid / shipped / completed / refunded
    completed_at  = Column(DateTime)

    created_at    = Column(DateTime, server_default=func.now())
