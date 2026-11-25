# -*- coding: utf-8 -*-
"""六维差异检查。

判定人按合同是 P；本模块只对已给出的逐对 0/1/U 做算术汇总，
不从正文推断原理差异，因此不证明五案真实不同。

F08 整改：被检查范围必须完整。
  * 给了 complete_ids：由五个实际完整候选**生成**唯一无序对，要求 pairs
    精确覆盖——数量相等、无缺、无重、无自配对、成员都在候选集内。
    任一不满足返回 PAIRS_INCOMPLETE，不给 CHECKED。
  * 每对六维必须齐全且不含 U，否则返回 DIMENSIONS_INCOMPLETE。
  * 不给 complete_ids 的老调用仍按 complete_count 算 pair_expected，
    但同样校验对数相等且无重复对；不满足仍不给 CHECKED（用状态字段，
    不抛异常打断调用方）。
"""

import argparse

from .envelope import InputError, RuleRejection

DIMENSIONS = ("basis", "topology", "load_path", "adjust_lock",
              "maintenance", "unknown_handling")
CORE_DIMENSIONS = DIMENSIONS[:4]
REQUIRED_COMPLETE = 5

STATUS_CHECKED = "CHECKED"
STATUS_COLLECTING = "COLLECTING_INCOMPLETE"
STATUS_PAIRS_INCOMPLETE = "PAIRS_INCOMPLETE"
STATUS_DIMENSIONS_INCOMPLETE = "DIMENSIONS_INCOMPLETE"
STATUS_CONSTRAINED = "DIVERSITY_CONSTRAINED"


def _pair_verdict(pair, index):
    if not isinstance(pair, dict):
        raise InputError("PAIR_NOT_AN_OBJECT", "pairs[%d] 必须是对象" % index)
    marks = pair.get("marks", {})
    if not isinstance(marks, dict):
        raise InputError("MARKS_NOT_AN_OBJECT", "pairs[%d].marks 必须是对象" % index)
    for name, mark in marks.items():
        if name not in DIMENSIONS:
            raise InputError("MARK_UNKNOWN_DIMENSION",
                             "pairs[%d].marks 含未知维度 %r" % (index, name))
        ok = (mark == "U") or (type(mark) is int and mark in (0, 1))
        if not ok:
            raise InputError("MARK_INVALID",
                             "pairs[%d].marks[%s] 只能是 0、1 或 U" % (index, name))
    unresolved = [name for name in DIMENSIONS if name not in marks or marks[name] == "U"]
    different = [name for name in DIMENSIONS if marks.get(name) == 1]
    core = [name for name in different if name in CORE_DIMENSIONS]
    return {
        "left": pair.get("left"),
        "right": pair.get("right"),
        "different_count": len(different),
        "core_different_count": len(core),
        "different_dimensions": different,
        "unresolved_dimensions": unresolved,
        "qualified": (not unresolved) and len(different) >= 2 and len(core) >= 1,
    }


def _pair_key(left, right):
    """无序对键：A|B 与 B|A 视为同一对。"""
    if left is None or right is None:
        raise InputError("PAIR_MEMBER_MISSING", "每对必须有 left 和 right")
    return tuple(sorted((str(left), str(right))))


def _key_text(key):
    return "%s|%s" % key


def _expected_keys(complete_ids):
    ids = []
    duplicates = []
    for value in complete_ids:
        text = str(value)
        if text in ids:
            if text not in duplicates:
                duplicates.append(text)
            continue
        ids.append(text)
    keys = set()
    for i, left in enumerate(ids):
        for right in ids[i + 1:]:
            keys.add(tuple(sorted((left, right))))
    return ids, keys, duplicates


