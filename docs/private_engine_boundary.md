# Private engine boundary

The public orchestration consumes [CoreEnginePort](../cad_agent_showcase/ports/core_engine.py).
The checkout supplies the fixed-fixture replay implementation. Geometry,
industrial drawing interpretation, rendering and manufacturing verification
stay inside the private system.

## Public port shape

| Method | Public input | Public output |
|---|---|---|
| `inspect_drawing_source` | Declared drawing fixture with its enrolled content digest | Fixed drawing evidence or refusal |
| `run_cognition_gate` | A replay scenario with declared evidence | Fixed gate evidence or refusal |
| `solve_parameter_bridge` | Declared parameters for the replay scenario | Recorded result or refusal |
| `construct_brep_and_measure` | A replay-domain request | Recorded evidence or refusal |
| `render_concept_views` | A replay-domain request | Pre-generated views or refusal |
| `emit_and_verify_sheets` | A replay-domain request | Fixed deliverables and byte-level readback or refusal |
| `inspect_evidence_media` | An evidence reference, content bytes and locator | Admission for the declared fixture or refusal |

The public envelope always contains `schema_version`, `mode`, `task_id`,
`revision`, `input_digest`, `status`, `code`, `artifacts`, `evidence_type` and
`limits`. Replay evidence is scoped to a synthetic fixture and its revision.

## Evidence scope

The drawing CLI rejects an external path at the replay boundary with exit code
1. The media port rejects an undeclared binary evidence file. Published
artifacts carry the replay identity and establish only the checks shown by the
checkout. The four engineering approval fields remain false.
