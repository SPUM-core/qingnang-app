"""SPUM 体质轨迹算法 — SPUM2611 + 青囊中医总纲 迭代

算法版本: spum_computeHealthBounds_v2
核心公理: 关系定义存在 → S五维健康向量 → σ空间密度 → dv/dt≤const
坐标系:   v2: S向量本体层 + 凸多面体H边界判定 + 离散帧动力学

v1 向后兼容: 所有 v1 函数保持不变，新增 v2 模块在文件末尾

v2 迭代点（SPUM2611/2610/knowledge 理论注入）:
  1. ✅ S 五维健康向量 + 先天基底 S₀ + S_effective 归一化
  2. ✅ 健康凸多面体 H（约束不等式组）+ margin 判定 + Touch 集合 + 越界深度
  3. ✅ σ 空间密度场 → 健康密度标量（∇σ → 收敛/发散）
  4. ✅ 离散帧 5 步动力学（创生→连接→变化→判断→删除）替代连续 EMA
  5. ✅ dv/dt ≤ const 健康变化率硬天花板
  6. ✅ 不完美定理 → 无完美健康态，残留驱动下一帧
  7. ✅ L0/L1/L2 三层分离（本体网络/五行指标/临床症状）
  8. ✅ 先天差异消除 S_effective = S_current - (S₀ - H_centroid)

数值回归基准: 曾银鸾 82 点终身数据（v1 不变，v2 输出新增字段）
"""
from __future__ import annotations
import math
from typing import Optional

# ═══════════════════════════════════════════════════════
# v1 常量（保持不变，向后兼容）
# ═══════════════════════════════════════════════════════

DIMS = ['wood', 'fire', 'earth', 'metal', 'water']
SCALE = 0.12           # Y/X 浓度 → driftData 幅值缩放
EMA_TAU_BOUNDARY = 4   # 边界滞后窗口（年视图=4年，月视图=样本/3）
EMA_TAU_METAL = 6      # 金属弹性平滑窗口
METAL_ELASTICITY_MIN = 0.30
METAL_ELASTICITY_MAX = 1.00

# ═══════════════════════════════════════════════════════
# v2 新增：SPUM2611 核心常量
# ═══════════════════════════════════════════════════════

# SPUM 拓扑核心
SPUM_TOPOLOGICAL_CONST_12 = 12      # 拓扑常数 12（欧拉恒等式强制解）
SPUM_SURFACE_CAPACITY = 16 * math.pi  # N_max ≈ 50.3 晶子表面容量
SPUM_D_MAX = 4.0                    # 临界直径 D_max = 4κ
SPUM_FIVE_RATIO = (1, 1, 2)          # k₀:k₁:k₂ = 1:1:2 普适拓扑比例

# 健康凸多面体 H — 五维边界约束
# 每个维度的健康区间 [lo, hi]（归一化到 [0, 100]）
# 来源: spum-青囊（中医）总纲 + 曾银鸾82点数据统计
HEALTH_POLYTOPE = {
    'wood':  [35, 65],   # 木: 生长/生发
    'fire':  [30, 70],   # 火: 温通/发散
    'earth': [40, 60],   # 土: 运化/守中（对称约束）
    'metal': [38, 62],   # 金: 收敛/肃降
    'water': [35, 65],   # 水: 润下/封藏
}

# 健康凸多面体中心 H_centroid
# ⚠️ 注意：此 50.0 与 v_innate center=20 (cases.py) 是两个不同量纲体系
# - v_innate: 藏干概率分布，Σ=100，每维数学期望=20
# - HEALTH_CENTROID: 多面体健康标量空间，各维独立 50±range，是大运推演的健康基准
# 两者不要统一 — 曾菊心/曾银鸾大运曲线依赖此 50 值
HEALTH_CENTROID = {
    'wood': 50.0,
    'fire': 50.0,
    'earth': 50.0,
    'metal': 50.0,
    'water': 50.0,
}

# ════════════════════════════════════════════════════════════════
# 向量量纲检测工具 — P0-1 修复
# 同一个 v_current / v_baseline 可能属于两种口径：
#   - 'prob':  v_innate 概率分布，center=20，Σ=100（cases.py 建档写入的先天基底）
#   - 'scalar': 健康标量空间，center=50（trajectory_algorithm.normalize_S_effective 输出）
# 消费端（assistant.py / knowledge.py / cases.py）之前不知道自己拿的是哪种口径，
# 把 center=20 的数据套 center=50 的 45/65 阈值 → earth:43（土壅！）被判为偏弱
# ════════════════════════════════════════════════════════════════
def detect_vector_scale(v: dict) -> str:
    """检测向量 v 的量纲口径：'prob'(center=20) 或 'scalar'(center=50)"""
    vals = [v[k] for k in DIMS if isinstance(v.get(k), (int, float))]
    if len(vals) < 3:
        return 'scalar'  # 默认健康标量口径（保守：缺少数据时不做 prob 判定）
    avg = sum(vals) / len(vals)
    # 概率分布均值在 20 附近，健康标量均值在 50 附近 → 用 30 作分界
    if avg < 30:
        return 'prob'
    return 'scalar'

def get_wu_thresholds(v: dict) -> tuple:
    """返回 (weak_threshold, strong_threshold) 基于检测到的量纲口径"""
    if detect_vector_scale(v) == 'prob':
        # v_innate 概率分布：体质推理用 ±25%（_V_INNATE_DEVIATION_PCT = 0.25）
        mean = 20.0
        return (mean * 0.65, mean * 1.35)  # <13 偏弱, >27 偏强（稍宽避免过判）
    else:
        # 健康标量：45/65（HEALTH_POLYTOPE 边界 35-65 内收缩）
        return (45, 65)

# dv/dt ≤ const — 健康变化率硬约束
# 每帧（年视图）健康向量单分量最大变化量
DV_DT_MAX = 8.0          # 单帧单分量最大变化（五行单位/帧）
DV_DT_MAX_SIGMA = 0.15   # 健康密度 σ 单帧最大变化（无量纲）

# 离散帧动力学参数
FRAME_CREATION_WEIGHT = 0.35   # 创生（新关系建立）权重
FRAME_CONNECTION_WEIGHT = 0.25 # 连接（度数重算）权重
FRAME_CHANGE_WEIGHT = 0.20     # 变化（体积/σ波动）权重
FRAME_JUDGMENT_WEIGHT = 0.10   # 判断（悬挂边检测）权重
FRAME_DELETION_WEIGHT = 0.10  # 删除（悬挂边清除）权重

# 不完美定理 — 健康残留下限
IMPERFECT_RESIDUE_MIN = 0.05   # 每帧残留至少 5% 的不完美度
PERFECT_HEALTH_LIMIT = 0.02    # 健康度低于此值视为"近乎完美"（理论上不可达）

# ═══════════════════════════════════════════════════════
# 1. 归一化
# ═══════════════════════════════════════════════════════

def norm(v: float, lo: float, hi: float) -> float:
    """钳制 + 线性归一化到 [0, 100]"""
    v = max(0.0, min(100.0, ((v - lo) / (hi - lo)) * 100))
    return v


# ═══════════════════════════════════════════════════════
# 2. computeYX — 五行向量 → Y（阳浓度）/ X（阴浓度）
#
# Y = fire 分量归一化×0.55 + wood 分量归一化×0.45
#   → 火/木 = 发散力量
# X = earth 土虚实 ×0.55 + coldN 水寒 ×0.45
#   → 土/水 = 收敛力量
# 阳旺则阴衰 → Y + X ≈ 100
# ═══════════════════════════════════════════════════════

def compute_yx(pt: dict) -> dict:
    fire = pt.get('fire', 50) or 50
    wood = pt.get('wood', 50) or 50
    earth = pt.get('earth', 50) or 50
    water = pt.get('water', 50) or 50

    y_val = (norm(fire, 30, 70) * 0.55) + (norm(wood, 35, 65) * 0.45)

    earth_n = max(norm(earth, 50, 80), norm(80 - earth, 0, 30))
    cold_n = norm(max(0, 50 - water), 0, 20)
    x_val = (earth_n * 0.55) + (cold_n * 0.45)

    return {'Y': round(y_val), 'X': round(x_val)}


# ═══════════════════════════════════════════════════════
# 3. EMA — 指数移动平均
# α = 1/tau, out[0] = arr[0], out[i] = arr[i]*α + out[i-1]*(1-α)
# 作用: 把边界线做"滞后"处理，避免单点噪声跳变
# ═══════════════════════════════════════════════════════

def ema(arr: list, tau: float) -> list:
    if not arr:
        return []
    alpha = 1.0 / tau
    out = [float(arr[0])]
    for i in range(1, len(arr)):
        out.append(float(arr[i]) * alpha + out[-1] * (1 - alpha))
    return out


# ═══════════════════════════════════════════════════════
# 4. metal_elasticity — 金属分量 → 弹性系数
#
# S_m ∈ [38, 62] (沙盒经验区间)
# t = clamp((S_m - 38)/24, 0, 1)
# el = 0.30 + 0.70 * sin(π * t)
#
# 金属旺 → 边界软（弹性大，能缓冲漂移）
# 金属弱 → 边界硬（弹性小，漂移易越界）
# 这解释了"金属弹性解耦"决策：边界位置(EMA)与弹性独立调制
# ═══════════════════════════════════════════════════════

def metal_elasticity(s_m: float) -> float:
    t = max(0.0, min(1.0, (s_m - 38.0) / 24.0))
    return METAL_ELASTICITY_MIN + 0.70 * math.sin(math.pi * t)


# ═══════════════════════════════════════════════════════
# 5. compute_health_bounds — 主入口
#
# 输入:
#   elems:   [{wood, fire, earth, metal, water, ...}, ...]  # 按时间升序
#   innate:  {wood, fire, earth, metal, water}              # 先天基底（用于边界参考）
#   events:  [{age/day, type, damage{...}, days}, ...]      # 可选，事件（瞬时视图可空）
#
# 输出 dict:
#   driftData:     [float, ...]   # 体质偏移（Y-X)*SCALE
#   yinTop:        [float, ...]   # 阴上界（正）
#   yangBot:       [float, ...]   # 阳下界（负）
#   diseaseModes:  [null|'acuteDeviation'|'chronicBoundary', ...]
#   elArr:         [float, ...]   # 金属弹性系数
# ═══════════════════════════════════════════════════════

