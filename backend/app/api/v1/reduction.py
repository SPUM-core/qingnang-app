"""reduction — 归约算法库 API（开放边集 + 闭合算式）

活算子，非静态查表。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.utils.reduction_engine import (
    reduce_prescription, reduce_new_herb_entry, compare_outcome,
    ReductionState, HERB_DELTA_S, SEASON_MODULATION, WUXING_LIST
)
from app.utils.spacetime_engine import spacetime_context

router = APIRouter()


class PrescriptionReduceRequest(BaseModel):
    herbs: list[str] | str                       # ["茯苓 15g", "桂枝 10g"] 或 "茯苓15g 桂枝10g"
    v_base: dict[str, float]                      # {"wood": 55, "fire": 60, ...}
    birthplace: str = "上海"
    date: Optional[str] = None                   # "2026-10-14"（默认今天）


class HerbReduceRequest(BaseModel):
    name: str
    siqi: str                                     # 寒/凉/平/温/热/微温/微寒
    taste: str                                    # 辛/甘/酸/苦/咸，可组合如 "辛甘"
    grade: str = "中品"                           # 上品/中品/下品


class OutcomeCompareRequest(BaseModel):
    expected_delta_S: dict[str, float]
    outcome_delta_S: dict[str, float]
    chain_prediction: Optional[dict] = None


@router.post("/prescription")
def api_reduce_prescription(req: PrescriptionReduceRequest):
    """
    方剂归约（R1→R2→R3→R4 四步链）

    活算子输出：
      - raw_sum: 未调制的 ΔS 叠加
      - expected_delta_S: R3 增益中庸治理加权后的事前预期
      - chain_desc: 链条描述（如 "金→水→木链断于水形"）
      - missing_herbs: 药表未收录的药材（可通过 /herb 端点注册）
    """
    try:
        ctx_date = datetime.fromisoformat(req.date) if req.date else datetime.now()
        ctx = spacetime_context(ctx_date, req.birthplace)
        state = ReductionState()
        result = reduce_prescription(req.herbs, req.v_base, ctx, state)
        return {"ok": True, "engine": "reduction_v1", **result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/herb")
def api_reduce_new_herb(req: HerbReduceRequest):
    """
    开放边集入口：新药材归约 + 自动注册

    任何药材只要能描述性味（四气 + 五味）→ 归约为 ΔS 向量 → 注册到药表
    下次方剂归约自动命中（无需重复描述性味）。

    这是 "互联网边集（开放·无限）" 的对接点——
    药表完备性不来自静态存量，来自能被持续追加的开放边集。
    """
    try:
        result = reduce_new_herb_entry(req.name, req.siqi, req.taste, req.grade)
        return {"ok": True, "engine": "reduction_v1", **result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/compare")
def api_compare_outcome(req: OutcomeCompareRequest):
    """
    L4 回填：事前预期 vs 观察窗 → 偏差归因

    这是闭环检验——归约引擎不是瞎猜，它输出的是**可验证的事前预期**。
    临床用这个端点对比 TreatmentPlan.expected_delta_S 和 outcome_delta_S，
    偏差归因后可调用 /correct 修正算子权重。
    """
    try:
        result = compare_outcome(req.expected_delta_S, req.outcome_delta_S, req.chain_prediction)
        return {"ok": True, "engine": "reduction_v1", **result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/herbs")
def api_list_herbs():
    """列出当前药表收录（含开放边集注册）"""
    return {
        "ok": True,
        "count": len(HERB_DELTA_S),
        "herbs": [
            {"name": n, "siqi": v["siqi"], "taste": v["taste"],
             "grade": v["grade"], "source": v.get("source", "classical")}
            for n, v in HERB_DELTA_S.items()
        ],
        "open_edge_registered": [
            n for n, v in HERB_DELTA_S.items() if v.get("source") == "open_edge_set"
        ],
    }


@router.get("/modulation")
def api_get_modulation():
    """列出节气/时辰乘数表（当前实体化数值）"""
    return {
        "ok": True,
        "seasons": SEASON_MODULATION,
        "hours": {
            k: {wx: v.get(wx, 1.0) for wx in WUXING_LIST}
            for k, v in {
                "子": {"wood": 0.9, "fire": 0.6, "earth": 0.8, "metal": 1.0, "water": 1.5},
                "丑": {"wood": 0.9, "fire": 0.7, "earth": 1.3, "metal": 1.0, "water": 1.1},
                "寅": {"wood": 1.4, "fire": 1.1, "earth": 0.8, "metal": 0.9, "water": 1.0},
                "卯": {"wood": 1.5, "fire": 1.0, "earth": 0.8, "metal": 0.8, "water": 1.1},
                "辰": {"wood": 0.8, "fire": 0.9, "earth": 1.3, "metal": 1.1, "water": 0.9},
                "巳": {"wood": 1.0, "fire": 1.4, "earth": 0.9, "metal": 0.8, "water": 0.7},
                "午": {"wood": 0.9, "fire": 1.5, "earth": 1.0, "metal": 0.6, "water": 0.5},
                "未": {"wood": 1.0, "fire": 1.1, "earth": 1.3, "metal": 0.9, "water": 0.8},
                "申": {"wood": 0.9, "fire": 0.7, "earth": 1.0, "metal": 1.4, "water": 1.1},
                "酉": {"wood": 0.8, "fire": 0.6, "earth": 0.9, "metal": 1.5, "water": 1.2},
                "戌": {"wood": 0.9, "fire": 0.8, "earth": 1.3, "metal": 1.0, "water": 0.9},
                "亥": {"wood": 0.9, "fire": 0.5, "earth": 0.8, "metal": 1.1, "water": 1.5},
            }.items()
        },
    }
