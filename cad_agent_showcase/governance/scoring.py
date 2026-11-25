# -*- coding: utf-8 -*-
"""七维评分、硬门、区间、扰动与成对一致性。

只做算术与规则校验：不评判设计好坏，不证明扰动结果是获胜概率。
128 个组合是 2^7 个顶点，不是抽样。

F03 整改：分数只收有限整数 0–5；point 与 interval 互斥；倒置区间、
越界值、NaN 一律拒收。任一非退化区间或未知维度都会让 point 为 null。
区间优先按同一场景内七项合计再取极值；做不到时明确标“独立包络，
相关性未建模”，不把互斥情景拼成同时最坏。

F04 整改：资格集合与总分键必须严格一致；无序对数量、去重、成员、
非自配对逐项校验。不充分、同分、近分、区间重叠进入对应推荐类别，
只有稳健领先才给 champion。
"""

import argparse
import itertools
import math

from .envelope import (InputError, RuleRejection, emit_ok, emit_rejected,
                       require_mapping)

WEIGHTS = {"C1": 20, "C2": 25, "C3": 15, "C4": 12, "C5": 10, "C6": 8, "C7": 10}
CRITERIA = tuple(WEIGHTS)
GATES = ("G1", "G2", "G3", "G4")
GATE_RESULTS = ("PASS_CONCEPT", "CONDITIONAL", "FAIL", "INCOMPLETE")
PASSING_GATES = ("PASS_CONCEPT", "CONDITIONAL")
FACTORS = (0.8, 1.2)
NEAR_MARGIN = max(WEIGHTS.values()) / 5
MAX_SCORE = 5
MAX_TOTAL = float(sum(WEIGHTS.values()))

ROBUST = "ROBUST_RECOMMENDATION"
CONDITIONAL = "CONDITIONAL_PREFERENCE"
CO_RECOMMENDATION = "CO_RECOMMENDATION"
NO_RECOMMENDATION = "NO_RECOMMENDATION"
NOT_EVALUATED = "NOT_EVALUATED"

INDEPENDENT_ENVELOPE = "independent_envelope"
SAME_SCENARIO = "same_scenario_then_extremes"
UNRESOLVED_MARK = "UNRESOLVED"
SCORED_MARK = "SCORED"


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _check_score(value, path):
    if isinstance(value, float):
        raise InputError("NON_INTEGER_SCORE", "分值必须是整数，收到 %r" % value, path)
    if not _is_int(value):
        raise InputError("NON_INTEGER_SCORE", "分值必须是整数，收到 %r" % (value,), path)
    if value < 0 or value > MAX_SCORE:
        raise InputError("SCORE_OUT_OF_RANGE",
                         "分值必须在 0..%d，收到 %d" % (MAX_SCORE, value), path)
    return value


def _parse_cell(criterion, cell, path):
    """把一格解析成 (low, high, unresolved, scenario_id)。"""
    if cell is None:
        return 0, MAX_SCORE, True, None
    if not isinstance(cell, dict):
        raise InputError("CELL_NOT_OBJECT", "%s 必须是对象" % criterion, path)
    status = cell.get("status", SCORED_MARK)
    if status not in (SCORED_MARK, UNRESOLVED_MARK):
        raise InputError("CELL_STATUS_UNKNOWN",
                         "status 只能是 %s 或 %s，收到 %r"
                         % (SCORED_MARK, UNRESOLVED_MARK, status), path)
    scenario_id = cell.get("scenario_id")
    has_point = "point" in cell and cell["point"] is not None
    has_interval = "interval" in cell and cell["interval"] is not None
    if status == UNRESOLVED_MARK:
        if has_point or has_interval:
            raise InputError("UNRESOLVED_WITH_SCORE",
                             "UNRESOLVED 格不得同时给 point 或 interval；"
                             "未知就保持未知，不能既声明未知又保留一个分",
                             path)
        return 0, MAX_SCORE, True, scenario_id
    if has_point and has_interval:
        raise InputError("POINT_INTERVAL_EXCLUSIVE",
                         "point 与 interval 互斥，不能同时给", path)
    if has_interval:
        interval = cell["interval"]
        if not isinstance(interval, (list, tuple)) or len(interval) != 2:
            raise InputError("INTERVAL_SHAPE", "interval 必须是两个整数的数组", path)
        low = _check_score(interval[0], path)
        high = _check_score(interval[1], path)
        if low > high:
            raise InputError("INTERVAL_INVERTED",
                             "区间顺序倒置：low=%d > high=%d" % (low, high), path)
        return low, high, low != high, scenario_id
    if has_point:
        point = _check_score(cell["point"], path)
        return point, point, False, scenario_id
    raise InputError("NO_SCORE",
                     "%s 既无 point 也无 interval；未知请显式写 status=UNRESOLVED"
                     % criterion, path)


