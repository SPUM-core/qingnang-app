"""voice_service — 语音样本管理 + 循环覆盖 + 自动闻诊触发

策略：
  - 每用户最多保留 5 条语音样本（质量分优先保留），
    超过时替换质量最低的；总存储阈值 10MB 循环覆盖。
  - 收满 5 条 → 异步触发五音分析 → 写 VoiceAnalysis → 注入 system prompt
"""
from __future__ import annotations
import asyncio, tempfile, os, json, base64
from datetime import datetime
from sqlalchemy.sql import func

# models 延迟导入（测试环境相对导入问题）
VoiceSample = None
VoiceAnalysis = None


def _ensure_models():
    global VoiceSample, VoiceAnalysis
    if VoiceSample is None:
        try:
            from app.models.chat import VoiceSample as _VS, VoiceAnalysis as _VA
        except ImportError:
            # 测试环境兜底
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
            from app.models.chat import VoiceSample as _VS, VoiceAnalysis as _VA
        VoiceSample = _VS
        VoiceAnalysis = _VA
    return VoiceSample, VoiceAnalysis


# ── 存储策略常量 ──
VOICE_SAMPLE_MAX_PER_USER = 5          # 每用户最多 5 条
VOICE_STORAGE_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10MB 单用户总阈值

# 并发锁
_voice_analyzing: set = set()


def _calc_quality_score(duration: float, rms_mean: float | None, voiced_ratio: float | None) -> float:
    """综合质量分（0-100），用于决定替换谁"""
    score = 50.0  # 基础分
    if duration < 3: return max(0, score - 40)
    if duration >= 15: score += 15
    elif duration >= 8: score += 8

    if rms_mean is not None:
        if rms_mean < 0.005: score -= 30
        elif rms_mean < 0.02: score -= 10
        elif rms_mean > 0.08: score += 10

    if voiced_ratio is not None:
        if voiced_ratio < 0.2: score -= 20
        elif voiced_ratio > 0.7: score += 10

    return min(100.0, max(0.0, score))


def save_voice_sample(
    db: Session,
    user_id: int,
    audio_bytes: bytes,
    file_format: str = "webm",
    duration: float | None = None,
    asr_text: str | None = None,
    source: str = "chat",
    source_id: int | None = None,
) -> object:
    """存一条语音样本，自动管理循环覆盖策略"""
    VS, _ = _ensure_models()
    file_size = len(audio_bytes)

    # 尝试快速算质量分（librosa 重依赖，import 失败就算 50）
    quality = 50.0
    rms = voiced_ratio = None
    if duration is None or True:  # 总是尝试快速分析
        try:
            from app.utils.voice_analyzer import analyze_voice
            tmp = tempfile.NamedTemporaryFile(suffix=f".{file_format}", delete=False)
            tmp.write(audio_bytes); tmp.close()
            try:
                result = analyze_voice(tmp.name)
                if "error" not in result:
                    basic = result.get("basic", {})
                    duration = basic.get("duration_sec", duration)
                    rms = basic.get("rms_mean")
                    voiced_ratio = basic.get("voiced_ratio_pct", 0) / 100.0
                    quality = _calc_quality_score(duration or 5.0, rms, voiced_ratio)
            finally:
                try: os.remove(tmp.name)
                except Exception: pass
        except Exception:
            pass

    # 1. 存新样本
    sample = VS(
        user_id=user_id,
        duration=duration,
        file_size=file_size,
        file_format=file_format,
        audio_data=audio_bytes,
        quality_score=quality,
        asr_text=asr_text,
        source=source,
        source_id=source_id,
    )
    db.add(sample)
    db.flush()

    # 2. 循环覆盖：超数量 / 超总容量
    _evict_if_needed(db, user_id)

    db.commit()
    return sample


def _evict_if_needed(db: Session, user_id: int):
    """循环覆盖：按质量分低 → 老的优先删"""
    VS, _ = _ensure_models()
    # 先算总容量
    total = db.query(func.coalesce(func.sum(VS.file_size), 0)) \
              .filter(VS.user_id == user_id).scalar() or 0

    # 样本数
    count = db.query(VS).filter(VS.user_id == user_id).count()

    while count > VOICE_SAMPLE_MAX_PER_USER or total > VOICE_STORAGE_THRESHOLD_BYTES:
        # 找"最该被替换的"
        victim = db.query(VS).filter(VS.user_id == user_id) \
                  .order_by(VS.quality_score.asc(), VS.created_at.asc()) \
                  .first()
        if not victim:
            break
        victim_size = victim.file_size or 0
        db.delete(victim)
        count -= 1
        total -= victim_size


