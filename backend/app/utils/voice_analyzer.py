"""voice_analyzer — 青囊闻诊（五音频谱分析）

实现 SPUM §4.6 音频数字信号分析协议：
  - 步骤 1: 音频解码（ffmpeg → 16kHz 单声道 wav）
  - 步骤 2: 基本声学特征（RMS / F0 / 光谱质心 / 过零率）
  - 步骤 3: 五音频段能量提取（宫商角徵羽频率带）
  - 步骤 4: 矛盾信号检测（虚阳外浮）
  - 步骤 5: S 向量闻诊判定
  - 步骤 6: 结构化输出

五音频率带（青囊agent.md §4.6.2）：
  宫(土)  130-260Hz   → S_土
  商(金)  260-390Hz   → S_金
  角(木)  390-520Hz   → S_木
  徵(火)  520-780Hz   → S_火
  羽(水)  780-1040Hz  → S_水
"""
from __future__ import annotations
import os, sys, tempfile, subprocess, json
from pathlib import Path

# librosa 是重依赖，延迟导入让无音频功能的模块也能正常启动
def _import_librosa():
    import librosa, numpy as np, soundfile as sf
    return librosa, np, sf


# ═══════════════════════════════════════════════════════
# 五音配置
# ═══════════════════════════════════════════════════════

WUYIN_BANDS = [
    # (五音名, 五行, 低频Hz, 高频Hz)
    ("宫", "土", 130, 260),
    ("商", "金", 260, 390),
    ("角", "木", 390, 520),
    ("徵", "火", 520, 780),
    ("羽", "水", 780, 1040),
]

WUYIN_TO_WUXING = {"宫": "土", "商": "金", "角": "木", "徵": "火", "羽": "水"}
WUXING_TO_WUYIN = {v: k for k, v in WUYIN_TO_WUXING.items()}

# 矛盾信号检测阈值（青囊agent.md §4.6.2）
VIRTUAL_YANG_FLOAT_THRESHOLD = 28.0   # 徵(火) 能量占比 %
VIRTUAL_YANG_FLOAT_RMS = 0.02         # RMS 能量


# ═══════════════════════════════════════════════════════
# 公开 API
# ═══════════════════════════════════════════════════════