def _validate_gates(gates, path):
    if not isinstance(gates, dict):
        raise InputError("GATES_NOT_OBJECT", "gates 必须是对象", path)
    missing = [gate for gate in GATES if gate not in gates]
    if missing:
        raise InputError("GATES_MISSING", "缺少门槛: %s" % ",".join(missing), path)
    for gate in GATES:
        if gates[gate] not in GATE_RESULTS:
            raise InputError("GATE_RESULT_UNKNOWN",
                             "%s 的门槛结果 %r 不在 %s 内"
                             % (gate, gates[gate], ",".join(GATE_RESULTS)), path)


def score_candidate(gates, cells, drop_criteria=(), path=None):
    """gates: {G1..G4: PASS_CONCEPT|CONDITIONAL|FAIL|INCOMPLETE}。

    cells: {C1..C7: {point|interval|status|scenario_id}}。drop_criteria 非空时拒绝：
    未知维度保留分母，不重归一。
    """
    if drop_criteria:
        raise InputError("DROP_CRITERIA_FORBIDDEN", "未知维度不得删除，不重归一", path)
    _validate_gates(gates, path)
    if not isinstance(cells, dict):
        raise InputError("CELLS_NOT_OBJECT", "cells 必须是对象", path)
    unknown = [key for key in cells if key not in WEIGHTS]
    if unknown:
        raise InputError("CELL_CRITERION_UNKNOWN",
                         "未知评分维度: %s" % ",".join(sorted(unknown)), path)

    failed = [gate for gate in GATES if gates[gate] == "FAIL"]
    incomplete = [gate for gate in GATES if gates[gate] == "INCOMPLETE"]
    if failed or incomplete:
        return {
            "eligible": False,
            "gate_result": "FAIL" if failed else "INCOMPLETE",
            "failed_gates": failed,
            "incomplete_gates": incomplete,
            "weighted_compensation": False,
            "total": None,
            "unresolved_criteria": [],
            "renormalized": False,
            "denominator_kept": True,
            "note": "硬门 FAIL/INCOMPLETE 不可用加权分补偿",
        }

    parsed = {}
    for criterion in CRITERIA:
        parsed[criterion] = _parse_cell(criterion, cells.get(criterion),
                                        "%s/%s" % (path, criterion) if path else criterion)

    unresolved = [c for c in CRITERIA if parsed[c][2]]
    scenario_ids = {parsed[c][3] for c in CRITERIA}

    # 同一场景聚合：每格都给了 scenario_id，且按场景分组后七项齐全。
    grouped = None
    if all(parsed[c][3] is not None for c in CRITERIA):
        ids = sorted(scenario_ids)
        block = {}
        complete = True
        for scenario in ids:
            items = [c for c in CRITERIA if parsed[c][3] == scenario]
            if len(items) != len(CRITERIA):
                complete = False
                break
            block[scenario] = items
        if complete and len(ids) >= 1:
            grouped = block

    if grouped is not None:
        scenario_totals = {}
        scenario_unresolved = {}
        for scenario, items in grouped.items():
            low = sum(WEIGHTS[c] * parsed[c][0] / 5.0 for c in items)
            high = sum(WEIGHTS[c] * parsed[c][1] / 5.0 for c in items)
            scenario_totals[scenario] = {"low": low, "high": high}
            scenario_unresolved[scenario] = [c for c in items if parsed[c][2]]
        low = min(v["low"] for v in scenario_totals.values())
        high = max(v["high"] for v in scenario_totals.values())
        single = len(scenario_totals) == 1
        all_definite = single and not unresolved
        point = low if all_definite else None
        interval_method = SAME_SCENARIO
        correlation_modeled = True
        note = ("同场景内七项合计后取极值；场景之间不假定同时发生"
                if not single else "单一共同场景，区间由该场景内区间取值决定")
        scenarios_out = scenario_totals
    else:
        low = sum(WEIGHTS[c] * parsed[c][0] / 5.0 for c in CRITERIA)
        high = sum(WEIGHTS[c] * parsed[c][1] / 5.0 for c in CRITERIA)
        point = None if unresolved else low
        if not unresolved and low == high:
            point = low
        interval_method = INDEPENDENT_ENVELOPE
        correlation_modeled = False
        note = "保守包络，相关性未建模：各维区间独立取极值"
        scenarios_out = {}

    return {
        "eligible": all(gates[gate] in PASSING_GATES for gate in GATES),
        "gate_result": "CONDITIONAL" if any(
            gates[gate] == "CONDITIONAL" for gate in GATES) else "PASS_CONCEPT",
        "failed_gates": [],
        "incomplete_gates": [],
        "weighted_compensation": False,
        "total": {
            "low": low,
            "high": high,
            "point": point,
            "max_possible": MAX_TOTAL,
            "interval_method": interval_method,
            "correlation_modeled": correlation_modeled,
            "note": note,
        },
        "scenario_totals": scenarios_out,
        "unresolved_criteria": unresolved,
        "renormalized": False,
        "denominator_kept": True,
    }


