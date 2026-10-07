"""五形 / 时辰 / 飞星常量 + SPUM 工具函数

图论建模纪律（取代之前的叙事层耦合）：
  - 五个形 = 同一张图的五个拓扑不变量（spum-core.md §6.1）
  - 耦合 = 同一张图上改变任何一个不变量，其他四个**必然联动**
  - 不需要 if-else 因果叙事，不需要"火驱动水"——那是实体本体范式
  - 图论来源：
      木 = μ = M - N + C              (环基数)
      火 = Φ = Var(degree)            (度分布方差/不均匀度)
      土 = F = 1 - |最大连通分量|/N    (碎片化指数)
      金 = B = nx.bridges()           (桥边数)
      水 = L = nx.average_shortest_path_length()

⚠️ 后端目前只有五维向量 S（center=20 概率分布），没有真实图结构。
   所以：1) 从 S 反推一张图；2) 在图上算不变量的真实耦合。
   这是 L1 投影层 → L0 图论本体的桥接。
"""
from __future__ import annotations
from typing import Literal
import math
import random
import networkx as nx

WUXING = Literal["wood", "fire", "earth", "metal", "water"]

WUXING_NAMES: dict[str, str] = {
    "wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"
}
WUXING_LIST = ["wood", "fire", "earth", "metal", "water"]

# 十二时辰
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
# 图论耦合：同一张图上五个拓扑不变量的数学互锁
# ════════════════════════════════════════════════════════════════

def _graph_invariants(G) -> dict[str, float]:
    """在图 G 上算五个拓扑不变量（对应五形）"""
    N = G.number_of_nodes()
    M = G.number_of_edges()
    C = nx.number_connected_components(G)
    mu = M - N + C                                    # 木 = 环基数
    degrees = [d for _, d in G.degree()]
    mean_d = sum(degrees) / max(len(degrees), 1)
    fire = sum((d - mean_d) ** 2 for d in degrees) / max(len(degrees), 1)  # 火 = Var(k)
    largest_cc = max((len(c) for c in nx.connected_components(G)), default=1)
    earth = 1.0 - largest_cc / max(N, 1)              # 土 = 碎片化
    metal = len(list(nx.bridges(G)))                  # 金 = 桥边数
    water = nx.average_shortest_path_length(G) if nx.is_connected(G) else 99.0  # 水 = 平均路径
    return {
        'wood': mu, 'fire': round(fire, 3),
        'earth': round(earth, 3), 'metal': metal, 'water': round(water, 3),
    }


def _vector_to_graph_params(s: dict[str, float], N: int = 40) -> dict:
    """从 center=20 五维向量反推图生成参数

    这是 L1 投影 → L0 图论的锚定：
      wood 高 → 高 μ → 高边密度
      fire 高 → 高度方差 → 度分布不均匀
      earth 高 → 高碎片化 → 多连通分量
      metal 高 → 多桥边 → 密度中等但有桥
      water 高 → 长路径 → 低边密度
    """
    vals = {k: float(s.get(k, 20)) for k in WUXING_LIST}
    # center=20 → 边概率 ≈ 0.10-0.15 的随机图
    density = 0.08 + (vals['wood'] - 20) * 0.004   # wood↑ → 边密
    # 碎片化 → 图生成后可能要加孤立节点
    isolated_count = int(vals['earth'] / 2)
    # fire 高 → 用 BA (Barabási-Albert) 而非 ER（BA 有 hub，度方差大）
    use_ba = vals['fire'] > 25
    return {
        'N': N, 'density': max(0.03, min(0.40, density)),
        'isolated': isolated_count, 'use_ba': use_ba,
    }


def _build_graph(params: dict):
    """根据参数生成图"""
    N = params['N']
    if params['use_ba']:
        G = nx.barabasi_albert_graph(N, 2)   # BA 模型 → 度方差大 → 火旺
    else:
        G = nx.erdos_renyi_graph(N, params['density'])
        while not nx.is_connected(G):
            comps = list(nx.connected_components(G))
            for i in range(1, len(comps)):
                u = list(comps[i])[0]
                G.add_edge(u, list(comps[0])[0])
    for i in range(params['isolated']):
        G.add_node(N + i)
    return G


