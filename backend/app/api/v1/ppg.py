"""ppg - PPG 采集上传 + 查询 + 硬件 SSE 桥接"""
import json
import sys
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import User, Case, Observation
from ..deps import get_current_user

router = APIRouter()


# ═══════════════════════════════════════════════════════
# 硬件桥：复用 qingnang/青囊/脉诊/采集 的 CheezPPGStreamer
# ═══════════════════════════════════════════════════════
# ──────────────────────────────────────────────────────
# 硬件桥：复用 qingnang/青囊/脉诊/采集 的采集脚本
# 两个目录是兄弟：e:\工作\qingnang-APP  和  e:\工作\qingnang
# ──────────────────────────────────────────────────────
_root = Path(__file__).resolve().parents[4]   # qingnang-APP
_HW_COLLECT_DIR = _root.parent / "qingnang" / "青囊" / "脉诊" / "采集"
if str(_HW_COLLECT_DIR) not in sys.path and _HW_COLLECT_DIR.exists():
    sys.path.insert(0, str(_HW_COLLECT_DIR))

# 全局单例：避免每次请求都重新开串口（Windows 串口独占）
_hw_streamer = None
_hw_lock = __import__("threading").Lock()


class PpgUpload(BaseModel):
    sqi: float = Field(..., ge=0, le=100)
    delta_f: dict
    v_obs: dict
    ppg_wave: list | None = None
    syndrome_hint: str | None = None


@router.post("/upload")
def upload_ppg(body: PpgUpload, db: Session = Depends(get_db),
               current: User = Depends(get_current_user)):
    """上传一次 PPG 观测"""
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="请先完成初始化建档")

    ob = Observation(
        case_id=case.id,
        source="cheezPPG",
        sqi=body.sqi,
        delta_f=body.delta_f,
        v_obs=body.v_obs,
        ppg_wave=body.ppg_wave,
        syndrome_hint=body.syndrome_hint,
    )
    db.add(ob)

    # 更新 case 的 v_current
    case.v_current = body.v_obs

    db.commit()
    db.refresh(ob)

    return {"observation_id": ob.id, "case_id": case.id, "sqi": ob.sqi}


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
            while streamer._running:
                # 每 33ms 推一帧 ≈ 30fps（前端平滑度足够）
                now = time.time()
                if deadline is not None and now >= deadline:
                    break
                if now - last_send < 0.033:
                    time.sleep(0.005)
                    continue
                last_send = now

                # 取最新样本
                latest = streamer._latest
                if is_cheez:
                    # CheezPPG: filtered 通道做示波
                    evt = {
                        "type": "data",
                        "wave": latest.get("filtered", 0),
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