def compute_health_bounds(elems: list, innate: Optional[dict] = None,
                          events: Optional[list] = None) -> dict:
    n = len(elems)
    if n == 0:
        return {
            'driftData': [], 'yinTop': [], 'yangBot': [],
            'diseaseModes': [], 'elArr': [],
        }

    # Step 1: 每个观测点 → Y/X 浓度
    y_real = []
    x_real = []
    for pt in elems:
        r = compute_yx(pt)
        y_real.append(r['Y'])
        x_real.append(r['X'])

    # Step 2: EMA 边界滞后（τ=4 年视图 / τ=样本/3 月视图由调用方决定；默认 4）
    y_boundary = ema(y_real, EMA_TAU_BOUNDARY)
    x_boundary = ema(x_real, EMA_TAU_BOUNDARY)

    # Step 3: 金属弹性曲线
    metal_real = [p.get('metal', 50) or 50 for p in elems]
    metal_boundary = ema(metal_real, EMA_TAU_METAL)
    el_arr = [metal_elasticity(mb) for mb in metal_boundary]

    # Step 4: 三曲线（SCALE 缩放 → driftData 幅值 ~ [-5, +5]）
    drift_data = []
    yin_top = []
    yang_bot = []
    for i in range(n):
        drift_data.append(round((y_real[i] - x_real[i]) * SCALE * 10) / 10)
        yin_top.append(round(x_boundary[i] * SCALE * 10) / 10)
        yang_bot.append(-round(y_boundary[i] * SCALE * 10) / 10)

    # Step 5: 疾病模式检测
    #   el_factor = 0.4 + 0.6 * el   (弹性调制有效边界)
    #   driftData > yinTop * el_factor  → acuteDeviation（冲出上界）
    #   driftData < yangBot * el_factor → acuteDeviation（冲出下界）
    #   连续 3+ 点贴边 → chronicBoundary
    el_factor = lambda el: 0.4 + 0.6 * el

    disease_modes = [None] * n
    for i in range(n):
        h = drift_data[i]
        eff_top = yin_top[i] * el_factor(el_arr[i])
        eff_bot = yang_bot[i] * el_factor(el_arr[i])
        if h > eff_top or h < eff_bot:
            disease_modes[i] = 'acuteDeviation'
            continue
        # 慢性贴边：检查 ±2 范围内的邻居
        bc = 0
        for j in range(max(0, i - 2), min(n, i + 3)):
            hj = drift_data[j]
            j_top = yin_top[j] * el_factor(el_arr[j])
            j_bot = yang_bot[j] * el_factor(el_arr[j])
            if (j_top - 1 <= hj <= j_top + 1) or (j_bot - 1 <= hj <= j_bot + 1):
                bc += 1
        if bc >= 3:
            disease_modes[i] = 'chronicBoundary'

    return {
        'driftData': drift_data,
        'yinTop': yin_top,
        'yangBot': yang_bot,
        'diseaseModes': disease_modes,
        'elArr': [round(e * 1000) / 1000 for e in el_arr],
        'algorithm': 'spum_computeHealthBounds_v1',
    }


# ═══════════════════════════════════════════════════════
# 6. 干支 → 五行权重（大运推演辅助）
# ═══════════════════════════════════════════════════════

TIANGAN_WUXING = {
    '甲': 'wood', '乙': 'wood',
    '丙': 'fire', '丁': 'fire',
    '戊': 'earth', '己': 'earth',
    '庚': 'metal', '辛': 'metal',
    '壬': 'water', '癸': 'water',
}

DIZHI_CANGGAN = {
    '子': {'water': 1.0},
    '丑': {'earth': 0.6, 'metal': 0.3, 'water': 0.1},
    '寅': {'wood': 0.6, 'fire': 0.3, 'earth': 0.1},
    '卯': {'wood': 1.0},
    '辰': {'earth': 0.6, 'wood': 0.3, 'water': 0.1},
    '巳': {'fire': 0.6, 'wood': 0.3, 'metal': 0.1},
    '午': {'fire': 0.85, 'earth': 0.15},
    '未': {'earth': 0.6, 'fire': 0.3, 'wood': 0.1},
    '申': {'metal': 0.6, 'water': 0.3, 'earth': 0.1},
    '酉': {'metal': 1.0},
    '戌': {'earth': 0.6, 'metal': 0.3, 'fire': 0.1},
    '亥': {'water': 0.7, 'wood': 0.3},
}

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

# 24 节气固定顺序（前端节气属性 tab 用的是这个顺序）
JIEQI_NAMES = [
    '立春','雨水','惊蛰','春分','清明','谷雨',
    '立夏','小满','芒种','夏至','小暑','大暑',
    '立秋','处暑','白露','秋分','寒露','霜降',
    '立冬','小雪','大雪','冬至','小寒','大寒',
]

# 每个节气的五行微调量（中医五运六气定义 · SPUM 基础偏移）
# 节气层 strength 比流年(6) 低，比大运(22) 更低 → 1-2 量级
JIEQI_WUXING_BIAS = {
    '立春': {'wood':+1.5,'fire':+0.3,'earth':0,'metal':0,'water':-0.3},
    '雨水': {'wood':+1.2,'fire':+0.5,'earth':0,'metal':0,'water':-0.5},
    '惊蛰': {'wood':+1.0,'fire':+0.8,'earth':0,'metal':0,'water':-0.8},
    '春分': {'wood':+0.8,'fire':+1.0,'earth':0,'metal':0,'water':-1.0},
    '清明': {'wood':+0.5,'fire':+1.2,'earth':+0.3,'metal':0,'water':-1.2},
    '谷雨': {'wood':+0.3,'fire':+1.3,'earth':+1.0,'metal':0,'water':-0.8},
    '立夏': {'wood':0,'fire':+1.5,'earth':+0.5,'metal':0,'water':-1.0},
    '小满': {'wood':0,'fire':+1.3,'earth':+0.8,'metal':0,'water':-0.8},
    '芒种': {'wood':-0.2,'fire':+1.2,'earth':+1.0,'metal':0,'water':-0.5},
    '夏至': {'wood':-0.5,'fire':+1.0,'earth':+1.2,'metal':0,'water':-0.3},
    '小暑': {'wood':-0.8,'fire':+0.8,'earth':+1.3,'metal':0,'water':0},
    '大暑': {'wood':-1.0,'fire':+0.5,'earth':+1.5,'metal':0,'water':+0.3},
    '立秋': {'wood':-0.8,'fire':+0.3,'earth':+1.2,'metal':+1.2,'water':0},
    '处暑': {'wood':-0.5,'fire':0,'earth':+0.8,'metal':+1.5,'water':+0.3},
    '白露': {'wood':-0.3,'fire':-0.2,'earth':+0.5,'metal':+1.5,'water':+0.5},
    '秋分': {'wood':0,'fire':-0.5,'earth':+0.3,'metal':+1.3,'water':+0.8},
    '寒露': {'wood':+0.2,'fire':-0.8,'earth':0,'metal':+1.0,'water':+1.0},
    '霜降': {'wood':+0.3,'fire':-1.0,'earth':+0.5,'metal':+0.8,'water':+0.8},
    '立冬': {'wood':+0.5,'fire':-1.2,'earth':0,'metal':+0.5,'water':+1.0},
    '小雪': {'wood':+0.3,'fire':-1.3,'earth':-0.3,'metal':+0.3,'water':+1.2},
    '大雪': {'wood':0,'fire':-1.5,'earth':-0.5,'metal':0,'water':+1.5},
    '冬至': {'wood':-0.3,'fire':-1.5,'earth':-0.8,'metal':-0.3,'water':+1.3},
    '小寒': {'wood':-0.5,'fire':-1.3,'earth':-1.0,'metal':-0.5,'water':+1.2},
    '大寒': {'wood':-0.3,'fire':-1.0,'earth':-0.8,'metal':-0.3,'water':+1.0},
}

# 每个节气的主五行
JIEQI_MAIN_WX = {
    '立春':'wood','雨水':'wood','惊蛰':'wood','春分':'wood','清明':'wood','谷雨':'earth',
    '立夏':'fire','小满':'fire','芒种':'fire','夏至':'fire','小暑':'fire','大暑':'earth',
    '立秋':'metal','处暑':'metal','白露':'metal','秋分':'metal','寒露':'metal','霜降':'earth',
    '立冬':'water','小雪':'water','大雪':'water','冬至':'water','小寒':'water','大寒':'water',
}


def build_jieqi_view_v2(calendar_year: int, dayun_active_gz: dict, liunian_gz: dict,
                        jieqi_dates: list) -> dict:
    """某年 × 24 节气 的五行属性视图（SPUM 逐帧注入中层）

    Args:
        calendar_year: 公历年份（如 2020）
        dayun_active_gz: 该年所在大运干支 {'gan':'己', 'zhi':'卯'}
        liunian_gz: 该年流年干支 {'g':'庚', 'z':'午'}
        jieqi_dates: 24 节气日期列表 [YYYY-MM-DD, ...]（lunar_python 精确计算）

    Returns:
        { jieqi: [{idx, name, date, month_day, wuxing_main, wuxing_bias, liunian_impact, dayun_impact}, ...],
          liunian_delta: {wood,fire,earth,metal,water},
          dayun_delta:   {wood,fire,earth,metal,water} }
    """
    # ⭐ 大运 impact：strength=22（十年层，天时推力大）
    dayun_delta_obj = elems_to_delta(
        ganzhi_to_elems(dayun_active_gz.get('gan','?'), dayun_active_gz.get('zhi','?'), wg=0.3, wz=0.7),
        strength=22,
    )
    # ⭐ 流年 impact：strength=6（年层，中等扰动）
    liunian_delta_obj = elems_to_delta(
        ganzhi_to_elems(liunian_gz.get('g','?'), liunian_gz.get('z','?'), wg=0.3, wz=0.7),
        strength=6,
    )

    jieqi = []
    for i, name in enumerate(JIEQI_NAMES):
        bias = JIEQI_WUXING_BIAS.get(name, {k:0 for k in DIMS})
        jieqi.append({
            'idx': i,
            'name': name,
            'date': jieqi_dates[i] if i < len(jieqi_dates) else f"{calendar_year}-01-01",
            'month_day': jieqi_dates[i][5:] if i < len(jieqi_dates) else '01-01',
            'wuxing_main': JIEQI_MAIN_WX.get(name, 'wood'),
            'wuxing_bias': bias,
            'liunian_impact': {k: round(liunian_delta_obj.get(k, 0), 2) for k in DIMS},
            'dayun_impact': {k: round(dayun_delta_obj.get(k, 0), 2) for k in DIMS},
        })

    return {
        'jieqi': jieqi,
        'liunian_delta': {k: round(liunian_delta_obj.get(k, 0), 2) for k in DIMS},
        'dayun_delta':   {k: round(dayun_delta_obj.get(k, 0), 2) for k in DIMS},
    }


# ═══════════════════════════════════════════════════════
# 7. build_year_view — 终身推演（L3 predict/lifetime 会用到）
#
# 用先天基底 + 大运 + 事件构建每年的五行向量，
# 再调用 compute_health_bounds 生成终身三曲线
#
# 参考 _gen_spum_mock.js 的曾银鸾 82 点推演
# ═══════════════════════════════════════════════════════

def _smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)

