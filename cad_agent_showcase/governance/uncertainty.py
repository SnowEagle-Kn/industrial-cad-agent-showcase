# -*- coding: utf-8 -*-
"""Independent per-candidate score uncertainty, with constructive counterexamples.
No probabilities, no new engineering scores, no mutation of prior judgments.
"""
import argparse
import itertools
from .scoring import WEIGHTS, CRITERIA, FACTORS, _check_score
from .envelope import InputError, run_cli


def runner(payload):
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(candidates, dict) or not 2 <= len(candidates) <= 20:
        raise InputError("CANDIDATES_INVALID", "需要2–20案的七维确定分")
    delta = payload.get("delta", 1)
    if not isinstance(delta, int) or isinstance(delta, bool) or not 0 <= delta <= 5:
        raise InputError("DELTA_INVALID", "delta必须0–5整数")
    for cid, points in candidates.items():
        if not isinstance(cid, str) or not isinstance(points, dict) or set(points) != set(CRITERIA):
            raise InputError("POINTS_INVALID", "每案须精确覆盖七维")
        for key, val in points.items():
            _check_score(val, cid + "/" + key)
    def total(points, weights):
        return sum(weights[k] * points[k] / 5 for k in CRITERIA)
    base = {cid: total(pts, WEIGHTS) for cid, pts in candidates.items()}
    leader = sorted(base, key=lambda x: (-base[x], x))[0]
    factors = list(itertools.product(FACTORS, repeat=7)) if payload.get("vary_weights", True) else [(1.0,) * 7]
    witnesses = []
    for rival in sorted(candidates):
        if rival == leader:
            continue
        low = {k: max(0, candidates[leader][k] - delta) for k in CRITERIA}
        high = {k: min(5, candidates[rival][k] + delta) for k in CRITERIA}
        best = None
        for fs in factors:
            raw = {k: WEIGHTS[k] * f for k, f in zip(CRITERIA, fs)}
            weights = {k: v * 100 / sum(raw.values()) for k, v in raw.items()}
            a, b = total(low, weights), total(high, weights)
            record = dict(rival=rival, leader_score=a, rival_score=b, margin=a-b,
                          leader_points=low, rival_points=high, weights=weights)
            if best is None or record["margin"] < best["margin"]:
                best = record
        witnesses.append(best)
    robust = all(row["margin"] > 1e-10 for row in witnesses)
    return dict(status="INDEPENDENT_UNCERTAINTY_CHECKED", base_totals=base, base_leader=leader,
        delta=delta, common_weight_vertices=len(factors),
        independent_per_candidate_per_criterion=True,
        robust_to_independent_score_uncertainty=robust, pairwise_worst_cases=witnesses,
        method="正权重下各维独立区间的线性极值；共用权重按归一前0.8/1.2顶点复算",
        probability_claim=False, engineering_validation=False,
        recommendation_changed=False,
        boundary="独立包络是所声明不确定集的反例检查，不代表互斥工程场景可同时发生；不自动改写历史评分或用户选择。")


def cli(argv=None):
    parser = argparse.ArgumentParser(prog="python -m cad_agent_showcase.governance.uncertainty")
    parser.add_argument("path")
    return run_cli("uncertainty", runner, parser.parse_args(argv))