async def trigger_voice_analysis(user_id: int, force: bool = False) -> VoiceAnalysis | None:
    """触发五音分析（每 5 条样本汇总分析一次）

    force=True 时不管样本数多少都跑
    """
    global _voice_analyzing
    if user_id in _voice_analyzing:
        return None
    _voice_analyzing.add(user_id)

    try:
        from app.database import SessionLocal
        from app.utils.voice_analyzer import analyze_voice as _do_analyze

        VS, VA = _ensure_models()

        db = SessionLocal()
        try:
            # 取所有样本（最多 5 条）
            samples = db.query(VS).filter(VS.user_id == user_id) \
                      .order_by(VS.created_at.desc()) \
                      .limit(VOICE_SAMPLE_MAX_PER_USER).all()

            if len(samples) < 2 and not force:
                return None  # 样本太少，等更多

            # 去旧分析
            db.query(VA).filter(VA.user_id == user_id).delete()

            # 对每条分别分析
            results = []
            for s in samples:
                tmp = tempfile.NamedTemporaryFile(suffix=f".{s.file_format or 'webm'}", delete=False)
                tmp.write(s.audio_data or b''); tmp.close()
                try:
                    r = _do_analyze(tmp.name)
                    results.append((s.id, r))
                except Exception as e:
                    print(f"[voice-analyze] sample={s.id} error: {e}")
                finally:
                    try: os.remove(tmp.name)
                    except Exception: pass

            if not results:
                return None

            # 汇总（各五音能量取平均）
            aggregated = _aggregate_results([r for _, r in results if "error" not in r])

            # 写 VoiceAnalysis
            s_vector_str = ", ".join(f"{k}{v}" for k, v in aggregated["s_vector"].items())
            wy_summary = "; ".join(f"{n}({aggregated['wuyin'][n]['wuxing']}){aggregated['wuyin'][n]['energy_pct']:.0f}%{aggregated['wuyin'][n]['arrow']}"
                                  for n in ["宫","商","角","徵","羽"])
            vy_flag = "⚠️ 虚阳外浮+" if aggregated.get("virtual_yang", {}).get("detected") else ""

            summary_text = f"闻诊（五音）: {wy_summary} | {vy_flag} | S修正={s_vector_str} | 置信度={aggregated['confidence']}"

            analysis = VA(
                user_id=user_id,
                sample_ids=[sid for sid, _ in results],
                aggregated=len(results) > 1,
                basic=aggregated.get("basic"),
                wuyin=aggregated.get("wuyin"),
                virtual_yang=aggregated.get("virtual_yang"),
                s_vector=aggregated.get("s_vector"),
                confidence=aggregated.get("confidence", "low"),
                warnings=aggregated.get("warnings", []),
                summary_text=summary_text,
            )
            db.add(analysis)
            db.commit()
            return analysis
        finally:
            db.close()
    finally:
        _voice_analyzing.discard(user_id)


def _aggregate_results(results: list[dict]) -> dict:
    """多样本五音分析结果取平均"""
    if not results:
        return {"s_vector": {}, "wuyin": {}, "virtual_yang": {"detected": False}, "confidence": "low"}

    if len(results) == 1:
        return results[0]

    # 平均 basic
    basics = [r.get("basic", {}) for r in results]
    basic_agg = {}
    for k in ["duration_sec", "rms_mean", "f0_median_hz", "centroid_hz", "voiced_ratio_pct"]:
        vals = [b.get(k) for b in basics if b.get(k) is not None]
        if vals: basic_agg[k] = round(sum(vals) / len(vals), 2)

    # 平均五音能量
    wuyin_agg = {}
    for name, wuxing, lo, hi in [("宫","土",130,260),("商","金",260,390),("角","木",390,520),
                                  ("徵","火",520,780),("羽","水",780,1040)]:
        pcts = [r["wuyin"][name]["energy_pct"] for r in results if "error" not in r and name in r.get("wuyin", {})]
        avg_pct = round(sum(pcts) / len(pcts), 1) if pcts else 20.0
        dev = round((avg_pct / 100.0 - 0.20) / 0.20 * 100.0, 1)
        from ...utils.voice_analyzer import _deviation_arrow
        wuyin_agg[name] = {"wuxing": wuxing, "hz_range": [lo, hi],
                           "energy_pct": avg_pct, "deviation_pct": dev, "arrow": _deviation_arrow(dev)}

    # 虚阳外浮：任一检测到就算
    vy_detected = any(r.get("virtual_yang", {}).get("detected") for r in results)
    vy_conf = "high" if vy_detected else "low"
    fire_pcts = [r["virtual_yang"]["fire_pct"] for r in results if r.get("virtual_yang")]
    vy = {"detected": vy_detected, "fire_pct": round(sum(fire_pcts) / len(fire_pcts), 1) if fire_pcts else 0,
          "rms": basic_agg.get("rms_mean", 0), "confidence": vy_conf}
    if vy_detected:
        vy["note"] = f"徵火{vy['fire_pct']}% + RMS{vy['rms']} → 浮越"

    # S 向量（多数表决：取出现最多的方向）
    s_vector = {}
    for wx in ["木","火","土","金","水"]:
        arrows = []
        for r in results:
            a = r.get("s_vector", {}).get(wx)
            if a: arrows.append(a)
        if arrows:
            from collections import Counter
            most_common = Counter(arrows).most_common(1)[0][0]
            s_vector[wx] = most_common
        else:
            s_vector[wx] = "↔"

    # 虚阳外浮强制覆盖火
    if vy_detected and "火" in s_vector:
        s_vector["火"] = "↓↓↓"

    # 置信度取最低
    conf_order = {"high": 3, "medium": 2, "low": 1}
    conf_val = min(conf_order.get(r.get("confidence", "low"), 1) for r in results)
    confidence = [k for k, v in conf_order.items() if v == conf_val][0]

    warnings = list(set(w for r in results for w in r.get("warnings", [])))

    return {
        "basic": basic_agg,
        "wuyin": wuyin_agg,
        "virtual_yang": vy,
        "s_vector": s_vector,
        "confidence": confidence,
        "warnings": warnings,
        "version": "1.0",
        "algorithm": "SPUM-§4.6-aggregated",
    }


def get_latest_voice_analysis(db: Session, user_id: int):
    """取用户最新一次闻诊分析（build_system_prompt 用）"""
    _, VA = _ensure_models()
    return db.query(VA).filter(VA.user_id == user_id) \
           .order_by(VA.analyzed_at.desc()).first()
