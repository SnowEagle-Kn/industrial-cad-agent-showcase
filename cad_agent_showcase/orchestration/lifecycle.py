# -*- coding: utf-8 -*-
"""Two-entry replay workflow with a real state machine.

The workflow executes transitions itself.  Fixed replay content comes from
the fixtures, but revision changes, confirmation binding, invalidation and
delivery gating are computed from the current task version.
"""

import copy
import os

from .. import evidence
from .delivery_bundle import write_standard_bundle
from ..confirmation import (ACTION_ACCEPT, ACTION_REJECT, binding_from_state,
                           compute_binding_sha256, invalidate, make_event,
                           record_confirmation, verify_for_delivery,
                           verify_reuse)
from ..contracts import (CODE_CONFIRMATION_REQUIRED, CODE_DUPLICATE_DELIVERY, ENGINEERING_FLAGS,
                        CODE_USER_REJECTED, ENTRY_CONCEPT, ENTRY_DRAWING,
                        STATE_CONCEPT_DRAFT, STATE_CONCEPT_ONLY_CLOSED,
                        STATE_CONFIRMATION_REQUIRED, STATE_CONFIRMED,
                        STATE_DESIGN_ONLY_CLOSED, STATE_DRAWING_INSPECTED,
                        STATE_NEED_PARAMETERS, STATE_PARAMETERS_READY,
                        STATE_REPLAY_DELIVERED, ReplayRejection)
from ..util import canonical_sha256

CONCEPT_ACCEPT_EVENT = "EVT-DEMO-CONCEPT-ACCEPT-1"
CONCEPT_REJECT_EVENT = "EVT-DEMO-CONCEPT-REJECT-1"
DRAWING_ACCEPT_EVENT = "EVT-DEMO-DRAWING-ACCEPT-1"

OBSERVED_CONCEPT = "2026-01-01T00:00:01Z"
OBSERVED_PARAMS = "2026-01-01T00:00:02Z"
OBSERVED_CONFIRM = "2026-01-01T00:00:03Z"
OBSERVED_MUTATION = "2026-01-01T00:00:04Z"
OBSERVED_REJECT = "2026-01-01T00:00:05Z"
OBSERVED_CONTINUE = "2026-01-01T00:00:06Z"
OBSERVED_DUPLICATE = "2026-01-01T00:00:07Z"


def _trace(state, note):
    state["trace"].append({
        "status": state["status"],
        "revision": state["revision"],
        "note": note,
    })


def _brief_digest(brief):
    return canonical_sha256(brief)


def _parameters_summary(parameters_payload):
    summary = []
    for item in parameters_payload.get("parameters", []):
        summary.append({
            "parameter_id": item["parameter_id"],
            "value": item.get("value"),
            "unit": item.get("unit"),
            "source": "USER_INPUT",
            "verified": False,
        })
    return summary


def _new_state(*, task_id, entry, fixture_id, input_digest, brief,
               assumptions, deliverable_spec):
    return {
        "task_id": task_id,
        "entry": entry,
        "fixture_id": fixture_id,
        "revision": 1,
        "status": STATE_CONCEPT_DRAFT if entry == ENTRY_CONCEPT else STATE_DRAWING_INSPECTED,
        "input_digest": input_digest,
        "brief": brief,
        "brief_digest": _brief_digest(brief),
        "parameters": None,
        "parameters_digest": "",
        "parameters_summary": [],
        "assumptions": list(assumptions),
        "assumptions_digest": canonical_sha256(list(assumptions)),
        "candidates": [],
        "selected_candidate": None,
        "candidate_digest": "",
        "deliverable_spec": copy.deepcopy(deliverable_spec),
        "deliverable_spec_digest": canonical_sha256(deliverable_spec),
        "object_summary": None,
        "confirmation": None,
        "delivered_binding_sha256": None,
        "deliveries": [],
        "events": [],
        "trace": [],
        **ENGINEERING_FLAGS,
    }


def _publish_context(context, state):
    context.update({
        "task_id": state.get("task_id"),
        "entry": state.get("entry"),
        "revision": state.get("revision"),
        "input_digest": state.get("input_digest"),
        "state": state,
    })


