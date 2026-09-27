"""doctor - 医生端专属 API（B 端）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import User, Case, Observation, TreatmentPlan, Friend, DoctorProfile
from ..deps import get_current_doctor

router = APIRouter()


@router.get("/my-patients")
def my_patients(db: Session = Depends(get_db), doctor: User = Depends(get_current_doctor)):
    """医生绑定的所有患者"""
    rels = db.query(Friend).filter(
        Friend.is_doctor_bind == True,
        ((Friend.user_id == doctor.id) | (Friend.friend_id == doctor.id)),
        Friend.status == "accepted"
    ).all()

    patients = []
    for f in rels:
        other_id = f.friend_id if f.user_id == doctor.id else f.user_id
        pu = db.query(User).filter(User.id == other_id).first()
        if not pu: continue
        case = db.query(Case).filter(Case.user_id == pu.id).first()
        latest_obs = db.query(Observation).filter(
            Observation.case_id == case.id).order_by(
            Observation.observed_at.desc()).first() if case else None
        latest_plan = db.query(TreatmentPlan).filter(
            TreatmentPlan.case_id == case.id).order_by(
            TreatmentPlan.created_at.desc()).first() if case else None
        patients.append({
            "user_id": pu.id, "name": pu.nickname, "qingnang_id": pu.qingnang_id,
            "syndrome": case.syndrome if case else None,
            "v_current": case.v_current if case else None,
            "latest_obs_sqi": latest_obs.sqi if latest_obs else None,
            "latest_obs_hint": latest_obs.syndrome_hint if latest_obs else None,
            "latest_plan": latest_plan.version if latest_plan else None,
            "latest_plan_pushed": latest_plan.pushed_at.isoformat() if latest_plan and latest_plan.pushed_at else None,
        })

    return patients


@router.get("/patients/{user_id}")
def patient_detail(user_id: int, db: Session = Depends(get_db),
                   doctor: User = Depends(get_current_doctor)):
    """查看某个患者的完整临床视图"""
    # 确认绑定关系
    bind = db.query(Friend).filter(
        Friend.is_doctor_bind == True,
        ((Friend.user_id == doctor.id) & (Friend.friend_id == user_id)) |
        ((Friend.user_id == user_id) & (Friend.friend_id == doctor.id)),
        Friend.status == "accepted"
    ).first()
    if not bind: raise HTTPException(403, "未绑定该患者")

    u = db.query(User).filter(User.id == user_id).first()
    case = db.query(Case).filter(Case.user_id == user_id).first()
    if not u or not case: raise HTTPException(404, "患者不存在")

    obs_list = db.query(Observation).filter(Observation.case_id == case.id).order_by(
        Observation.observed_at.desc()).all()
    plans = db.query(TreatmentPlan).filter(TreatmentPlan.case_id == case.id).order_by(
        TreatmentPlan.created_at.desc()).all()

    return {
        "patient": {
            "name": u.nickname, "qingnang_id": u.qingnang_id,
            "gender": u.gender, "birth": u.birth_date + " " + (u.birth_hour or ""),
            "height": u.height, "weight": u.weight,
        },
        "case": {
            "bazi": case.bazi, "syndrome": case.syndrome,
            "v_innate": case.v_innate, "v_baseline": case.v_baseline,
            "v_current": case.v_current,
        },
        "observations": [
            {"sqi": o.sqi, "delta_f": o.delta_f, "v_obs": o.v_obs,
             "hint": o.syndrome_hint, "at": o.observed_at.isoformat()}
            for o in obs_list
        ],
        "plans": [
            {"version": p.version, "strategy": p.strategy, "prescription": p.prescription,
             "signed": p.doctor_signed, "pushed": p.pushed_at.isoformat() if p.pushed_at else None,
             "effectiveness": p.effectiveness,
             "created_at": p.created_at.isoformat()}
            for p in plans
        ],
    }


@router.post("/plans/draft")
def create_plan_draft(body: dict, db: Session = Depends(get_db),
                      doctor: User = Depends(get_current_doctor)):
    """医生创建新方案草稿"""
    user_id = body.get("user_id")
    case = db.query(Case).filter(Case.user_id == user_id).first()
    if not case: raise HTTPException(404, "患者不存在")

    # 计算下一版本号
    latest = db.query(TreatmentPlan).filter(TreatmentPlan.case_id == case.id).order_by(
        TreatmentPlan.created_at.desc()).first()
    next_ver = _next_version(latest.version if latest else "v0.0")

    p = TreatmentPlan(
        case_id=case.id, doctor_id=doctor.id,
        version=next_ver, plan_type="iteration",
        strategy=body.get("strategy", ""),
        prescription=body.get("prescription", ""),
        herbs=body.get("herbs", []),
        life_advice=body.get("life_advice", []),
        avoidances=body.get("avoidances", []),
        reasoning=body.get("reasoning", ""),
        doctor_signed=False,  # 先不签字
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"plan_id": p.id, "version": next_ver}


@router.post("/plans/{plan_id}/sign")
def sign_plan(plan_id: int, db: Session = Depends(get_db),
              doctor: User = Depends(get_current_doctor)):
    """医生签字 - 方案才可推送给患者"""
    from datetime import datetime
    p = db.query(TreatmentPlan).filter(TreatmentPlan.id == plan_id).first()
    if not p: raise HTTPException(404, "方案不存在")
    p.doctor_signed = True
    p.pushed_at = datetime.utcnow()

    # 自动设为当前方案
    case = db.query(Case).filter(Case.id == p.case_id).first()
    if case: case.current_plan_id = p.id

    db.commit()
    return {"ok": True, "version": p.version, "pushed_at": p.pushed_at.isoformat()}


def _next_version(v: str) -> str:
    """v7.0 → v7.1, v7.9 → v8.0, v6.0.1 → v6.0.2"""
    try:
        parts = v.lstrip("v").split(".")
        if len(parts) == 2:
            major, minor = int(parts[0]), int(parts[1])
            return f"v{major}.{minor + 1}" if minor < 9 else f"v{major + 1}.0"
        elif len(parts) == 3:
            return f"v{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"
    except ValueError:
        pass
    return v + ".1"
