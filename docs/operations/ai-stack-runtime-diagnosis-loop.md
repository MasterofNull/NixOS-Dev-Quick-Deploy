# AI Stack Runtime Diagnosis Loop
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-07

Purpose: reduce token burn and rebuild churn when system services, packages, drivers, confinement, or runtime acceleration regress.

## Scope

Use this loop before:

- rebuilding repeatedly
- patching upstream source
- widening AppArmor or systemd settings blindly
- assuming a host driver problem

The loop is designed to classify problems across four layers:

1. systemd unit state
2. package/runtime linkage
3. path-scoped confinement
4. functional runtime probes

## Primary Tool

```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
aq-context-card --card runtime-incident --level brief
aq-runtime-diagnose --preset llama-cpp
aq-runtime-diagnose --preset llama-cpp --json
python3 scripts/ai/aq-runtime-plan
```

Compatibility wrapper:

```bash
aq-llama-debug
```

Planner:

```bash
python3 scripts/ai/aq-runtime-plan
python3 scripts/ai/aq-runtime-plan --preset llama-cpp --preset apparmor
python3 scripts/ai/aq-runtime-act
python3 scripts/ai/aq-runtime-act --brief
python3 scripts/ai/aq-runtime-remediate
python3 scripts/ai/aq-runtime-remediate --execute
```

Fixture-driven planner validation:

```bash
python3 scripts/ai/aq-runtime-plan \
  --qa-fixture tests/fixtures/runtime-plan/qa-unhealthy.json \
  --diagnosis-fixture tests/fixtures/runtime-plan/diagnoses-unhealthy.json

scripts/testing/check-runtime-plan-catalog.sh
```

## Generic Workflow

1. Run a preset or service-specific diagnosis.
2. Run the planner when more than one service may be involved.
3. Read the classification first, not the full logs.
4. Only move to deeper evidence in the layer that failed.
5. Expand context only for the failing layer: `brief` card first, then `standard` or `deep` if still blocked.
6. Rebuild or patch only after the failing layer is clear.

## Current Preset

`llama-cpp`
- checks `llama-cpp.service`
- verifies Vulkan linkage
- compares active binary vs copied alias binary
- extracts focused runtime logs
- supports bounded smoke validation

`open-webui`
- checks service state and web health/root response

`hybrid-coordinator`
- checks health plus `/hints` responsiveness

`qdrant`
- checks base endpoint plus collections response

`apparmor`
- checks confinement service state plus loaded profile inventory

## Classification Meanings

`service_inactive`
- Fix unit startup first.

`package_linkage_mismatch`
- The expected runtime library is not linked.
- Fix the package or overlay before runtime debugging.

`health_probe_failed`
- Unit is up but its health endpoint fails.
- Inspect env, port binding, or service wiring next.

`path_scoped_confinement_likely`
- Copied alias binary succeeds while original path does not.
- Prioritize AppArmor or other path-based restrictions.

`runtime_probe_mismatch`
- Unit is up but the preset/runtime probe does not show expected success.
- Investigate runtime env, device enumeration, or package behavior.

`runtime_probe_active`
- Expected runtime path is active.
- Stop debugging and move to cleanup or benchmarking.

## Lessons Generalized From The Vulkan Incident

1. Do not jump from “service is slow” to “driver is broken”.
2. Compare original path vs copied alias path early.
3. Treat confinement as a first-class layer, not a postscript.
4. Separate package linkage from runtime behavior.
5. Prefer focused probes and classifications before full `nixos-rebuild switch`.

## How To Extend

Add a new preset to [aq-runtime-diagnose](../../scripts/ai/aq-runtime-diagnose) with:

- `SERVICE`
- `HEALTH_URL`
- `EXPECTED_LIB`
- `SUCCESS_PATTERN`
- `JOURNAL_PATTERN`
- `PROBE_CMD`
- optional `SMOKE_CMD`

That keeps the loop reusable for:

- GPU runtime issues
- AppArmor or confinement regressions
- package linkage failures
- broken health endpoints
- systemd/service wiring regressions

## QA Integration

Use:

```bash
aq-qa 2
aq-qa 3
```

