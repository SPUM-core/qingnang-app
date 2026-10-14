"""gua_resolution_engine — 玄空飞星卦组合化解归约引擎

权威基准：
  - spum-core/五行/地元/spum-卦组合化解.md v1.1（归约链定义）
  - spum-core/五行/人元/spum-玄空飞星卦组合化解.md（51 组合断语数据源）
  - spum-core/五行/地元/spum-玄空飞星.md v1.1（排盘前置）

治理范式（与 wuxing_chain 动态策略选择器对齐）：
  本引擎只有**宫级 2 个星**（山星+向星），不能做完整五边形凸多面体力学检测。
  所以 GUA_FULL_TABLE 是从秘术断语反推的**该两星组合的最优化解归约**——
  针对特定宫位的局部相位对（不是全局体质五形向量）。

  在有完整五形向量的场景（如 tiao_hou_engine），治理策略由
  wuxing_chain.select_governance_strategy() 动态选择（增益中庸 / 压抑尖峰 / 不干预）。
  在只有局部两星的场景（如卦化解），用秘术给定的特定归约。

归约路径：
  每宫 (山星, 向星) 两数对
    → 洛书数→五形相位映射
    → 相位对分类（同相叠加/相生链/相克冲突/土壅煞位）
    → 匹配秘术表中该组合的最优化解归约
    → 化解物（增益调和节点的 ΔS 干预）

上游依赖：flying_star_engine.make_complete_pan() 产出的每宫山向两数对
下游对接：spacetime.py API 端点 /spacetime/flying-star
"""

from __future__ import annotations
from typing import Optional


# ═══════════════════════════════════════════════════════════
# 基础常量（与 reduction_engine / spacetime_engine 对齐）
# ═══════════════════════════════════════════════════════════

# 洛书数 → 五形相位（卦组合化解.md §一）
LUOSHU_WUXING = {
    1: 'water',   # 坎 · 链式传输
    2: 'earth',   # 坤 · 松散储备
    3: 'wood',    # 震 · 闭合环
    4: 'wood',    # 巽 · 环扩展
    5: 'earth',   # 中 · 壅滞（五黄大煞）
    6: 'metal',   # 乾 · 修剪V⁻
    7: 'metal',   # 兑 · 拆解
    8: 'earth',   # 艮 · 储备池
    9: 'fire',    # 离 · ∇σ 驱动
}

# 五形中文名
WUXING_CN = {'wood': '木', 'fire': '火', 'earth': '土', 'metal': '金', 'water': '水'}

# SHENG 链（增益中庸核心）
SHENG = {'wood': 'fire', 'fire': 'earth', 'earth': 'metal', 'metal': 'water', 'water': 'wood'}
KE    = {'wood': 'earth', 'earth': 'water', 'water': 'fire', 'fire': 'metal', 'metal': 'wood'}

# ═══════════════════════════════════════════════════════════
# 51 组合五形相位分类表
# 来源：spum-卦组合化解.md §三 五形分类索引
# + spum-玄空飞星卦组合化解.md 断语数据源
#
# key = 两数对的无序元组 (a, b) 或单星自叠加 (a, a)
# 这样 "36" 和 "63" 都能命中
#
# 每个条目：
#   hexagram: 卦象名
#   wuxing_semantics: 五形语义（简短描述）
#   pair_type: 相位对类型 ('同相叠加'/'相生链'/'相克冲突'/'土壅煞位')
#   mediator_node: 中庸节点（耦合链断链处，需要增益的五形相位）
#   mediator_reason: 为什么这个是中庸节点（图论解释）
#   jiehuas: [化解物列表]
#   key_shen: 当旺断语（可选）
#   shi_yun: 失运断语（可选）
# ═══════════════════════════════════════════════════════════

