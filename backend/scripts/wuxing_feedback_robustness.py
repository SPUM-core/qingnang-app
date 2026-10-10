# -*- coding: utf-8 -*-
"""wuxing_feedback_robustness.py — 多构型判别复验（B 路线：把 β 定死再接入主链路）

目标：确认推荐 β（0.50/0.30）对"任意虚证构型 × 任意注入方向"都稳健：
  - 健康组（ρ₀ 全 1）：任何方向持续注入都不破（零误报）
  - 每类先天虚弱构型：至少一个注入方向能突破（病机可显现、可判别）
任何一维 zone=OUT 即计为突破（传变传导到其它维也算）。

评估：误报数（健康组破的方向数，理想 0）
      检出率（虚弱构型中至少 1 方向可破的比例，理想 100%）
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "utils"))
import wuxing_feedback as wf
from wuxing_feedback import DIMS, step, reversal_threshold, zone_status

N = 60
STRENGTHS = [0.5, 1.0, 1.5, 2.0]   # 注入强度扫描（连续邪气强度）

# 先天虚证构型 ρ₀（火土虚 / 金水虚 / 木火虚 / 水土虚 / 单维木虚 / 单维土虚 /
#                木火旺+金水虚 / 全虚偏木 / 水旺火虚）
CONFIGS = [
    ("火土虚",     {"wood": 1.0, "fire": 0.5, "earth": 0.5, "metal": 0.8, "water": 0.8}),
    ("金水虚",     {"wood": 0.8, "fire": 1.0, "earth": 0.8, "metal": 0.5, "water": 0.5}),
    ("木火虚",     {"wood": 0.5, "fire": 0.5, "earth": 1.0, "metal": 0.8, "water": 0.8}),
    ("水土虚",     {"wood": 0.8, "fire": 0.8, "earth": 0.5, "metal": 0.8, "water": 0.5}),
    ("单维木虚",   {"wood": 0.5, "fire": 1.0, "earth": 1.0, "metal": 1.0, "water": 1.0}),
    ("单维土虚",   {"wood": 1.0, "fire": 1.0, "earth": 0.5, "metal": 1.0, "water": 1.0}),
    ("木火旺金水虚", {"wood": 1.4, "fire": 1.3, "earth": 0.9, "metal": 0.5, "water": 0.5}),
    ("全虚偏木",   {"wood": 0.7, "fire": 0.6, "earth": 0.6, "metal": 0.5, "water": 0.5}),
    ("水旺火虚",   {"wood": 1.0, "fire": 0.5, "earth": 1.0, "metal": 1.0, "water": 1.3}),
]
INJECT_DIRS = ["wood", "fire", "earth", "metal", "water"]
BETA_CANDIDATES = [
    (0.45, 0.35, "当前"),
    (0.45, 0.40, "克稍强"),
    (0.50, 0.30, "推荐折中"),
    (0.50, 0.35, "折中·克稍强"),
    (0.50, 0.40, "克强"),
    (0.55, 0.35, "生稍强·克中"),
    (0.55, 0.40, "生稍强·克强"),
    (0.60, 0.40, "生强·克强"),
]


def run_case(rho0, beta_s, beta_k, inj, strength=1.0):
    """返回首次出现任一维 OUT 的步数（None=全程未破）"""
    wf.BETA_SHENG, wf.BETA_KE = beta_s, beta_k
    A = wf.build_coupling_matrix()   # 按当前 β 构造耦合矩阵
    s = {k: 0.0 for k in DIMS}
    u = {k: 0.0 for k in DIMS}
    u[inj] = strength
    for t in range(N):
        th = reversal_threshold(s, rho0)
        zs = zone_status(s, th, rho0)
        if any(zs["out"].values()):
            return t
        s, _ = step(s, rho0, u, A)
    return None


def min_break_strength(rho0, beta_s, beta_k, inj):
    """该构型在该注入方向上的最小突破强度 u*（None=2.0 仍不破）"""
    for u in STRENGTHS:
        if run_case(rho0, beta_s, beta_k, inj, u) is not None:
            return u
    return None


def main():
    healthy = {k: 1.0 for k in DIMS}
    print("β_s   β_k  名称        健康耐受uh*  可判别  平均裕度  缺失构型")
    print("-" * 92)
    best_row = None
    for bs, bk, name in BETA_CANDIDATES:
        # 健康组每方向突破强度 u*_h（None=2.0 仍不破，记为 2.5 参与裕度）
        uh = {d: min_break_strength(healthy, bs, bk, d) for d in INJECT_DIRS}
        uh_eff = {d: (uh[d] if uh[d] is not None else 2.5) for d in INJECT_DIRS}
        uh_min = min(uh_eff.values())          # 健康最弱方向的耐受（越高越好）
        # 各构型：找最大判别裕度 margin = u*_h − u*_w（≥0.5 视为可判别）
        margins, missing = [], []
        for cname, rho0 in CONFIGS:
            best_m = None
            for d in INJECT_DIRS:
                uw = min_break_strength(rho0, bs, bk, d)
                if uw is None:
                    continue
                m = uh_eff[d] - uw
                if best_m is None or m > best_m:
                    best_m = m
            if best_m is not None and best_m >= 0.5:
                margins.append(best_m)
            else:
                missing.append(cname)
        detected = len(margins)
        avg_m = sum(margins) / len(margins) if margins else 0.0
        ok = (detected == len(CONFIGS))
        row = (bs, bk, name, uh_min, detected, avg_m, missing)
        print(f"{bs:.2f} {bk:.2f}  {name:<7}    {uh_min:.1f}        {detected}/9    {avg_m:.2f}      {','.join(missing) if missing else '无'}")
        if ok and (best_row is None or (avg_m, uh_min) > (best_row[5], best_row[3])):
            best_row = row

    print("-" * 92)
    if best_row:
        print("推荐（全可判别 & 平均裕度最大 & 健康耐受优先）: β_s=%.2f β_k=%.2f (%s)" % (best_row[0], best_row[1], best_row[2]))
        print("健康最弱方向耐受 u*=%.1f，9 构型全可判别，平均裕度 %.2f" % (best_row[3], best_row[5]))
    else:
        print("仍有构型不可判别；需扩大注入上限或调整阈值/候选")


if __name__ == "__main__":
    main()
