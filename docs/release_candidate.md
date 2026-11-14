# Source Release Candidate Details

## Scope And Inputs

`PUBLIC-SOURCE-RC-20261113` is an unpublished preparation label. Package
metadata stays at `0.1.0`; no tag or release has been created by this D3 revision.
The public payload consists of the two-entry replay workflow, public contracts,
confirmation binding/invalidation, synthetic fixtures, existing DEMO media,
tests and documentation.

| Input | Binding |
|---|---|
| Frozen B3 input | 58 files; file-manifest tree digest `8e0cb71bd06da83fc739350d30a96768f952908b60ddf71b7679f9590e540d1c` |
| Frozen B3 manifest SHA256 | `06e36858a24a7e05e1cba8fc82d781536de9e56539244ae3c7ff4d479d83e0bc` |
| Historical B3 review | 2026-11-11, local B3-RC only; reviewer retained B1/B2 context |
| Rights mode | `CAD-PUBLIC-CLOSEOUT-20261113-R0-r1`, D02: source display with rights reserved subject to law and applicable platform terms; mode decided, final wording pending integration/review |
| Closeout documentation | Newly integrated README/rights/platform and release documents require current review |
| Closeout distribution/CI | Explicit fixture newline policy and independent CLI steps require exact-commit checks |
| Actual file set, source map and hashes | External main-integrator whitelist and frozen manifest; pending integration at this author snapshot |
| Real Git commit/history | Created and recorded only by the main integrator; not bound by this snapshot |

The old B3 statement that 52 B1/B2 files were unchanged describes that historical
tree. It does not describe the closeout tree, which includes deliberate changes.
The new file set includes the actual `.gitattributes` supplied by the CI owner.
Any further addition, including a final rights file, must enter the explicit
file-level whitelist and source map before commit and review.

## Source-First Payload

First publication uses a source repository and the source snapshot bound to its
exact commit/tag. The source layout keeps `cad_agent_showcase`, `fixtures`,
`examples`, `tests`, documentation and the CI configuration together. Execute
the three commands in [the release notice](../RELEASE-CANDIDATE.md) from that root.

The old B3 wheel omits `fixtures`/`examples`. It and the old hand-built sdist
remain internal audit artifacts and must not be uploaded as Release assets.
No new wheel, package-index publication, installer or extra binary/media bundle
is part of this release. Additional Release assets are `[]`. Automatic GitHub
source zip/tar downloads are separate surfaces whose member sets and bytes must
be checked against the selected commit.

`pyproject.toml` declares `setuptools>=68` in its build system and an empty
runtime dependency list. Running the replay commands/tests from source does
not require setuptools. Setuptools builds, project pip installation and package
index compatibility are **not tested** by this closeout and are not advertised.

## Rights Mode And Final Wording

R0 D02, dated 2026-11-14, selected source display for public capability
demonstration, with all rights reserved subject to law, applicable platform
terms and any separate express agreement. No standard open-source license is
granted; MIT and Apache-2.0 were not selected. Public-platform viewing/forking
rights still apply. Private-engine and real-material rights are not granted.

The publication/rights mode is decided. U09 still requires accurate integrated
wording, file-level sources/rights and review of the final object. R0 recorded
no accepted candidate hash or commit and did not sign product technical
acceptance or final publication. The main integrator must synchronize the
actual rights documents, package metadata and these release documents before
the accurate-object review. Historical B3 and original pending drafts remain
unchanged as their own evidence.

## Required Evidence

| Area | Evidence before the corresponding state changes |
|---|---|
| Actual local source set | Selected full commit ID, actual tree/index, all reachable local history and tag metadata, exact whitelist hashes, archive comparison and media metadata scan |
| CADPUB-01 | Same integrated commit, clean Git checkouts with `core.autocrlf=true` and `false`; frozen DXF hashes, 26 tests, three commands, confirmation invalidation and three refusals in each |
| CADPUB-02 | Exact integrated workflow; first-command and second-command failure injections each fail their own step; later success cannot overwrite either failure |
| U09 | R0 D02 mode decision recorded; accurate final wording, per-file origins/rights and author metadata still require integration and exact-object review |
| P4 | Independent review of the accurate local RC and its evidence; no inherited approval |
| U10 remote / P5 | Actual repository/history, logs, source downloads and additional-asset inventory for the same commit/tag; `NOT_RUN` |
| U11 / P5 | Actual Windows and Linux Actions runs for the same commit, each test and command checked separately; both `NOT_RUN` |

Local script checks and local Windows shell experiments do not establish Actions
or Linux execution. Platform details belong to [portability](portability.md).
Scanning establishes only the stated checks over the inspected surfaces; every
reported suspicion needs disposition, and a clean scan does not grant rights.

## Behavior And Outstanding Boundaries

Invalid argparse usage such as an unknown `--case` exits 2 without a JSON
envelope. The documented refusal cases exit 1 with a JSON envelope. Runtime
errors use their existing error envelopes. No CLI behavior is changed here.

U01-U12 and CADPUB-01/02 retain their full original denominators. The U09 mode
decision is settled; accurate final wording and file-level review remain pending.
U10 remote surfaces and both U11 Actions arms remain `NOT_RUN`. Private C1,
A4/T18 and the private 72/103/26 contracts retain their separate states. Replay
output provides no manufacturing approval or real-world effectiveness evidence.

## Author-Time Preparation Status

```text
snapshot_date: 2026-11-14_UTC+08:00
implemented: true_for_D3_document_patches_only
local_check: pending_current_evidence
consumer_chain: not_evaluated_for_integrated_commit
independent_review: pending_for_this_rights_revision
effect_status: unknown
deployed: false
production_release_approved: false
local_rc_reviewed: false
public_release_ready: false
rights_decision: CAD-PUBLIC-CLOSEOUT-20261113-R0-r1_D02
U09_license: mode_decided_by_R0_D02
U09_final_wording: pending_integration_and_exact_object_review
U10_remote_surfaces: NOT_RUN
U11_windows_actions: NOT_RUN
U11_linux_actions: NOT_RUN
```

These fields are a static author-time snapshot of this rights revision. They
do not report the live state of a later final object or supersede later accurate
receipts. The main integrator records the actual commit, manifests, review and
deployment receipts outside the public source tree, then updates final wording
through the corresponding review. Original author-time records stay preserved.
