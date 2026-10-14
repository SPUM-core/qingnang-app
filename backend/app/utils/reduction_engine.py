"""reduction_engine — 青囊归约算法库（活算子，非静态表）

核心理念：
  归约算法库的完备性不来自存量，来自能被持续修正的算子。
  任何存在事实若不可归约为关系才证伪 SPUM。
  开放边集 + 闭合算式 = 枚举做不到的事。

闭环形态：
  归约算法库（算）
    ↓ 读
  互联网边集（开放·无限） + 理论源头的四步与变量式（已形式化）
    ↓ 出
  ΔS 五维推演 → 事前预期 → 观察窗 → 回填 ✅/❌
    ↓ 收
  变量/权重修正 → 回算法库 ⟲

四层架构（对应归约算法库草案 v0.1）：
  L0 变量层：ΔS 基底表、五味→ΔS、四气→σ、乘数表（实体化）
  L1 归约算子：R1 取方 → R2 取 ΔS → R3 定轴 → R4 抽先验
  L2 轴判定层：A1-A5 五轴（深度/方向/剂型/靶点/分布）+ 增益中庸治理
  L4 回填迭代：事前预期 vs 观察窗 → 偏差归因 → 算子权重修正

数据来源：
  - spum-core/五行/人元/spum-神农本草经.md §二~§五（药性→ΔS 向量）
  - spacetime_engine.py SHENG/KE 链 + wuxing_status + tiao_hou_engine
  - 归约算法库草案 v0.1 R1-R4 四步算子
  - 增益中庸治理准则（spum-governance.md / spacetime_engine v2）
"""

from __future__ import annotations
from typing import Optional
import re
import math

# ═══════════════════════════════════════════════════════════
# 共享常量（复用 spacetime_engine）
# ═══════════════════════════════════════════════════════════

SHENG = {"wood": "fire", "fire": "earth", "earth": "metal", "metal": "water", "water": "wood"}
KE    = {"wood": "earth", "earth": "water", "water": "fire", "fire": "metal", "metal": "wood"}
WUXING_LIST = ["wood", "fire", "earth", "metal", "water"]
WUXING_CN   = {"wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"}

# ═══════════════════════════════════════════════════════════
# L0 变量层：五味→ΔS 基底向量（神农本草经 §3.1）
# ═══════════════════════════════════════════════════════════

# 五味 → S 向量分量操作（火, 水, 木, 土, 金）
# 基底不是正交的——实际药物是加权组合
# 符号约定：+ = 注入 / - = 逸散
TASTE_DELTA_S = {
    # 辛：发散——提升局域 σ 梯度 + 加速水形链流动
    "辛": {"fire": +1.0, "water": +1.0, "wood":  0.0, "earth": 0.0, "metal": 0.0},
    # 甘：缓补——向土形储备池注入低度节点 + 温和建立新环路
    "甘": {"fire":  0.0, "water":  0.0, "wood": +0.5, "earth": +1.0, "metal": -0.3},
    # 酸：收涩——收紧木形环（降低 μ）+ 金形桥边拆解逸散边
    "酸": {"fire":  0.0, "water":  0.0, "wood": -0.8, "earth": 0.0, "metal": +0.8},
    # 苦：泄燥——金形桥边拆解 + 降低火形梯度（清热）
    "苦": {"fire": -0.8, "water":  0.0, "wood":  0.0, "earth": 0.0, "metal": +1.0},
    # 咸：软下——软化水形链上的锁定节点 + 排出土形储备
    "咸": {"fire":  0.0, "water": -0.8, "wood":  0.0, "earth": -0.8, "metal": 0.0},
}

# 四气 → σ 偏移（全局方向，神农本草经 §2.1）
QI_SIGMA_OFFSET = {
    "热": +1.0,   # 大幅提高局域 σ → S_火 ↑
    "温": +0.5,   # 轻微提高局域 σ
    "平":  0.0,   # 不改变基线
    "凉": -0.5,   # 轻微降低局域 σ
    "寒": -1.0,   # 大幅降低局域 σ → S_火 ↓
}

# 四气 → S_火 直接偏移系数（神农本草经 §2.2 耦合）
QI_FIRE_COEFF = {
    "热": +1.2,
    "温": +0.6,
    "平":  0.0,
    "凉": -0.6,
    "寒": -1.2,
}

# 三品 → ΔS 幅度系数（神农本草经 §4.1）
GRADE_COEFF = {
    "上品": 0.6,   # 小幅度，可久服
    "中品": 1.0,   # 中等幅度
    "下品": 1.6,   # 大幅度，不可久服
}

# ═══════════════════════════════════════════════════════════
# L0 变量层：核心药材 ΔS 向量表（神农本草经 §5）
# 格式：name, siqi(四气), taste(主味), grade(品级), delta_S(火/水/木/土/金)
# delta_S 为符号量级（+/- + 相对强度），用于快速查表
# 若未收录 → 走 R2 的五味基底归约路径
# ═══════════════════════════════════════════════════════════

