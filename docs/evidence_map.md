# Evidence map

This file maps observable demo behavior to the checks it supports. It is
evidence of *replay workflow behavior*, not of engineering correctness.

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

Every successful delivery writes:

```text
manifest.json
parameters-summary.json
readback.json
events.json
confirmation.json
DELIVERY-CHECKLIST.md
demo-preview files (SVG/PNG)
```
