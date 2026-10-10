# -*- coding: utf-8 -*-
"""wuxing_feedback_beta_scan.py — β 参数谱扫描：寻找"最正五边形的生克规律"

目标（用户几何直觉的标定化）：
  均匀 ρ（正五边形）下，恢复力谱的谱半径最小 → minimax 成立（最弱方向阻尼最大）；
  同时给出各向异性参考（谱半径差）。解析谱：五行循环矩阵的特征值逐网格计算。

离散线性化（ρ=1 均匀，dt 固定）：
  s_new = ((I − dt·A_off)·s) / (1 + dt·κ₀)
  A_off 行（j=1..4 相对 i=0）：子泄 −βs · 我克耗 −βk · 克我乘 −βk · 母养 +βs
  特征值 λ_m = Σ_k A_off_k·ω^{mk}，ω = e^{2πi/5}；μ_m = (1−dt·λ_m)/(1+dt·κ₀)
"""
from __future__ import annotations
import cmath
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "utils"))

DT = 0.25


def spectrum(beta_s: float, beta_k: float, dt: float = DT):
    """均匀 ρ 下的离散恢复特征值模长（降序）：[0]=谱半径（最弱方向）"""
    w = cmath.exp(2j * math.pi / 5)
    kappa0 = 2.0 * (beta_s + beta_k)
    aoff = [None, -beta_s, -beta_k, -beta_k, +beta_s]  # j=1..4
    mus = []
    for m in range(5):
        lam = sum(aoff[k] * w ** (m * k) for k in range(1, 5))
        mu = (1.0 - dt * lam) / (1.0 + dt * kappa0)
        mus.append(mu)
    mods = sorted((abs(mu) for mu in mus), reverse=True)
    return mods


def main():
    bs_vals = [0.30, 0.45, 0.60, 0.80]
    bk_vals = [round(0.05 + 0.05 * i, 2) for i in range(20)]  # 0.05 .. 1.00

    grid = {}
    best = None
    for bs in bs_vals:
        row = []
        for bk in bk_vals:
            mods = spectrum(bs, bk)
            radius, aniso, stable = mods[0], mods[0] - mods[-1], mods[0] < 1.0
            row.append({"bk": bk, "radius": round(radius, 4),
                        "aniso": round(aniso, 4), "stable": stable})
            if stable and (best is None or radius < best["radius"]):
                best = {"beta_s": bs, "beta_k": bk,
                        "radius": round(radius, 4), "aniso": round(aniso, 4)}
        grid[bs] = row

    cur = spectrum(0.45, 0.35)
    result = {
        "grid": grid, "bs_vals": bs_vals, "bk_vals": bk_vals,
        "best": best,
        "current": {"beta_s": 0.45, "beta_k": 0.35,
                    "radius": round(cur[0], 4), "aniso": round(cur[0] - cur[-1], 4)},
    }
    path = os.path.join(os.path.dirname(__file__), "output", "wuxing_fb_beta_scan.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print("best (谱半径最小):", best)
    print("current 0.45/0.35:", result["current"])
    print("json ->", path)


if __name__ == "__main__":
    main()