def build_year_view(innate: dict, dayun: list, age_start: int = 0,
                    age_end: int = 80, birth_year: int = 1957,
                    events: Optional[list] = None) -> dict:
    """终身推演 — 给定先天基底 + 大运 + 事件，生成每年 SPUM 曲线"""
    events = events or []
    TRANSITION_YEARS = 5

    # 预计算每个年龄的大运偏移（含交界平滑过渡）
    dayun_at_age = []
    for age in range(age_start, age_end + 1):
        idx = 0
        for i, d in enumerate(dayun):
            if d['start'] <= age < d['end']:
                idx = i
                break
        cur = dayun[idx]
        cur_delta = elems_to_delta(
            ganzhi_to_elems(cur.get('gan', ''), cur.get('zhi', '')), 22
        )
        age_in_dy = age - cur['start']
        if idx > 0 and age_in_dy < TRANSITION_YEARS:
            prev = dayun[idx - 1]
            prev_delta = elems_to_delta(
                ganzhi_to_elems(prev.get('gan', ''), prev.get('zhi', '')), 22
            )
            t = _smoothstep(age_in_dy / TRANSITION_YEARS)
            out = {}
            for k in DIMS:
                out[k] = prev_delta[k] * (1 - t) + cur_delta[k] * t
            dayun_at_age.append(out)
        else:
            dayun_at_age.append(cur_delta)

    # Phase 2: 流年干支 → 五行增量 → 5年平滑消锯齿
    raw_liunian = []
    for age in range(age_start, age_end + 1):
        year = birth_year + age
        ln = get_liunian(year)
        raw_liunian.append(liunian_delta(ln['g'], ln['z']))
    smooth_liunian = smooth5(raw_liunian)

    # Phase 3: 合成五行向量（先天 + 大运 + 流年 + 衰老 + 事件）
    elems = []
    for i, age in enumerate(range(age_start, age_end + 1)):
        v = dict(innate)
        # 衰老衰减（20岁后每10年各分量微降）
        decay = (age - 20) / 10 if age > 20 else 0
        v['fire'] -= decay * 0.8
        v['metal'] -= decay * 0.3
        v['water'] -= decay * 0.2
        # 大运偏移
        for k in DIMS:
            v[k] += dayun_at_age[i][k]
        # 流年偏移（5年平滑，消锯齿）
        for k in DIMS:
            v[k] += smooth_liunian[i][k]
        # 事件冲击（指数衰减）
        for ev in events:
            days_since = (age - ev.get('age', 0)) * 365
            if 0 <= days_since < ev.get('days', 365):
                progress = days_since / ev['days']
                impact = math.exp(-progress * 2)
                sign = -1 if ev.get('damage') else 1
                for k, val in (ev.get('damage') or {}).items():
                    v[k] = v.get(k, 50) + sign * val * impact
        # 钳制到 [5, 95]
        for k in DIMS:
            v[k] = max(5, min(95, round(v[k] * 10) / 10))
        dy_info = next((d for d in dayun if d['start'] <= age < d['end']), dayun[-1])
        elems.append({
            'age': age,
            'day': age * 365,
            't': f"{birth_year + age}·{age}岁·{dy_info.get('name', '?')}",
            'dayun': dy_info.get('name', '?'),
            **v,
        })

    # 三曲线
    bounds = compute_health_bounds(elems, innate)
    return {
        'view_mode': 'year',
        'algorithm': 'spum_computeHealthBounds_v1',
        'v_innate': innate,
        'dayun': dayun,
        'dayunMarkArea': [
            {'start_age': d['start'], 'end_age': d['end'],
             'name': d.get('name', ''), 'gan': d.get('gan', ''), 'zhi': d.get('zhi', '')}
            for d in dayun
        ],
        'elems': elems,
        **bounds,
    }


# ═══════════════════════════════════════════════════════════════════
# ╔════════════════════════════════════════════════════════════════╗
# ║          v2 模块 — SPUM2611 + 青囊中医总纲 迭代                 ║
# ║                                                                  ║
# ║  理论来源: SPUM2611.md / knowledge.md / spum-青囊中医总纲.md   ║
# ║  核心注入: S向量 + σ场 + 帧动力学 + dv/dt约束 + L0/L1/L2分层   ║
# ╚════════════════════════════════════════════════════════════════╝
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════
# V2-1. build_S_vector — 五行向量 → S 五维健康向量 (L1 层)
#
# SPUM 映射: S = (S_木, S_火, S_土, S_金, S_水, σ, τ)
#   S_* = 各五行分量归一化到 [0, 1]
#   σ   = 健康密度标量（∇σ 驱动收敛/发散）
#   τ   = 离散帧序号（时间 = 帧计数）
# ═══════════════════════════════════════════════════════

def build_S_vector(pt: dict, frame_idx: int = 0) -> dict:
    """从原始五行构建 SPUM S 向量（L1 指标层）

    关键: S 向量保留原始五行数值（[0,100] 范围），
    不做归一化。归一化到 [0,1] 的版本单独放在 normalized 字段中。
    这样 health_polytope_margin 可以直接对原始值做边界判定。

    映射关系（spum-气血津液图论.md）:
      S_木 → 闭合环数量（生长/生发）
      S_火 → ∇σ 幅度（温通/发散）
      S_土 → 储备池规模（运化/守中）
      S_金 → 桥边切换频率（收敛/肃降）
      S_水 → 连通度（润下/封藏）
    """
    s_vec = {}
    for dim in DIMS:
        raw = pt.get(dim, 50) or 50
        s_vec[dim] = raw  # 保留原始值

    # normalized 字段: 归一化到 [0, 1]（用于内部计算）
    normalized = {}
    for dim in DIMS:
        raw = pt.get(dim, 50) or 50
        lo, hi = HEALTH_POLYTOPE[dim]
        normalized[dim] = max(0.0, min(1.0, (raw - lo) / (hi - lo)))
    s_vec['normalized'] = normalized

    # σ 健康密度标量: 偏离中心的程度
    # σ = 1 - 平均偏离度 → 偏离越大 σ 越低 → 连接越稀疏
    deviations = []
    for dim in DIMS:
        raw = pt.get(dim, 50) or 50
        centroid = HEALTH_CENTROID[dim]
        max_deviation = 25.0  # [25, 75] 边界
        deviations.append(abs(raw - centroid) / max_deviation)
    avg_deviation = sum(deviations) / len(deviations)
    s_vec['sigma'] = max(0.0, min(1.0, 1.0 - avg_deviation))

    # τ 离散帧序号
    s_vec['tau'] = frame_idx

    # v1 兼容 Y/X 衍生量
    y_val = (norm(pt.get('fire', 50), 30, 70) * 0.55 +
             norm(pt.get('wood', 50), 35, 65) * 0.45)
    x_val = ((max(norm(pt.get('earth', 50), 50, 80),
                  norm(80 - (pt.get('earth', 50) or 50), 0, 30))) * 0.55 +
             norm(max(0, 50 - (pt.get('water', 50) or 50)), 0, 20) * 0.45)
    s_vec['Y'] = round(y_val)
    s_vec['X'] = round(x_val)

    return s_vec


# ═══════════════════════════════════════════════════════
# V2-2. normalize_S_effective — 先天差异消除
#
# S_effective = S_current - (S_0 - H_centroid)
#   S_0  = 先天基底（八字推导的初始健康向量）
#   H_centroid = 健康多面体中心（50, 50, 50, 50, 50）
#
# 核心思想: 每个人的"零健康"基线不同，先天 S_0 偏离中心的部分
# 不应被计为"异常"。此步骤消除个体先天差异，使健康判定
# 基于"偏离自身基线"而非"偏离绝对中心"。
# ═══════════════════════════════════════════════════════

def normalize_S_effective(S_current: dict, S_innate: dict) -> dict:
    """消除先天差异，返回 S_effective

    Args:
        S_current: 当前观测的 S 向量
        S_innate: 先天基底（八字推导）
    Returns:
        S_effective: 消除先天偏移后的健康向量
    """
    s_eff = {}
    for dim in DIMS:
        # 偏移修正 = 先天值 偏离 中心 的量
        # 2026-10-10 防护：NaN/None/非数值输入按健康中心兜底，避免污染 σ/判定
        _inn = S_innate.get(dim, 50)
        if not isinstance(_inn, (int, float)) or not math.isfinite(_inn):
            _inn = 50.0
        innate_bias = _inn - HEALTH_CENTROID[dim]
        # S_effective = S_current - 先天偏移
        _cur = S_current.get(dim, 50)
        if not isinstance(_cur, (int, float)) or not math.isfinite(_cur):
            _cur = 50.0
        s_eff[dim] = _cur - innate_bias
    # σ 和 τ 保持不变
    s_eff['sigma'] = S_current.get('sigma', 0.5)
    s_eff['tau'] = S_current.get('tau', 0)
    return s_eff


# ═══════════════════════════════════════════════════════
# V2-3. health_polytope_margin — 健康凸多面体边界判定
#
# 对 S_effective 的每个维度计算 margin:
#   margin_lo(dim) = S_eff[dim] - lo_boundary[dim]   # 下界裕度
#   margin_hi(dim) = hi_boundary[dim] - S_eff[dim]   # 上界裕度
#
# 判定 status:
#   IN  — 所有 margin > 0（健康多面体内）
#   ON  — 存在 margin ≈ 0（触碰边界）
#   OUT — 存在 margin < 0（越界）
#
# 输出:
#   Touch集合 = margin < threshold 的维度
#   越界深度 = min(margin) 取绝对值
# ═══════════════════════════════════════════════════════

def health_polytope_margin(S_eff: dict,
                           touch_threshold: float = 2.0,
                           innate: Optional[dict] = None) -> dict:
    """健康凸多面体 H 边界判定

    Args:
        S_eff: S_effective 向量（已消除先天差异）
        touch_threshold: 触碰边界阈值（默认 2.0 单位）
        innate: 可选先天基底，用于显示用
    Returns:
        {
            'status': 'IN'|'ON'|'OUT',
            'margins': {dim: {'lo': float, 'hi': float}},
            'touch': [str, ...],           # 触碰的维度列表
            'violation_depth': float,      # 越界深度（正数）
            'violation_dim': str|None,     # 最严重越界维度
            'innate_bias': {dim: float},   # 先天偏移修正量
        }
    """
    margins = {}
    violations = []    # 越界维度
    touches = []       # 触碰维度
    invalid_dims = []  # 非有限数值维度（2026-10-10 防护）

    for dim in DIMS:
        lo, hi = HEALTH_POLYTOPE[dim]
        val = S_eff.get(dim, HEALTH_CENTROID[dim])

        # 2026-10-10 防护：NaN/Inf 等非有限数值 → 标记 INVALID 而非误判 IN/ON/OUT
        if not isinstance(val, (int, float)) or not math.isfinite(val):
            invalid_dims.append(dim)
            margins[dim] = {'lo': None, 'hi': None}
            continue

        margin_lo = val - lo
        margin_hi = hi - val
        margins[dim] = {'lo': round(margin_lo, 2), 'hi': round(margin_hi, 2)}

        # 判定
        if margin_lo < 0:
            violations.append((dim, 'lo', abs(margin_lo)))
        elif margin_hi < 0:
            violations.append((dim, 'hi', abs(margin_hi)))
        elif margin_lo <= touch_threshold or margin_hi <= touch_threshold:
            touches.append(dim)

    # status 判定
    if invalid_dims:
        status = 'INVALID'
    elif violations:
        status = 'OUT'
    elif touches:
        status = 'ON'
    else:
        status = 'IN'

    # 最严重越界
    violation_depth = 0.0
    violation_dim = None
    if violations:
        violation_dim, _, violation_depth = max(violations, key=lambda x: x[2])

    return {
        'status': status,
        'margins': margins,
        'touch': touches,
        'violations': [(d, b, round(v, 2)) for d, b, v in violations],
        'violation_depth': round(violation_depth, 2),
        'violation_dim': violation_dim,
        'invalid_dims': invalid_dims,
    }


# ═══════════════════════════════════════════════════════
# V2-4. discrete_frame_5step — 离散帧 5 步动力学
#
# SPUM 帧定义: 创生 → 连接 → 变化 → 判断 → 删除
# 替代 v1 的连续 EMA 平滑
#
# 每帧输出:
#   该帧 S 向量的增量（而非 EMA 滞后值）
#   帧内悬挂边检测结果（不完美定理体现）
#   帧内净变化 ΔS = creation - deletion
# ═══════════════════════════════════════════════════════

