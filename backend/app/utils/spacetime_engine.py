"""spacetime_engine — 青囊时空引擎核心

核心理念（v2 增益中庸范式）：
  五行调和绝不是"补缺抑强"——木弱补木、火旺泻火，这是旧范式。
  秘术实践反推的底层规律：**通过增益中庸节点治理尖峰，而非直接处理尖峰和凹谷**。
  详见 spum-core/五行/地元/spum-卦组合化解.md §三·附。

  为什么旧范式错：
    直接处理尖峰/凹谷 → 在五形闭环上硬掰 → 力沿回路传递 → 制造新失衡（补木→木生火→火克金→...）
  为什么新范式对：
    尖峰和凹谷是耦合链同一个断链的两个侧面。
    不去碰尖峰本身，强化那个"本该调节尖峰但力不从心"的中庸节点，
    让耦合链恢复自调节节奏 → 尖峰自然收敛、凹谷自然填补。

  旧范式：土弱 → 补土（直接补凹谷）                              ❌
  新范式：土弱且木旺 → 增益火形（木→土链的衔接断了，补火让链条通） ✅

三层架构：
  L1 时空上下文   spacetime_context(dt, birthplace) → 四柱/节气/旺相/建除/奇门
  L2 调候引擎     tiao_hou(时空上下文, v_base)     → 找耦合链断链点 → 增益建议
  L3 建议管线     spacetime_advice(brief, 时空, v_base) → 最终建议
"""

from datetime import datetime, date, time
from typing import Optional
import math

# ═══════════════════════════════════════════════════════════
# L1 时空上下文
# ═══════════════════════════════════════════════════════════

# 天干地支
TIANGAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
DIZHI   = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']
TIANGAN_WUXING = {'甲': 'wood', '乙': 'wood', '丙': 'fire', '丁': 'fire',
                  '戊': 'earth', '己': 'earth', '庚': 'metal', '辛': 'metal',
                  '壬': 'water', '癸': 'water'}
DIZHI_WUXING   = {'子': 'water', '丑': 'earth', '寅': 'wood', '卯': 'wood',
                  '辰': 'earth', '巳': 'fire', '午': 'fire', '未': 'earth',
                  '申': 'metal', '酉': 'metal', '戌': 'earth', '亥': 'water'}
DIZHI_YIN_YANG = {'子': '阳', '丑': '阴', '寅': '阳', '卯': '阴',
                  '辰': '阳', '巳': '阴', '午': '阳', '未': '阴',
                  '申': '阳', '酉': '阴', '戌': '阳', '亥': '阴'}
# 月令：正月寅起（立春后为寅月），节气换月非农历初一
YUEJIAN = {'寅': 1, '卯': 2, '辰': 3, '巳': 4, '午': 5, '未': 6,
           '申': 7, '酉': 8, '戌': 9, '亥': 10, '子': 11, '丑': 12}

# 旺相休囚死（基于月令当令五行）
# 当令 = 旺；我生 = 相；生我 = 休；我克 = 囚；克我 = 死
# 五行生克：木生火、火生土、土生金、金生水、水生木
#          木克土、土克水、水克火、火克金、金克木
SHENG = {'wood': 'fire', 'fire': 'earth', 'earth': 'metal', 'metal': 'water', 'water': 'wood'}
KE    = {'wood': 'earth', 'earth': 'water', 'water': 'fire', 'fire': 'metal', 'metal': 'wood'}
# 旺相休囚死：当令者旺；旺所生者相；生旺者休；旺所克者囚；克旺者死
def wuxing_status(lingshou_wuxing: str, target_wuxing: str) -> str:
    """给定当令五行和目标五行，返回旺/相/休/囚/死"""
    if lingshou_wuxing == target_wuxing: return '旺'
    if SHENG[lingshou_wuxing] == target_wuxing: return '相'
    if SHENG[target_wuxing] == lingshou_wuxing: return '休'
    if KE[lingshou_wuxing] == target_wuxing: return '囚'
    if KE[target_wuxing] == lingshou_wuxing: return '死'
    return ''

# 旺相休囚死 → 强度系数（用于调候加权）
STATUS_WEIGHT = {'旺': 1.4, '相': 1.2, '休': 1.0, '囚': 0.8, '死': 0.6}

