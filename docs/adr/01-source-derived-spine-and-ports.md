# ADR 01 · Source-derived spine and a core port

## Context

The first public package demonstrated two fixed workflows. Its compact replay implementation left most of the local Agent engineering out of view. Copying the whole local system would disclose calibrated drawing intake, feature construction, readback, and rendering. Deleting those dependencies from the original execution path would leave callers without a working implementation.

## Decision

Retain sanitized, source-derived governance as Tier B. Extract the lifecycle, handoff, gates, and delivery control flow as Tier C. Give all requests for geometry, drawing inspection, rendering, and specialized evidence parsing one typed boundary with seven operations. Bind the only distributed implementation, `ReplayStubEngine`, to declared synthetic fixtures and expected byte digests.

## Counterexample and check

A renamed or modified external DXF can look equivalent to the reference drawing. Refusal must depend on the fixture identity and declared bytes, so the engine cannot return the old result for an unrecognized input. Test an admitted synthetic fixture and an out-of-scope request in the same boundary probe. The probe reports success when its expected refusals occur.

## Consequences

Readers can inspect the same decision logic that governs the local system and exercise its public path without obtaining the private engine. Replay proves the behavior of the simulated path on the declared fixtures. The separate disclosure scan checks the distribution. The geometry and independent engineering evidence stay within the private capability boundary.

[Core port](../../cad_agent_showcase/ports/core_engine.py) · [Replay stub](../../cad_agent_showcase/engines/replay_stub.py) · [Disclosure test](../../tests/test_disclosure_boundary.py) · [Architecture](../architecture.md)
