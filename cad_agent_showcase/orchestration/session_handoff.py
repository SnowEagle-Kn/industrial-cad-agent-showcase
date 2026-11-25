"""Build a five-seat anonymous packet and read back simulated Outbox and ACK."""

import copy
import hashlib
import tempfile
from pathlib import Path

from ..contracts import (CODE_FIXTURE_INTEGRITY, ENGINEERING_FLAGS, FixtureIntegrityError)
from ..util import canonical_sha256, write_json

_SEATS = tuple("D%d" % index for index in range(5))
_OUTBOX = "OUTBOX_READY_NOT_SENT"
_SENT = "SEND_RECEIPT_RECORDED_ACK_PENDING"
_ACK = "P_ACK_CONCEPT_START_REQUESTED"
_PACKET = "JUDGE_PACKET_READY"


def _require(condition, detail):
    if not condition:
        raise FixtureIntegrityError(CODE_FIXTURE_INTEGRITY, detail)


def prepare_judge_packet(completions, *, assignments, run_id, revision,
                         source_root, public_root, engine):
    """Consume the five exact v1.1 records in the coordinator's frozen ID assignment."""
    from ..governance.anonymize import anonymize
    from ..governance.neutral_evidence import ANONYMOUS_IDS, prepare_neutral_evidence

    _require(set(completions) == set(_SEATS) and set(assignments) == set(_SEATS)
             and set(assignments.values()) == set(ANONYMOUS_IDS),
             "The judge packet requires five seats with distinct anonymous IDs.")
    root = Path(public_root).resolve()
    candidates = {}
    public_evidence = []
    for seat in _SEATS:
        candidate = completions[seat]
        anonymous_id = assignments[seat]
        _require(candidate.get("schema") == "wishcad.candidate.v1.1",
                 "The judge packet requires v1.1 candidates.")
        prepared = prepare_neutral_evidence(
            candidate, source_root, root, anonymous_id, run_id, revision,
            media_inspector=engine.inspect_evidence_media)
        result = anonymize(
            candidate, anonymous_id=anonymous_id, evidence_map=prepared["evidence_map"],
            source_root=source_root, public_root=root, media_inspector=engine.inspect_evidence_media)
        candidates[anonymous_id] = result["packet"]
        for entry in prepared["evidence_map"]["mappings"]:
            reference = entry["public_evidence"]
            evidence_path = root / reference["path"]
            _require(evidence_path.resolve().is_relative_to(root)
                     and hashlib.sha256(evidence_path.read_bytes()).hexdigest() == reference["sha256"],
                     "A public evidence reference failed its on-disk readback.")
            public_evidence.append(reference)
    return {"schema": "cad_agent_showcase.judge_packet.v1", "status": _PACKET,
            "candidates": candidates, "public_evidence": sorted(
                public_evidence, key=lambda reference: reference["path"])}


def _transition(previous, state):
    from ..governance.state_machine import evaluate

    result, code = evaluate({"previous_state": previous, "action_status": state})
    _require(code == 0 and result["transition"]["allowed"], "Invalid replay handoff transition.")


def prepare_outbox(packet, selection, *, coordinator, judge, run_id, revision):
    """Bind an independently recorded synthetic choice to this packet and route."""
    _require(selection.get("selected_candidate_id") in packet["candidates"]
             and selection.get("actor") == "user"
             and selection.get("action") == "select_candidate"
             and selection.get("evidence_type") == "replay_simulated"
             and selection.get("run_id") == run_id and selection.get("revision") == revision
             and bool(selection.get("event_id"))
             and packet.get("status") == _PACKET,
             "The saved replay selection does not bind the current anonymous packet.")
    _transition("实际用户选择", _OUTBOX)
    event = {"status": _OUTBOX, "run_id": run_id, "revision": revision,
             "selected_candidate_id": selection["selected_candidate_id"],
             "selection_sha256": canonical_sha256(selection),
             "judge_packet_sha256": canonical_sha256(packet), "sender_session_id": judge,
             "recipient_session_id": coordinator, "evidence_type": "replay_simulated"}
    return {**event, "event_id": canonical_sha256(event)[:24]}


def record_send(outbox, request, receipt, raw):
    """Advance only when the original simulated request and receipt agree."""
    body = {key: value for key, value in outbox.items() if key != "event_id"}
    _require(outbox.get("status") == _OUTBOX
             and outbox.get("event_id") == canonical_sha256(body)[:24],
             "The Outbox identity does not match its bound content.")
    identity = {"event_id": outbox["event_id"], "recipient_session_id": outbox["recipient_session_id"]}
    _require(all(request.get(key) == value and receipt.get(key) == value
                 and raw.get(key) == value for key, value in identity.items())
             and request.get("event_sha256") == canonical_sha256(outbox)
             and request.get("fixture") is True and raw.get("fixture") is True
             and receipt.get("success") is True and raw.get("success") is True
             and all(raw.get(key, outbox["recipient_session_id"]) == outbox["recipient_session_id"]
                     for key in ("to", "recipient"))
             and bool(receipt.get("message_id"))
             and raw.get("message_id") == receipt["message_id"],
             "The synthetic send receipt, original request or route does not match the Outbox.")
    _transition(_OUTBOX, _SENT)
    return {"status": _SENT, **identity, "message_id": receipt["message_id"],
            "event_sha256": canonical_sha256(outbox), "request_sha256": canonical_sha256(request),
            "receipt_sha256": canonical_sha256(receipt), "raw_receipt_sha256": canonical_sha256(raw),
            "delivery_authenticated": False, "evidence_type": "replay_simulated"}