# 建除十二神（从月建起算，顺排）
JIANCHU = ['建', '除', '满', '平', '定', '执', '破', '危', '成', '收', '开', '闭']

# 玉匣记宜忌（基于建除 + 日干支）
# 简化版：建除吉凶 + 宜忌关键词
JIANCHU_GOOD  = {'除': '除旧迎新', '满': '祭祀祈福', '定': '安床', '执': '捕捉', '成': '开市', '开': '出行求财'}
JIANCHU_BAD   = {'建': '动土', '破': '诸事不宜', '危': '登高', '收': '出行', '闭': '开市'}

# 十二地支藏干（用于节气/时辰精化）
DIZHI_CANGGAN = {
    '子': ['癸'],
    '丑': ['己', '癸', '辛'],
    '寅': ['甲', '丙', '戊'],
    '卯': ['乙'],
    '辰': ['戊', '乙', '癸'],
    '巳': ['丙', '庚', '戊'],
    '午': ['丁', '己'],
    '未': ['己', '丁', '乙'],
    '申': ['庚', '壬', '戊'],
    '酉': ['辛'],
    '戌': ['戊', '辛', '丁'],
    '亥': ['壬', '甲'],
}


# ═══════════════════════════════════════════════════════════
# 时间推算（用 lunar_python，不可用时 fallback）
# ═══════════════════════════════════════════════════════════

def _get_lunar():
    """获取 lunar_python（优先直接 import，fallback 到 qingmeng_engine vendor）"""
    try:
        from lunar_python import Solar, Lunar
        return Solar, Lunar
    except ImportError:
        try:
            from qingmeng_engine._vendor.lunar_python import Solar, Lunar
            return Solar, Lunar
        except ImportError:
            return None, None


def compute_sizhu(dt: datetime, birthplace: Optional[str] = None) -> dict:
    """计算四柱（年月日时）天干地支
    
    Args:
        dt: 时间点（默认北京时间）
        birthplace: 出生地（用于真太阳时校正，暂简化为不校正）
    
    Returns:
        { year: '甲辰', month: '丁卯', day: '己丑', hour: '庚午',
          ganzhi: { year: ('甲','辰'), ... },
          wuxing: { year: 'wood', month: 'fire', day: 'earth', hour: 'metal' } }
    """
    Solar, Lunar = _get_lunar()
    if Solar and Lunar:
        try:
            s = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
            l = s.getLunar()
            year_ganzhi = l.getYearInGanZhiExact()
            month_ganzhi = l.getMonthInGanZhiExact()
            day_ganzhi = l.getDayInGanZhiExact()
            hour_ganzhi = l.getTimeInGanZhi()
            ganzhi = {
                'year':  (year_ganzhi[0],  year_ganzhi[1]),
                'month': (month_ganzhi[0], month_ganzhi[1]),
                'day':   (day_ganzhi[0],   day_ganzhi[1]),
                'hour':  (hour_ganzhi[0],  hour_ganzhi[1]),
            }
            wuxing = {
                'year':  TIANGAN_WUXING[ganzhi['year'][0]],
                'month': DIZHI_WUXING[ganzhi['month'][1]],   # 月令用地支五行
                'day':   TIANGAN_WUXING[ganzhi['day'][0]],
                'hour':  DIZHI_WUXING[ganzhi['hour'][1]],
            }
            return {
                'year': year_ganzhi,
                'month': month_ganzhi,
                'day': day_ganzhi,
                'hour': hour_ganzhi,
                'ganzhi': ganzhi,
                'wuxing': wuxing,
                'source': 'lunar_python',
            }
        except Exception:
            pass

    # Fallback：简化干支推算（误差在 1-2 天内，仅供视觉展示）
    return _fallback_sizhu(dt)