HERB_DELTA_S: dict[str, dict] = {
    # ── 上品 ──
    "人参":  {"siqi": "微温", "taste": "甘", "grade": "上品", "delta_S": {"fire": 0.0, "water": 0.0, "wood": +0.2, "earth": +1.0, "metal":  0.0}},
    "甘草":  {"siqi": "平",   "taste": "甘", "grade": "上品", "delta_S": {"fire": 0.0, "water": 0.0, "wood":  0.0, "earth": +1.0, "metal": -0.3}},
    "炙甘草": {"siqi": "温",  "taste": "甘", "grade": "上品", "delta_S": {"fire": +0.5, "water": 0.0, "wood":  0.0, "earth": +1.1, "metal": -0.2}},
    "地黄":  {"siqi": "寒",   "taste": "甘", "grade": "上品", "delta_S": {"fire": -0.8, "water": 0.0, "wood":  0.0, "earth": +1.0, "metal":  0.0}},
    "生地":  {"siqi": "寒",   "taste": "甘", "grade": "上品", "delta_S": {"fire": -0.8, "water": 0.0, "wood":  0.0, "earth": +1.0, "metal":  0.0}},
    "熟地":  {"siqi": "微温", "taste": "甘", "grade": "上品", "delta_S": {"fire": +0.3, "water": 0.0, "wood":  0.0, "earth": +1.2, "metal":  0.0}},
    "大枣":  {"siqi": "温",   "taste": "甘", "grade": "上品", "delta_S": {"fire": +0.6, "water": 0.0, "wood":  0.0, "earth": +1.0, "metal":  0.0}},
    "桂枝":  {"siqi": "温",   "taste": "辛甘", "grade": "上品", "delta_S": {"fire": +1.2, "water": +0.5, "wood":  0.0, "earth": 0.0, "metal":  0.0}},
    "茯苓":  {"siqi": "平",   "taste": "甘", "grade": "上品", "delta_S": {"fire": 0.0, "water": +0.8, "wood":  0.0, "earth": 0.0, "metal": -0.5}},
    "山药":  {"siqi": "平",   "taste": "甘", "grade": "上品", "delta_S": {"fire": 0.0, "water": 0.0, "wood":  0.0, "earth": +1.0, "metal":  0.0}},
    "枸杞":  {"siqi": "平",   "taste": "甘", "grade": "上品", "delta_S": {"fire": 0.0, "water": 0.0, "wood":  0.0, "earth": +0.8, "metal":  0.0}},
    "黄芪":  {"siqi": "微温", "taste": "甘", "grade": "上品", "delta_S": {"fire": +0.4, "water": 0.0, "wood":  0.0, "earth": +0.9, "metal":  0.0}},
    # ── 中品 ──
    "芍药":  {"siqi": "凉",   "taste": "苦酸", "grade": "中品", "delta_S": {"fire": -0.5, "water": 0.0, "wood": -0.5, "earth": 0.0, "metal": +0.8}},
    "白芍":  {"siqi": "凉",   "taste": "苦酸", "grade": "中品", "delta_S": {"fire": -0.5, "water": 0.0, "wood": -0.5, "earth": 0.0, "metal": +0.8}},
    "赤芍":  {"siqi": "微寒", "taste": "苦",   "grade": "中品", "delta_S": {"fire": -0.6, "water": 0.0, "wood": -0.3, "earth": 0.0, "metal": +1.0}},
    "当归":  {"siqi": "温",   "taste": "甘辛", "grade": "中品", "delta_S": {"fire": +0.5, "water": +0.4, "wood": +0.3, "earth": +0.5, "metal":  0.0}},
    "川芎":  {"siqi": "温",   "taste": "辛",   "grade": "中品", "delta_S": {"fire": +1.0, "water": +0.6, "wood":  0.0, "earth": 0.0, "metal":  0.0}},
    "白术":  {"siqi": "温",   "taste": "甘苦", "grade": "中品", "delta_S": {"fire": +0.3, "water": -0.3, "wood":  0.0, "earth": +0.9, "metal": -0.3}},
    "生白术": {"siqi": "温",  "taste": "甘苦", "grade": "中品", "delta_S": {"fire": +0.3, "water": -0.3, "wood":  0.0, "earth": +0.9, "metal": -0.3}},
    "炒白术": {"siqi": "微温","taste": "甘",   "grade": "中品", "delta_S": {"fire": +0.2, "water": -0.2, "wood":  0.0, "earth": +1.1, "metal": -0.2}},
    "泽泻":  {"siqi": "寒",   "taste": "甘",   "grade": "中品", "delta_S": {"fire": -0.5, "water": -0.3, "wood":  0.0, "earth": -0.8, "metal":  0.0}},
    "柴胡":  {"siqi": "微寒", "taste": "苦辛", "grade": "中品", "delta_S": {"fire": -0.4, "water": 0.0, "wood": +1.0, "earth": 0.0, "metal": +0.3}},
    "半夏":  {"siqi": "温",   "taste": "辛",   "grade": "中品", "delta_S": {"fire": +0.8, "water": +0.4, "wood":  0.0, "earth": -0.5, "metal":  0.0}},
    "麦冬":  {"siqi": "微寒", "taste": "甘",   "grade": "中品", "delta_S": {"fire": -0.5, "water": +0.5, "wood":  0.0, "earth": +0.5, "metal":  0.0}},
    "玄参":  {"siqi": "微寒", "taste": "甘苦咸","grade": "中品", "delta_S": {"fire": -0.6, "water": -0.3, "wood":  0.0, "earth": +0.5, "metal": +0.5}},
    "五味子": {"siqi": "温",  "taste": "酸甘", "grade": "中品", "delta_S": {"fire": +0.3, "water": -0.3, "wood": -0.5, "earth": +0.5, "metal": +0.3}},
    "川楝子": {"siqi": "寒",  "taste": "苦",   "grade": "中品", "delta_S": {"fire": -0.4, "water": 0.0, "wood": +0.5, "earth": 0.0, "metal": +0.5}},
    "苦杏仁": {"siqi": "微温","taste": "苦",   "grade": "中品", "delta_S": {"fire": +0.4, "water": 0.0, "wood": -0.3, "earth": 0.0, "metal": +0.8}},
    "山萸肉": {"siqi": "微温","taste": "酸甘", "grade": "中品", "delta_S": {"fire": +0.3, "water": +0.5, "wood": -0.5, "earth": +0.3, "metal":  0.0}},
    "白鲜皮": {"siqi": "寒",  "taste": "苦",   "grade": "中品", "delta_S": {"fire": -0.6, "water": 0.0, "wood": +0.3, "earth": 0.0, "metal": +0.8}},
    "北沙参": {"siqi": "微寒","taste": "甘",   "grade": "中品", "delta_S": {"fire": -0.4, "water": +0.3, "wood":  0.0, "earth": +0.5, "metal":  0.0}},
    "浮小麦": {"siqi": "凉",  "taste": "甘",   "grade": "中品", "delta_S": {"fire": -0.3, "water": 0.0, "wood":  0.0, "earth": +0.4, "metal": -0.2}},
    "葛根":  {"siqi": "平",   "taste": "甘辛", "grade": "中品", "delta_S": {"fire": +0.5, "water": +0.3, "wood": +0.8, "earth": +0.3, "metal":  0.0}},
    "生姜":  {"siqi": "微温", "taste": "辛",   "grade": "中品", "delta_S": {"fire": +0.9, "water": +0.5, "wood":  0.0, "earth": 0.0, "metal":  0.0}},
    "干姜":  {"siqi": "热",   "taste": "辛",   "grade": "中品", "delta_S": {"fire": +1.5, "water": 0.0, "wood":  0.0, "earth": 0.0, "metal":  0.0}},
    "石膏":  {"siqi": "大寒", "taste": "辛甘", "grade": "中品", "delta_S": {"fire": -1.5, "water": 0.5, "wood":  0.0, "earth": +0.5, "metal":  0.0}},
    "知母":  {"siqi": "寒",   "taste": "苦甘", "grade": "中品", "delta_S": {"fire": -1.2, "water": 0.0, "wood":  0.0, "earth": +0.5, "metal": +0.3}},
    "栀子":  {"siqi": "寒",   "taste": "苦",   "grade": "中品", "delta_S": {"fire": -1.0, "water": 0.0, "wood":  0.0, "earth": 0.0, "metal": +0.8}},
    # ── 下品 ──
    "大黄":  {"siqi": "寒",   "taste": "苦",   "grade": "下品", "delta_S": {"fire": -1.0, "water": -0.5, "wood":  0.0, "earth": -1.2, "metal": +1.0}},
    "附子":  {"siqi": "大热", "taste": "辛甘", "grade": "下品", "delta_S": {"fire": +1.8, "water": -0.5, "wood":  0.0, "earth": 0.0, "metal":  0.0}},
    "芒硝":  {"siqi": "大寒", "taste": "苦咸", "grade": "下品", "delta_S": {"fire": -1.5, "water": -0.8, "wood":  0.0, "earth": -1.2, "metal": +1.0}},
    "吴茱萸": {"siqi": "热",  "taste": "辛苦", "grade": "下品", "delta_S": {"fire": +1.2, "water": -0.3, "wood": +0.5, "earth": 0.0, "metal": +0.5}},
    "麻黄":  {"siqi": "温",   "taste": "辛",   "grade": "下品", "delta_S": {"fire": +1.5, "water": +0.8, "wood":  0.0, "earth": 0.0, "metal":  0.0}},
    "薄荷":  {"siqi": "凉",   "taste": "辛",   "grade": "下品", "delta_S": {"fire": -0.6, "water": +0.5, "wood":  0.0, "earth": 0.0, "metal":  0.0}},
    "黄连":  {"siqi": "寒",   "taste": "苦",   "grade": "下品", "delta_S": {"fire": -1.5, "water": 0.0, "wood":  0.0, "earth": 0.0, "metal": +1.2}},
}