def discrete_frame_5step(S_prev: dict, S_curr: dict,
                         frame_idx: int) -> dict:
    """执行一帧的 5 步动力学

    Args:
        S_prev: 上一帧的 S 向量
        S_curr: 当前帧的 S 向量（原始观测）
        frame_idx: 帧序号 τ
    Returns:
        {
            'delta_S': {dim: float},        # 帧内 S 增量
            'delta_sigma': float,            # σ 变化量
            'creation': {dim: float},        # 创生分量
            'connection': {dim: float},      # 连接分量
            'change': {dim: float},          # 变化分量
            'judgment': {dim: float},        # 判断分量
            'deletion': {dim: float},        # 删除分量
            'hanging_edges': {dim: bool},    # 悬挂边检测
            'residue': float,                # 本帧残留（不完美）
        }
    """
    # Step 1: 创生 — 新关系建立（正向增量）
    creation = {}
    for dim in DIMS:
        delta = (S_curr.get(dim, 50) or 50) - (S_prev.get(dim, 50) or 50)
        creation[dim] = max(0, delta) * FRAME_CREATION_WEIGHT

    # Step 2: 连接 — 度数重算（归一化调整）
    connection = {}
    for dim in DIMS:
        lo, hi = HEALTH_POLYTOPE[dim]
        val = S_curr.get(dim, 50) or 50
        # 归一化：超出范围的部分被"连接"稀释
        if val < lo:
            connection[dim] = (lo - val) * FRAME_CONNECTION_WEIGHT * 0.3
        elif val > hi:
            connection[dim] = (val - hi) * FRAME_CONNECTION_WEIGHT * 0.3
        else:
            connection[dim] = 0.0

    # Step 3: 变化 — 体积/σ 波动（直接映射）
    change = {}
    for dim in DIMS:
        delta = (S_curr.get(dim, 50) or 50) - (S_prev.get(dim, 50) or 50)
        change[dim] = delta * FRAME_CHANGE_WEIGHT

    # Step 4: 判断 — 悬挂边检测（边界触碰检测）
    judgment = {}
    hanging = {}
    for dim in DIMS:
        lo, hi = HEALTH_POLYTOPE[dim]
        val = S_curr.get(dim, 50) or 50
        # 悬挂边 = 触碰边界时的边缘不稳定性
        near_boundary = (val - lo) < 3 or (hi - val) < 3
        hanging[dim] = near_boundary
        judgment[dim] = -0.5 if near_boundary else 0.0

    # Step 5: 删除 — 悬挂边清除（负向反馈）
    deletion = {}
    for dim in DIMS:
        if hanging.get(dim, False):
            lo, hi = HEALTH_POLYTOPE[dim]
            val = S_curr.get(dim, 50) or 50
            # 向中心拉回的"删除"力
            target = HEALTH_CENTROID[dim]
            deletion[dim] = (target - val) * FRAME_DELETION_WEIGHT * 0.5
        else:
            deletion[dim] = 0.0

    # 净增量 ΔS = creation + connection + change + judgment + deletion
    delta_S = {}
    for dim in DIMS:
        delta_S[dim] = round(
            creation[dim] + connection[dim] + change[dim] +
            judgment[dim] + deletion[dim], 3
        )

    # σ 变化
    delta_sigma = round(
        S_curr.get('sigma', 0.5) - S_prev.get('sigma', 0.5), 3
    )

    # 不完美定理: 残留 = 悬挂边比例 + 帧未消化的增量
    hanging_count = sum(1 for v in hanging.values() if v)
    total_delta = sum(abs(v) for v in delta_S.values())
    residue = round(
        max(IMPERFECT_RESIDUE_MIN, hanging_count / len(DIMS) * 0.6 +
            min(0.4, total_delta / 20)), 3
    )

    return {
        'tau': frame_idx,
        'delta_S': delta_S,
        'delta_sigma': delta_sigma,
        'creation': {k: round(v, 3) for k, v in creation.items()},
        'connection': {k: round(v, 3) for k, v in connection.items()},
        'change': {k: round(v, 3) for k, v in change.items()},
        'judgment': {k: round(v, 3) for k, v in judgment.items()},
        'deletion': {k: round(v, 3) for k, v in deletion.items()},
        'hanging_edges': hanging,
        'residue': residue,
    }


# ═══════════════════════════════════════════════════════
# V2-5. clamp_dv_dt — dv/dt ≤ const 变化率硬约束
#
# SPUM 核心约束: 任何事物发展存在硬天花板
#   dv/dt → 单帧单分量变化量 ≤ DV_DT_MAX
#   dσ/dt → 单帧 σ 变化量 ≤ DV_DT_MAX_SIGMA
#
# 用途: 事件冲击、大运切换等引起的突变需要被钳制
# ═══════════════════════════════════════════════════════

def clamp_dv_dt(S_prev: dict, S_raw: dict) -> dict:
    """将 S_raw 钳制在 dv/dt ≤ const 范围内

    Args:
        S_prev: 上一帧 S 向量
        S_raw: 当前帧观测 S 向量（未经钳制）
    Returns:
        S_clamped: 变化率钳制后的 S 向量
    """
    clamped = {}
    for dim in DIMS:
        prev = S_prev.get(dim, 50) or 50
        raw = S_raw.get(dim, 50) or 50
        delta = raw - prev
        if abs(delta) > DV_DT_MAX:
            # 钳制到上限
            clamped[dim] = round(prev + DV_DT_MAX * (1 if delta > 0 else -1), 2)
        else:
            clamped[dim] = round(raw, 2)

    # σ 也钳制
    prev_sigma = S_prev.get('sigma', 0.5)
    raw_sigma = S_raw.get('sigma', 0.5)
    delta_s = raw_sigma - prev_sigma
    if abs(delta_s) > DV_DT_MAX_SIGMA:
        clamped['sigma'] = round(
            prev_sigma + DV_DT_MAX_SIGMA * (1 if delta_s > 0 else -1), 3
        )
    else:
        clamped['sigma'] = round(raw_sigma, 3)

    clamped['tau'] = S_raw.get('tau', 0)
    # 保留 v1 兼容 Y/X（从钳制后的 S 重新计算）
    clamped['Y'] = S_raw.get('Y', 50)
    clamped['X'] = S_raw.get('X', 50)

    return clamped


# ═══════════════════════════════════════════════════════
# V2-6. compute_health_bounds_v2 — v2 主入口
#
# 整合以上所有 v2 模块:
#   S 向量构建 → 先天归一化 → 离散帧动力学 → dv/dt 约束
#   → 凸多面体 margin 判定 → 不完美定理残留
#
# 输出:
#   保持 v1 的三曲线 + 疾病模式（向后兼容）
#   新增:
#     S_vectors: [{S_vec, S_eff, frame_result, margin, residue}]
#     sigma_trend: [float, ...]           # σ 密度趋势
#     polytope_statuses: [status, ...]     # IN/ON/OUT 序列
#     violation_depths: [float, ...]       # 越界深度序列
#     frame_residues: [float, ...]         # 不完美残留序列
#     health_score: [float, ...]           # 综合健康度
# ═══════════════════════════════════════════════════════

