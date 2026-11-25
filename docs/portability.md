# Portability

Run the v0.2.0 candidate from a Git checkout or a complete source snapshot.
Keep the package, `fixtures/`, `examples/` and `contracts/` together. The
README commands use CPython 3.12 and the standard library. A Git checkout can
also test index-aware enumeration. Historical evidence below retains its
v0.1.0 commit bindings.

Distribution mode: `source-display-no-open-source-license`. Rights are reserved
except as provided by law, applicable platform terms or another explicit
agreement; GitHub public viewing and forking rights remain unaffected. See
[Current rights status](../LICENSE-PENDING.md).

## Public runtime and full local project

The public replay commands and tests use only CPython 3.12 and its standard
library. They call no live LLM or private CAD backend and create no new STEP /
DXF / PDF. They copy fixed synthetic media and emit replay evidence records.

The full local project implements five-seat concept-design orchestration,
supported drawing-object inventory and review, and a local OCP/OCCT backend for
profile extrusion, through circular holes, closed slots and repeated instances.
That backend generates real STEP, native DXF and PDF with file readback checks,
supported by implementation and bounded safe synthetic development artifacts.

The private CAD, drawing and rendering stack and its dependencies are not
distributed with the public replay package. The empty public runtime dependency
list is a package boundary; it does not describe the full local project as
lacking CAD capabilities. Local-stack installation, platform coverage and a
complete real-user/real-host chain require their own evidence. No such new
validation is supplied by this documentation update.

## Historical platform evidence

The rows below preserve the release-preparation snapshot from before the
2026-11-14 publication of `v0.1.0`. Their Pending / NOT_RUN declarations refer
to that snapshot; subsequent published replay evidence is recorded separately.

| Environment | Available evidence | Declaration |
|---|---|---|
| Windows 11, CPython 3.12.15 | Original B3 self-check and dated 2026-11-11 local source-copy review: three commands and 26 tests passed | Historical local evidence for the original B3 bytes only |
| Local CPython 3.12.14 | The 2026-11-13 release plan records a new source-copy run of the original B3: three commands and 26 tests passed | Historical source-copy evidence, not a Git checkout or hosted CI result |
| Revised release commit, Windows | Exact-commit distribution and workflow evidence is not supplied by this documentation revision | Pending; no blanket checkout or CI pass claim |
| Linux, Python 3.12 | `ubuntu-latest` is a configured CI target; no real run evidence is supplied here | NOT_RUN; no Linux support claimed |
| macOS or other Python versions | No tested environment declared | Not tested; no support claim |
| Real GitHub Actions | A workflow configuration exists, not a completed run bound to this release commit | NOT_RUN in this documentation candidate |

The original B1/B2 baseline had 52 files and the original B3 had 58. The old
B3 review applies only to that historical tree. The release-closeout revision
changed documents and required a new manifest and exact-object review rather
than a claim that the approved baseline remained wholly unchanged.

## Published replay baseline (2026-11-14)

The [v0.1.0 Release](https://github.com/SnowEagle-Kn/industrial-cad-agent-showcase/releases/tag/v0.1.0)
records publication for commit `25d24914633c38b3cd4d981af00c941a5db3a030`.
[Actions run 43555129426](https://github.com/SnowEagle-Kn/industrial-cad-agent-showcase/actions/runs/43555129426)
records successful Windows and Ubuntu replay/test jobs for that exact commit.
The historical tag, release state and preparation snapshots are retained.

The presentation revision dated 2026-11-14 is a separate documentation object.
Exact-object review, CI and remote validation are revision-specific and must be
checked in the records for the exact presentation commit. This document does
not itself certify review, CI or remote validation; old CI results do not certify
a new commit or the private CAD stack. macOS, other Python versions and complete
local-project deployment are not validated by those public replay jobs.

## Commands and test suite

From the source root:

```text
python -m cad_agent_showcase demo concept --replay
python -m cad_agent_showcase demo drawing --replay
python -m cad_agent_showcase demo confirmation-mutation --replay
python -m cad_agent_showcase demo eval --replay
python -m cad_agent_showcase demo gates --replay
python -m cad_agent_showcase verify-boundary
python contracts/verify_checklist.py
python -m unittest discover -s tests -t .
```

Release checks exercise both original entries, confirmation mutation, the
new blind evaluation and gate replays, and refusal of outside input. The
Windows and Ubuntu CI results are recorded against the exact candidate commit.

## Historical Git and CI limits found during release planning

The following failure modes and validation requirements are retained from the
release-planning experiments. They are not new test runs for this presentation.

- **CADPUB-01:** a clean Git checkout with `core.autocrlf=true` changed the
  byte-bound DXF fixtures and made drawing replay return
  `UNSUPPORTED_REPLAY_INPUT`. A passing ordinary directory copy did not cover
  this distribution failure. The release-planning requirement was to preserve
  fixture bytes with repository attributes, followed by clean checkout checks
  under both `core.autocrlf=true` and `false`. Fixture digest validation had to
  remain intact; global Git settings did not need to be changed.
- **CADPUB-02:** an original Windows multiline CI step could hide an earlier
  failed command when a later command succeeded. The release-planning
  requirement was that the revised workflow preserve each command's failure,
  with first-command and second-command failure evidence. Local shell checks
  are separate from actual hosted runs.

These are historical release-closeout findings and requirements, not newly
opened issues against the published commit
`25d24914633c38b3cd4d981af00c941a5db3a030`. Their disposition and any
independent acceptance must be read from that exact commit's records, including
fixture hashes, commands, exit codes, checkout settings and real Windows/Linux
runs. This presentation update neither reopens those findings nor transfers the
published baseline's dated results to its new bytes.

## Build artifacts and installation

`pyproject.toml` declares `setuptools>=68` as a build dependency and an empty
runtime dependency list. The source replay commands and tests do not require
setuptools. Metadata `requires-python = ">=3.12"` is not evidence that every
later Python version has been tested.

The old B3 wheel and sdist were built by a standard-library audit builder,
not setuptools. Its historical review ran the unpacked sdist and checked
wheel installation/import. The wheel omits `fixtures/` and `examples/`;
installation/import does not make it a standalone runnable demo distribution.

The public `v0.1.0` release uses source only. Audit archives are not
formal Release attachments, and setuptools builds, project `pip install`, PyPI
compatibility, signatures and standalone wheel execution are not claimed.
GitHub's tag source zip/tar snapshots are distinct from extra Release assets.

## Network and external services

The replay package imports no network modules and the commands do not open
sockets. Historical network isolation checks were static import checks, not
an OS network sandbox experiment. Source download and GitHub Actions are
separate external operations; their configuration does not prove a successful
transfer, hosted run, publication or remote source replay.