# ---------------------------------------------------------------- concept
def start_concept(engine):
    payload = engine.load_concept_input()
    info = engine.inspect_concept_input(payload)
    expected = info["expected"]
    known = payload.get("known", {})
    required = expected.get("required_parameters", [])
    unknowns = [parameter_id for parameter_id in required
                if parameter_id not in known or known[parameter_id] in (None, "")]
    brief = {
        "task_id": payload["task_id"],
        "title": payload.get("title"),
        "description": payload.get("description"),
        "known": known,
        "missing_required_parameters": unknowns,
    }
    state = _new_state(
        task_id=payload["task_id"],
        entry=ENTRY_CONCEPT,
        fixture_id=expected["fixture_id"],
        input_digest=info["input_digest"],
        brief=brief,
        assumptions=expected.get("assumptions", []),
        deliverable_spec=expected["deliverable"],
    )
    state["unknowns"] = unknowns
    _trace(state, "concept input inspected; %d UNKNOWN parameters preserved" % len(unknowns))
    return state, expected


def build_concept(state, engine, expected):
    state["candidates"] = engine.run_cognition_gate(expected)
    state["status"] = STATE_NEED_PARAMETERS
    _trace(state, "concept candidates replayed; assumptions kept separate from parameters")
    return state


def _apply_parameters(state, engine, expected, fixture_name):
    payload = engine.load_parameters(
        engine_group_for(state), fixture_name)
    resolved = engine.solve_parameter_bridge(expected, payload)
    state["parameters"] = payload
    state["parameters_digest"] = resolved["parameters_digest"]
    state["parameters_summary"] = _parameters_summary(payload)
    state["revision"] += 1
    state["status"] = STATE_PARAMETERS_READY
    state["events"].append({
        "schema": "cad_agent_showcase.parameter_event.v1",
        "event_id": "EVT-DEMO-PARAMETERS-%d" % state["revision"],
        "action": "SUPPLEMENT_PARAMETERS",
        "revision": state["revision"],
        "parameters_digest": resolved["parameters_digest"],
        "mode": "replay",
        "evidence_type": "replay_simulated",
    })
    _trace(state, "parameters accepted; revision %d" % state["revision"])
    return payload


def engine_group_for(state):
    from ..engines.replay_stub import CONCEPT_FIXTURE_DIR, DRAWING_FIXTURE_DIR
    return CONCEPT_FIXTURE_DIR if state["entry"] == ENTRY_CONCEPT else DRAWING_FIXTURE_DIR


def require_confirmation(state):
    state["status"] = STATE_CONFIRMATION_REQUIRED
    _trace(state, "confirmation required for the current revision")
    return state


def confirm(state, action=ACTION_ACCEPT, event_id=None, observed_at=None,
            selected_candidate_id=None):
    if action == ACTION_REJECT:
        binding = binding_from_state(state)
        event = make_event(event_id or "EVT-DEMO-REJECT",
                           ACTION_REJECT,
                           observed_at or OBSERVED_REJECT)
        record = record_confirmation(binding, event)
        state["confirmation"] = record
        state["events"].append(event)
        state["status"] = (STATE_CONCEPT_ONLY_CLOSED if state["entry"] == ENTRY_CONCEPT
                           else STATE_DESIGN_ONLY_CLOSED)
        _trace(state, "user rejected the current revision; no deliverable produced")
        return state

    if state["entry"] == ENTRY_CONCEPT:
        if not state["candidates"]:
            raise ReplayRejection(CODE_CONFIRMATION_REQUIRED,
                                  "no concept candidate is available to confirm")
        selected = None
        for candidate in state["candidates"]:
            if selected_candidate_id is None or candidate.get("candidate_id") == selected_candidate_id:
                selected = candidate
                break
        if selected is None:
            raise ReplayRejection(CODE_CONFIRMATION_REQUIRED,
                                  "selected candidate does not exist: %r" % selected_candidate_id)
    else:
        selected = {"candidate_id": state["deliverable_spec"]["deliverable_id"],
                    "label": "synthetic plate demo deliverable"}
    state["selected_candidate"] = copy.deepcopy(selected)
    state["candidate_digest"] = canonical_sha256(
        state["object_summary"] if state["entry"] == ENTRY_DRAWING else selected)
    assumptions = list(state["assumptions"])
    for assumption in selected.get("assumptions", []):
        if assumption not in assumptions:
            assumptions.append(assumption)
    state["assumptions"] = assumptions
    state["assumptions_digest"] = canonical_sha256(assumptions)
    binding = binding_from_state(state)
    event = make_event(event_id or "EVT-DEMO-ACCEPT",
                       ACTION_ACCEPT,
                       observed_at or OBSERVED_CONFIRM,
                       selected_candidate_id=selected.get("candidate_id"))
    record = record_confirmation(binding, event)
    if record.get("state") != "RECORDED":
        raise ReplayRejection(CODE_CONFIRMATION_REQUIRED,
                              "confirmation was not recorded",
                              {"record": record})
    state["confirmation"] = record
    state["events"].append(event)
    state["status"] = STATE_CONFIRMED
    _trace(state, "confirmation recorded for revision %d" % state["revision"])
    return state