def perturb(candidates):
    """归一前各权重乘 0.8/1.2 的 128 组合。

    candidates: {id: {C1..C7: point}}，只对七项都有确定分的候选做。
    输出冠亚是否翻转、最大相对偏移；不是概率。
    """
    if not isinstance(candidates, dict):
        raise InputError("CANDIDATES_NOT_OBJECT", "candidates 必须是对象")
    ids = sorted(candidates)
    if len(ids) < 2:
        raise InputError("PERTURB_NEEDS_TWO", "扰动至少需要两个候选")
    for candidate_id in ids:
        points = candidates[candidate_id]
        if not isinstance(points, dict):
            raise InputError("POINTS_NOT_OBJECT", "%s 的分值必须是对象" % candidate_id)
        for criterion in CRITERIA:
            if criterion not in points:
                raise InputError("POINTS_MISSING",
                                 "%s 缺少 %s 的确定分" % (candidate_id, criterion))
            _check_score(points[criterion], "%s/%s" % (candidate_id, criterion))

    base_weights = [WEIGHTS[c] for c in CRITERIA]
    base_total = sum(base_weights)

    def totals(factors):
        raw = [weight * factor for weight, factor in zip(base_weights, factors)]
        scale = base_total / sum(raw)
        out = {}
        for candidate_id in ids:
            points = candidates[candidate_id]
            out[candidate_id] = sum(
                raw[i] * scale * points[CRITERIA[i]] / 5.0 for i in range(7))
        return out

    base = totals((1.0,) * 7)
    ranking = sorted(ids, key=lambda item: (-base[item], item))
    base_leader, base_runner = ranking[0], ranking[1]
    flips = 0
    max_shift = 0.0
    seen = {}
    for factors in itertools.product(FACTORS, repeat=7):
        raw = tuple(weight * factor for weight, factor in zip(base_weights, factors))
        normalized = tuple(round(item / sum(raw), 10) for item in raw)
        seen.setdefault(normalized, 0)
        seen[normalized] += 1
        current = totals(factors)
        order = sorted(ids, key=lambda item: (-current[item], item))
        if order[0] != base_leader or order[1] != base_runner:
            flips += 1
        for index, weight in enumerate(base_weights):
            shifted = raw[index] / sum(raw) * base_total
            max_shift = max(max_shift, abs(shifted - weight) / weight)
    return {
        "raw_combinations": 128,
        "unique_normalized_weight_sets": len(seen),
        "base_leader": base_leader,
        "base_runner_up": base_runner,
        "leader_runner_flipped_combinations": flips,
        "flip": flips > 0,
        "max_relative_shift": max_shift,
        "probability_claim": False,
    }


