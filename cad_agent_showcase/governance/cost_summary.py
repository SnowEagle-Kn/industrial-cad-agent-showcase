# -*- coding: utf-8 -*-
"""Four-axis exploration cost summary from saved checkpoint observations (C0).

Only saved observations are consumed. Under the current point-observation
semantics the cost/rework fields are always null, so this module reports null
with a reason instead of guessing zero. Wall-clock can only be derived from
paired UTC anchors and is marked as a derived span.
"""
import math
from datetime import datetime

from .envelope import InputError

SCHEMA = "wishcad.exploration-cost-summary.v1"
TIERS = ("概念方案", "受支持板件设计图", "开发输出")
AXES = ("active_work", "model_tool", "rework", "wall_clock")


def _utc(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        return None
    return parsed


def _null_axis(reason):
    return {"status": "null", "value": None, "reason": reason}


def _wall(pairs):
    if len(pairs) < 2:
        return {"status": "not_available", "value": None, "range_seconds": None,
                "basis_refs": [],
                "reason": "少于两个相邻 UTC 锚点，无法派生等待跨度"}
    deltas = [(later - earlier).total_seconds() for earlier, later in zip(pairs, pairs[1:])]
    if any(delta <= 0 for delta in deltas):
        return {"status": "not_available", "value": None, "range_seconds": None,
                "basis_refs": [],
                "reason": "锚点顺序非递增或重复，不能当作相邻差值"}
    span = math.ceil(sum(deltas))
    return {"status": "derived_range", "value": None, "range_seconds": [0, span],
            "basis_refs": [],
            "reason": "锚点跨度上限；下界、时钟域与连续性未证，无法区分用户等待与模型工作"}


def summarize(observations, delivery_tier):
    if delivery_tier not in TIERS:
        raise InputError("COST_TIER_INVALID", "delivery_tier 必须为本机三档之一")
    by_stage = {}
    all_times = []
    for event in observations or []:
        if not isinstance(event, dict):
            raise InputError("COST_OBSERVATION_INVALID", "观测须为对象")
        stage = event.get("stage")
        utc = _utc(((event.get("anchor") or {}).get("utc")) or event.get("observed_at"))
        if not isinstance(stage, str) or not stage.strip() or utc is None:
            raise InputError("COST_OBSERVATION_INVALID", "观测须有 stage 与 UTC 锚点")
        by_stage.setdefault(stage, []).append(utc)
        all_times.append(utc)
    stages = {}
    for stage in by_stage:
        times = by_stage[stage]
        stages[stage] = {
            "active_work": _null_axis("无观测字段"),
            "model_tool": _null_axis("costs 四项恒 None（无 provider/工具回执）"),
            "rework": _null_axis("rework_history 未观测；attempt 为调用方标签"),
            "wall_clock": _wall(times),
        }
    summary = {
        "schema": SCHEMA,
        "delivery_tier": delivery_tier,
        "axes": {
            "active_work": _null_axis("无观测字段"),
            "model_tool": _null_axis("costs 四项恒 None（无 provider/工具回执）"),
            "rework": _null_axis("rework_history 未观测；attempt 为调用方标签"),
            "wall_clock": _wall(all_times),
        },
        "stages": stages,
        "note": "null 保持 null，不猜 0；不宣称四轴均已计量；成本对照须同一交付档",
    }
    return summary


def validate(summary):
    if not isinstance(summary, dict) or summary.get("schema") != SCHEMA:
        raise InputError("COST_SUMMARY_INVALID", "schema 不符")
    if summary.get("delivery_tier") not in TIERS:
        raise InputError("COST_SUMMARY_INVALID", "delivery_tier 不合法")
    axes = summary.get("axes")
    if not isinstance(axes, dict) or set(axes) != set(AXES):
        raise InputError("COST_SUMMARY_INVALID", "四轴不齐")
    for name in ("active_work", "model_tool", "rework"):
        axis = axes[name]
        if axis.get("status") != "null" or axis.get("value") is not None:
            raise InputError("COST_SUMMARY_INVALID", name + " 在点观测语义下只能为 null")
    wall = axes["wall_clock"]
    if wall.get("status") not in ("derived_range", "not_available"):
        raise InputError("COST_SUMMARY_INVALID", "壁钟只能派生区间或不可用")
    if wall.get("status") == "derived_range":
        span = wall.get("range_seconds")
        if not isinstance(span, list) or len(span) != 2 or span[0] > span[1]:
            raise InputError("COST_SUMMARY_INVALID", "派生区间非法")
    return summary