Phase 2 is the runtime/package/confinement gate for the `llama-cpp` preset.

Phase 3 is the confinement/AppArmor gate.

## Recommended Default Incident Entry

```bash
aq-context-card --recommend "runtime incident on local ai stack" --level brief
aq-qa 0
aq-qa 2
aq-qa 3
python3 scripts/ai/aq-runtime-plan
```

That sequence is the preferred agentic entrypoint before source edits or rebuild loops.
Use [agent-context-progressive-disclosure.md](agent-context-progressive-disclosure.md) when you need the broader onboarding/token-discipline rules that sit around this incident loop.

Before invoking the remediation runner, inspect `approval_summary` from
`aq-runtime-plan`. It surfaces, per action:

- `action_id`
- `action_kind`
- `action_origin`
- `confidence`
- `provenance`
- `evidence_kind`
- `evidence_id`
- `evidence_refs`
- `highest_command_risk`
- `required_overrides`
- `contains_sudo_steps`
- `contains_unsafe_live_steps`

Then read `action_groups` in this order:

1. `observe_first`
2. `safe_to_run_now`
3. `requires_override`

That gives a practical execution posture instead of a flat list.

The planner now also emits `execution_order` with:

- `default_group_order`
- `non_empty_group_order`
- `recommended_group_order`

Use `recommended_group_order` when you want the planner to tell the runner which
bucket preference to use.

The planner now also emits `context_cards` so the next context load can stay
small and targeted. Read `recommended_card_order` first, then load only the
first card at its suggested level unless the current failing layer still needs
more detail.

If fewer actions appear than expected, inspect `suppressed_actions`. The planner
now collapses redundant lower-signal follow-ups for the same service/layer and
records:

- `action_id`
- `action_kind`
- `action_origin`
- `confidence`
- `provenance`
- `evidence_kind`
- `evidence_id`
- `suppression_reason`
- `suppression_key`
- `suppressed_by_index`
- `winner_summary`

Use `evidence_refs` to jump back to the source signal before acting. Current
reference patterns are lightweight:

- `qa:phase0`
- `action:<service>:<layer>`

Use `evidence_index` to resolve those refs without reconstructing the lookup by
hand. It maps each ref to the compact QA or diagnosis payload that justified
the planner output.

New consumers should prefer `evidence_kind` plus `evidence_id` over parsing ref
prefixes manually.

Prefer `action_kind` when you need a stable machine-facing action type. Current
planner values include:

- `phase0_stabilization`
- `healthy_cleanup`
- `confinement_followup`
- `diagnosis_primary`
- `diagnosis_secondary`

Prefer `action_id` when you need to correlate one action across `next_actions`,
`approval_summary`, `action_groups`, `suppressed_actions`, and remediation
selection without relying on list indices.

Prefer `action_origin` when you need the source context in one object instead of
combining multiple fields manually. Current shape is:

- `source`: `planner` or `catalog`
- `trigger`: planner or diagnosis action type
- `preset`: diagnosis preset when applicable
- `classification`: diagnosis classification when applicable
- `service`: target service when applicable
- `layer`: target layer when applicable

Use `provenance` to distinguish where an action came from:

- `planner_builtin_phase0` for the built-in phase-0 stabilization step
- `planner_builtin_healthy` for the built-in healthy-path cleanup step
- `planner_builtin_confinement` for the built-in confinement follow-up step
- `catalog_diagnosis` for actions derived from a concrete runtime diagnosis plus
  remediation catalog entry

If the selected next action is appropriate for the current host state, bridge from
planning to execution with:

```bash
python3 scripts/ai/aq-runtime-act
python3 scripts/ai/aq-runtime-act --brief
python3 scripts/ai/aq-runtime-act --execute
python3 scripts/ai/aq-runtime-remediate --list-actions
python3 scripts/ai/aq-runtime-remediate --action-group observe_first
python3 scripts/ai/aq-runtime-remediate --action-group safe_to_run_now
python3 scripts/ai/aq-runtime-remediate --prefer-group observe_first --prefer-group safe_to_run_now
python3 scripts/ai/aq-runtime-remediate --prefer-plan-order
python3 scripts/ai/aq-runtime-remediate
python3 scripts/ai/aq-runtime-remediate --action-index 1
python3 scripts/ai/aq-runtime-remediate --action-id healthy_cleanup
python3 scripts/ai/aq-runtime-remediate --execute
```