def _readback_concept(state, deliverable):
    parameters = {item["parameter_id"]: item.get("value")
                  for item in state["parameters"]["parameters"]}
    return {
        "fields": {
            "envelope_length_mm": parameters.get("envelope_length_mm"),
            "envelope_width_mm": parameters.get("envelope_width_mm"),
            "plate_thickness_mm": parameters.get("plate_thickness_mm"),
            "hole_pitch_mm": parameters.get("hole_pitch_mm"),
            "material": parameters.get("material"),
        },
        "counts": {"holes": deliverable["readback_spec"].get("counts", {}).get("holes", 2)},
        "from_user_input": sorted(parameters),
        "demo_assumptions": list(state["assumptions"]),
        "not_verified": ["load_n", "tolerance", "surface_treatment",
                         "strength", "manufacturability"],
        "media_hashes_verified": True,
        "note": "Readback checks manifest fields and pre-generated DEMO media hashes; "
                "it does not measure geometry.",
    }


def _readback_drawing(state, deliverable):
    parameters = {item["parameter_id"]: item.get("value")
                  for item in state["parameters"]["parameters"]}
    summary = state["object_summary"]
    return {
        "fields": {
            "material": parameters.get("material"),
            "plate_thickness_mm": parameters.get("plate_thickness_mm"),
            "hole_spec": parameters.get("hole_spec"),
            "tolerance": parameters.get("tolerance"),
        },
        "geometry": {
            "width_mm": summary["extents_mm"]["width"],
            "height_mm": summary["extents_mm"]["height"],
            "circles": summary["entities"]["CIRCLE"],
            "lines": summary["entities"]["LINE"],
            "texts": summary["entities"]["TEXT"],
            "unknown_objects": [item["type"] for item in summary["unknown_entities"]],
        },
        "from_file": {
            "width_mm": summary["extents_mm"]["width"],
            "height_mm": summary["extents_mm"]["height"],
            "circle_count": summary["entities"]["CIRCLE"],
        },
        "from_user_input": sorted(parameters),
        "demo_assumptions": list(state["assumptions"]),
        "not_verified": ["hole_position_tolerance", "material_certificate",
                         "surface_treatment", "manufacturability"],
        "media_hashes_verified": True,
        "note": "Readback checks the recorded synthetic DXF summary and pre-generated "
                "DEMO media hashes; it does not verify geometry or manufacture.",
    }


# ---------------------------------------------------------------- drawing
def start_drawing(engine, filename="plate-demo.dxf", *, source=None):
    info = engine.inspect_drawing(filename) if source is None else engine.inspect_drawing_source(source)
    filename = info["file"]
    expected = info["expected"]
    summary = info["object_summary"]
    brief = {
        "task_id": expected["task_id"],
        "file": filename,
        "format": info["format"],
        "objects": summary["entities"],
        "unknown_objects": [item["type"] for item in summary["unknown_entities"]],
    }
    state = _new_state(
        task_id=expected["task_id"],
        entry=ENTRY_DRAWING,
        fixture_id=expected["fixture_id"],
        input_digest=info["file_sha256"],
        brief=brief,
        assumptions=["The fixed fixture summary records LINE/CIRCLE/TEXT; "
                     "unknown entities remain listed without interpretation."],
        deliverable_spec=expected["deliverable"],
    )
    state["object_summary"] = summary
    state["file"] = filename
    _trace(state, "drawing inspected; unknown entities preserved without interpretation")
    return state, expected


def drawing_need_parameters(state, expected):
    state["missing_conditions"] = list(expected.get("missing_conditions", []))
    state["status"] = STATE_NEED_PARAMETERS
    _trace(state, "engineering conditions missing: %s"
           % ",".join(state["missing_conditions"]))
    return state


