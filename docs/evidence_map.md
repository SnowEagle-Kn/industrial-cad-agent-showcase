# Evidence map

The table below maps the public `v0.1.0` replay behavior to the checks it
supports. It is evidence of *replay workflow behavior*, not of engineering
correctness. Full local implementation and presentation evidence are separated
below.

| Behavior | How to observe it |
|---|---|
| Concept starts from UNKNOWNs | `demo concept` envelope `data.unknowns` and `state_trace` |
| Assumptions stay separate | `data.candidates[].assumptions`, `data.parameters[]` |
| Parameter supplement creates a new revision | `data.state_trace` revision 1 -> 2 |
| Confirmation is bound to the revision | `data.confirmation.binding_sha256` and `confirmation.json` |
| Version change invalidates the old confirmation | `demo confirmation-mutation` scenario `old_confirmation_invalidated` |
| Stale confirmation cannot deliver | scenario `deliver_with_old_confirmation` (`CONFIRMATION_INVALIDATED`) |
| Old confirmation reuse is detected | scenario `old_confirmation_reuse` (`CONFIRMATION_REUSED`) |
| User rejection closes without delivery | scenario `user_reject` (`CONCEPT_ONLY_CLOSED`) |
| New revision can continue | scenario `new_revision_continuation` (`REPLAY_DELIVERED`) |
| Duplicate execution is refused | scenario `duplicate_execution` (`DUPLICATE_DELIVERY`) |
| Drawing entry runs independently | `demo drawing` envelope `entry=MANUFACTURING_CAD` |
| Drawing byte change invalidates | `demo drawing` `data.mutation_check` |
| Missing/out-of-range/unknown format refused | `demo reject --case ...`, exit 1 with distinct codes |
| Runtime errors are separate | missing `--replay` -> exit 2; `--fail-engine` -> exit 3 |
| DEMO/REPLAY markers everywhere | README, manifest, checklist, SVG, PNG metadata |
| No engineering claim | manifest flags `manufacturing_release=false` etc. |

## Delivery files

Every successful replay delivery writes:

```text
manifest.json
parameters-summary.json
readback.json
events.json
confirmation.json
DELIVERY-CHECKLIST.md
demo-preview files (SVG/PNG)
```

`manifest.json` binds the delivered files and their expected SHA-256 values.
`readback.json` records declared fields, fixed-fixture summaries and media-check
summary flags. The CLI JSON `data.artifact_verification` contains the final
artifact hash recomputation results, file list and counts. These checks bind
bytes; they do not verify manufacturing geometry.

## Full local implementation evidence

| Local capability | Evidence basis and limit |
|---|---|
| Five-seat concept design and candidate evaluation | Orchestration, comparison and parameter-handling implementation; does not establish a current successful real-host multi-agent task. |
| Supported drawing reconstruction | DXF or calibrated vector PDF object inventory, interpretation, review and source-to-feature links, with bounded synthetic drawing-input development outputs. |
| Four-feature local CAD backend | Implementation for profile extrusion, through circular holes, closed slots and repeated instances, with real STEP, native DXF and PDF development artifacts and file readback. |
| Presentation screenshots | Safe synthetic development drawing images described in the [project overview](../README.md) and [static showcase](showcase/index.html); static evidence illustrations, not CAD produced by a replay command. |

These local capabilities are supported by code and bounded safe synthetic
artifacts. The local engine is not distributed in the public replay package.
The evidence does not establish an entire current real-user workflow, arbitrary
drawing support, external CAD acceptance or engineering/manufacturing approval.

## Dated release and presentation evidence

The [v0.1.0 Release](https://github.com/SnowEagle-Kn/industrial-cad-agent-showcase/releases/tag/v0.1.0),
published on 2026-11-14, and its
[Actions run 43555129426](https://github.com/SnowEagle-Kn/industrial-cad-agent-showcase/actions/runs/43555129426)
record public replay validation for commit
`25d24914633c38b3cd4d981af00c941a5db3a030`. The original B3 review dated
2026-11-11 is a separate historical object. Neither record supplies CI or
acceptance for a later documentation commit or the private local CAD chain.

The presentation update dated 2026-11-14, revision V1.0, describes the full
local project alongside the separately downloadable deterministic replay. It
adds documentation and static development-evidence illustrations, not a new
runtime or product tag. Exact-object review, CI and remote validation are
revision-specific and must be checked in the records for the exact presentation
commit. This document does not itself certify review, CI or remote validation.
Engineering, manufacturing and verified-truth flags remain false; no complete
current product chain is accepted by this evidence map.
