# -*- coding: utf-8 -*-
"""Public contracts: states, codes, exit codes and the result envelope.

This module is the only place that defines the public vocabulary.  The demo
runs in replay mode only; every envelope says so.
"""

from types import MappingProxyType

ENVELOPE_SCHEMA = "cad_agent_showcase.envelope.v1"
MANIFEST_SCHEMA = "cad_agent_showcase.demo_manifest.v1"
EVENT_SCHEMA = "cad_agent_showcase.confirmation_event.v1"
CONFIRMATION_SCHEMA = "cad_agent_showcase.confirmation.v1"
CONTRACTS_SCHEMA = "cad_agent_showcase.contracts.v1"

MODE_REPLAY = "replay"
EVIDENCE_REPLAY = "replay"
EVIDENCE_SIMULATED = "replay_simulated"
ENGINE_NAME = "ReplayEngine"

ENTRY_CONCEPT = "CONCEPT_CAD"
ENTRY_DRAWING = "MANUFACTURING_CAD"

STATE_CONCEPT_DRAFT = "CONCEPT_DRAFT"
STATE_NEED_PARAMETERS = "NEED_PARAMETERS"
STATE_PARAMETERS_READY = "PARAMETERS_READY"
STATE_CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
STATE_CONFIRMED = "CONFIRMED"
STATE_REPLAY_DELIVERED = "REPLAY_DELIVERED"
STATE_DRAWING_INSPECTED = "DRAWING_INSPECTED"
STATE_CONFIRMATION_INVALIDATED = "CONFIRMATION_INVALIDATED"
STATE_CONCEPT_ONLY_CLOSED = "CONCEPT_ONLY_CLOSED"
STATE_DESIGN_ONLY_CLOSED = "DESIGN_ONLY_CLOSED"
STATE_STOPPED = "STOPPED"

KNOWN_STATES = (
    STATE_CONCEPT_DRAFT,
    STATE_NEED_PARAMETERS,
    STATE_PARAMETERS_READY,
    STATE_CONFIRMATION_REQUIRED,
    STATE_CONFIRMED,
    STATE_REPLAY_DELIVERED,
    STATE_DRAWING_INSPECTED,
    STATE_CONFIRMATION_INVALIDATED,
    STATE_CONCEPT_ONLY_CLOSED,
    STATE_DESIGN_ONLY_CLOSED,
    STATE_STOPPED,
)

STATUS_OK = "OK"
STATUS_REJECTED = "REJECTED"
STATUS_INPUT_ERROR = "INPUT_ERROR"
STATUS_ENGINE_FAILURE = "ENGINE_FAILURE"

EXIT_OK = 0
EXIT_REJECTED = 1
EXIT_INPUT_ERROR = 2
EXIT_ENGINE_FAILURE = 3

STATUS_EXIT_CODES = {
    STATUS_OK: EXIT_OK,
    STATUS_REJECTED: EXIT_REJECTED,
    STATUS_INPUT_ERROR: EXIT_INPUT_ERROR,
    STATUS_ENGINE_FAILURE: EXIT_ENGINE_FAILURE,
}

CODE_OK = "OK"
CODE_MISSING_PARAMETERS = "MISSING_PARAMETERS"
CODE_PARAMETER_OUT_OF_RANGE = "PARAMETER_OUT_OF_RANGE"
CODE_UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
CODE_UNSUPPORTED_REPLAY_INPUT = "UNSUPPORTED_REPLAY_INPUT"
CODE_CORE_CAPABILITY_HIDDEN = "CORE_CAPABILITY_HIDDEN_IN_PUBLIC_REPO"
CODE_DISCLOSURE_BOUNDARY = "DISCLOSURE_BOUNDARY_VIOLATION"
CODE_CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
CODE_CONFIRMATION_INVALIDATED = "CONFIRMATION_INVALIDATED"
CODE_CONFIRMATION_REUSED = "CONFIRMATION_REUSED"
CODE_DUPLICATE_DELIVERY = "DUPLICATE_DELIVERY"
CODE_USER_REJECTED = "USER_REJECTED"
CODE_ENGINE_FAILURE = "ENGINE_FAILURE"
CODE_LIVE_MODE_UNAVAILABLE = "LIVE_MODE_UNAVAILABLE"
CODE_INVALID_INVOCATION = "INVALID_INVOCATION"
CODE_FIXTURE_NOT_FOUND = "FIXTURE_NOT_FOUND"
CODE_FIXTURE_INTEGRITY = "FIXTURE_INTEGRITY"
CODE_ARTIFACT_MISSING = "ARTIFACT_MISSING"
CODE_ARTIFACT_HASH_MISMATCH = "ARTIFACT_HASH_MISMATCH"
CODE_READBACK_MISMATCH = "READBACK_MISMATCH"
CODE_SCENARIO_MISMATCH = "SCENARIO_MISMATCH"
CODE_NOT_REJECTED = "NOT_REJECTED"
CODE_INTERNAL_ERROR = "INTERNAL_ERROR"

