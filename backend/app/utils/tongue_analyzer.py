"""tongue_analyzer — SPUM 舌诊分析（望诊补充）

参考青囊agent.md §5.2.3 望舌苔 + spum_face_reader.py 颜色分析模式。
核心：HSV 颜色阈值分割舌体 → RGB 特征提取 → SPUM 舌象规则映射。

SPUM 舌象映射规则（agent.md L707-710）：
  舌淡胖有齿痕  → S_火 ↓ + S_土 ↓（火不生土）
  舌红少苔     → S_火 ↑ + S_土 ↓↓（火旺灼土——阴液枯竭）
  舌紫暗有瘀斑  → S_水 ↓ + S_金失衡（水形停滞+金形桥边切换异常）
  舌苔白腻     → S_水 ↑异常（水形链上异常节点团附着——痰湿）
  舌淡白       → S_火 ↓ + S_土 ↓ + S_金 ↓（气血不足）
  舌红绛       → S_火 ↑↑ + S_水 ↓↓（热极伤阴）
"""
from __future__ import annotations
import numpy as np


# ═══════════════════════════════════════════════════════
# HSV 颜色阈值（舌体分割）
# ═══════════════════════════════════════════════════════

# 舌体红粉色 HSV 范围（OpenCV: H 0-180, S 0-255, V 0-255）
# 舌体主色：淡红/粉红 → Hue 大约 0-20（红粉区域）
TONGUE_HSV_LOWER = np.array([0, 30, 40])
TONGUE_HSV_UPPER = np.array([20, 255, 255])

# 舌苔白腻（白/微黄）— 低饱和度，高亮度
COATING_WHITE_HSV_LOWER = np.array([0, 0, 120])
COATING_WHITE_HSV_UPPER = np.array([40, 80, 255])

# 舌苔黄腻（黄/黄褐色）
COATING_YELLOW_HSV_LOWER = np.array([15, 60, 100])
COATING_YELLOW_HSV_UPPER = np.array([35, 255, 255])

# 舌紫暗/瘀斑（暗红发紫 — Hue 向紫移，偏暗）
PURPLE_HSV_LOWER = np.array([130, 30, 40])
PURPLE_HSV_UPPER = np.array([180, 255, 200])


