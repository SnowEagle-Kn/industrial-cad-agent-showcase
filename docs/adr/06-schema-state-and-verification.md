# ADR 06 · Schema contracts, state and five verification layers

## Context

A well-shaped JSON record can claim an impossible transition or carry a true-looking approval field. Conversely, a genuine observation can be assigned to the wrong layer. A single summary status then hides the difference between a validated form, a checked workflow and an approved engineering result.

## Decision

Give each concern a concrete contract. The repository carries 12 Draft 2020-12 schemas for cognition and requirements records, one runtime policy for allowed carriers and projections, and a 25-state vocabulary for workflow transitions. Keep original error codes and report verification by layer, with the actual evidence and independence scope for each.

| Layer | Evidence being checked |
|---|---|
| L1 · Construction readback | What was actually constructed and read |
| L2 · Dimension, unit and object checks | Meaning of the current dimensions, units, objects and relevant assembly steps |
| L3 · Controlled parameter reconstruction | Rebuilding from the declared parameter domain |
| L4 · Target consumer parsing | What the intended consumer can open and interpret |
| L5 · Engineering approval | An approval from the responsible authority |

## Counterexample and check

Pass a structurally valid selection before the required transition, and a well-shaped consent flag without an independent host event. Validate shape first, then require the current state and event evidence. A checklist structure pass must leave all 72 items marked `NOT_RUN`. A successful check at an earlier layer supplies only its own evidence.

## Consequences

Each failure points to a contract, transition, or verification layer. The public replay demonstrates bounded evidence checks and leaves the engineering approval flags `false`. Any full engineering acceptance must be recorded separately.

[Contracts](../../contracts/) · [State machine](../../cad_agent_showcase/governance/state_machine.py) · [Verification layers](../../cad_agent_showcase/governance/verification_layers.py) · [Checklist](../../contracts/acceptance-checklist-72.json) · [Coverage verifier](../../contracts/verify_checklist.py)