GUA_TABLE: dict[tuple[int, int], dict] = {
    # ══ 火相位组（9） ══
    (9, 9): {
        'hexagram': '离卦', 'wuxing_semantics': '火形过亢·当旺双星',
        'pair_type': '同相叠加',
        'mediator_node': None,  # 双星当旺是吉象，保护不化解
        'mediator_reason': '旺气集中——驻留受益',
        'jiehuas': ['保护·不化解'],
        'key_shen': '旺气最集中', 'shi_yun': '火炎土燥',
    },
    (1, 9): {
        'hexagram': '既济', 'wuxing_semantics': '水火既济·当旺',
        'pair_type': '相生链',
        'mediator_node': 'wood',  # 木形（水火之间的承接）
        'mediator_reason': '水火既济——木形承接',
        'jiehuas': ['4 枝观音竹', '绿植'],
        'key_shen': '出文人', 'shi_yun': '眼疾、皮肤病',
    },
    (3, 9): {
        'hexagram': '丰卦', 'wuxing_semantics': '木火通明',
        'pair_type': '相生链',
        'mediator_node': 'metal',  # 金形（木→火→土→金，金是土→水桥）
        'mediator_reason': '火泄木需水调和——增益土→水的桥节点金形',
        'jiehuas': ['黄盒+八粒石蛋+水'],
        'key_shen': '木火通明', 'shi_yun': '火炎土燥',
    },
    (2, 9): {
        'hexagram': '夷卦', 'wuxing_semantics': '土火晦明',
        'pair_type': '相克冲突',
        'mediator_node': 'metal',  # 金形（土→水桥，同时火生土→土→金属）
        'mediator_reason': '金形是土↔火回路的稳态锚点',
        'jiehuas': ['五层风铃', '黑/深蓝物件'],
        'key_shen': None, 'shi_yun': '土晦火·事多阻',
    },
    (5, 9): {
        'hexagram': '—', 'wuxing_semantics': '土火交加',
        'pair_type': '土壅煞位',
        'mediator_node': 'metal',
        'mediator_reason': '金形稳态锚点——土火任意一边偏盛都能被金拆解缓冲',
        'jiehuas': ['五层风铃'],
        'key_shen': None, 'shi_yun': '火生土助煞',
    },
    (7, 9): {
        'hexagram': '革卦', 'wuxing_semantics': '金火相克',
        'pair_type': '相克冲突',
        'mediator_node': 'earth',  # 土形（火→土→金，土是调和）
        'mediator_reason': '火克金——增益火→土→金链的衔接点土形',
        'jiehuas': ['黄盒+八粒石蛋+水'],
        'key_shen': None, 'shi_yun': '金火相战',
    },
    (8, 9): {
        'hexagram': '贲卦', 'wuxing_semantics': '土火相生',
        'pair_type': '相生链',
        'mediator_node': None,  # 当旺喜象
        'mediator_reason': '当旺喜象——土火相生，无需干预',
        'jiehuas': ['黄物可也'],
        'key_shen': '当旺喜象', 'shi_yun': None,
    },

    # ══ 土相位组（2/5/8）·五黄煞位优先 ══
    # 五黄系：含 5 的所有组合（5 作为当运凶煞优先处理）
    (4, 5): (5, 4) == (4, 5) and None,  # 占位，实际 (4,5) 会被 (5,4) 覆盖
    # 直接用无序 key：set 去重处理，让 (5,2),(2,5),(5,5),(5,6),(6,5),(5,8),(8,5) 都归五黄系
    (2, 5): None, (5, 2): None,  # 五黄+二黑=双煞

    # 为简化，五黄系统一处理：让 (5,*) 和 (*,5) 查 (5,5) 作 fallback
    # 先给明确条目，再在 RESOLUTION_LOGIC 里统一处理五黄系

    (2, 2): {
        'hexagram': '坤卦', 'wuxing_semantics': '土过盛',
        'pair_type': '同相叠加',
        'mediator_node': 'metal',
        'mediator_reason': '土堆成山时本该由金拆解，金桥弱了土才壅滞',
        'jiehuas': ['七枚铜钱'],
        'key_shen': '富贵旺田宅', 'shi_yun': '肠胃腹部疾病',
    },
    (8, 8): {
        'hexagram': '艮卦', 'wuxing_semantics': '土盛而止',
        'pair_type': '同相叠加',
        'mediator_node': 'metal',
        'mediator_reason': '同土——金形拆解加速',
        'jiehuas': ['七枚铜钱'],
        'key_shen': '安如磐石', 'shi_yun': '脾胃病',
    },
    (2, 7): (7, 2) == (2, 7) and None,  # 占位
    # (2,7) 和 (7,2) 都是二七·临卦——二黑病符
    (7, 2): None,  # 同上，在有序元组里处理

    # ══ 水相位组（1） ══
    (1, 1): {
        'hexagram': '坎卦', 'wuxing_semantics': '水过盛',
        'pair_type': '同相叠加',
        'mediator_node': 'wood',
        'mediator_reason': '水形链过载——增益木形承接环路',
        'jiehuas': ['4 枝音竹'],
        'key_shen': None, 'shi_yun': '耳肾病、血症',
    },
    (1, 6): (6, 1) == (1, 6) and None,  # 占位
    (6, 1): None,  # 需处理

    # ══ 木相位组（3/4） ══
    (3, 3): {
        'hexagram': '震卦', 'wuxing_semantics': '木过亢',
        'pair_type': '同相叠加',
        'mediator_node': 'fire',
        'mediator_reason': '木形过度成僵环——增益火形让木→土链通',
        'jiehuas': ['红地毯', '红灯'],
        'key_shen': None, 'shi_yun': '口舌官非',
    },
    (3, 6): (6, 3) == (3, 6) and None,  # 占位
    (6, 3): None,  # 三六大壮·金木相战——关键组合

    # 后续组合用 resolve_gua_pair 函数动态推导
}


