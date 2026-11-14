# -*- coding: utf-8 -*-
"""Command line entry: three public replay commands plus a rejection demo.

Exit codes:
  0  OK
  1  REJECTED        legitimate business refusal (missing parameter, mutation, rejection)
  2  INPUT_ERROR     invalid invocation or fixture integrity problem
  3  ENGINE_FAILURE  the replay engine failed
"""

import argparse
import json
import os
import sys

from . import workflow
from .contracts import (CODE_ENGINE_FAILURE, CODE_INTERNAL_ERROR,
                        CODE_INVALID_INVOCATION, CODE_LIVE_MODE_UNAVAILABLE,
                        CODE_OK, CODE_SCENARIO_MISMATCH, EXIT_ENGINE_FAILURE,
                        EXIT_INPUT_ERROR, EXIT_OK, EXIT_REJECTED,
                        STATUS_ENGINE_FAILURE, STATUS_INPUT_ERROR, STATUS_OK,
                        STATUS_REJECTED, FixtureIntegrityError, ReplayEngineFailure,
                        ReplayRejection, make_envelope, validate_envelope)

REJECT_CASES = ("missing-parameters", "out-of-range", "unknown-format")


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_parser():
    parser = argparse.ArgumentParser(
        prog="cad_agent_showcase",
        description="Two-entry CAD agent replay demo (DEMO/REPLAY only).")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="run a replay demo")
    demo_sub = demo.add_subparsers(dest="demo", required=True)

    for name, help_text in (
            ("concept", "concept -> UNKNOWN -> parameters -> confirmation -> replay delivery"),
            ("drawing", "drawing -> missing conditions -> confirmation -> replay delivery"),
            ("confirmation-mutation", "version change / rejection / reuse / duplicate branches")):
        item = demo_sub.add_parser(name, help=help_text)
        _add_common(item)
    reject = demo_sub.add_parser("reject", help="run a legitimate rejection case")
    _add_common(reject)
    reject.add_argument("--case", required=True, choices=REJECT_CASES)
    return parser


def _add_common(parser):
    parser.add_argument("--replay", action="store_true",
                        help="required: run the fixed ReplayEngine (no live engine exists)")
    parser.add_argument("--out", default=None,
                        help="output directory (default: demo-output/<command> in cwd)")
    parser.add_argument("--fixtures", default=None,
                        help="fixture root (default: the fixtures/ directory of this package)")
    parser.add_argument("--fail-engine", action="store_true",
                        help="DEMO fault injection: make the replay engine fail (U06 check)")


def _write_envelope(envelope):
    text = json.dumps(envelope, ensure_ascii=False, sort_keys=True,
                      indent=2, allow_nan=False) + "\n"
    target = getattr(sys.stdout, "buffer", None)
    if target is not None:
        sys.stdout.flush()
        target.write(text.encode("utf-8"))
        target.flush()
    else:
        sys.stdout.write(text)
        sys.stdout.flush()


def _finalize(envelope, exit_code):
    problems = validate_envelope(envelope)
    if problems:
        raise RuntimeError("envelope contract violation: %r" % problems)
    _write_envelope(envelope)
    return exit_code


def _context_summary(context):
    state = context.get("state") or {}
    return {
        "task_id": context.get("task_id"),
        "entry": context.get("entry"),
        "revision": context.get("revision"),
        "input_digest": context.get("input_digest"),
        "state_trace": state.get("trace", []),
    }


