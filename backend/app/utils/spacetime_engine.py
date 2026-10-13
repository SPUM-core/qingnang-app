"""spacetime_engine — 青囊时空引擎核心

核心理念：
  生活建议不能只看"五形偏缺→补"。
  必须结合时空变量（玉匣记择吉、奇门遁甲格局、协纪辩方旺相休囚），
  顺应天时节律，才是真正的识偏调平。

  静态：你土形弱 → 补土  ❌ 刻板
  动态：今日卯月卯日木旺克土 → 此时猛补土虚不受补 → 宜疏肝为先，申时金旺时再健脾 ✅

三层架构：
  L1 时空上下文   spacetime_context(dt, birthplace) → 四柱/节气/旺相/建除/奇门
  L2 调候引擎     tiao_hou(时空上下文, v_base)     → 动态调候建议
  L3 建议管线     spacetime_advice(brief, 时空, v_base) → 最终建议（覆盖 daily_brief）
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

# 调候方向：偏缺形 在 旺相时节 → 补；在 死囚时节 → 养（缓补不猛补）
#          偏旺形 在 旺相时节 → 泻；在 死囚时节 → 平（自然缓解）

def tiao_hou_engine(v_base: dict, ctx: dict) -> dict:
    """核心调候引擎
    
    不是"缺土→补土"，而是"缺土 + 今日卯月木旺克土→先疏肝再健脾"
    
    逻辑：
      1. 计算时空加权体质：v_base × wuxing_weight → 时空偏缺
      2. 对每个偏缺形，判断当下调候窗口（旺相→宜补；死囚→宜养）
      3. 对每个偏旺形，判断当下调候窗口（旺相→宜泻；死囚→平）
      4. 克我形旺 → 避克（先疏克者，再补被克者）
      5. 生我形旺 → 顺势（借力生我）
      6. 结合时辰窗口（某形活跃时辰 → 加强该形调理）
    
    Returns:
      {
        weighted_v: {...},            # 时空加权后的向量
        priorities: [...],            # 调候优先级列表
        avoid_now: [...],             # 当下不宜做的事
        opportunities: [...],         # 当下天赐良机
        window_tips: [...],           # 时辰窗口提示
        summary: str,                 # 一句话总结
      }
    """
    wuxing_weight = ctx['wuxing_weight']
    lingshou = ctx['lingshou']
    hour_wx = ctx['hour_wuxing']
    
    # 1. 时空加权体质
    weighted_v = {}
    for k in ['wood', 'fire', 'earth', 'metal', 'water']:
        raw = v_base.get(k, 50)
        w = wuxing_weight.get(k, 1.0)
        # 加权 = 原始偏缺 × 时空系数
        # 偏缺形在死囚时节 → 加倍虚弱（需要先调节律再补）
        # 偏缺形在旺相时节 → 虚弱被当令之气掩护（可以借力）
        weighted_v[k] = round(raw * (0.6 + 0.4 * w), 1)
    
    # 2. 识别优先级
    #   优先级 = |weighted_v - 50| × 时空权重
    priorities = []
    for k in ['wood', 'fire', 'earth', 'metal', 'water']:
        raw = v_base.get(k, 50)
        w = wuxing_weight.get(k, 1.0)
        deviation = raw - 50
        weighted_dev = deviation * w
        
        status = ctx['wuxing_status'][k]
        is_weak = raw < 45
        is_strong = raw > 65
        
        direction = None  # '补' / '泻' / '养' / '平'
        reason = ''
        
        if is_weak:
            if status in ('旺', '相'):
                # 偏缺但当令旺相 → 顺势借力，补效加倍
                direction = '补'
                reason = f'{WUXING_CN[k]}形偏弱，但当下{status}，借力当令之气补之效倍'
            elif status in ('休', '囚'):
                # 偏缺且当下被囚 → 此时猛补虚不受补，先养
                direction = '养'
                reason = f'{WUXING_CN[k]}形偏弱且当下{status}，猛补虚不受补，宜先养节律'
            else:  # 死
                # 偏缺且当下死 → 避之不及，换时辰
                direction = '换时辰'
                reason = f'{WUXING_CN[k]}形偏弱且当下死，此形调理窗口已过，换该形活跃时辰'
        elif is_strong:
            if status in ('旺', '相'):
                # 偏旺且当令 → 雪上加霜，必须泻
                direction = '泻'
                reason = f'{WUXING_CN[k]}形偏旺且当下{status}，顺势泻之，否则气结'
            elif status in ('休', '囚'):
                # 偏旺但当令休囚 → 自然缓解，平调
                direction = '平'
                reason = f'{WUXING_CN[k]}形偏旺但当下{status}，自然节律已在调平'
            else:  # 死
                direction = '平'
                reason = f'{WUXING_CN[k]}形偏旺且当下死，旺势衰减中'
        else:
            direction = '平'
            reason = f'{WUXING_CN[k]}形中和'
        
        priorities.append({
            'wuxing': k,
            'cn': WUXING_CN[k],
            'raw': raw,
            'weighted': weighted_v[k],
            'status': status,
            'direction': direction,
            'reason': reason,
            'score': abs(weighted_dev) * (1.2 if direction in ('补', '泻') else 0.6),
        })
    
    # 按 score 排序
    priorities.sort(key=lambda x: -x['score'])
    
    # 3. 当下不宜（避免克我形旺×我被克形弱）
    avoid_now = []
    opportunities = []
    
    for k in ['wood', 'fire', 'earth', 'metal', 'water']:
        if k == lingshou:
            # 当令五行
            my_ke = KE[k]      # 我克者
            ke_me = [wk for wk, v in KE.items() if v == k]  # 克我者
            sheng_me = [wk for wk, v in SHENG.items() if v == k]  # 生我者
            
            # 当令旺 × 被克者弱 → 当下不宜碰被克形
            for target in [my_ke]:
                if v_base.get(target, 50) < 45:
                    avoid_now.append({
                        'msg': f'当下{WUXING_CN[k]}形旺，克{WUXING_CN[target]}形，不宜猛补{WUXING_CN[target]}',
                        'wuxing': target,
                    })
            
            # 当令旺 × 生我者弱 → 天赐良机（生我者弱时，我旺可以帮它）
            for target in sheng_me:
                if v_base.get(target, 50) < 45:
                    opportunities.append({
                        'msg': f'当下{WUXING_CN[k]}形旺，能生{WUXING_CN[target]}形，补{WUXING_CN[target]}事半功倍',
                        'wuxing': target,
                    })
    
    # 4. 时辰窗口提示
    window_tips = []
    if hour_wx in ('wood', 'fire', 'metal', 'water', 'earth'):
        for p in priorities:
            if p['wuxing'] == hour_wx:
                window_tips.append(f'当下时辰属{WUXING_CN[hour_wx]}形，宜{p["direction"]}{WUXING_CN[hour_wx]}形')
    
    # 5. 一句话总结
    top = priorities[0] if priorities else None
    if top:
        summary = f'当令{WUXING_CN[lingshou]}形{ctx["wuxing_status"][lingshou]}。{top["cn"]}形{top["direction"]}（{top["reason"]}）'
    else:
        summary = f'当令{WUXING_CN[lingshou]}形{ctx["wuxing_status"][lingshou]}，节律平和'
    
    return {
        'weighted_v': weighted_v,
        'priorities': priorities,
        'avoid_now': avoid_now,
        'opportunities': opportunities,
        'window_tips': window_tips,
        'summary': summary,
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
    
    # 从调候引擎生成建议
    for p in tiao_hou['priorities']:
        if p['direction'] == '补':
            todos.append({
                'title': f'补{p["cn"]}形 · {_food_suggestion(p["wuxing"])}',
                'desc': f'当下{p["status"]}，补之效倍 — {p["reason"]}',
                'priority': 'high',
                'wuxing': p['wuxing'],
                'source': 'spacetime_tiao_hou',
            })
        elif p['direction'] == '泻':
            todos.append({
                'title': f'泻{p["cn"]}形 · {_action_suggestion(p["wuxing"], "泻")}',
                'desc': f'当下{p["status"]}，顺势泻之 — {p["reason"]}',
                'priority': 'high',
                'wuxing': p['wuxing'],
                'source': 'spacetime_tiao_hou',
            })
        elif p['direction'] == '养':
            avoidances.append({
                'title': f'暂不补{p["cn"]}形',
                'desc': p['reason'],
                'priority': 'medium',
                'wuxing': p['wuxing'],
                'source': 'spacetime_tiao_hou',
            })
        elif p['direction'] == '换时辰':
            avoidances.append({
                'title': f'换{p["cn"]}形活跃时辰再调理',
                'desc': p['reason'],
                'priority': 'low',
                'wuxing': p['wuxing'],
                'source': 'spacetime_tiao_hou',
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