def _fallback_sizhu(dt: datetime) -> dict:
    """简化干支推算 fallback"""
    # 年干支（近似，立春前仍算前一年）
    y = dt.year
    year_ganzhi = TIANGAN[(y - 4) % 10] + DIZHI[(y - 4) % 12]
    # 月干支（近似，节气边界不准）
    month_zhi_idx = (dt.month + 1) % 12  # 正月=寅=2
    month_ganzhi = TIANGAN[(y * 5 + dt.month + 2) % 10] + DIZHI[month_zhi_idx]
    # 日干支（用已知基准推算）
    DAY_BASE = datetime(1900, 1, 1)  # 甲戌日
    days_since = (dt.date() - DAY_BASE.date()).days
    day_idx = (days_since + 10) % 60
    day_ganzhi = TIANGAN[day_idx % 10] + DIZHI[day_idx % 12]
    # 时干支
    hour_idx = (dt.hour + 1) // 2 % 12
    hour_ganzhi = TIANGAN[(day_idx % 10 + hour_idx) % 10] + DIZHI[hour_idx]

    ganzhi = {
        'year':  (year_ganzhi[0], year_ganzhi[1]),
        'month': (month_ganzhi[0], month_ganzhi[1]),
        'day':   (day_ganzhi[0], day_ganzhi[1]),
        'hour':  (hour_ganzhi[0], hour_ganzhi[1]),
    }
    wuxing = {
        'year':  TIANGAN_WUXING[ganzhi['year'][0]],
        'month': DIZHI_WUXING[ganzhi['month'][1]],
        'day':   TIANGAN_WUXING[ganzhi['day'][0]],
        'hour':  DIZHI_WUXING[ganzhi['hour'][1]],
    }
    return {
        'year': year_ganzhi, 'month': month_ganzhi,
        'day': day_ganzhi, 'hour': hour_ganzhi,
        'ganzhi': ganzhi, 'wuxing': wuxing,
        'source': 'fallback_degraded', 'degraded': True,
    }


def compute_jieqi(dt: datetime) -> dict:
    """计算节气归属 + 最近节气信息"""
    Solar, Lunar = _get_lunar()
    if Solar:
        try:
            s = Solar.fromYmd(dt.year, dt.month, dt.day)
            current_jq = s.getJieQiTable()
            # 简化：返回当前月所有节气 + 下一个节气
            return {
                'solar_term_text': s.getSolarTermText(),
                'current_term': s.getCurrentJieQi(),
                'source': 'lunar_python',
            }
        except Exception:
            pass
    # Fallback：用近似表
    return {'solar_term_text': '', 'current_term': _approx_jieqi(dt), 'source': 'fallback'}


def _approx_jieqi(dt: datetime) -> str:
    """简化节气近似（精确到 ±2 天）"""
    # 24 节气近似日期表
    TERMS = [
        ('小寒', 1, 5), ('大寒', 1, 20), ('立春', 2, 4), ('雨水', 2, 19),
        ('惊蛰', 3, 6), ('春分', 3, 21), ('清明', 4, 5), ('谷雨', 4, 20),
        ('立夏', 5, 6), ('小满', 5, 21), ('芒种', 6, 6), ('夏至', 6, 21),
        ('小暑', 7, 7), ('大暑', 7, 23), ('立秋', 8, 8), ('处暑', 8, 23),
        ('白露', 9, 8), ('秋分', 9, 23), ('寒露', 10, 8), ('霜降', 10, 23),
        ('立冬', 11, 7), ('小雪', 11, 22), ('大雪', 12, 7), ('冬至', 12, 22),
    ]
    m, d = dt.month, dt.day
    current = None
    next_term = None
    for i, (name, tm, td) in enumerate(TERMS):
        if (m, d) >= (tm, td):
            current = name
        elif next_term is None:
            next_term = name
    return current or '冬至'


def compute_jianchu(month_zhi: str, day_zhi: str) -> str:
    """计算建除十二神
    
    建除规则：从月建起算，日支与月建相同则为"建"，顺排
    """
    month_idx = DIZHI.index(month_zhi)
    day_idx = DIZHI.index(day_zhi)
    offset = (day_idx - month_idx) % 12
    return JIANCHU[offset]


def compute_wuxing_status_dict(lingshou_wuxing: str) -> dict:
    """返回当令五行下，各五行的旺相休囚死状态"""
    return {w: wuxing_status(lingshou_wuxing, w) for w in ['wood', 'fire', 'earth', 'metal', 'water']}


