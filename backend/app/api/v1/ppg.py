"""ppg - PPG 采集上传 + 查询 + 硬件 SSE 桥接"""
import json
import logging
import sys
import threading
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import User, Case, Observation
from ...config import settings
from ..deps import get_current_user

router = APIRouter()
logger = logging.getLogger("qingnang.ppg")


# ═══════════════════════════════════════════════════════
# 青檬引擎 PPG 管线桥接 — 后台线程异步注入（不阻塞主响应）
# ═══════════════════════════════════════════════════════

def _ppg_to_qingmeng(qingnang_id: str,
                     v_obs: dict,
                     sqi: float | None,
                     delta_f: dict | None = None,
                     v_innate: dict | None = None) -> None:
    """后台线程同步调 qingmeng-engine PPG 端点。失败静默。"""
    try:
        payload = {"user_id": qingnang_id, "v_obs": v_obs, "sqi": sqi}
        if delta_f:
            payload["delta_f"] = delta_f
        if v_innate:
            payload["v_innate"] = v_innate  # 首次注入时用于建立先天基底
        with httpx.Client(timeout=3.0) as client:
            client.post(f"{settings.QINGMENG_URL}/v1/reasoning/ppg", json=payload)
    except Exception as exc:
        logger.info(f"[qingmeng-bridge] PPG 增量注入跳过: {exc}")


# ═══════════════════════════════════════════════════════
# 硬件桥：复用 qingnang/青囊/脉诊/采集 的 CheezPPGStreamer
# ═══════════════════════════════════════════════════════
# ──────────────────────────────────────────────────────
# 硬件桥：复用 qingnang/青囊/脉诊/采集 的采集脚本
# 两个目录是兄弟：e:\工作\qingnang-APP  和  e:\工作\qingnang
# ⚠ 两个目录都有 ppg_acquisition.py（不同版本）：
#   - 采集/ppg_acquisition.py — 有 selfcheck_hardware + CheezPPGStreamer（完整版）
#   - 理论/ppg_acquisition.py — 只有 CheezPPGStreamer（旧版）
# 所以 HW_COLLECT_DIR 必须 insert(0) 放在 sys.path 最前面，THEORY_DIR 放最后
# ──────────────────────────────────────────────────────
_root = Path(__file__).resolve().parents[4]   # qingnang-APP
_HW_COLLECT_DIR = _root.parent / "qingnang" / "青囊" / "脉诊" / "采集"
_THEORY_DIR = _root.parent / "qingnang" / "青囊" / "脉诊" / "理论"
if str(_HW_COLLECT_DIR) not in sys.path and _HW_COLLECT_DIR.exists():
    sys.path.insert(0, str(_HW_COLLECT_DIR))      # 最高优先级：硬件桥完整版
if str(_THEORY_DIR) not in sys.path and _THEORY_DIR.exists():
    sys.path.append(str(_THEORY_DIR))               # 最低优先级：理论目录（同名模块冲突）

# 全局单例：避免每次请求都重新开串口（Windows 串口独占）
_hw_streamer = None
_hw_lock = threading.Lock()

# collect 模式下 SSE handler 缓存的完整 raw filtered 波形（upload handler 读取）
_last_collect_raw_wave: list | None = None


class PpgUpload(BaseModel):
    """前端脉搏采集上传。

    前端定位为**采集程序**而非分析器——只上传原始波形 + 采集统计，
    分析（五形 ΔF / 证型匹配）由后端 qingmeng-engine 负责。
    """
    # 采集统计（前端直接测得，最可信）
    sqi: float = Field(..., ge=0, le=100)          # 心跳检出度（%）
    ppg_wave: list | None = None                    # 原始 PPG 波形（前端示波窗口快照）
    hr_bpm: float | None = None
    hrv_ms: float | None = None
    peak_count: int | None = None
    sample_count: int | None = None
    capture_duration_s: float | None = None

    # 可空：前端不再算 ΔF/v_obs，留空交给 qingmeng-engine
    delta_f: dict | None = None
    v_obs: dict | None = None
    syndrome_hint: str | None = None
    patient_height_m: float | None = Field(None, ge=0.5, le=2.5)