def pairwise_expected(n):
    return n * (n - 1) // 2


def _pair_key(left, right):
    return (left, right) if left < right else (right, left)


def _parse_totals(eligible_ids, totals):
    """total 支持数值或 {low, high, point}；返回 (parsed, key_problems)。

    totals 键与资格集合不一致不是“输入格式错”，而是**排名结论不成立**：
    返回问题清单，由 check_ranking 转成 RANKING_CONFLICT，champion=None。
    不能抛异常让调用方拿不到任何结果，也不能容忍 K99 混进来当冠军。
    """
    if not isinstance(totals, dict):
        raise InputError("TOTALS_NOT_OBJECT", "totals 必须是对象")
    ids = set(eligible_ids)
    keys = set(totals)
    extra = sorted(keys - ids)
    missing = sorted(ids - keys)
    problems = []
    if extra or missing:
        problems.append({"kind": "totals_keys_mismatch",
                         "extra_ids": extra, "missing_ids": missing,
                         "detail": "资格集合与总分键必须严格一致；"
                                   "资格外候选不得进入排名"})
    parsed = {}
    for candidate_id in eligible_ids:
        if candidate_id not in totals:
            continue
        value = totals[candidate_id]
        if _is_int(value) or isinstance(value, float):
            number = float(value)
            if not math.isfinite(number):
                raise InputError("TOTAL_NOT_FINITE",
                                 "%s 的总分不是有限数" % candidate_id)
            # 数值分支同样要校验范围：200 分不是“合法高分”，而是坏数据。
            if number < 0 or number > MAX_TOTAL:
                problems.append({"kind": "total_out_of_range",
                                 "candidate_id": candidate_id,
                                 "value": number,
                                 "detail": "总分必须在 0..%s，收到 %s"
                                           % (MAX_TOTAL, number)})
            parsed[candidate_id] = {"low": number, "high": number, "point": number}
            continue
        if not isinstance(value, dict):
            raise InputError("TOTAL_SHAPE", "%s 的总分必须是数值或区间对象" % candidate_id)
        low = value.get("low")
        high = value.get("high")
        point = value.get("point")
        for name, item in (("low", low), ("high", high)):
            if not isinstance(item, (int, float)) or isinstance(item, bool) \
                    or not math.isfinite(float(item)):
                raise InputError("TOTAL_NOT_FINITE",
                                 "%s.%s 必须是有限数值" % (candidate_id, name))
        if float(low) > float(high):
            raise InputError("TOTAL_INTERVAL_INVERTED",
                             "%s 的总分区间倒置" % candidate_id)
        if float(low) < 0 or float(high) > MAX_TOTAL:
            raise InputError("TOTAL_OUT_OF_RANGE",
                             "%s 的总分超出 0..%s" % (candidate_id, MAX_TOTAL))
        if point is not None:
            if not isinstance(point, (int, float)) or isinstance(point, bool) \
                    or not math.isfinite(float(point)):
                raise InputError("TOTAL_NOT_FINITE",
                                 "%s.point 必须是有限数值" % candidate_id)
            if not (float(low) <= float(point) <= float(high)):
                raise InputError("TOTAL_POINT_OUTSIDE",
                                 "%s.point 不在区间内" % candidate_id)
            point = float(point)
        parsed[candidate_id] = {"low": float(low), "high": float(high),
                                "point": point}
    return parsed, problems