def acknowledge(outbox, request, receipt, raw, send_record, *, consumer, packet, revision):
    """Re-read the complete send chain at the original recipient and revision."""
    verified_send = record_send(outbox, request, receipt, raw)
    _require(verified_send == send_record
             and consumer == send_record["recipient_session_id"]
             and revision == outbox["revision"]
             and canonical_sha256(packet) == outbox["judge_packet_sha256"],
             "The ACK does not bind the current anonymous packet, revision, send record and recipient.")
    _transition(_SENT, _ACK)
    return {"status": _ACK, "event_id": outbox["event_id"],
            "event_sha256": canonical_sha256(outbox), "send_sha256": canonical_sha256(send_record),
            "selected_candidate_id": outbox["selected_candidate_id"],
            "next_action": "START_CONCEPT_VISUALIZATION", "evidence_type": "replay_simulated",
            "backend_called": False, "delivery_authenticated": False, **ENGINEERING_FLAGS}


def _replay_handoff(packet, fixture):
    run_id, revision = fixture["run_id"], fixture["revision"]
    outbox = prepare_outbox(packet, fixture["selection"], coordinator=fixture["coordinator"],
                            judge=fixture["judge"], run_id=run_id, revision=revision)
    identity = {"event_id": outbox["event_id"], "recipient_session_id": fixture["coordinator"]}
    request = {**identity, "event_sha256": canonical_sha256(outbox), "fixture": True}
    receipt = {**identity, "success": True, "message_id": "REPLAY-MESSAGE-1"}
    raw = {**receipt, "fixture": True}
    sent = record_send(outbox, request, receipt, raw)
    ack = acknowledge(outbox, request, receipt, raw, sent, consumer=fixture["coordinator"],
                      packet=packet, revision=revision)
    return {"statuses": [outbox["status"], sent["status"], ack["status"]],
            "selected_candidate_id": ack["selected_candidate_id"],
            "delivery_authenticated": ack["delivery_authenticated"],
            "evidence_type": ack["evidence_type"]}


def run_evaluation_replay(engine, out_dir):
    """Run real v1.1 redaction and scoring over the five synthetic inputs."""
    from ..governance.scoring import GATES, perturb, score_spec

    fixture = engine.load_event("evaluation", "session.json")
    source_root = engine.fixture_root / "evaluation"
    source_bytes = engine.read_fixture_bytes("evaluation", "observation.json")
    evidence = {"path": "observation.json", "sha256": hashlib.sha256(source_bytes).hexdigest(),
                "locator": {"kind": "derived_record", "token": "record:OBS-1",
                            "view_id": None, "region": None}}
    candidates = {}
    for seat in _SEATS:
        candidate = copy.deepcopy(fixture["candidate"])
        candidate["candidate_id"] = seat
        candidate["role"] = seat
        candidate["author_session"] = fixture["designers"][seat]
        candidate["decision_records"][0]["source_refs"] = [evidence]
        candidate["evidence_refs"]["artifacts"] = [evidence]
        candidates[seat] = candidate
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "judge-packet"
    with tempfile.TemporaryDirectory(dir=out) as temporary:
        staging = Path(temporary) / "packet"
        packet = prepare_judge_packet(
            candidates, assignments=fixture["assignments"], run_id=fixture["run_id"],
            revision=fixture["revision"], source_root=source_root,
            public_root=staging, engine=engine)
        score_points = {anonymous_id: fixture["score_points"][anonymous_id]
                        for anonymous_id in packet["candidates"]}
        scores = score_spec({"candidates": {
            anonymous_id: {"gates": dict.fromkeys(GATES, "PASS_CONCEPT"),
                           "cells": {criterion: {"point": point} for criterion, point in points.items()}}
            for anonymous_id, points in score_points.items()
        }})
        sensitivity = perturb(score_points)
        handoff = _replay_handoff(packet, fixture)
        write_json(staging / "packet.json", packet)
        try:
            staging.rename(target)
        except OSError:
            # A retry succeeds only for the same complete anonymous packet.
            expected = {path.relative_to(staging): path.read_bytes()
                        for path in staging.rglob("*") if path.is_file()}
            _require(target.is_dir() and not target.is_symlink()
                     and {path.relative_to(target): path.read_bytes()
                          for path in target.rglob("*") if path.is_file()} == expected,
                     "A different anonymous packet occupies the selected output directory.")
    return {"candidate_schema": "wishcad.candidate.v1.1",
            "packet_path": "judge-packet/packet.json", "packet_sha256": canonical_sha256(packet),
            "anonymous_ids": sorted(packet["candidates"]), "public_evidence": packet["public_evidence"],
            "scoring": scores, "sensitivity": sensitivity, "outbox_ack": handoff, **ENGINEERING_FLAGS}