# ── 归一化层 ────────────────────────────────────────────────────
# 三个功能：炮制前缀剥离 → 异名归一 → 未收录自动回落

# 炮制前缀 → 剥离（这些前缀通常指向同一 base 药材，仅 ΔS 幅度微调）
# 注意：表内有独立条目的炮制变体（炙甘草/熟地/生白术/白芍/赤芍）不会被剥离
PROCESSING_PREFIXES = [
    "生", "炒", "炙", "熟", "酒", "醋", "盐", "姜",
    "制", "炮", "煅", "焙", "煨", "蒸", "煮",
]

# 异名 → 表内标准名映射（归一化）
ALIAS_MAP: dict[str, str] = {
    # 地黄家族
    "生地": "生地",          # 表内已有
    "生地黄": "生地",
    "熟地黄": "熟地",
    # 甘草家族
    "生甘草": "甘草",
    "炙甘草": "炙甘草",     # 表内已有
    # 白术家族
    "生白术": "生白术",     # 表内已有
    "炒白术": "炒白术",     # 表内已有
    "麸炒白术": "炒白术",
    # 白芍/赤芍
    "白芍药": "白芍",
    "赤芍药": "赤芍",
    # 当归家族
    "全当归": "当归",
    "当归头": "当归",
    "当归尾": "当归",
    # 茯苓家族
    "白茯苓": "茯苓",
    "赤茯苓": "茯苓",
    "茯苓皮": "茯苓",
    # 其他常见异名
    "元参": "玄参",
    "乌药": "乌药",          # 占位（表内无，让回落处理）
    "川楝实": "川楝子",
    "山茱萸": "山萸肉",
    "酸枣仁": "酸枣仁",      # 占位
    "莲子肉": "莲子",        # 占位
}

# 未收录药的默认性味回落（ fallback）
# 按常用药补——没在这里的 → 纯五味基底（默认平甘）
DEFAULT_SIQI_TASTE: dict[str, tuple[str, str]] = {
    # 常用补药
    "乌药": ("温", "辛"),
    "酸枣仁": ("平", "酸甘"),
    "莲子": ("平", "甘涩"),
    "芡实": ("平", "甘涩"),
    "桑椹": ("寒", "甘酸"),
    "黄精": ("平", "甘"),
    "玉竹": ("平", "甘"),
    "天冬": ("寒", "甘苦"),
    # 常用理气药
    "香附": ("平", "辛微苦"),
    "延胡索": ("温", "辛苦"),
    "郁金": ("寒", "辛苦"),
    "佛手": ("温", "辛苦酸"),
    # 常用活血药
    "丹参": ("微寒", "苦"),
    "桃仁": ("平", "苦甘"),
    "红花": ("温", "辛"),
    # 常用利水药
    "猪苓": ("平", "甘淡"),
    "车前子": ("寒", "甘"),
    "滑石": ("寒", "甘淡"),
    "木通": ("寒", "苦"),
    # 常用安神药
    "远志": ("温", "苦辛"),
    "石菖蒲": ("温", "辛苦"),
    "龙骨": ("平", "甘涩"),
    # 常用收涩药
    "金樱子": ("平", "甘酸"),
    "益智仁": ("温", "辛"),
    # 常用清热药
    "金银花": ("寒", "甘"),
    "连翘": ("微寒", "苦"),
    "黄芩": ("寒", "苦"),
    "黄柏": ("寒", "苦"),
    "龙胆草": ("寒", "苦"),
    # 常用化痰药
    "陈皮": ("温", "辛苦"),
    "橘红": ("温", "辛苦"),
    "白芥子": ("温", "辛"),
    "桔梗": ("平", "苦辛"),
}


def _normalize_herb_name(name: str) -> tuple[str, bool]:
    """
    药名归一化：异名映射 + 炮制前缀剥离

    返回:
        (normalized_name, was_modified)
    """
    orig = name

    # 1) 直接命中 → 返回
    if name in HERB_DELTA_S:
        return name, False

    # 2) 异名表 → 替换后再查
    alias = ALIAS_MAP.get(name)
    if alias and alias in HERB_DELTA_S:
        return alias, True

    # 3) 炮制前缀剥离（逐个试，先剥一层再查，直到没前缀或命中）
    for prefix in sorted(PROCESSING_PREFIXES, key=len, reverse=True):
        if name.startswith(prefix) and len(name) > len(prefix):
            stripped = name[len(prefix):]
            # 剥离后命中
            if stripped in HERB_DELTA_S:
                return stripped, True
            # 剥离后异名命中
            alias2 = ALIAS_MAP.get(stripped)
            if alias2 and alias2 in HERB_DELTA_S:
                return alias2, True
            # 递归：前缀可能叠加（如"炒炙甘草"）
            normed, mod2 = _normalize_herb_name(stripped)
            if mod2:
                return normed, True

    # 没归一化到任何已知条目 → 返回原名（让调用方处理）
    return orig, (orig != name)