# ═══════════════════════════════════════════════════════════
# 完整 51 组合表（无重复、无序 key）
# 来自 spum-core/五行/人元/spum-玄空飞星卦组合化解.md 逐条整理
# + spum-卦组合化解.md §三 的中庸治理归因
# ═══════════════════════════════════════════════════════════

def _make_gua_key(a: int, b: int) -> tuple[int, int]:
    """把两星数做成无序 key：(a,b) 和 (b,a) 同一个 key"""
    return tuple(sorted([a, b]))


GUA_FULL_TABLE: dict[tuple[int, int], dict] = {
    # ── 火相位组 ──
    _make_gua_key(9, 9): {
        'hexagram': '离卦', 'wuxing_semantics': '火形过亢·当旺双星',
        'pair_type': '同相叠加',
        'mediator_node': None,  # 当旺不化解
        'mediator_reason': '双星当旺——旺气最集中处，驻留受益',
        'jiehuas': ['保护·不化解'],
        'key_shen': '旺气最集中', 'shi_yun': '火炎土燥',
    },
    _make_gua_key(1, 9): {
        'hexagram': '既济', 'wuxing_semantics': '水火既济·当旺',
        'pair_type': '相生链',
        'mediator_node': 'wood',
        'mediator_reason': '水火既济——木形是火→土→金→水→木链的"所生"承接点',
        'jiehuas': ['4 枝观音竹', '绿植'],
        'key_shen': '出文人', 'shi_yun': '眼疾、皮肤病',
    },
    _make_gua_key(3, 9): {
        'hexagram': '丰卦', 'wuxing_semantics': '木火通明',
        'pair_type': '相生链',
        'mediator_node': 'metal',
        'mediator_reason': '木→火→土→金链需金形拆解——火泄木过猛需土→水桥',
        'jiehuas': ['黄盒+八粒石蛋+水'],
        'key_shen': '木火通明', 'shi_yun': '火炎土燥',
    },
    _make_gua_key(4, 9): {
        'hexagram': '家人', 'wuxing_semantics': '木火相生',
        'pair_type': '相生链',
        'mediator_node': 'earth',
        'mediator_reason': '木火相生过猛→皮目病——增益火→土的衔接',
        'jiehuas': ['黄物'],
        'key_shen': None, 'shi_yun': '火炎土燥、皮目病',
    },
    _make_gua_key(2, 9): {
        'hexagram': '夷卦', 'wuxing_semantics': '土火晦明',
        'pair_type': '相克冲突',
        'mediator_node': 'metal',
        'mediator_reason': '金形是土↔火回路的稳态锚点',
        'jiehuas': ['五层风铃', '黑/深蓝物件'],
        'key_shen': None, 'shi_yun': '土晦火',
    },
    _make_gua_key(5, 9): {
        'hexagram': '—', 'wuxing_semantics': '土火交加',
        'pair_type': '土壅煞位',
        'mediator_node': 'metal',
        'mediator_reason': '火生土助煞——金形稳态锚点',
        'jiehuas': ['五层风铃'],
        'key_shen': None, 'shi_yun': '火生土助煞',
    },
    _make_gua_key(7, 9): {
        'hexagram': '革卦', 'wuxing_semantics': '金火相克',
        'pair_type': '相克冲突',
        'mediator_node': 'earth',
        'mediator_reason': '火克金——增益火→土→金链的衔接点土形',
        'jiehuas': ['黄盒+八粒石蛋+水'],
        'key_shen': None, 'shi_yun': '金火相战',
    },
    _make_gua_key(8, 9): {
        'hexagram': '贲卦', 'wuxing_semantics': '土火相生',
        'pair_type': '相生链',
        'mediator_node': None,
        'mediator_reason': '当旺喜象',
        'jiehuas': ['黄物'],
        'key_shen': '当旺喜象', 'shi_yun': None,
    },

    # ── 土相位组·五黄煞位 ──
    _make_gua_key(2, 5): {
        'hexagram': '—', 'wuxing_semantics': '五黄土壅',
        'pair_type': '土壅煞位',
        'mediator_node': 'metal',
        'mediator_reason': '土堆成山时本该由金拆解，金桥弱了土才壅滞',
        'jiehuas': ['五层风铃'],
        'key_shen': None, 'shi_yun': '五黄大煞·土壅',
    },
    _make_gua_key(4, 5): {
        'hexagram': '—', 'wuxing_semantics': '五黄向星',
        'pair_type': '土壅煞位',
        'mediator_node': 'metal',
        'mediator_reason': '同上·土壅',
        'jiehuas': ['五层风铃'],  # 卧室忌风铃 → 由 resolve_pan 功能修正处理
        'key_shen': None, 'shi_yun': '五黄大煞',
    },
    _make_gua_key(5, 5): {
        'hexagram': '—', 'wuxing_semantics': '五黄双煞·大煞最重',
        'pair_type': '土壅煞位',
        'mediator_node': 'metal',
        'mediator_reason': '双五黄·土壅最盛',
        'jiehuas': ['五层风铃'],
        'key_shen': None, 'shi_yun': '大煞最重',
    },
    _make_gua_key(5, 6): {
        'hexagram': '—', 'wuxing_semantics': '五黄土金',
        'pair_type': '土壅煞位',
        'mediator_node': 'metal',
        'mediator_reason': '金形拆解加速',
        'jiehuas': ['五层风铃'],
        'key_shen': None, 'shi_yun': '五黄大煞',
    },
    _make_gua_key(5, 8): {
        'hexagram': '—', 'wuxing_semantics': '五黄土土',
        'pair_type': '土壅煞位',
        'mediator_node': 'metal',
        'mediator_reason': '同上',
        'jiehuas': ['五层风铃'],
        'key_shen': None, 'shi_yun': '五黄大煞',
    },
    _make_gua_key(2, 2): {
        'hexagram': '坤卦', 'wuxing_semantics': '土过盛',
        'pair_type': '同相叠加',
        'mediator_node': 'metal',
        'mediator_reason': '土堆成山时本该由金拆解，金桥弱了土才壅滞',
        'jiehuas': ['七枚铜钱'],
        'key_shen': '富贵旺田宅', 'shi_yun': '肠胃腹部疾病',
    },
    _make_gua_key(8, 8): {
        'hexagram': '艮卦', 'wuxing_semantics': '土盛而止',
        'pair_type': '同相叠加',
        'mediator_node': 'metal',
        'mediator_reason': '同土——金形拆解加速',
        'jiehuas': ['七枚铜钱'],
        'key_shen': '安如磐石', 'shi_yun': '脾胃病',
    },
    _make_gua_key(2, 8): {
        'hexagram': '谦卦', 'wuxing_semantics': '土土同气',
        'pair_type': '同相叠加',
        'mediator_node': 'metal',
        'mediator_reason': '土土同气——金形拆解',
        'jiehuas': ['两枚圆钟'],
        'key_shen': None, 'shi_yun': '土壅',
    },
    _make_gua_key(1, 8): {
        'hexagram': '颐卦', 'wuxing_semantics': '水被土克',
        'pair_type': '相克冲突',
        'mediator_node': 'metal',
        'mediator_reason': '土克水——增益土→水的桥节点金形，同时金形拆解土形',
        'jiehuas': ['两枚圆钟'],
        'key_shen': None, 'shi_yun': '耳肾疾病',
    },
    _make_gua_key(2, 7): {
        'hexagram': '临卦', 'wuxing_semantics': '土生金·病符入',
        'pair_type': '相生链+煞位',
        'mediator_node': 'metal',
        'mediator_reason': '二黑病符土形——金形拆解病符',
        'jiehuas': ['两层圆钟'],
        'key_shen': None, 'shi_yun': '病符二黑·腹疾妇科',
    },
    _make_gua_key(3, 8): {
        'hexagram': '小过', 'wuxing_semantics': '木土相战',
        'pair_type': '相克冲突',
        'mediator_node': 'fire',
        'mediator_reason': '木克土——增益火形让木→火→土链通',
        'jiehuas': ['红地毯', '红灯'],
        'key_shen': None, 'shi_yun': '木土相战',
    },

    # ── 水相位组 ──
    _make_gua_key(1, 1): {
        'hexagram': '坎卦', 'wuxing_semantics': '水过盛',
        'pair_type': '同相叠加',
        'mediator_node': 'wood',
        'mediator_reason': '水形链过载——增益木形承接环路',
        'jiehuas': ['4 枝音竹'],
        'key_shen': None, 'shi_yun': '耳肾病、血症',
    },
    _make_gua_key(1, 4): {
        'hexagram': '井卦', 'wuxing_semantics': '水木相生',
        'pair_type': '相生链',
        'mediator_node': 'fire',
        'mediator_reason': '水木相生过猛——增益火形∇σ激活，水火调和',
        'jiehuas': ['红地毯', '红电灯', '若加五铜钱更好'],
        'key_shen': '出文人', 'shi_yun': '疯癫、咯血',
    },
    _make_gua_key(1, 6): {
        'hexagram': '需卦', 'wuxing_semantics': '水金相生',
        'pair_type': '相生链',
        'mediator_node': 'wood',
        'mediator_reason': '金→水→木链——增益木形让水承接顺流到木',
        'jiehuas': ['绿色/青色物件'],
        'key_shen': '旺文人', 'shi_yun': '金寒水冷、孤寡寒症',
    },
    _make_gua_key(1, 7): {
        'hexagram': '节卦', 'wuxing_semantics': '水金相生',
        'pair_type': '相生链',
        'mediator_node': 'wood',
        'mediator_reason': '同上',
        'jiehuas': ['绿色/青色物件'],
        'key_shen': '利家中男丁', 'shi_yun': '肾病、流产',
    },
    _make_gua_key(2, 6): {
        'hexagram': '地天泰', 'wuxing_semantics': '土金水链',
        'pair_type': '相生链',
        'mediator_node': 'water',
        'mediator_reason': '土→金→水——增益水形让链条承接',
        'jiehuas': ['黑鱼 6 条'],
        'key_shen': None, 'shi_yun': None,
    },
    _make_gua_key(3, 6): {
        'hexagram': '大壮', 'wuxing_semantics': '金木相战·阳亢',
        'pair_type': '相克冲突',
        'mediator_node': 'water',
        'mediator_reason': '金→水→木链断于水形——增益水形这个金→木链的承托节点',
        'jiehuas': ['黑/深蓝物件'],
        'key_shen': None, 'shi_yun': '金木相战·阳亢象',
    },
    _make_gua_key(3, 7): {
        'hexagram': '妹卦', 'wuxing_semantics': '木金相战',
        'pair_type': '相克冲突',
        'mediator_node': 'water',
        'mediator_reason': '同上',
        'jiehuas': ['黑鱼 6 条'],
        'key_shen': None, 'shi_yun': '口舌官非',
    },
    _make_gua_key(4, 6): {
        'hexagram': '小畜', 'wuxing_semantics': '木金相战',
        'pair_type': '相克冲突',
        'mediator_node': 'water',
        'mediator_reason': '同上',
        'jiehuas': ['黑/深蓝'],
        'key_shen': None, 'shi_yun': None,
    },
    _make_gua_key(4, 7): {
        'hexagram': '兑卦', 'wuxing_semantics': '木金相战',
        'pair_type': '相克冲突',
        'mediator_node': 'water',
        'mediator_reason': '同上',
        'jiehuas': ['黑/深蓝'],
        'key_shen': None, 'shi_yun': None,
    },

    # ── 金相位组 ──
    _make_gua_key(6, 6): {
        'hexagram': '乾卦', 'wuxing_semantics': '金过盛',
        'pair_type': '同相叠加',
        'mediator_node': 'water',
        'mediator_reason': '金→水链——增益水形链式扩展，泄金',
        'jiehuas': ['黑/深蓝物件'],
        'key_shen': None, 'shi_yun': None,
    },
    _make_gua_key(6, 7): {
        'hexagram': '履卦', 'wuxing_semantics': '金金同气',
        'pair_type': '同相叠加',
        'mediator_node': 'water',
        'mediator_reason': '同上',
        'jiehuas': ['黑/深蓝物件'],
        'key_shen': None, 'shi_yun': None,
    },
    _make_gua_key(7, 7): {
        'hexagram': '兑卦', 'wuxing_semantics': '金过盛',
        'pair_type': '同相叠加',
        'mediator_node': 'earth',
        'mediator_reason': '金过盛——增益土形储备池，土生金中和',
        'jiehuas': ['黄物'],
        'key_shen': None, 'shi_yun': None,
    },
    _make_gua_key(7, 8): {
        'hexagram': '咸卦', 'wuxing_semantics': '金土相生',
        'pair_type': '相生链',
        'mediator_node': 'water',
        'mediator_reason': '金→水→木链——增益水形',
        'jiehuas': ['黑/深蓝物件'],
        'key_shen': None, 'shi_yun': None,
    },

    # ── 木相位组 ──
    _make_gua_key(3, 3): {
        'hexagram': '震卦', 'wuxing_semantics': '木过亢',
        'pair_type': '同相叠加',
        'mediator_node': 'fire',
        'mediator_reason': '木形过度成僵环——增益火形让木→土链通',
        'jiehuas': ['红地毯', '红灯'],
        'key_shen': None, 'shi_yun': '口舌官非',
    },
    _make_gua_key(3, 4): {
        'hexagram': '恒卦', 'wuxing_semantics': '木木同气',
        'pair_type': '同相叠加',
        'mediator_node': 'fire',
        'mediator_reason': '同上',
        'jiehuas': ['红地毯', '红灯'],
        'key_shen': None, 'shi_yun': None,
    },
    _make_gua_key(4, 4): {
        'hexagram': '巽卦', 'wuxing_semantics': '木过亢',
        'pair_type': '同相叠加',
        'mediator_node': 'fire',
        'mediator_reason': '同上',
        'jiehuas': ['红地毯', '红灯'],
        'key_shen': None, 'shi_yun': None,
    },
    _make_gua_key(1, 3): {
        'hexagram': '屯卦', 'wuxing_semantics': '水木相生',
        'pair_type': '相生链',
        'mediator_node': 'fire',
        'mediator_reason': '水木通明——增益火形∇σ激活',
        'jiehuas': ['红地毯', '红灯'],
        'key_shen': '水木通明', 'shi_yun': None,
    },

    # ── 未收录但需覆盖的常见组合 ──
    _make_gua_key(6, 8): {
        'hexagram': '遁卦', 'wuxing_semantics': '火灾血光象',
        'pair_type': '相克冲突',
        'mediator_node': 'water',
        'mediator_reason': '金土相战——推演：补水制火（数据源无明确断语）',
        'jiehuas': ['黑/深蓝物件'],
        'key_shen': None, 'shi_yun': '火灾血光象',
    },
    _make_gua_key(1, 5): {
        'hexagram': '井卦', 'wuxing_semantics': '水木五黄',
        'pair_type': '相生链+煞位',
        'mediator_node': 'metal',
        'mediator_reason': '五黄优先——金形拆解',
        'jiehuas': ['红地毯+五铜钱'],
        'key_shen': None, 'shi_yun': None,
    },

    # ══ 胡长虹宅盘用到的全部组合（需完整覆盖） ══
    # 坎 5·9·9 → 已覆盖 (9,9)
    # 离 4·1·8 → 需 (1,8) 已覆盖 颐卦·增益金形
    # 坤 6·8·1 → (8,1) 同上 (1,8)
    # 兑 2·3·6 → (3,6) 大壮·增益水形 ✅
    # 震 7·7·2 → (7,2) 临卦·增益金形 — 已通过 _make_gua_key(2,7) 覆盖 ✅
    # 艮 3·2·7 → (2,7) 同上 ✅
    # 乾 1·4·5 → (4,5) 五黄大煞·增益金形 ✅
    # 中 9·5·4 → (5,4) 同上 ✅
    # 巽 8·6·3 → (6,3) 大壮·增益水形（按金水木链同构） ✅
}