def next_drawing_revision(state, engine, filename):
    """Inspect a new drawing file as a new task revision."""
    info = engine.inspect_drawing(filename)
    new_state = copy.deepcopy(state)
    new_state["revision"] += 1
    new_state["input_digest"] = info["file_sha256"]
    new_state["object_summary"] = info["object_summary"]
    new_state["file"] = filename
    new_state["brief"] = {
        "task_id": state["task_id"],
        "file": filename,
        "format": info["format"],
        "objects": info["object_summary"]["entities"],
        "unknown_objects": [item["type"] for item in info["object_summary"]["unknown_entities"]],
    }
    new_state["brief_digest"] = _brief_digest(new_state["brief"])
    new_state["status"] = STATE_DRAWING_INSPECTED
    if isinstance(state.get("confirmation"), dict):
        new_state["previous_confirmation"] = copy.deepcopy(state["confirmation"])
        new_state["confirmation"] = invalidate(state["confirmation"], binding_from_state(new_state))
    _trace(new_state, "drawing bytes changed; new revision %d" % new_state["revision"])
    return new_state, info["expected"]


def next_parameter_revision(state, engine, expected, fixture_name):
    """Apply a new parameter set as a new task revision."""
    new_state = copy.deepcopy(state)
    previous_confirmation = new_state.get("confirmation")
    _apply_parameters(new_state, engine, expected, fixture_name)
    require_confirmation(new_state)
    new_state["previous_confirmation"] = previous_confirmation
    if isinstance(previous_confirmation, dict):
        new_state["confirmation"] = invalidate(previous_confirmation, binding_from_state(new_state))
    return new_state


# ---------------------------------------------------------------- delivery
def emit_and_readback(state, engine, command, out_dir):
    verification = verify_for_delivery(state)
    if not verification["allowed"]:
        raise ReplayRejection(
            verification["code"],
            "delivery is blocked for the current revision",
            {"verification": verification,
             "state_trace": copy.deepcopy(state["trace"])})
    binding = binding_from_state(state)
    current_sha = compute_binding_sha256(binding)
    if state.get("delivered_binding_sha256") == current_sha:
        raise ReplayRejection(
            CODE_DUPLICATE_DELIVERY,
            "this confirmation already produced a deliverable",
            {"binding_sha256": current_sha,
             "state_trace": copy.deepcopy(state["trace"])})
    deliverable = engine.emit_and_verify_sheets(state["deliverable_spec"])
    booklet = engine.replay_booklet()
    media_artifacts = engine.copy_media(deliverable, out_dir)
    readback = (_readback_concept(state, deliverable)
                if state["entry"] == ENTRY_CONCEPT
                else _readback_drawing(state, deliverable))
    manifest, manifest_sha = evidence.write_delivery(
        out_dir,
        command=command,
        task_id=state["task_id"],
        entry=state["entry"],
        revision=state["revision"],
        fixture_id=state["fixture_id"],
        input_digest=state["input_digest"],
        brief_digest=state["brief_digest"],
        parameters_digest=state["parameters_digest"],
        assumptions_digest=state["assumptions_digest"],
        candidate_digest=state["candidate_digest"],
        deliverable_spec_digest=state["deliverable_spec_digest"],
        confirmation=state["confirmation"],
        parameters_summary=state["parameters_summary"],
        readback=readback,
        events=state["events"],
        deliverable=deliverable,
        media_artifacts=media_artifacts,
    )
    state["artifact_verification"] = engine.readback(manifest, out_dir)
    state["artifact_verification"]["standard_bundle"] = write_standard_bundle(
        out_dir, manifest, manifest_sha, booklet)
    state["delivered_binding_sha256"] = current_sha
    state["deliveries"].append({
        "revision": state["revision"],
        "binding_sha256": current_sha,
        "manifest": os.path.join(out_dir, "manifest.json"),
        "manifest_sha256": manifest_sha,
        "artifacts": [item["path"] for item in media_artifacts],
    })
    state["status"] = STATE_REPLAY_DELIVERED
    _trace(state, "replay deliverable emitted with DEMO/REPLAY manifest")
    return manifest, manifest_sha, readback


