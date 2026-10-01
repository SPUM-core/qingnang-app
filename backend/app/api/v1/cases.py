"""cases - 案例 CRUD + 初始化建档"""
import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...database import get_db
from ...models import User, Case, Observation, TreatmentPlan, TrajectoryEvent
from ..deps import get_current_user
from ...config import settings
from ...utils import WUXING_LIST
from ...utils.trajectory_algorithm import (
    compute_health_bounds, compute_health_bounds_v2,
    compute_yx, build_year_view, build_year_view_v2, norm,
)
from ...utils.lunar_helper import compute_dayun

router = APIRouter()
logger = logging.getLogger("qingnang.cases")


# ═══════════════════════════════════════════════════════
# 青檬引擎拓扑管线桥接 — 非阻塞异步注入
# ═══════════════════════════════════════════════════════

async def _async_seed_qingmeng_topology(qingnang_id: str,
                                        v_innate: dict,
                                        bazi: str = "") -> None:
    """onboarding 后异步把 v_innate 种子注入青檬引擎 per-user 拓扑。

    失败静默记录，不影响主请求响应。
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                f"{settings.QINGMENG_URL}/v1/reasoning/ppg",
                json={
                    "user_id": qingnang_id,
                    "v_innate": v_innate,
                    "v_obs": v_innate,  # onboarding 尚无真实 PPG，先用 v_innate 占坑
                    "sqi": 0.0,  # 种子注入标记，低 SQI 让注入幅度小
                },
            )
    except Exception as exc:
        logger.info(f"[qingmeng-bridge] onboarding 种子注入跳过: {exc}")


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


# ═══════════════════════════════════════════════════════
# v0.2 三曲线轨迹端点 — 体质调理曲线核心数据源
# ═══════════════════════════════════════════════════════

import math
from datetime import datetime, timedelta

def _health_score (v: dict) -> float:
    """综合健康得分：0-100，越高越收敛到健康多面体 H (50,50,50,50,50)"""
    dims = ['wood', 'fire', 'earth', 'metal', 'water']
    total_sq = 0.0
    for k in dims:
        val = v.get(k, 50)
        if val is None or not isinstance(val, (int, float)):
            val = 50
        total_sq += (val - 50) ** 2
    return round((100 - math.sqrt(total_sq / 5)) * 10, 1)

def _target_curve (start_score: float, target_score: float, n_points: int) -> list:
    """指数收敛目标曲线：从 start → target，缓 S 曲线"""
    if n_points <= 1:
        return [round(target_score * 10) / 10] * max(1, n_points)
    result = []
    tau = n_points / 2.5  # 收敛速度
    for i in range(n_points):
        progress = 1 - math.exp(-i / tau)
        score = start_score + (target_score - start_score) * progress
        result.append(round(score * 10) / 10)
    return result


@router.get("/trajectories")
def get_trajectories(db: Session = Depends(get_db),
                     current: User = Depends(get_current_user)):
    """返回三曲线数据：target（目标收敛）+ actual（真实观测）+ events（事件标注）
    
    数据流：observations.v_obs → health_score → 时间序列
    target = 初始观测 health_score 按指数收敛到 72（健康区带中心）
    events = 自动推断（暂时返回空数组，后续接入事件录入）
    """
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if not case:
        return {
            "algorithm": "spum_computeHealthBounds_v1",
            "target": [], "actual": [], "actual_elements": [], "events": [],
            "driftData": [], "yinTop": [], "yangBot": [],
            "diseaseModes": [], "elArr": [],
            "message": "未初始化建档",
        }

    # 按时间升序取所有观测
    obs_list = db.query(Observation).filter(
        Observation.case_id == case.id,
        Observation.status == "analyzed"
    ).order_by(Observation.observed_at.asc()).all()

    # 如果 analyzed 太少，降级取所有观测
    if len(obs_list) < 2:
        obs_list = db.query(Observation).filter(
            Observation.case_id == case.id,
        ).order_by(Observation.observed_at.asc()).all()

    if len(obs_list) == 0:
        # 无观测，返回空 SPUM 字段
        return {
            "algorithm": "spum_computeHealthBounds_v1",
            "target": [], "actual": [], "actual_elements": [], "events": [],
            "driftData": [], "yinTop": [], "yangBot": [],
            "diseaseModes": [], "elArr": [],
            "v_innate": case.v_innate, "v_baseline": case.v_baseline,
        }

    # 计算每个观测点的健康得分
    dims = ['wood', 'fire', 'earth', 'metal', 'water']
    actual_points = []
    actual_scores = []
    actual_elements = []  # per-element 分量时间序列
    for i, ob in enumerate(obs_list):
        v = ob.v_obs or {}
        hs = _health_score(v)
        t = ob.observed_at
        if t:
            t_str = t.strftime('%m-%d')
        else:
            t_str = f'Day{i+1}'
        actual_points.append({
            'day': i + 1,
            't': t_str,
            'score': hs,
            'observed_at': t.isoformat() if t else None,
            'v_obs': v,
            'syndrome_hint': ob.syndrome_hint,
        })
        actual_scores.append(hs)
        # per-element — 带 paradoxFlags 和 syndromeHint
        paradox_flags = []
        try:
            bl = case.v_baseline or {}
            if v.get('earth', 50) >= 70 and bl.get('earth', 50) <= 40:
                paradox_flags.append('earth_false_fullness')
            if v.get('fire', 50) >= 70:
                paradox_flags.append('fire_empty_float')
        except Exception:
            pass
        hhmm_str = t.strftime('%H:%M') if t else None
        actual_elements.append({
            'day': i + 1,
            't': t_str,
            'hhmm': hhmm_str,
            **{k: (v.get(k) or 50) for k in dims},
            'syndromeHint': ob.syndrome_hint or '',
            'paradoxFlags': paradox_flags,
        })

    # 目标收敛曲线：从第一个观测得分 → 72（健康区带中心）
    start_score = actual_scores[0]
    target_scores = _target_curve(start_score, 72.0, len(actual_scores))
    target_points = [{'day': i + 1, 't': p['t'], 'score': target_scores[i]}
                     for i, p in enumerate(actual_points)]

    # 事件自动推断（后续可替换为 events 表）
    events = []
    # 规则 1：观测间隔 > 72h → 标注"数据间断"
    for i in range(1, len(obs_list)):
        prev_t = obs_list[i - 1].observed_at
        curr_t = obs_list[i].observed_at
        if prev_t and curr_t:
            gap_days = (curr_t - prev_t).total_seconds() / 86400
            if gap_days > 3:
                events.append({
                    'day': i + 1,
                    'type': '间断',
                    'label': f'数据间断 {gap_days:.0f} 天',
                    'direction': '—',
                })

    # 规则 2：相邻观测健康得分突变 > 6 → 标注"体质波动"
    for i in range(1, len(actual_scores)):
        delta = actual_scores[i] - actual_scores[i - 1]
        if abs(delta) > 6:
            direction = '发散' if delta < 0 else '收敛'
            hint = obs_list[i].syndrome_hint or ''
            label = f'{direction} Δ{abs(delta):.0f}'
            if hint:
                # 截取 hint 前 15 字
                clean = hint[:15].replace('—', '·').strip()
                label = f'{clean}'
            events.append({
                'day': i + 1,
                'type': '波动',
                'label': label,
                'direction': direction,
                'scoreDelta': round(delta, 1),
            })

    # ═══ 预设关键临床事件（基于病历 syndrome_hint 匹配）═══
    PRESET_EVENTS = [
        {'contains': '假性充盈', 'type': '悖论态', 'label': 'PPG土+0.60=假性充盈≠真旺',
         'direction': '注意', 'isParadox': True},
        {'contains': '湿热化火', 'type': '干预', 'label': 'v5.5方：薏苡仁+竹茹清湿热',
         'direction': '收敛', 'scoreDelta': 3.5},
        {'contains': '气滞血瘀', 'type': '排病', 'label': '湿泻+阳虚寒象暴露',
         'direction': '短期发散', 'isSideEffect': True},
        {'contains': '趋于正常', 'type': '干预', 'label': 'v5.7最小试探方·桂枝汤透火郁',
         'direction': '收敛', 'scoreDelta': 8.2},
        {'contains': '正常脉象', 'type': '收敛', 'label': '服方on·五形回归正常',
         'direction': '收敛'},
        {'contains': '停药off', 'type': '偏离', 'label': '停药on-off验证复发·肝郁87%',
         'direction': '发散', 'scoreDelta': -6.3},
        {'contains': '气阴两虚', 'type': '偏离', 'label': '爬山耗气·气阴两虚',
         'direction': '发散', 'isSideEffect': True},
        {'contains': '湿遏', 'type': '排病', 'label': '湿遏·火衰-0.41·重建v7.0苓桂术甘',
         'direction': '短期发散', 'isSideEffect': True},
    ]
    for ev_def in PRESET_EVENTS:
        for i, ob in enumerate(obs_list):
            hint = (ob.syndrome_hint or '')
            if ev_def['contains'] in hint:
                day = i + 1
                exists = any(e.get('day') == day and e.get('type') == ev_def['type'] for e in events)
                if not exists:
                    events.append({
                        'day': day,
                        'type': ev_def['type'],
                        'label': ev_def['label'],
                        'direction': ev_def['direction'],
                        'scoreDelta': ev_def.get('scoreDelta', 0),
                        'isParadox': ev_def.get('isParadox', False),
                        'isSideEffect': ev_def.get('isSideEffect', False),
                    })

    # ═══════════════════════════════════════════════════════
    # 叠加 trajectory_events 表（前端编辑器写入的持久化事件）
    # manual 事件优先级最高：覆盖同 type+day 的内存推断事件
    # ═══════════════════════════════════════════════════════
    try:
        db_events = db.query(TrajectoryEvent).filter(
            TrajectoryEvent.case_id == case.id
        ).all()
        for te in db_events:
            # day = age * 365（月视图兼容）
            ev_day = te.day or (te.age * 365)
            ev = {
                'day': ev_day,
                'type': te.event_type,
                'label': te.label or '',
                'direction': te.direction or '—',
                'source': te.source or 'manual',
            }
            if te.damage:
                ev['isMedical'] = True
                ev['impact'] = te.damage
            # 去重：manual 覆盖同 day+type 的内存事件
            events = [e for e in events
                      if not (e.get('day') == ev_day and e.get('type') == te.event_type
                              and ev.get('source') == 'manual')]
            events.append(ev)
    except Exception:
        # trajectory_events 表可能不存在（alembic 未跑），静默跳过
        pass

    events.sort(key=lambda e: (e['day'], e['type']))

    # ═══════════════════════════════════════════════════════
    # SPUM 三曲线计算 — v1 + v2 并行（向后兼容 + 新功能）
    # v1: compute_health_bounds (Y/X → EMA → 金属弹性)
    # v2: compute_health_bounds_v2 (S向量 + σ场 + 帧动力学 + dv/dt约束)
    # ═══════════════════════════════════════════════════════
    innate_ref = case.v_innate or {k: 50 for k in dims}
    spum_bounds_v1 = compute_health_bounds(actual_elements, innate_ref)
    spum_bounds_v2 = compute_health_bounds_v2(actual_elements, innate_ref, events)

    return {
        'algorithm': 'spum_computeHealthBounds_v2',
        'algorithm_v1_fallback': 'spum_computeHealthBounds_v1',
        'theory_source': 'SPUM2611 + 青囊中医总纲',
        'topological_constant_12': 12,
        'target': target_points,
        'actual': actual_points,
        'actual_elements': actual_elements,
        'events': events,
        'v_innate': case.v_innate,
        'v_baseline': case.v_baseline,
        'v_current': case.v_current,
        'innate_elements': case.v_innate or {k: 50 for k in dims},
        'observation_count': len(obs_list),
        'health_zone': {'min': 40, 'max': 60, 'label': '健康区带 H'},
        'computed_at': datetime.now().isoformat(),
        # ── SPUM v1 兼容字段（三曲线 + 金属弹性）──
        'elems': actual_elements,
        'driftData': spum_bounds_v1['driftData'],
        'yinTop': spum_bounds_v1['yinTop'],
        'yangBot': spum_bounds_v1['yangBot'],
        'diseaseModes': spum_bounds_v2['diseaseModes'],  # v2 联合判定更精确
        'elArr': spum_bounds_v1['elArr'],
        # 动态健康区间（基于 SPUM 边界的 ±10%）
        'spum_healthy_zone': {
            'min': round(min(spum_bounds_v1['yangBot']) * 1.1, 1) if spum_bounds_v1['yangBot'] else -10,
            'max': round(max(spum_bounds_v1['yinTop']) * 1.1, 1) if spum_bounds_v1['yinTop'] else +10,
            'label': 'SPUM 动态健康区间',
        },
        # ── SPUM v2 新增字段 ──
        'sigma_trend': spum_bounds_v2['sigma_trend'],
        'polytope_statuses': spum_bounds_v2['polytope_statuses'],
        'violation_depths': spum_bounds_v2['violation_depths'],
        'frame_residues': spum_bounds_v2['frame_residues'],
        'health_score': spum_bounds_v2['health_score'],
        'S_vectors': spum_bounds_v2['S_vectors'],
    }


# ═══════════════════════════════════════════════════════
# 🆕 trajectories/year-view — 纯八字推演年视图（L3 终身预测基础）
# 数据源: User.birth_date/hour/gender → lunar_python 排大运
#       Case.v_innate + trajectory_events 表事件
# ═══════════════════════════════════════════════════════

@router.get("/trajectories/year-view")
def get_year_view(db: Session = Depends(get_db), current: User = Depends(get_current_user),
                 start_year: int = 1957, end_age: int = 81):
    """终身推演年视图 — 用 v_innate + 大运 + 事件构建每年 SPUM 三曲线

    Query params:
      start_year: 起始年份（默认 1957 曾银鸾/1986 胡运涛可推断）
      end_age:    推演到几岁（默认 81）
    """
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if not case:
        return {"message": "未初始化建档"}

    innate = case.v_innate or {k: 50 for k in dims}

    # ── 大运排盘（lunar_python，失败返回空 dayun 不 crash）──
    dayun = compute_dayun(
        birth_date=current.birth_date or '1990-01-01',
        birth_hour=current.birth_hour,
        gender=current.gender or 'male',
        n_da_yun=10,
    )
    # 如果 lunar_python 不可用，用 fallback：从 case.bazi 硬编码
    if not dayun and case.bazi:
        # 简化 fallback：每 10 岁一段，用 case.ganzhi_year 做起点
        for i in range(8):
            start_age = i * 10 + 1
            dayun.append({
                'gan': '?', 'zhi': '?', 'name': f'大运{i+1}',
                'start': start_age, 'end': min(start_age + 10, end_age + 1),
                'start_year': start_year + start_age,
                'end_year': start_year + min(start_age + 10, end_age),
            })

    # ── trajectory_events 表事件（年视图需要 age + damage）──
    year_events = []
    try:
        te_list = db.query(TrajectoryEvent).filter(
            TrajectoryEvent.case_id == case.id,
            TrajectoryEvent.age.isnot(None),
        ).all()
        for te in te_list:
            if te.damage:
                year_events.append({
                    'age': te.age,
                    'damage': dict(te.damage),
                    'days': te.duration_days or 540,
                    'type': te.event_type,
                    'label': te.label,
                })
    except Exception:
        pass

    # ── 核心推演（v2: build_year_view_v2 + dv/dt 约束 + σ 场）──
    result = build_year_view_v2(
        innate=innate,
        dayun=dayun,
        age_start=0, age_end=end_age,
        birth_year=start_year,
        events=year_events,
    )

    # 事件标注（给前端 markLine 用，day = age*365）
    event_marks = []
    for te in year_events:
        event_marks.append({
            'day': te['age'] * 365,
            'age': te['age'],
            'type': te['type'],
            'label': te['label'] or '',
            'direction': '发散' if te.get('damage') else '收敛',
            'isMedical': True,
            'impact': te.get('damage'),
        })
    result['events'] = event_marks
    result['user_id'] = current.qingnang_id
    result['case_id'] = case.id
    result['birth_year'] = start_year

    return result


# ═══════════════════════════════════════════════════════
# 🆕 radar — 体质雷达图三层（先天基底 + 当前观测 + 健康区带）
# docs/08 §4 契约
# ═══════════════════════════════════════════════════════

H_RANGE = {'wood': 30, 'fire': 40, 'earth': 30, 'metal': 24, 'water': 30}  # 每维健康区间半宽


@router.get("/radar")
def get_radar(db: Session = Depends(get_db), current: User = Depends(get_current_user),
              layer: str = 'all'):
    """体质雷达图三层数据

    Query params:
      layer: 'innate' | 'current' | 'all' — 显示哪层（默认 all 三层叠加）
    """
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if not case:
        return {"message": "未初始化建档"}

    dims = ['wood', 'fire', 'earth', 'metal', 'water']
    innate = case.v_innate or {k: 50 for k in dims}

    # v_current: 优先 case.v_current（上次 PPG 写入），否则取最新 Observation
    v_current = case.v_current
    if not v_current:
        latest = db.query(Observation).filter(
            Observation.case_id == case.id
        ).order_by(Observation.observed_at.desc()).first()
        v_current = (latest.v_obs if latest else None) or innate

    # 健康区带中心 H = [50,50,50,50,50]
    v_health_center = {k: 50 for k in dims}

    # 归一化偏离度: (v_current - v_innate) / H_RANGE
    delta_norm = {}
    for k in dims:
        v_cur = v_current.get(k, 50) if isinstance(v_current, dict) else 50
        v_in  = innate.get(k, 50) if isinstance(innate, dict) else 50
        hr    = H_RANGE.get(k, 30)
        delta_norm[k] = round((v_cur - v_in) / hr, 2)

    # SPUM Y/X 实时（用 v_current 算）
    yx = compute_yx(v_current) if isinstance(v_current, dict) else {'Y': 50, 'X': 50}

    # 三层
    layers = []
    if layer in ('all', 'innate'):
        layers.append({
            'name': '先天基底 S₀⁰', 'type': 'innate',
            'value': [innate.get(k, 50) for k in dims],
            'color': '#1A4D45', 'style': 'solid',
        })
    if layer in ('all', 'current'):
        layers.append({
            'name': '当前观测 V_obs', 'type': 'current',
            'value': [v_current.get(k, 50) for k in dims] if isinstance(v_current, dict) else [50]*5,
            'color': '#A8442F', 'style': 'solid',
        })
    if layer == 'all':
        layers.insert(0, {
            'name': '健康区带 H', 'type': 'center',
            'value': [50, 50, 50, 50, 50],
            'color': '#7BC4A9', 'style': 'dashed',
        })

    return {
        'user_id': current.qingnang_id,
        'case_id': case.id,
        'v_innate': innate,
        'v_current': v_current,
        'v_health_center': v_health_center,
        'h_range': H_RANGE,
        'delta_normalized': delta_norm,
        'yx_realtime': yx,
        'layers': layers,
        'computedAt': datetime.now().isoformat(),
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

    # ── 八字推演：前端如已带 v_innate（engine 为任何八字推演引擎），跳过重算 ──
    engine = body.get("engine", "")
    provided_v_innate = body.get("v_innate") if (
        engine.startswith("spum_bazi") or engine in ("local_fallback", "spum_bazi_provided")
    ) else None

    if provided_v_innate:
        # 复用前端已算好的结果
        v_innate = provided_v_innate
        bazi_result = body.get("bazi_result") or {}
        bazi = bazi_result.get("bazi") or "/".join(bazi_result.get("pillars") or []) or "未知"
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

    # ── 异步注入青檬引擎 per-user 拓扑管线（不阻塞响应）──
    qingnang_id = current.qingnang_id or f"user_{current.id}"
    asyncio.create_task(
        _async_seed_qingmeng_topology(qingnang_id, v_innate, bazi)
    )

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
    """调用 qingmeng-engine /v1/reasoning/bazi。失败时 fallback 到 lunar_python。"""
    # 1. 先调青檬引擎
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
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
    except Exception:
        pass
    # 2. fallback: lunar_python 本地推演
    from app.api.v1.assistant import _local_bazi_fallback, BaziIn
    body = BaziIn(birth_date=birth_date, birth_hour=birth_hour, birthplace=birthplace)
    return _local_bazi_fallback(body)
