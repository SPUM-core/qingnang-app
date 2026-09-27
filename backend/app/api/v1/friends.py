"""friends - 好友 CRUD + 医生绑定 + 体质匹配"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid

from ...database import get_db
from ...models import User, Friend
from ...utils import vector_similarity, vector_intersection, vector_complement, WUXING_NAMES
from ..deps import get_current_user

router = APIRouter()


class AddFriendIn(BaseModel):
    friend_qingnang_id: str
    relation: str = "friend"  # family / friend / doctor


@router.get("/list")
def list_friends(db: Session = Depends(get_db),
                 current: User = Depends(get_current_user)):
    """获取我的好友列表"""
    # 双向关系（user_id 或 friend_id 是当前用户）
    fwd = db.query(Friend).filter(Friend.user_id == current.id,
                                  Friend.status == "accepted").all()
    rev = db.query(Friend).filter(Friend.friend_id == current.id,
                                  Friend.status == "accepted").all()

    friends = []
    for f in fwd:
        fu = db.query(User).filter(User.id == f.friend_id).first()
        if fu:
            friends.append(_serialize(f, fu, is_reverse=False))
    for f in rev:
        fu = db.query(User).filter(User.id == f.user_id).first()
        if fu:
            friends.append(_serialize(f, fu, is_reverse=True))

    return friends


def _serialize(rel: Friend, other: User, is_reverse: bool) -> dict:
    from ...models import DoctorProfile
    doctor_info = None
    if other.is_doctor:
        dp = None  # 医生资质详情，仅在绑定关系里可见
        if not is_reverse:
            dp = db_query_doctor(other.id)
        doctor_info = dp
    return {
        "friend_id": rel.id,
        "qingnang_id": other.qingnang_id,
        "name": other.nickname,
        "relation": rel.relation,
        "is_doctor": other.is_doctor,
        "is_doctor_bind": rel.is_doctor_bind,
        "bind_date": rel.bind_date.isoformat() if rel.bind_date else None,
        "permissions": rel.permissions or {"ppg": True, "feedback": False, "family": False},
        "v_base_summary": _summarize(other.v_base),
        "doctor_info": doctor_info,
    }


def db_query_doctor(user_id: int):
    from ...database import SessionLocal
    from ...models import DoctorProfile
    dbs = SessionLocal()
    try:
        dp = dbs.query(DoctorProfile).filter(DoctorProfile.user_id == user_id).first()
        if dp:
            return {"hospital": dp.hospital, "title": dp.title, "verified": dp.verified}
        return None
    finally:
        dbs.close()


def _summarize(v: dict | None) -> str:
    if not v: return ""
    directions = []
    for k, name in WUXING_NAMES.items():
        val = v.get(k, 50)
        if val >= 70: directions.append(f"{name}↑")
        elif val >= 60: directions.append(f"{name}↔")
        elif val <= 40: directions.append(f"{name}↓")
    return " ".join(directions)


@router.post("/add")
def add_friend(body: AddFriendIn, db: Session = Depends(get_db),
               current: User = Depends(get_current_user)):
    """发送好友请求"""
    target = db.query(User).filter(User.qingnang_id == body.friend_qingnang_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="未找到该青囊用户")
    if target.id == current.id:
        raise HTTPException(status_code=400, detail="不能添加自己为好友")

    # 已存在？
    exist = db.query(Friend).filter(
        ((Friend.user_id == current.id) & (Friend.friend_id == target.id)) |
        ((Friend.user_id == target.id) & (Friend.friend_id == current.id))
    ).first()
    if exist:
        if exist.status == "accepted":
            raise HTTPException(status_code=400, detail="已是好友")
        return {"ok": True, "status": exist.status, "message": "请求已存在"}

    rel = Friend(
        user_id=current.id, friend_id=target.id,
        relation=body.relation, status="pending",
        permissions={"ppg": False, "feedback": False, "family": False},
    )
    db.add(rel)
    db.commit()

    return {"ok": True, "message": f"已向 {target.nickname} 发送好友请求"}


@router.post("/bind-doctor/{friend_id}")
def bind_doctor(friend_id: int, db: Session = Depends(get_db),
                current: User = Depends(get_current_user)):
    """绑定医生好友 - 生成邀请码"""
    f = db.query(Friend).filter(Friend.id == friend_id).first()
    if not f or f.status != "accepted":
        raise HTTPException(status_code=404, detail="好友关系不存在")

    other_id = f.friend_id if f.user_id == current.id else f.user_id
    other = db.query(User).filter(User.id == other_id).first()
    if not other or not other.is_doctor:
        raise HTTPException(status_code=400, detail="对方不是医生")

    import datetime
    f.is_doctor_bind = True
    f.relation = "doctor"
    f.invite_code = f"QN-DR-{uuid.uuid4().hex[:8].upper()}"
    f.bind_date = datetime.datetime.utcnow()
    # 医生绑定默认全量共享
    f.permissions = {"ppg": True, "feedback": True, "family": True}
    db.commit()

    return {"ok": True, "invite_code": f.invite_code, "friend_name": other.nickname}


@router.get("/match/{friend_id}")
def match_report(friend_id: int, db: Session = Depends(get_db),
                 current: User = Depends(get_current_user)):
    """体质匹配度报告（两个好友之间）"""
    f = db.query(Friend).filter(Friend.id == friend_id).first()
    if not f or f.status != "accepted":
        raise HTTPException(status_code=404, detail="好友关系不存在")

    other_id = f.friend_id if f.user_id == current.id else f.user_id
    other = db.query(User).filter(User.id == other_id).first()
    if not other:
        raise HTTPException(status_code=404, detail="用户不存在")

    a = current.v_base or {}
    b = other.v_base or {}

    similarity = round(vector_similarity(a, b), 3)
    intersection = vector_intersection(a, b)
    complement = vector_complement(a, b)

    return {
        "me": {"name": current.nickname, "v_base": a},
        "friend": {"name": other.nickname, "v_base": b},
        "similarity": similarity,
        "intersection": [WUXING_NAMES.get(w, w) for w in intersection],
        "complement": [WUXING_NAMES.get(w, w) for w in complement],
        "conclusion": _match_conclusion(current.nickname, other.nickname, intersection, complement, similarity),
    }


def _match_conclusion(me, friend, intersection, complement, sim):
    parts = []
    if intersection:
        names = [WUXING_NAMES.get(w, w) for w in intersection]
        parts.append(f"你们的{'、'.join(names)}形都偏弱，这是共同短板，一起调理效果会加倍")
    if complement:
        names = [WUXING_NAMES.get(w, w) for w in complement]
        parts.append(f"{'、'.join(names)}形互补，你的高值能帮到ta的低值")
    if sim > 0.7:
        parts.append("总体相似度很高，适合互相参考调理经验")
    elif sim < 0.4:
        parts.append("你们体质差异较大，建议各自独立调理")
    return "。".join(parts) + "。"