KNOWN_CODES = (
    CODE_OK,
    CODE_MISSING_PARAMETERS,
    CODE_PARAMETER_OUT_OF_RANGE,
    CODE_UNSUPPORTED_FORMAT,
    CODE_UNSUPPORTED_REPLAY_INPUT,
    CODE_CORE_CAPABILITY_HIDDEN,
    CODE_DISCLOSURE_BOUNDARY,
    CODE_CONFIRMATION_REQUIRED,
    CODE_CONFIRMATION_INVALIDATED,
    CODE_CONFIRMATION_REUSED,
    CODE_DUPLICATE_DELIVERY,
    CODE_USER_REJECTED,
    CODE_ENGINE_FAILURE,
    CODE_LIVE_MODE_UNAVAILABLE,
    CODE_INVALID_INVOCATION,
    CODE_FIXTURE_NOT_FOUND,
    CODE_FIXTURE_INTEGRITY,
    CODE_ARTIFACT_MISSING,
    CODE_ARTIFACT_HASH_MISMATCH,
    CODE_READBACK_MISMATCH,
    CODE_SCENARIO_MISMATCH,
    CODE_NOT_REJECTED,
    CODE_INTERNAL_ERROR,
)

WATERMARK = "DEMO / REPLAY - SYNTHETIC FIXTURE - NOT FOR MANUFACTURING"
ENGINEERING_FLAGS = MappingProxyType({
    "verified_truth": False,
    "engineering_approval": False,
    "can_enter_p2": False,
    "production_approved": False,
})

DEFAULT_LIMITS = [
    "DEMO / REPLAY only: fixed synthetic fixtures, not a CAD engine.",
    "Not for manufacturing, production release, engineering approval or design verification.",
    "Readback checks declared fixture data, manifest fields and pre-generated demo media bytes; "
    "it does not measure a drawing or verify geometry.",
    "Confirmation events are simulated replay events, not real host user receipts.",
    "No private engine, no network access, no host agent and no third-party package is used.",
]


class ReplayRejection(Exception):
    """A legitimate business refusal; maps to REJECTED / exit code 1."""

    def __init__(self, code, detail, data=None):
        self.code = code
        self.detail = detail
        self.data = data or {}
        super().__init__("%s: %s" % (code, detail))


class ReplayEngineFailure(Exception):
    """The replay engine itself failed; maps to ENGINE_FAILURE / exit code 3."""

    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
        super().__init__("%s: %s" % (code, detail))


class FixtureIntegrityError(Exception):
    """Fixture or artifact integrity problem; maps to INPUT_ERROR / exit code 2."""

    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
        super().__init__("%s: %s" % (code, detail))


def make_envelope(*, command, entry, task_id, revision, input_digest,
                  status, code, artifacts=None, data=None, errors=None,
                  limits=None, mode=MODE_REPLAY, evidence_type=EVIDENCE_REPLAY):
    status = status if status in STATUS_EXIT_CODES else STATUS_INPUT_ERROR
    return {
        "schema_version": ENVELOPE_SCHEMA,
        "command": command,
        "mode": mode,
        "entry": entry,
        "task_id": task_id,
        "revision": revision,
        "input_digest": input_digest,
        "status": status,
        "code": code,
        "artifacts": list(artifacts or []),
        "evidence_type": evidence_type,
        "engine": ENGINE_NAME,
        "limits": list(limits or DEFAULT_LIMITS),
        "data": data or {},
        "errors": list(errors or []),
        "manufacturing_release": False,
        **ENGINEERING_FLAGS,
    }


def validate_envelope(envelope):
    """Return a list of contract problems; empty means the envelope is valid."""
    problems = []
    if not isinstance(envelope, dict):
        return ["ENVELOPE_NOT_OBJECT"]
    required = ("schema_version", "command", "mode", "entry", "task_id",
                "revision", "input_digest", "status", "code", "artifacts",
                "evidence_type", "engine", "limits", "manufacturing_release",
                "engineering_approval", "production_approved", "verified_truth")
    for key in required:
        if key not in envelope:
            problems.append("MISSING_%s" % key.upper())
    if envelope.get("schema_version") != ENVELOPE_SCHEMA:
        problems.append("SCHEMA_VERSION_MISMATCH")
    if envelope.get("mode") != MODE_REPLAY:
        problems.append("MODE_NOT_REPLAY")
    if envelope.get("engine") != ENGINE_NAME:
        problems.append("ENGINE_NOT_REPLAY_ENGINE")
    if envelope.get("evidence_type") != EVIDENCE_REPLAY:
        problems.append("EVIDENCE_TYPE_NOT_REPLAY")
    if envelope.get("status") not in STATUS_EXIT_CODES:
        problems.append("UNKNOWN_STATUS")
    if envelope.get("code") not in KNOWN_CODES:
        problems.append("UNKNOWN_CODE")
    flags = ("manufacturing_release", "engineering_approval", "production_approved", "verified_truth")
    if "can_enter_p2" in envelope:
        flags += ("can_enter_p2",)
    for flag in flags:
        if envelope.get(flag) is not False:
            problems.append("%s_NOT_FALSE" % flag.upper())
    return problems