def _check_pairs(eligible_ids, pairs):
    """返回 (expected_keys, got_keys, conflicts, insufficient_keys)。"""
    if pairs is None:
        pairs = []
    if not isinstance(pairs, list):
        raise InputError("PAIRS_NOT_LIST", "pairs 必须是数组")
    ids = sorted(eligible_ids)
    expected = {(left, right) for index, left in enumerate(ids)
                for right in ids[index + 1:]}
    seen = {}
    conflicts = []
    insufficient = set()
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            raise InputError("PAIR_NOT_OBJECT", "第 %d 个成对记录不是对象" % index)
        left = pair.get("left")
        right = pair.get("right")
        if left not in eligible_ids or right not in eligible_ids:
            conflicts.append({"kind": "pair_member",
                              "pair": [left, right],
                              "detail": "成员不在资格集合内"})
            continue
        if left == right:
            conflicts.append({"kind": "pair_self", "pair": [left, right],
                              "detail": "自己不能与自己成对"})
            continue
        key = _pair_key(left, right)
        if key in seen:
            conflicts.append({"kind": "pair_duplicate", "pair": list(key),
                              "detail": "同一无序对重复出现"})
            continue
        seen[key] = pair
        verdict = pair.get("verdict")
        if verdict not in ("LEFT", "RIGHT", "TIE", "INSUFFICIENT"):
            conflicts.append({"kind": "verdict", "pair": list(key),
                              "detail": "verdict 必须是 LEFT/RIGHT/TIE/INSUFFICIENT",
                              "got": verdict})
            continue
        if verdict == "INSUFFICIENT":
            insufficient.add(key)
    missing = expected - set(seen)
    if missing:
        conflicts.append({"kind": "pair_missing",
                          "pairs": [list(item) for item in sorted(missing)],
                          "detail": "应检查的无序对缺 %d 个" % len(missing)})
    return expected, seen, conflicts, insufficient


