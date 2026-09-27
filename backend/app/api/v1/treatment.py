"""treatment - 调理方案版本链"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import User, Case, TreatmentPlan
from ..deps import get_current_user

router = APIRouter()


@router.get("/versions")
def list_versions(db: Session = Depends(get_db),
                  current: User = Depends(get_current_user)):
    """获取用户的所有方案版本（按日期降序）"""
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if not case:
        return []

    plans = db.query(TreatmentPlan).filter(
        TreatmentPlan.case_id == case.id
    ).order_by(TreatmentPlan.created_at.desc()).all()

    return [
        {
            "id": p.id,
            "version": p.version,
            "plan_type": p.plan_type,
            "strategy": p.strategy,
            "prescription": p.prescription,
            "herbs": p.herbs,
            "life_advice": p.life_advice,
            "avoidances": p.avoidances,
            "reasoning": p.reasoning,
            "doctor_signed": p.doctor_signed,
            "user_confirmed": p.user_confirmed,
            "effectiveness": p.effectiveness,
            "created_at": p.created_at.isoformat(),
            "is_current": case.current_plan_id == p.id,
        }
        for p in plans
    ]


@router.get("/current")
def current_version(db: Session = Depends(get_db),
                    current: User = Depends(get_current_user)):
    """获取当前生效的方案（current_plan_id 指向不存在的 plan 时，选最新版本兜底）"""
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if not case:
        return None

    p = None
    if case.current_plan_id:
        p = db.query(TreatmentPlan).filter(TreatmentPlan.id == case.current_plan_id).first()
    # current_plan_id 指向脏数据 → 选最新版本
    if not p:
        p = db.query(TreatmentPlan).filter(
            TreatmentPlan.case_id == case.id
        ).order_by(TreatmentPlan.created_at.desc()).first()
    if not p:
        return None

    return {
        "id": p.id,
        "version": p.version,
        "strategy": p.strategy,
        "prescription": p.prescription,
        "herbs": p.herbs,
        "life_advice": p.life_advice,
        "avoidances": p.avoidances,
        "reasoning": p.reasoning,
    }


@router.post("/confirm/{plan_id}")
def confirm_plan(plan_id: int, db: Session = Depends(get_db),
                 current: User = Depends(get_current_user)):
    """用户确认采纳某方案"""
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="未初始化建档")

    p = db.query(TreatmentPlan).filter(TreatmentPlan.id == plan_id,
                                       TreatmentPlan.case_id == case.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="方案不存在")

    p.user_confirmed = True
    case.current_plan_id = p.id
    db.commit()

    return {"ok": True, "current_plan_id": p.id, "version": p.version}