def check_diversity(pairs, complete_count, explanations=None, complete_ids=None, *, formal_set=False):
    """pairs: [{left, right, marks: {六维: 0|1|U}}]。

    五份全趋同（没有任何一对达到“至少 2 维且前四维至少 1 维”）时
    返回 DIVERSITY_CONSTRAINED，并要求说明；不伪造差异。
    """
    if not isinstance(pairs, list):
        raise InputError("PAIRS_NOT_A_LIST", "pairs 必须是数组")
    try:
        count = int(complete_count)
    except (TypeError, ValueError):
        raise InputError("COMPLETE_COUNT_INVALID", "complete_count 必须是整数")
    if count < 0:
        raise InputError("COMPLETE_COUNT_NEGATIVE", "complete_count 不能为负")

    judged = [_pair_verdict(pair, index) for index, pair in enumerate(pairs)]
    keys = [_pair_key(item["left"], item["right"]) for item in judged]

    self_pairs = sorted({_key_text(key) for key in keys if key[0] == key[1]})
    seen = {}
    for key in keys:
        seen[key] = seen.get(key, 0) + 1
    duplicate_pairs = sorted(_key_text(key) for key, times in seen.items() if times > 1)

    expected_keys = set()
    unknown_members = []
    duplicate_ids = []
    if complete_ids is not None:
        if not isinstance(complete_ids, list):
            raise InputError("COMPLETE_IDS_NOT_A_LIST", "complete_ids 必须是数组")
        ids, expected_keys, duplicate_ids = _expected_keys(complete_ids)
        if count != len(ids):
            # 自报份数与实际 ID 数量冲突时不能静默取后者（P2-05）。
            # `complete_count=0` 也在此列：0 是“零份完整”，不是“未提供”，
            # 旧写法 `if count and ...` 把 0 当假值放过（第 3 轮 P2-04）。
            raise InputError(
                "COMPLETE_COUNT_CONFLICT",
                "complete_count=%d 与 complete_ids 的 %d 个不同 ID 不一致；"
                "两者必须相符，不能静默覆盖" % (count, len(ids)))
        count = len(ids)
        known = set(ids)
        unknown = sorted({member for key in keys for member in key if member not in known})
        unknown_members = unknown
    else:
        expected_keys = set()

    pair_expected = (len(expected_keys) if complete_ids is not None
                     else count * (count - 1) // 2)

    missing_pairs = []
    extra_pairs = []
    if complete_ids is not None:
        missing_pairs = sorted(_key_text(key) for key in expected_keys - set(keys))
        extra_pairs = sorted(_key_text(key) for key in set(keys) - expected_keys
                             if key[0] != key[1])
    else:
        # 老调用没有候选清单，只能校验对数与重复。
        extra_pairs = sorted(_key_text(key) for key, times in seen.items() if times > 1)

    unresolved_pairs = [
        {"pair": _key_text(keys[index]),
         "unresolved_dimensions": item["unresolved_dimensions"]}
        for index, item in enumerate(judged) if item["unresolved_dimensions"]
    ]
    any_qualified = any(item["qualified"] for item in judged)

    result = {
        "complete_count": count,
        "required_complete": count if formal_set else REQUIRED_COMPLETE,
        "pair_count": len(judged),
        "pair_expected": pair_expected,
        "pairs": judged,
        "forged_difference": False,
        "complete_ids_supplied": complete_ids is not None,
        "missing_pairs": missing_pairs,
        "duplicate_pairs": duplicate_pairs,
        "unknown_members": unknown_members,
        "duplicate_ids": duplicate_ids,
        "self_pairs": self_pairs,
        "extra_pairs": extra_pairs,
        "unresolved_pairs": unresolved_pairs,
        "coverage_complete": False,
        "dimensions_complete": not unresolved_pairs,
    }

    coverage_problem = bool(missing_pairs or duplicate_pairs or unknown_members
                            or duplicate_ids or self_pairs
                            or len(judged) != pair_expected)
    if complete_ids is not None and extra_pairs:
        coverage_problem = True
    result["coverage_complete"] = not coverage_problem

    if not formal_set and count < REQUIRED_COMPLETE:
        result["status"] = STATUS_COLLECTING
        result["note"] = "收到 %d/%d，不复制凑数、不缩分母" % (count, REQUIRED_COMPLETE)
        if coverage_problem or unresolved_pairs:
            result["note"] += "；差异对本身也未覆盖完整，收齐后重查"
        return result

    if coverage_problem:
        result["status"] = STATUS_PAIRS_INCOMPLETE
        result["note"] = (
            "差异对被检查范围不完整：应有 %d 对，实收 %d 对；"
            "缺对/重复/自配对/越界成员均不得判 CHECKED" % (pair_expected, len(judged)))
        if unresolved_pairs:
            result["note"] += "；另有 %d 对六维不齐" % len(unresolved_pairs)
        return result

    if unresolved_pairs:
        result["status"] = STATUS_DIMENSIONS_INCOMPLETE
        result["note"] = ("%d 对存在缺维或 U，六维不齐不能判 CHECKED" % len(unresolved_pairs))
        return result

    if formal_set and count == 1:
        result.update(status=STATUS_CHECKED, note="一案，无互比对；按同工况比较基线")
        return result
    if not any_qualified:
        result["status"] = STATUS_CONSTRAINED
        if not explanations:
            result["note"] = "全趋同但未附被排除原理及理由，不得判 CHECKED，也不伪造差异"
            raise RuleRejection(
                STATUS_CONSTRAINED,
                "DIVERSITY_CONSTRAINED 必须附被排除原理及理由，不伪造差异",
                result)
        result["explanations"] = explanations
        result["note"] = "共同约束下原理收敛；不是多样性通过，说明后仍可比较"
        return result

    result["status"] = STATUS_CHECKED
    result["note"] = ("本版全部候选对已覆盖，六维齐全，至少一对达到 2/6 且前四维 1 维"
                      if formal_set else "五案十对覆盖完整，六维齐全，至少一对达到 2/6 且前四维 1 维")
    return result


def _runner(payload):
    if not isinstance(payload, dict):
        raise InputError("NOT_AN_OBJECT", "顶层必须是 JSON 对象")
    if "pairs" not in payload:
        raise InputError("MISSING_FIELD", "缺少字段 pairs")
    return check_diversity(payload.get("pairs", []),
                           payload.get("complete_count", 0),
                           payload.get("explanations"),
                           complete_ids=payload.get("complete_ids"))


def _parser():
    parser = argparse.ArgumentParser(
        prog="python -m cad_agent_showcase.governance.diversity",
        description="六维差异检查：pairs、complete_count、complete_ids、explanations")
    parser.add_argument("path", help="含 pairs/complete_count/complete_ids 的 JSON")
    return parser


def cli(argv=None):
    args = _parser().parse_args(argv)
    from .envelope import run_cli
    return run_cli("diversity", _runner, args)


if __name__ == "__main__":
    import sys
    sys.exit(cli(sys.argv[1:]))
