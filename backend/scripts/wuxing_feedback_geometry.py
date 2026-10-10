# -*- coding: utf-8 -*-
"""wuxing_feedback_geometry.py — 五边形几何验证（Wuxing-Pentagon）

命题（来自用户几何直觉）：
  正五边形（ρ 均匀）= D5 对称 = 恢复力各向同性 = 阻尼最大（无薄弱方向）；
  形变五边形（ρ 不均）= 对称性破缺 = 出现薄弱方向 = 沿薄弱方向易突破逆转阈值。

验证法：对同一扰动范数、不同方向（单维 + 随机），比较 1 步恢复率
  r = |s(1)|/|s(0)|   （越小 = 该方向阻尼越强）
  - ρ 均匀：各方向 r 应几乎相等（各向同性，spread≈0）
  - ρ 不均：各方向 r 拉开差距（薄弱方向 r 明显偏大）

另输出五边形重心（体质点）的失衡度 d 与主导方向角 φ。
"""
from __future__ import annotations
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "utils"))
from wuxing_feedback import DIMS, step, build_coupling_matrix  # noqa: E402

# 五行顶点（相生序 木火土金水，顺时针）
ANGLES = [2 * math.pi * k / 5 for k in range(5)]
PTS = {DIMS[k]: (math.cos(ANGLES[k]), math.sin(ANGLES[k])) for k in range(5)}
ZERO = {k: 0.0 for k in DIMS}


def centroid(rho):
    """体质点重心（ρ 加权）"""
    sx = sum(rho[k] * PTS[k][0] for k in DIMS)
    sy = sum(rho[k] * PTS[k][1] for k in DIMS)
    st = sum(rho.values())
    return sx / st, sy / st


def imbalance(rho):
    """失衡度 d = |重心−中心|（正五边形=0，完全偏到某顶点≈0.8）"""
    cx, cy = centroid(rho)
    return math.hypot(cx, cy)


def recovery_rate(s0, rho0, A, steps=1):
    """s0 扰动出发 steps 步后的范数衰减率"""
    s = dict(s0)
    for _ in range(steps):
        s, _ = step(s, rho0, ZERO, A)
    n0 = math.sqrt(sum(x * x for x in s0.values()))
    n1 = math.sqrt(sum(x * x for x in s.values()))
    return n1 / n0


def build_directions():
    dirs = []
    for k in DIMS:  # 五个单维方向
        v = {x: 0.0 for x in DIMS}
        v[k] = 1.0
        dirs.append(("单维·" + k, v))
    random.seed(7)
    for i in range(12):  # 十二个随机方向
        raw = {k: random.uniform(-1.0, 1.0) for k in DIMS}
        n = math.sqrt(sum(x * x for x in raw.values()))
        dirs.append((f"随机{i}", {k: raw[k] / n for k in DIMS}))
    return dirs


def sweep(rho0, name):
    dirs = build_directions()
    A = build_coupling_matrix()
    rates = []
    for label, d in dirs:
        s0 = {k: 0.5 * d[k] for k in DIMS}
        rates.append((round(recovery_rate(s0, rho0, A), 4), label))
    rates.sort()
    best, worst = rates[0], rates[-1]
    spread = worst[0] - best[0]
    print(f"[{name}] 失衡度 d={imbalance(rho0):.4f}")
    print(f"  最强阻尼方向 : {best[1]}  r={best[0]}")
    print(f"  最弱(薄弱)方向: {worst[1]}  r={worst[0]}")
    print(f"  各向异性 spread = {spread:.4f}  (0=完美各向同性)")
    return rates, dict(dirs)


def main():
    rho_uni = {k: 1.0 for k in DIMS}                       # 正五边形（先天均衡）
    rho_weak = {"wood": 1.0, "fire": 0.5, "earth": 0.5, "metal": 0.8, "water": 0.8}  # 形变（火土虚）

    uni, _ = sweep(rho_uni, "正五边形  ρ 均匀")
    weak, dmap = sweep(rho_weak, "形变五边形  ρ 不均(火土虚)")

    # 薄弱方向与五行顶点的重合度（余弦）: 五维扰动向量 → 重心位移方向
    print("\n形变五边形 最弱方向投影到各五行顶点（余弦，|cos| 越大越指向该维）:")
    worst_label = weak[-1][1]
    v = dmap[worst_label]
    sx = sum(v[DIMS[i]] * PTS[DIMS[i]][0] for i in range(5))
    sy = sum(v[DIMS[i]] * PTS[DIMS[i]][1] for i in range(5))
    n = math.hypot(sx, sy) or 1e-9
    for k in DIMS:
        cos = (sx * PTS[k][0] + sy * PTS[k][1]) / (n * math.hypot(*PTS[k]))
        flag = " ← 虚维" if rho_weak[k] < 0.9 else ""
        print(f"  {k}: cos={cos:+.3f}{flag}")

    print("\n结论: 正五边形最弱方向 r=%.4f < 形变最弱方向 r=%.4f → 任何方向的最小阻尼，正五边形都更大" % (
        uni[-1][0], weak[-1][0]))


if __name__ == "__main__":
    main()
