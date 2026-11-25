# ADR 02 · Path-aware blind review and neutral evidence

## Context

Removing an author field leaves other identity channels in a candidate. An attachment path can name its author. Dropping that attachment can remove necessary proof. A term that also happens to resemble a seat label can be valid engineering notation, so a global text replacement can corrupt the claim.

## Decision

Isolate D0–D4 before submission. P freezes the candidates and keeps the author and source mappings on the coordination side. Project a declared allowlist into the judging context, using field and path rules for identity removal. For v1.1, rewrite evidence references to neutral locations and check that the destination is contained, non-symlinked, readable, and free of known identity material. Only the public references and evidence go to J0. JSON and text use the public evidence mapper. Binary media inspection crosses the typed core port.

## Counterexample and check

Give a synthetic candidate one legitimate engineering token and one evidence path carrying an author identifier. Preserve the engineering token, open the neutral evidence through the projected reference, and check that the original private source mapping is absent. A path that escapes the declared root or resolves through a symlink must fail. The same handoff can fail on unreadable evidence even when its candidate record passes shape validation.

## Consequences

J0 can assess a traceable claim while seeing less author and transport metadata. This projection limits one form of bias. Shared bad assumptions can still produce unanimous conclusions, so J0 checks the common evidence first.

[Anonymizer](../../cad_agent_showcase/governance/anonymize.py) · [Neutral evidence mapper](../../cad_agent_showcase/governance/neutral_evidence.py) · [Carrier policy](../../contracts/cognition/carrier-and-anonymization-policy.json) · [J0 contract](../../skills/wish-cad-frontend/prompts/J0-judge.md)
