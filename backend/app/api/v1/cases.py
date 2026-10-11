"""cases - 案例 CRUD + 初始化建档"""
import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...database import get_db
from ...models import (
    User, Case, Observation, TreatmentPlan, TrajectoryEvent,
    ChatMessage, LifeSignal,
    Challenge, Checkin,
    ShopReview, ShopOrder,
    Feedback, Friend,
    InquirySession,
)
# chat.py 里其他模型未在 __init__.py 导出，直接子模块导入
from ...models.chat import (
    ChatMemoryNode, VoiceSample, VoiceAnalysis,
    TonguePhoto, MedicalReport,
)
from ..deps import get_current_user
from ...config import settings
from ...utils import WUXING_LIST
from ...utils.trajectory_algorithm import (
    compute_health_bounds, compute_health_bounds_v2,
    compute_yx, build_year_view, build_year_view_v2, build_year_view_v3, norm,
    DIMS as _WU, get_wu_thresholds as _get_wu_thresholds,
    ganzhi_to_elems, elems_to_delta, get_liunian,
    build_jieqi_view_v2 as _build_jieqi_view_v2,
    build_jieqi_view_v3, WUXING_FB_AVAILABLE,
)
from ...utils.lunar_helper import (
    compute_dayun, compute_dayun_with_location,
    get_true_solar_hour, get_jieqi_dates,
    JIEQI_24,
)

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
        # ⚠️ 双重修复：显式五形白名单(P0-2) + 动态量纲阈值(P0-1)
        _wt, _st = _get_wu_thresholds(v)
        weak = [k for k in _WU if isinstance(v.get(k), (int, float)) and v.get(k) < _wt]
        strong = [k for k in _WU if isinstance(v.get(k), (int, float)) and v.get(k) > _st]
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
        # 无观测，返回 v2 格式空 SPUM 字段（保持前端字段一致性）
        return {
            "algorithm": "spum_computeHealthBounds_v2",
            "theory_source": "SPUM2611 + 青囊中医总纲",
            "target": [], "actual": [], "actual_elements": [], "events": [],
            "elems": [], "driftData": [], "yinTop": [], "yangBot": [],
            "diseaseModes": [], "elArr": [],
            "stateFlags": [], "spikeUp": [], "spikeDown": [], "adaptiveParams": {},
            "sigma_trend": [], "polytope_statuses": [], "health_score": [],
            "v_innate": case.v_innate, "v_baseline": case.v_baseline,
            "message": "暂无观测数据",
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
    spum_bounds_v2 = compute_health_bounds_v2(actual_elements, innate_ref, events)

    return {
        'algorithm': 'spum_computeHealthBounds_v2',
        'theory_source': 'SPUM2611 + 青囊中医总纲 + tizhi-curve沙盒(流年+平滑)',
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
        # ── SPUM 三曲线（统一用 v2，消除 v1/v2 漂移数据不一致）──
        'elems': actual_elements,
        'driftData': spum_bounds_v2['driftData'],
        'yinTop': spum_bounds_v2['yinTop'],
        'yangBot': spum_bounds_v2['yangBot'],
        'diseaseModes': spum_bounds_v2['diseaseModes'],
        'elArr': spum_bounds_v2['elArr'],
        # 动态健康区间（基于 SPUM 边界的 ±10%）
        'spum_healthy_zone': {
            'min': round(min(spum_bounds_v2['yangBot']) * 1.1, 1) if spum_bounds_v2['yangBot'] else -10,
            'max': round(max(spum_bounds_v2['yinTop']) * 1.1, 1) if spum_bounds_v2['yinTop'] else +10,
            'label': 'SPUM 动态健康区间',
        },
        # ── SPUM v2 完整字段（前端 DriftChart.vue 全部消费）──
        'sigma_trend': spum_bounds_v2['sigma_trend'],
        'polytope_statuses': spum_bounds_v2['polytope_statuses'],
        'violation_depths': spum_bounds_v2['violation_depths'],
        'frame_residues': spum_bounds_v2['frame_residues'],
        'health_score': [s / 100.0 for s in actual_scores],
        'S_vectors': spum_bounds_v2['S_vectors'],
        # tizhi-curve 沙盒核心：三态 + 尖峰触边 + 自适应参数
        'stateFlags': spum_bounds_v2['stateFlags'],
        'spikeUp': spum_bounds_v2['spikeUp'],
        'spikeDown': spum_bounds_v2['spikeDown'],
        'adaptiveParams': spum_bounds_v2['adaptiveParams'],
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

    # ── 核心推演（v3: Wuxing-FB 五形生克负反馈旁路叠加 v2 全部输出）──
    result = build_year_view_v3(
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
    innate_raw = case.v_innate or {k: 20 for k in dims}

    # v_current: 优先 case.v_current（上次 PPG 写入），否则取最新 Observation
    v_current_raw = case.v_current
    if not v_current_raw:
        latest = db.query(Observation).filter(
            Observation.case_id == case.id
        ).order_by(Observation.observed_at.desc()).first()
        v_current_raw = (latest.v_obs if latest else None) or innate_raw

    # ═══ 量纲归一化：全部映射到 Σ=100 概率分布空间（center=20）═══
    # DB 可能混存 center=20 概率分布（Σ≈100）和 center=50 标量（Σ≈250）
    # 这里统一归一化，确保 delta_norm / layers / YX 都在同一坐标系
    def _normalize(d: dict) -> dict:
        if not isinstance(d, dict):
            return {k: 20.0 for k in dims}
        vals = [float(d.get(k, 0)) for k in dims]
        total = sum(vals)
        if total < 1:  # 防止除零
            return {k: 20.0 for k in dims}
        return {k: round(d.get(k, 0) / total * 100, 1) for k in dims}

    innate = _normalize(innate_raw)
    v_current = _normalize(v_current_raw)

    # 健康区带中心 H = [20,20,20,20,20]（center=20 概率分布口径）
    v_health_center = {k: 20 for k in dims}

    # ── 2026-10-08 E2：H_RANGE 动态化 — Wuxing-FB θ（分岔式健康区间）↔ 概率分布口径 ──
    # 相对空间 s_i ≈ v_i/mean(v) − 1 → s=1.0 ↔ 分布均值 20；半宽 h_i = θ_i × 20
    # θ 由「当前观测」的稳态虚实折损决定：越虚 θ 越小 → 区间越窄（健康区间变窄=风险升高）
    h_range = dict(H_RANGE)
    try:
        from ...utils import wuxing_feedback as _wfb
        v_rel_cur = _wfb.to_relative(v_current)
        rho0_dyn = _wfb.rho_from_relative(v_rel_cur, equilibrium=1.0)
        A_dyn = _wfb.build_coupling_matrix()
        ss_dyn = _wfb.steady_state(rho0_dyn, {k: 0.0 for k in dims}, A_dyn, n_steps=12)
        h_range = {k: round(max(6.0, float(ss_dyn['theta'][k]) * 20.0), 1) for k in dims}
    except Exception:
        h_range = dict(H_RANGE)  # fallback：wuxing_feedback 不可用时保持静态区间

    # 归一化偏离度: (v_current_norm - v_innate_norm) / h_range
    # 注：h_range 是 center=20 概率分布空间的各维健康半宽（θ×20 动态换算）
    delta_norm = {}
    for k in dims:
        v_cur = v_current.get(k, 20)
        v_in  = innate.get(k, 20)
        hr    = h_range.get(k, 30)
        delta_norm[k] = round((v_cur - v_in) / hr, 2)

    # SPUM Y/X 实时（用归一化后 v_current 算）
    yx = compute_yx(v_current) if isinstance(v_current, dict) else {'Y': 20, 'X': 20}

    # 三层（全部 center=20 概率分布空间）
    layers = []
    if layer == 'all':
        layers.append({
            'name': '健康区带 H', 'type': 'center',
            'value': [20, 20, 20, 20, 20],
            'color': '#7BC4A9', 'style': 'dashed',
        })
    if layer in ('all', 'innate'):
        layers.append({
            'name': '先天基底 S₀⁰', 'type': 'innate',
            'value': [innate.get(k, 20) for k in dims],
            'color': '#1A4D45', 'style': 'solid',
        })
    if layer in ('all', 'current'):
        layers.append({
            'name': '当前观测 V_obs', 'type': 'current',
            'value': [v_current.get(k, 20) for k in dims],
            'color': '#A8442F', 'style': 'solid',
        })

    return {
        'user_id': current.qingnang_id,
        'case_id': case.id,
        'v_innate': innate,
        'v_current': v_current,
        'v_health_center': v_health_center,
        'h_range': h_range,             # 动态 θ×20（2026-10-08 E2）
        'h_range_static': H_RANGE,      # 静态参考（旧口径，用于对比）
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
    # ⭐ 2026-10-08 新增：出生地经纬度（真太阳时校正必需）
    if body.get("birthplace"): current.birth_city = body["birthplace"]
    if body.get("longitude") is not None and body.get("longitude") != "":
        current.birth_longitude = float(body["longitude"])
    # birth_latitude 前端 QuestionnaireView 暂时没传，先看 birth_city 是否能自动查
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
    清：所有 user_id 关联数据 + Case 关联数据 + qingmeng 引擎拓扑文件。
    用户账号本身保留。"""
    import os, glob as _glob

    deleted = {
        # ── Case 关联（case_id）──
        "observations": 0, "plans": 0, "events": 0, "case": False,
        # ── User 关联（user_id / creator_id）──
        "chat_messages": 0, "chat_memory": 0, "life_signals": 0,
        "voice_samples": 0, "voice_analyses": 0,
        "tongue_photos": 0, "medical_reports": 0,
        "challenges": 0, "checkins": 0,
        "shop_reviews": 0, "shop_orders": 0,
        "feedbacks": 0, "friends": 0,
        "inquiry_sessions": 0,
        # ── 文件系统 ──
        "qingmeng_topology_files": 0,
    }

    case = db.query(Case).filter(Case.user_id == current.id).first()
    cid = case.id if case else None

    # ── 1. Case 级清理（case_id 关联）──
    if cid:
        deleted["observations"] = db.query(Observation).filter(Observation.case_id == cid).delete()
        deleted["plans"]       = db.query(TreatmentPlan).filter(TreatmentPlan.case_id == cid).delete()
        deleted["events"]      = db.query(TrajectoryEvent).filter(TrajectoryEvent.case_id == cid).delete()
        db.delete(case)
        deleted["case"] = True

    # ── 2. User 级清理（全部按 user_id / creator_id / participant 清理）──
    uid = current.id

    # Chat & 对话信号（today-todos 的数据源 2 和 3！不清除的话今日建议会残留）
    deleted["chat_messages"] = db.query(ChatMessage).filter(ChatMessage.user_id == uid).delete()
    deleted["chat_memory"]   = db.query(ChatMemoryNode).filter(ChatMemoryNode.user_id == uid).delete()
    deleted["life_signals"]  = db.query(LifeSignal).filter(LifeSignal.user_id == uid).delete()

    # 五诊采集数据
    deleted["voice_samples"]  = db.query(VoiceSample).filter(VoiceSample.user_id == uid).delete()
    deleted["voice_analyses"] = db.query(VoiceAnalysis).filter(VoiceAnalysis.user_id == uid).delete()
    deleted["tongue_photos"]  = db.query(TonguePhoto).filter(TonguePhoto.user_id == uid).delete()
    deleted["medical_reports"] = db.query(MedicalReport).filter(MedicalReport.user_id == uid).delete()

    # 挑战打卡（只清用户创建的 + 用户参与的 checkin）
    deleted["challenges"] = db.query(Challenge).filter(
        Challenge.creator_id == uid
    ).delete(synchronize_session=False)
    deleted["checkins"] = db.query(Checkin).filter(Checkin.user_id == uid).delete()

    # 商城
    deleted["shop_reviews"] = db.query(ShopReview).filter(ShopReview.user_id == uid).delete()
    deleted["shop_orders"]  = db.query(ShopOrder).filter(ShopOrder.user_id == uid).delete()

    # 反馈
    deleted["feedbacks"] = db.query(Feedback).filter(Feedback.user_id == uid).delete()

    # 好友关系（双向：user_id=我 OR friend_id=我）
    deleted["friends"] = db.query(Friend).filter(
        (Friend.user_id == uid) | (Friend.friend_id == uid)
    ).delete()

    # 问诊会话
    deleted["inquiry_sessions"] = db.query(InquirySession).filter(InquirySession.user_id == uid).delete()

    # ── 3. 重置用户建档标记 + 清体质向量基底 ──
    current.is_onboarded = False
    current.v_base = None
    db.commit()

    # ── 4. 清理 qingmeng 引擎拓扑持久化文件（与 _reset_user.py 一致）──
    TOPO_DIR = os.path.expanduser('~/.qingmeng/user_states')
    qingnang_id = current.qingnang_id or f"user_{uid}"
    if os.path.isdir(TOPO_DIR):
        removed = 0
        for f in _glob.glob(os.path.join(TOPO_DIR, f'user_*{qingnang_id}*.pkl')):
            try:
                os.remove(f); removed += 1
            except OSError: pass
        for f in _glob.glob(os.path.join(TOPO_DIR, f'user_{uid}.pkl')):
            try:
                os.remove(f); removed += 1
            except OSError: pass
        deleted["qingmeng_topology_files"] = removed

    logger.info(f"[reset] user={qingnang_id} 已重置: {deleted}")
    return {"ok": True, "deleted": deleted, "message": "已重置，请重新建档"}


@router.get("/today-todos")
async def get_today_todos(db: Session = Depends(get_db),
                          current: User = Depends(get_current_user)):
    """今日生活建议 Todo 聚合端点 — 时间空间 × 分类 × 人性化约束版。

    核心原则：一个人的时间是有限的 → 建议卡片在时间空间里占位，
    同类同时间槽最多 2 条，新建议只能替换占位而不是无限追加。

    约束规则：
    ┌─────────────────────────────────────────────────┐
    │ 每个 (时间槽, 分类) 组合最多 2 条                 │
    │   早餐 × 饮食 → 最多 2 种                         │
    │   早晨 × 运动 → 最多 2 种（且互斥：只选一种执行）  │
    │   全天 × 穿衣 → 最多 2 套                          │
    │   全天 × 住家 → 最多 3 条                          │
    │ 总量 ≤ 12 条                                       │
    │ 同类关键词归并（"泡脚"/"足浴"/"睡前泡脚" → 一类）   │
    └─────────────────────────────────────────────────┘
    """
    import json as _json
    from datetime import datetime, timedelta
    from collections import defaultdict
    from ...models import ChatMessage, LifeSignal
    from ...utils.maturity import compute_maturity

    # ═══════════════════════════════════════════════════════
    # 🎯 约束常量（人性化天花板）
    # ═══════════════════════════════════════════════════════

    # 每个分类的硬上限（不管时间槽）
    _PER_CATEGORY_LIMIT = {
        "diet": 4,        # 饮食建议每天最多 4 条
        "cloth": 2,       # 穿衣最多 2 套（一套推荐一套备选）
        "exercise": 3,    # 运动最多 3 条（早晨/午后/晚上各一种）
        "sleep": 2,       # 睡眠最多 2 条
        "home": 3,        # 住家最多 3 条
        "avoid": 3,       # 避忌最多 3 条（警示类）
        "herb": 2,        # 方药最多 2 条
        "lifestyle": 3,   # 生活方式最多 3 条
    }
    # 每个 (时间槽, 分类) 组合的子上限
    _PER_SLOT_CAT_LIMIT = 2
    # 总量天花板
    _TOTAL_CAP = 12

    # 同类关键词归并表 → 归一化 key（模糊去重 + 时间槽推断）
    _CATEGORY_KEYWORDS = {
        "diet": ["早餐", "早餐", "午餐", "晚餐", "夜宵", "吃", "食", "粥", "汤", "菜", "茶", "饮", "饭", "面", "羹"],
        "cloth": ["穿衣", "穿搭", "衣服", "着", "戴", "围巾", "外套", "鞋", "袜"],
        "exercise": ["运动", "跑步", "走", "练", "八段锦", "太极", "瑜伽", "健身", "晨练", "散步", "动"],
        "sleep": ["睡", "眠", "卧", "躺", "早休", "午歇", "子时"],
        "home": ["住", "房", "家", "居", "室", "通风", "打扫", "整理"],
        "avoid": ["忌", "禁", "避免", "勿", "慎", "别"],
        "herb": ["药", "汤", "方", "丸", "散", "膏", "饮", "泡", "煮"],
        "lifestyle": ["泡脚", "足浴", "按", "灸", "浴", "洗", "护", "养", "调"],
    }

    # 时间槽关键词 → 推断标题属于哪个时间空间
    _SLOT_KEYWORDS = {
        "morning": ["早", "晨", "卯", "辰", "朝霞", "清晨"],
        "noon": ["午", "中", "未", "日中", "白天"],
        "evening": ["晚", "傍", "申", "酉", "黄昏", "入夜"],
        "night": ["夜", "深", "戌", "亥", "子", "丑", "寅", "眠", "睡"],
    }

    def _infer_category(title: str, hint: str = "") -> str:
        """从标题推断分类（AI suggestions 里可能没 category 字段）"""
        t = title + hint
        for cat, kws in _CATEGORY_KEYWORDS.items():
            for kw in kws:
                if kw in t:
                    return cat
        return "lifestyle"

    def _infer_time_slot(title: str) -> str:
        """从标题推断时间槽 → morning/noon/evening/night/全天"""
        for slot, kws in _SLOT_KEYWORDS.items():
            for kw in kws:
                if kw in title:
                    return slot
        return "any"  # 全天适用的

    def _normalize(title: str) -> str:
        """归一化关键词 → 模糊去重 key"""
        t = title.lower().replace(" ", "")
        # 核心归并：不同表述 → 同一 key
        merges = {
            "泡脚": "足浴", "足浴": "足浴", "洗脚": "足浴", "沐足": "足浴",
            "跑步": "跑步/运动", "晨跑": "跑步/运动",
            "八段锦": "八段锦", "八段": "八段锦",
            "散步": "散步", "快走": "散步", "走路": "散步",
            "早餐": "早餐", "早饭": "早餐", "早点": "早餐",
            "午餐": "午餐", "午饭": "午餐",
            "晚餐": "晚餐", "晚饭": "晚餐",
            "早睡": "早睡", "早卧": "早睡", "子时": "早睡",
            "通风": "通风/住家", "开窗": "通风/住家",
        }
        for k, v in merges.items():
            if k in t:
                return v
        return title.strip()[:8]  # 兜底取前 8 字

    # ═══════════════════════════════════════════════════════
    # 聚合主流程开始
    # ═══════════════════════════════════════════════════════

    case = db.query(Case).filter(Case.user_id == current.id).first()
    todos_raw = []  # 所有原始候选（带 category/time_slot/norm_key）

    # ═══ maturity stage 过滤 ═══
    mat = compute_maturity(current, db)
    stage = mat["stage"]
    _ALLOW_CATS_BY_STAGE = {
        1: {"lifestyle"},
        2: {"diet", "avoid", "lifestyle"},
        3: {"diet", "avoid", "lifestyle", "exercise", "sleep", "cloth", "home"},
        4: {"diet", "avoid", "lifestyle", "exercise", "sleep", "cloth", "home", "herb"},
    }
    allowed_cats = _ALLOW_CATS_BY_STAGE.get(stage, _ALLOW_CATS_BY_STAGE[1])

    # ═══ 数据源 1：qingmeng-engine lifestyle（food_good + home_reminders）═══
    try:
        from .notifications import _call_qingmeng_lifestyle, build_user_meta
        v = (case.v_baseline if case else None) or current.v_base or {}
        if v:
            llm_data = await _call_qingmeng_lifestyle(
                v_base=v,
                v_current=(case.v_current if case else None),
                qingnang_id=current.qingnang_id or f"user_{current.id}",
                user_meta=build_user_meta(current, case),
            )
            # food_good → diet category
            if "diet" in allowed_cats:
                for i, f in enumerate(llm_data.get("food_good", [])):
                    title = f.get("title", "")
                    todos_raw.append({
                        "id": f"food-good-{i}",
                        "title": title, "desc": f.get("desc", ""),
                        "detail": f.get("detail", ""), "reason": f.get("reason", ""),
                        "source_ref": f.get("source_ref", ""),
                        "icon": "🍜",
                        "priority": "medium", "source_type": "lifestyle",
                        "route": "/notifications",
                        "category": "diet",
                        "time_slot": _infer_time_slot(title),
                        "norm_key": _normalize(title),
                    })
            # cloth_reminders（如果有） → cloth
            if "cloth" in allowed_cats:
                for i, c in enumerate(llm_data.get("cloth_reminders", [])[:3]):
                    title = c.get("title", "")
                    todos_raw.append({
                        "id": f"cloth-{i}",
                        "title": title, "desc": c.get("desc", ""),
                        "detail": c.get("detail", ""), "reason": c.get("reason", ""),
                        "source_ref": c.get("source_ref", ""),
                        "icon": "👔", "priority": "medium", "source_type": "lifestyle",
                        "route": "/notifications",
                        "category": "cloth",
                        "time_slot": _infer_time_slot(title),
                        "norm_key": _normalize(title),
                    })
            # home_reminders → home（最多 3 条）
            if "home" in allowed_cats:
                for i, h in enumerate(llm_data.get("home_reminders", [])[:3]):
                    title = h.get("title", "")
                    todos_raw.append({
                        "id": f"home-{i}",
                        "title": title, "desc": h.get("desc", ""),
                        "detail": h.get("detail", ""), "reason": h.get("reason", ""),
                        "source_ref": h.get("source_ref", ""),
                        "icon": "🏠", "priority": "high" if h.get("urgent") else "medium",
                        "source_type": "lifestyle", "route": "/notifications",
                        "category": "home",
                        "time_slot": _infer_time_slot(title),
                        "norm_key": _normalize(title),
                    })
    except Exception as e:
        logger.info(f"[today-todos] qingmeng LLM 源跳过: {e}")

    # ═══ 数据源 2：AI 对话 suggestions（**per-category limit 2**）═══
    # 关键改动：不再无限拉，每个 category 最多取 2 条
    cutoff = datetime.utcnow() - timedelta(hours=48)
    recent_ai_msgs = db.query(ChatMessage).filter(
        ChatMessage.user_id == current.id,
        ChatMessage.role == "assistant",
        ChatMessage.created_at >= cutoff,
        ChatMessage.signals.isnot(None),
    ).order_by(ChatMessage.created_at.desc()).all()

    # per-category 计数器 → 达到 limit 就跳过
    _ai_cat_count: dict[str, int] = defaultdict(int)

    for m in recent_ai_msgs:
        signals = m.signals if isinstance(m.signals, dict) else {}
        suggestions = signals.get("suggestions", [])
        chief_complaint = signals.get("chief_complaint", "")

        if chief_complaint and case and not case.chief_complaint:
            case.chief_complaint = chief_complaint
            try: db.commit()
            except: db.rollback()

        for s in suggestions:
            title = s.get("title", "")
            if not title:
                continue
            cat = s.get("category") or _infer_category(title)
            if cat not in allowed_cats:
                continue
            # 🎯 每个 category 最多 2 条 AI 建议（关键 limit！）
            if _ai_cat_count[cat] >= 2:
                continue
            _ai_cat_count[cat] += 1

            icon_map = {"diet": "🍜", "herb": "🌿", "exercise": "🏃",
                        "avoid": "⚠️", "lifestyle": "💡", "sleep": "🌙",
                        "cloth": "👔", "home": "🏠"}
            todos_raw.append({
                "id": f"ai-{m.id}-{_ai_cat_count[cat]}",
                "title": title,
                "desc": s.get("detail", ""),          # 短描述
                "detail": s.get("detail", ""),        # 🎯 做法详情
                "reason": s.get("reason", "") or s.get("note", ""),  # 🎯 推荐原因
                "source_ref": s.get("source", ""),     # 🎯 LLM 给的经典出处
                "icon": icon_map.get(cat, "💡"),
                "priority": s.get("priority", "medium"),
                "source_type": "ai",                    # 🎯 明确来源类型
                "route": "/shop" if cat in ("diet", "herb") else "/discover",
                "category": cat,
                "time_slot": _infer_time_slot(title),
                "norm_key": _normalize(title),
            })

    # ═══ 数据源 3：LifeSignal（仅聚合标签，不做 todos）═══
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
        tag_counts = {}
        for tag, label, cnt in sigs:
            tag_counts[tag] = tag_counts.get(tag, 0) + cnt
            recent_signals.append({"tag": tag, "label": label, "count": cnt})
    except Exception as e:
        logger.info(f"[today-todos] signals 源跳过: {e}")

    # ═══════════════════════════════════════════════════════
    # 🎯 人性化约束层：按 (time_slot, category) 分组 → 每组最多 2 条
    # ═══════════════════════════════════════════════════════

    # 阶段 1：同类关键词归并去重（norm_key 相同只留 priority 最高的）
    by_norm: dict[str, list] = defaultdict(list)
    for t in todos_raw:
        by_norm[t["norm_key"]].append(t)

    deduped = []
    priority_order = {"high": 0, "medium": 1, "low": 2}
    for nk, group in by_norm.items():
        group.sort(key=lambda x: priority_order.get(x["priority"], 9))
        deduped.append(group[0])  # 每组留 priority 最高的那条

    # 阶段 2：按 (time_slot, category) 分组 → 每组 2 条上限
    by_slot_cat: dict[tuple, list] = defaultdict(list)
    for t in deduped:
        by_slot_cat[(t["time_slot"], t["category"])].append(t)

    slot_limited = []
    for (slot, cat), group in by_slot_cat.items():
        group.sort(key=lambda x: priority_order.get(x["priority"], 9))
        slot_limited.extend(group[:_PER_SLOT_CAT_LIMIT])

    # 阶段 3：per-category 硬上限
    by_cat: dict[str, list] = defaultdict(list)
    for t in slot_limited:
        by_cat[t["category"]].append(t)

    cat_limited = []
    for cat, group in by_cat.items():
        lim = _PER_CATEGORY_LIMIT.get(cat, 4)
        group.sort(key=lambda x: priority_order.get(x["priority"], 9))
        cat_limited.extend(group[:lim])

    # 阶段 4：总量排序 → 按 priority + 分源（AI vs lifestyle 平衡）+ 时段时效 → 截 12
    # 🆕 2026-10-11 按时间推荐：hero 主卡片永远推荐"现在该做的事"，
    #    已过时辰的建议沉底（早晨任务下午不再占据第一位）
    now_h = datetime.now().hour  # 本地时间小时（0-23）
    # 各时间槽窗口 [start, end)：start 到点才算进入当下，end 过后即沉底
    _SLOT_WINDOW = {
        "morning": (5, 11),     # 早晨 5-11 点（卯辰巳）
        "noon":    (11, 17),    # 午后 11-17 点（午未申）
        "evening": (17, 21),    # 傍晚 17-21 点（酉戌）
        "night":   (21, 24),    # 夜间 21-24 点（亥子时）
        "any":     (0, 24),     # 全天适用
    }

    def _time_rank(t):
        start_h, end_h = _SLOT_WINDOW.get(t.get("time_slot", "any"), (0, 24))
        if now_h >= end_h:
            return 3   # 已过时辰 → 沉底（今天的早晨任务，下午不再推荐）
        if start_h <= now_h < end_h:
            return 0   # 当下时辰 → 最优先（现在就该做）
        return 1       # 未到时辰 → 次优先（今天稍后安排）

    def _score(t):
        p = priority_order.get(t["priority"], 9)
        src_bonus = 0 if t.get("source_type") == "lifestyle" else 1
        return (_time_rank(t), p, src_bonus)

    cat_limited.sort(key=_score)
    final_todos = cat_limited[:_TOTAL_CAP]

    # 🎯 拆分：禁忌类 → 放到 avoidances（顶部提醒，不可打卡）；可执行 → 留在 todos
    # 双重判定：category=="avoid" OR title 以禁忌词开头（兜底 keyword 分类不准的情况）
    import re as _re
    _AVOID_PREFIX = _re.compile(r'^(避免|勿|忌|禁|严禁|不得|不可|不宜|少|不要|别)')
    def _is_avoid(t):
        if t.get("category") == "avoid": return True
        title = t.get("title", "")
        if _AVOID_PREFIX.search(title): return True
        desc = t.get("desc", "") or ""
        if _AVOID_PREFIX.search(desc[:10]): return True
        return False

    avoidances = [t for t in final_todos if _is_avoid(t)]
    actionable = [t for t in final_todos if not _is_avoid(t)]

    # 清理聚合字段（前端不需要这些内部字段）
    for t in actionable + avoidances:
        t.pop("category", None)
        t.pop("time_slot", None)
        t.pop("norm_key", None)

    return {
        "todos": actionable,
        "avoidances": [{"title": t["title"], "desc": t.get("desc", "")} for t in avoidances],
        "total": len(actionable),
        "chief_complaint": case.chief_complaint if case else "",
        "recent_signals": recent_signals,
        "sources": {
            "lifestyle": len([t for t in actionable if t.get("source_type") == "lifestyle"]),
            "ai": len([t for t in actionable if str(t.get("source", "")).startswith("ai")]),
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


# ═══════════════════════════════════════════════════════
# 🆕 trajectories/jieqi-view — 24 节气五行属性视图
# 后端算法占位（算法层 build_jieqi_view_v2 待实现）
# 先用真实节气日期 + mock 五行偏移返回
# ═══════════════════════════════════════════════════════

# 每个节气的五行微调量（中医理论定义）
_JIEQI_WUXING_BIAS = {
    '立春': {'wood':+1.5,'fire':+0.3,'earth':0,'metal':0,'water':-0.3},
    '雨水': {'wood':+1.2,'fire':+0.5,'earth':0,'metal':0,'water':-0.5},
    '惊蛰': {'wood':+1.0,'fire':+0.8,'earth':0,'metal':0,'water':-0.8},
    '春分': {'wood':+0.8,'fire':+1.0,'earth':0,'metal':0,'water':-1.0},
    '清明': {'wood':+0.5,'fire':+1.2,'earth':+0.3,'metal':0,'water':-1.2},
    '谷雨': {'wood':+0.3,'fire':+1.3,'earth':+1.0,'metal':0,'water':-0.8},
    '立夏': {'wood':0,'fire':+1.5,'earth':+0.5,'metal':0,'water':-1.0},
    '小满': {'wood':0,'fire':+1.3,'earth':+0.8,'metal':0,'water':-0.8},
    '芒种': {'wood':-0.2,'fire':+1.2,'earth':+1.0,'metal':0,'water':-0.5},
    '夏至': {'wood':-0.5,'fire':+1.0,'earth':+1.2,'metal':0,'water':-0.3},
    '小暑': {'wood':-0.8,'fire':+0.8,'earth':+1.3,'metal':0,'water':0},
    '大暑': {'wood':-1.0,'fire':+0.5,'earth':+1.5,'metal':0,'water':+0.3},
    '立秋': {'wood':-0.8,'fire':+0.3,'earth':+1.2,'metal':+1.2,'water':0},
    '处暑': {'wood':-0.5,'fire':0,'earth':+0.8,'metal':+1.5,'water':+0.3},
    '白露': {'wood':-0.3,'fire':-0.2,'earth':+0.5,'metal':+1.5,'water':+0.5},
    '秋分': {'wood':0,'fire':-0.5,'earth':+0.3,'metal':+1.3,'water':+0.8},
    '寒露': {'wood':+0.2,'fire':-0.8,'earth':0,'metal':+1.0,'water':+1.0},
    '霜降': {'wood':+0.3,'fire':-1.0,'earth':+0.5,'metal':+0.8,'water':+0.8},
    '立冬': {'wood':+0.5,'fire':-1.2,'earth':0,'metal':+0.5,'water':+1.0},
    '小雪': {'wood':+0.3,'fire':-1.3,'earth':-0.3,'metal':+0.3,'water':+1.2},
    '大雪': {'wood':0,'fire':-1.5,'earth':-0.5,'metal':0,'water':+1.5},
    '冬至': {'wood':-0.3,'fire':-1.5,'earth':-0.8,'metal':-0.3,'water':+1.3},
    '小寒': {'wood':-0.5,'fire':-1.3,'earth':-1.0,'metal':-0.5,'water':+1.2},
    '大寒': {'wood':-0.3,'fire':-1.0,'earth':-0.8,'metal':-0.3,'water':+1.0},
}

_JIEQI_MAIN_WX = {
    '立春':'wood','雨水':'wood','惊蛰':'wood','春分':'wood','清明':'wood','谷雨':'earth',
    '立夏':'fire','小满':'fire','芒种':'fire','夏至':'fire','小暑':'fire','大暑':'earth',
    '立秋':'metal','处暑':'metal','白露':'metal','秋分':'metal','寒露':'metal','霜降':'earth',
    '立冬':'water','小雪':'water','大雪':'water','冬至':'water','小寒':'water','大寒':'water',
}


@router.get("/trajectories/jieqi-view")
def get_jieqi_view(db: Session = Depends(get_db), current: User = Depends(get_current_user),
                   year_age: int = 30):
    """某一年 24 节气的五行属性视图（前端「流年气运」和「节气属性」tab 共用）

    Query params:
      year_age: 该年年龄（用户当前年龄 ±n）
    """
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if not case:
        return {"message": "未初始化建档"}

    # 基础信息
    birth_year = int(str(current.birth_date)[:4]) if current.birth_date else 1990
    calendar_year = birth_year + year_age
    v_innate = case.v_innate or {k: 50 for k in ['wood','fire','earth','metal','water']}

    # 大运（带真太阳时校正）
    birth_lon = current.birth_longitude
    dayun_list = compute_dayun_with_location(
        current.birth_date or '1990-01-01',
        current.birth_hour, current.gender, birth_longitude=birth_lon, n_da_yun=10,
    )

    # 该年所在大运
    dayun_active = None
    for dy in dayun_list:
        if dy['start'] <= year_age <= dy['end']:
            dayun_active = dy
            break
    if not dayun_active and dayun_list:
        # fallback：找最接近的
        dayun_active = dayun_list[0]

    # 24 节气日期（lunar_python 精确计算）
    jq_dates = get_jieqi_dates(calendar_year)

    # 真太阳时展示
    solar_hour, solar_offset = get_true_solar_hour(
        current.birth_date or '1990-01-01',
        current.birth_hour, current.birth_longitude,
    )

    # ⭐ 统一算法层：trajectory_algorithm.build_jieqi_view_v3
    # v2 + Wuxing-FB 旁路: 每帧节气 = 大运+流年+节气 bias → 弛豫 → 稳态
    # 新增 tolerance_u*, zone, weak_virtual（报告第 6 章产品信号）
    liunianGZ = get_liunian(calendar_year)  # {g, z}
    dayun_active_gz = {'gan': dayun_active['gan'], 'zhi': dayun_active['zhi']} if dayun_active else {'gan':'?','zhi':'?'}
    jv_result = build_jieqi_view_v3(calendar_year, dayun_active_gz, liunianGZ, jq_dates, innate=v_innate)

    # 在算法层结果上叠加 true_solar_time（算法层不管地理，这里补充）
    jieqi = []
    for jq in jv_result['jieqi']:
        jieqi.append({
            **jq,
            'true_solar_time': solar_hour,
        })

    return {
        'view_mode': 'jieqi_view',
        'algorithm': 'spumHealthBounds_v2',
        'theory_source': 'SPUM 五运六气引擎',
        'year_age': year_age,
        'calendar_year': calendar_year,
        'liunian': _split_ganzhi(case.ganzhi_year or ''),
        'dayun_active': dayun_active,
        'dayun': dayun_list,
        'user_location': {
            'city': current.birth_city or '未设置',
            'longitude': current.birth_longitude,
            'latitude': current.birth_latitude,
            'true_solar_offset_min': solar_offset,
            'note': '请在个人设置补填出生地经纬度以启用真太阳时校正',
        },
        'v_innate': v_innate,
        'jieqi': jieqi,
    }


# ═══════════════════════════════════════════════════════
# 🆕 trajectories/adjustment-view — 调节视图（2026-10-08 接 v3 真实链路）
# 自然发展（反事实 projected）vs 青囊介入（actual）
# ═══════════════════════════════════════════════════════

@router.get("/trajectories/adjustment-view")
def get_adjustment_view(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    """调节视图：先天自然发展（虚线）vs 青囊调平介入（实线）

    2026-10-08 修复：替换原 mock（随机数伪造 projected/actual）为 build_year_view_v3 真实推演。
      - projected = 无干预推演（天时注入：大运+流年）
      - actual    = 带干预推演（干预年龄后向虚维补注入）
      - 净改善量  = Δu*（调平后耐受强度的抬升），不再用 mock 的"疾病天数"

    干预来源（按优先级）：
      1. trajectory_events 中 boost 非空的事件（boost 最大维 = 补虚目标）
      2. 最近 TreatmentPlan.expected_delta_S（方案预期的补益向量）
      3. 无记录 → 尚未介入，projected=actual 前段重合，comparison 全 0
    """
    case_obj = db.query(Case).filter(Case.user_id == current.id).first()
    if not case_obj:
        return {"message": "未初始化建档"}

    innate = (case_obj.v_innate if case_obj else None) or {k: 20 for k in ['wood', 'fire', 'earth', 'metal', 'water']}

    # ── 与 year-view 相同的推演参数（dayun/events/age 范围）──
    start_year = (current.birth_date or '1990-01-01')[:4]
    try:
        start_year = int(start_year)
    except ValueError:
        start_year = 1990
    end_age = max(0, datetime.now().year - start_year)
    if end_age < 30:
        end_age = 81

    dayun = compute_dayun(
        birth_date=current.birth_date or '1990-01-01',
        birth_hour=current.birth_hour,
        gender=current.gender or 'male',
        n_da_yun=10,
    )
    if not dayun and case_obj.bazi:
        for i in range(8):
            s_a = i * 10 + 1
            dayun.append({'gan': '?', 'zhi': '?', 'name': f'大运{i+1}',
                          'start': s_a, 'end': min(s_a + 10, end_age + 1)})

    year_events = []
    try:
        te_list = db.query(TrajectoryEvent).filter(
            TrajectoryEvent.case_id == case_obj.id,
            TrajectoryEvent.age.isnot(None),
        ).all()
        for te in te_list:
            if te.damage:
                year_events.append({'age': te.age, 'damage': dict(te.damage),
                                    'days': te.duration_days or 540,
                                    'type': te.event_type, 'label': te.label})
    except Exception:
        pass

    # ── 调平干预（补虚目标维 = boost / expected_delta_S 最大正向维）──
    interventions = []
    try:
        iv_list = db.query(TrajectoryEvent).filter(
            TrajectoryEvent.case_id == case_obj.id,
            TrajectoryEvent.boost.isnot(None),
        ).all()
        for te in iv_list:
            boost = te.boost or {}
            if boost:
                dim = max(boost, key=lambda k: boost.get(k, 0))
                interventions.append({
                    'age': te.age, 'idx': te.age, 'dim': dim, 'strength': 1.2,
                    'label': te.label or te.event_type, 'day': te.age * 365,
                    'impact': round(float(boost.get(dim, 0)), 1),
                })
    except Exception:
        pass
    if not interventions:
        try:
            plan = db.query(TreatmentPlan).filter(
                TreatmentPlan.case_id == case_obj.id,
                TreatmentPlan.expected_delta_S.isnot(None),
            ).order_by(TreatmentPlan.created_at.desc()).first()
            if plan and plan.expected_delta_S:
                ed = plan.expected_delta_S
                dim = max(ed, key=lambda k: ed.get(k, 0))
                inter_age = max(0, int(round((datetime.now().year - start_year) * 0.6)))
                interventions.append({
                    'age': inter_age, 'idx': inter_age, 'dim': dim, 'strength': 1.2,
                    'label': (plan.strategy or '青囊调平方案'), 'day': inter_age * 365,
                    'impact': round(float(ed.get(dim, 0)), 1),
                })
        except Exception:
            pass

    # ── 双线推演 ──
    proj = build_year_view_v3(innate=innate, dayun=dayun, age_start=0, age_end=end_age,
                              birth_year=start_year, events=year_events)
    act = build_year_view_v3(innate=innate, dayun=dayun, age_start=0, age_end=end_age,
                             birth_year=start_year, events=year_events,
                             interventions=interventions)

    wfp = proj.get('wuxing_fb') or {}
    wfa = act.get('wuxing_fb') or {}
    if not wfp:
        return {'view_mode': 'adjustment_view', 'algorithm': 'v2 (wuxing_fb 未加载)',
                'message': 'Wuxing-FB 不可用，调节视图暂缺'}

    n = len(wfp['driftData_wuxing'])
    ages = list(range(0, end_age + 1))[:n]

    def build_side(wf):
        elems = []
        for age, s in zip(ages, wf['s_series']):
            e = {'day': age * 365, 'age': age, 't': f'第{age}岁'}
            e.update(s)
            elems.append(e)
        return {
            'elems': elems,
            'driftData': wf['driftData_wuxing'],        # 相对空间 −s_mean
            's_series': wf['s_series'],
            'tolerance_u_series': wf['tolerance_u_series'],
            'zone_series': wf['zone_series'],
            'weak_virtual_series': wf['weak_virtual_series'],
            # 临界下沿健康带（θ≈1.0 → 0.7θ 下沿 ≈ 0.7，相对空间）
            'yangBot': [-0.7] * n,
            'yinTop': [+0.7] * n,
            'stateFlags': ['healthy'] * n,
            'wuxing_fb': wf,
        }

    projected = build_side(wfp)
    actual = build_side(wfa)

    # ── 净改善量：Δu*（调平后耐受抬升）──
    proj_u = [t['tolerance_u_star'] for t in wfp['tolerance_u_series']]
    act_u = [t['tolerance_u_star'] for t in wfa['tolerance_u_series']]
    total_shift = round(sum(act_u) / len(act_u) - sum(proj_u) / len(proj_u), 2)

    def bad_days(wf):
        cnt = 0
        for z in wf['zone_series']:
            for d, tag in z['zone'].items():
                if tag in ('OUT', '实', '虚', 'CRIT', '临界'):
                    cnt += 1
                    break
        return cnt

    proj_bad, act_bad = bad_days(wfp), bad_days(wfa)

    plan_out = None
    try:
        plan = db.query(TreatmentPlan).filter(TreatmentPlan.case_id == case_obj.id).order_by(
            TreatmentPlan.created_at.desc()).first()
        if plan:
            plan_out = {
                'name': plan.strategy or '青囊调平方案',
                'start_date': plan.created_at.strftime('%Y-%m-%d') if plan.created_at else None,
                'end_date': None,
                'expected_improvement': 12,
                'actual_improvement': total_shift,
                'status': 'ongoing' if plan.user_confirmed is False else 'completed',
            }
    except Exception:
        pass

    return {
        'view_mode': 'adjustment_view',
        'algorithm': 'spum_wuxing_fb_v3 + intervention',
        'projected': projected,
        'actual': actual,
        'interventions': interventions,
        'plan': plan_out,
        'comparison': {
            'total_shift': total_shift,                       # Δu* 净改善（耐受抬升）
            'disease_days_projected': proj_bad,               # 带外/临界年数（最脆维）
            'disease_days_actual': act_bad,
            'peak_reduction': round(max(act_u) - max(proj_u), 2),
        },
    }


def _split_ganzhi(name: str) -> dict:
    """'庚午' → {gan:'庚', zhi:'午', name:'庚午'}"""
    if not name or len(name) < 2:
        return {'gan': '', 'zhi': '', 'name': name or ''}
    return {'gan': name[0], 'zhi': name[1], 'name': name}
