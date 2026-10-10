# -*- coding: utf-8 -*-
"""wuxing_feedback_beta_validate.py — 双目标折中：谱半径 vs 病态判别力

目标 A（几何）：均匀 ρ 谱半径最小（正五边形阻尼大）
目标 B（临床）：同一注入下 健康组不破(IN) 且 先天虚弱组突破(OUT) —— 判别力
扫描 β 组合，输出两张表，找同时满足 A/B 的折中点。
"""
from __future__ import annotations
import cmath
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "utils"))
import wuxing_feedback as wf
from wuxing_feedback import DIMS, step, reversal_threshold

N = 60
DT = 0.25


def spectrum_radius(beta_s: float, beta_k: float) -> float:
    """均匀 ρ 下谱半径（最弱方向恢复率），复用 β 扫描公式"""
    w = cmath.exp(2j * math.pi / 5)
    kappa0 = 2.0 * (beta_s + beta_k)
    aoff = [None, -beta_s, -beta_k, -beta_k, +beta_s]
    mods = []
    for m in range(5):
        lam = sum(aoff[k] * w ** (m * k) for k in range(1, 5))
        mods.append(abs((1.0 - DT * lam) / (1.0 + DT * kappa0)))
    return max(mods)


def run_case(rho0, beta_s, beta_k):
    wf.BETA_SHENG, wf.BETA_KE = beta_s, beta_k
    A = wf.build_coupling_matrix()   # 按当前 β 构造耦合矩阵
    s = {k: 0.0 for k in DIMS}
    u = {"wood": 1.0, "fire": 0.0, "earth": 0.0, "metal": 0.0, "water": 0.0}
    trace = []
    for t in range(N):
        th = reversal_threshold(s, rho0)
        trace.append((dict(s), th["wood"]))
        s, _ = step(s, rho0, u, A)
    wood = [x[0]["wood"] for x in trace]
    thw = [x[1] for x in trace]
    broke = next((t for t in range(N) if abs(wood[t]) >= thw[t]), None)
    return broke, wood[-1], thw[-1]


def main():
    healthy_rho0 = {k: 1.0 for k in DIMS}
    weak_rho0 = {"wood": 1.0, "fire": 0.5, "earth": 0.5, "metal": 0.8, "water": 0.8}

    combos = [
        (0.45, 0.35), (0.50, 0.30), (0.60, 0.25), (0.60, 0.20),
        (0.70, 0.20), (0.70, 0.15), (0.80, 0.15), (0.80, 0.20),
        (0.90, 0.20), (0.90, 0.25), (1.00, 0.25), (1.00, 0.30),
    ]
    print("bs    bk    radius  h_broke w_broke  h_final w_final  h_th  w_th  判别")
    rows = []
    for bs, bk in combos:
        radius = spectrum_radius(bs, bk)
        hb, hf, ht = run_case(healthy_rho0, bs, bk)
        wb, wf_, wt = run_case(weak_rho0, bs, bk)
        ok = (hb is None) and (wb is not None)
        rows.append((bs, bk, radius, hb, wb, hf, wf_, ht, wt, ok))
        print(f"{bs:.2f} {bk:.2f}  {radius:.4f}  {str(hb):>7} {str(wb):>7}  "
              f"{hf:.3f} {wf_:.3f}  {ht:.3f} {wt:.3f}  {'✓' if ok else '✗'}")

    ok_rows = [r for r in rows if r[-1]]
    if ok_rows:
        best = min(ok_rows, key=lambda r: r[2])
        print("\n推荐折中（判别成立 & 谱半径最小）: β_s=%.2f β_k=%.2f radius=%.4f" % (best[0], best[1], best[2]))


if __name__ == "__main__":
    main()
