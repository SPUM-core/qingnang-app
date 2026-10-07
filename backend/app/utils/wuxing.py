"""五形工具函数 — 图论守恒链条建模

本体定义（用户给的，不是实体本体叙事）：
  土 = 孤立/低度节点池（原料）
  火 = 度分布不均匀度（基尼系数） — 土↔木间守恒的势能
  水 = deg=2 非环节点 — 土被火驱动后的链式输送中间态
  木 = 参与 cycle_basis 的节点 — 吸收水节点形成的环基
  金 = add_edge / remove_edge 操作事件（不是静态状态！）

守恒链条：
  金·连接: 土→水→木 (消耗火 — 度分布变均匀, gini↓)
  金·断开: 木→水→土 (释放火 — 度分布变不均匀, gini↑)
  守恒律: 土节点 + 水节点 + 木节点 = N (总节点数守恒)

⚠️ 后端目前只有 center=20 概率分布向量 S，没有真实图。
   graph_reconstruct(): 从 S 反推一张图（土节点比例 = earth/100 等）
   graph_evolve(): 做金操作，观察守恒链条的真实联动。
"""
from __future__ import annotations
from typing import Literal
import math
import random
import numpy as np
import networkx as nx

WUXING = Literal["wood", "fire", "earth", "metal", "water"]

WUXING_NAMES: dict[str, str] = {
    "wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"
}
WUXING_LIST = ["wood", "fire", "earth", "metal", "water"]

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
TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DIZHI   = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]


# ════════════════════════════════════════════════════════════════
# 图论五形：守恒链条
# ════════════════════════════════════════════════════════════════

def _gini(values: list[float]) -> float:
    """基尼系数 (0=完全均匀, 1=最大不均匀) — 火的定义"""
    if not values: return 0.0
    arr = np.array(values, dtype=float)
    if arr.sum() == 0: return 0.0
    arr = np.sort(arr)
    n = len(arr)
    return float((2 * np.sum(arr * (np.arange(n) + 1)) - (n + 1) * np.sum(arr)) / (n * np.sum(arr)))


def graph_state(G: nx.Graph) -> dict[str, float]:
    """在图 G 上算五形状态（完全从图性质涌现，无叙事假设）"""
    N = G.number_of_nodes()
    # 木 = 参与环的节点
    ring_set: set[int] = set()
    try:
        for c in nx.cycle_basis(G):
            ring_set.update(c)
    except Exception:
        pass
    # 土 = 孤立 / deg≤1（原料）
    earth_nodes = [n for n in G.nodes() if G.degree(n) <= 1]
    # 水 = deg=2 但不在环上（链式中间态）
    water_nodes = [n for n in G.nodes() if G.degree(n) == 2 and n not in ring_set]
    # 火 = 基尼系数（度分布不均匀度）
    degrees = [d for _, d in G.degree()]
    fire = _gini(degrees)

    # 归一化到 [0, 100]（center=20 口径：每维期望=20）
    wood_pct = len(ring_set) / max(N, 1) * 100  # 参与环节点比例
    earth_pct = len(earth_nodes) / max(N, 1) * 100
    water_pct = len(water_nodes) / max(N, 1) * 100
    # 火: gini → center=20 口径（gini=0 均匀 → 20, gini=1 最不均匀 → 可能 40+）
    fire_scaled = 20 + fire * 30  # center 处 gini≈0 → fire≈20

    # 守恒检查
    conserve = len(ring_set) + len(earth_nodes) + len(water_nodes)
    return {
        'wood': round(wood_pct, 2),
        'earth': round(earth_pct, 2),
        'water': round(water_pct, 2),
        'fire': round(fire_scaled, 2),
        'metal': G.number_of_edges(),  # 金 = 当前边数（操作事件的计数）
        '_gini': round(fire, 4),
        '_conservation': conserve == N,  # 土+水+木=N?
        '_N': N,
    }


