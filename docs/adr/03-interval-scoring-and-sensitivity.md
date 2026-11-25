# ADR 03 · Seven-criteria interval scoring and vertex sensitivity

## Context

A single weighted score can hide both missing evidence and how easily the order changes. Two concepts can swap places when the importance of a criterion changes. A shared score shift can also leave the displayed ranking unchanged while independent uncertainty would reverse it.

## Decision

Keep gate outcomes and eligibility alongside the score. For each comparable candidate, bind the evidence and reasons for seven criteria, giving the scores as intervals where uncertainty requires it. Enumerate the two endpoint choices on each of the seven weight axes, yielding `2^7 = 128` common weight vertices. For each pair, evaluate ranking sensitivity and keep the counterexample when an order can flip. Treat common scenarios and independent candidate-score uncertainty as distinct cases.

## Counterexample and check

One synthetic candidate has a higher nominal total, while the other's evidence is stronger on a criterion emphasized at an endpoint. The pairwise result should expose the possible flip. Reversing the lower and upper bounds should reject the record. An unresolved or ineligible candidate should keep its diagnostic record and stay outside the ranked result.

## Consequences

A robust result applies to the declared score and weight envelope. A conditional preference should name what could change the ordering. Assessing evidence or assigning a score remains separate from physical verification and user selection.

[Scoring](../../cad_agent_showcase/governance/scoring.py) · [Uncertainty](../../cad_agent_showcase/governance/uncertainty.py) · [J0 contract](../../skills/wish-cad-frontend/prompts/J0-judge.md)