# ── 乘数表（变量层，实体化草案 §4.1）──────────────────────
# 这些是从归约算法库草案 v0.1 的 ↑↑/↓↓ 方向指示转成的实际数值
# 用于调制 R4 ΔS 叠加时的权重

# 节气乘数（24 节气 × 五形）
SEASON_MODULATION: dict[str, dict[str, float]] = {
    # 春季（立春~谷雨）：木旺
    "立春":  {"wood": 1.4, "fire": 1.1, "earth": 0.9, "metal": 0.8, "water": 1.1},
    "雨水":  {"wood": 1.3, "fire": 1.2, "earth": 0.9, "metal": 0.8, "water": 1.1},
    "惊蛰":  {"wood": 1.5, "fire": 1.2, "earth": 0.8, "metal": 0.7, "water": 1.0},
    "春分":  {"wood": 1.4, "fire": 1.2, "earth": 0.9, "metal": 0.9, "water": 1.0},
    "清明":  {"wood": 1.2, "fire": 1.3, "earth": 0.9, "metal": 0.9, "water": 1.0},
    "谷雨":  {"wood": 1.1, "fire": 1.2, "earth": 1.1, "metal": 0.9, "water": 1.0},
    # 夏季（立夏~大暑）：火旺
    "立夏":  {"wood": 1.0, "fire": 1.5, "earth": 1.1, "metal": 0.7, "water": 0.8},
    "小满":  {"wood": 1.0, "fire": 1.5, "earth": 1.2, "metal": 0.7, "water": 0.7},
    "芒种":  {"wood": 0.9, "fire": 1.6, "earth": 1.2, "metal": 0.6, "water": 0.6},
    "夏至":  {"wood": 0.8, "fire": 1.8, "earth": 1.3, "metal": 0.6, "water": 0.5},
    "小暑":  {"wood": 0.8, "fire": 1.7, "earth": 1.3, "metal": 0.6, "water": 0.5},
    "大暑":  {"wood": 0.7, "fire": 1.8, "earth": 1.4, "metal": 0.5, "water": 0.4},
    # 秋季（立秋~霜降）：金旺
    "立秋":  {"wood": 0.7, "fire": 0.7, "earth": 1.1, "metal": 1.6, "water": 1.1},
    "处暑":  {"wood": 0.8, "fire": 0.8, "earth": 1.1, "metal": 1.5, "water": 1.2},
    "白露":  {"wood": 0.8, "fire": 0.8, "earth": 1.0, "metal": 1.6, "water": 1.2},
    "秋分":  {"wood": 0.9, "fire": 0.9, "earth": 1.0, "metal": 1.5, "water": 1.1},
    "寒露":  {"wood": 0.8, "fire": 0.8, "earth": 1.0, "metal": 1.5, "water": 1.1},
    "霜降":  {"wood": 0.7, "fire": 0.7, "earth": 1.2, "metal": 1.4, "water": 1.0},
    # 冬季（立冬~大寒）：水旺
    "立冬":  {"wood": 0.8, "fire": 0.5, "earth": 1.0, "metal": 1.2, "water": 1.6},
    "小雪":  {"wood": 0.7, "fire": 0.5, "earth": 1.0, "metal": 1.2, "water": 1.7},
    "大雪":  {"wood": 0.6, "fire": 0.4, "earth": 0.9, "metal": 1.3, "water": 1.8},
    "冬至":  {"wood": 0.5, "fire": 0.3, "earth": 0.9, "metal": 1.3, "water": 2.0},
    "小寒":  {"wood": 0.6, "fire": 0.4, "earth": 1.0, "metal": 1.2, "water": 1.8},
    "大寒":  {"wood": 0.7, "fire": 0.5, "earth": 1.0, "metal": 1.1, "water": 1.7},
}

# 时辰乘数（十二地支 × 五形）
HOUR_MODULATION: dict[str, dict[str, float]] = {
    # 子丑：水旺；寅卯：木旺；辰戌丑未：土旺；巳午：火旺；申酉：金旺
    "子": {"wood": 0.9, "fire": 0.6, "earth": 0.8, "metal": 1.0, "water": 1.5},
    "丑": {"wood": 0.9, "fire": 0.7, "earth": 1.3, "metal": 1.0, "water": 1.1},
    "寅": {"wood": 1.4, "fire": 1.1, "earth": 0.8, "metal": 0.9, "water": 1.0},
    "卯": {"wood": 1.5, "fire": 1.0, "earth": 0.8, "metal": 0.8, "water": 1.1},
    "辰": {"wood": 0.8, "fire": 0.9, "earth": 1.3, "metal": 1.1, "water": 0.9},
    "巳": {"wood": 1.0, "fire": 1.4, "earth": 0.9, "metal": 0.8, "water": 0.7},
    "午": {"wood": 0.9, "fire": 1.5, "earth": 1.0, "metal": 0.6, "water": 0.5},
    "未": {"wood": 1.0, "fire": 1.1, "earth": 1.3, "metal": 0.9, "water": 0.8},
    "申": {"wood": 0.9, "fire": 0.7, "earth": 1.0, "metal": 1.4, "water": 1.1},
    "酉": {"wood": 0.8, "fire": 0.6, "earth": 0.9, "metal": 1.5, "water": 1.2},
    "戌": {"wood": 0.9, "fire": 0.8, "earth": 1.3, "metal": 1.0, "water": 0.9},
    "亥": {"wood": 0.9, "fire": 0.5, "earth": 0.8, "metal": 1.1, "water": 1.5},
}

# ── 算法库当前权重（可被 L4 回填修正）──────────────────
# 这些权重在 init_algorithm_weights() 时从 DB 或默认值加载
# L4 回填模块修改这些权重 → 下一次归约自动生效

class ReductionState:
    """算法库活状态：可被回填修正的算子权重"""
    def __init__(self):
        # R3 增益中庸：断链点增益系数（默认 1.0）
        self.broken_node_gain = 1.0
        # R3 尖峰压制系数（默认 0.3，不直接处理尖峰）
        self.peak_suppress = 0.3
        # R3 KE 冲突升级系数（默认 1.5）
        self.ke_conflict_mult = 1.5
        # L0 乘数表覆盖（可被观测数据修正）
        self.season_corrections: dict[str, dict[str, float]] = {}
        self.hour_corrections: dict[str, dict[str, float]] = {}

    def get_season_mod(self, jieqi: str) -> dict[str, float]:
        """取节气乘数（优先用修正值）"""
        base = SEASON_MODULATION.get(jieqi, SEASON_MODULATION.get("春分", {}))
        corr = self.season_corrections.get(jieqi, {})
        return {wx: base.get(wx, 1.0) * corr.get(wx, 1.0) for wx in WUXING_LIST}

    def get_hour_mod(self, dizhi: str) -> dict[str, float]:
        """取时辰乘数（优先用修正值）"""
        base = HOUR_MODULATION.get(dizhi, HOUR_MODULATION.get("子", {}))
        corr = self.hour_corrections.get(dizhi, {})
        return {wx: base.get(wx, 1.0) * corr.get(wx, 1.0) for wx in WUXING_LIST}


