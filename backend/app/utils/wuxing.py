"""五形 / 时辰 / 飞星常量 + SPUM 工具函数

⚠️ 耦合建模纪律（纪律 C）：
  以下所有函数**输入会先经过 coupled_transform**，
  显式建模 spum-core.md §6.2 定义的火→水→土→木→金→火闭环耦合。
  临界阈值来自 §6.1 各形异常态（火衰/水断/土虚/木僵/金亢）定义。
  这是 L1 投影层的工程近似——库内未定义精确耦合微分方程。
"""
from __future__ import annotations
from typing import Literal

WUXING = Literal["wood", "fire", "earth", "metal", "water"]

# 五形中文名
WUXING_NAMES: dict[str, str] = {
    "wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"
}
WUXING_LIST = ["wood", "fire", "earth", "metal", "water"]

# 十二时辰（子=23-1, 丑=1-3, ...）
SHICHEN = [
    {"period": "zishi",   "range": "23-01", "elem": "water", "desc": "子时"},
    {"period": "choushi", "range": "01-03", "elem": "earth", "desc": "丑时"},
    {"period": "yinshi",  "range": "03-05", "elem": "wood",  "desc": "寅时"},
    {"period": "maoshi",  "range": "05-07", "elem": "wood",  "desc": "卯时"},
    {"period": "chenshi", "range": "07-09", "elem": "earth", "desc": "辰时"},
    {"period": "sishi",   "range": "09-11", "elem": "fire",  "desc": "巳时"},
    {"period": "wushi",   "range": "11-13", "elem": "fire",  "desc": "午时"},
    {"period": "weishi",  "range": "13-15", "elem": "earth", "desc": "未时"},
    {"period": "shenshi", "range": "15-17", "elem": "metal", "desc": "申时"},
    {"period": "youshi",  "range": "17-19", "elem": "metal", "desc": "酉时"},
    {"period": "xushi",   "range": "19-21", "elem": "earth", "desc": "戌时"},
    {"period": "haishi",  "range": "21-23", "elem": "water", "desc": "亥时"},
]

# 天干地支（简化 - 实际需要黄历库计算）
TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DIZHI   = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# ════════════════════════════════════════════════════════════════
# 五形耦合链条（spum-core.md:167-183）
#   火形梯度 → 水形链输送土形节点 → 土形储备填充 → 木形生长
#   → μ 临界触发 → 金形修剪 → 节点回归土形 + 火梯度再生
# ════════════════════════════════════════════════════════════════

# 默认临界阈值（来自 §6.1 各形异常态的文字描述，center=20 概率分布口径）
# 每个阈值标注其 §6.1 来源 — center=20 意味着：正常范围 ≈ 15~25
COUPLING_THRESHOLDS_DEFAULT = {
    "fire_floor":       15.0,   # 火衰临界：∇σ ≈ 0 → 梯度不驱动链条（§6.1 火异常态）
    "fire_threshold":   22.0,   # 火形驱动阈值：高于此值才显著驱动链条
    "water_floor":       8.0,   # 水断临界：关键边被剪 → L 骤增（§6.1 水异常态）
    "earth_reserve":    25.0,   # 土储充足：储备够才供木（§6.1 土异常态）
    "earth_deplete":    10.0,   # 土虚临界：储备枯竭（§6.1 土异常态）
    "wood_critical":    25.0,   # 木僵触发：μ 超临界 → 金形修剪激活（§6.1 木异常态）
    "metal_trim":        6.0,   # 金形修剪生效阈值
}

def _renormalize(s: dict[str, float]) -> dict[str, float]:
    """把向量重分配到总和≈100（center=20 概率分布口径）"""
    total = sum(max(v, 0) for v in s.values())
    if total <= 0:
        # 零向量 → 均匀分布
        return {w: 20.0 for w in WUXING_LIST}
    scale = 100.0 / total
    return {w: round(max(s.get(w, 0) * scale, 0), 2) for w in WUXING_LIST}