@router.post("/upload")
def upload_ppg(body: PpgUpload, db: Session = Depends(get_db),
               current: User = Depends(get_current_user)):
    """上传 PPG 观测 — 后端完整管线：
       raw_wave → preprocess → beat detect → features → six_qualities → delta_f → v_obs
       → qingmeng-engine 拓扑诊断 → 回写 DB → 返回完整报告。
    """
    import numpy as np
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="请先完成初始化建档")

    # ── Step 0: 初始化 Observation ──
    ob = Observation(
        case_id=case.id, source="cheezPPG", sqi=body.sqi,
        ppg_wave=body.ppg_wave,
        status="uploading",
        patient_height_m=(current.height / 100.0) if current.height else None,
    )
    db.add(ob); db.commit(); db.refresh(ob)

    def _fail(msg: str):
        ob.status = "failed"; ob.syndrome_hint = msg
        db.commit()
        raise HTTPException(status_code=422, detail=msg)

    # ── Step 1: 取完整 raw 波形（优先后端 collect 缓存，fallback 前端传来的）──
    global _last_collect_raw_wave
    raw_wave = _last_collect_raw_wave
    _last_collect_raw_wave = None   # 消费后清掉

    if not raw_wave or len(raw_wave) < 200:
        # fallback：前端传来的是 [-1, 1] 归一化波，跳过 preprocess
        if body.ppg_wave and len(body.ppg_wave) >= 100:
            raw_wave = [float(x) for x in body.ppg_wave]
            logger.info(f"[ppg] fallback: 使用前端归一化波形 {len(raw_wave)} 样本")
        else:
            _fail("波形数据过短，无法分析")

    try:
        ob.status = "analyzing"; db.commit()

        # ── Step 2: 用旧 bridge 完整 pipeline（特征聚合、身高必录、跨视角一致性、辨证解码）──
        from ppg_to_wuxing_bridge import PpgToWuxingBridge

        fs = 125.0
        raw_arr = np.array(raw_wave, dtype=np.float64)

        # 判断是否已归一化（前端 fallback）：范围在 [-1.5, 1.5]
        if raw_arr.max() < 2.0 and raw_arr.min() > -2.0:
            logger.info(f"[ppg] 检测到归一化输入，bridge 会跳过 preprocess")

        bridge = PpgToWuxingBridge(fs=fs, patient_height_m=(current.height / 100.0) if current.height else None)
        bridge_result = bridge.pipeline(raw_arr, return_raw=False)

        if 'error' in bridge_result:
            ob.status = "failed"; ob.syndrome_hint = f"波形处理失败: {bridge_result['error']}"
            db.commit()
            raise HTTPException(status_code=422, detail=bridge_result['error'])

        six_q = bridge_result['six_qualities']
        delta_f_list = bridge_result['delta_F']       # list[5] ∈ [-1, 1]
        hr_bpm = bridge_result.get('hr_bpm', 0)
        sqi = bridge_result.get('sqi', 0)

        # 跨视角一致性警告（诚实报告，不隐藏）
        if bridge_result.get('view_disagreement'):
            logger.warning(f"[ppg] 硬度跨视角不一致 {bridge_result.get('hardness_views')}")

        # ── Step 3: 组装五形向量（delta_f ∈ [-1,1] → v_obs ∈ [0,100]）──
        LABELS = ["wood", "fire", "earth", "metal", "water"]
        v_obs = {lab: float(50 + 50 * delta_f_list[i]) for i, lab in enumerate(LABELS)}
        delta_f_dict = {lab: float(delta_f_list[i]) for i, lab in enumerate(LABELS)}

        # 写回 Observation
        ob.v_obs = v_obs; ob.delta_f = delta_f_dict
        ob.sqi = sqi if body.sqi is None else body.sqi   # bridge 计算的 SQI 更准
        ob.status = "analyzed"
        # bridge 返回的辨证结果（如果引擎没返回就用这个）
        bridge_summary = bridge_result.get('summary', '')
        bridge_pathos = []
        sm = bridge_result.get('syndrome_main') or {}
        if sm.get('证型'): bridge_pathos.append(sm['证型'])
        for sub in bridge_result.get('syndrome_sub', []):
            if sub.get('证型'): bridge_pathos.append(sub['证型'])
        ob.syndrome_hint = bridge_summary
        db.commit()

        logger.info(f"[ppg] bridge 分析完成: HR={hr_bpm:.1f} ΔF={[round(v,3) for v in delta_f_list]}")

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"[ppg] 波形处理管线失败: {exc}")
        ob.status = "failed"; ob.syndrome_hint = f"波形处理失败: {exc}"
        db.commit()
        raise HTTPException(status_code=500, detail=f"波形处理失败: {exc}")

    # ── Step 4: 调青檬引擎做拓扑诊断 ──
    qingnang_id = current.qingnang_id or f"user_{current.id}"
    engine_result = None
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                f"{settings.QINGMENG_URL}/v1/reasoning/ppg",
                json={
                    "user_id": qingnang_id,
                    "v_obs": v_obs,
                    "sqi": ob.sqi,           # bridge 计算的 SQI（更准）
                    "delta_f": delta_f_dict,
                    "v_innate": case.v_innate,
                    "patient_height_m": current.height / 100.0 if current.height else None,
                },
            )
            if resp.status_code == 200:
                engine_result = resp.json()
                ob.s_graph = engine_result.get("S_graph")
                # 引擎有病理标签用引擎的，否则用 bridge 的（主证+兼证）
                ob.pathologies = engine_result.get("pathologies") or bridge_pathos
                ob.diagnosis_summary = engine_result.get("summary", "")
                # 引擎没 summary 但 bridge 有 → fallback
                if not ob.diagnosis_summary:
                    ob.diagnosis_summary = bridge_summary
                ob.syndrome_hint = ob.diagnosis_summary or bridge_summary
                logger.info(f"[ppg] 引擎诊断完成: {ob.diagnosis_summary}, 病理={ob.pathologies}")
            else:
                logger.warning(f"[ppg] 引擎返回 {resp.status_code}: {resp.text[:200]}")
                # 引擎失败 → bridge pathos + summary 兜底
                ob.pathologies = bridge_pathos
    except Exception as exc:
        logger.warning(f"[ppg] 引擎调用失败: {exc} — 波形分析仍可返回")
        # 引擎失败 → bridge pathos + summary 兜底
        ob.pathologies = bridge_pathos

    if not ob.diagnosis_summary:
        ob.diagnosis_summary = bridge_summary
    ob.status = "analyzed"; db.commit()

    # ── Step 5: 更新 case.v_current（引擎结果或 v_obs fallback）──
    case.v_current = ob.s_graph or v_obs; db.commit()

    # ── Step 6: 返回完整报告 ──
    return {
        "id": ob.id, "observation_id": ob.id, "case_id": case.id,
        "status": ob.status, "sqi": ob.sqi,
        "v_obs": ob.v_obs, "delta_f": ob.delta_f,
        "s_graph": ob.s_graph, "pathologies": ob.pathologies,
        "diagnosis_summary": ob.diagnosis_summary or ob.syndrome_hint,
        "engine_result": engine_result,
    }


