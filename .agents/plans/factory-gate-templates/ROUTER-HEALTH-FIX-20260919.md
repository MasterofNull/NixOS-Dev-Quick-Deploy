# Router-health fix — recommend only healthy lanes (owner-directed)

Fixes the owner-reported defect: the router recommended `qwen` — a lane guaranteed
to fail (local qwen + gemini unusable, only codex + claude healthy), degrading all
delegation (ai_coordinator_delegate 49.2%/65 calls, 11.1% last hour).

## Root cause (multi-surface)
- `scripts/ai/lib/model_tiering.py::get_recommended_model()` hardcoded
  `qwen-3-35b`/`llama-3-8b` with no health check — but it is DEAD (0 callers; a
  known ACTIVATION-AUDIT duplicate). Fixed + reconciled anyway (health ladder + real
  config keys) so it is correct when F2.5 wires it.
- LIVE culprits (the surface the owner actually observed):
  - `knowledge/llm_router.py::route_task()` hardcoded `qwen-coder`/`llama-cpp-local`,
    no health check, no codex tier. Wired via POST /control/llm/route + /execute.
  - `extensions/model_coordinator.py::classify_and_route()` bare `qwen-coder`
    fallback, `is_available` never health-updated. Wired via POST /control/models/route.

## Fix
- Both live routers now pass their pick through a health filter that reuses
  aq-role-route's exact filesystem probe (`.agents/delegation/.<lane>-down` +
  `.codex-quota-cooldown`) — no new network probes, fail-safe to healthy if the
  probe can't load. An unhealthy lane is never returned; substitution walks the
  cheapest-eligible `local -> codex -> claude` ladder, logged. Added
  `AgentTier.CODEX` so codex is a real selectable fallback (its exact cost 0.0 =
  REMOTE_FREE bucket; reuses the existing `remote-coding` profile — no new profile).
  No-op (byte-identical) when nothing is down.
- Route request/response CONTRACTS unchanged (same keys; only a new possible
  `codex` tier/model VALUE). Verified by reading each handler + 10/10 new
  test_router_health.py + existing test_llm_router/advisor 13/13.

## Deferred / flagged
- Live activation needs an owner-gated coordinator service restart (systemd
  ai-hybrid-coordinator) — safe at rest until then. IMPLEMENTED_FOLLOWUP_REQUIRED.
- `GET /control/models` `list_available_models()` still reports every profile
  `is_available: true`; only routing DECISIONS are health-aware. Small separate
  follow-up (same `_profile_is_healthy` helper, different call site).
- Separate pre-existing (NOT this fix, confirmed via stash at HEAD): 7
  `test-agent-agnostic-router.py` failures from a stale
  `config/lane-eligibility-registry.json` (grant expiry/freshness); 5
  `test_ai_coordinator_model_awareness.py` profile-naming drift; 2
  `test_http_query_runtime_optimization.py` `logger` NameError in
  http_server_impl.py. Logged for follow-up; the lane-eligibility staleness is
  itself routing-health-relevant.