# ---------------------------------------------------------------- runs
def run_concept_demo(repo_root, fixture_root, out_dir, fail_engine, context):
    engine = engine_for(repo_root, fixture_root, fail_engine)
    state, expected = start_concept(engine)
    _publish_context(context, state)
    state = build_concept(state, engine, expected)
    _apply_parameters(state, engine, expected, "parameters.json")
    _publish_context(context, state)
    require_confirmation(state)
    confirm(state, ACTION_ACCEPT, CONCEPT_ACCEPT_EVENT, OBSERVED_CONFIRM, "C1")
    _publish_context(context, state)
    manifest, manifest_sha, readback = emit_and_readback(
        state, engine, "demo concept", out_dir)
    _publish_context(context, state)
    return state, manifest, manifest_sha, readback


def run_drawing_demo(repo_root, fixture_root, out_dir, fail_engine, context, *, source=None):
    engine = engine_for(repo_root, fixture_root, fail_engine)
    state, expected = start_drawing(engine, source=source)
    _publish_context(context, state)
    drawing_need_parameters(state, expected)
    _apply_parameters(state, engine, expected, "parameters.json")
    _publish_context(context, state)
    require_confirmation(state)
    confirm(state, ACTION_ACCEPT, DRAWING_ACCEPT_EVENT, OBSERVED_CONFIRM)
    _publish_context(context, state)
    manifest, manifest_sha, readback = emit_and_readback(
        state, engine, "demo drawing", out_dir)

    # Negative mutation: the file bytes change, so the old confirmation cannot
    # be carried over to the new revision.
    old_confirmation = state["confirmation"]
    changed_fixture = "plate-demo-mutated.dxf" if state["file"] == "plate-demo.dxf" else "plate-demo.dxf"
    mutated_state, _ = next_drawing_revision(state, engine, changed_fixture)
    mutation_diff = invalidate(old_confirmation, binding_from_state(mutated_state))
    blocked = verify_for_delivery(dict(mutated_state, confirmation=old_confirmation))
    _publish_context(context, mutated_state)
    state["mutation_check"] = {
        "new_revision": mutated_state["revision"],
        "input_digest_changed": mutated_state["input_digest"] != state["input_digest"],
        "invalidation": {
            "state": mutation_diff.get("state"),
            "changed_fields": mutation_diff.get("invalidated_by", {}).get("changed_fields"),
        },
        "old_confirmation_delivery": {"allowed": blocked["allowed"],
                                      "code": blocked["code"]},
    }
    return state, manifest, manifest_sha, readback


