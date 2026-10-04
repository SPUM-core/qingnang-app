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

# _health_score (v1 启发式 欧氏距离→健康度) 已于 2026-10-02 删除。
# 统一使用 trajectory_algorithm.compute_health_bounds_v2 的 health_score 字段
# （基于 SPUM2611 σ 密度场 + 越界深度 + 不完美修正 + dv/dt 钳制）。
# v2 health_score ∈ [0,1]，前端展示时 × 100 转百分比。
# _target_curve 保留（指数收敛曲线本身不含理论假设）。

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

    # 计算每个观测点的健康得分（统一用 v2 SPUM health_score，在循环后批量注入）
    dims = ['wood', 'fire', 'earth', 'metal', 'water']
    actual_points = []
    actual_scores = []
    actual_elements = []  # per-element 分量时间序列
    for i, ob in enumerate(obs_list):
        v = ob.v_obs or {}
        t = ob.observed_at
        if t:
            t_str = t.strftime('%m-%d')
        else:
            t_str = f'Day{i+1}'
        actual_points.append({
            'day': i + 1,
            't': t_str,
            'score': None,  # 将在 v2 compute_health_bounds_v2 后注入
            'observed_at': t.isoformat() if t else None,
            'v_obs': v,
            'syndrome_hint': ob.syndrome_hint,
        })
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

    # ═══ 统一用 v2 SPUM health_score（替代 v1 _health_score 启发式）═══
    # health_score 不依赖 events（σ × 越界深度 × 不完美修正 × dv/dt 钳制），
    # 提前调用拿分数，供 target 曲线和波动推断使用。
    innate_ref = case.v_innate or {k: 50 for k in dims}
    spum_bounds_v2_pre = compute_health_bounds_v2(actual_elements, innate_ref, events=None)
    # health_score ∈ [0,1]，× 100 转前端展示百分比
    v2_scores = [round(s * 100, 1) for s in spum_bounds_v2_pre['health_score']]
    for i, pt in enumerate(actual_points):
        pt['score'] = v2_scores[i] if i < len(v2_scores) else 50.0
    actual_scores = v2_scores

    # 目标收敛曲线：从第一个观测得分 → 90（v2 SPUM 健康区间中心，对齐 v2 实际范围）
    start_score = actual_scores[0]
    target_scores = _target_curve(start_score, 90.0, len(actual_scores))
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

    # ═══ 自动推断临床事件（基于 Observation 的 syndrome_hint）═══
    # 仅限 source='auto_infer' 级别启发式规则，已不再硬编码特定患者病历标签。
    # 历史上的 PRESET_EVENTS（胡运涛/曾银鸾专属综合征推断规则）已于 2026-10-02 移除，
    # 改为由前端事件编辑器手动写入 TrajectoryEvent 表。seed 脚本见
    # backend/scripts/seed_clinical_events.py （可选，用于迁移历史病历事件）。
    for i, ob in enumerate(obs_list):
        hint = (ob.syndrome_hint or '')
        # 未来可在这里添加通用的 syndrome_hint 自动推断规则，当前留空。
        # 所有持久化事件统一由 TrajectoryEvent 表提供。
        pass

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
    # 注：health_score 已在前面提前用 v2_pre 计算（不带 events），
    #     保证与 target/波动推断的一致性；此处再调一次 v2（带 events）
    #     仅用于 diseaseModes/frame_residues 等受事件影响的字段。
    # ═══════════════════════════════════════════════════════
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
        'health_score': [s / 100.0 for s in actual_scores],  # 与 actual_points.score 同源
        'S_vectors': spum_bounds_v2['S_vectors'],
    }


# ═══════════════════════════════════════════════════════
# 🆕 trajectories/year-view — 纯八字推演年视图（L3 终身预测基础）
# 数据源: User.birth_date/hour/gender → lunar_python 排大运
#       Case.v_innate + trajectory_events 表事件
# ═══════════════════════════════════════════════════════

@router.get("/trajectories/year-view")
def get_year_view(db: Session = Depends(get_db), current: User = Depends(get_current_user),
                 start_year: int | None = None, end_age: int = 81):
    """终身推演年视图 — 用 v_innate + 大运 + 事件构建每年 SPUM 三曲线

    Query params:
      start_year: 起始年份（默认从 User.birth_date 自动推导；未传则 1990 兜底）
      end_age:    推演到几岁（默认 81）
    """
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if not case:
        return {"message": "未初始化建档"}

    # 2026-10-02 修复：默认 start_year 从 User.birth_date 推导
    if start_year is None:
        try:
            start_year = int(str(current.birth_date)[:4]) if current.birth_date else 1990
        except (ValueError, TypeError):
            start_year = 1990

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


@router.post("/reset")
async def reset_my_case(db: Session = Depends(get_db),
                        current: User = Depends(get_current_user)):
    """重置当前用户的全部数据（"重新开始"按钮）。
    清：Observations → TreatmentPlans → TrajectoryEvents → Case → User.is_onboarded=False
    用户账号本身保留。"""
    deleted = {"observations": 0, "plans": 0, "events": 0, "case": False}

    case = db.query(Case).filter(Case.user_id == current.id).first()
    if case:
        cid = case.id
        deleted["observations"] = db.query(Observation).filter(Observation.case_id == cid).delete()
        deleted["plans"]       = db.query(TreatmentPlan).filter(TreatmentPlan.case_id == cid).delete()
        deleted["events"]      = db.query(TrajectoryEvent).filter(TrajectoryEvent.case_id == cid).delete()
        db.delete(case)
        deleted["case"] = True

    # 重置用户建档标记 + 清体质向量基底（让重新建档从白纸开始）
    current.is_onboarded = False
    current.v_base = None
    db.commit()

    logger.info(f"[reset] user={current.qingnang_id} 已重置: {deleted}")
    return {"ok": True, "deleted": deleted, "message": "已重置，请重新建档"}