@router.get("/observations/{obs_id}")
def get_observation(obs_id: int, db: Session = Depends(get_db),
                    current: User = Depends(get_current_user)):
    """前端轮询：获取某次 PPG 观测的完整状态（含引擎诊断结果）。"""
    ob = db.query(Observation).filter(Observation.id == obs_id).first()
    if not ob or ob.case.user_id != current.id:
        raise HTTPException(status_code=404, detail="观测记录不存在")
    return {
        "id": ob.id, "status": ob.status, "sqi": ob.sqi,
        "v_obs": ob.v_obs, "delta_f": ob.delta_f,
        "s_graph": ob.s_graph, "pathologies": ob.pathologies,
        "diagnosis_summary": ob.diagnosis_summary,
        "syndrome_hint": ob.syndrome_hint,
        "observed_at": ob.observed_at.isoformat() if ob.observed_at else None,
    }


@router.get("/history")
def ppg_history(limit: int = 20, db: Session = Depends(get_db),
                current: User = Depends(get_current_user)):
    """获取 PPG 观测历史"""
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if not case:
        return []

    obs_list = db.query(Observation).filter(
        Observation.case_id == case.id
    ).order_by(Observation.observed_at.desc()).limit(limit).all()

    return [
        {
            "id": o.id,
            "sqi": o.sqi,
            "delta_f": o.delta_f,
            "v_obs": o.v_obs,
            "syndrome_hint": o.syndrome_hint,
            "patient_height_m": o.patient_height_m,
            "observed_at": o.observed_at.isoformat(),
        }
        for o in obs_list
    ]


