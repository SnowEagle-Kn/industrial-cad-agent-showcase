# Portability

The release is prepared for **source-first replay**: a GitHub source repository
and tag-matched source snapshot, with commands run from the source root. Keep
the package, `fixtures/` and `examples/` together. CPython 3.12 and the standard
library are sufficient for the replay commands and tests.

Distribution mode: `source-display-no-open-source-license`. Rights are reserved
except as provided by law, applicable platform terms or another explicit
agreement; GitHub public viewing and forking rights remain unaffected. See
[Current rights status](../LICENSE-PENDING.md).

## Platform evidence

| Environment | Available evidence | Declaration |
|---|---|---|
| Windows 11, CPython 3.12.15 | Original B3 self-check and dated 2026-11-11 local source-copy review: three commands and 26 tests passed | Historical local evidence for the original B3 bytes only |
| Local CPython 3.12.14 | The 2026-11-13 release plan records a new source-copy run of the original B3: three commands and 26 tests passed | Historical source-copy evidence, not a Git checkout or hosted CI result |
| Revised release commit, Windows | Exact-commit distribution and workflow evidence is not supplied by this documentation revision | Pending; no blanket checkout or CI pass claim |
| Linux, Python 3.12 | `ubuntu-latest` is a configured CI target; no real run evidence is supplied here | NOT_RUN; no Linux support claimed |
| macOS or other Python versions | No tested environment declared | Not tested; no support claim |
| Real GitHub Actions | A workflow configuration exists, not a completed run bound to this release commit | NOT_RUN in this documentation candidate |

The original B1/B2 baseline had 52 files and the original B3 had 58. The old
B3 review applies only to that historical tree. This release-closeout revision
changes documents, so it needs a new manifest and exact-object review rather
than a claim that the approved baseline remains wholly unchanged.

## Commands and test suite

From the source root:

```text
python -m cad_agent_showcase demo concept --replay
python -m cad_agent_showcase demo drawing --replay
python -m cad_agent_showcase demo confirmation-mutation --replay
python -m unittest discover -s tests -t .
```

The suite contains 26 tests. Both entries, confirmation mutation and the three
refusals must retain their outcomes in the exact-commit release checks. A
source-copy result is not sufficient evidence for all Git checkout settings.

## Git and CI limits found during release planning

- **CADPUB-01:** a clean Git checkout with `core.autocrlf=true` changed the
  byte-bound DXF fixtures and made drawing replay return
  `UNSUPPORTED_REPLAY_INPUT`. A passing ordinary directory copy did not cover
  this distribution failure. The revised release commit needs repository
  attributes that preserve fixture bytes, followed by clean checkout checks
  under both `core.autocrlf=true` and `false`. Fixture digest validation must
  remain intact; global Git settings need not be changed.
- **CADPUB-02:** an original Windows multiline CI step could hide an earlier
  failed command when a later command succeeded. The revised workflow must
  preserve each command's failure, with first-command and second-command
  failure evidence. Local shell checks are separate from actual hosted runs.

These are existing release-closeout findings. This document does not close
them or claim their fixes were independently accepted. The integrated commit's
own evidence must identify the fixture hashes, commands, exit codes, checkout
settings and real Windows/Linux runs before broader claims are made.

## Build artifacts and installation

`pyproject.toml` declares `setuptools>=68` as a build dependency and an empty
runtime dependency list. The source replay commands and tests do not require
setuptools. Metadata `requires-python = ">=3.12"` is not evidence that every
later Python version has been tested.

The old B3 wheel and sdist were built by a standard-library audit builder,
not setuptools. Its historical review ran the unpacked sdist and checked
wheel installation/import. The wheel omits `fixtures/` and `examples/`;
installation/import does not make it a standalone runnable demo distribution.

First release preparation therefore uses source only. Audit archives are not
formal Release attachments, and setuptools builds, project `pip install`, PyPI
compatibility, signatures and standalone wheel execution are not claimed.
GitHub's tag source zip/tar snapshots are distinct from extra Release assets.

## Network and external services

The replay package imports no network modules and the commands do not open
sockets. Historical network isolation checks were static import checks, not
an OS network sandbox experiment. Source download and GitHub Actions are
separate external operations; their configuration does not prove a successful
transfer, hosted run, publication or remote source replay.
