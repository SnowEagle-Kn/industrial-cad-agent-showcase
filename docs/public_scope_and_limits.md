# Public scope and limits

This source candidate demonstrates a two-entry workflow in **DEMO / REPLAY**
mode. It consumes fixed synthetic inputs and copies existing pre-generated
preview images. It cannot generate manufacturing CAD from arbitrary drawings.

## Included public candidate content

- Routing, state transitions, task revisions, confirmation binding and
  invalidation, delivery gating and evidence writing.
- Public states, statuses, codes, CLI exit codes, envelopes, manifests and
  simulated confirmation event schemas.
- Two synthetic fixture groups, including their declared allowed digests.
- Existing DEMO SVG and PNG media produced with the Python standard library.
- The 26-test standard-library suite and source documentation.

"Public candidate" describes the proposed content boundary. Current mode is
`source-display-no-open-source-license`: public capability display with rights
reserved except as provided by law, applicable platform terms or another
explicit agreement. GitHub public viewing and forking rights remain unaffected.
See the current terms in the historically named
[LICENSE-PENDING.md](../LICENSE-PENDING.md).

## Outside the source candidate

- The real industrial CAD engine, OCP and real STEP / DXF / PDF processing.
- Complete private rules, feature registries, geometric checks, full prompt
  text, scoring details, internal contracts and whitelists.
- Real drawings, photos, machine data, customer data and project logs.
- Host session IDs, receipts, personal paths, credentials and deployment data.

The drawing entry contains only the public synthetic DXF subset inspector. It
recognizes LINE, CIRCLE and TEXT in that fixture and reports unknown SPLINE
objects. This is separate from any real CAD processing chain.

## Source-first demonstration

The prepared release format is a source repository and tag-matched source
snapshot. The three README commands run from the source root with `fixtures/`
and `examples/` present. Existing B3 wheel/sdist files are internal audit
artifacts, not promised standalone demo packages or release attachments.

The short demonstration consists of the two existing image groups, the three
commands and their JSON outcomes. No new renderer, GIF, video, interactive site,
private adapter or CAD feature is part of this closeout.

## What each output means

| Output | Meaning |
|---|---|
| Envelope JSON | One valid invocation's replay result, with status, code, limits and exit semantics; argparse usage errors may exit 2 without JSON. |
| `manifest.json` | DEMO/REPLAY manifest binding the task revision, digests and delivered bytes. |
| `parameters-summary.json` | Supplied values, declared provenance and `verified: false`; no measurement assurance. |
| `readback.json` | Checks of manifest fields, declared fixture summaries and media/document hashes; no geometric verification. |
| `events.json` | Simulated replay events, including accept/reject events. |
| `confirmation.json` | Revision binding and replay accept/reject record; no real user or host identity assurance. |
| `DELIVERY-CHECKLIST.md` | Human-readable delivery file list and limits. |
| SVG/PNG previews | Pre-generated illustrations copied into the delivery, not dimensioned CAD output. |

Every envelope keeps `manufacturing_release`, `engineering_approval`,
`production_approved` and `verified_truth` false. A successful hash readback
establishes byte consistency under the checked conditions, not correct geometry
or a measured match between the preview and supplied dimensions.

## Evidence and review boundaries

The original B3 local review dated 2026-11-11 recorded APPROVED only for the
original 58-file tree identified in the README. It disclosed same-model review
and prior B1/B2 context; it was neither fresh nor third-party independent
verification. Its approval does not cover this documentation revision.

The 26-test result from that review is historical local replay evidence. It
does not establish real GitHub Actions success, Linux support, exact-commit Git
distribution correctness, license approval or a completed public release.
See [Portability](portability.md).

Public replay checks remain separate from private-engine/C1 tests, real A/B
closure, A4/T18 and the original private 72/103/26 contracts. Neither their
completion nor their cancellation follows from a replay result. Business
effects, independent engineering acceptance and manufacturing approval remain
outside this demonstration.

## Unsupported interpretations

Replay results cannot establish general-purpose CAD generation, arbitrary
drawing support, geometric accuracy, authentic user confirmation, engineering
approval, production readiness or manufacturing release. They cannot substitute
for private-engine tests or acceptance records.

The current documentation candidate's exact-object review and real remote
validation remain pending. The source-display mode follows delegated decision
`CAD-PUBLIC-CLOSEOUT-20261113-R0-r1`, D02; it does not establish legal ownership
or technical release acceptance. No current CI pass or Linux support claim is
made.