# ── 持久化层：模块级缓存 + DB 读写 ──────────────────────────
# 进程内单例缓存，避免每次归约都查 DB；apply_correction 后自动同步

_state_cache: ReductionState | None = None


def load_state_from_db() -> ReductionState:
    """
    从 DB 加载 ReductionState（reduction_states 表）
    若表不存在或无记录 → 返回默认状态（不抛异常，让本地调试可用）
    """
    state = ReductionState()
    try:
        from app.database import SessionLocal
        from app.models.reduction import ReductionStateDB
        db = SessionLocal()
        try:
            row = db.query(ReductionStateDB).order_by(ReductionStateDB.id.asc()).first()
            if row:
                state.broken_node_gain = row.broken_node_gain or 1.0
                state.peak_suppress = row.peak_suppress or 0.3
                state.ke_conflict_mult = row.ke_conflict_mult or 1.5
                state.season_corrections = row.season_corrections or {}
                state.hour_corrections = row.hour_corrections or {}
        finally:
            db.close()
    except Exception:
        # DB 不可用（迁移没跑、本地 SQLite 没表）→ 返回默认
        pass
    return state


def save_state_to_db(state: ReductionState) -> None:
    """把 ReductionState 写回 DB（upsert 单行）"""
    try:
        from app.database import SessionLocal
        from app.models.reduction import ReductionStateDB
        db = SessionLocal()
        try:
            row = db.query(ReductionStateDB).order_by(ReductionStateDB.id.asc()).first()
            if row is None:
                row = ReductionStateDB(label="default")
                db.add(row)
            row.broken_node_gain = state.broken_node_gain
            row.peak_suppress = state.peak_suppress
            row.ke_conflict_mult = state.ke_conflict_mult
            row.season_corrections = state.season_corrections
            row.hour_corrections = state.hour_corrections
            db.commit()
        finally:
            db.close()
    except Exception:
        # DB 不可用 → 静默跳过（内存态仍有效）
        pass


def get_persistent_state() -> ReductionState:
    """获取全局持久化 ReductionState（首次调用从 DB 加载到缓存）"""
    global _state_cache
    if _state_cache is None:
        _state_cache = load_state_from_db()
    return _state_cache


# ═══════════════════════════════════════════════════════════
# L1 归约算子：R1-R4 四步硬规则
# ═══════════════════════════════════════════════════════════

def R1_split_formula(herbs: list[str] | str) -> list[dict]:
    """
    R1 取方：拆君臣佐使 + 剂量

    输入:
        herbs: ["茯苓 15g", "桂枝 10g", ...] 或 "苓桂术甘汤：茯苓15g 桂枝10g ..."
    输出:
        [{"name": "茯苓", "dose": 15.0, "unit": "g"}, ...]

    君臣佐使识别：
      第一味（或剂量最大）= 君
      第二 = 臣
      其余 = 佐使（需按剂量区分佐/使）
      不强制标记——让 R4 加权时剂量自动决定权重
    """
    if isinstance(herbs, str):
        # 拆处方字符串：支持 "人参 10g, 白术 10g" / "人参10g 白术10g" / "人参：10克"
        text = herbs.split("：", 1)[-1] if "：" in herbs else herbs
        # 先把逗号/分号统一成空格分隔
        text = re.sub(r"[,，;；、]+", " ", text)
        raw_parts = [p for p in text.split() if p.strip()]
        # 合并 "药名" + "剂量单位" 的空格分隔对
        parts = []
        i = 0
        while i < len(raw_parts):
            cur = raw_parts[i]
            # 当前是纯中文（药名），下一个以数字开头（剂量+单位）→ 合并
            if re.match(r"^[\u4e00-\u9fff]+$", cur) and i + 1 < len(raw_parts) and re.match(r"^\d", raw_parts[i + 1]):
                parts.append(cur + raw_parts[i + 1])
                i += 2
            else:
                parts.append(cur)
                i += 1
    else:
        parts = herbs

    result = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # 匹配药名 + 剂量（格式：药名+数字+单位，如 "人参10g" / "人参 10g" / "人参10"）
        # 药名：连续的中文字符（避免把数字/单位吃进去）
        m = re.match(r"([\u4e00-\u9fff]+)\s*(\d*\.?\d*)\s*([a-zA-Z克枚片]*)$", part)
        if m and m.group(1):
            name = m.group(1)
            dose = float(m.group(2)) if m.group(2) else 10.0
            unit = m.group(3) or "g"
        else:
            # 兜底：整串当药名（无剂量信息）
            name = part
            dose = 10.0
            unit = "g"
        result.append({"name": name, "dose": dose, "unit": unit})

    return result


def R2_get_delta_S(herb_name: str, auto_fallback: bool = True) -> tuple[dict | None, str | None]:
    """
    R2 取 ΔS：归一化 → 查药表 → 未收录自动回落

    返回:
        (delta_S_or_None, source_label)
          source_label = "direct" | "normalized:<原名→标准名>" | "fallback:<性味>" | None

    新策略（v1.1）：未收录药自动回落——不静默跳过。
      1) 归一化（异名映射 + 炮制前缀剥离）
      2) 查药表直接命中 → source="direct" 或 "normalized:..."
      3) 查 DEFAULT_SIQI_TASTE 常用回落 → 走 R2_reduce_new_herb → source="fallback:..."
      4) 完全没信息 → return (None, None)
    """
    # Step 1: 归一化
    normed, modified = _normalize_herb_name(herb_name)

    # Step 2: 查药表
    entry = HERB_DELTA_S.get(normed)
    if entry:
        source = f"normalized:{herb_name}→{normed}" if modified else "direct"
        return dict(entry["delta_S"]), source

    # Step 3: 常用回落（DEFAULT_SIQI_TASTE）
    fb = DEFAULT_SIQI_TASTE.get(normed) or DEFAULT_SIQI_TASTE.get(herb_name)
    if fb and auto_fallback:
        siqi, taste = fb
        ds = R2_reduce_new_herb(siqi, taste)
        return ds, f"fallback:{siqi}{taste}"

    # Step 4: 完全没信息
    return None, None