def compute_health_bounds_v2(elems: list, innate: Optional[dict] = None,
                             events: Optional[list] = None) -> dict:
    """v2 主入口 — SPUM2611 理论完整注入

    Args:
        elems: 原始五行观测序列 [{wood, fire, earth, metal, water, ...}, ...]
        innate: 先天基底（八字推导的五维向量）
        events: 事件序列 [{age/day, type, damage, days}, ...]
    Returns:
        完整 v2 输出 dict，包含 v1 兼容字段 + v2 新增字段
    """
    n = len(elems)
    if n == 0:
        return {
            'driftData': [], 'yinTop': [], 'yangBot': [],
            'diseaseModes': [], 'elArr': [],
            'S_vectors': [], 'sigma_trend': [], 'polytope_statuses': [],
            'violation_depths': [], 'frame_residues': [], 'health_score': [],
            'algorithm': 'spum_computeHealthBounds_v2',
            'theory_source': 'SPUM2611 + 青囊中医总纲',
        }

    # 先天基底默认为健康中心
    innate = innate or HEALTH_CENTROID.copy()

    # ══════════════════════════════════════════════════
    # Phase 1: S 向量构建 + dv/dt 约束 + 帧动力学
    # ══════════════════════════════════════════════════

    S_vectors = []
    S_clamped_series = []    # dv/dt 钳制后的序列
    frame_results = []       # 每帧的 5 步动力学结果

    # 初始帧: 用先天基底
    S_init = build_S_vector(innate, frame_idx=0)
    S_clamped_series.append(S_init)

    for i, pt in enumerate(elems):
        # 构建当前 S 向量
        S_raw = build_S_vector(pt, frame_idx=i + 1)

        # dv/dt ≤ const 变化率钳制
        S_prev = S_clamped_series[-1]
        S_clamped = clamp_dv_dt(S_prev, S_raw)
        S_clamped_series.append(S_clamped)

        # 离散帧 5 步动力学
        frame_result = discrete_frame_5step(S_prev, S_clamped, frame_idx=i + 1)
        frame_results.append(frame_result)

        # S_effective 先天归一化
        S_eff = normalize_S_effective(S_clamped, innate)

        # 健康凸多面体 margin 判定
        margin = health_polytope_margin(S_eff)

        S_vectors.append({
            'tau': i + 1,
            'S_raw': {k: round(v, 2) for k, v in S_raw.items()
                      if k in DIMS},
            'S_clamped': {k: round(v, 2) for k, v in S_clamped.items()
                          if k in DIMS},
            'sigma': S_clamped['sigma'],
            'S_effective': {k: round(v, 2) for k, v in S_eff.items()
                            if k in DIMS},
            'margin': margin,
            'frame': frame_result,
        })

    # ══════════════════════════════════════════════════
    # Phase 2: v1 兼容三曲线计算（从 v2 结果反算）
    # ══════════════════════════════════════════════════

    # Y/X 序列从 S 向量提取
    y_real = [s['Y'] if 'Y' in s else (s.get('S_clamped', {}).get('fire', 50))
              for s in S_clamped_series[1:]]
    x_real = [s['X'] if 'X' in s else 50 for s in S_clamped_series[1:]]

    # v1 EMA 边界（保持向后兼容）
    y_boundary = ema(y_real, EMA_TAU_BOUNDARY) if y_real else []
    x_boundary = ema(x_real, EMA_TAU_BOUNDARY) if x_real else []

    # 金属弹性
    metal_real = [pt.get('metal', 50) or 50 for pt in elems]
    metal_boundary = ema(metal_real, EMA_TAU_METAL)
    el_arr = [metal_elasticity(mb) for mb in metal_boundary]

    # 三曲线
    drift_data = [round((y_real[i] - x_real[i]) * SCALE * 10) / 10
                  for i in range(n)]
    yin_top = [round(x_boundary[i] * SCALE * 10) / 10 for i in range(n)]
    yang_bot = [-round(y_boundary[i] * SCALE * 10) / 10 for i in range(n)]

    # ══════════════════════════════════════════════════
    # Phase 2.5: 尖峰三条件判定（L1 投影层 · 2D 阴阳平面）
    #
    # ⚠️ 显式标注：以下尖峰判定在 L1 投影层进行。
    #    原始五形本体是闭环耦合关系链条，塌缩为 2D（driftData）后丢失耦合细节。
    #    判定结果对应体质曲线形态，不声称对应 L0 本体层的五形状态。
    #
    # 三条件全部锚定已有变量：
    #   ① 快：|Δh| > SPIKE_BASIC_THRESH × el_factor(el[t-1])
    #   ② 顶：触有效边界 ± TOUCH_EPS
    #   ③ 弹：下一帧朝反方向运动
    #
    # viewMode 自适应（根据 elems 结构推断）：
    #   年视图：每帧=1年，driftData 幅度 ±5~10
    #   月视图：每帧≈几天，EMA 压缩后幅度 ±0.5~2
    # ══════════════════════════════════════════════════
    is_year_view = (n > 30 and all(p.get('age') is not None for p in elems))
    SPIKE_BASIC_THRESH = 2.0 if is_year_view else 0.4
    TOUCH_EPS = 0.5 if is_year_view else 0.1
    WINDOW_HALF = 2 if is_year_view else 1

    el_factor = lambda el: 0.4 + 0.6 * el

    # Phase 2.5a: 尖峰扫描
    spike_up = [False] * n    # 撞 yinTop（上边界）
    spike_down = [False] * n  # 撞 yangBot（下边界）

    for i in range(1, n - 1):
        h_prev = drift_data[i - 1]
        h_cur = drift_data[i]
        h_next = drift_data[i + 1]

        el_prev = el_arr[i - 1]
        thresh = SPIKE_BASIC_THRESH * el_factor(el_prev)
        delta = h_cur - h_prev

        if abs(delta) <= thresh:
            continue  # 条件①不满足 → 跳过

        if delta > 0:
            # 向上冲 → 撞 yinTop（正边界）
            eff_top = yin_top[i] * el_factor(el_arr[i])
            if eff_top - TOUCH_EPS <= h_cur <= eff_top + TOUCH_EPS:  # 条件②
                if h_next < h_cur:  # 条件③弹回
                    spike_up[i] = True
        else:
            # 向下冲 → 撞 yangBot（负边界）
            eff_bot = yang_bot[i] * el_factor(el_arr[i])
            if eff_bot - TOUCH_EPS <= h_cur <= eff_bot + TOUCH_EPS:  # 条件②
                if h_next > h_cur:  # 条件③弹回
                    spike_down[i] = True

    # Phase 2.5c: 5D 根判定增强尖峰（S₀ 中心化 · 2026-10-10 新增）
    #
    # 设计意图（algorithm.md 尖峰触边判定核实结论）：
    #   ① 快   = |Δh| ≥ spikeThresh（与 2.5a 相同，2D 投影层速度）
    # ① 快   = |Δ drift| > 基础阈值（SPIKE_BASIC_THRESH）
    # ② 顶   = 5D 健康多面体 H 触边（margin ≤ TOUCH_EPS）或首次越界
    #            （S_effective 根判定层，替代 EMA 滞后边界）
    # ③ 弹   = 下一帧 drift 反向且回落幅度 ≥ 30% 当前速度（子类型，非必要条件）
    #
    # 2026-10-10 按《尖峰触边判定_核实结论》4.1 落地：弹回从必要条件降为子类型。
    #   - 尖峰 + 弹回（rebound=True） = 弹性尚可（金形仍在工作）
    #   - 尖峰 + 不回（rebound=False）= 弹性失效（金形修剪不足，需干预）
    # 若仍把弹回当必要条件，穿出后持续恶化的帧永远不会被标为尖峰（acuteDeviation 盲区）。
    #
    # 旧实现仅以 EMA 滞后边界为"顶"，边界随信号漂移 → 实测任何场景
    # （平稳/冲击/终身推演）都撞不上，尖峰判定功能失效（P1-01）。
    spike_up_5d = [False] * n
    spike_down_5d = [False] * n
    rebound_up = [False] * n
    rebound_down = [False] * n
    for i in range(1, n - 1):
        h_prev = drift_data[i - 1]
        h_cur = drift_data[i]
        h_next = drift_data[i + 1]
        delta = h_cur - h_prev
        if abs(delta) <= SPIKE_BASIC_THRESH:
            continue  # ① 不快 → 跳过

        m = S_vectors[i]['margin']
        m_prev_status = S_vectors[i - 1]['margin']['status'] if i >= 1 else 'IN'
        touch_up = any(m['margins'][d]['hi'] is not None and
                       m['margins'][d]['hi'] <= TOUCH_EPS for d in DIMS)
        touch_dn = any(m['margins'][d]['lo'] is not None and
                       m['margins'][d]['lo'] <= TOUCH_EPS for d in DIMS)
        first_viol_up = (m['status'] == 'OUT' and m_prev_status != 'OUT' and
                         any(b == 'hi' for _, b, _ in m['violations']))
        first_viol_dn = (m['status'] == 'OUT' and m_prev_status != 'OUT' and
                         any(b == 'lo' for _, b, _ in m['violations']))

        if delta > 0:
            # 上冲触上边界 / 首越上界 → 尖峰（弹回为子类型标记）
            if touch_up or first_viol_up:
                spike_up_5d[i] = True
                rebound_up[i] = h_next < h_cur
        else:
            # 下冲触下边界 / 首越下界 → 尖峰（弹回为子类型标记）
            if touch_dn or first_viol_dn:
                spike_down_5d[i] = True
                rebound_down[i] = h_next > h_cur

    # 合并 EMA 路径与 5D 路径（保留原有判定 + 新增根判定，互不覆盖）
    spike_up = [a or b for a, b in zip(spike_up, spike_up_5d)]
    spike_down = [a or b for a, b in zip(spike_down, spike_down_5d)]

    # 速度 / 方向序列（S₀ 中心化曲线的一阶差分；前端 tooltip 与形态判定用）
    velocity = [0.0] * n
    direction = ['flat'] * n
    for i in range(1, n):
        _v = drift_data[i] - drift_data[i - 1]
        velocity[i] = round(_v, 3)
        direction[i] = 'up' if _v > 1e-9 else ('down' if _v < -1e-9 else 'flat')

    # S₀ 中心化后的漂移（去均值，均值回归到 0 轴；旧 driftData 以 EMA 中心为参考）
    _mean = sum(drift_data) / n if n else 0.0
    drift_centered = [round(h - _mean, 3) for h in drift_data]

    # 先天偏置向量（S₀ 中心化设计：S_effective = S_current − (S₀ − C)）
    centroid_bias = {d: round((innate.get(d, 50) or 50) - HEALTH_CENTROID[d], 2)
                     for d in DIMS}

    # Phase 2.5b: 三态 + 原有疾病模式联合判定
    state_flags = ['healthy'] * n  # healthy / subhealthy / disease
    disease_modes = [None] * n

    for i in range(n):
        h = drift_data[i]
        eff_top = yin_top[i] * el_factor(el_arr[i])
        eff_bot = yang_bot[i] * el_factor(el_arr[i])

        # v2 越界判定（保留 5D 凸多面体 OUT，更精确）
        v2_status = S_vectors[i]['margin']['status']
        v2_out = v2_status == 'OUT'
        v2_on = v2_status == 'ON'
        v2_touch = S_vectors[i]['margin']['touch']
        v2_depth = S_vectors[i]['margin']['violation_depth']
        v2_dim = S_vectors[i]['margin']['violation_dim']

        # ── 状态 3：疾病 ──
        if h > eff_top or h < eff_bot or v2_out:
            state_flags[i] = 'disease'
            if v2_depth > 5 or v2_dim in ('water', 'fire'):
                disease_modes[i] = 'acuteDeviation'
            else:
                disease_modes[i] = 'subtleDeviation'
            continue

        # ── 状态 2：亚健康（窗口内同方向尖峰 ≥ 2）──
        win_lo = max(0, i - WINDOW_HALF)
        win_hi = min(n, i + WINDOW_HALF + 1)
        up_spikes = sum(1 for j in range(win_lo, win_hi) if spike_up[j])
        dn_spikes = sum(1 for j in range(win_lo, win_hi) if spike_down[j])

        # 也用 v2 Touch≥2 辅助（5D 层 ON 状态反复触边）
        if up_spikes >= 2 or dn_spikes >= 2:
            state_flags[i] = 'subhealthy'
            disease_modes[i] = 'chronicBoundary'
            continue
        if v2_on and len(v2_touch) >= 2:
            state_flags[i] = 'subhealthy'
            disease_modes[i] = 'subtleDeviation'
            continue

        # 状态 1：健康（留在 default 初始化）

    # ══════════════════════════════════════════════════
    # Phase 3: v2 新增输出
    # ══════════════════════════════════════════════════

    sigma_trend = [s['sigma'] for s in S_clamped_series[1:]]
    polytope_statuses = [s['margin']['status'] for s in S_vectors]
    violation_depths = [s['margin']['violation_depth'] for s in S_vectors]
    frame_residues = [s['frame']['residue'] for s in S_vectors]

    # 综合健康度 = σ × (1 - 越界深度) × 不完美修正 × dv/dt 钳制度
    # 钳制到 [0, 1] 保证输出一致范围
    health_score = []
    for i in range(n):
        sigma = sigma_trend[i]
        depth = violation_depths[i]
        residue = frame_residues[i]
        # 基础健康度（σ 越高越健康，越界越深越差）
        base = sigma * (1 - min(1.0, depth / 20.0))
        # 不完美修正（有一个最小不完美度，残留高则健康差）
        imperfect_modifier = max(0.0, 1.0 - residue * 0.5)
        # dv/dt 钳制度（变化太剧烈扣分）
        raw_clamped_diff = abs(
            sum(S_clamped_series[i + 1].get(d, 0) - S_clamped_series[i].get(d, 0)
                for d in DIMS) / len(DIMS)
        )
        dv_penalty = max(0.5, 1.0 - raw_clamped_diff / DV_DT_MAX)
        # 钳制到 [0, 1]
        score = max(0.0, min(1.0, base * imperfect_modifier * dv_penalty))
        health_score.append(round(score, 3))

    return {
        # v1 兼容输出
        'driftData': drift_data,
        'yinTop': yin_top,
        'yangBot': yang_bot,
        'diseaseModes': disease_modes,
        'elArr': [round(e * 1000) / 1000 for e in el_arr],
        # v2 新增输出
        'S_vectors': [
            {
                'tau': sv['tau'],
                'S': sv['S_clamped'],
                'sigma': sv['sigma'],
                'S_effective': sv['S_effective'],
                'margin': sv['margin'],
                'frame': {
                    'delta_S': sv['frame']['delta_S'],
                    'delta_sigma': sv['frame']['delta_sigma'],
                    'hanging_edges': sv['frame']['hanging_edges'],
                    'residue': sv['frame']['residue'],
                },
            }
            for sv in S_vectors
        ],
        'sigma_trend': sigma_trend,
        'polytope_statuses': polytope_statuses,
        'violation_depths': violation_depths,
        'frame_residues': frame_residues,
        'health_score': health_score,
        # 元数据
        'algorithm': 'spum_computeHealthBounds_v2',
        'theory_source': 'SPUM2611 + 青囊中医总纲 + spum-病机五形失衡检测',
        'topological_constant_12': SPUM_TOPOLOGICAL_CONST_12,
        'health_polytope': HEALTH_POLYTOPE,
        'dv_dt_max': DV_DT_MAX,
        # Phase 2.5 三态判定新增输出
        'stateFlags': state_flags,        # ['healthy'|'subhealthy'|'disease'] * n
        'spikeUp': spike_up,              # [bool] * n — 撞上边界（yinTop）尖峰
        'spikeDown': spike_down,          # [bool] * n — 撞下边界（yangBot）尖峰
        'spikeUp5d': spike_up_5d,         # [bool] * n — 5D 根判定触边尖峰（2026-10-10）
        'spikeDown5d': spike_down_5d,     # [bool] * n — 5D 根判定触边尖峰
        'reboundUp': rebound_up,          # [bool] * n — 上冲尖峰弹回子类型（金形弹性尚可）
        'reboundDown': rebound_down,      # [bool] * n — 下冲尖峰弹回子类型（金形弹性尚可）
        'velocity': velocity,             # [float] * n — 漂移速度（一阶差分）
        'direction': direction,           # ['up'|'down'|'flat'] * n — 漂移方向
        'driftCentered': drift_centered,  # [float] * n — S₀ 中心化漂移（去均值）
        'centroidBias': centroid_bias,    # {dim: float} — 先天偏置向量（S₀ − C）
        'adaptiveParams': {               # viewMode 自适应参数（前端调试用）
            'isYearView': is_year_view,
            'spikeThresh': SPIKE_BASIC_THRESH,
            'touchEps': TOUCH_EPS,
            'windowHalf': WINDOW_HALF,
        },
    }