def spacetime_context(dt: datetime, birthplace: Optional[str] = None) -> dict:
    """时空上下文完整计算
    
    Returns:
        {
          sizhu: { year/month/day/hour, ganzhi, wuxing },
          lingshou: 'wood',       # 月令当令五行（最关键的调候锚点）
          wuxing_status: { wood: '旺', fire: '休', earth: '死', metal: '囚', water: '相' },
          wuxing_weight: { wood: 1.4, fire: 1.0, ... },  # 状态→强度系数
          jianchu: '建',          # 建除十二神
          jianchu_advice: { good: '...', bad: '...' },
          jieqi: { current_term: '...', ... },
          hour_wuxing: 'fire',    # 时辰五行
          day_wuxing: 'earth',    # 日五行（日干）
        }
    """
    sizhu = compute_sizhu(dt, birthplace)
    # 月令当令五行 = 月支五行
    month_zhi = sizhu['ganzhi']['month'][1]
    lingshou = sizhu['wuxing']['month']
    
    wuxing_status = compute_wuxing_status_dict(lingshou)
    wuxing_weight = {w: STATUS_WEIGHT[s] for w, s in wuxing_status.items()}
    
    # 建除
    day_zhi = sizhu['ganzhi']['day'][1]
    jianchu = compute_jianchu(month_zhi, day_zhi)
    jianchu_advice = {
        'good': JIANCHU_GOOD.get(jianchu, ''),
        'bad':  JIANCHU_BAD.get(jianchu, ''),
    }
    
    # 节气
    jieqi = compute_jieqi(dt)
    
    return {
        'sizhu': sizhu,
        'lingshou': lingshou,
        'lingshou_gz': sizhu['month'],
        'wuxing_status': wuxing_status,
        'wuxing_weight': wuxing_weight,
        'jianchu': jianchu,
        'jianchu_advice': jianchu_advice,
        'jieqi': jieqi,
        'hour_wuxing': sizhu['wuxing']['hour'],
        'day_wuxing': sizhu['wuxing']['day'],
        'day_gan': sizhu['ganzhi']['day'][0],
        'day_zhi': day_zhi,
        'day_gz': sizhu['day'],
        'is_degraded': sizhu.get('degraded', False),
    }


# ═══════════════════════════════════════════════════════════
# L2 调候引擎：时空 × 体质 → 动态调候建议
# ═══════════════════════════════════════════════════════════

# 五形中文名
WUXING_CN = {'wood': '木', 'fire': '火', 'earth': '土', 'metal': '金', 'water': '水'}

# 调候方向（v2 中庸治理范式）：
#   旧：补/泻/养/平 —— 直接处理尖峰/凹谷
#   新：增益耦合链里的断链节点，让链条自恢复
#   direction 取值：
#     '增益'       —— 断链节点在旺相时节，顺势借力
#     '增益待时'   —— 断链节点在死囚时节，此时增益虚不受补，等它活跃时辰
#     '顺势增益'   —— 当令五行恰好就是断链节点，天赐良机
#     '不干预'     —— 链条自洽，无需动作

