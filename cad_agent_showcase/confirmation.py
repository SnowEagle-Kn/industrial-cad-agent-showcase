# -*- coding: utf-8 -*-
"""Confirmation binding and invalidation for the public replay demo.

The public contract keeps the same shape as the private workflow: a
confirmation is bound to a digest of the task version, input, parameters and
candidate results, and any substantive change invalidates it.  In this demo
the confirmation event is a *simulated replay event* (``evidence_type`` is
``replay_simulated``); it is not a host receipt and is never claimed as one.
"""

import copy
import re

from .contracts import (CONFIRMATION_SCHEMA, EVIDENCE_SIMULATED, MODE_REPLAY,
                        STATE_CONFIRMATION_INVALIDATED, STATE_CONCEPT_ONLY_CLOSED,
                        STATE_DESIGN_ONLY_CLOSED, STATE_STOPPED, ENTRY_CONCEPT)
from .util import canonical_sha256

BINDING_FIELDS = (
    "task_id",
    "entry",
    "revision",
    "fixture_id",
    "input_digest",
    "brief_digest",
    "parameters_digest",
    "assumptions_digest",
    "candidate_digest",
    "deliverable_spec_digest",
    "engine_mode",
)

# Only these metadata keys may change without invalidating a confirmation.
EXCLUDED_METADATA = ("recorded_at", "confirmed_at", "invalidated_at")

ACTION_ACCEPT = "ACCEPT"
ACTION_REJECT = "REJECT"
ALL_ACTIONS = (ACTION_ACCEPT, ACTION_REJECT)

_ISO_LIKE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$")


def binding_from_state(state):
    """Build the public binding document for the current task version."""
    return {
        "task_id": state["task_id"],
        "entry": state["entry"],
        "revision": state["revision"],
        "fixture_id": state["fixture_id"],
        "input_digest": state["input_digest"],
        "brief_digest": state["brief_digest"],
        "parameters_digest": state["parameters_digest"],
        "assumptions_digest": state["assumptions_digest"],
        "candidate_digest": state["candidate_digest"],
        "deliverable_spec_digest": state["deliverable_spec_digest"],
        "engine_mode": MODE_REPLAY,
    }


def binding_subset(binding):
    subset = {field: binding[field] for field in BINDING_FIELDS if field in binding}
    return subset


def compute_binding_sha256(binding):
    return canonical_sha256(binding_subset(binding))


def _is_sha_like(value):
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value.lower())


def validate_event(event):
    """Return a list of problems with a simulated confirmation event."""
    problems = []
    if not isinstance(event, dict):
        return ["EVENT_NOT_OBJECT"]
    if not isinstance(event.get("event_id"), str) or not event.get("event_id"):
        problems.append("EVENT_ID_MISSING")
    if not isinstance(event.get("actor"), str) or not event.get("actor"):
        problems.append("ACTOR_MISSING")
    if event.get("action") not in ALL_ACTIONS:
        problems.append("ACTION_UNKNOWN")
    if not isinstance(event.get("observed_at"), str) or not _ISO_LIKE.match(
            event.get("observed_at", "").strip()):
        problems.append("OBSERVED_AT_NOT_ISO8601")
    if event.get("mode") != MODE_REPLAY:
        problems.append("EVENT_MODE_NOT_REPLAY")
    if event.get("evidence_type") != EVIDENCE_SIMULATED:
        problems.append("EVENT_EVIDENCE_NOT_SIMULATED")
    return problems


def make_event(event_id, action, observed_at, actor="demo-user",
               selected_candidate_id=None):
    event = {
        "schema": "cad_agent_showcase.confirmation_event.v1",
        "event_id": event_id,
        "actor": actor,
        "action": action,
        "observed_at": observed_at,
        "mode": MODE_REPLAY,
        "evidence_type": EVIDENCE_SIMULATED,
        "note": "Simulated replay event for the public demo; not a host user receipt.",
    }
    if selected_candidate_id is not None:
        event["selected_candidate_id"] = selected_candidate_id
    return event