def check_ranking(eligible_ids, totals, pairs, claimed_champion=None,
                  near_margin=NEAR_MARGIN, perturbation=None):
    """成对矩阵与加权总分的一致性，并给出推荐类别。

    pairs: [{left, right, verdict: LEFT|RIGHT|TIE|INSUFFICIENT}]。
    任一处矛盾返回 RANKING_CONFLICT 且不给 champion。只有稳健领先
    （无冲突、无 INSUFFICIENT、无同分/区间重叠、分差 > near_margin、
    扰动不翻转）才给 ROBUST_RECOMMENDATION 与 champion。
    """
    if not isinstance(eligible_ids, (list, tuple)):
        raise InputError("ELIGIBLE_NOT_LIST", "eligible_ids 必须是数组")
    ids = list(eligible_ids)
    for item in ids:
        if not isinstance(item, str) or not item:
            raise InputError("ELIGIBLE_ID_INVALID", "资格编号必须是非空字符串")
    if len(set(ids)) != len(ids):
        raise InputError("ELIGIBLE_DUPLICATE", "资格集合有重复编号")
    parsed_totals, totals_problems = _parse_totals(ids, totals)
    expected, seen, conflicts, insufficient = _check_pairs(ids, pairs)
    conflicts.extend(totals_problems)

    # 成对结论与总分算术的对照。
    #
    # 三段分流（F04↔F03 打通，独立审查 P1-01/P1-02）：
    #   a) 某案根本没有总分 → 记 arithmetic_skipped（缺数据），不崩、不算冲突；
    #   b) 双方都有确定 point → 比 point，矛盾即 arithmetic 冲突；
    #   c) 至少一方是区间（point=None）→ 比区间：只有**不相容**才算冲突
    #      （LEFT 要求 left.low > right.high，RIGHT 反之）；重叠不冲突，
    #      交给下面的推荐分类归 CO_RECOMMENDATION。
    # 之前 a 抛 KeyError、c 一律 arithmetic_unavailable，导致区间案件永远
    # NO_RECOMMENDATION，使合同 §7.5 的条件性/并列推荐不可达。
    arithmetic_skipped = []
    interval_comparisons = []
    interval_insufficient = set()
    for key, pair in seen.items():
        verdict = pair["verdict"]
        if verdict == "INSUFFICIENT":
            continue
        left_total = parsed_totals.get(pair["left"])
        right_total = parsed_totals.get(pair["right"])
        if left_total is None or right_total is None:
            arithmetic_skipped.append({"pair": list(key),
                                       "missing": [name for name, value in
                                                   ((pair["left"], left_total),
                                                    (pair["right"], right_total))
                                                   if value is None]})
            continue
        left_point = left_total["point"]
        right_point = right_total["point"]
        if left_point is not None and right_point is not None:
            # verdict 的 LEFT/RIGHT 指 pair["left"]/pair["right"] 这两案本身，
            # 与排序后的无序对键无关。
            if left_point == right_point:
                consistent = verdict == "TIE"
            elif verdict == "LEFT":
                consistent = left_point > right_point
            else:
                consistent = right_point > left_point
            if not consistent:
                conflicts.append({"kind": "arithmetic",
                                  "pair": [pair["left"], pair["right"]],
                                  "verdict": verdict,
                                  "totals": {pair["left"]: left_point,
                                             pair["right"]: right_point}})
            continue
        # 区间比较。口径统一（独立审查第 2 轮 P2-D）：
        #   区间**互不相容**（left 整体低于 right，裁判却说 LEFT）→ 冲突，方向反了；
        #   区间**重叠** → 不是冲突，只是“比较依据不足”，由下面的推荐分类
        #   归 CO_RECOMMENDATION（合同 §7.5）。不能让同一份重叠数据因为裁判
        #   写 LEFT 还是写 INSUFFICIENT 就落到两种完全不同的结论。
        left_low, left_high = left_total["low"], left_total["high"]
        right_low, right_high = right_total["low"], right_total["high"]
        left_below = left_high < right_low
        right_below = right_high < left_low
        overlaps = not (left_below or right_below)
        interval_comparisons.append({"pair": [pair["left"], pair["right"]],
                                     "verdict": verdict,
                                     "overlaps": overlaps})
        if overlaps:
            # 重叠：不冲突，交给推荐分类；记为“依据不足”以便分类时归并列。
            interval_insufficient.add(key)
            continue
        # 分离：裁判的方向必须与区间一致。
        if verdict == "LEFT":
            supports = right_below
        elif verdict == "RIGHT":
            supports = left_below
        else:  # TIE —— 区间明显分离时判 TIE 是方向错
            supports = False
        if not supports:
            conflicts.append({"kind": "arithmetic_interval",
                              "pair": [pair["left"], pair["right"]],
                              "verdict": verdict,
                              "intervals": {pair["left"]: [left_low, left_high],
                                            pair["right"]: [right_low, right_high]},
                              "detail": "两案区间分离，成对结论方向与之相反"})

    ranked_ids = [item for item in ids if item in parsed_totals]
    ordered = sorted(ranked_ids,
                     key=lambda item: (-(parsed_totals[item]["low"]), item))
    base = {
        "pairwise_expected": pairwise_expected(len(ids)),
        "pairwise_supplied": len(pairs or []),
        "ranking": ordered,
        "eligible_count": len(ids),
        "unranked_ids": sorted(set(ids) - set(ranked_ids)),
        "arithmetic_skipped": arithmetic_skipped,
        "interval_comparisons": interval_comparisons,
    }
    if conflicts:
        base.update({"status": "RANKING_CONFLICT", "conflicts": conflicts,
                     "champion": None, "leading_candidate": None,
                     "recommendation": {
                         "category": NO_RECOMMENDATION,
                         "candidate_ids": [],
                         "reason": "存在成对或算术冲突，先复算与核对场景/需求"}})
        return base

    if not ids:
        base.update({"status": "NO_ELIGIBLE", "champion": None,
                     "leading_candidate": None,
                     "recommendation": {"category": NO_RECOMMENDATION,
                                        "candidate_ids": [],
                                        "reason": "没有通过硬门的资格候选"}})
        return base

    if len(ids) == 1:
        base.update({"status": "SINGLE_ELIGIBLE", "champion": None,
                     "leading_candidate": ids[0],
                     "recommendation": {
                         "category": CONDITIONAL,
                         "candidate_ids": [ids[0]],
                         "reason": "仅一份有资格：只能说明唯一条件性候选，"
                                   "不称五案竞争的稳定冠军"}})
        return base

    leader = ordered[0]
    runner = ordered[1]
    lead_low = parsed_totals[leader]["low"]
    run_high = parsed_totals[runner]["high"]
    lead_point = parsed_totals[leader]["point"]
    run_point = parsed_totals[runner]["point"]
    margin = None
    if lead_point is not None and run_point is not None:
        margin = lead_point - run_point

    reasons = []
    overlap = lead_low <= run_high
    if overlap:
        reasons.append("区间重叠：首位 low=%s 不大于次位 high=%s" % (lead_low, run_high))
    if interval_insufficient:
        # 区间重叠的成对：比较依据不足，不是冲突。
        reasons.append("有 %d 组成对因区间重叠而依据不足" % len(interval_insufficient))
    if margin is not None and margin == 0:
        reasons.append("总分同分")
    elif margin is not None and 0 < margin <= near_margin:
        reasons.append("分差 %s 不大于 near_margin %s" % (margin, near_margin))
    if insufficient:
        reasons.append("存在 %d 组 INSUFFICIENT，比较依据不足" % len(insufficient))
    if perturbation is not None and perturbation.get("flip"):
        reasons.append("冻结权重扰动下冠亚翻转 %d 次"
                       % perturbation.get("leader_runner_flipped_combinations", 0))
    if lead_point is None:
        reasons.append("首位缺少确定总分（区间或未知），不能给确定冠军")

    # 合同 §7.5 分类（独立审查 P1-04）：
    #   CO_RECOMMENDATION      ← 区间重叠、缺比较依据（INSUFFICIENT）、同分、循环
    #   CONDITIONAL_PREFERENCE ← 近似区内、仅特定情景优先
    #   ROBUST_RECOMMENDATION  ← 硬门合格、无冲突、严格领先且超过 near_margin
    # 区间重叠必须归“并列”，不能归“条件性首选”。
    if insufficient or interval_insufficient or overlap or (
            margin is not None and margin == 0):
        category = CO_RECOMMENDATION
    elif reasons:
        category = CONDITIONAL
    else:
        category = ROBUST

    champion = leader if category == ROBUST else None
    base.update({
        "status": "CONSISTENT",
        "conflicts": [],
        "champion": champion,
        "leading_candidate": leader,
        "runner_up": runner,
        "margin": margin,
        "near_margin": near_margin,
        "interval_overlap": overlap,
        "insufficient_pairs": [list(item) for item in sorted(insufficient)],
        "recommendation": {
            "category": category,
            "candidate_ids": [leader] if category in (ROBUST, CONDITIONAL) else
                              [leader, runner],
            "reason": "；".join(reasons) if reasons else
                      "硬门合格、无冲突、同条件严格领先且超过 near_margin",
            "conditional_title": "条件性首选" if category == CONDITIONAL else None,
            "co_recommendation_note": (
                "并列或比较依据不足，由用户在并列案中选择" if category == CO_RECOMMENDATION
                else None),
        },
    })
    if claimed_champion is not None and claimed_champion != champion:
        base.update({"status": "RANKING_CONFLICT", "champion": None,
                     "conflicts": [{"kind": "claimed_champion",
                                    "claimed": claimed_champion,
                                    "computed": champion}],
                     "recommendation": {
                         "category": NO_RECOMMENDATION, "candidate_ids": [],
                         "reason": "声称的冠军与计算结论不一致"}})
    return base