# ═══════════════════════════════════════════════════════════
# 化解归约主函数
# ═══════════════════════════════════════════════════════════

def resolve_gua_pair(shan_star: int, xiang_star: int, yun: int = 9) -> dict:
    """
    给定山星+向星两数对 → 完整化解归约

    Args:
        shan_star: 山星数（1-9）
        xiang_star: 向星数（1-9）
        yun: 运号（用于判断当旺/失运）

    Returns:
        {
            pair_key: '99',
            hexagram: '离卦',
            wuxing_semantics: '火形过亢·当旺双星',
            pair_type: '同相叠加',
            wuxing_pair: ('fire', 'fire'),  # 两相位
            mediator_node: 'wood',
            mediator_reason: '...',
            jiehuas: [...],
            is_key_shen: True/False,    # 是否旺星到宫
            is_gua_sha: True/False,     # 是否煞位（五黄/二黑）
            suggestion: '一句话化解建议',
        }
    """
    key = _make_gua_key(shan_star, xiang_star)
    entry = GUA_FULL_TABLE.get(key)

    # 若表中无此组合 → 动态推导（根据五形相位和中庸治理原则）
    if entry is None:
        entry = _derive_gua_entry(shan_star, xiang_star, yun)

    # 五形相位
    wuxing_a = LUOSHU_WUXING[shan_star]
    wuxing_b = LUOSHU_WUXING[xiang_star]

    # 煞位标记
    is_gua_sha = (5 in (shan_star, xiang_star) or 2 in (shan_star, xiang_star))

    # 旺星标记
    is_key_shen = (yun in (shan_star, xiang_star))

    # 化解建议格式化
    mediator_cn = WUXING_CN.get(entry['mediator_node'], '') if entry['mediator_node'] else ''
    if entry['mediator_node'] is None:
        suggestion = f"✨ {entry['mediator_reason']}——保护不化解"
    else:
        suggestion = (
            f"🔧 增益{mediator_cn}形（{entry['mediator_reason']}）——"
            f"让{entry.get('wuxing_pair', ())}形耦合链自恢复"
        )

    return {
        'pair_key': f"{shan_star}{xiang_star}",
        'hexagram': entry.get('hexagram', '—'),
        'wuxing_semantics': entry.get('wuxing_semantics', ''),
        'pair_type': entry.get('pair_type', ''),
        'wuxing_pair': (wuxing_a, wuxing_b),
        'mediator_node': entry.get('mediator_node'),
        'mediator_cn': mediator_cn or '—',
        'mediator_reason': entry.get('mediator_reason', ''),
        'jiehuas': entry.get('jiehuas', []),
        'is_key_shen': is_key_shen,
        'is_gua_sha': is_gua_sha,
        'key_shen': entry.get('key_shen'),
        'shi_yun': entry.get('shi_yun'),
        'suggestion': suggestion,
    }