Use dry-run first. Only pass `--execute` after checking the selected action’s
commands, stable `action_id`, and rollback note.

`aq-runtime-remediate` now also returns a normalized top-level `selection`
object and includes `available_actions` in selection errors, so callers can
recover from stale indices or IDs without re-running a separate discovery step.

Use [aq-runtime-act](../../scripts/ai/aq-runtime-act)
when you want the shortest path:

1. build or load the plan
2. apply `execution_order.recommended_group_order`
3. preview or execute the selected action

The wrapper now also emits `selection_strategy`, so callers can tell whether the
result came from:

- `list_actions`
- `explicit_action_id`
- `explicit_action_group`
- `prefer_plan_order`

It also emits `selection_reason`, a compact explanation object that summarizes
why the wrapper selected the current action, without forcing consumers to derive
that from `selection_strategy`, `execution_order`, and the nested remediation
result separately.

Use `--brief` when you want that wrapper decision in a handoff-sized payload
instead of the full nested output.

For a fast human-facing read, use `incident_summary` first. It condenses the
current wrapper result to a small status/headline/selection block before you
drill into the full nested payload.

Use `--save-artifact <path>` when you want to keep the full wrapper payload for
later replay, debugging, or attachment to an incident note.

Saved wrapper payloads now include `artifact_meta`, so the artifact carries its
own tool identity, repo root, and creation timestamp.

Execution is bounded by:

- [runtime-remediation-policy.json](../../config/runtime-remediation-policy.json)

Only commands matching that allowlist may run under `--execute`. Everything
else remains preview-only and returns a policy block.

When one remediation needs mixed safety levels, use per-command entries in the
catalog rather than forcing the whole action into one risk bucket. The runner
honors metadata on individual commands and stops at the first blocked step.

## Remediation Catalog

The planner’s next-step behavior is driven by:

- [runtime-remediation-catalog.json](../../config/runtime-remediation-catalog.json)

Tune that catalog when you want to change:

- layer priority
- recommended commands
- per-command command entries
- relevant files to inspect
- rollback guidance
- action risk metadata
- sudo requirements
- live-session safety

Prefer updating the catalog before changing planner code.

## Regression Guard

The planner now supports fixture-driven tests so unhealthy classifications can be
validated without depending on live service failures.

Use:

```bash
scripts/testing/check-runtime-incident-tooling.sh
```

That check validates:

- catalog loading
- preset-specific remediation overrides
- action ordering under mixed failures
- healthy-path output

The diagnosis classification check validates:

- `service_inactive`
- `package_linkage_mismatch`
- `health_probe_failed`
- `path_scoped_confinement_likely`
- `runtime_probe_mismatch`
- `runtime_probe_active`
- `unknown`

The wrapper runs both:

- [check-runtime-plan-catalog.sh](../../scripts/testing/check-runtime-plan-catalog.sh)
- [check-runtime-diagnose-classifications.sh](../../scripts/testing/check-runtime-diagnose-classifications.sh)
- [check-runtime-loop-integration.sh](../../scripts/testing/check-runtime-loop-integration.sh)
- [check-runtime-remediation-runner.sh](../../scripts/testing/check-runtime-remediation-runner.sh)

The integration check validates:

- fixture-driven `aq-qa 2`
- fixture-driven `aq-qa 3`
- planner handoff after runtime/confinement failures

The remediation runner validates:

- dry-run by default
- explicit `--execute` gating
- command result capture from selected next actions
- policy blocking for disallowed command families
- metadata blocking for `requires_sudo` and `safe_in_live_session`
- per-command metadata gating within a single action

Blocked command results now include a machine-readable approval contract:

- `block_reason`
- `required_overrides`
- `rollback`

That allows agents to explain why a command stopped and what explicit override,
if any, would permit it.
- metadata blocking for `requires_sudo` and `safe_in_live_session`
