# Learning attribution boundary

## Status

PLAN_READY_WITH_FOLLOWUPS — frozen 2026-11-11 after independent design scrutiny. The implementation below is limited to the existing tracker and its MCP ingress.

## Problem

`extensions/interaction_tracker.py` currently treats every non-`success`/`partial` outcome as an agent failure. A zero rating is likewise treated as negative feedback. It then updates context metrics for every outcome and can extract reusable patterns solely from a high score. Thus an infeasible task, cancelled request, service outage, or unclassified failure can punish the model or become learning material without evidence of agent fault.

## Goal

Preserve raw interaction observations while adding an explicit, compatible attribution boundary that permits learning-side reward, penalty, context, pattern, procedural-memory, and training effects only when their attribution is eligible.

## Scope and ownership

Owned planned code/tests:

- `ai-stack/mcp-servers/hybrid-coordinator/extensions/interaction_tracker.py`
- focused regression test file in `ai-stack/mcp-servers/hybrid-coordinator/tests/` (new only if no existing tracker test harness is suitable)
- `ai-stack/mcp-servers/hybrid-coordinator/extensions/mcp_handlers.py` only if the already-wired `track_interaction` / `update_outcome` ingress must forward the new optional field.

This PRD and `.agents/plans/learning-attribution/tracker.json` are planning artifacts only. No service, dependency, authentication, spool-integrity, dashboard, or unrelated learning-pipeline changes are included.

## Contract proposal

1. Store the caller-supplied attribution alongside the raw outcome/feedback observation as a normalized enum and a separate `attribution_supplied` boolean. Missing input is distinguishable from explicit `unknown`; both must never be inferred as agent fault.
2. Recognize exactly: `agent_error`, `infrastructure_error`, `infeasible`, `cancelled`, and `unknown`. Invalid values fail closed to `unknown` (or are rejected if the existing ingress validation convention already supports this without compatibility breakage).
3. Preserve legacy outcome labels (`success`, `partial`, `failure`) as descriptive task-result observations. They do not alone establish fault attribution.
4. One private sink-policy decision derives and persists `learning_eligible`:
   - positive updates are only missing-attribution legacy `success`/`partial`; explicit `unknown` and every explicit non-agent attribution are neutral even when the result says `success`/`partial`;
   - negative performance effects require stored, explicit `agent_error` plus a failure outcome or linked negative rating; a contradictory `success`/`partial` plus `agent_error` is neutral;
   - zero feedback is neutral and never a preference signal;
   - `infrastructure_error`, `infeasible`, `cancelled`, `unknown`, and missing failure attribution retain raw observation but cause no reward, penalty, context update, pattern extraction, procedural-memory write, or fine-tuning/training contribution.
5. Fine-tuning export requires `learning_eligible is True`; historical records that lack the field are excluded. Simple feedback retains all signs in its raw stores, but unlinked feedback produces no performance/reward or learning-memory write. A linked negative correction needs the explicit stored interaction attribution, not a caller claim.
5. Caller-declared attribution is unverified input, not provenance: this slice must not represent it as independently established or change authorization/trust boundaries.

The precise eligibility table and compatibility defaults require reviewer freeze. Recommended default: legacy callers that report a `success`/`partial` result remain eligible for positive learning; all failures with no explicit attribution are `unknown` and have no negative-learning effects.

## Existing wired path and affected sinks

- MCP ingress dispatches `track_interaction` and `update_outcome` in `extensions/mcp_handlers.py` (around lines 1609 and 1622).
- `track_interaction` persists the interaction, computes value, triggers pattern extraction, and writes successful procedural memory in `extensions/interaction_tracker.py` (around lines 308–445).
- `update_interaction_outcome` recomputes value and calls `update_context_metrics`, currently using outcome-derived success (around lines 374–475).
- `extract_patterns` is the direct pattern/procedural-learning sink (around lines 476–605); downstream fine-tuning consumes retained learning artifacts, so noneligible interactions must be blocked before those writes.

## Minimal implementation plan

1. Add one small private normalization/sink-policy decision in the existing tracker module; reuse it from scoring, context update, pattern extraction, performance, feedback memory, and training-facing paths. Do not add a standalone unused subsystem or dependency.
2. Extend only the existing MCP argument forwarding necessary to transport optional attribution through both initial tracking and outcome update paths.
3. Persist attribution as raw metadata with the observation, preserving existing fields and legacy callers.
4. Gate every identified learning sink on the shared decision before any state-changing learning write.
5. Add focused async/mocked regression coverage for the real MCP ingress and each sink.

## Acceptance and validation

- Explicit `agent_error` can produce a negative performance effect only for a failure outcome or linked negative rating; zero rating is neutral.
- `infrastructure_error`, `infeasible`, `cancelled`, and `unknown` preserve the observation but produce none of: reward/penalty feedback, context metric update, pattern extraction, procedural-memory write, or training contribution.
- A missing failure attribution behaves as `unknown`, never as `agent_error`.
- Missing-attribution `success`/`partial` callers retain compatible positive behavior; every explicitly attributed result is neutral unless it is an eligible `agent_error` negative case.
- Regression tests invoke both MCP handler ingress paths, then assert all affected mocked sinks, batch-export filtering, raw simple-feedback retention, and each frozen attribution combination.
- Run the focused pytest file plus Python syntax compilation for edited modules after implementation. Tier0 and commit remain orchestrator-owned/out of this planning slice.

## Security and non-goals

No new trust claim is made from caller input. The change does not verify attribution, redesign authentication, add dependencies, or address forged-spool provenance. Those require separate scope and authority.

## Frozen follow-ups and activation deferral

Runtime activation is deferred as of 2026-11-11: this isolated implementation slice cannot rebuild or exercise the running service. Parent/orchestrator must run the focused tests and a live MCP path after merge. Caller attribution remains unverified; authenticated provenance and forged-spool protection are separate follow-up work, not an implication of this field.
