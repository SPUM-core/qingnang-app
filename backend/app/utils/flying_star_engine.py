"""flying_star_engine — SPUM 玄空飞星排盘引擎

权威基准：spum-core/五行/地元/spum-玄空飞星.md v1.1
排盘算法：§五 5.1 通用算法（运盘恒顺飞，山/向盘依三元龙阴阳定顺逆）
实战锚点：胡长虹宅（九运·子山午向）——本文排盘规则经 2026-08 实战校验修正

架构定位：独立于 spacetime_engine 的并列模块（输入不同：坐向+运 vs v_base+时辰），
但共享 SHENG/KE/WUXING 等五形基础常量（从 reduction_engine 或 spacetime_engine import）

九宫编号（洛书位）：
  ┌───┬───┬───┐
  │ 4 │ 9 │ 2 │   巽东南 离南 坤西南
  ├───┼───┼───┤
  │ 3 │ 5 │ 7 │   震东   中宫 兑西
  ├───┼───┼───┤
  │ 8 │ 1 │ 6 │   艮东北 坎北 乾西北
  └───┴───┴───┘
"""

from __future__ import annotations
from typing import Optional


# ═══════════════════════════════════════════════════════════
# 基础常量
# ═══════════════════════════════════════════════════════════

# 九宫宫位 → 洛书数（地盘不变）
PALACE_LUOSHU = {
    '离': 9, '坤': 2, '兑': 7, '乾': 6,
    '中': 5, '巽': 4, '震': 3, '艮': 8, '坎': 1,
}
# 反向：洛书数 → 宫位
LUOSHU_PALACE = {v: k for k, v in PALACE_LUOSHU.items()}

# 飞星轨迹：中→乾→兑→艮→离→坎→坤→震→巽（循环）
FLYING_ORDER = ['中', '乾', '兑', '艮', '离', '坎', '坤', '震', '巽']

# 三元九运时间表
# 数据来源：spum-玄空飞星.md §2.2
YUN_TABLE = [
    # (运号, 起始年, 结束年)
    (1, 1864, 1883),  (2, 1884, 1903),  (3, 1904, 1923),
    (4, 1924, 1943),  (5, 1944, 1963),  (6, 1964, 1983),
    (7, 1984, 2003),  (8, 2004, 2023),  (9, 2024, 2043),
]

# ═══════════════════════════════════════════════════════════
# 三元龙阴阳表
# 权威基准：spum-玄空飞星.md §4.3
# 版本注记（重要）：四正山（子午卯酉）阴阳判定采用实战确立规则
#   子=阴、午=阳、卯=阴、酉=阴（胡长虹宅盘校验）
#   同一宅盘排盘必须保持同一流派自洽
# ═══════════════════════════════════════════════════════════

# 三元龙阴阳字典 {山名: 阴阳}
# 阳=顺飞, 阴=逆飞
SHAN_YIN_YANG = {
    # ── 天元龙 ──（四正山/四维山）
    '子': '阴', '午': '阳', '卯': '阴', '酉': '阴',
    '乾': '阳', '坤': '阳', '艮': '阳', '巽': '阳',
    # ── 地元龙 ──
    '壬': '阳', '丙': '阳', '甲': '阳', '庚': '阳',
    '戌': '阴', '未': '阴', '丑': '阴', '辰': '阴',
    # ── 人元龙 ──
    '癸': '阴', '丁': '阴', '乙': '阴', '辛': '阴',
    '亥': '阳', '申': '阳', '寅': '阳', '巳': '阳',
}

# 二十山 → 宫位映射（山名 → 所属宫位）
SHAN_TO_PALACE = {
    # 坎宫（北）
    '子': '坎', '癸': '坎', '壬': '坎',
    # 坤宫（西南）
    '未': '坤', '坤': '坤', '申': '坤',
    # 震宫（东）
    '卯': '震', '乙': '震', '甲': '震',
    # 巽宫（东南）
    '辰': '巽', '巽': '巽', '巳': '巽',
    # 乾宫（西北）
    '戌': '乾', '乾': '乾', '亥': '乾',
    # 兑宫（西）
    '酉': '兑', '辛': '兑', '庚': '兑',
    # 艮宫（东北）
    '丑': '艮', '艮': '艮', '寅': '艮',
    # 离宫（南）
    '午': '离', '丁': '离', '丙': '离',
}

