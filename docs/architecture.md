# Architecture

## Two entries, one workflow

```text
concept input ──> brief (unknowns preserved)
                 └─> concept candidates (assumptions)
                      └─> parameter supplement ──> new revision
                           └─> confirmation ──> replay deliverable + readback

drawing input ──> object summary (unknown entities listed)
                 └─> missing engineering conditions
                      └─> parameter supplement ──> new revision
                           └─> confirmation ──> replay deliverable + readback
```

The two entries share the same state vocabulary, binding rules and delivery
bundle. The `demo concept` and `demo drawing` commands run independently and
report separately.

## Modules

| Module | Responsibility |
|---|---|
| `contracts.py` | Public states, statuses, codes, exit codes and envelope builder |
| `routing.py` | Input kind/format routing; unknown input stops explicitly |
| `workflow.py` | State machine, revision handling, delivery gating |
| `confirmation.py` | Binding digest, accept/reject recording, invalidation, reuse detection |
| `evidence.py` | Delivery bundle and DEMO manifest writer |
| `engines/replay_engine.py` | Fixture digest checks, minimal DXF parser, replay media |
| `cli.py` | Three public commands, rejection demo, exit codes |
| `util.py` | Canonical JSON, SHA-256 and file helpers |

## Confirmation binding

A confirmation is a digest over the current task version:

```text
task_id, entry, revision, fixture_id,
input_digest, brief_digest, parameters_digest, assumptions_digest,
candidate_digest, deliverable_spec_digest, engine_mode
```

Any substantive change to these fields invalidates the confirmation. Timestamp
metadata is excluded. Delivery is allowed only when the attached confirmation's
digest equals the digest of the current binding. Reusing an older revision's
confirmation is reported as `CONFIRMATION_REUSED`, not silently accepted.

The demo's confirmation events are simulated replay events
(`evidence_type = replay_simulated`). They are not host receipts and the demo
never claims they are.

## Replay contract

- Every fixture declares the allowed input digests and parameter digests.
- Input outside the declared set is refused (`UNSUPPORTED_REPLAY_INPUT`); the
  engine never replays an old result for a changed input.
- The drawing fixture declares file hashes, entity counts, unknown entity types
  and extents; a mismatch is a fixture-integrity error, not a silent success.
- Deliverable media are pre-generated; the manifest binds their actual bytes.
- Readback checks manifest fields, declared fixture summaries and media hashes.
  It does not measure geometry.

## Package layout note

The plan sketches `src/cad_agent_showcase/`. This candidate puts the package at
the repository root instead so that `python -m cad_agent_showcase ...` runs from
a fresh copy with no install and no `PYTHONPATH`; the three README commands are
then literally executable. Module names and responsibilities are unchanged.
