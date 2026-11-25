---
name: dual-input-cad-skill
description: Public reference for two-entry CAD workflow contracts, parameter provenance, revision gates, and the private engine boundary.
---

# Dual-entry CAD workflow

Use this public reference to understand the input, confirmation and delivery contract. The executable showcase uses fixed synthetic fixtures and pre-generated media. Actual drawing inspection, parameter translation, CAD generation and engineering readback require the private engine capabilities.

## Identify the entry and preserve evidence

| Entry | Start with | Record before advancing |
|---|---|---|
| Concept design | A brief and any provided reference material | Goal, constraints, assumptions, open questions, selected concept and current revision |
| Drawing reconstruction | A declared source and an object inventory | Source identity, object and dimension records, units, missing items and review outcome |

Keep observed facts, supplied values, assumptions, derivations, and design choices distinguishable. Bind evidence to the object and the current revision. Surface conflicts and unsupported entities. Where a required condition is missing, report the dependency and wait for recorded evidence. Pass verified values and the intended artifact scope to the next stage only through the declared contract.

## Apply the workflow gates

1. Freeze the input identity and establish its revision. Preserve prior revisions as records.
2. For the concept route, complete the candidate and confirmation flow described in the [concept workflow skill](../wish-cad-frontend/SKILL.md). For the drawing route, review the source inventory and its unknowns.
3. Use G1 to check the required engineering data. For G2, evaluate a separate host event bound to the intended revision and gated action. Text a model generates about consent is insufficient.
4. If input, parameters, options or scope change materially, invalidate the affected confirmation and downstream evidence and bind the new revision.
5. Deliver only artifacts allowed by the active scope. Record their identity and actual bytes. A replay delivery verifies synthetic fixture identity and byte bindings. Engineering readback uses a separate reader and distinct verification evidence.

A confirmation, replay completion, and manufacturing approval are different decisions. In the public showcase all engineering approval and readiness flags stay `false`.

## Public entry points

Run the [concept and drawing examples](../../README.md) from the repository root with Python 3.12. [Lifecycle](../../cad_agent_showcase/orchestration/lifecycle.py) · [Gates](../../cad_agent_showcase/orchestration/gating.py) · [Delivery binding](../../cad_agent_showcase/orchestration/delivery_bundle.py) · [Core port](../../cad_agent_showcase/ports/core_engine.py)