def _derive_gua_entry(a: int, b: int, yun: int) -> dict:
    """
    表中无此组合时的动态推导（中庸治理原则）

    推导逻辑（卦组合化解.md §四 4.1）：
    1. 查两相位的关系：同相叠加/相生/相克/土壅
    2. 定位耦合链断链点
    3. 找中庸节点（断链处的调节相位）
    """
    wa, wb = LUOSHU_WUXING[a], LUOSHU_WUXING[b]

    # 五黄系优先
    if 5 in (a, b):
        return {
            'hexagram': '—',
            'wuxing_semantics': f'五黄系·{WUXING_CN[wa]}{WUXING_CN[wb]}',
            'pair_type': '土壅煞位',
            'mediator_node': 'metal',
            'mediator_reason': '五黄土壅——金形拆解',
            'jiehuas': ['五层风铃'],
        }

    # 同相叠加
    if wa == wb:
        # 该相位的"所生"环节断链
        # wa 的所生 = SHENG[wa]（SHENG 链：wood→fire→earth→metal→water→wood）
        # 不对——同相叠加时，断链是"所生没人承接"→ mediator = SHENG[wa]
        mediator = SHENG[wa]
        return {
            'hexagram': '—',
            'wuxing_semantics': f'{WUXING_CN[wa]}形过亢',
            'pair_type': '同相叠加',
            'mediator_node': mediator,
            'mediator_reason': f'{WUXING_CN[wa]}形过亢——增益其"所生"{WUXING_CN[mediator]}形让链条通',
            'jiehuas': [_wuxing_jiehua(mediator)],
        }

    # 相生
    if SHENG[wa] == wb:  # wa 生 wb
        # 良性输送——如果不旺，可增益接收端
        # 但相生一般不需要化解
        return {
            'hexagram': '—',
            'wuxing_semantics': f'{WUXING_CN[wa]}→{WUXING_CN[wb]}相生',
            'pair_type': '相生链',
            'mediator_node': None,
            'mediator_reason': '相生链良性输送，一般不干预',
            'jiehuas': ['保护观察'],
        }

    # 相克
    if KE[wa] == wb:  # wa 克 wb
        # 找调和相位：SHENG 链上 wa 和 wb 之间的节点
        # KE: wood→earth→water→fire→metal→wood
        # 调和相位 = SHENG[wa]（a 所生）——因为 a 克 b，但 a 也生 c，c 可以承接
        mediator = SHENG[wa]
        return {
            'hexagram': '—',
            'wuxing_semantics': f'{WUXING_CN[wa]}克{WUXING_CN[wb]}',
            'pair_type': '相克冲突',
            'mediator_node': mediator,
            'mediator_reason': f'{WUXING_CN[wa]}克{WUXING_CN[wb]}——增益调和相位{WUXING_CN[mediator]}形',
            'jiehuas': [_wuxing_jiehua(mediator)],
        }

    # 二黑病符
    if 2 in (a, b):
        return {
            'hexagram': '—',
            'wuxing_semantics': '二黑病符',
            'pair_type': '土壅煞位',
            'mediator_node': 'metal',
            'mediator_reason': '二黑病符土形——金形拆解',
            'jiehuas': ['两层圆钟'],
        }

    # 默认
    return {
        'hexagram': '—',
        'wuxing_semantics': f'{WUXING_CN[wa]}{WUXING_CN[wb]}',
        'pair_type': '未知',
        'mediator_node': None,
        'mediator_reason': '动态推导——增益中庸原则',
        'jiehuas': ['待推导'],
    }