def graph_coupling_matrix(s: dict[str, float], N: int = 40) -> dict[str, dict[str, float]]:
    """计算图论耦合矩阵：改变一个不变量，其他四个跟着变多少

    Returns:
        5×5 耦合矩阵 {from_wux → {to_wux → delta_per_unit}}
        这个矩阵**完全从图的数学性质涌现**，没有叙事层假设。

    用法：任何逐维独立运算（vector_similarity 等）的结果乘以这个矩阵，
    就能得到耦合修正后的向量。
    """
    import networkx as nx
    params = _vector_to_graph_params(s, N)
    G_base = _build_graph(params)
    base_inv = _graph_invariants(G_base)

    # 对每个形做 +10% 边操作，观察其他形的变化
    coupling = {}
    edge_step = max(1, G_base.number_of_edges() // 10)

    for target in WUXING_LIST:
        G_test = G_base.copy()
        if target == 'wood':
            for _ in range(edge_step):
                u, v = random.sample(range(G_test.number_of_nodes()), 2)
                if not G_test.has_edge(u, v):
                    G_test.add_edge(u, v)
        elif target == 'metal':
            bridges = list(nx.bridges(G_test))[:edge_step]
            for u, v in bridges:
                G_test.remove_edge(u, v)
        elif target == 'earth':
            cur_N = G_test.number_of_nodes()
            for i in range(edge_step):
                G_test.add_node(cur_N + i)
        elif target == 'water':
            edges = list(G_test.edges())[:edge_step]
            for u, v in edges:
                if G_test.has_edge(u, v):
                    G_test.remove_edge(u, v)
            while not nx.is_connected(G_test) and G_test.number_of_edges() > 0:
                comps = list(nx.connected_components(G_test))
                if len(comps) < 2: break
                G_test.add_edge(list(comps[0])[0], list(comps[1])[0])
        elif target == 'fire':
            hubs = random.sample(range(G_test.number_of_nodes()), min(3, G_test.number_of_nodes()))
            for h in hubs:
                others = [n for n in range(G_test.number_of_nodes()) if n != h]
                for n in random.sample(others, min(5, len(others))):
                    if not G_test.has_edge(h, n):
                        G_test.add_edge(h, n)

        test_inv = _graph_invariants(G_test)
        # 归一化：每个目标形自己的改变量 → 其他形的归一化耦合系数
        self_delta = test_inv[target] - base_inv[target]
        row = {}
        for w in WUXING_LIST:
            if self_delta == 0:
                row[w] = 0.0
            else:
                row[w] = round((test_inv[w] - base_inv[w]) / abs(self_delta), 4)
        coupling[target] = row

    return coupling


def vector_coupled_transform(
    s: dict[str, float],
    coupling: dict[str, dict[str, float]] | None = None,
) -> dict[str, float]:
    """用图论耦合矩阵修正五维向量

    不是叙事层"火驱动水"的 if-else 链。
    而是：给定同一张图上五个不变量的真实耦合系数矩阵，
    把输入向量的各维偏离，按耦合矩阵重分配。

    Args:
        s: center=20 五维向量
        coupling: 预计算的耦合矩阵（默认实时算，生产应缓存）

    Returns:
        耦合修正后的向量
    """
    if coupling is None:
        coupling = graph_coupling_matrix(s)
    deviations = {w: s.get(w, 20) - 20 for w in WUXING_LIST}  # 偏离 center
    result = {w: 0.0 for w in WUXING_LIST}
    for w in WUXING_LIST:
        # 每个形的最终偏离 = 所有其他形偏离 × 它们到 w 的耦合系数
        total = 0.0
        for src in WUXING_LIST:
            if src == w:
                total += deviations[src] * 1.0  # 自耦合系数默认 1
            else:
                total += deviations[src] * coupling[src].get(w, 0.0)
        result[w] = max(0, 20 + total)
    # 归一化回 center=20 口径 Σ≈100
    total = sum(result.values())
    if total > 0:
        scale = 100.0 / total
        result = {w: round(v * scale, 2) for w, v in result.items()}
    return result


# ════════════════════════════════════════════════════════════════
# 以下函数保持签名兼容，但输入先过图论耦合修正
# ════════════════════════════════════════════════════════════════

def vector_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """余弦相似度 — 先对输入做图论耦合修正再算

    ⚠️ 纪律：不是逐维独立算。先把 a,b 各维偏离按图的真实耦合矩阵重分配。
    """
    ac = vector_coupled_transform(a)
    bc = vector_coupled_transform(b)
    dot = sum(ac.get(k, 0) * bc.get(k, 0) for k in WUXING_LIST)
    na = math.sqrt(sum(v * v for v in ac.values()))
    nb = math.sqrt(sum(v * v for v in bc.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def vector_intersection(a: dict[str, float], b: dict[str, float],
                        threshold: float = 50) -> list[str]:
    """两个向量都偏弱的五形 — 共同弱项（先耦合修正）"""
    ac = vector_coupled_transform(a)
    bc = vector_coupled_transform(b)
    return [w for w in WUXING_LIST if ac.get(w, 100) < threshold and bc.get(w, 100) < threshold]


def vector_complement(a: dict[str, float], b: dict[str, float],
                      hi: float = 70, lo: float = 45) -> list[str]:
    """一个高一个低的五形 — 互补（先耦合修正）"""
    ac = vector_coupled_transform(a)
    bc = vector_coupled_transform(b)
    result = []
    for w in WUXING_LIST:
        av, bv = ac.get(w, 50), bc.get(w, 50)
        if (av > hi and bv < lo) or (bv > hi and av < lo):
            result.append(w)
    return result