# 坐山 → 向首的对宫映射（子山必午向，以此类推）
SHAN_TO_XIANG = {
    '子': '午', '癸': '丁', '壬': '丙',
    '未': '丑', '坤': '艮', '申': '寅',
    '卯': '酉', '乙': '辛', '甲': '庚',
    '辰': '戌', '巽': '乾', '巳': '亥',
}

# 向首 → 坐山的反查（从向首推坐山）
XIANG_TO_SHAN = {v: k for k, v in SHAN_TO_XIANG.items()}


# ═══════════════════════════════════════════════════════════
# 排盘函数
# ═══════════════════════════════════════════════════════════

def get_current_yun(year: Optional[int] = None) -> int:
    """根据年份推算当前运号（1-9）"""
    import datetime
    y = year or datetime.datetime.now().year
    for yun, start, end in YUN_TABLE:
        if start <= y <= end:
            return yun
    # 超出时间表范围：按九运循环外推
    # 九运周期 180 年，循环
    cycle = (y - 1864) // 180
    offset = (y - 1864) % 180
    # 在一个 180 年循环里找运号
    local_y = 1864 + offset
    for yun, start, end in YUN_TABLE:
        if start <= local_y <= end:
            return yun
    return 9  # fallback


def _fly(start_star: int, direction: str) -> dict[str, int]:
    """
    飞星：给定入中星 + 顺/逆 → 返回九宫各宫星数

    Args:
        start_star: 入中星数（1-9）
        direction: '顺' 或 '逆'（阳顺阴逆）

    Returns:
        {宫位名: 星数} — 按 FLYING_ORDER 顺序排好
    """
    result = {}
    star = start_star
    step = 1 if direction == '顺' else -1
    for palace in FLYING_ORDER:
        result[palace] = star
        # 下一颗星：顺飞 +1，逆飞 -1；循环 1-9
        star = (star - 1 + step) % 9 + 1
    return result


def _reverse_flying_dict(flying: dict[str, int]) -> dict[int, str]:
    """把 {宫位: 星数} 反过来变成 {星数: 宫位}，方便查某星落在哪个宫"""
    return {v: k for k, v in flying.items()}


def make_yun_pan(yun: int) -> dict[str, int]:
    """运盘：运星入中，恒顺飞"""
    return _fly(yun, '顺')


def make_shan_pan(yun_pan: dict[str, int], shan: str) -> dict[str, int]:
    """
    山盘：坐山宫在运盘上的星数入中，依坐山阴阳定顺逆

    Args:
        yun_pan: 运盘（{宫位: 星数}）
        shan: 坐山（如 '子'）

    Returns:
        {宫位: 星数} — 山盘
    """
    shan_palace = SHAN_TO_PALACE.get(shan)
    if not shan_palace:
        raise ValueError(f"未知坐山：{shan}")
    # 坐山宫在运盘上的星数 = 山盘入中星
    start_star = yun_pan[shan_palace]
    # 坐山阴阳 → 顺逆
    yin_yang = SHAN_YIN_YANG.get(shan, '阳')
    direction = '顺' if yin_yang == '阳' else '逆'
    return _fly(start_star, direction)


def make_xiang_pan(yun_pan: dict[str, int], xiang: str) -> dict[str, int]:
    """
    向盘：向首宫在运盘上的星数入中，依向首阴阳定顺逆
    """
    xiang_palace = SHAN_TO_PALACE.get(xiang)
    if not xiang_palace:
        raise ValueError(f"未知向首：{xiang}")
    start_star = yun_pan[xiang_palace]
    yin_yang = SHAN_YIN_YANG.get(xiang, '阳')
    direction = '顺' if yin_yang == '阳' else '逆'
    return _fly(start_star, direction)