@router.get("/today-todos")
def get_today_todos(db: Session = Depends(get_db),
                    current: User = Depends(get_current_user)):
    """今日生活建议 Todo 聚合端点。

    合并三个数据源 → 统一格式 Todo 卡片：
      1. /notifications/today 的动态生活提醒（food_good + home + 睡眠类）
      2. 最近 assistant 消息的 analysis.suggestions（AI 从对话中给出的建议）
      3. LifeSignal 最近标签（给前端做"你聊过这些"提示）

    返回结构:
      todos: [{id, title, desc, icon, priority, source, route?}]
      chief_complaint: str  # 自动回填到 Case 的主诉
      recent_signals: [{tag, label, count}]  # 30 天聚合
    """
    import json as _json
    from datetime import datetime, timedelta
    from ...models import ChatMessage, LifeSignal

    case = db.query(Case).filter(Case.user_id == current.id).first()
    todos = []

    # ═══ 数据源 1：notifications 生活提醒 ═══
    try:
        from .notifications import _generate_reminders
        v = (case.v_baseline if case else None) or current.v_base or {}
        if v:
            rem = _generate_reminders(v)
            # food_good → todo
            for i, f in enumerate(rem.get("food_good", [])):
                todos.append({
                    "id": f"food-good-{i}",
                    "title": f.get("title", ""),
                    "desc": f.get("desc", ""),
                    "icon": "🍜",
                    "priority": "medium",
                    "source": "lifestyle",
                    "route": "/notifications",
                })
            # home → todo（最多 3 条）
            for i, h in enumerate(rem.get("home", [])[:3]):
                todos.append({
                    "id": f"home-{i}",
                    "title": h.get("title", ""),
                    "desc": h.get("desc", ""),
                    "icon": "🏠",
                    "priority": "high" if h.get("urgent") else "medium",
                    "source": "lifestyle",
                    "route": "/notifications",
                })
    except Exception as e:
        logger.info(f"[today-todos] notifications 源跳过: {e}")

    # ═══ 数据源 2：AI 对话的 analysis.suggestions ═══
    # 找最近 24h 的 assistant 消息，signals 里有 suggestions
    cutoff = datetime.utcnow() - timedelta(hours=48)
    recent_ai_msgs = db.query(ChatMessage).filter(
        ChatMessage.user_id == current.id,
        ChatMessage.role == "assistant",
        ChatMessage.created_at >= cutoff,
        ChatMessage.signals.isnot(None),
    ).order_by(ChatMessage.created_at.desc()).all()

    seen_titles = set()
    for m in recent_ai_msgs:
        signals = m.signals if isinstance(m.signals, dict) else {}
        suggestions = signals.get("suggestions", [])
        chief_complaint = signals.get("chief_complaint", "")

        # 自动回填 chief_complaint
        if chief_complaint and case and not case.chief_complaint:
            case.chief_complaint = chief_complaint
            try:
                db.commit()
            except Exception:
                db.rollback()

        for s in suggestions:
            title = s.get("title", "")
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            cat = s.get("category", "lifestyle")
            icon_map = {"diet": "🍜", "herb": "🌿", "exercise": "🏃",
                        "avoid": "⚠️", "lifestyle": "💡", "sleep": "🌙"}
            todos.append({
                "id": f"ai-{m.id}-{len(seen_titles)}",
                "title": title,
                "desc": s.get("detail", ""),
                "icon": icon_map.get(cat, "💡"),
                "priority": s.get("priority", "medium"),
                "source": f"ai·{cat}",
                "route": "/shop" if cat in ("diet", "herb") else "/discover",
            })

    # ═══ 数据源 3：LifeSignal 最近 30 天聚合 ═══
    recent_signals = []
    try:
        cutoff30 = datetime.utcnow() - timedelta(days=30)
        sigs = db.query(
            LifeSignal.tag, LifeSignal.label,
            func.count(LifeSignal.id).label("cnt")
        ).filter(
            LifeSignal.user_id == current.id,
            LifeSignal.created_at >= cutoff30,
        ).group_by(LifeSignal.tag, LifeSignal.label).order_by(
            func.count(LifeSignal.id).desc()
        ).limit(15).all()
        # 聚合成 tag→count 摘要
        tag_counts = {}
        for tag, label, cnt in sigs:
            tag_counts[tag] = tag_counts.get(tag, 0) + cnt
            recent_signals.append({"tag": tag, "label": label, "count": cnt})
    except Exception as e:
        logger.info(f"[today-todos] signals 源跳过: {e}")

    # 去重 todos（按 title）
    deduped = []
    seen = set()
    priority_order = {"high": 0, "medium": 1, "low": 2}
    for t in sorted(todos, key=lambda x: priority_order.get(x["priority"], 9)):
        if t["title"] not in seen:
            seen.add(t["title"])
            deduped.append(t)

    return {
        "todos": deduped[:12],  # 最多 12 条
        "total": len(deduped),
        "chief_complaint": case.chief_complaint if case else "",
        "recent_signals": recent_signals,
        "sources": {
            "lifestyle": len([t for t in deduped if t["source"] == "lifestyle"]),
            "ai": len([t for t in deduped if t["source"].startswith("ai")]),
        },
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
