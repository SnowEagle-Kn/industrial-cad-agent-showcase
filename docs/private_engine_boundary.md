# Private engine boundary

The private engine is not published, in whole or in part. The public demo talks
to the same conceptual `EnginePort` shape so that a local, uncommitted adapter
can be wired later without exposing engine internals.

## Public port shape

| Method | Public input | Public output |
|---|---|---|
| `inspect_input` | declared input record | input digest + format/object summary or explicit refusal |
| `build_concept` | brief with unknowns | fixed concept candidates with assumptions |
| `resolve_parameters` | parameter payload | parameters digest or explicit refusal |
| `emit_deliverable` | current revision + delivery spec | media artifacts + manifest payload |
| `readback` | manifest + declared fixture data | checked fields, assumptions, unverified items |

The public envelope always contains `schema_version`, `mode`, `task_id`,
`revision`, `input_digest`, `status`, `code`, `artifacts`, `evidence_type` and
`limits`. In replay mode `mode=replay`, `evidence_type=replay` and
`engine=ReplayEngine`.

## Local private adapter (not part of this repository)

A private adapter may implement the same methods against a local engine. It must:

- read its configuration from the local machine, never hard-code private paths
  in public source or outputs;
- keep private engine code, rules and fixtures outside the public tree;
- return the same envelope/status/code semantics so public and private results
  stay comparable but separately recorded;
- label its evidence as private-engine evidence, not as replay evidence.

No adapter is included in this candidate; the private-engine demo and consumer
chain are `not_run` / `not_evaluated`.