def analyze_tongue(image_path: str) -> dict:
    """分析舌象图片，返回结构化舌诊结果

    返回 dict:
      bgr_stats:     整体 BGR 均值
      tongue_mask:   分割出的舌体像素比例
      coating_ratio: 舌苔覆盖比例（白+黄腻像素 / 舌体像素）
      purple_ratio:  紫暗/瘀斑比例
      spum_mapping:  SPUM 舌象判定 + S 向量修正
      confidence:    high / medium / low
      warnings:      警告（没检测到舌体等）
    """
    import cv2

    # 1. 加载 + 预处理
    img = cv2.imread(image_path)
    if img is None:
        return {"error": "无法读取图片", "confidence": "low", "warnings": ["图片格式不支持或损坏"]}

    h, w = img.shape[:2]

    # 2. HSV 转换
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 3. 舌体分割
    tongue_mask = cv2.inRange(hsv, TONGUE_HSV_LOWER, TONGUE_HSV_UPPER)
    # 形态学：闭运算填洞 + 开运算去噪
    kernel = np.ones((15, 15), np.uint8)
    tongue_mask = cv2.morphologyEx(tongue_mask, cv2.MORPH_CLOSE, kernel)
    tongue_mask = cv2.morphologyEx(tongue_mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))

    tongue_pixels = int(np.sum(tongue_mask > 0))
    total_pixels = h * w
    tongue_ratio = tongue_pixels / total_pixels if total_pixels > 0 else 0

    # 置信度：检测到的舌体面积比例
    confidence = "low"
    if tongue_ratio > 0.05:
        confidence = "medium"
    if tongue_ratio > 0.15:
        confidence = "high"

    warnings = []
    if tongue_ratio < 0.03:
        warnings.append(f"舌体检测面积过小（{tongue_ratio*100:.1f}%），请正对舌头拍摄")

    # 4. 在舌体 mask 区域内分析颜色特征
    tongue_pixels_all = img[tongue_mask > 0]
    if len(tongue_pixels_all) == 0:
        return {
            "error": "未检测到舌体",
            "confidence": "low",
            "warnings": ["请确保舌头正对镜头、光线充足"],
            "spum_mapping": {"tongue_type": "unknown", "s_vector": {}},
            "bgr_stats": {},
            "tongue_ratio": round(tongue_ratio, 3),
        }

    bgr_mean = tongue_pixels_all.mean(axis=0)
    b, g, r = float(bgr_mean[0]), float(bgr_mean[1]), float(bgr_mean[2])

    # 5. 舌苔比例（在舌体 mask 内找舌苔像素）
    tongue_hsv = hsv.copy()
    tongue_hsv[tongue_mask == 0] = 0

    white_mask = cv2.inRange(tongue_hsv, COATING_WHITE_HSV_LOWER, COATING_WHITE_HSV_UPPER)
    yellow_mask = cv2.inRange(tongue_hsv, COATING_YELLOW_HSV_LOWER, COATING_YELLOW_HSV_UPPER)
    purple_mask = cv2.inRange(tongue_hsv, PURPLE_HSV_LOWER, PURPLE_HSV_UPPER)

    white_pct = float(np.sum(white_mask[tongue_mask > 0] > 0)) / tongue_pixels if tongue_pixels > 0 else 0
    yellow_pct = float(np.sum(yellow_mask[tongue_mask > 0] > 0)) / tongue_pixels if tongue_pixels > 0 else 0
    purple_pct = float(np.sum(purple_mask[tongue_mask > 0] > 0)) / tongue_pixels if tongue_pixels > 0 else 0
    coating_ratio = white_pct + yellow_pct

    # 6. SPUM 舌象判定（agent.md L707-710）
    spum_mapping = _classify_tongue(b, g, r, white_pct, yellow_pct, purple_pct)

    return {
        "confidence": confidence,
        "warnings": warnings,
        "image_size": {"h": h, "w": w},
        "tongue_ratio": round(tongue_ratio, 3),
        "bgr_mean": {"B": round(b, 1), "G": round(g, 1), "R": round(r, 1)},
        "coating": {
            "white_pct": round(white_pct * 100, 1),
            "yellow_pct": round(yellow_pct * 100, 1),
            "total_coating_pct": round(coating_ratio * 100, 1),
            "purple_pct": round(purple_pct * 100, 1),
        },
        "spum_mapping": spum_mapping,
        "algorithm": "SPUM-tongue-1.0",
    }