# ═══════════════════════════════════════════════════════
# V2-7. build_year_view_v2 — 终身推演 v2 版
#
# 在 v1 build_year_view 的大运推演基础上，
# 注入 v2 的 S 向量 + σ 场 + dv/dt 约束
# ═══════════════════════════════════════════════════════

def build_year_view_v2(innate: dict, dayun: list, age_start: int = 0,
                       age_end: int = 80, birth_year: int = 1957,
                       events: Optional[list] = None) -> dict:
    """v2 终身推演 — 完整 SPUM 理论注入"""
    events = events or []
    TRANSITION_YEARS = 5

    # 预计算每个年龄的大运偏移（含交界平滑过渡）
    dayun_at_age = []
    for age in range(age_start, age_end + 1):
        idx = 0
        for i, d in enumerate(dayun):
            if d['start'] <= age < d['end']:
                idx = i
                break
        cur = dayun[idx]
        cur_delta = elems_to_delta(
            ganzhi_to_elems(cur.get('gan', ''), cur.get('zhi', '')), 22
        )
        age_in_dy = age - cur['start']
        if idx > 0 and age_in_dy < TRANSITION_YEARS:
            prev = dayun[idx - 1]
            prev_delta = elems_to_delta(
                ganzhi_to_elems(prev.get('gan', ''), prev.get('zhi', '')), 22
            )
            t = _smoothstep(age_in_dy / TRANSITION_YEARS)
            out = {}
            for k in DIMS:
                out[k] = prev_delta[k] * (1 - t) + cur_delta[k] * t
            dayun_at_age.append(out)
        else:
            dayun_at_age.append(cur_delta)

    # Phase 2: 流年干支 → 五行增量 → 5年平滑消锯齿
    raw_liunian = []
    for age in range(age_start, age_end + 1):
        year = birth_year + age
        ln = get_liunian(year)
        raw_liunian.append(liunian_delta(ln['g'], ln['z']))
    smooth_liunian = smooth5(raw_liunian)

    # Phase 3: 逐年推演五行向量（注入 dv/dt 约束 + 流年平滑）
    elems = []
    prev_v = dict(innate)
    for i, age in enumerate(range(age_start, age_end + 1)):
        v = dict(innate)
        # 衰老衰减
        decay = (age - 20) / 10 if age > 20 else 0
        v['fire'] -= decay * 0.8
        v['metal'] -= decay * 0.3
        v['water'] -= decay * 0.2
        # 大运偏移
        for k in DIMS:
            v[k] += dayun_at_age[i][k]
        # 流年偏移（5年平滑）
        for k in DIMS:
            v[k] += smooth_liunian[i][k]
        # 事件冲击（指数衰减 + dv/dt 钳制）
        for ev in events:
            days_since = (age - ev.get('age', 0)) * 365
            if 0 <= days_since < ev.get('days', 365):
                progress = days_since / ev['days']
                impact = math.exp(-progress * 2)
                sign = -1 if ev.get('damage') else 1
                for k, val in (ev.get('damage') or {}).items():
                    v[k] = v.get(k, 50) + sign * val * impact
        # dv/dt ≤ const 约束（年视图帧）
        for k in DIMS:
            delta = v[k] - prev_v[k]
            if abs(delta) > DV_DT_MAX:
                v[k] = prev_v[k] + DV_DT_MAX * (1 if delta > 0 else -1)
        # 钳制到 [5, 95]
        for k in DIMS:
            v[k] = max(5, min(95, round(v[k] * 10) / 10))
        prev_v = dict(v)
        dy_info = next((d for d in dayun if d['start'] <= age < d['end']), dayun[-1])
        year = birth_year + age
        ln = get_liunian(year)
        elems.append({
            'age': age,
            'day': age * 365,
            't': f"{year}·{age}岁·{dy_info.get('name', '?')}",
            'dayun': dy_info.get('name', '?'),
            'liunian': ln['g'] + ln['z'],
            'liunian_elem': ganzhi_main_elem(ln['g'], ln['z']),
            **v,
        })

    # v2 完整分析
    bounds_v2 = compute_health_bounds_v2(elems, innate)
    # v1 兼容输出（同时计算 v1 以保持回归基准）
    bounds_v1 = compute_health_bounds(elems, innate)

    return {
        'view_mode': 'year',
        'algorithm': 'spum_computeHealthBounds_v2',
        'theory_source': 'SPUM2611 + 青囊中医总纲 + tizhi-curve沙盒(流年+平滑)',
        'v_innate': innate,
        'dayun': dayun,
        'dayunMarkArea': [
            {'start_age': d['start'], 'end_age': d['end'],
             'name': d.get('name', ''), 'gan': d.get('gan', ''), 'zhi': d.get('zhi', '')}
            for d in dayun
        ],
        'elems': elems,
        # v2 三曲线（统一用 v2 结果，v1 仅作回归基准）
        'driftData': bounds_v2['driftData'],
        'yinTop': bounds_v2['yinTop'],
        'yangBot': bounds_v2['yangBot'],
        'diseaseModes': bounds_v2['diseaseModes'],
        'elArr': bounds_v2['elArr'],
        # v2 新增：三态 + 尖峰 + 自适应参数（tizhi-curve 沙盒核心判定）
        'stateFlags': bounds_v2['stateFlags'],
        'spikeUp': bounds_v2['spikeUp'],
        'spikeDown': bounds_v2['spikeDown'],
        # 2026-10-10 新增：5D 触边尖峰 + 弹回子类型 + 速度/方向 + S₀ 中心化漂移
        'spikeUp5d': bounds_v2['spikeUp5d'],
        'spikeDown5d': bounds_v2['spikeDown5d'],
        'reboundUp': bounds_v2['reboundUp'],
        'reboundDown': bounds_v2['reboundDown'],
        'velocity': bounds_v2['velocity'],
        'direction': bounds_v2['direction'],
        'driftCentered': bounds_v2['driftCentered'],
        'centroidBias': bounds_v2['centroidBias'],
        'adaptiveParams': bounds_v2['adaptiveParams'],
        # v2 深层分析（S 向量 / σ / 凸多面体 margin）
        'S_vectors': bounds_v2['S_vectors'],
        'sigma_trend': bounds_v2['sigma_trend'],
        'polytope_statuses': bounds_v2['polytope_statuses'],
        'violation_depths': bounds_v2['violation_depths'],
        'frame_residues': bounds_v2['frame_residues'],
        'health_score': bounds_v2['health_score'],
    }


# ════════════════════════════════════════════════════════════════
# V3 · Wuxing-FB 五形生克负反馈网络（2026-10-08 新增）
#
# 不替换 v2，作为旁路分析层：
#   - v2 原有 driftData / 边界 / 平滑全部保留（向后兼容）
#   - v3 新增 zone / tolerance_u* / weak_virtual 三个新信号
#   - 前端可选展示「耐受强度 u*」副轴（报告第 6 章产品意义）
#
# 理论: Wuxing-FB 研究报告 (wuxing-fb-report)
# ════════════════════════════════════════════════════════════════

# v3 注入标定（2026-10-08 修复）：
# 天时注入本征强度 = 固定绝对量（与个人无关），个人差异由 ρ₀（先天）表达。
# 模型口径：θ=1.0、健康 u*≈2.2~2.8。注入峰值 2.0 →
#   健康者（u*>2.0）带内为主、偶发 CRIT；虚弱者（u*<2.0）CRIT/OUT 增多 —— "同邪不同命"
U_PEAK_FIXED = 2.0   # 主维本征强度：健康者带内为主/偶发 CRIT，虚弱者 CRIT 偏多（先天地形判据）
                     # 注：仅形状模式（均值恒1）下 u* 差异≈8%，稳定 OUT 判别需观测绝对水平（调节视图）
INJECT_SIDE  = 0.4   # 非峰值维弱化系数（主维主导结构）

# Wuxing-FB 可选导入（独立模块，零依赖，导入失败不影响 v2）
try:
    from app.utils.wuxing_feedback import (
        DIMS as WX_DIMS,
        build_coupling_matrix as wx_build_A,
        compute_frame as wx_compute_frame,
        steady_state as wx_steady_state,
        to_relative as wx_to_relative,
        rho_from_relative as wx_rho0_from_rel,
        compute_thresholds as wx_theta,
        BETA_SHENG as wx_BS,
        BETA_KE as wx_BK,
        RHO_MAX as wx_RHO_MAX,
        _compute_tolerance as wx_tol,
    )
    WUXING_FB_AVAILABLE = True
except Exception:
    WUXING_FB_AVAILABLE = False


