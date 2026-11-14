# -*- coding: utf-8 -*-
"""Write the DEMO delivery bundle and its manifest.

Every artifact carries the DEMO/REPLAY watermark in its manifest entry, and
the manifest itself repeats the watermark and the false engineering flags.
"""

import os

from .contracts import (DEFAULT_LIMITS, EVIDENCE_REPLAY, MANIFEST_SCHEMA,
                        MODE_REPLAY, WATERMARK)
from .util import file_sha256, write_json

CHECKLIST_NAME = "DELIVERY-CHECKLIST.md"


def _write_text(path, text):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(text.encode("utf-8"))


def _document_entry(out_dir, filename, role):
    path = os.path.join(out_dir, filename)
    return {
        "role": role,
        "path": filename,
        "sha256": file_sha256(path),
        "bytes": os.path.getsize(path),
        "demo": True,
        "evidence_type": EVIDENCE_REPLAY,
    }


def write_delivery(out_dir, *, command, task_id, entry, revision, fixture_id,
                   input_digest, brief_digest, parameters_digest,
                   assumptions_digest, candidate_digest,
                   deliverable_spec_digest, confirmation, parameters_summary,
                   readback, events, deliverable, media_artifacts,
                   limits=None):
    os.makedirs(out_dir, exist_ok=True)
    limits = list(limits or DEFAULT_LIMITS)

    write_json(os.path.join(out_dir, "parameters-summary.json"), {
        "schema": "cad_agent_showcase.parameters_summary.v1",
        "demo": True,
        "replay": True,
        "watermark": WATERMARK,
        "parameters": parameters_summary,
        "note": "USER_INPUT here means supplied in the declared replay fixture narrative; "
                "it is not verified engineering data.",
    })
    write_json(os.path.join(out_dir, "readback.json"), {
        "schema": "cad_agent_showcase.readback.v1",
        "demo": True,
        "replay": True,
        "watermark": WATERMARK,
        "readback": readback,
        "limits": limits,
    })
    write_json(os.path.join(out_dir, "events.json"), {
        "schema": "cad_agent_showcase.event_log.v1",
        "demo": True,
        "replay": True,
        "watermark": WATERMARK,
        "events": events,
    })
    write_json(os.path.join(out_dir, "confirmation.json"), confirmation)

    checklist_lines = [
        WATERMARK,
        "",
        "Task: %s" % task_id,
        "Entry: %s" % entry,
        "Revision: %s" % revision,
        "Fixture: %s" % fixture_id,
        "Deliverable: %s" % deliverable["deliverable_id"],
        "Evidence type: %s (ReplayEngine)" % EVIDENCE_REPLAY,
        "",
        "Files:",
    ]
    for item in media_artifacts:
        checklist_lines.append("  - %s (%s) sha256=%s"
                               % (item["path"], item["role"], item["sha256"]))
    checklist_lines.extend([
        "  - parameters-summary.json",
        "  - readback.json",
        "  - events.json",
        "  - confirmation.json",
        "",
        "Limits:",
    ])
    checklist_lines.extend("  - %s" % line for line in limits)
    checklist_lines.append("")
    _write_text(os.path.join(out_dir, CHECKLIST_NAME), "\n".join(checklist_lines))

    documents = [
        _document_entry(out_dir, "parameters-summary.json", "parameters-summary"),
        _document_entry(out_dir, "readback.json", "readback"),
        _document_entry(out_dir, "events.json", "event-log"),
        _document_entry(out_dir, "confirmation.json", "confirmation"),
        _document_entry(out_dir, CHECKLIST_NAME, "delivery-checklist"),
    ]

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "schema_version": MANIFEST_SCHEMA,
        "demo": True,
        "replay": True,
        "watermark": WATERMARK,
        "mode": MODE_REPLAY,
        "engine": "ReplayEngine",
        "evidence_type": EVIDENCE_REPLAY,
        "command": command,
        "task_id": task_id,
        "entry": entry,
        "revision": revision,
        "fixture_id": fixture_id,
        "input_digest": input_digest,
        "brief_digest": brief_digest,
        "parameters_digest": parameters_digest,
        "assumptions_digest": assumptions_digest,
        "candidate_digest": candidate_digest,
        "deliverable_spec_digest": deliverable_spec_digest,
        "confirmation_binding_sha256": confirmation.get("binding_sha256"),
        "deliverable_id": deliverable["deliverable_id"],
        "artifacts": list(media_artifacts),
        "documents": documents,
        "readback": readback,
        "limits": limits,
        "manufacturing_release": False,
        "engineering_approval": False,
        "production_approved": False,
        "verified_truth": False,
    }
    write_json(os.path.join(out_dir, "manifest.json"), manifest)
    return manifest, file_sha256(os.path.join(out_dir, "manifest.json"))
