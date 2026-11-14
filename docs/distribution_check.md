# Source Distribution Checks

This document specifies the closeout checks at this rights revision's author
snapshot, dated 2026-11-14. It does not report an integrated commit as inspected,
reviewed or published. Current check receipts are external to the source tree
and must name their exact inputs.

## Local Surfaces

| Surface | Required check |
|---|---|
| Whitelist and source map | Every public path has an exact origin and SHA256; include actual new files such as `.gitattributes`. Reconcile the 58-file B3 baseline with every replacement/addition/removal. |
| Actual Git tree and index | Read the supplied real full commit ID and index. Require the selected commit to be HEAD and the indexed paths/modes/blob IDs to match it. Compare committed bytes with the frozen whitelist, rather than trusting ignored files or a directory copy. |
| Actual history | Scan all commits reachable from all local refs plus the selected commit, including historical file names/blobs, commit author/committer metadata and messages, ref names and annotated tag payloads. Earlier revisions may omit later additions but may not contain extra private paths. Reject shallow/incomplete or altered history views. |
| Local Git archive | Generate an in-memory source archive from that actual commit; inspect member names/types, duplicates and bytes, and require the exact selected-tree file set and hashes. Never extract untrusted archive paths. |
| Downloaded source snapshots | Independently inspect zip/tar members for the same commit/tag, remove at most one common source-root prefix and compare every file byte with the Git tree. Record archive SHA256. |
| Media | Scan PNG text chunks including compressed zTXt/iTXt and inspect SVG XML/text/references; retain the existing DEMO marker requirements. Unsupported media metadata needs separate review. |
| Additional Release assets | Planned set is empty: `[]`. Old wheels and hand-built sdists are internal audit evidence and are excluded. Any actual extra asset is a discrepancy requiring review. |

The local audit helper is an external preparation tool, not part of the public
runtime or an additional public file. The main integrator invokes it with the
actual repository, commit and frozen whitelist. Its interface is:

```text
python audit_public_tree.py --repo PUBLIC_REPO --commit FULL_COMMIT_ID --whitelist FROZEN_WHITELIST --output LOCAL_REPORT
python audit_public_tree.py --repo PUBLIC_REPO --commit FULL_COMMIT_ID --whitelist FROZEN_WHITELIST --archive SOURCE_ZIP --archive SOURCE_TAR --output LOCAL_REPORT
```

Directory-only inspection uses `--tree` instead of `--repo`/`--commit` and
explicitly leaves actual Git history `NOT_RUN`. Neither directory scans nor
B3's two materialized simulated revisions are actual release commits. A test of
the audit helper against a pre-existing development probe remains a helper test.

## Scan Rules And Reports

Reuse the reviewed B3 path/credential marker and drive-path rules, the PNG text
metadata and SVG DEMO checks. Scan file names as well as payloads. Add only the
necessary handling for real Git objects, compressed PNG text and source archive
membership. Reports identify rule, surface, file/object and line or metadata
field without reproducing matched values, excerpts, identities or credentials.

For each run retain the exact audit script/rules SHA256, whitelist SHA256, full
commit and tree IDs, scanned commit/blob counts, source archive hashes and
findings. A finding is a concrete suspicion, not a conclusion that the matched
content is a secret. Hash equality proves byte identity only. The source map
records declared authorship; a scan cannot decide publication rights or confirm
that an author identity is approved for public use.

R0 decision `CAD-PUBLIC-CLOSEOUT-20261113-R0-r1`, D02, dated 2026-11-14, has
selected source display with all rights reserved subject to law, applicable
platform terms and any separate express agreement. No standard open-source
license is granted; MIT and Apache-2.0 were not selected. Public-platform
viewing/forking rights still apply. No private-engine or real-material rights
are granted. This is the settled mode decision, not a scan result or acceptance
of final bytes. U09 accurate final wording, file-level origins/rights and the
integrated object still require review; original pending evidence is preserved.

## P4 And P5 Receipts

P4 consumes local actual-commit evidence, the CI owner's same-commit Git checkout
and failure-injection results, and independent review of the integrated RC.
It may produce `local_rc_reviewed` only within that scope. R0 D02 alone does
not accept the revised candidate or sign final publication.

P5 additionally inspects the real remote tree/history, Actions history/logs,
source downloads, README asset delivery and actual Release asset inventory.
Local `git archive` is not a substitute for a remote source download. CI logs
must be scanned even when the verification repository was temporarily private.
Remote observations must name the exact repository, commit/tag and run IDs.

```text
snapshot_date: 2026-11-14_UTC+08:00
rights_decision: CAD-PUBLIC-CLOSEOUT-20261113-R0-r1_D02
U09_license: mode_decided_by_R0_D02
U09_final_wording: pending_integration_and_exact_object_review
U10_integrated_local_git: NOT_RUN
U10_remote_surfaces: NOT_RUN
U11_windows_actions: NOT_RUN
U11_linux_actions: NOT_RUN
local_rc_reviewed: false
public_release_ready: false
deployed: false
```

These fields are a static author-time snapshot of this rights revision, not a
live status claim for a later final object. Subsequent accurate decisions,
commit/CI and publication receipts belong to the main integration record;
original author-time records remain unchanged. A local clean-scan result does
not establish public readiness.
