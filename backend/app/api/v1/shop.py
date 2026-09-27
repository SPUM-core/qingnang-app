"""shop - 商城商品 / 评价 / 分销"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from ...database import get_db
from ...models import User, ShopItem, ShopReview
from ..deps import get_current_user
from ...utils import WUXING_NAMES

router = APIRouter()


@router.get("/items")
def list_items(category: str | None = None, keyword: str | None = None,
               limit: int = 50, db: Session = Depends(get_db)):
    """商品列表 - 可按分类/关键词筛选"""
    q = db.query(ShopItem).filter(ShopItem.active == True)
    if category:
        q = q.filter(ShopItem.category == category)
    if keyword:
        q = q.filter(or_(ShopItem.title.ilike(f"%{keyword}%"),
                         ShopItem.description.ilike(f"%{keyword}%")))
    items = q.order_by(ShopItem.review_count.desc()).limit(limit).all()
    return [_item_serialize(i) for i in items]


@router.get("/items/{sku}")
def item_detail(sku: str, db: Session = Depends(get_db)):
    """商品详情 + 所有评价"""
    item = db.query(ShopItem).filter(ShopItem.sku == sku, ShopItem.active == True).first()
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在")

    reviews = db.query(ShopReview).filter(ShopReview.item_id == item.id).order_by(
        ShopReview.created_at.desc()).all()

    return {
        "item": _item_serialize(item),
        "reviews": [{
            "rating": r.rating,
            "tags": r.tags,
            "wuxing_feel": r.wuxing_feel,
            "text": r.text,
            "ai_annotated": r.ai_annotated,
            "ai_tags": r.ai_tags,
            "created_at": r.created_at.isoformat(),
        } for r in reviews],
        "ai_summary": _build_ai_summary(item.id, db),
    }


def _item_serialize(i: ShopItem) -> dict:
    return {
        "sku": i.sku, "title": i.title, "category": i.category,
        "price": i.price, "provider_url": i.provider_url,
        "spum_tags": i.spum_tags, "description": i.description,
        "review_count": i.review_count, "avg_rating": i.avg_rating,
    }


def _build_ai_summary(item_id: int, db: Session) -> str | None:
    """AI 综合体验摘要 - 基于真实用户评价聚合（不编造）"""
    reviews = db.query(ShopReview).filter(ShopReview.item_id == item_id).all()
    if len(reviews) == 0:
        return None
    # 简化版：抽取高频 tag
    from collections import Counter
    all_tags = []
    for r in reviews:
        if r.tags: all_tags.extend(r.tags)
        if r.ai_tags: all_tags.extend(r.ai_tags)
    common = Counter(all_tags).most_common(5)
    positives = [t for t, c in common if c >= 2]
    if positives:
        return f"多位用户反馈：{'、'.join(positives)}。共 {len(reviews)} 条评价。"
    return f"共 {len(reviews)} 条真实用户评价，暂无显著共性。"


@router.post("/reviews")
def submit_review(body: dict, db: Session = Depends(get_db),
                  current: User = Depends(get_current_user)):
    """提交评价 - 必须有关联分销订单（准入校验简化）"""
    # 简化：此处只要求提供 order_id，真实实现需查 ShopOrder 验证
    if not body.get("order_id"):
        raise HTTPException(status_code=400, detail="需要关联分销订单号")

    item = db.query(ShopItem).filter(ShopItem.sku == body.get("sku")).first()
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在")

    review = ShopReview(
        item_id=item.id,
        user_id=current.id,
        order_id=body["order_id"],
        rating=body.get("rating", 3),
        tags=body.get("tags", []),
        wuxing_feel=body.get("wuxing_feel"),
        text=body.get("text", ""),
        flagged=_check_risk(body.get("text", "")),
    )
    db.add(review)

    # 更新商品统计
    item.review_count += 1
    avg = db.query(func.avg(ShopReview.rating)).filter(ShopReview.item_id == item.id).scalar()
    item.avg_rating = round(avg, 1) if avg else item.avg_rating

    db.commit()
    db.refresh(review)

    return {"ok": True, "review_id": review.id, "flagged": review.flagged}


def _check_risk(text: str) -> bool:
    """风险词检测 - 拦截功效类表述"""
    RISK_WORDS = ["治愈", "治好", "根治", "药到病除", "根治", "降", "特效"]
    return any(w in text for w in RISK_WORDS)


@router.get("/recommend")
def recommend_for_me(db: Session = Depends(get_db),
                     current: User = Depends(get_current_user)):
    """为当前用户推荐商品 - 基于 v_base 的 SPUM 适配标签匹配"""
    v = current.v_base or {}
    # 找出用户弱项（<50）
    weak = [w for w, val in v.items() if val and val < 50]
    items = db.query(ShopItem).filter(ShopItem.active == True).all()

    scored = []
    for it in items:
        tags = it.spum_tags or {}
        suit = tags.get("suitable", [])
        avoid = tags.get("avoid", [])
        score = sum(2 for w in suit if w in weak)  # 弱项匹配加分
        score -= sum(1 for w in avoid if w in weak)  # 相忌扣分
        scored.append((score, it))

    scored.sort(key=lambda x: -x[0])
    return [{
        "sku": i.sku, "title": i.title, "price": i.price,
        "spum_tags": i.spum_tags, "recommend_score": s,
    } for s, i in scored if s > 0][:10]
