# Architecture

The public repository presents the governance, orchestration, and contracts derived from an 82-module, 30,588-line local industrial CAD system. Its roughly 5,000-line public spine executes control flow on fixed synthetic inputs. The local implementation contains a concept frontend, a parameter bridge with seven evidence states, and a drawing backend.

## Two entries, one workflow

```text
Concept brief  → shared facts → five candidates → blind review → selected concept
Drawing source → object record → supported conditions and unknowns → review
Both paths     → supplement → current revision → confirmation → replay delivery
```

The public drawing route reads the declared fixture and its associated records. The concept route uses fixed candidates and pre-generated views. Both identify unknowns explicitly and bind deliverables to the current input and confirmation. G1 checks engineering data before handover toward development drawing work. G2 requires a separate, revision-bound authorization event for the next gated step. The replay exercises these decisions using synthetic evidence. [Dual-entry skill](../skills/dual-input-cad-skill/SKILL.md) · [Concept workflow skill](../skills/wish-cad-frontend/SKILL.md)

## Modules

| Layer | Responsibility | Public entry points |
|---|---|---|
| Tier B · Source-derived governance | 25-state transitions, v1.1 blind projection and neutral evidence, seven-criteria interval scoring with 128 shared weight vertices, revision-bound invalidation | [State machine](../cad_agent_showcase/governance/state_machine.py), [anonymizer](../cad_agent_showcase/governance/anonymize.py), [scoring](../cad_agent_showcase/governance/scoring.py), [confirmation](../cad_agent_showcase/governance/confirm.py) |
| Tier B · Contracts | 12 Draft 2020-12 schemas, one runtime policy for carrier/projection rules, a 72-item checklist kept at `NOT_RUN` and checklist coverage verification | [Contracts](../contracts/), [runtime validation](../cad_agent_showcase/governance/schema_runtime.py), [checklist verifier](../contracts/verify_checklist.py) |
| Tier C · Orchestration | Gates, blind evaluation handoff, lifecycle bindings, and the delivery-bundle contract | [Gates](../cad_agent_showcase/orchestration/gating.py), [handoff](../cad_agent_showcase/orchestration/session_handoff.py), [lifecycle](../cad_agent_showcase/orchestration/lifecycle.py), [delivery](../cad_agent_showcase/orchestration/delivery_bundle.py) |
| Tier C · Boundary and replay | Seven capability operations, an explicit refusal contract, and a replay engine limited to digest-checked synthetic fixtures | [Port](../cad_agent_showcase/ports/core_engine.py), [replay adapter](../cad_agent_showcase/engines/replay_stub.py), [CLI](../cad_agent_showcase/cli.py) |
| Tier A · Private industrial core | Calibrated PDF/DXF source intake, engineering reasoning and parameter mapping, OCCT B-Rep construction and measurement, native drawing generation, independent readback, and scene rendering | Capability names and bounded development examples in the [public showcase](showcase/index.html) |

## Confirmation binding

A confirmation identifies a task, entry and revision with digests for the input, parameter evidence, assumptions, selected candidate, and delivery specification as applicable. Record timestamps separately from the content that determines validity. A material change creates a new revision and invalidates affected confirmations and downstream artifacts. A matching digest establishes byte or content identity at that boundary. Simulated evidence stays marked `replay_simulated`. [Revision and handoff decision](adr/05-revision-binding-and-handoff.md)

## Replay contract

1. The replay engine accepts the declared synthetic fixture IDs and expected digests. Unsupported replay inputs are refused with `UNSUPPORTED_REPLAY_INPUT`. Requests for private capabilities are refused with `CORE_CAPABILITY_HIDDEN_IN_PUBLIC_REPO`. Both are CLI exit `1` when returned as the command result.
2. The v1.1 handoff writes neutral references for allowed evidence. A map shared with the judging context exposes only the neutral identifiers and readable artifacts. Source mapping stays private. The media-location port handles binary format boundaries.
3. The delivery manifest binds files and their bytes to the replay revision. A successful readback can establish fixture and byte consistency. Engineering readback of CAD geometry and drawing semantics requires the private capabilities and engineering evidence described in [ADR 04](adr/04-independent-readback.md).
4. Outbox creation, transport send, consumer validation and ACK are separate. The public evaluation is a local replay of those roles. A live host receipt, fresh host context and actual user decision require evidence from that host.

The seven-operation [core port](../cad_agent_showcase/ports/core_engine.py) covers drawing inspection, a cognition gate, the parameter bridge, B-Rep construction and measurement, concept rendering, sheet output and verification, and binary evidence inspection. The public adapter has no live implementation for arbitrary inputs.

## Package layout

Run `python -m cad_agent_showcase` from the source root. The [README](../README.md) lists all current commands. The original concept, drawing and confirmation-mutation replay commands and [demo wrappers](../demo/) remain available. The scope of the historical [v0.1.0 replay](https://github.com/SnowEagle-Kn/industrial-cad-agent-showcase/releases/tag/v0.1.0) is bound to that release.

A local run, a CI result, a delivery receipt, and engineering approval require their own evidence. All 72 engineering acceptance items are `NOT_RUN` in this repository. Public runs retain all four engineering approval and readiness flags as `false`.
