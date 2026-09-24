# Lifecycle authority consolidation — bounded implementation packet

## Evidence and objective

Three consumer runs returned `current_phase: COMMIT` immediately and
`lifecycle_status: stub_status`; explicit complexity and domain inputs were lost.
Source confirms the root `intake_gateway.py` imports the durable workflow gateway
and then shadows it with a second placeholder session, pipeline, and HTTP handlers.

Consolidate to one durable authority. This is not a new orchestration framework.

## Bounded source scope

- `ai-stack/mcp-servers/hybrid-coordinator/intake_gateway.py`: compatibility facade
  only; re-export the durable workflow gateway without defining competing handlers.
- `ai-stack/mcp-servers/hybrid-coordinator/workflow/intake_gateway.py`: change only
  if a verified compatibility gap in the live `http_server_impl.py` init contract
  exists.
- `scripts/testing/test-intake-gateway.py`: replace stub-pipeline expectations with
  durable intake/status/advance/replay and explicit complexity/domain preservation.
- Phase-0 integration check and dashboard lifecycle indicator: ship in the same
  delivery sequence under the service-coverage contract.

## Acceptance

1. One `LifecycleSession` authority: `workflow/lifecycle_fsm.py`.
2. Root and workflow imports resolve the same route handlers and module state.
3. A new complex task preserves requested complexity/domain and begins at the
   requested/derived lifecycle phase; it does not auto-walk placeholder phases to
   COMMIT.
4. Status reads persisted session state; advance applies the durable FSM transition;
   missing sessions return typed 404; replay uses recorded trajectory.
5. Existing `http_server_impl.py` initialization and route registration remain
   compatible, with no duplicate routes or module instances.
6. Phase-0 exercises the integration path, and the dashboard exposes current
   lifecycle authority/state rather than a static label.

## Exclusions and ordering

No provider credentials, model/budget changes, collective timeout tuning, consumer
writes, or lifecycle data deletion. Land only after the Run-3 lossless-upgrade
corrective. Runtime restart/reload and consumer proof are activation gates, not
assumed by unit tests.
