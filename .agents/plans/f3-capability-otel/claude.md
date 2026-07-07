# claude — F3 Design: CapabilityLease + OTel + Signed A2A Envelope

## 1. The CapabilityLease contract (one abstraction for the 5 layers)
Every capability (tool, skill, plugin, MCP, RAG source, DB, cache, model, remote lane) is declared as a
lease:
```json
{ "id":"tool:reload-model", "version":"1", "source":"builtin|mcp|plugin", "owner":"switchboard",
  "permissions":["invoke"], "input_schema":{…}, "output_schema":{…},
  "trust_tier":"privileged|standard|readonly", "zero_trust_behavior":"strip|allow|readonly",
  "cost_class":"free|local|remote-metered", "observability_hooks":["otel:span"],
  "revocation_rule":"per-request|session|manual" }
```
- **Deny-by-default admission** for external plugins/MCP/tools via the existing capability-intake path
  (nothing is usable until it has a lease).
- **Monotonic least-privilege per request:** additions only via policy; elevation audited; a zero_trust
  strip is IRREVERSIBLE for that request. **The Phase-0 `zero_trust` flag becomes ONE lease behavior**
  (`zero_trust_behavior: strip` on privileged leases). The existing a2a_guard / action-policy /
  dispatch-budget become lease ENFORCERS, not separate gates.
- Property tests: stripped-can't-reacquire · caller-false-can't-downgrade · stale-lease-can't-revive.

## 2. OTel-mapped observability (the paused work, done right)
- **Span per agent turn**; tool calls = child spans. Attributes: model, model_version, role, leased
  bundle, zero_trust, cost_class, tokens_in/out, latency, lane, round_id.
- **Emit points:** `agent_executor` (turn + tool spans), `switchboard` (route + lease decision spans),
  `coordinator` (delegation span). Emit to a local OTLP collector OR a JSONL span log (no external dep).
- **Read:** the matrix gets a live "Selections" panel reading the span stream (the paused observability,
  now OTel-native → also Jaeger/Grafana-compatible). Selections (bundle/hot-swap/injectHints/zero_trust)
  become span ATTRIBUTES — one schema, inspectable everywhere.

## 3. Signed A2A envelope + heartbeat (antigravity node, no keys)
- The inbox drop becomes a **signed task envelope**: `{round_id, task, deadline, idempotency_key,
  expected_output, sig}` — signed with a LOCAL harness key (NOT the IDE OAuth; signing ≠ auth).
- **Heartbeat:** the IDE agent touches a liveness file; the round marks antigravity `pending-late` vs
  `dead` accordingly (feeds F1 quorum).
- **Output contract:** the typed F1 contribution (`antigravity.json` + `.md`), validated on ingest.

## 4. Automatic rollback (write-execution safety)
Before any write-access execution, snapshot via **`git worktree`** isolation (the harness already has a
worktrees dir) — the sub-agent (Slice-2 bwrap) writes into the worktree; on gate/test FAIL, discard the
worktree (instant revert); on pass, merge. Ties Slice-2 sandbox + F3 rollback + the gates into one safe
write path.

## Top 3
1. **CapabilityLease as the ONE abstraction** — subsumes zero_trust + all 5 auto-selection layers;
   deny-by-default, monotonic least-privilege, revocation. [object-capability / macaroons / Zanzibar]
2. **OTel span model** — turn/tool spans with capability attributes; the observability standard, not
   bespoke; the matrix reads spans. [OpenTelemetry semantic conventions]
3. **Signed envelope + heartbeat + worktree rollback** — makes the antigravity node + write-execution
   robust and revertible. [SPIFFE/TUF ideas; git worktree isolation]
