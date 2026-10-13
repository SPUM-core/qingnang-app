"""spacetime — 青囊时空引擎 API

核心理念：生活建议必须结合时空变量
  - 不能只说"你土形弱→补土"
  - 要说"今日卯月卯日木旺克土，此时猛补土虚不受补，宜疏肝为先，申时金旺时再健脾"

三个端点：
  GET  /spacetime/context          — 时空上下文（四柱/旺相/建除/节气）
  POST /spacetime/tiao-hou         — 调候引擎（时空×体质→动态建议）
  GET  /spacetime/daily-brief      — 一站式 daily_brief（推荐接入点）
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from ...database import get_db
from ...models import User, Case
from ...utils.spacetime_engine import (
    spacetime_context, tiao_hou_engine, spacetime_advice, spacetime_daily_brief,
    WUXING_CN, TIANGAN, DIZHI,
)
from ..deps import get_current_user

router = APIRouter()


class TiaoHouIn(BaseModel):
    v_base: dict[str, float]
    datetime: Optional[str] = None       # ISO 格式，不传用当前时间
    birthplace: Optional[str] = None


# ═══════════════════════════════════════════════════════════
# 1. 时空上下文（公开接口，不鉴权也能算）
# ═══════════════════════════════════════════════════════════
@router.get("/context")
def get_spacetime_context(
    ts: Optional[str] = Query(None, description="ISO 格式时间，不传用当前时间"),
    birthplace: Optional[str] = Query(None),
):
    """返回指定时间点的完整时空上下文"""
    try:
        dt = datetime.fromisoformat(ts) if ts else datetime.now()
    except ValueError:
        raise HTTPException(400, "ts 必须是 ISO 格式时间")

    ctx = spacetime_context(dt, birthplace)
    return {
        "datetime": dt.isoformat(),
        "sizhu": ctx['sizhu'],
        "lingshou": {
            "ganzhi": ctx['lingshou_gz'],
            "wuxing": ctx['lingshou'],
            "cn": WUXING_CN.get(ctx['lingshou'], ctx['lingshou']),
        },
        "wuxing_status": ctx['wuxing_status'],
        "wuxing_weight": ctx['wuxing_weight'],
        "jianchu": ctx['jianchu'],
        "jianchu_advice": ctx['jianchu_advice'],
        "jieqi": ctx['jieqi'],
        "day": {"gan": ctx['day_gan'], "zhi": ctx['day_zhi'], "gz": ctx['day_gz']},
        "hour_gz": ctx['sizhu']['hour'],
        "is_degraded": ctx.get('is_degraded', False),
    }


# ═══════════════════════════════════════════════════════════
# 2. 调候引擎（需要 v_base）
# ═══════════════════════════════════════════════════════════
@router.post("/tiao-hou")
def run_tiao_hou(body: TiaoHouIn):
    """纯调候引擎 — 给定 v_base + 时间 → 返回动态调候建议
    
    不依赖后端用户数据，前端也可以自己算。
    """
    try:
        dt = datetime.fromisoformat(body.datetime) if body.datetime else datetime.now()
    except ValueError:
        raise HTTPException(400, "datetime 必须是 ISO 格式")

    ctx = spacetime_context(dt, body.birthplace)
    th = tiao_hou_engine(body.v_base, ctx)
    return {
        "context": {
            "lingshou": WUXING_CN.get(ctx['lingshou'], ctx['lingshou']),
            "wuxing_status": ctx['wuxing_status'],
            "jianchu": ctx['jianchu'],
            "jieqi": ctx['jieqi'].get('current_term', ''),
        },
        "priorities": th['priorities'],
        "avoid_now": th['avoid_now'],
        "opportunities": th['opportunities'],
        "window_tips": th['window_tips'],
        "summary": th['summary'],
    }


# ═══════════════════════════════════════════════════════════
# 3. ⭐ 一站式 daily_brief（推荐接入点，带鉴权自动拉 v_base）
# ═══════════════════════════════════════════════════════════
@router.get("/daily-brief")
def spacetime_daily_brief_endpoint(
    ts: Optional[str] = Query(None, description="ISO 格式时间，不传用当前时间"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """时空调候版 daily_brief — 替换原有的"静态补偏"建议
    
    调用链：
      1. 从用户档案拉 v_base
      2. 计算时空上下文（四柱/旺相/建除/节气）
      3. 调候引擎（时空 × 体质 → 动态建议）
      4. 返回完整建议 + 时空上下文（供前端渲染）
    
    Returns:
      {
        ctx: { sizhu, lingshou, wuxing_status, jianchu, jieqi },
        tiao_hou: { priorities, avoid_now, opportunities, summary },
        advice: { todos, avoidances, spacetime_summary },
      }
    """
    # 1. 拉用户 v_base
    case = db.query(Case).filter(Case.user_id == current.id).first()
    v_base = case.v_baseline if case else {"wood": 50, "fire": 50, "earth": 50, "metal": 50, "water": 50}

    # 2. 算时间
    try:
        dt = datetime.fromisoformat(ts) if ts else datetime.now()
    except ValueError:
        raise HTTPException(400, "ts 必须是 ISO 格式")

    # 3. 一站式调候
    result = spacetime_daily_brief(v_base, dt, birthplace=None)

    # 4. 补上用户信息
    result['user'] = {
        'qingnang_id': current.qingnang_id,
        'nickname': current.nickname,
        'has_case': case is not None,
    }
    result['datetime'] = dt.isoformat()

    return result


# ═══════════════════════════════════════════════════════════
# 4. 静态参考表（前端渲染用，纯元数据）
# ═══════════════════════════════════════════════════════════
@router.get("/reference")
def spacetime_reference():
    """返回时空引擎的静态参考表（前端渲染用）"""
    return {
        "tiangan": TIANGAN,
        "dizhi": DIZHI,
        "wuxing_names": WUXING_CN,
        "shengsheng": {
            "木": "火", "火": "土", "土": "金", "金": "水", "水": "木",
        },
        "ke克": {
            "木": "土", "土": "水", "水": "火", "火": "金", "金": "木",
        },
        "status_wuxing": {
            "旺": "当令", "相": "我生", "休": "生我", "囚": "我克", "死": "克我",
        },
        "jianchu_good": {
            "除": "除旧迎新", "满": "祭祀祈福", "定": "安床",
            "执": "捕捉", "成": "开市", "开": "出行求财",
        },
        "jianchu_bad": {
            "建": "动土", "破": "诸事不宜", "危": "登高",
            "收": "出行", "闭": "开市",
        },
    }
