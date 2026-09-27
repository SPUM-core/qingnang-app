"""challenges - 挑战打卡"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import User, Challenge, Checkin
from ..deps import get_current_user

router = APIRouter()


class CreateChallengeIn(BaseModel):
    title: str
    description: str = ""
    rule: dict  # {"type": "daily_before", "target": "22:30"}
    category: str = "sleep"
    days: int = 30


@router.post("/")
def create(body: CreateChallengeIn, db: Session = Depends(get_db),
           current: User = Depends(get_current_user)):
    from datetime import datetime, timedelta
    ch = Challenge(
        creator_id=current.id, title=body.title, description=body.description,
        rule=body.rule, category=body.category,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=body.days),
        participants=[{"user_id": current.id, "streak": 0, "joined_at": datetime.utcnow().isoformat()}],
        status="active",
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return {"challenge_id": ch.id}


@router.get("/mine")
def my_challenges(db: Session = Depends(get_db),
                  current: User = Depends(get_current_user)):
    """我创建的 + 我参与的"""
    all_ch = db.query(Challenge).all()
    mine = []
    for ch in all_ch:
        pids = [p["user_id"] for p in (ch.participants or [])]
        if ch.creator_id == current.id or current.id in pids:
            mine.append({
                "id": ch.id, "title": ch.title, "rule": ch.rule,
                "category": ch.category, "status": ch.status,
                "participants_count": len(ch.participants or []),
                "start_date": ch.start_date.isoformat() if ch.start_date else None,
                "end_date": ch.end_date.isoformat() if ch.end_date else None,
            })
    return mine


@router.post("/join/{challenge_id}")
def join(challenge_id: int, db: Session = Depends(get_db),
         current: User = Depends(get_current_user)):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch: raise HTTPException(404, "挑战不存在")

    parts = ch.participants or []
    if current.id in [p["user_id"] for p in parts]:
        return {"ok": True, "already": True}

    from datetime import datetime
    parts.append({"user_id": current.id, "streak": 0,
                  "joined_at": datetime.utcnow().isoformat()})
    ch.participants = parts
    db.commit()
    return {"ok": True}


@router.post("/checkin/{challenge_id}")
def checkin(challenge_id: int, note: str = "", db: Session = Depends(get_db),
            current: User = Depends(get_current_user)):
    ch = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not ch: raise HTTPException(404, "挑战不存在")

    ci = Checkin(challenge_id=ch.id, user_id=current.id, note=note)
    db.add(ci)

    # 更新 streak
    parts = ch.participants or []
    for p in parts:
        if p["user_id"] == current.id:
            p["streak"] = p.get("streak", 0) + 1
    ch.participants = parts
    db.commit()
    return {"ok": True, "streak": next((p.get("streak", 0)
                                         for p in ch.participants
                                         if p["user_id"] == current.id), 0)}
