"""cases - 案例 CRUD + 初始化建档"""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...database import get_db
from ...models import User, Case, Observation, TreatmentPlan
from ..deps import get_current_user
from ...config import settings
from ...utils import WUXING_LIST

router = APIRouter()


@router.get("/reports")
def get_reports(db: Session = Depends(get_db),
                current: User = Depends(get_current_user)):
    """历次推演报告 — 从 PPG 观测 + 方案版本自动聚合"""
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if not case:
        return {"reports": [], "message": "未初始化建档"}

    reports = []

    # 1. 每次 PPG 观测 → 一条报告
    obs_list = db.query(Observation).filter(
        Observation.case_id == case.id
    ).order_by(Observation.observed_at.desc()).all()

    for i, ob in enumerate(obs_list):
        v = ob.v_obs or {}
        # 算主要偏移
        weak = [k for k, val in v.items() if isinstance(val, (int, float)) and val < 45]
        strong = [k for k, val in v.items() if isinstance(val, (int, float)) and val > 65]
        label = {"wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"}
        weak_s = "、".join(label.get(w, w) for w in weak[:3])
        strong_s = "、".join(label.get(s, s) for s in strong[:3])

        notice = ob.syndrome_hint or ""
        if not notice:
            parts = []
            if weak_s: parts.append(f"{weak_s}形偏弱")
            if strong_s: parts.append(f"{strong_s}形偏旺")
            notice = " · ".join(parts) if parts else "五形基本调和"

        reports.append({
            "id": f"obs-{ob.id}",
            "title": f"脉诊观测 #{len(obs_list)-i}",
            "scope": "PPG · CheezPPG",
            "notice": notice,
            "sqi": ob.sqi,
            "v_obs": v,
            "created_at": ob.observed_at.isoformat() if ob.observed_at else None,
        })

    # 2. 每个方案版本 → 一条报告
    plan_list = db.query(TreatmentPlan).filter(
        TreatmentPlan.case_id == case.id
    ).order_by(TreatmentPlan.created_at.desc()).all()

    for i, p in enumerate(plan_list):
        reports.append({
            "id": f"plan-{p.id}",
            "title": f"调理方案 {p.version}",
            "scope": f"医生: {p.plan_type or '青囊'}{' · 用户已确认' if p.user_confirmed else ''}",
            "notice": p.strategy or "",
            "prescription": p.prescription,
            "herbs": p.herbs,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    # 3. 初始建档报告
    reports.append({
        "id": "onboarding",
        "title": "初始建档",
        "scope": f"八字: {case.bazi}",
        "notice": case.syndrome or f"先天基底已建立（{case.engine_type if hasattr(case, 'engine_type') else ''}）",
        "v_innate": case.v_innate,
        "engine": getattr(case, 'engine_type', None),
        "created_at": case.created_at.isoformat() if case.created_at else None,
    })

    # 按时间倒序
    reports.sort(key=lambda r: r.get("created_at") or "", reverse=True)

    return {
        "reports": reports,
        "total": len(reports),
        "observation_count": len(obs_list),
        "plan_count": len(plan_list),
    }


@router.get("/mine")
def get_my_case(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    """获取当前用户的完整案例（含向量、最近观测、当前方案）"""
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if not case:
        return {"onboarded": False, "message": "未初始化建档"}

    # 最新观测
    latest_obs = db.query(Observation).filter(
        Observation.case_id == case.id
    ).order_by(Observation.observed_at.desc()).first()

    # 当前方案
    current_plan = None
    if case.current_plan_id:
        current_plan = db.query(TreatmentPlan).filter(TreatmentPlan.id == case.current_plan_id).first()

    return {
        "onboarded": True,
        "case": {
            "id": case.id,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "bazi": case.bazi,
            "ganzhi_year": case.ganzhi_year,
            "ganzhi_month": case.ganzhi_month,
            "ganzhi_day": case.ganzhi_day,
            "v_innate": case.v_innate,
            "v_baseline": case.v_baseline,
            "v_current": case.v_current,
            "syndrome": case.syndrome,
            "chief_complaint": case.chief_complaint,
            "observation_count": db.query(Observation).filter(Observation.case_id == case.id).count(),
            "plan_count": db.query(TreatmentPlan).filter(TreatmentPlan.case_id == case.id).count(),
            # 观测简要 (SettingsView / 导出数据用)
            "observations": [
                {
                    "sqi": o.sqi,
                    "delta_f": o.delta_f,
                    "v_obs": o.v_obs,
                    "syndrome_hint": o.syndrome_hint,
                    "observed_at": o.observed_at.isoformat() if o.observed_at else None,
                }
                for o in db.query(Observation).filter(
                    Observation.case_id == case.id
                ).order_by(Observation.observed_at.desc()).limit(20).all()
            ],
        },
        "latest_observation": {
            "sqi": latest_obs.sqi,
            "delta_f": latest_obs.delta_f,
            "v_obs": latest_obs.v_obs,
            "syndrome_hint": latest_obs.syndrome_hint,
            "observed_at": latest_obs.observed_at.isoformat(),
        } if latest_obs else None,
        "current_plan": {
            "id": current_plan.id,
            "version": current_plan.version,
            "strategy": current_plan.strategy,
            "prescription": current_plan.prescription,
            "herbs": current_plan.herbs,
            "life_advice": current_plan.life_advice,
            "avoidances": current_plan.avoidances,
        } if current_plan else None,
    }


@router.post("/onboarding")
async def do_onboarding(body: dict, db: Session = Depends(get_db),
                        current: User = Depends(get_current_user)):
    """初始化建档 - 前端 QuestionnaireView 提交后调用
    body 包含: nickname, gender, birth_date, birth_hour, birthplace, height, weight, chief_complaint
    SPUM 后端: 调用 qingmeng-engine /v1/reasoning/bazi → 真实八字推演 → 先天基底 S_0^0
    """
    birth_date = body.get("birth_date", "1986-08-02")
    birth_hour = body.get("birth_hour")
    birthplace = body.get("birthplace")

    # ── 八字推演：前端如已带 v_innate（+ engine=spum_bazi），跳过重算 ──
    provided_v_innate = body.get("v_innate") if body.get("engine", "").startswith("spum_bazi") else None

    if provided_v_innate:
        # 复用前端已算好的结果
        v_innate = provided_v_innate
        bazi_result = body.get("bazi_result") or {}
        bazi = bazi_result.get("bazi", "未知")
        pillars = bazi_result.get("pillars") or bazi.split("/") or ["?", "?", "?", "?"]
        true_solar_time = bazi_result.get("true_solar_time", "")
        engine = "spum_bazi_provided"
    else:
        # 调 qingmeng-engine 真实八字推演
        bazi_result = await _forward_bazi(birth_date, birth_hour, birthplace)
        bazi = bazi_result.get("bazi", "未知")
        pillars = bazi_result.get("pillars", ["?", "?", "?", "?"])
        v_innate = bazi_result.get("v_innate")
        if not v_innate:
            raise HTTPException(status_code=502, detail="八字推演返回无五形向量")
        true_solar_time = bazi_result.get("true_solar_time", "")
        engine = bazi_result.get("engine", "unknown")

    # 解析四柱 → 年/月/日干支
    ganzhi_year = pillars[0] if len(pillars) >= 1 else ""
    ganzhi_month = pillars[1] if len(pillars) >= 2 else ""
    ganzhi_day = pillars[2] if len(pillars) >= 3 else ""

    # 更新用户基本资料
    if body.get("nickname"): current.nickname = body["nickname"]
    if body.get("gender"): current.gender = body["gender"]
    if body.get("birth_date"): current.birth_date = body["birth_date"]
    if body.get("birth_hour"): current.birth_hour = body["birth_hour"]
    if body.get("height"): current.height = body["height"]
    if body.get("weight"): current.weight = body["weight"]
    current.v_base = v_innate
    current.is_onboarded = True

    # 创建 Case（如已存在则更新，避免重复调用报错）
    existing_case = db.query(Case).filter(Case.user_id == current.id).first()
    if existing_case:
        existing_case.bazi = bazi
        existing_case.ganzhi_year = ganzhi_year or "占位"
        existing_case.ganzhi_month = ganzhi_month or "占位"
        existing_case.ganzhi_day = ganzhi_day or "占位"
        existing_case.v_innate = v_innate
        existing_case.v_baseline = v_innate
        existing_case.v_current = v_innate
        existing_case.syndrome = "初始化建档完成，请采集第一次 PPG 观测以建立基线"
        existing_case.chief_complaint = body.get("chief_complaint", existing_case.chief_complaint)
        case = existing_case
    else:
        case = Case(
            user_id=current.id,
            bazi=bazi,
            ganzhi_year=ganzhi_year or "占位",
            ganzhi_month=ganzhi_month or "占位",
            ganzhi_day=ganzhi_day or "占位",
            v_innate=v_innate,
            v_baseline=v_innate,
            v_current=v_innate,
            syndrome="初始化建档完成，请采集第一次 PPG 观测以建立基线",
            chief_complaint=body.get("chief_complaint", ""),
        )
        db.add(case)
    db.commit()
    db.refresh(case)

    return {
        "onboarded": True,
        "case_id": case.id,
        "bazi": bazi,
        "pillars": pillars,
        "lunar": bazi_result.get("lunar", ""),
        "true_solar_time": true_solar_time,
        "longitude": bazi_result.get("longitude"),
        "engine": engine,
        "v_innate": v_innate,
        "message": "初始化建档完成，请采集第一次 PPG 观测",
    }


async def _forward_bazi(birth_date: str, birth_hour: str | None, birthplace: str | None) -> dict:
    """调用 qingmeng-engine /v1/reasoning/bazi。失败时抛 502。"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{settings.QINGMENG_URL}/v1/reasoning/bazi",
                json={
                    "birth_date": birth_date,
                    "birth_hour": birth_hour,
                    "birthplace": birthplace,
                },
            )
            if r.status_code == 200:
                return r.json()
            raise HTTPException(status_code=502,
                detail=f"八字推演服务返回 HTTP {r.status_code}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502,
            detail=f"青檬引擎不可达: {exc}")