def score_spec(payload):
    """CLI 主体：输入 spec → 各候选资格/总分/冲突/推荐。"""
    candidates = require_mapping(payload, "candidates")
    if not candidates:
        raise InputError("NO_CANDIDATES", "candidates 不能为空")
    results = {}
    eligible = []
    for candidate_id in sorted(candidates):
        spec = candidates[candidate_id]
        if not isinstance(spec, dict):
            raise InputError("CANDIDATE_NOT_OBJECT", "%s 必须是对象" % candidate_id)
        scored = score_candidate(spec.get("gates"), spec.get("cells", {}),
                                 path=candidate_id)
        results[candidate_id] = scored
        if scored["eligible"] and scored["total"] is not None:
            eligible.append(candidate_id)

    totals = {cid: results[cid]["total"] for cid in eligible}
    pairs = payload.get("pairs")
    out = {
        "weights": WEIGHTS,
        "near_margin": NEAR_MARGIN,
        "candidates": results,
        "eligible_ids": eligible,
        "totals": totals,
    }
    if pairs is None:
        out["ranking"] = {
            "status": "PAIRWISE_PENDING",
            "champion": None,
            "leading_candidate": None,
            "pairwise_expected": pairwise_expected(len(eligible)),
            "pairwise_supplied": 0,
            "recommendation": {
                "category": NOT_EVALUATED,
                "candidate_ids": [],
                "reason": "未提供成对矩阵；分数已算，但推荐不成立（缺比较依据）"},
        }
        return out
    out["ranking"] = check_ranking(eligible, totals, pairs,
                                   payload.get("claimed_champion"))
    return out


