---
doc_type: reference
id: herdr-h2-operator-context--herdr-layout-planner
title: Herdr H2 Operator Context to Layout Planner Integration Contract
status: draft
date: 2026-08-09
parent_prd: herdr-agent-operations
contract_number: 2
contract_zero_sha256: 716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48
implementation_authority: false
runtime_authority: false
---

# Integration Contract #2: `aq.operator-context.v1` -> HERDR layout planner

## Purpose and boundary

This contract defines the one-way semantic boundary from canonical operator context to a derived HERDR
layout plan. The planner may decide how to present work; it may not decide what the work state is. Canonical
AQ state remains authoritative, and no planner outcome writes back into `aq.operator-context.v1`, a task
record, review receipt, lease, evidence record, or approval state.

This is design only. It grants no schema, resolver, adapter, planner, CLI, socket, pane, session, process,
deployment, commit, rebuild, or activation authority.

## Shared interface

### Inputs

- exactly one schema-valid `aq.operator-context.v1` object;
- a closed, versioned, non-authoritative presentation policy containing only bounded layout capabilities,
  visible-item budgets, accessibility preferences, and terminal-size category;
- optional prior layout-plan revision token for deterministic comparison, never as canonical truth.

Raw prompts, transcripts, terminal content, reasoning, secrets, paths, provider/session IDs, argv,
environment, action payloads, and unbounded identifiers are invalid inputs.

### Output

The planner returns one closed, deterministic `aq.herdr.layout-plan.v1` design object containing only:

- input schema version, projection revision, projection digest, and plan revision/digest;
- bounded mission-ribbon content references and freshness/unknown emphasis;
- tab/region/role assignments by bounded work reference and interaction mode;
- visible attention references in the frozen priority order, visible budget, and overflow count;
- parent-control guidance categories for `through_parent` work;
- accessibility mode, narrow-layout category, reduced-motion policy, and fallback summary references;
- explicit `unplaced`, `unsupported`, `degraded`, and `unknown` collections/count states.

The output contains no command, shell fragment, socket operation, pane-creation request, executable action,
or canonical-state transition. Layout execution/reconciliation is a separate, unauthorized slice.

### Normative closed output (`aq.herdr.layout-plan.v1`)

This is the complete contract-level closure (a later schema must encode it without adding fields). Every
object has `additionalProperties: false`; all `*_ref` values match `aqref:v1:` grammar; every list has a
policy-bound maximum of 64; and all free text is forbidden.

```text
{schema_version:"aq.herdr.layout-plan.v1", plan_revision:token, plan_digest:sha256,
 input:{schema_version:"aq.operator-context.v1", projection_revision:token, projection_digest:sha256},
 status:"ready|degraded|unavailable|unknown", reason:"none|input_invalid|input_stale|unsupported|overflow|unsafe_input|planner_failure",
 mission:{mission_ref:aqref|null, freshness:"fresh|stale|unknown|unavailable"},
 placements:[{work_ref:aqref, region:"ribbon|attention|work|evidence|learning|fallback|unplaced", interaction_mode:"direct|through_parent|read_only|unavailable|unknown", parent_ref:aqref|null}],
 attention:{refs:[aqref], visible_count:uint0..64, overflow_count:uint0..65535},
 accessibility:{mode:"standard|keyboard|screen_reader", viewport:"wide|narrow|unknown", motion:"full|reduced|unknown", fallback_refs:[aqref]},
 exceptions:{unplaced_refs:[aqref], unsupported_refs:[aqref], unknown_count:uint0..65535, degraded_count:uint0..65535}}
```

`plan_digest` binds canonical serialization of every field above, the planner revision, and the closed
policy digest. `status != ready` requires a non-`none` reason; `ready` requires `reason:none`. A work item
appears at most once in `placements`; every exception reference must be a valid input work/evidence reference.

### Direction

```text
aq.operator-context.v1 -> pure HERDR layout planner -> derived layout plan
```

There is no reverse semantic flow. HERDR observations flow separately through contract #5 as
`aq.herdr.presentation.v1`; they never enter canonical authority through this planner.

## Error behaviour

- Schema/version/digest mismatch: reject the input and emit planner unavailable/degraded; never infer a
  compatible default.
- Missing, stale, conflicting, or malformed operator context: preserve unknown/stale state in the plan and
  omit unsafe placement; never render it as empty healthy work.
- Unsupported role/tab/terminal capability: place the reference in bounded `unsupported`/`unplaced` state
  and retain mission/top-attention fallback semantics.
- Budget overflow: apply deterministic grouping/order and expose exact overflow state; never silently drop
  safety, approval/review, authority, freshness, or unknown signals.
- Unsafe content or identifier injection: reject/redact before planning and emit a bounded reason without
  echoing input.
- Planner failure: no prior plan may be represented as current; cached output is explicitly stale with its
  source projection revision/digest.

Unknown never becomes `0`, `false`, healthy, complete, empty success, or blank `--`.

## Auth and trust requirements

- `aq.operator-context.v1` is read-only input and must validate against the exact supported version.
- The planner is not a task, workflow, review, lease, evidence, approval, action, or HERDR runtime authority.
- Layout priority cannot raise authority or convert advisory `recommended_action`/`required_authority` labels
  into controls.
- Parent/child interaction semantics are preserved; `through_parent` never becomes direct input.
- Projection and plan digests/revisions remain visible for audit correlation. The planner has no presentation
  input and cannot compute, label, or prioritize cross-projection drift.
- Layout policy is allowlisted, closed, low-cardinality, and cannot contain user/model-provided commands.

## Acceptance vectors

1. Identical valid context and policy produce byte-identical layout-plan output and digest.
2. Every placed item retains its operator-context work/evidence reference and source digest.
3. Canonical state always wins over presentation preference; the planner never writes back.
4. Missing/malformed/stale inputs remain visible unknown/degraded, never healthy zero.
5. `through_parent` work renders parent guidance and never exposes direct control.
6. Attention order is safety/integrity, approval/review, blocked, stale/unknown, advisory; overflow is
   explicit and deterministic.
7. A narrow-terminal plan preserves mission, highest attention, freshness, authority, and unknown.
8. Keyboard-only, screen-reader, and reduced-motion semantics survive every supported plan variant.
9. Prompt/output/secret/path/identity/reasoning/argv/environment injection cannot cross the planner boundary.
10. Presentation comparison is deferred to contract #5's separately materialized comparator; this planner
    neither accepts presentation input nor synthesizes a mismatch/completion state.

## Explicit exclusions

- JSON Schema or resolver implementation;
- planner, layout executor, reconciliation, pane/session/socket, CLI, or runtime implementation;
- HERDR/TUI/web consumer changes;
- human-control or audited-action implementation;
- H1 baseline repair, acceptance, staging, commit, rebuild, or activation;
- H3 brokered agent PTYs and every agent launch/execution path.

## Sign-off

- [ ] Claude: PENDING — independent orchestrator review required.
- [x] Codex: AGREED — design only; one-way derived layout; no implementation/runtime authority.
- [ ] Owner: PENDING — freeze required before any later implementation request.

PREPARED_ONLY; independent review required; implementation gated on accepted H1 + separate authorization.