def run_confirmation_mutation_demo(repo_root, fixture_root, out_dir, fail_engine,
                                   context):
    engine = engine_for(repo_root, fixture_root, fail_engine)
    expected = engine.concept_expected()
    scenarios = []

    state, _ = start_concept(engine)
    _publish_context(context, state)
    state = build_concept(state, engine, expected)
    _apply_parameters(state, engine, expected, "parameters.json")
    require_confirmation(state)
    confirm(state, ACTION_ACCEPT, CONCEPT_ACCEPT_EVENT, OBSERVED_CONFIRM, "C1")
    emit_and_readback(state, engine, "demo confirmation-mutation", out_dir)
    scenarios.append({
        "scenario": "baseline_delivery",
        "status": state["status"],
        "code": "OK",
        "revision": state["revision"],
        "manifest": state["deliveries"][-1]["manifest_sha256"],
    })
    old_confirmation = state["confirmation"]

    # 1. A parameter change creates a new revision and invalidates the old confirmation.
    mutated_state = next_parameter_revision(state, engine, expected,
                                            "parameters-mutated.json")
    _publish_context(context, mutated_state)
    invalidation = invalidate(old_confirmation, binding_from_state(mutated_state))
    scenarios.append({
        "scenario": "old_confirmation_invalidated",
        "status": invalidation.get("state"),
        "code": "OK",
        "changed_fields": invalidation.get("invalidated_by", {}).get("changed_fields"),
        "revision": mutated_state["revision"],
    })

    # 2. Delivering with the stale confirmation is refused.
    stale_state = dict(mutated_state, confirmation=old_confirmation)
    blocked = verify_for_delivery(stale_state)
    scenarios.append({
        "scenario": "deliver_with_old_confirmation",
        "status": "REJECTED",
        "code": blocked["code"],
        "allowed": blocked["allowed"],
        "revision": mutated_state["revision"],
    })

    # 3. Reusing the old record is detected explicitly.
    reuse = verify_reuse(old_confirmation, binding_from_state(mutated_state))
    scenarios.append({
        "scenario": "old_confirmation_reuse",
        "status": "REJECTED",
        "code": reuse["code"],
        "reused": reuse["reused"],
        "revision": mutated_state["revision"],
    })

    # 4. A user rejection closes the current revision without delivery.
    rejected_state = copy.deepcopy(mutated_state)
    rejected_state["confirmation"] = None
    confirm(rejected_state, ACTION_REJECT, CONCEPT_REJECT_EVENT, OBSERVED_REJECT)
    scenarios.append({
        "scenario": "user_reject",
        "status": rejected_state["status"],
        "code": CODE_USER_REJECTED,
        "revision": rejected_state["revision"],
        "deliveries": len(rejected_state["deliveries"]),
    })

    # 5. A later revision can continue: fresh parameters, fresh confirmation, delivery.
    continued_state = next_parameter_revision(rejected_state, engine, expected,
                                              "parameters-continued.json")
    _publish_context(context, continued_state)
    confirm(continued_state, ACTION_ACCEPT, "EVT-DEMO-CONTINUE-ACCEPT",
            OBSERVED_CONTINUE, "C1")
    manifest, manifest_sha, _ = emit_and_readback(
        continued_state, engine, "demo confirmation-mutation", out_dir)
    scenarios.append({
        "scenario": "new_revision_continuation",
        "status": continued_state["status"],
        "code": "OK",
        "revision": continued_state["revision"],
        "manifest": manifest_sha,
    })

    # 6. A repeated delivery with the same confirmation is refused.
    duplicate = verify_for_delivery(continued_state)
    duplicate_blocked = False
    try:
        emit_and_readback(continued_state, engine, "demo confirmation-mutation", out_dir)
    except ReplayRejection as exc:
        duplicate_blocked = exc.code == CODE_DUPLICATE_DELIVERY
    scenarios.append({
        "scenario": "duplicate_execution",
        "status": "REJECTED" if duplicate_blocked else "UNEXPECTED",
        "code": CODE_DUPLICATE_DELIVERY if duplicate_blocked else "NOT_BLOCKED",
        "revision": continued_state["revision"],
        "confirmation_verification": duplicate["allowed"],
    })

    expectations = [
        ("baseline_delivery", "code", "OK"),
        ("old_confirmation_invalidated", "status", "CONFIRMATION_INVALIDATED"),
        ("deliver_with_old_confirmation", "code", "CONFIRMATION_INVALIDATED"),
        ("old_confirmation_reuse", "code", "CONFIRMATION_REUSED"),
        ("user_reject", "code", "USER_REJECTED"),
        ("new_revision_continuation", "code", "OK"),
        ("duplicate_execution", "code", "DUPLICATE_DELIVERY"),
    ]
    mismatches = []
    for name, field, expected_value in expectations:
        item = next(item for item in scenarios if item["scenario"] == name)
        if item.get(field) != expected_value:
            mismatches.append({"scenario": name, "field": field,
                               "expected": expected_value,
                               "actual": item.get(field)})
    _publish_context(context, continued_state)
    return {
        "state": continued_state,
        "scenarios": scenarios,
        "mismatches": mismatches,
        "manifest": manifest,
        "manifest_sha256": manifest_sha,
        "out_dir": out_dir,
    }


def run_reject_demo(repo_root, fixture_root, kind, fail_engine, context):
    """Exercise a legitimate rejection.  ReplayRejection is raised on purpose."""
    engine = engine_for(repo_root, fixture_root, fail_engine)
    expected = engine.concept_expected()
    state, _ = start_concept(engine)
    _publish_context(context, state)
    if kind == "missing-parameters":
        _apply_parameters(state, engine, expected, "parameters-missing.json")
    elif kind == "out-of-range":
        _apply_parameters(state, engine, expected, "parameters-out-of-range.json")
    elif kind == "unknown-format":
        engine.inspect_drawing("unsupported.xyz")
    else:
        raise ReplayRejection("INVALID_INVOCATION",
                              "unknown rejection case: %r" % kind,
                              {"cases": ["missing-parameters", "out-of-range",
                                         "unknown-format"]})
    return state


def engine_for(repo_root, fixture_root, fail_engine):
    from ..engines.replay_stub import ReplayStubEngine
    return ReplayStubEngine(repo_root, fixture_root, fail=fail_engine)