def _state_data(state, manifest_sha, readback):
    data = {
        "state_trace": state.get("trace", []),
        "unknowns": state.get("unknowns", []),
        "missing_conditions": state.get("missing_conditions", []),
        "candidates": [
            {"candidate_id": item.get("candidate_id"),
             "label": item.get("label"),
             "summary": item.get("summary"),
             "assumptions": item.get("assumptions", [])}
            for item in state.get("candidates", [])
        ],
        "selected_candidate": state.get("selected_candidate"),
        "assumptions": state.get("assumptions", []),
        "parameters": state.get("parameters_summary", []),
        "confirmation": {
            "state": state.get("confirmation", {}).get("state"),
            "binding_sha256": state.get("confirmation", {}).get("binding_sha256"),
            "event_id": state.get("confirmation", {}).get("event", {}).get("event_id"),
            "evidence_type": state.get("confirmation", {}).get("identity_assurance"),
        },
        "delivery": {
            "manifest_sha256": manifest_sha,
            "artifacts": state.get("deliveries", [{}])[-1].get("artifacts", []),
        },
        "readback": readback,
        "artifact_verification": state.get("artifact_verification"),
    }
    if state.get("entry") == "MANUFACTURING_CAD":
        summary = state.get("object_summary") or {}
        data["drawing"] = {
            "file": state.get("file"),
            "entities": summary.get("entities"),
            "unknown_objects": [item["type"] for item in summary.get("unknown_entities", [])],
            "extents_mm": summary.get("extents_mm"),
        }
        data["mutation_check"] = state.get("mutation_check")
    return data


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    command_label = "demo %s" % args.demo
    context = {}
    out_dir = args.out or os.path.join(os.getcwd(), "demo-output", args.demo)
    fixtures = args.fixtures or os.path.join(_repo_root(), "fixtures")
    fail_engine = bool(args.fail_engine or os.environ.get("CAD_SHOWCASE_FAIL_ENGINE") == "1")

    if not args.replay:
        envelope = make_envelope(
            command=command_label, entry=None, task_id=None, revision=0,
            input_digest=None, status=STATUS_INPUT_ERROR,
            code=CODE_LIVE_MODE_UNAVAILABLE,
            errors=[{"code": CODE_LIVE_MODE_UNAVAILABLE,
                     "detail": "Only replay mode is public; pass --replay."}])
        _write_envelope(envelope)
        return EXIT_INPUT_ERROR

    try:
        if args.demo == "concept":
            state, manifest, manifest_sha, readback = workflow.run_concept_demo(
                _repo_root(), fixtures, out_dir, fail_engine, context)
            envelope = make_envelope(
                command=command_label, entry=state["entry"], task_id=state["task_id"],
                revision=state["revision"], input_digest=state["input_digest"],
                status=STATUS_OK, code=CODE_OK,
                artifacts=state["deliveries"][-1]["artifacts"],
                data=_state_data(state, manifest_sha, readback))
            return _finalize(envelope, EXIT_OK)
        if args.demo == "drawing":
            state, manifest, manifest_sha, readback = workflow.run_drawing_demo(
                _repo_root(), fixtures, out_dir, fail_engine, context)
            envelope = make_envelope(
                command=command_label, entry=state["entry"], task_id=state["task_id"],
                revision=state["revision"], input_digest=state["input_digest"],
                status=STATUS_OK, code=CODE_OK,
                artifacts=state["deliveries"][-1]["artifacts"],
                data=_state_data(state, manifest_sha, readback))
            return _finalize(envelope, EXIT_OK)
        if args.demo == "confirmation-mutation":
            result = workflow.run_confirmation_mutation_demo(
                _repo_root(), fixtures, out_dir, fail_engine, context)
            mismatches = result["mismatches"]
            status = STATUS_OK if not mismatches else STATUS_REJECTED
            code = CODE_OK if not mismatches else CODE_SCENARIO_MISMATCH
            envelope = make_envelope(
                command=command_label, entry=result["state"]["entry"],
                task_id=result["state"]["task_id"],
                revision=result["state"]["revision"],
                input_digest=result["state"]["input_digest"],
                status=status, code=code,
                artifacts=result["state"]["deliveries"][-1]["artifacts"],
                data={
                    "scenarios": result["scenarios"],
                    "mismatches": mismatches,
                    "state_trace": result["state"]["trace"],
                    "manifest_sha256": result["manifest_sha256"],
                })
            return _finalize(envelope, EXIT_OK if not mismatches else EXIT_REJECTED)
        if args.demo == "reject":
            workflow.run_reject_demo(_repo_root(), fixtures, args.case,
                                     fail_engine, context)
            # run_reject_demo always raises a ReplayRejection; reaching this line
            # means the fixture unexpectedly accepted the input.
            envelope = make_envelope(
                command=command_label, entry=context.get("entry"),
                task_id=context.get("task_id"), revision=context.get("revision"),
                input_digest=context.get("input_digest"),
                status=STATUS_REJECTED, code="NOT_REJECTED",
                errors=[{"code": "NOT_REJECTED",
                         "detail": "the rejection fixture was accepted unexpectedly"}])
            return _finalize(envelope, EXIT_REJECTED)
        raise ReplayRejection(CODE_INVALID_INVOCATION,
                              "unknown demo command: %r" % args.demo)
    except ReplayRejection as exc:
        envelope = make_envelope(
            command=command_label, entry=context.get("entry"),
            task_id=context.get("task_id"), revision=context.get("revision"),
            input_digest=context.get("input_digest"),
            status=STATUS_REJECTED, code=exc.code,
            errors=[{"code": exc.code, "detail": exc.detail}],
            data={"rejection": exc.data, "context": _context_summary(context)})
        _write_envelope(envelope)
        return EXIT_REJECTED
    except ReplayEngineFailure as exc:
        envelope = make_envelope(
            command=command_label, entry=context.get("entry"),
            task_id=context.get("task_id"), revision=context.get("revision"),
            input_digest=context.get("input_digest"),
            status=STATUS_ENGINE_FAILURE, code=CODE_ENGINE_FAILURE,
            errors=[{"code": CODE_ENGINE_FAILURE, "detail": exc.detail}],
            data={"context": _context_summary(context)})
        _write_envelope(envelope)
        return EXIT_ENGINE_FAILURE
    except FixtureIntegrityError as exc:
        envelope = make_envelope(
            command=command_label, entry=context.get("entry"),
            task_id=context.get("task_id"), revision=context.get("revision"),
            input_digest=context.get("input_digest"),
            status=STATUS_INPUT_ERROR, code=exc.code,
            errors=[{"code": exc.code, "detail": exc.detail}],
            data={"context": _context_summary(context)})
        _write_envelope(envelope)
        return EXIT_INPUT_ERROR
    except Exception as exc:  # no traceback on stdout; keep the envelope contract
        envelope = make_envelope(
            command=command_label, entry=context.get("entry"),
            task_id=context.get("task_id"), revision=context.get("revision"),
            input_digest=context.get("input_digest"),
            status=STATUS_INPUT_ERROR, code=CODE_INTERNAL_ERROR,
            errors=[{"code": CODE_INTERNAL_ERROR,
                     "detail": "%s: %s" % (type(exc).__name__, exc)}],
            data={"context": _context_summary(context)})
        _write_envelope(envelope)
        return EXIT_INPUT_ERROR

    problems = validate_envelope(envelope)
    if problems:
        raise RuntimeError("envelope contract violation: %r" % problems)
    _write_envelope(envelope)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
