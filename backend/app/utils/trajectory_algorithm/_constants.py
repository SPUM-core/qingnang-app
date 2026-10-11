"""_constants - SPUM 轨迹算法公共常量（v1/v2/v3 全部常量单一信源）"""
from __future__ import annotations
import math

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


_GAN_CHARS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
_ZHI_CHARS = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

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



U_PEAK_FIXED = 2.0   # 主维本征强度：健康者带内为主/偶发 CRIT，虚弱者 CRIT 偏多（先天地形判据）
                     # 注：仅形状模式（均值恒1）下 u* 差异≈8%，稳定 OUT 判别需观测绝对水平（调节视图）
INJECT_SIDE  = 0.4   # 非峰值维弱化系数（主维主导结构）

YY_W_YANG = {'fire': 0.55, 'wood': 0.45}
YY_W_YIN = {'earth': 0.55, 'water': 0.45}