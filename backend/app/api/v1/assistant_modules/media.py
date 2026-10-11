"""media - 多媒体与档案：语音样本 / 舌象照片 / 检查报告上传与查询"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from ....database import get_db
from ....models import User
from ...deps import get_current_user

router = APIRouter()


@router.get("/voice/samples")
async def list_voice_samples(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """当前用户的语音样本列表（元数据，不含音频二进制）"""
    from ....models.chat import VoiceSample
    samples = db.query(VoiceSample).filter(VoiceSample.user_id == current.id) \
              .order_by(VoiceSample.created_at.desc()).limit(10).all()
    return {
        "samples": [
            {
                "id": s.id,
                "duration": s.duration,
                "file_format": s.file_format,
                "file_size": s.file_size,
                "quality_score": s.quality_score,
                "asr_text": s.asr_text,
                "source": s.source,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            } for s in samples
        ],
        "count": len(samples),
        "storage_used": sum(s.file_size or 0 for s in samples),
        "storage_threshold": 10 * 1024 * 1024,
        "max_per_user": 5,
    }


@router.post("/voice/upload")
async def upload_voice_sample(
    body: dict,  # {audio_base64, format, duration}
    force_analyze: bool = False,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """手动上传一条语音样本（VoiceSampleView 用）"""
    import base64 as _b64
    from ....utils.voice_service import save_voice_sample, trigger_voice_analysis

    audio_b64 = body.get("audio_base64") or body.get("voice_base64")
    if not audio_b64:
        raise HTTPException(status_code=400, detail="缺少 audio_base64")

    audio_bytes = _b64.b64decode(audio_b64)
    sample = save_voice_sample(
        db=db, user_id=current.id,
        audio_bytes=audio_bytes,
        file_format=body.get("format", body.get("voice_format", "webm")),
        duration=body.get("duration") or body.get("voice_duration"),
        asr_text=body.get("asr_text"),
        source=body.get("source", "voice_sample_view"),
    )

    # 触发闻诊分析
    import asyncio as _asyncio3
    _asyncio3.create_task(trigger_voice_analysis(current.id, force=force_analyze))

    return {"id": sample.id, "quality_score": sample.quality_score, "ok": True}


@router.get("/voice/latest-analysis")
async def get_latest_voice_analysis(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """最新闻诊分析结果"""
    from ....utils.voice_service import get_latest_voice_analysis
    va = get_latest_voice_analysis(db, current.id)
    if not va:
        return {"found": False, "message": "暂无闻诊数据"}
    return {
        "found": True,
        "id": va.id,
        "confidence": va.confidence,
        "summary_text": va.summary_text,
        "basic": va.basic,
        "wuyin": va.wuyin,
        "virtual_yang": va.virtual_yang,
        "s_vector": va.s_vector,
        "aggregated": va.aggregated,
        "analyzed_at": va.analyzed_at.isoformat() if va.analyzed_at else None,
        "warnings": va.warnings,
    }


@router.post("/voice/force-analyze")
async def force_voice_analysis(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """手动触发闻诊分析（不管样本数量）"""
    import asyncio as _asyncio4
    from ....utils.voice_service import trigger_voice_analysis
    _asyncio4.create_task(trigger_voice_analysis(current.id, force=True))
    return {"ok": True, "message": "闻诊分析已触发"}


# ═══════════════════════════════════════════════════════
# 舌诊（望诊）
# ═══════════════════════════════════════════════════════

@router.post("/tongue/upload")
async def upload_tongue_photo(
    body: dict,  # {image_base64, format}
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """上传舌部照片 → OpenCV HSV 分析 → SPUM 舌象判定"""
    import base64 as _b64, tempfile, os
    from app.models.chat import TonguePhoto
    from app.utils.tongue_analyzer import analyze_tongue as _analyze

    img_b64 = body.get("image_base64")
    if not img_b64:
        raise HTTPException(status_code=400, detail="缺少 image_base64")

    img_bytes = _b64.b64decode(img_b64)
    file_format = body.get("format", "jpeg").lower().replace("image/", "")
    if file_format not in ("jpeg", "jpg", "png", "webp"):
        file_format = "jpeg"

    # 临时文件 → 调 OpenCV 分析
    suffix = ".jpg" if file_format in ("jpeg", "jpg") else f".{file_format}"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(img_bytes); tmp.close()

    try:
        result = _analyze(tmp.name)
    finally:
        try: os.remove(tmp.name)
        except Exception: pass

    file_size = len(img_bytes)
    # 质量分：面积占比 + 置信度
    quality = 50.0
    if "tongue_ratio" in result: quality += min(result["tongue_ratio"] * 200, 30)
    if result.get("confidence") == "high": quality += 20
    elif result.get("confidence") == "medium": quality += 10
    quality = min(100, quality)

    # 循环覆盖：每用户最多 3 张 + 20MB 总阈值
    MAX_PHOTOS = 3
    MAX_BYTES = 20 * 1024 * 1024

    tp = TonguePhoto(
        user_id=current.id,
        file_format=file_format,
        file_size=file_size,
        image_data=img_bytes,
        quality_score=quality,
        confidence=result.get("confidence", "low"),
        tongue_type=result.get("spum_mapping", {}).get("tongue_type") or result.get("tongue_type"),
        s_vector=result.get("spum_mapping", {}).get("s_vector"),
        bgr_mean=result.get("bgr_mean"),
        coating_pct=result.get("coating"),
        rationale=result.get("spum_mapping", {}).get("rationale") or result.get("rationale"),
        warnings=result.get("warnings"),
    )
    db.add(tp); db.flush()

    # 循环覆盖
    count = db.query(TonguePhoto).filter(TonguePhoto.user_id == current.id).count()
    total = db.query(func.coalesce(func.sum(TonguePhoto.file_size), 0)).filter(
        TonguePhoto.user_id == current.id).scalar() or 0

    while count > MAX_PHOTOS or total > MAX_BYTES:
        victim = db.query(TonguePhoto).filter(TonguePhoto.user_id == current.id) \
                 .order_by(TonguePhoto.quality_score.asc(), TonguePhoto.created_at.asc()).first()
        if not victim: break
        total -= victim.file_size or 0; count -= 1
        db.delete(victim)

    db.commit()

    return {
        "ok": True,
        "id": tp.id,
        "confidence": tp.confidence,
        "tongue_type": tp.tongue_type,
        "s_vector": tp.s_vector,
        "rationale": tp.rationale,
        "warnings": tp.warnings,
        "quality_score": tp.quality_score,
    }


@router.get("/tongue/latest")
async def get_latest_tongue(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """最新闻诊舌象"""
    from app.models.chat import TonguePhoto
    tp = db.query(TonguePhoto).filter(TonguePhoto.user_id == current.id) \
         .order_by(TonguePhoto.created_at.desc()).first()
    if not tp:
        return {"found": False}
    return {
        "found": True,
        "id": tp.id,
        "confidence": tp.confidence,
        "tongue_type": tp.tongue_type,
        "s_vector": tp.s_vector,
        "rationale": tp.rationale,
        "coating_pct": tp.coating_pct,
        "bgr_mean": tp.bgr_mean,
        "created_at": tp.created_at.isoformat() if tp.created_at else None,
    }


# ═══════════════════════════════════════════════════════
# 检查报告（归档）
# ═══════════════════════════════════════════════════════

@router.post("/report/upload")
async def upload_medical_report(
    body: dict,  # {image_base64, format, report_title?, report_type?}
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """上传检查报告 → 存图 → 可选 LLM 结构化提取（有 vision 时自动）

    注：当前项目只有 DeepSeek（非 vision），所以默认只存图 + metadata。
    有 vision LLM API 时自动启用结构化识别。
    """
    import base64 as _b64
    from app.models.chat import MedicalReport
    from datetime import datetime

    img_b64 = body.get("image_base64")
    if not img_b64:
        raise HTTPException(status_code=400, detail="缺少 image_base64")

    img_bytes = _b64.b64decode(img_b64)
    file_format = body.get("format", "jpeg").lower().replace("image/", "")
    if file_format not in ("jpeg", "jpg", "png", "webp"):
        file_format = "jpeg"

    # 尝试 LLM 识别（检查是否有 vision API）
    structured = None
    raw_text = None
    provider = "manual"

    # DeepSeek JSON mode 不能看图，但可以做结构化文本提取
    # 这里留入口：有 vision API（如 qwen-vl）时自动启用
    # 当前先只存图，用户可手动填写 metadata

    MAX_REPORTS = 20
    MAX_BYTES = 50 * 1024 * 1024

    mr = MedicalReport(
        user_id=current.id,
        file_format=file_format,
        file_size=len(img_bytes),
        image_data=img_bytes,
        report_title=body.get("report_title"),
        report_type=body.get("report_type", "other"),
        report_date=body.get("report_date"),
        recognized=structured is not None,
        provider=provider,
        raw_text=raw_text,
        structured=structured,
        manual_notes=body.get("manual_notes"),
    )
    db.add(mr); db.flush()

    # 循环覆盖
    count = db.query(MedicalReport).filter(MedicalReport.user_id == current.id).count()
    total = db.query(func.coalesce(func.sum(MedicalReport.file_size), 0)).filter(
        MedicalReport.user_id == current.id).scalar() or 0

    while count > MAX_REPORTS or total > MAX_BYTES:
        victim = db.query(MedicalReport).filter(MedicalReport.user_id == current.id) \
                 .order_by(MedicalReport.created_at.asc()).first()
        if not victim: break
        total -= victim.file_size or 0; count -= 1
        db.delete(victim)

    db.commit()
    return {"ok": True, "id": mr.id, "message": "报告已上传（可稍后手动填写标题和类型）"}


@router.get("/report/list")
async def list_medical_reports(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    limit: int = 20,
):
    """用户报告列表（不含图片二进制，前端按需单条调取）"""
    from app.models.chat import MedicalReport
    reports = db.query(MedicalReport).filter(MedicalReport.user_id == current.id) \
              .order_by(MedicalReport.created_at.desc()).limit(limit).all()
    return {
        "reports": [
            {
                "id": r.id,
                "report_title": r.report_title,
                "report_type": r.report_type,
                "report_date": r.report_date.isoformat() if r.report_date else None,
                "recognized": r.recognized,
                "summary": r.summary,
                "file_size": r.file_size,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            } for r in reports
        ],
    }


@router.get("/report/{report_id}")
async def get_medical_report(
    report_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """单条报告详情（含图片二进制 base64，供前端查看）"""
    import base64 as _b64
    from app.models.chat import MedicalReport
    mr = db.query(MedicalReport).filter(
        MedicalReport.id == report_id,
        MedicalReport.user_id == current.id,
    ).first()
    if not mr:
        raise HTTPException(status_code=404, detail="报告不存在")
    return {
        "id": mr.id,
        "report_title": mr.report_title,
        "report_type": mr.report_type,
        "report_date": mr.report_date.isoformat() if mr.report_date else None,
        "recognized": mr.recognized,
        "provider": mr.provider,
        "raw_text": mr.raw_text,
        "structured": mr.structured,
        "summary": mr.summary,
        "spum_note": mr.spum_note,
        "manual_notes": mr.manual_notes,
        "file_format": mr.file_format,
        "image_base64": _b64.b64encode(mr.image_data or b"").decode() if mr.image_data else None,
        "created_at": mr.created_at.isoformat() if mr.created_at else None,
    }


@router.put("/report/{report_id}")
async def update_medical_report(
    report_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """手动更新报告 metadata（填标题、类型、备注等）"""
    from app.models.chat import MedicalReport
    from datetime import datetime

    mr = db.query(MedicalReport).filter(
        MedicalReport.id == report_id,
        MedicalReport.user_id == current.id,
    ).first()
    if not mr:
        raise HTTPException(status_code=404, detail="报告不存在")

    for field in ["report_title", "report_type", "report_date", "manual_notes", "spum_note", "summary"]:
        if field in body:
            setattr(mr, field, body[field])
    mr.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": mr.id}


@router.delete("/report/{report_id}")
async def delete_medical_report(
    report_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """删除一条报告"""
    from app.models.chat import MedicalReport
    mr = db.query(MedicalReport).filter(
        MedicalReport.id == report_id,
        MedicalReport.user_id == current.id,
    ).first()
    if not mr:
        raise HTTPException(status_code=404, detail="报告不存在")
    db.delete(mr); db.commit()
    return {"ok": True}