# ═══════════════════════════════════════════════════════
# 硬件检测：复用 ppg_acquisition.py 的 selfcheck_hardware
# ═══════════════════════════════════════════════════════
@router.get("/hardware-status")
def hardware_status():
    """检测 PPG 硬件状态（串口枚举 + 连接测试 + 嗅探）。

    与 /stream 共享 _hw_lock 串行化，避免 Windows 串口独占冲突：
    - 若当前已有活跃数据流（预览/采集），直接返回流状态，不再开串口自检
    - 否则在锁内执行 selfcheck_hardware()
    """
    try:
        from ppg_acquisition import selfcheck_hardware, format_selftest

        with _hw_lock:
            active = _hw_streamer is not None and getattr(_hw_streamer, "_running", False)
            if active:
                st = _hw_streamer
                return {
                    "ok": True,
                    "verdict": "STREAMING",
                    "port_count": 1,
                    "ports": [{"device": st.port, "desc": f"数据流活跃中（{st.tag}）"}],
                    "default_port": st.port,
                    "connect_ok": True,
                    "stream_ok": True,
                    "stream_rate": getattr(st, "current_rate", 0) or 0,
                    "stream_mode": "cheez" if getattr(st, "tag", "") == "CheezPPG" else "adc",
                    "report": [f"[OK] 数据流活跃中（{st.port} · {st._total} 样本）"],
                }

            check = selfcheck_hardware()

        return {
            "ok": check.get("verdict") != "FAIL",
            "verdict": check.get("verdict"),
            "port_count": check.get("port_count", 0),
            "ports": check.get("ports", []),
            "default_port": check.get("default_port"),
            "connect_ok": check.get("connect", {}).get("ok", False),
            "stream_ok": check.get("stream", {}).get("had_data", False),
            "stream_rate": check.get("stream", {}).get("rate_hz", 0),
            "stream_mode": check.get("stream", {}).get("mode", "none"),
            "report": check.get("lines", []),
        }
    except ImportError:
        return {
            "ok": False,
            "verdict": "NO_BRIDGE",
            "error": "ppg_acquisition.py 未找到（硬件桥目录未加入 sys.path）",
            "bridge_path": str(_HW_COLLECT_DIR),
        }
    except Exception as exc:
        return {"ok": False, "verdict": "ERROR", "error": str(exc)}