def tiao_hou_engine(v_base: dict, ctx: dict) -> dict:
    """核心调候引擎（v2 增益中庸范式）
    
    旧范式（已废弃）：对每个形独立判断 → is_weak→补/养；is_strong→泻/平
      问题：直接处理尖峰/凹谷，在闭环上硬掰，力沿回路传递制造新失衡
    
    新范式：找耦合链断链点 → 增益那个中庸节点
      原理：
        五形 SHENG 链 = wood→fire→earth→metal→water→wood
        每个节点同时是上游的"所生"（承接上游输出）和下游的"生我"（向下游输送）
        某个节点弱了 → 它的上游输出没人接 → 上游堆积成尖峰
                        它的下游输入没人送 → 下游匮乏成凹谷
        尖峰和凹谷是同一个断链的两个侧面，不独立存在
        治理 = 增益断链节点，让链条恢复 → 尖峰自然收敛、凹谷自然填补
      详见 spum-core/五行/地元/spum-卦组合化解.md §三·附
    
    Returns:
      {
        weighted_v: {...},            # 时空加权后的向量
        priorities: [...],            # 断链节点增益建议（通常 1-2 条）
        avoid_now: [...],             # 当下不宜（兼容）
        opportunities: [...],         # 天赐良机（兼容）
        window_tips: [...],           # 时辰窗口提示（兼容）
        summary: str,                 # 一句话总结
        broken_chain: {...},          # 新增：断链分析详情（供前端展示）
      }
    """
    wuxing_weight = ctx['wuxing_weight']
    lingshou = ctx['lingshou']
    hour_wx = ctx['hour_wuxing']
    
    # 1. 时空加权体质（保留，和旧版相同）
    weighted_v = {}
    for k in ['wood', 'fire', 'earth', 'metal', 'water']:
        raw = v_base.get(k, 50)
        w = wuxing_weight.get(k, 1.0)
        weighted_v[k] = round(raw * (0.6 + 0.4 * w), 1)
    
    # 2. 找耦合链断链点
    #    每个节点的"链上地位" = weighted_v[node]
    #    SHENG 链: wood→fire→earth→metal→water→wood
    #    断链点 = weighted_v 最小的那个节点（它同时卡了上游输出和下游输入）
    chain_nodes = ['wood', 'fire', 'earth', 'metal', 'water']
    sorted_nodes = sorted(chain_nodes, key=lambda n: weighted_v[n])
    
    # ── 平衡边界：五形差值 < 5 → 链条自洽，不干预 ──
    max_v = max(weighted_v.values())
    min_v = min(weighted_v.values())
    if max_v - min_v < 5:
        return {
            'weighted_v': weighted_v,
            'priorities': [],
            'avoid_now': [],
            'opportunities': [],
            'window_tips': [],
            'summary': f'当令{WUXING_CN[lingshou]}形{ctx["wuxing_status"][lingshou]}，五形链条自洽，无需干预',
            'broken_chain': {'broken_node': None, 'peaks': [], 'valleys': []},
        }
    
    broken_node = sorted_nodes[0]  # 最弱 = 断链点
    second_weakest = sorted_nodes[1] if len(sorted_nodes) > 1 else None
    
    # 断链分析详情
    prev_node = [k for k, v in SHENG.items() if v == broken_node][0]  # 生 broken 的
    next_node = SHENG[broken_node]  # broken 生的
    
    # ── KE 链冲突检测（金木相战型） ──
    #    KE 链: wood→earth→water→fire→metal→wood
    #    相邻两个都 > 60 = 冲突（如 metal>60 且 wood>60 = 金木相战）
    #    调和节点 = SHENG 链上的中间相位（metal→water→wood → water 是调和节点）
    ke_conflict = None
    for a, b in KE.items():  # KE[a] = b 表示 a 克 b
        if weighted_v.get(a, 50) > 60 and weighted_v.get(b, 50) > 60:
            # a 克 b 且两者都旺 → 找 SHENG 调和节点
            # 调和节点 = SHENG[a]（a 所生 = SHENG 链上 a 之后的节点）
            mediator = SHENG.get(a)
            if mediator and mediator != a and mediator != b:
                ke_conflict = {'a': a, 'b': b, 'mediator': mediator}
                # 如果调和节点恰好就是 SHENG 断链点 → 评分加倍
                if mediator == broken_node:
                    second_weakest = None  # 不生成次要点位了
                    break
    
    # 因断链导致的尖峰（上游堆积）和凹谷（下游匮乏）
    peaks = []
    valleys = []
    if weighted_v[prev_node] > 55:
        peaks.append(prev_node)
    if weighted_v[next_node] < 45:
        valleys.append(next_node)
    # KE 冲突的两个强节点也是尖峰
    if ke_conflict:
        for p in [ke_conflict['a'], ke_conflict['b']]:
            if p not in peaks and weighted_v[p] > 55:
                peaks.append(p)
    
    # 3. 对断链节点判定增益窗口 + opportunities
    broken_status = ctx['wuxing_status'][broken_node]
    opportunities = []  # ✅ 恢复 opportunities 生成
    
    if broken_node == lingshou:
        # 断链节点恰好是当令五行 → 天赐良机
        direction = '顺势增益'
        reason = (
            f'五形{WUXING_CN[prev_node]}→{WUXING_CN[broken_node]}→{WUXING_CN[next_node]}链中，'
            f'{WUXING_CN[broken_node]}形力弱承上启下断链'
            + (f'（导致{WUXING_CN[prev_node]}形堆积成峰）' if peaks else '')
            + (f'（导致{WUXING_CN[next_node]}形匮乏成谷）' if valleys else '')
            + f'。当下当令{WUXING_CN[broken_node]}形{broken_status}，顺势增益，链条通 → 尖峰自消、凹谷自填'
        )
        opportunities.append({
            'msg': f'断链节点{WUXING_CN[broken_node]}形恰为当令{broken_status}，顺势增益效倍',
            'wuxing': broken_node,
        })
    elif broken_status in ('旺', '相'):
        direction = '增益'
        reason = (
            f'{WUXING_CN[prev_node]}→{WUXING_CN[broken_node]}→{WUXING_CN[next_node]}链断于{WUXING_CN[broken_node]}形'
            + (f'（{WUXING_CN[prev_node]}形堆积为峰）' if peaks else '')
            + (f'（{WUXING_CN[next_node]}形匮乏为谷）' if valleys else '')
            + f'。当下{WUXING_CN[broken_node]}形{broken_status}，增益{WUXING_CN[broken_node]}让链条恢复自调节'
        )
    elif broken_status in ('休', '囚'):
        direction = '增益'
        reason = (
            f'{WUXING_CN[prev_node]}→{WUXING_CN[broken_node]}→{WUXING_CN[next_node]}链断于{WUXING_CN[broken_node]}形'
            + f'。当下{WUXING_CN[broken_node]}形{broken_status}，增益但不宜过猛，等申时/子时等活跃窗口效果更佳'
        )
    else:  # 死
        direction = '增益待时'
        reason = (
            f'{WUXING_CN[prev_node]}→{WUXING_CN[broken_node]}→{WUXING_CN[next_node]}链断于{WUXING_CN[broken_node]}形'
            + f'。当下{WUXING_CN[broken_node]}形死，此时增益虚不受补，换{WUXING_CN[broken_node]}活跃时辰再调'
        )
    
    # KE 冲突追加到 reason
    if ke_conflict:
        reason += f' 同时KE链{WUXING_CN[ke_conflict["a"]]}克{WUXING_CN[ke_conflict["b"]]}两旺相战，增益{WUXING_CN[ke_conflict["mediator"]]}形即为调和节点'
    
    # 评分（断链越严重分越高）
    broken_dev = 50 - weighted_v[broken_node]
    peak_penalty = sum(weighted_v[p] - 55 for p in peaks) if peaks else 0
    score = max(broken_dev, broken_dev + peak_penalty)
    if ke_conflict and ke_conflict['mediator'] == broken_node:
        score *= 1.5  # KE 冲突与 SHENG 断链指向同一节点 → 升级
    
    priorities = [{
        'wuxing': broken_node,
        'cn': WUXING_CN[broken_node],
        'raw': v_base.get(broken_node, 50),
        'weighted': weighted_v[broken_node],
        'status': broken_status,
        'direction': direction,
        'reason': reason,
        'score': round(score, 1),
        'chain_from': WUXING_CN[prev_node],
        'chain_to': WUXING_CN[next_node],
        'peaks': [WUXING_CN[p] for p in peaks],
        'valleys': [WUXING_CN[v] for v in valleys],
        'ke_conflict': WUXING_CN.get(ke_conflict['a'], '') + '克' + WUXING_CN.get(ke_conflict['b'], '') if ke_conflict else None,
    }]
    
    # 如果第二弱节点也偏弱（和最弱差距 < 5），也生成一条
    if second_weakest and (weighted_v[broken_node] - weighted_v[second_weakest] < 5):
        b2_status = ctx['wuxing_status'][second_weakest]
        p2 = [k for k, v in SHENG.items() if v == second_weakest][0]
        n2 = SHENG[second_weakest]
        priorities.append({
            'wuxing': second_weakest,
            'cn': WUXING_CN[second_weakest],
            'raw': v_base.get(second_weakest, 50),
            'weighted': weighted_v[second_weakest],
            'status': b2_status,
            'direction': '增益',
            'reason': f'同时{WUXING_CN[p2]}→{WUXING_CN[second_weakest]}→{WUXING_CN[n2]}链也偏弱，次要点位增益',
            'score': round(50 - weighted_v[second_weakest], 1),
            'chain_from': WUXING_CN[p2],
            'chain_to': WUXING_CN[n2],
            'peaks': [],
            'valleys': [],
        })
    
    priorities.sort(key=lambda x: -x['score'])
    
    # 4. 当下不宜 —— 当令五行克到凹谷节点 → 避
    avoid_now = []
    opportunities = []
    if lingshou in KE:
        ke_target = KE[lingshou]  # 当令所克
        if ke_target in valleys or weighted_v.get(ke_target, 50) < 45:
            avoid_now.append({
                'msg': f'当下{WUXING_CN[lingshou]}形旺，克{WUXING_CN[ke_target]}形（凹谷），不宜猛补{WUXING_CN[ke_target]}',
                'wuxing': ke_target,
            })
    
    # 5. 时辰窗口提示
    window_tips = []
    if hour_wx == broken_node:
        window_tips.append(f'当下时辰属{WUXING_CN[hour_wx]}形，正是断链节点活跃时，增益效倍')
    
    # 6. 一句话总结
    top = priorities[0] if priorities else None
    if top:
        chain_desc = f'{top["chain_from"]}→{top["cn"]}→{top["chain_to"]}'
        peak_desc = f'，{"/".join(top["peaks"])}形堆积为峰' if top['peaks'] else ''
        valley_desc = f'，{"/".join(top["valleys"])}形匮乏为谷' if top['valleys'] else ''
        summary = f'{WUXING_CN[lingshou]}形{ctx["wuxing_status"][lingshou]}。{chain_desc}链断于{top["cn"]}形{peak_desc}{valley_desc}——{top["direction"]}，让链条自恢复'
    else:
        summary = f'当令{WUXING_CN[lingshou]}形{ctx["wuxing_status"][lingshou]}，五形链条自洽'
    
    return {
        'weighted_v': weighted_v,
        'priorities': priorities,
        'avoid_now': avoid_now,
        'opportunities': opportunities,
        'window_tips': window_tips,
        'summary': summary,
        'broken_chain': {
            'broken_node': broken_node,
            'prev': prev_node,
            'next': next_node,
            'peaks': peaks,
            'valleys': valleys,
        },
    }