def _diagnostics(result, context=None, perturbation=None):
    """Additive robustness diagnostics; never changes champion or totals (Q2)."""
    ranking = result.get("ranking") or {}
    leader = ranking.get("leading_candidate")
    runner = ranking.get("runner_up")
    margin = ranking.get("margin")
    totals = result.get("totals") or {}
    runner_total = totals.get(runner) if runner else None
    context = context or {}
    flip_fact = None
    for row in context.get("flip_facts") or []:
        if (isinstance(row, dict) and row.get("candidate_id") in (leader, runner)
                and isinstance(row.get("fact"), str) and row["fact"].strip()):
            flip_fact = row["fact"].strip()
            break
    caliber = context.get("caliber")
    if not (isinstance(caliber, str) and caliber.strip()):
        caliber = "Σwᵢsᵢ/5；权重 20/25/15/12/10/8/10 冻结；near_margin=5"
    checked = [FACTORS[0], FACTORS[1]] if perturbation else None
    constraints = context.get("constraints")
    if not (isinstance(constraints, list) and all(isinstance(item, str) and item.strip()
                                                  for item in constraints)):
        constraints = []
    suggestion = context.get("suggested_action")
    if not (isinstance(suggestion, str) and suggestion.strip()):
        suggestion = None
    return {
        "nearest_rival": {"id": runner, "total": runner_total} if runner else None,
        "same_scenario_delta": margin,
        "caliber": caliber,
        "flip_fact": flip_fact,
        "weight_range_checked": checked,
        "perturbation_run": perturbation is not None,
        "scale_assumption": "0–100 锚点固定，不做候选内归一；扰动比例不解释为概率",
        "near_margin_distance": (margin - NEAR_MARGIN) if type(margin) in (int, float) else None,
        "constraints": constraints,
        "suggested_action": suggestion,
        "policy_unchanged": True,
    }


def score_current_formal(candidates, diagnostic_pairs, claimed_champion=None,
                         diagnostic_context=None):
    """Retain diagnostics for every formal case; rank only cases with an eligible total."""
    result = score_spec({"candidates": candidates})
    eligible = set(result["eligible_ids"])
    ranking_pairs = [row for row in diagnostic_pairs if row["left"] in eligible and row["right"] in eligible]
    result["ranking"] = check_ranking(result["eligible_ids"], result["totals"], ranking_pairs, claimed_champion)
    perturbation = None
    if isinstance(diagnostic_context, dict) and diagnostic_context.get("perturbation_run") is True:
        points = {}
        for cid, row in candidates.items():
            cells = row.get("cells") or {}
            values = {}
            complete = True
            for criterion in CRITERIA:
                cell = cells.get(criterion)
                if not isinstance(cell, dict) or cell.get("status", "SCORED") != "SCORED":
                    complete = False
                    break
                point = cell.get("point")
                if type(point) not in (int, float):
                    complete = False
                    break
                values[criterion] = point
            if complete:
                points[cid] = values
        if len(points) >= 2:
            perturbation = perturb(points)
    result["diagnostics"] = _diagnostics(result, diagnostic_context, perturbation)
    return result


def _parser():
    parser = argparse.ArgumentParser(
        prog="python -m cad_agent_showcase.governance.scoring",
        description="七维评分、硬门、成对一致性与推荐类别")
    parser.add_argument("path", help="评分输入 JSON")
    return parser


def cli(argv=None):
    args = _parser().parse_args(argv)
    from .envelope import run_cli
    return run_cli("scoring", score_spec, args)


if __name__ == "__main__":
    import sys
    sys.exit(cli(sys.argv[1:]))