def analyze_voice(audio_path: str) -> dict:
    """分析一段语音，返回结构化闻诊结果

    返回 dict:
      basic:        {duration, sample_rate, rms_mean, f0_median, centroid, voiced_ratio}
      wuyin:        {"宫": {"hz":(130,260), "energy_pct":35.2, "deviation":+76.0, "arrow":"↑↑"}, ...}
      virtual_yang: {"detected": bool, "fire_pct": float, "rms": float, "confidence": "high|low"}
      s_vector:     {"wood":"", "fire":"", "earth":"", "metal":"", "water":""}  // 闻诊修正方向
      confidence:   "high" | "medium" | "low"
      warnings:     [str, ...]  // 信噪比/时长不足等提示
    """
    warnings: list[str] = []
    librosa, np, sf = _import_librosa()

    # ── 步骤 1: 解码 ──
    tmp_wav = None
    try:
        # 尝试用 imageio-ffmpeg 自带 ffmpeg
        ffmpeg = None
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            ffmpeg = get_ffmpeg_exe()
        except Exception:
            # 兜底：系统 ffmpeg
            ffmpeg = "ffmpeg"

        tmp_wav = os.path.join(tempfile.gettempdir(), f"spum_wenzhen_{os.getpid()}_{abs(hash(audio_path))}.wav")
        result = subprocess.run(
            [ffmpeg, "-i", audio_path, "-ar", "16000", "-ac", "1", "-f", "wav", "-y", tmp_wav],
            capture_output=True, timeout=30,
        )
        if result.returncode != 0 or not os.path.exists(tmp_wav):
            return {"error": f"ffmpeg decode failed: {result.stderr.decode(errors='ignore')[:200]}"}

        y, sr = sf.read(tmp_wav)
        if len(y.shape) > 1:
            y = y[:, 0]  # 取单声道
    finally:
        if tmp_wav and os.path.exists(tmp_wav):
            try: os.remove(tmp_wav)
            except Exception: pass

    duration = len(y) / sr

    # 时长检查
    if duration < 3:
        warnings.append(f"录音过短（{duration:.1f}s < 3s），结果仅供参考")
    if duration < 15:
        warnings.append("录音 < 15s，五音分析精度下降")

    # ── 步骤 2: 基本特征 ──
    rms = float(np.mean(librosa.feature.rms(y=y)[0]))

    f0, voiced, _ = librosa.pyin(y, fmin=65, fmax=1040, sr=sr)
    voiced_mask = ~np.isnan(f0)
    f0_median = float(np.nanmedian(f0[voiced_mask])) if np.any(voiced_mask) else 0.0
    voiced_ratio = float(np.mean(voiced_mask))

    centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)[0]))

    # SNR 粗估：RMS 极低（< 0.005）且有声段极少 → 信噪比不足
    if rms < 0.005 and voiced_ratio < 0.1:
        warnings.append("信噪比不足，可能是纯环境噪声，结果仅供参考")

    basic = {
        "duration_sec": round(duration, 1),
        "sample_rate": sr,
        "rms_mean": round(rms, 4),
        "rms_judgement": _rms_label(rms),
        "f0_median_hz": round(f0_median, 1),
        "f0_judgement": _f0_label(f0_median),
        "centroid_hz": round(centroid, 1),
        "centroid_judgement": _centroid_label(centroid),
        "voiced_ratio_pct": round(voiced_ratio * 100, 1),
    }

    # ── 步骤 3: 五音频段 ──
    D = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)

    # 只在 130-1040Hz 范围内归一化
    mask_total = (freqs >= 130) & (freqs < 1040)
    total_energy = float(np.sum(D[mask_total]))

    if total_energy < 1e-10:
        return {"error": "音频能量过低，无法做五音分析", "basic": basic}

    wuyin_result = {}
    max_deviation = 0.0
    for name, wuxing, lo, hi in WUYIN_BANDS:
        mask = (freqs >= lo) & (freqs < hi)
        energy = float(np.sum(D[mask]))
        pct = energy / total_energy * 100.0
        deviation = (pct / 100.0 - 0.20) / 0.20 * 100.0   # 相对于基准 20% 的偏差 %
        arrow = _deviation_arrow(deviation)
        wuyin_result[name] = {
            "wuxing": wuxing,
            "hz_range": [lo, hi],
            "energy_pct": round(pct, 1),
            "deviation_pct": round(deviation, 1),
            "arrow": arrow,
        }
        max_deviation = max(max_deviation, abs(deviation))

    # ── 步骤 4: 矛盾信号（虚阳外浮） ──
    fire_pct = wuyin_result["徵"]["energy_pct"]
    virtual_yang = {
        "detected": False,
        "fire_pct": fire_pct,
        "rms": rms,
        "confidence": "low",
    }
    if fire_pct > VIRTUAL_YANG_FLOAT_THRESHOLD and rms < VIRTUAL_YANG_FLOAT_RMS:
        virtual_yang["detected"] = True
        virtual_yang["confidence"] = "high"
        virtual_yang["note"] = f"徵火{fire_pct:.1f}% + RMS{rms:.4f} → 浮越之火"
    elif fire_pct > 30.0:
        virtual_yang["detected"] = True
        virtual_yang["confidence"] = "low"
        virtual_yang["note"] = f"徵火{fire_pct:.1f}% > 30% 即使 RMS 不低，疑似虚阳外浮"

    # ── 步骤 5: S 向量闻诊判定 ──
    s_vector = {}
    for name, wuxing, lo, hi in WUYIN_BANDS:
        info = wuyin_result[name]
        arrow = info["arrow"]
        # 虚阳外浮：火强制 ↓↓↓
        if virtual_yang["detected"] and wuxing == "火":
            s_vector[wuxing] = "↓↓↓"
        else:
            s_vector[wuxing] = arrow

    # ── 步骤 6: 置信度 ──
    if warnings:
        confidence = "low"
    elif max_deviation > 30 or virtual_yang["detected"]:
        confidence = "medium"
    else:
        confidence = "high"

    return {
        "basic": basic,
        "wuyin": wuyin_result,
        "virtual_yang": virtual_yang,
        "s_vector": s_vector,
        "confidence": confidence,
        "warnings": warnings,
        "version": "1.0",
        "algorithm": "SPUM-§4.6",
    }