def spacetime_advice(v_base: dict, ctx: dict, tiao_hou: dict, 
                     base_advice: Optional[dict] = None) -> dict:
    """时空调候后的最终建议
    
    Args:
        v_base: 用户五形向量
        ctx: 时空上下文
        tiao_hou: 调候引擎输出
        base_advice: qingmeng-engine daily_brief 返回的建议（可选）
    
    Returns:
        覆盖/增强后的建议字典
    """
    todos = []
    avoidances = []
    
    # 从调候引擎生成建议（v2 增益中庸范式）
    for p in tiao_hou['priorities']:
        chain_desc = f'{p.get("chain_from","?")}→{p["cn"]}→{p.get("chain_to","?")}'
        if p['direction'] in ('增益', '顺势增益'):
            emoji = '✨' if p['direction'] == '顺势增益' else '🔧'
            todos.append({
                'title': f'{emoji} 增益{p["cn"]}形 · {_food_suggestion(p["wuxing"])}',
                'desc': f'五形{chain_desc}链断于{p["cn"]}形。增益{p["cn"]}让链条自恢复 → 尖峰自消、凹谷自填。{p["reason"]}',
                'priority': 'high' if p['direction'] == '顺势增益' else 'high',
                'wuxing': p['wuxing'],
                'source': 'spacetime_tiao_hou',
                'direction': p['direction'],
                'broken_chain': chain_desc,
                'peaks': p.get('peaks', []),
                'valleys': p.get('valleys', []),
            })
        elif p['direction'] == '增益待时':
            avoidances.append({
                'title': f'⏸ {p["cn"]}形活跃时辰再增益',
                'desc': f'五形{chain_desc}链断于{p["cn"]}形，但当下{p["status"]}虚不受补。{p["reason"]}',
                'priority': 'medium',
                'wuxing': p['wuxing'],
                'source': 'spacetime_tiao_hou',
                'direction': p['direction'],
                'broken_chain': chain_desc,
            })
    
    # 当下不宜
    for a in tiao_hou['avoid_now']:
        avoidances.append({
            'title': f'⚠️ {a["msg"]}',
            'desc': '顺应天时节律，避之则吉',
            'priority': 'high',
            'wuxing': a['wuxing'],
            'source': 'spacetime_avoid',
        })
    
    # 天赐良机
    for o in tiao_hou['opportunities']:
        todos.append({
            'title': f'✨ {o["msg"]}',
            'desc': '趁当令旺势，事半功倍',
            'priority': 'high',
            'wuxing': o['wuxing'],
            'source': 'spacetime_opportunity',
        })
    
    # 时辰窗口
    for w in tiao_hou['window_tips']:
        todos.append({
            'title': w,
            'desc': '当下时辰契合此形，即时行动',
            'priority': 'high',
            'source': 'spacetime_window',
        })
    
    # 建除宜忌
    jianchu = ctx['jianchu']
    if ctx['jianchu_advice']['good']:
        todos.append({
            'title': f'建除·{jianchu}日宜：{ctx["jianchu_advice"]["good"]}',
            'desc': '《玉匣记》择吉',
            'priority': 'medium',
            'source': 'jianchu',
        })
    if ctx['jianchu_advice']['bad']:
        avoidances.append({
            'title': f'建除·{jianchu}日忌：{ctx["jianchu_advice"]["bad"]}',
            'desc': '《玉匣记》避凶',
            'priority': 'medium',
            'source': 'jianchu',
        })
    
    # 如果有 base_advice（qingmeng-engine 的 daily_brief），合并调候建议到前部
    # 调候建议优先级更高
    if base_advice:
        if base_advice.get('todos'):
            todos = todos + base_advice['todos']
        if base_advice.get('avoidances'):
            avoidances = avoidances + base_advice['avoidances']
    
    return {
        'todos': todos,
        'avoidances': avoidances,
        'spacetime_summary': tiao_hou['summary'],
        'spacetime_ctx': {
            'sizhu': ctx['sizhu'],
            'lingshou': ctx['lingshou_gz'],
            'wuxing_status': ctx['wuxing_status'],
            'jianchu': ctx['jianchu'],
            'jieqi': ctx['jieqi'].get('current_term', ''),
        },
    }


