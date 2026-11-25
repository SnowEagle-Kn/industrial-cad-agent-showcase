# -*- coding: utf-8 -*-
"""One real checkpoint observation, never a request/stop/delivery collector.

Called only after the unchanged sessions._route guard. No file IO, scheduling,
clock bridges, cost aggregation, host authentication or performance verdict.
Observation fields retain their original anchor semantics. One point segment is
created per call; even matching process identities do not prove full coverage.
"""
import copy
import hashlib
import json
import math
import os
import socket
import threading
import time
import uuid
from datetime import datetime, timezone

from .envelope import InputError

SCHEMA = "wishcad.checkpoint-observation.v1"
CONSUMER_SCHEMA = "wishcad.checkpoint-consumer.v1"
COST_FIELDS = ("model_calls", "input_tokens", "output_tokens", "tool_calls")
SEATS = ("P", "D0", "D1", "D2", "D3", "D4", "J0")
_LOCK = threading.Lock()
_PROCESS = None


def _fail(detail):
    raise InputError("TIMING_OBSERVATION_INVALID", detail)


def _label(value, name, *, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        _fail(name + " must be a nonempty string of at most 256 characters")
    return value


def _number(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        _fail(name + " must be an integer >= " + str(minimum))
    return value


def _utc(value):
    _label(value, "UTC")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail("invalid UTC anchor")
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        _fail("UTC anchor must have an explicit zero offset")
    return value


def _digest(value):
    raw = {k: v for k, v in value.items() if k != "payload_digest"}
    return hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def observe_checkpoint(route, payload):
    """Sample real paired clocks after authorization; optional labels are claims.

    route.run_id/version are consumed from the guarded existing route. Payload
    labels do not authenticate a seat, an actual operation attempt or endpoints.
    Supplied timestamps/host/cost/coverage fields are never promoted to evidence.
    """
    global _PROCESS
    run_id = _label(route.get("run_id"), "route.run_id")
    revision = _label(route.get("version"), "route.version", optional=True)
    if payload.get("run_id") not in (None, run_id):
        _fail("checkpoint run_id differs from the guarded route")
    if payload.get("revision") is not None and payload["revision"] != revision:
        _fail("checkpoint revision differs from the guarded route version")
    stage = _label(payload.get("stage"), "stage")
    seat = _label(payload.get("seat"), "seat", optional=True)
    if seat is not None and seat not in SEATS:
        _fail("seat must be P, D0..D4 or J0")
    operation = _label(payload.get("operation_id"), "operation_id", optional=True)
    attempt = payload.get("attempt")
    if attempt is not None:
        _number(attempt, "attempt", 1)
        if operation is None:
            _fail("attempt requires an operation_id")
    with _LOCK:
        pid = os.getpid()
        if _PROCESS is None or _PROCESS["pid"] != pid:
            _PROCESS = dict(pid=pid, collector_instance_id="instance-" + uuid.uuid4().hex,
                            clock_domain_id="domain-" + uuid.uuid4().hex, sequence=0,
                            previous_tick=None)
        before = _number(time.monotonic_ns(), "monotonic before")
        utc = _utc(datetime.now(timezone.utc).isoformat())
        after = _number(time.monotonic_ns(), "monotonic after")
        if before > after or (_PROCESS["previous_tick"] is not None
                              and before < _PROCESS["previous_tick"]):
            _fail("CLOCK_REGRESSION: no clamping or invented replacement tick")
        _PROCESS["previous_tick"] = after
        _PROCESS["sequence"] += 1
        info = time.get_clock_info("monotonic")
        event = dict(
            schema=SCHEMA, event_kind="checkpoint_observation",
            event_id="observation-" + uuid.uuid4().hex,
            run_id=run_id, revision=revision, stage=stage, seat=seat,
            operation_id=operation, attempt=attempt,
            context_source={"run_id": "guarded_route.run_id",
                            "revision": "guarded_route.version" if revision is not None else "unavailable",
                            "stage": "checkpoint label", "seat_operation_attempt": "caller labels; not host receipts"},
            collector_id="wishcad.sessions.checkpoint.v1",
            collector_instance_id=_PROCESS["collector_instance_id"],
            clock_domain_id=_PROCESS["clock_domain_id"],
            segment_id="point-" + uuid.uuid4().hex,
            segment_semantics="one observation; continuity to any other checkpoint is unproven",
            sequence=_PROCESS["sequence"], process_id=pid,
            host_id=socket.gethostname(), host_identity_scope="local hostname observation; unauthenticated",
            boot_id=None, boot_unavailable_reason="OS boot identity not collected",
            monotonic_tick=after, tick_unit="ns",
            anchor={"utc": utc, "monotonic_before_ns": before,
                    "monotonic_after_ns": after, "uncertainty_ns": after - before},
            clock_implementation=info.implementation,
            clock_resolution_ns=max(1, math.ceil(info.resolution * 1_000_000_000)),
            monotonic=info.monotonic, adjustable=info.adjustable,
            suspend_accounting="unknown",
            suspend_reason="get_clock_info does not attest suspend accounting",
            aggregation="non_counting", costs={k: None for k in COST_FIELDS},
            cost_unavailable_reasons={k: "checkpoint has no provider/tool cost receipt" for k in COST_FIELDS},
            retry_count=None, retry_unavailable_reason="original unit attempt history not observed",
            rework_count=None, rework_unavailable_reason="rework history not observed",
            original_request_receipt=None, qualified_delivery=None, T_stop_s=None,
            delivery_elapsed_s=None, system_executable_elapsed_s=None,
            interval_from_previous_ns=None,
            clock_coverage_verified=False, identity_verified=False, quality_verified=False,
            complete_collector_chain=False, budget_origin_reset=False,
            unknown_reasons={
                "original_request_receipt": "checkpoint does not observe the original effective request",
                "qualified_delivery": "stage label does not prove a qualified delivery",
                "T_stop_s": "original request and actual stop endpoints not collected",
                "delivery_elapsed_s": "original request and qualified endpoint not collected",
                "system_executable_elapsed_s": "complete coverage and wait union not collected",
                "interval_from_previous_ns": "no consumed shared-domain continuous collector chain",
                "revision": None if revision is not None else "legacy route has no version",
                "seat": None if seat is not None else "seat not supplied",
                "operation_id": None if operation is not None else "operation not supplied",
                "attempt": None if attempt is not None else "actual attempt not supplied"},
        )
        event["payload_digest"] = _digest(event)
        return event


def consume_checkpoint(checkpoint, *, expected_run_id=None):
    """Minimal pure consumer of saved old/new checkpoint JSON.

    Returns an observation only. Does not invoke downstream timing analysis,
    compute inter-call differences or manufacture any missing ledger endpoint.
    Digest checks transport consistency, not provenance or independent acceptance.
    """
    if not isinstance(checkpoint, dict) or checkpoint.get("status") != "TIMING_RECORDED":
        _fail("expected a saved TIMING_RECORDED checkpoint")
    if checkpoint.get("schema") != "wishcad.sessions.v1.3":
        _fail("unknown checkpoint schema")
    run_id = _label(checkpoint.get("run_id"), "checkpoint.run_id")
    stage = _label(checkpoint.get("stage"), "checkpoint.stage")
    utc = _utc(checkpoint.get("observed_at"))
    if expected_run_id is not None and expected_run_id != run_id:
        _fail("saved checkpoint belongs to a different run")
    observation = checkpoint.get("timing_observation")
    if "timing_observation" in checkpoint:
        if not isinstance(observation, dict) or observation.get("schema") != SCHEMA:
            _fail("unknown timing_observation format")
        if observation.get("payload_digest") != _digest(observation):
            _fail("observation digest mismatch")
        if not isinstance(observation.get("anchor"), dict):
            _fail("paired anchor must be an object")
        if (observation.get("run_id"), observation.get("stage"), observation.get("anchor", {}).get("utc")) != (run_id, stage, utc):
            _fail("checkpoint/observation binding mismatch")
        if observation.get("event_kind") != "checkpoint_observation":
            _fail("checkpoint cannot claim request or delivery event semantics")
        anchor = observation["anchor"]
        before = _number(anchor.get("monotonic_before_ns"), "before")
        after = _number(anchor.get("monotonic_after_ns"), "after")
        if before > after or observation.get("monotonic_tick") != after or anchor.get("uncertainty_ns") != after - before:
            _fail("invalid paired anchor")
        for name in ("collector_id", "collector_instance_id", "clock_domain_id", "segment_id"):
            _label(observation.get(name), name)
        _number(observation.get("sequence"), "sequence", 1)
        if any(observation.get(k) is not None for k in ("original_request_receipt", "qualified_delivery", "T_stop_s", "delivery_elapsed_s", "system_executable_elapsed_s", "interval_from_previous_ns")):
            _fail("checkpoint cannot supply original endpoints or whole-run duration")
        if any(observation.get(k) is not False for k in ("complete_collector_chain", "clock_coverage_verified", "identity_verified", "quality_verified", "budget_origin_reset")):
            _fail("checkpoint cannot certify coverage/identity/quality or reset budget")
        if observation.get("aggregation") != "non_counting" or observation.get("costs") != {k: None for k in COST_FIELDS}:
            _fail("checkpoint cannot supply observed cost totals")
        if not isinstance(observation.get("cost_unavailable_reasons"), dict):
            _fail("cost reasons must be an object")
        if any(not isinstance(observation.get("cost_unavailable_reasons", {}).get(k), str) or not observation["cost_unavailable_reasons"][k].strip() for k in COST_FIELDS):
            _fail("null costs require nonempty reasons")
    return dict(schema=CONSUMER_SCHEMA, run_id=run_id, stage=stage, observed_at=utc,
                legacy_utc_only=observation is None, observation=copy.deepcopy(observation),
                original_request_receipt=None, qualified_delivery=None,
                interval_from_previous_ns=None, complete_collector_chain=False,
                budget_origin_reset=False, core_analysis_applicable=False,
                unknown_reason="observation only; original endpoints and complete collector chain absent")