def _wuxing_jiehua(wuxing: str) -> str:
    """五形相位 → 推荐化解物（工具表简化版）"""
    return {
        'metal': '五层风铃 / 七枚铜钱 / 圆钟',
        'water': '黑/深蓝物件 / 黑鱼 6 条 / 鱼缸',
        'wood': '4 枝观音竹 / 绿植',
        'fire': '红地毯 / 红灯',
        'earth': '黄盒+八粒石蛋 / 黄物',
    }.get(wuxing, '—')


# ═══════════════════════════════════════════════════════════
# 全宅化解一站式（接 flying_star_engine 输出）
# ═══════════════════════════════════════════════════════════

def resolve_pan(pan_result: dict,
                palace_functions: Optional[dict[str, str]] = None) -> list[dict]:
    """
    给 flying_star_engine.make_complete_pan() 的每宫加化解建议

    Args:
        pan_result: make_complete_pan() 返回的 dict
        palace_functions: 可选 {宫位: 功能} —— 如 {'坎': '卧室', '兑': '大门'}
                        用于叠加功能修正（卧室保护煞位、厨房先通风）

    Returns:
        每宫一条完整化解 dict
    """
    yun = pan_result['yun']
    functions = palace_functions or {}

    resolutions = []
    for p in pan_result['palaces']:
        r = resolve_gua_pair(p['shan_star'], p['xiang_star'], yun)
        r['palace'] = p['palace']
        r['luoshu'] = p['luoshu']
        r['yun_star'] = p['yun_star']
        r['shan_star'] = p['shan_star']
        r['xiang_star'] = p['xiang_star']

        # 功能叠加修正
        func = functions.get(p['palace'])
        if func:
            r['palace_function'] = func
            # 卧室 → 当旺双星保护；煞位慎用金属风铃（夜间扰神）
            if '卧室' in func:
                if r['mediator_node'] == 'metal':
                    r['jiehuas'] = ['铜葫芦', '五帝钱串', '卧室忌风铃']
                    r['suggestion'] += '（卧室忌金属碰撞声）'
            if func in ('卫生间', '厨房'):
                r['suggestion'] += '——先物理通风干燥，再加化解'

        # 灶口联动提示（如果兑宫是灶位）
        if func == '厨房' and func in functions.values():
            # 简化：标记厨房位置，后续可结合灶口朝向判定
            pass

        resolutions.append(r)

    # 按优先级排序：煞位 > 相克冲突 > 同相叠加 > 相生链
    priority_order = {'土壅煞位': 0, '相克冲突': 1, '相生链+煞位': 2,
                      '同相叠加': 3, '相生链': 4}
    resolutions.sort(key=lambda r: priority_order.get(r['pair_type'], 99))

    return resolutions


