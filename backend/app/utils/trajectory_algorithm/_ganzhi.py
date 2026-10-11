"""_ganzhi - 干支五行工具：天干地支映射 / 流年大运增量 / 平滑"""
from __future__ import annotations

from ._constants import TIANGAN_WUXING, DIZHI_CANGGAN, _GAN_CHARS, _ZHI_CHARS, DIMS

def ganzhi_to_elems(gan: str, zhi: str, wg: float = 0.3, wz: float = 0.7) -> dict:
    """干支 → 五行权重（藏干加权）"""
    w = {k: 0.0 for k in DIMS}
    w[TIANGAN_WUXING.get(gan, 'earth')] += wg
    cg = DIZHI_CANGGAN.get(zhi, {'earth': 1.0})
    for k, v in cg.items():
        w[k] += wz * v
    return w

def elems_to_delta(elems: dict, strength: float = 1.0) -> dict:
    """五行权重 → 生克传导后的净增益
    生: 木→火→土→金→水→木   克: 木→土→水→火→金→木"""
    base = {k: elems.get(k, 0) * strength for k in DIMS}
    deltas = dict(base)
    deltas['fire']  += 0.45 * base['wood']  - 0.35 * base['water']
    deltas['earth'] += 0.45 * base['fire']  - 0.35 * base['wood']
    deltas['metal'] += 0.45 * base['earth'] - 0.35 * base['fire']
    deltas['water'] += 0.45 * base['metal'] - 0.35 * base['earth']
    deltas['wood']  += 0.45 * base['water'] - 0.35 * base['metal']
    return deltas


# ═══════════════════════════════════════════════════════
# 8. 流年干支自动生成 + 平滑（从 tizhi-curve 沙盒合并）
#
# 公元年 → 干支：gan = (year-4)%10, zhi = (year-4)%12
# 消除硬编码大表，一次定义终身使用
# ═══════════════════════════════════════════════════════

_GAN_CHARS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
_ZHI_CHARS = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

def get_liunian(year: int) -> dict:
    """公元年 → {g: 天干, z: 地支} 公式生成（消除越界，消除硬编码表）"""
    g = _GAN_CHARS[(year - 4 + 1200) % 10]
    z = _ZHI_CHARS[(year - 4 + 1200) % 12]
    return {'g': g, 'z': z}


def liunian_delta(g: str, z: str) -> dict:
    """流年干支 → 五行增量（strength=6，单年扰动）"""
    return elems_to_delta(ganzhi_to_elems(g, z), 6)


def dayun_delta(gan: str, zhi: str, is_neutral: bool = False) -> dict:
    """大运干支 → 五行增量（strength=22，天时推力大）"""
    if is_neutral:
        return {k: 0.0 for k in DIMS}
    return elems_to_delta(ganzhi_to_elems(gan, zhi), 22)


def smooth3(arr5d: list) -> list:
    """3年居中滑动平均 — 消流年锯齿，保留整体趋势"""
    n = len(arr5d)
    out = [{k: 0.0 for k in DIMS} for _ in range(n)]
    for i in range(n):
        i0 = max(0, i - 1)
        i1 = min(n - 1, i + 1)
        for k in DIMS:
            v = arr5d[i][k] * 0.5 + arr5d[i0][k] * 0.25 + arr5d[i1][k] * 0.25
            out[i][k] = round(v * 100) / 100
    return out


def smooth5(arr5d: list) -> list:
    """5年居中滑动平均 — 流年扰动主要平滑器"""
    n = len(arr5d)
    out = [{k: 0.0 for k in DIMS} for _ in range(n)]
    for i in range(n):
        i0 = max(0, i - 2)
        i1 = max(0, i - 1)
        i3 = min(n - 1, i + 1)
        i4 = min(n - 1, i + 2)
        for k in DIMS:
            v = (arr5d[i][k] * 0.35
                 + arr5d[i1][k] * 0.25 + arr5d[i3][k] * 0.25
                 + arr5d[i0][k] * 0.075 + arr5d[i4][k] * 0.075)
            out[i][k] = round(v * 100) / 100
    return out


def ganzhi_main_elem(gan: str, zhi: str) -> str:
    """干支 → 主五行（大运 markArea 渲染辅助）"""
    cg = DIZHI_CANGGAN.get(zhi)
    if cg:
        max_w, main = 0, 'earth'
        for k, w in cg.items():
            if w > max_w:
                max_w, main = w, k
        return main
    return TIANGAN_WUXING.get(gan, 'earth')


# ═══════════════════════════════════════════════════════
# 6.5 节气层 · build_jieqi_view_v2
#
# 把 cases.py 里的静态节气五行表 + impact 计算统一到算法层
# SPUM 逐帧注入模型：
#   每年 = 大运(strength=22) + 流年(strength=6) + 24节气微调(strength≈1-2)
# ═══════════════════════════════════════════════════════