def wuxing_frame_analysis(innate: dict,
                          injection: dict,
                          n_steps: int = 12) -> Optional[dict]:
    """单帧 Wuxing-FB 分析（旁路 · 不替换 v2）

    Args:
        innate: 先天五行向量（任意口径，center=20 或 50 都行，会过 to_relative）
        injection: 注入向量（dayun + liunian + jieqi bias 之和）
        n_steps: 弛豫步数（默认 12，稳态）

    Returns:
        {
            's':        五维动态偏移 s_i（稳态）
            'rho':      五维总势能 ρ_i = ρ₀_i + s_i
            'theta':    五维逆转阈值 θ_i（动态）
            'zone':     每维 IN/CRIT/OUT 带状态
            'weak_virtual': {虚:[], 实:[], 临界:[], 带内:[]}
            'tolerance_u':   各维耐受强度 u*（使该维破阈值的最小注入）
            'min_tolerance': 最弱方向 (dim, u*) — 邪之所凑其气必虚
            'gap':       当前注入 vs 耐受强度的裕度 gap_i = u*_i - |s_i|
        }
        或 None（Wuxing-FB 模块不可用时）
    """
    if not WUXING_FB_AVAILABLE:
        return None

    try:
        result = wx_compute_frame(innate, injection, n_steps=n_steps)

        # 最弱方向
        tol = result['tolerance_u']
        min_dim = min(tol, key=lambda d: tol[d])
        min_u = tol[min_dim]

        # 裕度 gap = u* - |s| 越大越安全
        gap = {d: round(tol[d] - abs(result['s'][d]), 3) for d in WX_DIMS}

        # weak_virtual dict keys 里加带内
        wv = result['weak_virtual']
        # normalize keys（2026-10-10：zone 标签体系为 IN/CRIT/实/虚，
        # 旧写法把 CRIT 也计入带内、'临界' 恒空 —— 修正为精确语义）
        zone_map = result['zone']
        in_zone = [d for d, z in zone_map.items() if z == 'IN']

        return {
            's': {d: round(result['s'][d], 4) for d in WX_DIMS},
            'rho': {d: round(result['rho'][d], 4) for d in WX_DIMS},
            'theta': {d: round(result['theta'][d], 4) for d in WX_DIMS},
            'zone': zone_map,
            'weak_virtual': {
                '虚': wv.get('虚', []),
                '实': wv.get('实', []),
                '临界': [d for d, z in zone_map.items() if z == 'CRIT'],
                '带内': in_zone,
            },
            'tolerance_u': tol,
            'min_tolerance': {'dim': min_dim, 'u_star': round(min_u, 3)},
            'gap': gap,
        }
    except Exception as e:
        import logging as _lg
        _lg.getLogger(__name__).warning(f"Wuxing-FB frame analysis failed: {e}")
        return None


# ════════════════════════════════════════════════════════════════
# V3.1 · 阴阳投影层（tizhi-curve 借鉴 · 2026-10-09）
#
# 把 Wuxing-FB 五维相对偏移 s 翻译成旧版"人生曲线"的直观形态：
#   阳偏 = 火/木发散力（s_fire, s_wood 加权）—— 阳化气
#   阴偏 = 土/水收敛力（s_earth, s_water 加权）—— 阴成形
#   金   = 边界调节器，不投影（SPUM 本体：金决定区间弹性，algorithm.md:51）
#   实线 = 有符号阴阳偏移 drift_yy（正=阳偏↑ 负=阴偏↓）
#   区间 = 逆转阈值 θ 投影 × 金弹性 × 生命周期包络（2D 呈现层）
#
# ⚠️ 判定仍在 5D（zone_series / 逆转阈值分岔）；本层只作可视化
#    （tizhi-curve 核实结论 4.2 约定：2D 只呈现，不承担判定）
# ════════════════════════════════════════════════════════════════

# 阴阳投影权重（沿用 tizhi-curve computeYX 的 SPUM 五行归属：
# 阳 = 火(∇σ 创生驱动)0.55 + 木(创生产物)0.45
# 阴 = 土(储备池)0.55 + 水(储能链)0.45）
YY_W_YANG = {'fire': 0.55, 'wood': 0.45}
YY_W_YIN = {'earth': 0.55, 'water': 0.45}


def yang_growth_factor(age: float) -> float:
    """阳生命周期包络（tizhi-curve yangAgeFactor 移植）：
    0-16 幼儿阳气充盛（sigmoid→2.5）；16-35 壮年峰值线性降；35+ 高斯衰退"""
    if not age or age <= 0:
        return 0.05
    if age <= 16:
        return (1 - math.exp(-age / 5)) * 2.5
    if age <= 35:
        return 2.5 - (age - 16) * (0.7 / 19)
    return max(0.15, 1.8 * math.exp(-((age - 35) ** 2) / (2 * 28 * 28)))


def yin_growth_factor(age: float) -> float:
    """阴生命周期包络（tizhi-curve yinAgeFactor 移植）：
    0-16 阴基本不动；16-35 壮年；35+ 同步衰退"""
    if not age or age <= 0:
        return 0.1
    if age <= 16:
        return 0.1 + (age / 16) * 0.6
    if age <= 35:
        return 0.7 + (age - 16) * (0.3 / 19)
    return max(0.15, 1.0 * math.exp(-((age - 35) ** 2) / (2 * 28 * 28)))


def build_yin_yang_projection(s_series: list, theta_series: list, ages: list,
                              metal_series: Optional[list] = None,
                              el_factor: Optional[callable] = None) -> dict:
    """五维相对偏移 s → 有符号阴阳偏移 + 阴阳健康区间（呈现层）

    Args:
        s_series:     [{wood,fire,earth,metal,water}, ...] 稳态 s（Wuxing-FB 相对空间）
        theta_series: [{wood,fire,earth,metal,water}, ...] 逆转阈值 θ（动态）
        ages:         [age, ...] 每个点年龄（生命周期包络用）
        metal_series: [metal, ...] 金分量原始值（弹性调制，可选）
        el_factor:    el→有效弹性系数，默认 0.4+0.6el（[0.58, 1.0]）

    Returns:
        {drift_yy, yy_top, yy_bot, s_yang, s_yin,
         cap_yang, cap_yin, el_arr, yg_arr, yng_arr}
          drift_yy: 有符号阴阳偏移（正=阳偏↑ 负=阴偏↓）—— 实线
          yy_top:   +阴方向容量 × 弹性 × 阴生命周期（阴界，正值，在上）
          yy_bot:   −阳方向容量 × 弹性 × 阳生命周期（阳界，负值，在下）
          cap_yang/cap_yin: 逆转阈值最弱维容量（邪之所凑其气必虚）
    """
    n = len(s_series)
    if n == 0:
        return {'drift_yy': [], 'yy_top': [], 'yy_bot': [],
                's_yang': [], 's_yin': [], 'cap_yang': [], 'cap_yin': [],
                'el_arr': [], 'yg_arr': [], 'yng_arr': []}
    ef = el_factor or (lambda el: 0.4 + 0.6 * el)

    drift_yy, yy_top, yy_bot = [], [], []
    s_yang_list, s_yin_list = [], []
    cap_yang_list, cap_yin_list = [], []
    el_list, yg_list, yng_list = [], [], []

    for i in range(n):
        s = s_series[i] or {}
        th = theta_series[i] or {}
        age = ages[i] if i < len(ages) else 30

        # 阴阳投影（金不参与，SPUM 本体：金=边界调节器）
        s_yang = sum(w * s.get(d, 0.0) for d, w in YY_W_YANG.items())
        s_yin = sum(w * s.get(d, 0.0) for d, w in YY_W_YIN.items())

        # 区间容量 = 各方向最弱维逆转阈值（邪之所凑其气必虚）
        cap_yang = min(th.get('fire', 1.0), th.get('wood', 1.0))
        cap_yin = min(th.get('earth', 1.0), th.get('water', 1.0))

        # 金弹性（金形状态 → 区间有效宽度，不影响判定）
        if metal_series is not None and i < len(metal_series):
            el = metal_elasticity(float(metal_series[i] or 50.0))
        else:
            el = 1.0
        el_list.append(round(el, 3))

        # 生命周期包络（呈现层调制）
        yg = yang_growth_factor(age)
        yng = yin_growth_factor(age)
        yg_list.append(round(yg, 4))
        yng_list.append(round(yng, 4))

        yy_top.append(round(cap_yin * ef(el) * yng, 4))
        yy_bot.append(round(-cap_yang * ef(el) * yg, 4))
        drift_yy.append(round(s_yang - s_yin, 4))
        s_yang_list.append(round(s_yang, 4))
        s_yin_list.append(round(s_yin, 4))
        cap_yang_list.append(round(cap_yang, 4))
        cap_yin_list.append(round(cap_yin, 4))

    return {'drift_yy': drift_yy, 'yy_top': yy_top, 'yy_bot': yy_bot,
            's_yang': s_yang_list, 's_yin': s_yin_list,
            'cap_yang': cap_yang_list, 'cap_yin': cap_yin_list,
            'el_arr': el_list, 'yg_arr': yg_list, 'yng_arr': yng_list}