def make_complete_pan(shan: str, xiang: Optional[str] = None,
                      yun: Optional[int] = None,
                      year: Optional[int] = None) -> dict:
    """
    完整排盘：运盘 + 山盘 + 向盘 → 九宫 (运·山·向) 三元组

    Args:
        shan: 坐山（如 '子'）
        xiang: 向首（如 '午'），不传则自动用 SHAN_TO_XIANG 推
        yun: 运号（1-9），不传则根据年份推当前运
        year: 年份（用于推运），不传则用当前年份

    Returns:
        {
            yun, shan, xiang, direction_shan, direction_xiang,
            yun_pan, shan_pan, xiang_pan,
            palaces: [ {宫位, 运, 山, 向, shan_xiang组合, ...}, ... ]
        }
    """
    # 1. 运
    yun = yun or get_current_yun(year)

    # 2. 向首（自动推）
    if xiang is None:
        xiang = SHAN_TO_XIANG.get(shan)
        if not xiang:
            raise ValueError(f"无法从坐山 {shan} 推向首（请显式传入 xiang）")

    # 3. 三盘
    yun_pan = make_yun_pan(yun)
    shan_pan = make_shan_pan(yun_pan, shan)
    xiang_pan = make_xiang_pan(yun_pan, xiang)

    # 4. 顺逆信息（供展示用）
    shan_palace = SHAN_TO_PALACE.get(shan)
    xiang_palace = SHAN_TO_PALACE.get(xiang)
    shan_yy = SHAN_YIN_YANG.get(shan, '阳')
    xiang_yy = SHAN_YIN_YANG.get(xiang, '阳')

    # 5. 汇总九宫三元组
    palaces = []
    for palace in FLYING_ORDER:
        y = yun_pan[palace]
        s = shan_pan[palace]
        x = xiang_pan[palace]
        palaces.append({
            'palace': palace,
            'luoshu': PALACE_LUOSHU[palace],
            'yun_star': y,
            'shan_star': s,
            'xiang_star': x,
            'shan_xiang': f"{s}{x}",  # 山向两数对（如 '99', '36'）
        })

    return {
        'yun': yun,
        'yun_dynasty': f"{['上','中','下'][(yun-1)//3]}元",
        'shan': shan,
        'xiang': xiang,
        'shan_palace': shan_palace,
        'xiang_palace': xiang_palace,
        'shan_yin_yang': shan_yy,
        'xiang_yin_yang': xiang_yy,
        'shan_direction': '顺飞' if shan_yy == '阳' else '逆飞',
        'xiang_direction': '顺飞' if xiang_yy == '阳' else '逆飞',
        'yun_pan': yun_pan,
        'shan_pan': shan_pan,
        'xiang_pan': xiang_pan,
        'palaces': palaces,
    }


# ═══════════════════════════════════════════════════════════
# 快速验证：胡长虹宅盘（九运·子山午向）
# 预期结果（spum-玄空飞星.md §5.2）：
#   坎宫 = 5·9·9（双九当旺）
#   中宫 = 9·5·4（五四·五黄）
#   兑宫 = 2·3·6（三六·大壮）
# ═══════════════════════════════════════════════════════════
if __name__ == '__main__':
    result = make_complete_pan('子', '午', yun=9)
    print(f"=== 九运·子山午向 ===\n")
    print(f"运星入中9 顺飞；坐山子(阴)→坎5入中逆飞；向首午(阳)→离4入中顺飞\n")

    # 按宫位展示（地理顺序）
    geo_order = ['离', '坤', '兑', '乾', '中', '巽', '震', '艮', '坎']
    print("九宫终盘（运·山·向）：")
    for p in result['palaces']:
        if p['palace'] in geo_order:
            tag = ""
            if p['shan_xiang'] == '99': tag = " ← 双九当旺"
            elif p['shan_xiang'] in ('45','54','25','52','55','56','65','58','85'): tag = " ← 五黄大煞"
            elif p['shan_xiang'] in ('27','72'): tag = " ← 病符二黑"
            elif p['shan_xiang'] == '36': tag = " ← 三六大壮·金木相战"
            print(f"  {p['palace']:4s} {p['yun_star']}·{p['shan_star']}·{p['xiang_star']}  山向{p['shan_xiang']}{tag}")

    print(f"\n验证坎宫=5·9·9: ", end="")
    kan = next(p for p in result['palaces'] if p['palace'] == '坎')
    assert kan['yun_star'] == 5 and kan['shan_star'] == 9 and kan['xiang_star'] == 9
    print("✅")

    print(f"验证兑宫=2·3·6: ", end="")
    dui = next(p for p in result['palaces'] if p['palace'] == '兑')
    assert dui['yun_star'] == 2 and dui['shan_star'] == 3 and dui['xiang_star'] == 6
    print("✅")

    print(f"验证中宫=9·5·4: ", end="")
    zhong = next(p for p in result['palaces'] if p['palace'] == '中')
    assert zhong['yun_star'] == 9 and zhong['shan_star'] == 5 and zhong['xiang_star'] == 4
    print("✅")

    print("\n🎉 胡长虹宅盘排盘验证通过！")