def R2_reduce_new_herb(siqi: str, taste: str) -> dict[str, float]:
    """
    R2 开放边集归约：从性味信息归约 ΔS 向量

    这是"互联网边集"的核心接口——任何新药材/方剂只要能描述性味，
    就能被归约为 ΔS 五维向量。

    输入:
        siqi: 四气（寒/凉/平/温/热 或 微温/微寒）
        taste: 五味组合（辛/甘/酸/苦/咸，可能多字如 "辛甘"、"苦酸"）
    输出:
        {"fire": x, "water": x, "wood": x, "earth": x, "metal": x}
    """
    # 1. 五味基底加权
    delta = {wx: 0.0 for wx in WUXING_LIST}
    taste_count = 0
    for ch in taste:
        base = TASTE_DELTA_S.get(ch)
        if base:
            for wx in WUXING_LIST:
                delta[wx] += base[wx]
            taste_count += 1
    if taste_count > 0:
        for wx in WUXING_LIST:
            delta[wx] /= taste_count

    # 2. 四气调制 S_火
    # 微温 = 温 × 0.5；微寒 = 凉 × 0.5
    qi = siqi
    qi_mult = 1.0
    if "微" in siqi:
        qi_mult = 0.5
        qi = siqi.replace("微", "")
    coeff = QI_FIRE_COEFF.get(qi, 0.0) * qi_mult
    delta["fire"] += coeff

    # 3. σ 全局偏移传导（§2.2 耦合规则）
    sigma_offset = QI_SIGMA_OFFSET.get(qi, 0.0) * qi_mult
    # 热→火↑→水↑（加速链）→木↓（过热松解）→土↓（储备消耗）
    # 寒→火↓→水↓→木↑（僵化）→土↑（沉淀）
    if sigma_offset > 0:  # 温/热
        delta["water"] += sigma_offset * 0.5
        delta["wood"]  -= sigma_offset * 0.3
        delta["earth"] -= sigma_offset * 0.2
    elif sigma_offset < 0:  # 凉/寒
        delta["water"] += sigma_offset * 0.3  # 冷水形链减速
        delta["wood"]  -= sigma_offset * 0.4  # 冷木形环锁死（↑）
        delta["earth"] -= sigma_offset * 0.3  # 寒土形储备冻结（↑）

    return delta


def R3_governance_weighting(delta_S_raw: dict[str, float], v_base: dict[str, float],
                             ctx: dict | None, state: ReductionState) -> dict[str, float]:
    """
    R3 定轴：增益中庸治理（核心！）

    不是直接对每味药的 ΔS_raw 做简单叠加——
    而是先看 SHENG 链哪段断了，再按断链位置加权每味药的增益方向。

    输入:
        delta_S_raw: 方剂 ΔS 原始叠加（未调制）
        v_base: 体质五形向量
        ctx: 时空上下文（含节气、时辰、旺相）
        state: 活状态（含回填修正的权重）
    输出:
        加权后的 ΔS（用于 R4 抽先验）+ 附带治理元信息
    """
    # 1. 找 SHENG 链断链点（复用 spacetime_engine 逻辑）
    weighted = _apply_wuxing_weight(v_base, ctx)
    broken, peaks, valleys, chain_from, chain_to = _detect_broken_chain(weighted)

    # 2. 增益中庸：断链点方向加权
    modulated = dict(delta_S_raw)
    chain_desc = f"{WUXING_CN[chain_from]}→{WUXING_CN[broken]}→{WUXING_CN[chain_to]}链断于{WUXING_CN[broken]}形"

    if broken:
        # 断链点方向 × broken_node_gain（默认 1.0）
        modulated[broken] = modulated.get(broken, 0) * state.broken_node_gain

        # 尖峰方向轻微压制（× peak_suppress，默认 0.3——不直接处理尖峰）
        for pk in peaks:
            modulated[pk] = modulated.get(pk, 0) * state.peak_suppress

    # 3. KE 冲突检测：若 delta_S 恰好在冲突调和方向 → 升级
    ke_conflict = _detect_ke_conflict(weighted)
    if ke_conflict and broken in ke_conflict.get("harmony_nodes", []):
        for wx in WUXING_LIST:
            modulated[wx] *= state.ke_conflict_mult

    return {
        "delta_S": modulated,
        "governance": "增益中庸",
        "broken_node": broken,
        "peaks": peaks,
        "valleys": valleys,
        "chain_desc": chain_desc,
        "ke_conflict": ke_conflict,
    }


def R4_extract_prior(governed_delta: dict, state: ReductionState) -> dict:
    """
    R4 抽先验：把 R3 加权后的 ΔS 转成可验证的事前预期

    这是"事前预期（§0.4d）"的形式化——
    不是只输出 ΔS 数值，而是输出：
      - 预期位移（expected_delta_S）
      - 预期链条变化（broken_node → 通 → peaks 应下降）
      - 可证伪判据（如果 outcome 显示 peaks 没降 → 治理失败）
    """
    delta = governed_delta["delta_S"]
    broken = governed_delta["broken_node"]
    peaks = governed_delta["peaks"]
    valleys = governed_delta["valleys"]

    expected = {wx: round(delta.get(wx, 0), 2) for wx in WUXING_LIST}

    # 预期链条变化（增益中庸的直接推论）
    chain_change_prediction = {}
    if broken:
        chain_change_prediction["broken_node"] = broken
        chain_change_prediction["broken_should_increase"] = True
        for pk in peaks:
            chain_change_prediction[f"peak_{pk}_should_decrease"] = True
        for vl in valleys:
            chain_change_prediction[f"valley_{vl}_should_fill"] = True

    return {
        "expected_delta_S": expected,
        "chain_desc": governed_delta["chain_desc"],
        "chain_change_prediction": chain_change_prediction,
        "governance": "增益中庸",
        "confidence": 0.8,  # 可被历史回填修正
    }


# ═══════════════════════════════════════════════════════════
# R3 的辅助检测函数（与 spacetime_engine 同步）
# ═══════════════════════════════════════════════════════════