def build_year_view_v3(innate: dict, dayun: list, age_start: int = 0,
                       age_end: int = 80, birth_year: int = 1957,
                       events: Optional[list] = None,
                       interventions: Optional[list] = None) -> dict:
    """v3 终身推演 — 在 v2 基础上叠加 Wuxing-FB 旁路分析

    不替换 v2 输出结构，新增:
      - driftData_wuxing: 基于 Wuxing-FB s_i 的体质偏移曲线（平行 driftData）
      - tolerance_u_series: 逐年最弱方向 u*（青囊调平的量化目标）
      - zone_statuses: 逐年五维带状态
      - weak_virtual_series: 逐年虚实演化（用于调节视图 projected/actual 对比）

    interventions（2026-10-08 新增，调节视图 actual 使用）:
      [{'age': 40, 'dim': 'metal', 'strength': 0.8, ...}]
      age ≥ 指定年龄后，每年向 dim 维追加补虚注入 strength（调平干预）：
      虚维被正向拉起 → u* 抬升、CRIT/OUT 减少 → 与 projected（无干预）对比即"调平收益"。

    原 v2 三曲线 + stateFlags + health_score 全部保留（向后兼容）。
    """
    # 先跑 v2（保留全部原有输出）
    v2_result = build_year_view_v2(innate, dayun, age_start, age_end, birth_year, events)

    if not WUXING_FB_AVAILABLE:
        v2_result['algorithm'] = 'spum_computeHealthBounds_v2 (wuxing_fb 未加载)'
        return v2_result

    # Wuxing-FB 耦合矩阵（默认 β_s=0.60, β_k=0.40）
    A_mat = wx_build_A()

    # 先天向量 → 相对构型 → 势能基底（柔和映射，仅形状；无观测绝对水平）
    # 2026-10-10 口径统一：缺省 50.0 与 v2 HEALTH_CENTROID 一致（旧 20.0 使
    # 未传 innate 时 v3 rho0 与 v2 语义不同；to_relative 对中心不敏感但保持一致性）
    v_rel = wx_to_relative({d: float(innate.get(d, 50.0)) for d in WX_DIMS})
    rho0 = wx_rho0_from_rel(v_rel, equilibrium=1.0)

    # ── 注入标定（2026-10-08 修复）──────────────────────────────
    # 旧实现：dayun/liunian 输出 ±4~±10，被硬帽压到 ±2.0，未对标模型口径
    #         （u*≈2.79，u=2.0 已是强邪）→ zone 全 IN、无区分度。
    # 新实现：天时注入本征强度固定（U_PEAK_FIXED=2.0），方向保留、
    #         峰值归一 —— 健康者带内为主、虚弱者 CRIT/OUT 增多（同邪不同命）
    u_peak = U_PEAK_FIXED

    # 逐年注入（大运 + 流年） → 弛豫 → 取稳态
    n_ages = age_end - age_start + 1
    driftData_wuxing = []
    tol_u_series = []
    zone_series = []
    weak_virtual_series = []
    s_series = []
    max_s_series = []

    # 串联弛豫：s 在逐年间传递（2026-10-09 新增）
    # 旧：每年龄独立弛豫（从 s=0 起）→ 仅反映"该年孤立注入"效果
    # 新：年龄 N 的 s 作为 N+1 的 s_start → 累积偏移 / 调平效应可传递
    #     每步 dt=DT(0.25)，每年龄弛豫 4 步 = 1 年（与 year-view 粒度匹配）
    cur_s = {d: 0.0 for d in WX_DIMS}

    for age in range(age_start, age_end + 1):
        # 获取该年大运偏移
        cur_dy = None
        for d in dayun:
            if d.get('start', 0) <= age < d.get('end', 100):
                cur_dy = d
                break
        if cur_dy is None and dayun:
            cur_dy = dayun[-1]

        # 大运注入
        dy_elems = ganzhi_to_elems(cur_dy.get('gan', '?'), cur_dy.get('zhi', '?'), wg=0.3, wz=0.7)
        # 流年注入
        year = birth_year + age
        ln = get_liunian(year)
        ln_delta = liunian_delta(ln['g'], ln['z'])

        # 合成注入向量 → 主维主导结构（2026-10-08 修复）
        # 旧：整体归一 + 硬帽 ±2.0 → 多维注入互相牵制（水涨船高），zone 全 IN。
        # 新：峰值维（|raw| 最大）保持 u_peak 本征强度，其余维按 0.4 弱化 →
        #     行为接近单维扫描，判别窗口（u* 单维定义）得以重现
        raw_inj = {}
        for d in WX_DIMS:
            raw_inj[d] = dy_elems.get(d, 0.0) * 0.3 + ln_delta.get(d, 0.0) * 0.7
        max_abs = max(abs(x) for x in raw_inj.values()) if raw_inj else 0.0
        if max_abs > 1e-9:
            inj = {d: raw_inj[d] / max_abs * u_peak * (1.0 if abs(raw_inj[d]) >= max_abs - 1e-9 else INJECT_SIDE) for d in WX_DIMS}
        else:
            inj = {d: 0.0 for d in WX_DIMS}

        # 调平干预（actual 曲线）：修正 ρ₀ 基底（2026-10-08 v2 设计）
        # 补虚 = 增强虚维势能基底（ρ₀[dim] += strength，持久）→ 该维阻尼升、耐受升，
        # 区间变宽 —— 而非向虚维注入正 u（那只会把虚推成实，不改变 u*）。
        rho0_eff = rho0
        if interventions:
            for iv in interventions:
                if age >= int(iv.get('age', 999)):
                    dim = iv.get('dim')
                    if dim in WX_DIMS:
                        if rho0_eff is rho0:
                            rho0_eff = dict(rho0)
                        rho0_eff[dim] = min(wx_RHO_MAX, rho0_eff.get(dim, 1.0) + float(iv.get('strength', 1.2)))

        # 弛豫（用干预后的 rho0_eff 基底，从上一年 cur_s 串联）
        # 2026-10-09 修复：n_steps 4→12 —— 之前取"1年=4步"的未收敛准稳态，
        #   s 只到瞬态 ≈0.38，永远够不到阈值 0.7θ → zone 全 IN、体质无区分。
        #   steady_state 的语义是"弛豫取稳态"（复核脚本判别窗口即 12 步稳态，
        #   虚弱组 CRIT fin=0.61）；year-view 也应按稳态取，否则 B 修复的
        #   "同邪不同命"（健康带内为主、虚弱 CRIT/OUT 增多）在终身曲线上失效。
        ss = wx_steady_state(rho0_eff, inj, A_mat, n_steps=12, s_start=cur_s)
        cur_s = ss['s']  # 传递给下一年

        # 相对空间体质偏移（去 ×5 魔法数，量纲与 θ=1.0 一致）
        s_abs = [abs(ss['s'][d]) for d in WX_DIMS]
        s_mean = sum(s_abs) / len(WX_DIMS)
        driftData_wuxing.append(round(-s_mean, 3))
        s_series.append({d: round(ss['s'][d], 4) for d in WX_DIMS})
        max_s_series.append(round(-max(s_abs), 3))

        # 最弱方向 u*
        tol = ss['tolerance_u']
        min_d = min(tol, key=lambda k: tol[k])
        tol_u_series.append({
            'age': age,
            'tolerance_u_star': round(tol[min_d], 3),
            'weakest_dim': min_d,
            'all_u_star': {d: round(tol[d], 3) for d in WX_DIMS},
        })

        # zone
        zone_series.append({
            'age': age,
            'zone': ss['zone'],
            'theta': {d: round(ss['theta'][d], 3) for d in WX_DIMS},
        })

        # 虚实
        wv = ss['weak_virtual']
        weak_virtual_series.append({
            'age': age,
            '虚': wv.get('虚', []),
            '实': wv.get('实', []),
            '临界': wv.get('临界', []),
            '带内': wv.get('带内', []),
        })

    # 回写到 v2 结果（扩展而非替换）
    v2_result['algorithm'] = 'spum_computeHealthBounds_v3 + wuxing_fb_v1'
    v2_result['theory_source'] = 'Wuxing-FB 五形生克负反馈网络 β_s=0.60/β_k=0.40 (2026-10-08)'
    v2_result['wuxing_fb'] = {
        'available': True,
        'params': {
            'beta_s': wx_BS, 'beta_k': wx_BK,
            'theta0': 1.0, 'gamma': 0.6, 'dt': 0.25,
            'u_peak': u_peak,
        },
        'rho0': {d: round(rho0[d], 4) for d in WX_DIMS},
        'driftData_wuxing': driftData_wuxing,        # 相对空间 s 均值（−s_mean，量纲与 θ=1.0 一致）
        's_series': s_series,                        # 每维稳态 s（相对空间）
        's_mean_series': driftData_wuxing,           # 别名：五维 |s| 均值（负号=翻转对齐）
        'max_s_series': max_s_series,                # 五维 max|s|（当前最大偏移维，负号对齐）
        'tolerance_u_series': tol_u_series,          # 动态 u*（从当前状态起扫，随调平移动）
        'zone_series': zone_series,
        'weak_virtual_series': weak_virtual_series,
    }

    # ── 阴阳投影层（tizhi-curve 借鉴 · 2026-10-09）────────────────
    # 人生曲线主呈现：有符号阴阳偏移（实线）+ 逆转阈值阴阳区间（黄/红线）
    # 生命周期包络（0-16 阳盛 / 16-35 壮年 / 35+ 衰退）只调 2D 呈现宽度，
    # 不参与 5D 判定（zone_series 是唯一判定源）
    try:
        yy_ages = list(range(age_start, age_end + 1))[:len(s_series)]
        yy_theta = [zs['theta'] for zs in zone_series]
        yy_metal = [s.get('metal', 50.0) for s in s_series]
        v2_result['wuxing_fb']['yin_yang'] = build_yin_yang_projection(
            s_series, yy_theta, yy_ages, metal_series=yy_metal,
        )
    except Exception as _yy_e:
        import logging as _yy_lg
        _yy_lg.getLogger(__name__).warning(f"yin_yang projection failed: {_yy_e}")
        v2_result['wuxing_fb']['yin_yang'] = None
    return v2_result


def build_jieqi_view_v3(calendar_year: int, dayun_active_gz: dict,
                        liunian_gz: dict, jieqi_dates: list,
                        innate: Optional[dict] = None) -> dict:
    """节气视图 v3 — 在 v2 的 24 节气基础上叠加 Wuxing-FB 分析

    每帧节气 = 大运 + 流年 + 节气五行 bias 合成注入 → 弛豫 → 取稳态
    新增字段: tolerance_u*, zone, weak_virtual
    """
    # 先跑 v2（保留全部原有字段）
    v2 = build_jieqi_view_v2(calendar_year, dayun_active_gz, liunian_gz, jieqi_dates)

    if not WUXING_FB_AVAILABLE:
        v2['algorithm'] = 'jieqi_view_v2 (wuxing_fb 未加载)'
        return v2

    # 构造 rho0（如果给了 innate，用它；否则用均匀 1.0 基底）
    # 2026-10-10 口径统一：缺省 50.0 与 v2 HEALTH_CENTROID 一致
    if innate:
        v_rel = wx_to_relative({d: float(innate.get(d, 50.0)) for d in WX_DIMS})
        rho0 = wx_rho0_from_rel(v_rel, equilibrium=1.0)
    else:
        rho0 = {d: 1.0 for d in WX_DIMS}

    A_mat = wx_build_A()

    # ── 注入标定（2026-10-09 修复：节气视图让 bias 主导）─────────────
    # 节气 bias 量级 ±1.5，大运+流年 ±16 — bias 被完全淹没，24 帧无区分度。
    # 合成权重: dy×0.3 + ln×0.3 + bias×3.0 → bias 成为主导差异信号
    # （year-view 用 dy×0.3 + ln×0.7，区别在于 year-view 大运已按年切换）
    u_peak = U_PEAK_FIXED

    # ── 节气视图：串联弛豫（2026-10-09 新增）─────────────────────
    # 立春 → 雨水 → ... 大寒，s 状态在 24 节气间串联传递。
    # dt = 0.25（year-view 标准步长），每帧 4 步弛豫 = 1 年/帧。
    # 模型含义：每个节气节点代表 1 年的体质演化快照（节气注入×大运流年背景）。
    # 24 帧 × 1 年 = 24 年的体质演化浓缩到一个日历年的 24 个状态点。

    cur_s = {d: 0.0 for d in WX_DIMS}  # 初始 s（年初 = 中和）

    # 每帧节气跑 Wuxing-FB
    jieqi_v3 = []
    for jq in v2['jieqi']:
        # 注入 = 大运(弱背景) + 流年(弱背景) + 节气(主导) → 各帧有区分度
        raw_inj = {}
        for d in WX_DIMS:
            raw_inj[d] = (jq['dayun_impact'].get(d, 0) * 0.3 +
                         jq['liunian_impact'].get(d, 0) * 0.3 +
                         jq['wuxing_bias'].get(d, 0) * 3.0)
        max_abs = max(abs(x) for x in raw_inj.values()) if raw_inj else 0.0
        if max_abs > 1e-9:
            inj = {d: raw_inj[d] / max_abs * u_peak * (1.0 if abs(raw_inj[d]) >= max_abs - 1e-9 else INJECT_SIDE) for d in WX_DIMS}
        else:
            inj = {d: 0.0 for d in WX_DIMS}

        # 串联弛豫：从上一节气的 s 起弛豫 4 步（dt=0.25 → 1 年/帧）
        ss = wx_steady_state(rho0, inj, A_mat, n_steps=4, s_start=cur_s)
        cur_s = ss['s']  # 传递给下一节气

        tol = ss['tolerance_u']
        min_d = min(tol, key=lambda k: tol[k])

        jq_out = dict(jq)  # copy v2 fields
        jq_out['tolerance_u'] = {d: round(tol[d], 3) for d in WX_DIMS}
        jq_out['min_tolerance'] = {'dim': min_d, 'u_star': round(tol[min_d], 3)}
        jq_out['zone'] = ss['zone']
        jq_out['weak_virtual'] = ss['weak_virtual']
        jq_out['s_wuxing'] = {d: round(ss['s'][d], 4) for d in WX_DIMS}
        jq_out['gap'] = {d: round(tol[d] - abs(ss['s'][d]), 3) for d in WX_DIMS}
        jieqi_v3.append(jq_out)

    v2['algorithm'] = 'jieqi_view_v3 + wuxing_fb_v1'
    v2['theory_source'] = 'Wuxing-FB β_s=0.60/β_k=0.40'
    v2['jieqi'] = jieqi_v3
    v2['rho0'] = {d: round(rho0[d], 4) for d in WX_DIMS}
    return v2
