---
name: wish-cad-frontend
description: Public reference for coordinating isolated design seats, neutral evidence projection, blind judging, and revision-bound handoff.
---

# Multi-agent concept workflow

Use this reference to trace the coordination, design, judging and handoff contracts. The public eval command exercises these contracts using recorded synthetic inputs. Live host sessions and independent engineering approval require evidence from the corresponding host and responsible authority.

## Roles and evidence access

| Role | Reads | Produces |
|---|---|---|
| [P, coordinator](prompts/P-coordinator.md) | Source facts, brief, design receipts and private routing map | Neutral brief, frozen candidate set, projected review packet and handoff records |
| [D0–D4, isolated designers](prompts/D-designer.md) | The same brief and facts at one revision, plus seat-specific materials | A candidate, design reasoning, parameter provenance and verifiable supporting evidence |
| [J0, independent judge](prompts/J0-judge.md) | Neutral brief, anonymous candidates, referenced public evidence and a minimal return route | Comparability findings, criterion evidence, score sensitivity and decision handoff |
| [Skeptic](prompts/skeptic.md) | The assigned anonymous candidate and relevant neutral constraints | Concrete counterexamples tied to evidence and an observable check |

## Execution contract

1. Capture the request, constraints, expected delivery depth and source evidence in a shared neutral brief. Ask only for missing facts that affect the next decision. Preserve other unknowns and explain the assumptions and what would change if they were false.
2. Give each design seat the same frozen input and its assigned scope. Collect independently authored solutions. Compare substantive design principles, interfaces or load paths. Renaming a design does not create meaningful diversity.
3. Freeze the current candidate set and the evidence references. Path-aware projection removes identity material while preserving engineering content. The v1.1 handoff rewrites allowed evidence references into readable neutral paths. Keep source and author mappings on the coordination side.
4. Judge comparability before ranking. Verify the current evidence and common premises. Report conditional or unresolved alternatives with their original evidence. Record seven-criteria interval scores and the outcome at 128 common weight vertices, with an explicit counterexample where an ordering can flip.
5. Keep the final choice with the decision authority. Bind the selection and requested scope to the current revision. Track outbox, send, consume and ACK separately. A changed source, candidate or requested scope invalidates decisions that depended on the old revision.
6. Follow the [dual-entry workflow](../dual-input-cad-skill/SKILL.md) for later data and authorization gates. Treat delivery evidence and engineering approval as distinct records.

[Handoff implementation](../../cad_agent_showcase/orchestration/session_handoff.py) · [Candidate schema](../../contracts/cognition/candidate-cognition.schema.json) · [Carrier policy](../../contracts/cognition/carrier-and-anonymization-policy.json) · [Blind-review decision](../../docs/adr/02-blind-review-and-neutral-evidence.md)