# ═══════════════════════════════════════════════════════
# SSE 实时 PPG 流：Python 读串口 → 推给浏览器
# ═══════════════════════════════════════════════════════
@router.get("/stream")
def ppg_sse_stream(
    duration: float = 20.0,
    port: str | None = None,
    baud: int = 115200,
    preview: int = 0,
):
    """
    开启 PPG 硬件 SSE 实时流。

    流程：
      1. 锁内打开串口（自动检测默认端口 + 嗅探固件，串行化防独占冲突）
      2. 嗅探固件 → CheezPPG 6ch / Pulsesensor 1ch
      3. 实时推送 SSE 事件：{wave, hr?, hrv?, mode, sample}
      4. duration 秒后自动结束（preview=1 时无限推流，仅预览），
         或客户端断开 / 前端调 /disconnect 主动停止
    """
    try:
        from ppg_acquisition import (
            CheezPPGStreamer, PPGStreamer,
            resolve_port, detect_format,
        )
    except ImportError:
        def _err():
            yield f"data: {json.dumps({'error': 'ppg_acquisition.py 未找到'})}\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream")

    def _gen():
        global _hw_streamer
        streamer = None
        try:
            # ── 打开串口阶段：锁内串行，避免 Windows 串口独占冲突 ──
            with _hw_lock:
                # 若已有活跃流（预览/采集），先停旧流再开新流，保证单流
                if _hw_streamer is not None:
                    _hw_streamer.stop()
                    _hw_streamer = None

                resolved_port = port or resolve_port()
                if not resolved_port:
                    yield f"data: {json.dumps({'error': '未检测到串口'})}\n\n"
                    return

                fmt = detect_format(resolved_port, baud)
                is_cheez = fmt["mode"] == "cheez"
                Cls = CheezPPGStreamer if is_cheez else PPGStreamer

                streamer = Cls(port=resolved_port, baud=baud)
                if not streamer.connect():
                    yield f"data: {json.dumps({'error': f'连接 {resolved_port} 失败'})}\n\n"
                    return

                # 开启采集（preview 无限 / record 由 deadline 控制停止）
                streamer.start(duration=None)
                _hw_streamer = streamer
                handshake = {
                    "type": "init",
                    "port": resolved_port,
                    "baud": baud,
                    "mode": fmt["mode"],
                    "fs": fmt["fs"],
                    "channels": streamer.channel_names,
                }

            # ── 握手帧：告诉前端固件模式 + 采样率（锁外推送）──
            yield f"data: {json.dumps(handshake)}\n\n"

            # ── 推流循环（锁外：/disconnect 可获取锁主动停止流）──
            deadline = None if preview else time.time() + duration
            last_send = 0
            # 归一化滑动窗口：2 秒内的 filtered 值做 min-max → [-1, 1]
            # 前端只画归一化后的 wave，幅值模型统一
            norm_window = []   # [(timestamp, value), ...]
            NORM_WINDOW_SEC = 2.0

            # collect 模式（preview=0）缓存完整 raw filtered 波形，供 upload handler 做分析
            collect_raw_buf: list[float] = [] if not preview else None

            while streamer._running:
                # 每 16ms 推一帧 ≈ 60fps（与浏览器 rAF 合帧后不丢数据）
                now = time.time()
                if deadline is not None and now >= deadline:
                    break
                if now - last_send < 0.016:
                    time.sleep(0.003)
                    continue
                last_send = now

                # 取最新样本
                latest = streamer._latest
                if is_cheez:
                    raw_filtered = latest.get("filtered", 0)
                    # collect 模式：缓存完整 raw filtered（每个样本只来一次，不会重复）
                    if collect_raw_buf is not None:
                        collect_raw_buf.append(raw_filtered)
                    # 归一化：维护滑动窗口 + 动态 min-max
                    norm_window.append((now, raw_filtered))
                    # 清理过期
                    cutoff = now - NORM_WINDOW_SEC
                    while norm_window and norm_window[0][0] < cutoff:
                        norm_window.pop(0)
                    if len(norm_window) >= 8:   # 至少 8 个样本才归一，避免起步抖动
                        vals = [v for _, v in norm_window]
                        vmin, vmax = min(vals), max(vals)
                        if vmax - vmin > 1e-6:
                            wave_norm = 2.0 * (raw_filtered - vmin) / (vmax - vmin) - 1.0
                        else:
                            wave_norm = 0.0
                    else:
                        wave_norm = 0.0     # 窗口不够时给 0，等积累
                    evt = {
                        "type": "data",
                        "wave": round(wave_norm, 4),   # [-1, 1]
                        "hr": latest.get("HR"),
                        "hrv": latest.get("HRV"),
                        "peak": latest.get("peak"),
                        "sample": streamer._total,
                    }
                else:
                    # Pulsesensor: adc 通道（若流内带 HR/HRV 也透传，供前端显示）
                    evt = {
                        "type": "data",
                        "wave": latest.get("adc", 0),
                        "sample": streamer._total,
                    }
                    if latest.get("HR") is not None:
                        evt["hr"] = latest["HR"]
                    if latest.get("HRV") is not None:
                        evt["hrv"] = latest["HRV"]

                yield f"data: {json.dumps(evt)}\n\n"

        finally:
            # collect 模式：把完整 raw filtered 波形缓存到全局变量，供 upload handler 读取
            global _last_collect_raw_wave
            if not preview and collect_raw_buf is not None and len(collect_raw_buf) >= 100:
                _last_collect_raw_wave = collect_raw_buf
                logger.info(f"[ppg] collect 缓存 raw filtered: {len(collect_raw_buf)} 样本")
            # 停止流并注销全局单例（幂等：disconnect 端点可能已停）
            if streamer is not None:
                streamer.stop()
                with _hw_lock:
                    if _hw_streamer is streamer:
                        _hw_streamer = None
            if not preview:
                yield f"data: {json.dumps({'type': 'done', 'total': streamer._total if streamer else 0})}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.post("/disconnect")
def ppg_disconnect():
    """主动停止当前采集/预览流，释放串口（前端点「断开」时调用）。

    用户可安全拔线的依据：COM3 被 _hw_streamer.stop() 释放后，
    后端不再持有串口句柄。
    """
    global _hw_streamer
    with _hw_lock:
        if _hw_streamer is not None:
            _hw_streamer.stop()
            _hw_streamer = None
            return {"ok": True, "released": True}
        return {"ok": True, "released": False}