def _apply_wuxing_weight(v_base: dict, ctx: dict | None) -> dict[str, float]:
    """时空加权：v_base × 节气乘数 × 时辰乘数 × 旺相系数"""
    result = {wx: float(v_base.get(wx, 50)) for wx in WUXING_LIST}

    if not ctx:
        return result

    # 节气加权
    jieqi = ctx.get("jieqi")
    if isinstance(jieqi, dict):
        jieqi = jieqi.get("current_term")
    if jieqi and jieqi in SEASON_MODULATION:
        for wx in WUXING_LIST:
            result[wx] *= SEASON_MODULATION[jieqi].get(wx, 1.0)

    # 时辰加权
    dizhi = ctx.get("hour_branch") or ctx.get("shichen_dizhi")
    if dizhi and dizhi in HOUR_MODULATION:
        for wx in WUXING_LIST:
            result[wx] *= HOUR_MODULATION[dizhi].get(wx, 1.0)

    # 旺相加权（tingshou → status → STATUS_WEIGHT）
    lingshou = ctx.get("lingshou")
    if lingshou:
        from .spacetime_engine import wuxing_status, STATUS_WEIGHT
        for wx in WUXING_LIST:
            st = wuxing_status(lingshou, wx)
            result[wx] *= STATUS_WEIGHT.get(st, 1.0)

    return result


def _detect_broken_chain(weighted: dict[str, float]) -> tuple:
    """找 SHENG 链断链点 + 尖峰 + 凹谷"""
    # 断链点 = SHENG 链里加权最弱的节点
    broken = min(weighted, key=lambda wx: weighted[wx])
    chain_from = next((k for k, v in SHENG.items() if v == broken), None)
    chain_to = SHENG.get(broken)

    # 尖峰 = SHENG 链上紧邻 broken 的上游（堆积）
    peaks = []
    if chain_from and weighted.get(chain_from, 0) > weighted[broken] + 5:
        peaks.append(chain_from)
    # 再加其他显著偏高的（> 平均 +10）
    avg = sum(weighted.values()) / len(weighted)
    for wx in WUXING_LIST:
        if wx != broken and wx not in peaks and weighted[wx] > avg + 10:
            peaks.append(wx)

    # 凹谷 = SHENG 链上紧邻 broken 的下游（匮乏）
    valleys = []
    if chain_to and weighted.get(chain_to, 0) < weighted[broken] + 5:
        valleys.append(chain_to)

    return broken, peaks, valleys, chain_from, chain_to


def _detect_ke_conflict(weighted: dict[str, float]) -> dict | None:
    """KE 链冲突检测：相邻两形加权后都 > 60"""
    for a, b in KE.items():
        if weighted.get(a, 0) > 60 and weighted.get(b, 0) > 60:
            # 调和节点 = SHENG[a]（a 所生）
            harmony = SHENG[a]
            return {"a": a, "b": b, "harmony": harmony}
    return None


# ═══════════════════════════════════════════════════════════
# 对外主入口
# ═══════════════════════════════════════════════════════════

def reduce_prescription(herbs: list[str] | str, v_base: dict[str, float],
                        ctx: dict | None = None,
                        state: ReductionState | None = None) -> dict:
    """
    方剂归约主入口（R1→R2→R3→R4 四步链）

    输入:
        herbs: ["茯苓 15g", "桂枝 10g", ...] 或 处方字符串
        v_base: 体质五形向量 {"wood": 55, "fire": 60, "earth": 70, "metal": 30, "water": 45}
        ctx: 时空上下文（节气/时辰/旺相——用于 R3 治理定轴）
        state: 活状态（默认新建）

    输出:
        {
            "herbs_parsed": [...],           # R1 结果
            "herb_delta_S": {...},           # R2 结果（每味药 ΔS）
            "raw_sum": {...},                # 未调制叠加
            "expected_delta_S": {...},       # R4 事前预期（可验证）
            "chain_desc": "土→金→水链断于金形",
            "broken_node": "metal",
            "governance": "增益中庸",
            "missing_herbs": ["XXX", ...],   # 未收录需走开放边集的药材
        }
    """
    if state is None:
        state = ReductionState()

    # R1 取方
    parsed = R1_split_formula(herbs)

    # R2 取 ΔS（带归一化 + 自动回落）
    herb_deltas = {}
    herb_sources = {}    # 追踪每味药的来源（direct / normalized / fallback）
    missing = []
    for h in parsed:
        ds, source = R2_get_delta_S(h["name"])
        herb_sources[h["name"]] = source or "unknown"
        if ds is None:
            missing.append(h["name"])
            herb_deltas[h["name"]] = None
        else:
            herb_deltas[h["name"]] = ds

    # 计算原始叠加（剂量 × grade）
    raw_sum = {wx: 0.0 for wx in WUXING_LIST}
    total_dose = sum(h["dose"] for h in parsed) or 1
    for h in parsed:
        ds = herb_deltas.get(h["name"])
        if ds is None:
            continue
        # 剂量权重（归一化）
        dose_weight = h["dose"] / total_dose
        # 品级系数（从 HERB_DELTA_S 取）
        grade = HERB_DELTA_S.get(h["name"], {}).get("grade", "中品")
        grade_coeff = GRADE_COEFF.get(grade, 1.0)
        for wx in WUXING_LIST:
            raw_sum[wx] += ds[wx] * dose_weight * grade_coeff

    # R3 定轴（增益中庸治理）
    governed = R3_governance_weighting(raw_sum, v_base, ctx, state)

    # R4 抽先验
    prior = R4_extract_prior(governed, state)

    return {
        "herbs_parsed": parsed,
        "herb_delta_S": herb_deltas,
        "herb_sources": herb_sources,       # 新增：每味药来源追踪
        "raw_sum": {wx: round(v, 3) for wx, v in raw_sum.items()},
        # R3 治理元信息
        "broken_node": governed["broken_node"],
        "peaks": governed["peaks"],
        "valleys": governed["valleys"],
        "ke_conflict": governed.get("ke_conflict"),
        # R4 先验
        **prior,
        "missing_herbs": missing,
        "fallback_used": len(herb_sources) - sum(1 for v in herb_sources.values() if v == "direct" or v.startswith("normalized")),
    }


def reduce_new_herb_entry(name: str, siqi: str, taste: str, grade: str = "中品") -> dict:
    """
    开放边集入口：新药材归约 + 可选注册到 HERB_DELTA_S

    互联网边集（开放·无限）对接点——
    任何新药材只要能描述性味（四气 + 五味），就能被归约为 ΔS 向量。

    输入:
        name: 药名
        siqi: 四气
        taste: 五味组合
        grade: 品级
    输出:
        {"name", "siqi", "taste", "grade", "delta_S", "registered": bool}
    """
    ds = R2_reduce_new_herb(siqi, taste)

    # 可选：注册到药表（下次 R2 直接查）
    registered = False
    if name and name not in HERB_DELTA_S:
        HERB_DELTA_S[name] = {
            "siqi": siqi, "taste": taste, "grade": grade,
            "delta_S": ds,
            "source": "open_edge_set",  # 标记来自开放边集
        }
        registered = True

    return {
        "name": name, "siqi": siqi, "taste": taste, "grade": grade,
        "delta_S": ds,
        "registered": registered,
    }