def _food_suggestion(wuxing: str) -> str:
    """补某形的饮食建议（协纪辩方风格）"""
    return {
        'wood': '菊花茶 + 乌梅饮 · 绿色蔬菜',
        'fire': '莲子百合粥 · 避免辛辣',
        'earth': '小米粥 + 山药 · 茯苓饼',
        'metal': '百合莲子 · 白萝卜',
        'water': '银耳雪梨 · 温淡盐水',
    }.get(wuxing, '')

def _action_suggestion(wuxing: str, direction: str = '泻') -> str:
    """泻某形的动作建议"""
    if direction == '泻':
        return {
            'wood': '散步 30min · 八段锦疏木',
            'fire': '温水泡脚 · 避免熬夜',
            'earth': '清淡饮食 · 避免甜腻',
            'metal': '深呼吸 · 扩胸运动',
            'water': '少饮寒凉 · 固水保阴',
        }.get(wuxing, '')
    return ''


# ═══════════════════════════════════════════════════════════
# L3 一站式入口
# ═══════════════════════════════════════════════════════════

def spacetime_daily_brief(v_base: dict, dt: Optional[datetime] = None,
                          birthplace: Optional[str] = None,
                          base_advice: Optional[dict] = None) -> dict:
    """时空调候版 daily_brief — 一站式调用
    
    调用链：
      1. 计算时空上下文（四柱/旺相/建除/节气）
      2. 调候引擎（时空 × 体质 → 动态调候建议）
      3. 合并 base_advice（如果有）
    
    Returns:
        {
          ctx: {...},          # 时空上下文（供前端渲染）
          tiao_hou: {...},     # 调候引擎原始输出
          advice: {...},       # 最终建议（todos / avoidances）
        }
    """
    if dt is None:
        dt = datetime.now()
    
    ctx = spacetime_context(dt, birthplace)
    th = tiao_hou_engine(v_base, ctx)
    advice = spacetime_advice(v_base, ctx, th, base_advice)
    
    return {
        'ctx': {
            'sizhu': ctx['sizhu'],
            'lingshou_gz': ctx['lingshou_gz'],
            'lingshou_cn': WUXING_CN.get(ctx['lingshou'], ctx['lingshou']),
            'wuxing_status': ctx['wuxing_status'],
            'jianchu': ctx['jianchu'],
            'jianchu_advice': ctx['jianchu_advice'],
            'jieqi': ctx['jieqi'].get('current_term', ctx['jieqi'].get('solar_term_text', '')),
            'day_gz': ctx['day_gz'],
            'hour_gz': ctx['sizhu']['hour'],
            'is_degraded': ctx.get('is_degraded', False),
        },
        'tiao_hou': {
            'priorities': th['priorities'],
            'avoid_now': th['avoid_now'],
            'opportunities': th['opportunities'],
            'summary': th['summary'],
        },
        'advice': advice,
    }
