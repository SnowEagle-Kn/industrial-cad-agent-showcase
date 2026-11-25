# ADR 04 · Independent write and read checks

## Context

A writer knows what it intended to emit. Reusing its in-memory geometry or its write summary as verification can pass a broken file. A drawing can look plausible and still bind a dimension or repeated feature to the wrong object.

## Decision

The local design separates writer and reader. The writer emits its artifacts and manifest. The independent read side starts from the emitted file and a frozen intent record. It records what it observes and compares object relationships, dimensions, units, and view semantics where supported. Bind observations to the exact artifact bytes and retain failures with their evidence and scope.

## Counterexample and check

Swap the references of two repeated features while preserving counts and approximate shape. A count or preview can pass. Reading the actual associations against the declared intent should flag the mismatch. Other meaningful challenges include a changed unit, a displaced annotation, and an incomplete page. A file digest detects mutation once an expected digest is known. Inspecting meaning requires a separate observation.

## Consequences

The private design provides write/read separation at the engineering boundary. The public repository exposes the boundary and a verification report contract. It exercises fixture and delivered-byte readback using synthetic data, with engineering generation and measurement kept private.

[Verification layers](../../cad_agent_showcase/governance/verification_layers.py) · [Delivery contract](../../cad_agent_showcase/orchestration/delivery_bundle.py) · [Core port](../../cad_agent_showcase/ports/core_engine.py) · [Synthetic development media](../showcase/MEDIA.md)
