# ADR 05 · Revision-bound decisions and four handoff states

## Context

A user's earlier selection can persist in a conversation after the inputs change. A created outbox item can also appear in a log before any recipient sees it. Treating these as current confirmation and completed delivery creates two distinct false successes.

## Decision

Compare the decision's bound task, input, parameters, candidate and scope with the current revision before dependent work. Material changes invalidate affected confirmations and downstream evidence. Retain the old record with its previous binding. Bind separately obtained authorization evidence to the revision and requested step.

Record four handoff states with their own evidence.

| State | Evidence |
|---|---|
| Outbox | Versioned payload, bound recipient, and expected digest |
| Sent | Transport receipt for that payload and recipient |
| Consumed | Recipient validated the current identity and payload |
| Acknowledged | Matching recipient ACK tied to the consumed handoff |

## Counterexample and check

Change a geometry-driving value after confirmation. Reusing that confirmation must stop the dependent action. Then stage an outbox record and simulate a send without an ACK. The replay should preserve the pending state. A later mismatched ACK must not advance that record. Duplicate delivery can be identified using the same event and revision binding.

## Consequences

The distinction makes retries observable and exposes stale decisions. The public replay exercises the state logic using synthetic messages and `replay_simulated` decisions. A live user or host receipt requires actual transport and consumer evidence.

[Binding](../../cad_agent_showcase/governance/binding.py) · [Confirmation](../../cad_agent_showcase/governance/confirm.py) · [Handoff](../../cad_agent_showcase/orchestration/session_handoff.py) · [Gates](../../cad_agent_showcase/orchestration/gating.py)
