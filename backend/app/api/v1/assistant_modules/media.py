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
# 检查报告（归档）— 重构版 v2：多格式 → 异步 LLM 提取
# 流水线：上传 → 文件解析 → LLM 结构化 → 自动写 TrajectoryEvent（待确认）
# ═══════════════════════════════════════════════════════

# 模块级缓存：report_id → asyncio.Task（用于检查是否还在跑）
import asyncio as _asyncio
import time as _time
_RUNNING_TASKS: dict[int, _asyncio.Task] = {}
# 进程启动时间（用于判断 pending 记录是否为孤儿）
_PROCESS_START = _time.time()


async def _resurrect_orphans(db):
    """进程启动时把 DB 里 provider='pending' 的孤儿记录重新派发。

    触发时机：应用启动时（main.py 的 lifespan）。
    """
    from app.models.chat import MedicalReport
    orphans = db.query(MedicalReport).filter(MedicalReport.provider == "pending").all()
    for mr in orphans:
        if mr.id in _RUNNING_TASKS: continue   # 已在跑
        # 把 image_data 读出来重新派发给 _process_report_async
        task = _asyncio.create_task(
            _process_report_async(mr.id, mr.user_id, mr.image_data or b"", mr.report_title)
        )
        _RUNNING_TASKS[mr.id] = task
        def _cleanup(t, _id=mr.id): _RUNNING_TASKS.pop(_id, None)
        task.add_done_callback(_cleanup)


# 暴露给 main.py lifespan 钩子
def resurrect_pending_reports():
    """同步包装：应用启动时扫 DB 重挂 pending 任务。"""
    from ....database import SessionLocal
    db = SessionLocal()
    try:
        # 注意：resurrect 需要 asyncio loop 已跑，这里先注册，真正派发在 lifespan 里
        loop = _asyncio.get_event_loop()
        loop.create_task(_resurrect_orphans(db))
    except Exception as e:
        print(f"[report] resurrect orphans skipped: {e}")
        db.close()