# ═══════════════════════════════════════════════════════════
# L4 回填迭代：预期 vs 实际 → 偏差归因 → 算子修正
# ═══════════════════════════════════════════════════════════

def compare_outcome(expected: dict, actual: dict,
                    chain_prediction: dict | None = None) -> dict:
    """
    L4 回填核心：事前预期 vs 观察窗 → 偏差归因

    输入:
        expected: {"wood": +0.1, "fire": -0.05, ...}  # ΔS 量级通常在 ±1 以内
        actual: {"wood": +0.05, "fire": -0.08, ...}  # TreatmentPlan.outcome_delta_S
        chain_prediction: R4 产出的链条变化预测（可证伪判据）

    量纲修正（v1.1）：用相对偏差而非绝对偏差——
      |actual - expected| / max(|expected|, 0.5)
    避免 expected 量级小（0.01）时绝对偏差阈值 1.0 永远不触发的问题。
    """
    deviation = {wx: actual.get(wx, 0) - expected.get(wx, 0) for wx in WUXING_LIST}

    # 相对偏差：用 max(|expected|, 0.5) 做分母，避免 expected≈0 时爆炸
    rel_dev = {}
    for wx in WUXING_LIST:
        denom = max(abs(expected.get(wx, 0)), 0.5)
        rel_dev[wx] = abs(deviation[wx]) / denom if denom > 0 else abs(deviation[wx])

    max_rel_wx = max(rel_dev, key=rel_dev.get)
    max_rel = rel_dev[max_rel_wx]

    # 链条预测验证（增益中庸的核心可证伪判据）
    chain_ok = True
    chain_failures = []
    broken = None  # 断链点（从 chain_prediction 提取，后续归因分支引用）
    if chain_prediction:
        broken = chain_prediction.get("broken_node")
        if broken:
            # broken_node 应该上升（expected > 0 → actual 也应 > 0）
            exp_broken = expected.get(broken, 0)
            act_broken = actual.get(broken, 0)
            if exp_broken > 0 and act_broken <= 0:
                chain_ok = False
                chain_failures.append(f"断链点{WUXING_CN[broken]}未上升（expected={exp_broken:+.2f} actual={act_broken:+.2f}）")
            elif exp_broken < 0 and act_broken >= 0:
                chain_ok = False
                chain_failures.append(f"断链点{WUXING_CN[broken]}未下降（expected={exp_broken:+.2f} actual={act_broken:+.2f}）")
        # peak 应该下降
        for key, should_decrease in chain_prediction.items():
            if key.startswith("peak_") and should_decrease:
                pk = key.replace("peak_", "").replace("_should_decrease", "")
                if actual.get(pk, 0) > expected.get(pk, 0):
                    chain_ok = False
                    chain_failures.append(f"尖峰{WUXING_CN.get(pk,pk)}未下降")

    # 相对偏差阈值 1.0 = 实际值偏离预期 100% 以上
    if max_rel < 1.0 and chain_ok:
        match = True
    else:
        match = False

    # 从 chain_prediction 解析 peaks / valleys（R4 产出的 peak_*_should_decrease 键）
    peaks_in_prediction = []
    if chain_prediction:
        for key in chain_prediction:
            if key.startswith("peak_") and key.endswith("_should_decrease"):
                peaks_in_prediction.append(key.replace("peak_", "").replace("_should_decrease", ""))

    # 偏差归因
    attribution = "none"
    suggestion = {}

    if not chain_ok:
        # 区分 failure 类型：只有 peak 未下降 → peak_suppress；有 broken_node 方向错 → broken_node_gain
        has_broken_failure = any("断链点" in f for f in chain_failures)
        has_peak_failure = any("尖峰" in f for f in chain_failures)
        if has_peak_failure and not has_broken_failure:
            attribution = "peak_suppress"
            suggestion = {"peak_suppress": "尖峰压制不足，减小 peak_suppress 系数让压制更强"}
        else:
            attribution = "broken_node_gain"
            suggestion = {"broken_node_gain": "检查断链点识别逻辑或增益系数"}
    elif max_rel >= 1.0:
        # peak_suppress: 偏差集中在 peaks 上，尖峰压制不足（chain_ok=True 但量级偏差大）
        if peaks_in_prediction and max_rel_wx in peaks_in_prediction:
            attribution = "peak_suppress"
            suggestion = {"peak_suppress": "尖峰压制量级不准，微调 peak_suppress 系数"}
        elif broken is not None and max_rel_wx == broken and deviation[max_rel_wx] < 0:
            attribution = "broken_node_gain"
            suggestion = {"broken_node_gain": "增益效果不足，增大增益系数"}
        elif abs(deviation.get("fire", 0)) > 0.5:
            attribution = "season_mod"
            suggestion = {"season_mod": "乘数表可能不准，需人工复核"}
        else:
            attribution = "general"
            suggestion = {"recheck": "偏差过大，可能断链点识别或药表收录有问题"}

    return {
        "match": match,
        "deviation": {wx: round(v, 3) for wx, v in deviation.items()},
        "relative_deviation": {wx: round(v, 3) for wx, v in rel_dev.items()},
        "max_relative_deviation": round(max_rel, 3),
        "max_deviation_wuxing": WUXING_CN.get(max_rel_wx, max_rel_wx),
        "chain_verification": {"ok": chain_ok, "failures": chain_failures},
        "attribution": attribution,
        "correction_suggestion": suggestion,
    }


def apply_correction(state: ReductionState, correction: dict) -> ReductionState:
    """
    L4 回填执行：把偏差归因应用到算子权重 → 自动持久化到 DB

    这是"变量/权重修正 → 回算法库 ⟲"的核心实现。
    修正完内存态后自动 save_state_to_db，下一次归约直接生效。
    """
    attr = correction.get("attribution")
    if attr == "broken_node_gain":
        # 轻微增大增益系数（保守，每次 +0.05）
        state.broken_node_gain = min(2.0, state.broken_node_gain + 0.05)
    elif attr == "peak_suppress":
        state.peak_suppress = max(0.1, state.peak_suppress - 0.02)
    elif attr == "season_mod":
        # 标记需要人工复核
        pass

    # 自动持久化（让下一次归约生效）
    save_state_to_db(state)
    # 同步更新模块缓存（如果 state 就是全局缓存的引用）
    global _state_cache
    if _state_cache is state:
        _state_cache = state

    return state