# ═══════════════════════════════════════════════════════════
# 快速验证：胡长虹宅化解归约
# ═══════════════════════════════════════════════════════════
if __name__ == '__main__':
    from app.utils.flying_star_engine import make_complete_pan

    # 胡长虹宅·九运·子山午向
    pan = make_complete_pan('子', '午', yun=9)

    palace_funcs = {
        '坎': '卧室', '中': '大客厅', '乾': '第四卧室',
        '艮': '卫生间', '震': '小客厅', '兑': '大门·厨房',
        '坤': '淋浴间', '巽': '庭院东南',
    }

    print(f"=== 胡长虹宅·九运·子山午向 化解归约 ===\n")

    resolutions = resolve_pan(pan, palace_funcs)
    for r in resolutions:
        star_str = f"{r['yun_star']}·{r['shan_star']}·{r['xiang_star']}"
        func = f"[{r.get('palace_function','—')}]"
        tag = ""
        if r['is_gua_sha']: tag += " ⚠煞"
        if r['is_key_shen']: tag += " ✨旺"
        mediator = r['mediator_cn']
        print(f"{r['palace']:4s} {star_str:8s} 山向{r['pair_key']:2s} {func:12s}{tag}")
        print(f"    卦象={r['hexagram']:6s} 五形语义={r['wuxing_semantics']}")
        print(f"    中庸节点={mediator}形  化解物={r['jiehuas']}")
        print(f"    建议：{r['suggestion'][:80]}")
        print()