def record_confirmation(binding, event):
    """Record accept/reject against a binding.  Never mutates the input."""
    missing = [field for field in BINDING_FIELDS if not binding.get(field)]
    if missing:
        return {
            "schema": CONFIRMATION_SCHEMA,
            "state": STATE_STOPPED,
            "recorded": False,
            "reason": "BINDING_FIELDS_MISSING",
            "missing_fields": missing,
            "binding": copy.deepcopy(binding),
            "event": copy.deepcopy(event),
            "identity_assurance": EVIDENCE_SIMULATED,
            "engineering_approval": False,
            "production_approved": False,
            "limits_acknowledged": True,
        }
    problems = validate_event(event)
    if problems:
        return {
            "schema": CONFIRMATION_SCHEMA,
            "state": STATE_STOPPED,
            "recorded": False,
            "reason": "EVENT_INVALID:" + ",".join(problems),
            "event_problems": problems,
            "binding": copy.deepcopy(binding),
            "event": copy.deepcopy(event),
            "identity_assurance": EVIDENCE_SIMULATED,
            "engineering_approval": False,
            "production_approved": False,
            "limits_acknowledged": True,
        }
    for field in BINDING_FIELDS:
        value = binding.get(field)
        if field.endswith("_digest") and not _is_sha_like(value):
            return {
                "schema": CONFIRMATION_SCHEMA,
                "state": STATE_STOPPED,
                "recorded": False,
                "reason": "BINDING_DIGEST_INVALID:%s" % field,
                "binding": copy.deepcopy(binding),
                "event": copy.deepcopy(event),
                "identity_assurance": EVIDENCE_SIMULATED,
                "engineering_approval": False,
                "production_approved": False,
                "limits_acknowledged": True,
            }
    if event.get("action") == ACTION_REJECT:
        closed = (STATE_CONCEPT_ONLY_CLOSED if binding.get("entry") == ENTRY_CONCEPT
                  else STATE_DESIGN_ONLY_CLOSED)
        return {
            "schema": CONFIRMATION_SCHEMA,
            "state": closed,
            "recorded": False,
            "reason": "USER_REJECTED",
            "binding": copy.deepcopy(binding),
            "binding_sha256": compute_binding_sha256(binding),
            "event": copy.deepcopy(event),
            "identity_assurance": EVIDENCE_SIMULATED,
            "continues_delivery": False,
            "engineering_approval": False,
            "production_approved": False,
            "limits_acknowledged": True,
        }
    stored = copy.deepcopy(binding)
    return {
        "schema": CONFIRMATION_SCHEMA,
        "state": "RECORDED",
        "recorded": True,
        "reason": None,
        "binding": stored,
        "binding_sha256": compute_binding_sha256(stored),
        "event": copy.deepcopy(event),
        "identity_assurance": EVIDENCE_SIMULATED,
        "engineering_approval": False,
        "production_approved": False,
        "limits_acknowledged": True,
    }


def invalidate(previous, current_binding):
    """Compare a recorded confirmation with the current binding.

    Returns a new document; ``previous`` is never modified.
    """
    if not isinstance(previous, dict):
        raise TypeError("previous must be a dict")
    original = copy.deepcopy(previous)
    if not isinstance(previous.get("binding"), dict):
        return {
            "schema": CONFIRMATION_SCHEMA,
            "state": "NOT_RECORDED",
            "invalidated": False,
            "reason": "NOTHING_TO_INVALIDATE",
            "previous_state": previous.get("state"),
            "continues_delivery": False,
            "re_confirmation_required": True,
        }
    stored = previous["binding"]
    changed = [field for field in BINDING_FIELDS
               if field in current_binding and stored.get(field) != current_binding.get(field)]
    previous_sha = compute_binding_sha256(stored)
    current_sha = compute_binding_sha256(current_binding)
    result = copy.deepcopy(previous)
    if changed or previous_sha != current_sha:
        if not changed:
            changed = ["binding_sha256"]
        result["state"] = STATE_CONFIRMATION_INVALIDATED
        result["invalidated"] = True
        result["invalidated_by"] = {
            "changed_fields": changed,
            "previous_binding_sha256": previous_sha,
            "current_binding_sha256": current_sha,
        }
        result["previous_event_id"] = previous.get("event", {}).get("event_id")
        result["continues_delivery"] = False
        result["re_confirmation_required"] = True
    else:
        result["state"] = "VALID"
        result["invalidated"] = False
        result["unchanged_metadata_only"] = any(
            previous.get(key) != current_binding.get(key)
            for key in EXCLUDED_METADATA if key in current_binding)
        result["binding_sha256"] = previous_sha
    if previous != original:
        raise RuntimeError("previous confirmation was modified")
    return result


def verify_for_delivery(state):
    """Check the confirmation attached to a state version."""
    record = state.get("confirmation")
    if not isinstance(record, dict):
        return {"allowed": False, "code": "CONFIRMATION_REQUIRED", "detail": None}
    current = binding_from_state(state)
    stored_sha = record.get("binding_sha256")
    current_sha = compute_binding_sha256(current)
    if stored_sha != current_sha:
        return {
            "allowed": False,
            "code": "CONFIRMATION_INVALIDATED",
            "detail": {
                "record_binding_sha256": stored_sha,
                "current_binding_sha256": current_sha,
                "record_revision": record.get("binding", {}).get("revision"),
                "current_revision": current["revision"],
            },
        }
    if record.get("state") != "RECORDED":
        return {"allowed": False, "code": "CONFIRMATION_REQUIRED",
                "detail": {"record_state": record.get("state")}}
    return {"allowed": True, "code": "OK", "detail": None}


def verify_reuse(record, current_binding):
    """Detect an attempt to reuse an older revision's confirmation."""
    if not isinstance(record, dict) or not isinstance(record.get("binding"), dict):
        return {"reused": False, "code": "NOT_A_CONFIRMATION"}
    current_sha = compute_binding_sha256(current_binding)
    reused = record.get("binding_sha256") != current_sha
    return {
        "reused": reused,
        "code": "CONFIRMATION_REUSED" if reused else "NOT_REUSED",
        "record_binding_sha256": record.get("binding_sha256"),
        "current_binding_sha256": current_sha,
        "record_revision": record.get("binding", {}).get("revision"),
        "current_revision": current_binding.get("revision"),
    }