@router.post("/report/upload")
async def upload_medical_report(
    body: dict,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """上传检查报告（支持图片/TXT/MD/XLSX/DOCX/PDF）→ 后台异步解析 + LLM 结构化

    请求体两种模式任选：
      A. 前端 FileReader 读的 base64：{file_base64, filename, report_title?, report_type?, manual_notes?}
      B. 向后兼容旧图上传：{image_base64, format, report_title?, report_type?, manual_notes?}

    返回：{id, status:"processing", message}
          前端用 GET /report/{id} 轮询，status=done 时拿结构化结果。
    """
    import base64 as _b64
    from app.models.chat import MedicalReport
    from datetime import datetime

    # ── 1. 解 body（兼容新旧两种上传模式）──
    file_b64 = body.get("file_base64") or body.get("image_base64")
    filename = body.get("filename")
    file_format = body.get("format") or filename.split(".")[-1].lower() if filename else None

    if not file_b64:
        raise HTTPException(status_code=400, detail="缺少 file_base64 或 image_base64")

    raw_bytes = _b64.b64decode(file_b64)

    # ── 2. 先入库一条 processing 记录 ──
    MAX_REPORTS, MAX_BYTES = 30, 80 * 1024 * 1024

    mr = MedicalReport(
        user_id=current.id,
        file_format=file_format or "unknown",
        file_size=len(raw_bytes),
        image_data=raw_bytes if (file_format or "").startswith("image") else None,
        report_title=body.get("report_title"),
        report_type=body.get("report_type", "other"),
        report_date=None,     # LLM 提取后回填
        recognized=False,
        provider="pending",
        raw_text=None,
        structured=None,
        summary=None,
        manual_notes=body.get("manual_notes"),
        source="collect",
    )
    db.add(mr); db.flush()
    report_id = mr.id

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

    # ── 3. 启动后台异步流水线 ──
    task = _asyncio.create_task(_process_report_async(report_id, current.id, raw_bytes, filename))
    _RUNNING_TASKS[report_id] = task
    # task 结束后自动清理
    def _cleanup(t: _asyncio.Task):
        _RUNNING_TASKS.pop(report_id, None)
    task.add_done_callback(_cleanup)

    return {"ok": True, "id": report_id, "status": "processing",
            "message": "已上传，后台正在解析和提取，请稍后刷新查看"}


async def _process_report_async(report_id: int, user_id: int, raw_bytes: bytes, filename: str | None):
    """后台流水线：文件解析 → LLM 提取 → 写 DB → 写 TrajectoryEvent（pending）"""
    from app.models.chat import MedicalReport, Case
    from app.models.user import User
    from app.models.trajectory_event import TrajectoryEvent
    from app.utils.report_parser import parse
    from app.utils.report_llm import extract_report

    # 开一个独立 DB session（与请求线程解耦）
    from ....database import SessionLocal
    db = SessionLocal()
    try:
        mr = db.query(MedicalReport).filter(MedicalReport.id == report_id).first()
        if not mr: return

        # ── Step 1: 文件解析 ──
        parsed = parse(raw_bytes, filename)
        mr.raw_text = parsed.get("text_content") or ""
        mr.provider = parsed.get("format", "unknown")

        if not parsed.get("ok"):
            # 解析失败 — 入库标记，前端提示手动补填
            mr.recognized = False
            mr.summary = parsed.get("reason", "解析失败")
            mr.provider = "parse_failed"
            db.commit()
            return

        # ── Step 2: LLM 结构化提取 ──
        if parsed.get("text_content"):
            llm_result = await extract_report(parsed["text_content"])

            mr.recognized = llm_result.get("ok", False)
            mr.provider   = llm_result.get("provider", "llm")
            mr.structured = llm_result.get("structured")

            # 回填 metadata（前端没填的让 LLM 补）
            if llm_result.get("report_title") and not mr.report_title:
                mr.report_title = llm_result["report_title"]
            if llm_result.get("report_type") and mr.report_type == "other":
                mr.report_type = llm_result["report_type"]
            if llm_result.get("summary"):
                mr.summary = llm_result["summary"]
            if llm_result.get("report_date"):
                try:
                    from datetime import datetime as _dt
                    mr.report_date = _dt.strptime(llm_result["report_date"], "%Y-%m-%d")
                except Exception: pass

            # ── Step 3: trajectory_proposal → TrajectoryEvent(pending) ──
            proposal = llm_result.get("trajectory_proposal")
            if proposal and proposal.get("damage"):  # 有实质内容才写
                case = db.query(Case).filter(Case.user_id == user_id).first()
                if case:
                    # 算 age：从 User.birth_date + report_date 推
                    age = None
                    user = db.query(User).filter(User.id == user_id).first()
                    if user and user.birth_date and mr.report_date:
                        try:
                            from datetime import datetime as _dt3
                            bd = _dt3.strptime(user.birth_date[:10], "%Y-%m-%d")
                            age = mr.report_date.year - bd.year
                            if mr.report_date.month < bd.month or (mr.report_date.month == bd.month and mr.report_date.day < bd.day):
                                age -= 1
                        except Exception: pass

                    from datetime import datetime as _dt2
                    te = TrajectoryEvent(
                        case_id=case.id,
                        age=age or 0,   # 0 表示"报告里没日期，用户可手动调"
                        day=age * 365 if age else None,
                        event_type=proposal.get("event_type") or "波动",
                        label=f"[报告自动] {mr.report_title or filename or '未知报告'}",
                        direction=proposal.get("direction") or "注意",
                        damage=proposal.get("damage"),
                        boost=proposal.get("boost") or {},
                        duration_days=365,
                        source="report_archive",
                        confidence=0.6,
                        confirmed=False,
                        pending=True,
                    )
                    db.add(te)
            # llm_result.note 也写进 summary 尾部
            if llm_result.get("note"):
                suffix = f"\n（{llm_result['note']}）"
                if mr.summary: mr.summary = mr.summary + suffix
                else: mr.summary = suffix.strip()

        db.commit()
    except Exception as e:
        # 任何异常 — 入库标记，不要让用户卡死
        try:
            mr = db.query(MedicalReport).filter(MedicalReport.id == report_id).first()
            if mr:
                mr.summary = f"后台处理异常：{e}"
                mr.provider = "exception"
                db.commit()
        except Exception: pass
    finally:
        db.close()


@router.get("/report/{report_id}/status")
async def poll_report_status(
    report_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """前端轮询处理状态（轻量，只返回 status 字段）

    孤儿任务自动重生：provider=pending 但进程已启动超过 60s
    （说明旧进程的 asyncio.Task 已随进程消失）→ 此处重挂。
    """
    from app.models.chat import MedicalReport
    mr = db.query(MedicalReport).filter(
        MedicalReport.id == report_id,
        MedicalReport.user_id == current.id,
    ).first()
    if not mr:
        raise HTTPException(status_code=404, detail="报告不存在")

    task_alive = report_id in _RUNNING_TASKS

    # ── 孤儿重生：pending 但 Task 不在内存 + 进程已启动很久 ──
    if mr.provider == "pending" and not task_alive and (_time.time() - _PROCESS_START) > 60:
        _try_resurrect(report_id, mr.user_id, mr.image_data, mr.report_title)
        task_alive = True

    if task_alive or mr.provider == "pending":
        status = "processing"
    elif mr.recognized:
        status = "done"
    else:
        status = "failed" if mr.provider in ("parse_failed", "exception") else "done"

    return {
        "id": mr.id,
        "status": status,
        "recognized": mr.recognized,
        "provider": mr.provider,
        "note": mr.summary[:200] if mr.summary else None,
        "_orphan_resurrected": (mr.provider == "pending" and task_alive and
                                (_time.time() - _PROCESS_START) > 60),
    }


def _try_resurrect(report_id: int, user_id: int, raw_bytes: bytes | None, filename: str | None):
    """把孤儿 pending 记录重新派发给 _process_report_async。"""
    if report_id in _RUNNING_TASKS: return  # 已有人认领
    import asyncio as _aio
    task = _aio.create_task(
        _process_report_async(report_id, user_id, raw_bytes or b"", filename)
    )
    _RUNNING_TASKS[report_id] = task
    def _cleanup(t, _id=report_id): _RUNNING_TASKS.pop(_id, None)
    task.add_done_callback(_cleanup)
    print(f"[report] orphan report {report_id} resurrected")


@router.get("/report/list")
async def list_medical_reports(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    limit: int = 30,
):
    """用户报告列表（不含二进制）"""
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
                "provider": r.provider,
                "summary": r.summary,
                "file_format": r.file_format,
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
    """单条报告详情（含 base64 图 + 结构化 JSON + trajectory 提案）"""
    import base64 as _b64
    from app.models.chat import MedicalReport
    from app.models.trajectory_event import TrajectoryEvent
    mr = db.query(MedicalReport).filter(
        MedicalReport.id == report_id,
        MedicalReport.user_id == current.id,
    ).first()
    if not mr:
        raise HTTPException(status_code=404, detail="报告不存在")

    # 查本报告自动写入的 trajectory 提案
    from ..cases import Case   # 用已有的 Case 查询
    case = db.query(Case).filter(Case.user_id == current.id).first()
    trajectory_proposals = []
    if case:
        tps = db.query(TrajectoryEvent).filter(
            TrajectoryEvent.case_id == case.id,
            TrajectoryEvent.source == "report_archive",
        ).all()
        # 用 summary 里的 label 匹配（简单策略，精确匹配会加 source_id 关联）
        for tp in tps:
            if mr.report_title and mr.report_title in (tp.label or ""):
                trajectory_proposals.append({
                    "id": tp.id,
                    "age": tp.age,
                    "event_type": tp.event_type,
                    "label": tp.label,
                    "direction": tp.direction,
                    "damage": tp.damage,
                    "boost": tp.boost,
                    "confidence": tp.confidence,
                    "pending": tp.pending,
                    "confirmed": tp.confirmed,
                })

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
        "file_size": mr.file_size,
        "image_base64": _b64.b64encode(mr.image_data or b"").decode() if mr.image_data else None,
        "trajectory_proposals": trajectory_proposals,
        "created_at": mr.created_at.isoformat() if mr.created_at else None,
    }


@router.put("/report/{report_id}")
async def update_medical_report(
    report_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """手动更新报告 metadata"""
    from app.models.chat import MedicalReport
    from datetime import datetime
    mr = db.query(MedicalReport).filter(
        MedicalReport.id == report_id,
        MedicalReport.user_id == current.id,
    ).first()
    if not mr:
        raise HTTPException(status_code=404, detail="报告不存在")
    for field in ["report_title", "report_type", "report_date",
                  "manual_notes", "spum_note", "summary"]:
        if field in body: setattr(mr, field, body[field])
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

