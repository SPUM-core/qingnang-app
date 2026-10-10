# -*- coding: utf-8 -*-
"""wuxing_feedback_experiment.py — Wuxing-FB 数值实验

运行（项目根 E:\\工作\\qingnang-APP）：
    python backend/scripts/wuxing_feedback_experiment.py

输出：
    backend/scripts/output/wuxing_fb_exp.json  （完整序列，供图表/回归用）
"""
from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "utils"))
import wuxing_feedback as wf  # noqa: E402  （模块引用以支持运行时覆盖 β）
from wuxing_feedback import (  # noqa: E402
    DIMS, step, reversal_threshold, zone_status, THETA0, GAMMA, DT,
)

ap = argparse.ArgumentParser(description="Wuxing-FB 数值实验")
ap.add_argument("--beta-s", type=float, default=None, help="覆盖相生阻尼系数")
ap.add_argument("--beta-k", type=float, default=None, help="覆盖相克阻尼系数")
ap.add_argument("--out", default="wuxing_fb_exp.json", help="输出文件名")
_args = ap.parse_args()
if _args.beta_s:
    wf.BETA_SHENG = _args.beta_s
if _args.beta_k:
    wf.BETA_KE = _args.beta_k

OUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUT_DIR, exist_ok=True)
N = 60  # 演化步数

ZERO = {k: 0.0 for k in DIMS}


def series_of(run):
    return {k: [round(run[t][k], 4) for t in range(len(run))] for k in DIMS}


# ── 实验1：自愈性（健康构型 + 单次脉冲，观察阻尼收敛）──
def exp1():
    s0 = {"wood": 0.3, "fire": -0.2, "earth": 0.15, "metal": -0.1, "water": 0.05}
    pulse = {"wood": 2.0}  # t=0 单次脉冲（外邪一过性）
    rho_health = {k: 1.0 for k in DIMS}          # 健康基底（旧 API 无 ρ 网络，取均匀基底）
    A = wf.build_coupling_matrix()               # 定稿 β 耦合矩阵
    run, s = [], dict(s0)
    for t in range(N):
        run.append(dict(s))
        s, _ = step(s, rho_health, pulse if t == 0 else ZERO, A)
    wood = [r["wood"] for r in run]
    peak = max(wood)
    settle = next((t for t, x in enumerate(wood) if abs(x) < 0.2), N)  # 回落到 0.2
    final_max = max(abs(r[k]) for r in run[-5:] for k in DIMS)
    return {
        "s0": s0, "pulse": 2.0,
        "series": series_of(run),
        "metrics": {"peak_wood": round(peak, 4), "settle_step": settle, "final_max": round(final_max, 4)},
    }


# ── 实验2：虚弱化对照（同一持续注入，健康 vs 先天虚弱）──
def exp2():
    healthy_rho0 = {k: 1.0 for k in DIMS}                                    # 先天均衡
    weak_rho0 = {"wood": 1.0, "fire": 0.5, "earth": 0.5, "metal": 0.8, "water": 0.8}  # 先天火土虚
    s0 = {k: 0.0 for k in DIMS}                                              # 后天从中和起步
    u = {"wood": 1.0, "fire": 0.0, "earth": 0.0, "metal": 0.0, "water": 0.0}  # 持续注入（木旺之年）

    def run_case(rho0, A):
        run, s = [], dict(s0)
        theta_trace, zone_trace = [], []
        for t in range(N):
            run.append(dict(s))
            th = reversal_threshold(s, rho0)
            theta_trace.append(th)
            zs = zone_status(s, th, rho0)
            zone_trace.append({k: ("OUT" if zs["out"][k] else ("CRIT" if zs["crit"][k] else "IN")) for k in DIMS})
            s, _ = step(s, rho0, u, A)
        return run, theta_trace, zone_trace

    def summarize(run, theta_trace, zone_trace, rho0):
        wood = [r["wood"] for r in run]
        wood_th = [theta_trace[t]["wood"] for t in range(N)]
        broke = next((t for t in range(N) if abs(wood[t]) >= wood_th[t]), None)
        final, theta_f = run[-1], theta_trace[-1]
        zf = zone_status(final, theta_f, rho0)
        return {
            "s_wood": [round(x, 4) for x in wood],
            "theta_wood": [round(x, 4) for x in wood_th],
            "zone_wood": zone_trace,
            "broke_step": broke,
            "final": {k: round(final[k], 4) for k in DIMS},
            "final_theta": {k: round(theta_f[k], 4) for k in DIMS},
            "final_zone": {k: ("OUT" if zf["out"][k] else ("CRIT" if zf["crit"][k] else "IN")) for k in DIMS},
            "xu": {k: bool(zf["xu"][k]) for k in DIMS},
            "shi": {k: bool(zf["shi"][k]) for k in DIMS},
        }

    return {
        "u_wood": 1.0,
        "healthy": summarize(*run_case(healthy_rho0, wf.build_coupling_matrix()), healthy_rho0),
        "weak": summarize(*run_case(weak_rho0, wf.build_coupling_matrix()), weak_rho0),
        "weak_rho0": weak_rho0,
    }


def main():
    result = {
        "params": {"beta_sheng": wf.BETA_SHENG, "beta_ke": wf.BETA_KE, "theta0": THETA0,
                   "gamma": GAMMA, "dt": DT, "steps": N},
        "exp1_self_healing": exp1(),
        "exp2_weakness_comparison": exp2(),
    }
    path = os.path.join(OUT_DIR, _args.out)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    e1 = result["exp1_self_healing"]["metrics"]
    h = result["exp2_weakness_comparison"]["healthy"]
    w = result["exp2_weakness_comparison"]["weak"]
    print("=== EXP1 self-healing ===")
    print("peak_wood=%s settle_step=%s final_max=%s" % (e1["peak_wood"], e1["settle_step"], e1["final_max"]))
    print("=== EXP2 healthy vs weak (u_wood=1.0 const) ===")
    print("healthy: broke_step=%s final_wood=%s zone=%s" % (h["broke_step"], h["final"]["wood"], h["final_zone"]["wood"]))
    print("weak   : broke_step=%s final_wood=%s zone=%s" % (w["broke_step"], w["final"]["wood"], w["final_zone"]["wood"]))
    print("weak final_theta_wood=%s" % w["final_theta"]["wood"])
    print("weak xu(虚)=%s shi(实)=%s" % (w["xu"], w["shi"]))
    print("weak final all dims: %s" % w["final"])
    print("json ->", path)


if __name__ == "__main__":
    main()
