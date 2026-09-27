"""五形 / 时辰 / 飞星常量 + SPUM 工具函数"""
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

def vector_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """两个五形向量的余弦相似度 0-1"""
    import math
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in WUXING_LIST)
    na = math.sqrt(sum(v*v for v in a.values()))
    nb = math.sqrt(sum(v*v for v in b.values()))
    if na == 0 or nb == 0: return 0.0
    return dot / (na * nb)

def vector_intersection(a: dict[str, float], b: dict[str, float],
                        threshold: float = 50) -> list[str]:
    """两个向量都偏弱（< threshold）的五形 - 共同弱项"""
    return [w for w in WUXING_LIST if a.get(w, 100) < threshold and b.get(w, 100) < threshold]

def vector_complement(a: dict[str, float], b: dict[str, float],
                      hi: float = 70, lo: float = 45) -> list[str]:
    """一个高（>hi）另一个低（<lo）的五形 - 互补"""
    result = []
    for w in WUXING_LIST:
        av, bv = a.get(w, 50), b.get(w, 50)
        if (av > hi and bv < lo) or (bv > hi and av < lo):
            result.append(w)
    return result