def coupled_transform(
    s: dict[str, float],
    thresholds: dict | None = None,
) -> dict[str, float]:
    """按耦合链条重分配五形向量（显式建模闭环耦合）

    这**不是**把 s 当五个独立数字处理，而是先判断链条上哪些转移被激活
    （基于 §6.1 的临界条件），再让各维约束性地变形。

    Args:
        s: 原始五形向量 {wood, fire, earth, metal, water}，center=20 口径
        thresholds: 自定义临界阈值（默认 COUPLING_THRESHOLDS_DEFAULT）

    Returns:
        经过耦合变换的向量，总和≈100
    """
    th = thresholds or COUPLING_THRESHOLDS_DEFAULT
    t = {w: float(s.get(w, 20)) for w in WUXING_LIST}

    # ── 火形驱动：火衰链条停，正常驱动链条但只在偏离 center 时才改动大 ──
    fire_strength = t['fire'] - 20  # 正 = 火旺, 负 = 火衰
    if t['fire'] < th['fire_floor']:
        # 火衰 → ∇σ ≈ 0 → 梯度不驱动 → 链条停 → 各维向 center 收敛
        for w in WUXING_LIST:
            t[w] = t[w] * 0.5 + 20 * 0.5    # 50% 回归 center
        return _renormalize(t)

    # ── 火→水 → 水→土：火形高于驱动阈值 + 水不断 → 土储备填充 ──
    if t['fire'] > th['fire_threshold'] and t['water'] > th['water_floor']:
        t['earth'] = min(50, t['earth'] * 1.15)

        # ── 土→木：储备充足才供木生长 ──
        if t['earth'] > th['earth_reserve'] and t['wood'] < th['wood_critical']:
            t['wood'] = min(45, t['wood'] * 1.10)

        # ── 木→金（关键转移）：μ ≥ 临界 → 木僵触发金形修剪 ──
        if t['wood'] >= th['wood_critical'] and t['metal'] > th['metal_trim']:
            t['metal'] = min(45, t['metal'] * 1.20)   # 金形加强
            t['wood']  = max(0, t['wood']  * 0.85)    # 木形被剪
            # ── 金→土 + 再生火：释放节点回归土 + σ 不均匀再生 ──
            t['earth'] = min(50, t['earth'] * 1.08)
            t['fire']  = min(45, t['fire']  * 1.05)

    # ── 土虚反向：土储备枯竭 → 木形失供 → 金形修剪减弱 ──
    if t['earth'] < th['earth_deplete']:
        t['wood']  = max(0, t['wood']  * 0.90)
        t['metal'] = max(0, t['metal'] * 0.95)

    return _renormalize(t)


def coupling_state(s: dict[str, float], thresholds: dict | None = None) -> list[str]:
    """描述耦合链条上哪些转移被激活（用于日志/解释）"""
    th = thresholds or COUPLING_THRESHOLDS_DEFAULT
    active = []

    if s['fire'] < th['fire_floor']:
        return ['⚠️ 火衰 → 链条停转']

    if s['fire'] > th['fire_threshold'] and s['water'] > th['water_floor']:
        active.append('fire→water→earth')
        if s['earth'] > th['earth_reserve'] and s['wood'] < th['wood_critical']:
            active.append('earth→wood')
        if s['wood'] >= th['wood_critical'] and s['metal'] > th['metal_trim']:
            active.append('⚠️ wood→metal (木僵触发修剪)')
            active.append('metal→earth+fire (再生)')

    if s['earth'] < th['earth_deplete']:
        active.append('⚠️ earth 土虚 → 木金减弱')

    return active or ['链条未激活（center 附近）']


# ════════════════════════════════════════════════════════════════
# 以下函数保持签名兼容，但**先对输入做 coupled_transform**
# 纪律 C：逐维独立运算前必须显式标注耦合假设
# ════════════════════════════════════════════════════════════════

def vector_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """两个五形向量的余弦相似度 0-1

    ⚠️ 纪律 C：先对 a,b 做 coupled_transform 再算余弦。
    原实现完全不建模耦合 — 这里保留接口不变，内部加耦合层。
    """
    import math
    ac = coupled_transform(a)
    bc = coupled_transform(b)
    dot = sum(ac.get(k, 0) * bc.get(k, 0) for k in WUXING_LIST)
    na = math.sqrt(sum(v*v for v in ac.values()))
    nb = math.sqrt(sum(v*v for v in bc.values()))
    if na == 0 or nb == 0: return 0.0
    return dot / (na * nb)

def vector_intersection(a: dict[str, float], b: dict[str, float],
                        threshold: float = 50) -> list[str]:
    """两个向量都偏弱（< threshold）的五形 - 共同弱项

    ⚠️ 纪律 C：先对 a,b 做 coupled_transform。
    """
    ac = coupled_transform(a)
    bc = coupled_transform(b)
    return [w for w in WUXING_LIST if ac.get(w, 100) < threshold and bc.get(w, 100) < threshold]

def vector_complement(a: dict[str, float], b: dict[str, float],
                      hi: float = 70, lo: float = 45) -> list[str]:
    """一个高（>hi）另一个低（<lo）的五形 - 互补

    ⚠️ 纪律 C：先对 a,b 做 coupled_transform。
    """
    ac = coupled_transform(a)
    bc = coupled_transform(b)
    result = []
    for w in WUXING_LIST:
        av, bv = ac.get(w, 50), bc.get(w, 50)
        if (av > hi and bv < lo) or (bv > hi and av < lo):
            result.append(w)
    return result