# ═══════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════

def _deviation_arrow(dev_pct: float) -> str:
    """偏差百分比 → 方向箭头

    > +15% → ↑↑    > +5% → ↑
    < -15% → ↓↓    < -5% → ↓
    else → ↔
    """
    if dev_pct > 15: return "↑↑"
    if dev_pct > 5:  return "↑"
    if dev_pct < -15: return "↓↓"
    if dev_pct < -5:  return "↓"
    return "↔"


def _rms_label(rms: float) -> str:
    if rms < 0.02: return "语声低微（S_火↓）"
    if rms < 0.05: return "中气偏弱（S_火偏↓）"
    if rms > 0.08: return "中气充足（S_火↔或↑）"
    return "正常"


def _f0_label(f0: float) -> str:
    if f0 == 0: return "未检出基频"
    if f0 < 190: return "音区偏低沉（羽水/宫土倾向）"
    if f0 < 220: return "音区适中（宫土/商金倾向）"
    return "音区偏高（角木/徵火倾向）"


def _centroid_label(c: float) -> str:
    if c < 800: return "音色偏暗沉（金/水型）"
    if c < 1200: return "音色适中（土型）"
    return "音色偏明亮（火/木型）"


def format_report(result: dict) -> str:
    """把 analyze_voice 结果格式化为可读报告"""
    if "error" in result:
        return f"❌ 分析失败: {result['error']}"

    b = result["basic"]
    wy = result["wuyin"]
    vy = result["virtual_yang"]
    sv = result["s_vector"]
    conf = result["confidence"]

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "闻诊音频分析报告",
        f"时长: {b['duration_sec']}s | 采样率: {b['sample_rate']}Hz | 置信度: {conf}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "【声学基础】",
        f"- 基频F0: {b['f0_median_hz']} Hz（{b['f0_judgement']}）",
        f"- RMS能量: {b['rms_mean']}（{b['rms_judgement']}）",
        f"- 光谱质心: {b['centroid_hz']} Hz（{b['centroid_judgement']}）",
        f"- 有声段比例: {b['voiced_ratio_pct']}%",
        "",
        "【五音能量分布】",
    ]
    for name in ["宫", "商", "角", "徵", "羽"]:
        w = wy[name]
        lines.append(f"  {name}({w['wuxing']}) {w['hz_range'][0]}-{w['hz_range'][1]}Hz: "
                     f"{w['energy_pct']}%  dev={w['deviation_pct']:+.1f}% {w['arrow']}")

    lines += [
        "",
        "【矛盾信号】",
        f"- 虚阳外浮: {'⚠️ 检测阳性' if vy['detected'] else '阴性'}",
    ]
    if vy["detected"]:
        lines.append(f"  {vy.get('note', '')}")

    lines += [
        "",
        "【闻诊S向量修正】",
    ]
    for wx in ["木", "火", "土", "金", "水"]:
        arrow = sv.get(wx, "?")
        lines.append(f"  S_{wx}: {arrow}")

    if result.get("warnings"):
        lines += ["", "⚠️ 注意:"] + [f"  - {w}" for w in result["warnings"]]

    return "\n".join(lines)


if __name__ == "__main__":
    # CLI 入口：python voice_analyzer.py <audio_path>
    if len(sys.argv) < 2:
        print("用法: python voice_analyzer.py <audio_path>")
        sys.exit(1)

    audio_path = sys.argv[1]
    if not os.path.exists(audio_path):
        print(f"文件不存在: {audio_path}")
        sys.exit(1)

    result = analyze_voice(audio_path)
    print(format_report(result))
    print()
    print("── JSON ──")
    print(json.dumps(result, ensure_ascii=False, indent=2))
