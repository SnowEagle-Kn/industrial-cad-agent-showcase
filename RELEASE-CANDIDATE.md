# Source release candidate

Candidate label: `PUBLIC-SOURCE-RC-20261113`. Package version: `0.1.0`.
This label describes preparation work; it is not a published Git tag.

**DEMO / REPLAY only.** The two entries replay synthetic fixtures and copy
pre-generated DEMO media. The private CAD engine is outside this repository.
The output carries no engineering, design-verification or manufacturing approval.

## Distribution

The first release uses a **source-first** route: the public source repository
and the source zip/tar snapshot for its exact reviewed commit/tag. Run from the
extracted repository root so that `cad_agent_showcase`, `fixtures`, `examples`
and `tests` stay together.

```text
python -m cad_agent_showcase demo concept --replay
python -m cad_agent_showcase demo drawing --replay
python -m cad_agent_showcase demo confirmation-mutation --replay
python -m unittest discover -s tests -t .
```

The old B3 wheel and hand-built sdist remain internal audit evidence. They are
excluded from the public tree and from additional Release assets. The old wheel
does not include the fixtures/examples needed to run these demos on its own.
No pip/PyPI installation or setuptools build compatibility is claimed.
Additional Release assets are an explicit empty set for this source-first plan;
GitHub's automatic source downloads are checked separately.

## Baseline And Review

The frozen B3 input has 58 files, tree digest
`8e0cb71bd06da83fc739350d30a96768f952908b60ddf71b7679f9590e540d1c`
and manifest SHA256
`06e36858a24a7e05e1cba8fc82d781536de9e56539244ae3c7ff4d479d83e0bc`.
That digest is a file-manifest digest, not a Git commit or Git tree identifier.

The B3 review dated 2026-11-11 accepted that historical local B3-RC only;
its reviewer had B1/B2 context and it was not fresh or third-party verification.
The historical author-time `not_run` field does not erase that review. Changes
in this closeout require review of the newly integrated bytes and real commit.
No prior signature covers this new candidate by inheritance.

## Rights Decision

Delegated decision `CAD-PUBLIC-CLOSEOUT-20261113-R0-r1`, D02, dated 2026-11-14,
selects source display for public capability demonstration, with all rights
reserved subject to law, applicable platform terms and any separate express
agreement. No standard open-source license is granted; MIT and Apache-2.0
were not selected. Applicable public-platform viewing/forking rights still
apply. This mode grants no rights to the private engine or real task materials.

The mode decision is settled. Accurate final rights wording across the
integrated candidate and its file-level U09 review remain pending. R0 did not
accept these revised bytes or a final commit, and did not sign final publication.

## Author-Time Preparation State

```text
snapshot_date: 2026-11-14_UTC+08:00
integration_commit: not_bound_by_this_snapshot
local_rc_reviewed: false
independent_review: pending_for_this_rights_revision
rights_decision: CAD-PUBLIC-CLOSEOUT-20261113-R0-r1_D02
U09_license: mode_decided_by_R0_D02
U09_final_wording: pending_integration_and_exact_object_review
U10_local_git_surfaces: NOT_RUN_for_integrated_commit
U10_remote_surfaces: NOT_RUN
U11_windows_actions: NOT_RUN
U11_linux_actions: NOT_RUN
ci_run: false
published_by_this_batch: false
uploaded_by_this_batch: false
deployed: false
public_release_ready: false
production_release_approved: false
manufacturing_release: false
```

These fields are a static author-time snapshot of this rights revision, not a
live account inventory or the status of a later integrated object. Original
author-time pending evidence remains preserved. Later review, commit, CI or
publication receipts apply only to their own accurate objects; the main
integrator records them separately and updates the final wording as reviewed.

P4 may accept only the exact local RC after its required local checks. U10
remote propagation and both real U11 Actions arms remain `NOT_RUN` until P5
receipts exist. The main integrator owns subsequent status changes and binds
them to the actual commit and review record.

See [release details](docs/release_candidate.md),
[distribution checks](docs/distribution_check.md),
[platform evidence](docs/portability.md) and
[rights and sources](RIGHTS-AND-SOURCES.md).
