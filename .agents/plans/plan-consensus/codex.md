# PLAN-CONSENSUS — codex

1. VERDICT: APPROVE-WITH-CHANGES — The keystone is implementable and correctly centered on a derived per-request flag, but the plan needs explicit precedence/edge-test requirements before coding so enforcement cannot be bypassed by route hints, forced profiles, or lease refreshes.

2. IMPLEMENTABLE as written? Mostly. Required changes before coding:
   - P0.1 must define the canonical internal context shape, e.g. `zero_trust` plus `zero_trust_kinds`, and must explicitly ignore caller-supplied `zero_trust=false`; caller-supplied `true` may only raise, never lower, derived state.
   - P0.2 must apply the privileged-tool filter to the base catalog before `_normalize_local_tools`, to explicit requested tools, and again inside `_resolve_tool_lease`; `lease_tools` must not be able to reacquire stripped tools.
   - P0.3 must check `zero_trust` before every remote-return branch in `_route_target`, including `forceProvider=remote`, `ROUTING_MODE=remote_only`, `x-ai-route: remote`, provider hints, remote model prefixes, intent routing, and `DEFAULT_PROVIDER=remote`.
   - `SWB_ZERO_TRUST_ENFORCE=off` should mean derive + audit only; tests must verify observe mode does not strip/block while enforce mode does.
   - P0.4 should specify redacted audit payload fields and failure-reason labeling for fail-closed derivation so ops can distinguish real findings from scanner failure.

3. RISKS:
   - Correctness: fail-closed is the right default, but only if exceptions, malformed scan results, missing scanner imports, and stale/unparseable findings all collapse to `zero_trust=true`; this should be one helper with narrow, unit-tested semantics. Per-request re-eval is acceptable if derived from the current request messages each time and never stored as a conversation/session latch.
   - Performance: clean-path scan cost is probably acceptable as a regex/content pass, but the plan should cap scanned text or reuse a bounded extraction helper so large-context requests do not pay unbounded full-payload traversal cost before routing.
   - Integration: stripping tools at `_resolve_tool_lease` alone is insufficient; the initial catalog and `_normalize_local_tools` path also need filtering. Blocking remote at `_route_target` can cover streaming and non-streaming because the route is chosen before both paths, but only if the guard runs before all early remote returns and explicit override branches.

4. TEST adequacy:
   - The keystone test combining secret -> tools stripped + remote blocked is the right acceptance spine, and fail-closed + mid-conversation tests cover the core PRD requirements.
   - Missing tests: observe-vs-enforce flag behavior; caller-supplied `zero_trust=false` cannot downgrade; caller-supplied `zero_trust=true` is honored; explicit `tools` lease cannot reacquire privileged tools; forced remote profile/header/model/default-provider cases are downgraded/refused under enforce; streaming request follows the same block; scanner exception emits audit with redacted kinds/failure reason; clean large request remains under the latency budget.

Sign-off: APPROVE-WITH-CHANGES. Make the above clarifications part of P0.1-P0.5 acceptance before implementation, then proceed with the keystone first.
