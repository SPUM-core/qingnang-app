"""friends - 好友关系网完整 API

  基础 CRUD    : list / add / accept / reject / pending-requests / delete
  权限分级     : update-permissions
  医生绑定     : bind-doctor
  体质匹配     : match
  关系网核心   : family-aggregate  (家人合并向量推算)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid, datetime

from ...database import get_db
from ...models import User, Friend
from ...utils import vector_similarity, vector_intersection, vector_complement, WUXING_NAMES
from ..deps import get_current_user

router = APIRouter()


# ═══════════════════════════════════════════════════════════
# Pydantic schemas
# ═══════════════════════════════════════════════════════════
class AddFriendIn(BaseModel):
    friend_qingnang_id: str
    relation: str = "friend"       # family / friend / doctor / other
    kinship_type: str | None = None  # 仅 family: spouse / parent / child / sibling / grandparent / grandchild
    generation_level: int | None = None


class PermissionsIn(BaseModel):
    permissions: dict


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════
def _me_or_other(f: Friend, me_id: int):
    """返回 (other_user_id, is_reverse) —— 判断哪一边是当前用户"""
    if f.user_id == me_id:
        return f.friend_id, False
    return f.user_id, True


def _serialize(rel: Friend, other: User, is_reverse: bool, db: Session) -> dict:
    doctor_info = None
    if other.is_doctor and rel.is_doctor_bind:
        dp = db.query(User).filter(User.id == other.id).first()  # lazy DoctorProfile 可以从 User 取
        if dp:
            doctor_info = {
                "hospital": getattr(dp, "hospital", None),
                "title": getattr(dp, "title", None),
                "verified": getattr(dp, "doctor_verified", dp.is_doctor),
            }
    return {
        "friend_id": rel.id,
        "qingnang_id": other.qingnang_id,
        "nickname": other.nickname,
        "relation": rel.relation,
        "kinship_type": rel.kinship_type,
        "generation_level": rel.generation_level,
        "is_doctor": other.is_doctor,
        "is_doctor_bind": rel.is_doctor_bind,
        "bind_date": rel.bind_date.isoformat() if rel.bind_date else None,
        "permissions": rel.permissions or {"ppg": False, "feedback": False, "family": False},
        "v_base": other.v_base or {},
        "v_base_summary": _summarize(other.v_base),
        "doctor_info": doctor_info,
        "is_reverse": is_reverse,  # 当前用户是 friend_id（被动方）
    }


def _summarize(v: dict | None) -> str:
    if not v: return ""
    parts = []
    for k, name in WUXING_NAMES.items():
        val = v.get(k, 50)
        if val >= 70: parts.append(f"{name}↑↑")
        elif val >= 60: parts.append(f"{name}↑")
        elif val <= 40: parts.append(f"{name}↓")
        elif val <= 50: parts.append(f"{name}↓↓")
        else: parts.append(f"{name}↔")
    return " ".join(parts)


KINSHIP_LABEL = {
    "spouse": "夫妻", "parent": "父/母", "child": "子/女",
    "sibling": "兄/弟/姐/妹", "grandparent": "祖辈", "grandchild": "孙辈",
    "other": "其他亲属", None: "",
}


# ═══════════════════════════════════════════════════════════
# 1. 好友列表
# ═══════════════════════════════════════════════════════════
@router.get("/list")
def list_friends(db: Session = Depends(get_db),
                 current: User = Depends(get_current_user)):
    """返回我所有已接受的好友（双向合并）"""
    fwd = db.query(Friend).filter(Friend.user_id == current.id, Friend.status == "accepted").all()
    rev = db.query(Friend).filter(Friend.friend_id == current.id, Friend.status == "accepted").all()

    friends = []
    for f in fwd:
        fu = db.query(User).filter(User.id == f.friend_id).first()
        if fu: friends.append(_serialize(f, fu, is_reverse=False, db=db))
    for f in rev:
        fu = db.query(User).filter(User.id == f.user_id).first()
        if fu: friends.append(_serialize(f, fu, is_reverse=True, db=db))
    return friends


# ═══════════════════════════════════════════════════════════
# 2. 请求流：发送 / 接受 / 拒绝 / 待处理
# ═══════════════════════════════════════════════════════════
@router.post("/add")
def add_friend(body: AddFriendIn, db: Session = Depends(get_db),
               current: User = Depends(get_current_user)):
    """发送好友请求"""
    target = db.query(User).filter(User.qingnang_id == body.friend_qingnang_id).first()
    if not target:
        raise HTTPException(404, "未找到该青囊用户")
    if target.id == current.id:
        raise HTTPException(400, "不能添加自己为好友")

    exist = db.query(Friend).filter(
        ((Friend.user_id == current.id) & (Friend.friend_id == target.id)) |
        ((Friend.user_id == target.id) & (Friend.friend_id == current.id))
    ).first()
    if exist:
        if exist.status == "accepted":
            raise HTTPException(400, "已是好友")
        return {"ok": True, "status": exist.status, "message": "请求已存在"}

    rel = Friend(
        user_id=current.id, friend_id=target.id,
        relation=body.relation,
        kinship_type=body.kinship_type if body.relation == "family" else None,
        generation_level=body.generation_level if body.relation == "family" else None,
        status="pending",
        permissions={"ppg": False, "feedback": False, "family": False},
    )
    db.add(rel)
    db.commit()
    return {"ok": True, "message": f"已向 {target.nickname} 发送好友请求", "pending_id": rel.id}


@router.get("/pending-requests")
def pending_requests(db: Session = Depends(get_db),
                     current: User = Depends(get_current_user)):
    """别人发给我的 pending 请求列表"""
    reqs = db.query(Friend).filter(
        Friend.friend_id == current.id, Friend.status == "pending"
    ).all()
    out = []
    for r in reqs:
        su = db.query(User).filter(User.id == r.user_id).first()
        if su:
            out.append({
                "friend_id": r.id,
                "from_qingnang_id": su.qingnang_id,
                "from_nickname": su.nickname,
                "relation": r.relation,
                "kinship_type": r.kinship_type,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
    return out


@router.post("/{friend_id}/accept")
def accept_friend(friend_id: int, db: Session = Depends(get_db),
                  current: User = Depends(get_current_user)):
    """接受别人发来的好友请求"""
    f = db.query(Friend).filter(Friend.id == friend_id).first()
    if not f: raise HTTPException(404, "好友关系不存在")
    if f.friend_id != current.id: raise HTTPException(403, "这不是发给你的请求")
    if f.status != "pending": raise HTTPException(400, "该请求已处理")

    f.status = "accepted"
    f.bind_date = datetime.datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/{friend_id}/reject")
def reject_friend(friend_id: int, db: Session = Depends(get_db),
                  current: User = Depends(get_current_user)):
    """拒绝好友请求"""
    f = db.query(Friend).filter(Friend.id == friend_id).first()
    if not f: raise HTTPException(404, "好友关系不存在")
    if f.friend_id != current.id and f.user_id != current.id:
        raise HTTPException(403, "无权操作")

    db.delete(f)
    db.commit()
    return {"ok": True}


@router.delete("/{friend_id}")
def remove_friend(friend_id: int, db: Session = Depends(get_db),
                  current: User = Depends(get_current_user)):
    """解除好友关系"""
    f = db.query(Friend).filter(Friend.id == friend_id).first()
    if not f: raise HTTPException(404, "好友关系不存在")
    if f.user_id != current.id and f.friend_id != current.id:
        raise HTTPException(403, "无权操作")
    db.delete(f)
    db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# 3. 权限管理
# ═══════════════════════════════════════════════════════════
@router.put("/{friend_id}/permissions")
def update_permissions(friend_id: int, body: PermissionsIn,
                       db: Session = Depends(get_db),
                       current: User = Depends(get_current_user)):
    """更新我给这位好友开放的数据共享权限"""
    f = db.query(Friend).filter(Friend.id == friend_id).first()
    if not f: raise HTTPException(404, "好友关系不存在")
    if f.user_id != current.id and f.friend_id != current.id:
        raise HTTPException(403, "无权操作")
    if f.is_doctor_bind:
        raise HTTPException(400, "医生绑定关系使用独立权限")

    f.permissions = {
        "ppg": bool(body.permissions.get("ppg", f.permissions.get("ppg", False))),
        "feedback": bool(body.permissions.get("feedback", f.permissions.get("feedback", False))),
        "family": bool(body.permissions.get("family", f.permissions.get("family", False))),
    }
    db.commit()
    return {"ok": True, "permissions": f.permissions}


# ═══════════════════════════════════════════════════════════
# 4. 医生绑定
# ═══════════════════════════════════════════════════════════
@router.post("/bind-doctor/{friend_id}")
def bind_doctor(friend_id: int, db: Session = Depends(get_db),
                current: User = Depends(get_current_user)):
    """绑定医生好友 —— 自动全量共享 + 生成邀请码"""
    f = db.query(Friend).filter(Friend.id == friend_id).first()
    if not f or f.status != "accepted": raise HTTPException(404, "好友关系不存在")

    other_id, _ = _me_or_other(f, current.id)
    other = db.query(User).filter(User.id == other_id).first()
    if not other or not other.is_doctor: raise HTTPException(400, "对方不是医生")

    f.is_doctor_bind = True
    f.relation = "doctor"
    f.invite_code = f"QN-DR-{uuid.uuid4().hex[:8].upper()}"
    f.bind_date = datetime.datetime.utcnow()
    f.permissions = {"ppg": True, "feedback": True, "family": True}
    db.commit()

    return {"ok": True, "invite_code": f.invite_code, "friend_name": other.nickname}


# ═══════════════════════════════════════════════════════════
# 5. 体质匹配度报告
# ═══════════════════════════════════════════════════════════
@router.get("/match/{friend_id}")
def match_report(friend_id: int, db: Session = Depends(get_db),
                 current: User = Depends(get_current_user)):
    f = db.query(Friend).filter(Friend.id == friend_id).first()
    if not f or f.status != "accepted": raise HTTPException(404, "好友关系不存在")

    other_id, _ = _me_or_other(f, current.id)
    other = db.query(User).filter(User.id == other_id).first()
    if not other: raise HTTPException(404, "用户不存在")

    a = current.v_base or {}
    b = other.v_base or {}
    similarity = round(vector_similarity(a, b), 3)
    intersection = vector_intersection(a, b)
    complement = vector_complement(a, b)

    wuxing_detail = []
    for k, name in WUXING_NAMES.items():
        wuxing_detail.append({
            "k": k, "label": name,
            "me": a.get(k, 50),
            "friend": b.get(k, 50),
            "intersection": k in intersection,
            "complement": k in complement,
        })

    return {
        "me": {"name": current.nickname, "v_base": a},
        "friend": {
            "name": other.nickname,
            "v_base": b,
            "relation": f.relation,
            "kinship_label": KINSHIP_LABEL.get(f.kinship_type, ""),
        },
        "similarity": similarity,
        "wuxing": wuxing_detail,
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


# ═══════════════════════════════════════════════════════════
# 6. ⭐ 家庭数据合并推算（family-aggregate）
#
# 输入：relation=family 的所有已接受好友
# 输出：
#   members     — 家庭成员（含自己） + 各自 kinship / generation
#   union       — 全家向量并集（每形 max）
#   intersection — 全家向量交集弱项（每形 min < 45）
#   tensions    — 相克检测（长辈木极旺 × 晚辈土枯竭 = 木克土）
#   guidance    — 联合调理建议
# ═══════════════════════════════════════════════════════════
@router.get("/family-aggregate")
def family_aggregate(db: Session = Depends(get_db),
                     current: User = Depends(get_current_user)):
    """全家体质合并推算 —— 家人关系网的核心后端"""

    # 1. 收集家人（双向）
    fam_fwd = db.query(Friend).filter(
        Friend.user_id == current.id, Friend.status == "accepted", Friend.relation == "family"
    ).all()
    fam_rev = db.query(Friend).filter(
        Friend.friend_id == current.id, Friend.status == "accepted", Friend.relation == "family"
    ).all()

    members = []
    # 先加自己
    members.append({
        "qingnang_id": current.qingnang_id,
        "nickname": current.nickname or "我",
        "is_me": True,
        "kinship_type": "self",
        "generation_level": 0,
        "v_base": current.v_base or {},
    })
    generation_min = 0
    generation_max = 0

    for f in fam_fwd:
        other = db.query(User).filter(User.id == f.friend_id).first()
        if other:
            gl = f.generation_level if f.generation_level is not None else 0
            generation_min = min(generation_min, gl)
            generation_max = max(generation_max, gl)
            members.append({
                "friend_id": f.id,
                "qingnang_id": other.qingnang_id,
                "nickname": other.nickname,
                "is_me": False,
                "kinship_type": f.kinship_type,
                "kinship_label": KINSHIP_LABEL.get(f.kinship_type, "家人"),
                "generation_level": gl,
                "v_base": other.v_base or {},
            })

    for f in fam_rev:
        other = db.query(User).filter(User.id == f.user_id).first()
        if other:
            gl = -(f.generation_level) if f.generation_level is not None else 0  # 反向取反
            generation_min = min(generation_min, gl)
            generation_max = max(generation_max, gl)
            members.append({
                "friend_id": f.id,
                "qingnang_id": other.qingnang_id,
                "nickname": other.nickname,
                "is_me": False,
                "kinship_type": f.kinship_type,
                "kinship_label": KINSHIP_LABEL.get(f.kinship_type, "家人"),
                "generation_level": gl,
                "v_base": other.v_base or {},
            })

    if len(members) < 2:
        return {"members": members, "note": "至少添加 1 位家人才能生成家庭看板"}

    # 2. 全家向量并集 / 交集弱项
    import math
    keys = list(WUXING_NAMES.keys())
    union = {}
    intersection_weak = {}
    for k in keys:
        vals = [m["v_base"].get(k, 50) for m in members]
        union[k] = round(max(vals), 1)
        # 交集弱项：全家最小 < 45 → 这形是全家共同短板
        if min(vals) < 45:
            intersection_weak[k] = round(min(vals), 1)

    # 3. 相克检测 —— 木克土 / 土克水 / 水克火 / 火克金 / 金克木
    ke_map = [("wood","earth","木克土"),("earth","water","土克水"),
              ("water","fire","水克火"),("fire","metal","火克金"),("metal","wood","金克木")]
    tensions = []
    for a, b, label in ke_map:
        high_a = [m for m in members if m["v_base"].get(a, 50) >= 70]
        low_b  = [m for m in members if m["v_base"].get(b, 50) <= 40]
        if high_a and low_b:
            tensions.append({
                "label": label,
                "attacker": [(m["nickname"], m["v_base"].get(a,0)) for m in high_a],
                "victim":   [(m["nickname"], m["v_base"].get(b,0)) for m in low_b],
            })

    # 4. 联合调理建议
    guidance = []
    weak_labels = [WUXING_NAMES.get(k, k) for k in intersection_weak]
    if weak_labels:
        guidance.append({"cat": "family", "text": f"全家共同短板：{'、'.join(weak_labels)}形 — 饮食上统一健脾方案效果加倍"})
    if tensions:
        for t in tensions[:2]:
            guidance.append({"cat": "tension", "text": f"{t['label']} — 建议 {'、'.join([x[0] for x in t['attacker']])} 避免 {'、'.join([x[0] for x in t['victim']])} 同时在场时起冲突，可各自选时辰调理"})
    guidance.append({"cat": "lifestyle", "text": f"建议全家约定统一入睡时间 22:30 — 早睡比单独做更能形成集体节律"})

    return {
        "members": members,
        "union": union,
        "intersection_weak": {WUXING_NAMES.get(k, k): v for k, v in intersection_weak.items()},
        "tensions": tensions,
        "guidance": guidance,
        "generation_span": [generation_min, generation_max],
    }
