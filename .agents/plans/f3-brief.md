# F3 Design Brief — CapabilityLease Contract + OTel Observability + Signed A2A Envelope

Source: factory-critique #3 + codex's deepest insight (the CapabilityLease) + antigravity's rollback/
event-broker + the paused live-observability work. Unify the ad-hoc capability layers, make
everything traceable, and make the antigravity node + write-execution safe. Design only.

## Design targets
1. **The `CapabilityLease` contract (unify the 5 auto-selection layers).** ONE canonical schema for
   every capability (tool, skill, plugin, MCP, RAG source, DB, cache, model, remote lane):
   `{id, version, source, owner, permissions, input_schema, output_schema, trust_tier, zero_trust_behavior,
   cost_class, observability_hooks, revocation_rule}`. **Deny-by-default** admission for external
   plugins/MCP/tools (via the existing capability-intake path). **Monotonic least-privilege** within a
   request (additions only via policy; elevation audited; zero_trust strips irreversible for the request).
   The Phase-0 `zero_trust` flag becomes ONE CapabilityLease behavior. Property tests: stripped-can't-
   reacquire, caller-false-can't-downgrade, stale-lease-can't-revive.
2. **OTel-mapped observability.** Map the audit/PULSE/matrix to OpenTelemetry semantic conventions: a
   SPAN per agent turn, tool calls as child spans; attributes = model, model_version, role, leased
   bundle, zero_trust, tokens_in/out, latency, lane. Where do spans emit (agent_executor, switchboard,
   coordinator)? How does the matrix READ them (a live selections panel) — the paused observability
   work, done OTel-native (Jaeger/Grafana-compatible) instead of bespoke.
3. **Signed A2A task envelope + heartbeat + output contract (antigravity node).** A watched folder
   alone is fragile. Design: a signed task envelope (round_id, task, deadline, idempotency_key,
   expected-output-path), a heartbeat (IDE agent liveness), and an output contract (the typed
   contribution). No API keys — signing uses a local harness key, NOT the IDE's OAuth.
4. **Automatic rollback (write-execution safety).** Before any write-access execution, snapshot the
   workspace (git stash / worktree isolation); revert instantly on validation/test failure. How does
   this integrate with the Slice-2 bwrap sandbox + the gates?

## Constraints
No API keys (OAuth/local-signing only). Declarative-only (Nix). Reuse existing: a2a_guard/action-policy/
budget (they become CapabilityLease enforcers), capability-intake, the audit trail, worktrees dir.
Study: object-capability security, macaroons (attenuated credentials), SPIFFE/SPIRE (workload identity),
TUF/Sigstore (provenance), Zanzibar (relationship-based authz), OpenTelemetry semantic conventions.

## Output
`.agents/plans/f3-capability-otel/<agent>.md`: the CapabilityLease schema + admission/least-privilege
rules, the OTel span model + emit/read points, the signed-envelope + heartbeat design, and the
rollback mechanism. Rank your top 3.
