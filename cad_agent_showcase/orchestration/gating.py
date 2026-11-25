"""G1 minimum-data status and G2 independently bound consent in replay."""

import math

from ..contracts import ENGINEERING_FLAGS
from ..util import canonical_sha256

G1_REQUIRED_FIELDS = ("outer_profile", "thickness", "mounting_holes", "inner_rings")
G1_OPTIONAL_FIELDS = ("material_and_finish", "tolerance_accuracy")
G1_FIELDS = G1_REQUIRED_FIELDS + G1_OPTIONAL_FIELDS


def _gate(status, code, *, allowed=False, **fields):
    return {"status": status, "code": code, "allowed": allowed, **fields,
            **ENGINEERING_FLAGS}


def _provided(row):
    value = row.get("value")
    empty = value is None or value == [] or value == {}
    if isinstance(value, str):
        empty = not value.strip()
    return row.get("provided", True) is True and not empty


def g1_gate(decision, items):
    """Read six declared fields and advance only when the required four are present."""
    if decision == "DECLINED":
        return _gate("CONCEPT_ONLY_CLOSED", "USER_DECLINED_MIN_DATA",
                     watermark_required=True, blocking_missing=[], not_specified=[],
                     items=[{"id": field, "status": "DECLINED"} for field in G1_FIELDS])
    if decision != "PROVIDED" or not isinstance(items, list):
        return _gate("AWAITING_MIN_DATA", "MIN_DATASET_DECISION_INVALID")
    by_id = {}
    for row in items:
        if not isinstance(row, dict) or row.get("id") not in G1_FIELDS:
            return _gate("AWAITING_MIN_DATA", "MIN_DATASET_ID_UNKNOWN")
        field = row["id"]
        if field in by_id or type(row.get("provided", True)) is not bool:
            return _gate("AWAITING_MIN_DATA", "MIN_DATASET_ITEM_INVALID")
        by_id[field] = row
    result = []
    missing = []
    unspecified = []
    for field in G1_FIELDS:
        row = by_id.get(field, {})
        value = row.get("value")
        provided = _provided(row)
        if provided and field == "thickness" and (
                type(value) not in (float, int) or value <= 0
                or (type(value) is float and not math.isfinite(value))):
            return _gate("AWAITING_MIN_DATA", "MIN_DATASET_THICKNESS_INVALID")
        if provided:
            status = "PROVIDED"
            if field == "inner_rings" and isinstance(value, str) and value.strip().casefold() in (
                    "none", "无", "没有", "无内环"):
                status = "NONE_EXPLICIT"
        elif field in G1_REQUIRED_FIELDS:
            status = "NOT_PROVIDED"
            missing.append(field)
        else:
            status = "NOT_SPECIFIED"
            unspecified.append(field)
        result.append({"id": field, "status": status, "value": value if provided else None,
                       "unit": row.get("unit"), "source": row.get("source")})
    return _gate("AWAITING_MIN_DATA" if missing else "MIN_DATA_READY",
                 "MIN_DATASET_INCOMPLETE" if missing else "OK", allowed=not missing,
                 watermark_required=True, blocking_missing=missing,
                 not_specified=unspecified, items=result)


def g2_binding(run_id, revision, design_drawing_sha256, transfer_sha256):
    """Bind a prompt and later reply to the same revision, drawing and handoff."""
    fields = {"run_id": run_id, "revision": revision,
              "design_drawing_sha256": design_drawing_sha256,
              "transfer_sha256": transfer_sha256}
    return {**fields, "binding_sha256": canonical_sha256(fields)}


def g2_gate(request, current_binding, *, prompt_binding, engine):
    """Check separately saved replay receipt data, independent of the request."""
    from ..governance.confirm import ASSURANCE_HOST, classify_event

    awaiting = "AWAITING_MANUFACTURING_CONSENT"
    consent = request.get("consent") if isinstance(request, dict) else None
    if type(consent) is not bool:
        return _gate(awaiting, "CONSENT_INVALID")
    if consent is False:
        return _gate("DESIGN_ONLY_CLOSED", "USER_DECLINED_CONSENT")
    if prompt_binding != current_binding:
        return _gate(awaiting, "G2_CONSENT_INVALIDATED")
    ref = request.get("user_event_ref")
    saved_events = engine.load_event("gates", "saved-events.json")
    event = saved_events.get(ref) if isinstance(ref, str) and ref else None
    if not isinstance(event, dict):
        return _gate(awaiting, "G2_EVENT_MISSING")
    if (event.get("action") == "adopt" or event.get("value_role") == "DESIGN_CHOICE"
            or "feature_id" in event):
        return _gate(awaiting, "G2_ADOPTION_REUSE")
    required = {"actor": "user", "action": "manufacturing_consent", "consent": True,
                "run_id": current_binding["run_id"], "revision": current_binding["revision"],
                "binding_sha256": current_binding["binding_sha256"], "evidence_type": "replay_simulated"}
    assurance, _ = classify_event(event)
    if (any(type(event.get(key)) is not type(value) or event[key] != value
            for key, value in required.items()) or assurance != ASSURANCE_HOST):
        return _gate(awaiting, "G2_EVENT_BINDING")
    return _gate("MANUFACTURING_CONSENT_RECORDED", "OK", allowed=True, consent=True,
                 binding_sha256=current_binding["binding_sha256"],
                 identity_assurance="replay_simulated")


def run_gate_replay(engine):
    """Exercise complete, incomplete, stale and forged inputs on fixed replay data."""
    fixture = engine.load_event("gates", "scenarios.json")
    saved = engine.load_event("gates", "saved-events.json")
    binding = g2_binding(**fixture["binding"])
    revised = g2_binding(**{**fixture["binding"], "revision": binding["revision"] + 1})
    complete = fixture["g1_items"]
    cases = (
        ("g1_missing_outer_profile",
         g1_gate("PROVIDED", [row for row in complete if row["id"] != "outer_profile"]),
         "MIN_DATASET_INCOMPLETE"),
        ("g1_ready", g1_gate("PROVIDED", complete), "OK"),
        ("g1_declined", g1_gate("DECLINED", []), "USER_DECLINED_MIN_DATA"),
        ("g2_forged_consent", g2_gate({"consent": True, "user_event_ref": "unsaved",
                                     "event": next(iter(saved.values()))},
                                    binding, prompt_binding=binding, engine=engine),
         "G2_EVENT_MISSING"),
        ("g2_saved_replay_consent", g2_gate(fixture["request"], binding,
                                           prompt_binding=binding, engine=engine), "OK"),
        ("g2_revision_changed", g2_gate(fixture["request"], revised,
                                       prompt_binding=binding, engine=engine),
         "G2_CONSENT_INVALIDATED"),
        ("g2_declined", g2_gate({"consent": False}, binding,
                               prompt_binding=binding, engine=engine), "USER_DECLINED_CONSENT"),
    )
    results = [{"scenario": name, "expected_code": expected, **result}
               for name, result, expected in cases]
    return {"scenarios": results, "passed": all(
        case["code"] == case["expected_code"] for case in results)}