def _classify_tongue(b: float, g: float, r: float,
                     white_pct: float, yellow_pct: float, purple_pct: float) -> dict:
    """基于颜色特征 + 舌苔比例判定舌象，映射到 SPUM S 向量修正

    核心判定逻辑（基于 agent.md §5.2.3）：
      1. 先看主色（R 值 → 舌质淡/红/绛）
      2. 再看舌苔覆盖比例（无苔/薄苔/厚腻）
      3. 特殊：紫色 → 瘀血 → S_水 ↓ + S_金失衡
    """
    s_vector = {}
    tongue_type = []
    rationale = []

    # ── 主色判定 ──
    # OpenCV BGR: R 在索引 2
    # 正常舌红（健康舌）: R ≈ G + 20, 整体中等亮度
    brightness = (b + g + r) / 3
    red_dominance = r - max(b, g)  # 红色主导程度

    # 舌紫暗：紫色区域多 OR R 和 B 都偏高（红蓝混合 = 紫）
    if purple_pct > 0.05 or (r > g and b > g and purple_pct > 0.01):
        tongue_type.append("紫暗")
        s_vector = {"水": "↓", "金": "失衡"}
        rationale.append(f"舌紫暗 {purple_pct*100:.1f}% → S_水↓ + S_金失衡")

    # 舌红绛：红色主导非常明显 + 亮度高
    elif red_dominance > 60 and r > 180:
        tongue_type.append("红绛")
        s_vector = {"火": "↑↑", "水": "↓↓"}
        rationale.append(f"舌红绛 R={r:.0f} → S_火↑↑ + S_水↓↓")

    # 舌红：红色明显但不过
    elif red_dominance > 30 and r > 140:
        tongue_type.append("红")
        if coating_ratio < 0.10:
            # 舌红少苔 → S_火↑ + S_土↓↓（火旺灼土）
            tongue_type.append("少苔")
            s_vector = {"火": "↑", "土": "↓↓"}
            rationale.append(f"舌红少苔 → 火旺灼土")
        else:
            s_vector = {"火": "↑"}
            rationale.append("舌红 → S_火↑")

    # 舌淡白：整体亮度低 + 红色主导弱
    elif brightness < 120 and red_dominance < 20:
        tongue_type.append("淡白")
        s_vector = {"火": "↓", "土": "↓", "金": "↓"}
        rationale.append(f"舌淡白 brightness={brightness:.0f} → 气血不足")

    # 舌淡胖：亮度中等 + 舌苔偏厚（胖 = 水湿停聚）
    elif coating_ratio > 0.40 and red_dominance < 35:
        tongue_type.append("淡胖有齿痕?")
        s_vector = {"火": "↓", "土": "↓"}
        rationale.append(f"舌淡胖 + 舌苔厚 → 火不生土")

    # 正常舌：红粉色 + 薄苔
    else:
        tongue_type.append("淡红（正常）")
        s_vector = {}
        rationale.append("舌象接近正常淡红")

    # ── 舌苔覆盖补充 ──
    if white_pct > 0.30:
        # 舌苔白腻（agent.md: S_水↑异常 — 痰湿）
        tongue_type.append("白腻苔")
        if "水" in s_vector:
            s_vector["水"] = "↑异常" if s_vector["水"] != "↓" else "↑异常(矛盾)"
        else:
            s_vector["水"] = "↑异常"
        rationale.append(f"舌苔白腻 {white_pct*100:.0f}% → 痰湿 S_水↑异常")

    if yellow_pct > 0.20:
        tongue_type.append("黄腻苔")
        s_vector["火"] = s_vector.get("火", "") + "↑"
        rationale.append(f"舌苔黄腻 → 火湿交蒸")

    # 无苔或少苔 → 阴液枯竭信号
    if coating_ratio < 0.05 and red_dominance > 30:
        tongue_type.append("少苔/无苔")
        if "土" not in s_vector:
            s_vector["土"] = "↓"

    return {
        "tongue_type": "/".join(tongue_type) if tongue_type else "unknown",
        "s_vector": s_vector,
        "rationale": rationale,
        "brightness": round(brightness, 1),
        "red_dominance": round(red_dominance, 1),
    }


def format_report(result: dict) -> str:
    """把 analyze_tongue 结果格式化为可读报告"""
    if "error" in result:
        return f"❌ 舌诊分析失败: {result['error']}"

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "舌诊分析报告（SPUM）",
        f"舌体占比: {result['tongue_ratio']*100:.1f}% | 置信度: {result['confidence']}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "【舌象特征】",
        f"- 主色 BGR: B={result['bgr_mean']['B']} G={result['bgr_mean']['G']} R={result['bgr_mean']['R']}",
        f"- 舌苔覆盖: 白{result['coating']['white_pct']}% 黄{result['coating']['yellow_pct']}% 总{result['coating']['total_coating_pct']}%",
        f"- 紫暗/瘀斑: {result['coating']['purple_pct']}%",
        "",
        "【SPUM 舌象判定】",
        f"  {result['spum_mapping']['tongue_type']}",
    ]
    if result["spum_mapping"]["rationale"]:
        lines.append("  依据：" + "; ".join(result["spum_mapping"]["rationale"]))

    lines += [
        "",
        "【S 向量修正】",
    ]
    sv = result["spum_mapping"]["s_vector"]
    if sv:
        for wx in ["木", "火", "土", "金", "水"]:
            if wx in sv:
                lines.append(f"  S_{wx}: {sv[wx]}")
    else:
        lines.append("  无显著修正（舌象接近正常）")

    if result.get("warnings"):
        lines += ["", "⚠️ 注意:"] + [f"  - {w}" for w in result["warnings"]]

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python tongue_analyzer.py <tongue_photo.jpg>")
        sys.exit(1)
    result = analyze_tongue(sys.argv[1])
    print(format_report(result))