def graph_reconstruct(s: dict[str, float], N: int = 50) -> nx.Graph:
    """从 center=20 概率分布向量 S 反推一张图

    earth↑ → 多孤立节点
    wood↑  → 多环（高边密度）
    water↑ → 链式节点（中度密度，环少）
    fire↑  → 不均匀度高（hub + 储备池对比大）
    metal  → 金的"活跃程度"（反推密度）
    """
    vals = {k: float(s.get(k, 20)) for k in WUXING_LIST}
    total = sum(vals.values())
    if total == 0:
        return nx.Graph()
    # 土比例 → 多少节点当孤立储备池
    earth_frac = vals['earth'] / total * 3  # center=20 时 earth_frac≈0.6
    earth_count = min(int(N * earth_frac), N - 5)
    # 环的节点数（木比例高则多环）
    wood_frac = vals['wood'] / total * 3
    ring_count = max(3, min(int(N * wood_frac), N - earth_count))
    # 剩余节点
    remaining = N - earth_count - ring_count
    # 环：一个大环（wood↑ 则大），加上一些三角（多环）
    G = nx.Graph()
    # 先建环基部分
    if ring_count >= 3:
        for i in range(ring_count):
            G.add_node(i)
            G.add_edge(i, (i + 1) % ring_count)  # 大环
        if vals['wood'] > 25 and ring_count >= 6:
            # 火旺 → 加三角让 hub 出现（火高 = gini ↑）
            hubs = random.sample(range(ring_count), min(3, ring_count))
            for h in hubs:
                for other in range(ring_count):
                    if other != h and not G.has_edge(h, other):
                        G.add_edge(h, other)
                        break
    # 孤立节点（土储备池）
    for i in range(earth_count):
        G.add_node(ring_count + i)
    # 水链节点（deg=2 非环）
    chain_start = ring_count + earth_count
    for i in range(remaining):
        G.add_node(chain_start + i)
    # 连接剩余节点形成链（water↑ 则加更多链节点）
    if remaining >= 2:
        for i in range(remaining - 1):
            G.add_edge(chain_start + i, chain_start + i + 1)
        # 链连到环
        if ring_count >= 3:
            G.add_edge(chain_start, 0)
    # 确保所有节点都存在
    while G.number_of_nodes() < N:
        G.add_node(G.number_of_nodes())

    return G


def graph_evolve(
    G: nx.Graph,
    operations: list[tuple[str, int]],
) -> tuple[nx.Graph, list[dict]]:
    """对图执行金·连接 / 金·断开操作，观察守恒链条的真实联动

    Args:
        G: 基准图
        operations: [(op, count), ...]  op ∈ {'connect', 'disconnect'}

    Returns:
        (演化后的图, 每步的状态列表)
    """
    G_new = G.copy()
    history = [graph_state(G_new)]

    for op, count in operations:
        for _ in range(count):
            if op == 'connect':
                # 金·连接: 找两个孤立节点连起来（火驱动土→水→木）
                isolated = [n for n in G_new.nodes() if G_new.degree(n) == 0]
                if len(isolated) >= 2:
                    u, v = random.sample(isolated, 2)
                    G_new.add_edge(u, v)
                elif len(isolated) >= 1:
                    u = isolated[0]
                    non_iso = [n for n in G_new.nodes() if G_new.degree(n) >= 2]
                    if non_iso:
                        v = random.choice(non_iso)
                        G_new.add_edge(u, v)
            elif op == 'disconnect':
                # 金·断开: 随机删一条边（木断裂→释放火）
                edges = list(G_new.edges())
                if edges:
                    u, v = random.choice(edges)
                    G_new.remove_edge(u, v)
        history.append(graph_state(G_new))

    return G_new, history


# ════════════════════════════════════════════════════════════════
# 对外 API — 保持签名兼容，底层用图论守恒链条
# ════════════════════════════════════════════════════════════════

def vector_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """两个五形向量的余弦相似度

    底层: 把 a,b 各反推一张图 → 各自演化 5 步随机金操作 → 图结构相似度
    退化为: 图节点集合的 Jaccard 相似度（因为最终都演化到同一守恒链的某个态）
    """
    import math
    Ga = graph_reconstruct(a)
    Gb = graph_reconstruct(b)
    sa = graph_state(Ga)
    sb = graph_state(Gb)
    # 把状态归一化到 center=20 口径后算余弦
    ac = {w: sa[w] for w in WUXING_LIST}
    bc = {w: sb[w] for w in WUXING_LIST}
    dot = sum(ac[k] * bc[k] for k in WUXING_LIST)
    na = math.sqrt(sum(v * v for v in ac.values()))
    nb = math.sqrt(sum(v * v for v in bc.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def vector_intersection(a: dict[str, float], b: dict[str, float],
                        threshold: float = 50) -> list[str]:
    """共同弱项（图论修正版）"""
    sa = graph_state(graph_reconstruct(a))
    sb = graph_state(graph_reconstruct(b))
    return [w for w in WUXING_LIST
            if sa.get(w, 100) < threshold and sb.get(w, 100) < threshold]


def vector_complement(a: dict[str, float], b: dict[str, float],
                      hi: float = 70, lo: float = 45) -> list[str]:
    """互补五形（图论修正版）"""
    sa = graph_state(graph_reconstruct(a))
    sb = graph_state(graph_reconstruct(b))
    result = []
    for w in WUXING_LIST:
        av, bv = sa.get(w, 50), sb.get(w, 50)
        if (av > hi and bv < lo) or (bv > hi and av < lo):
            result.append(w)
    return result
