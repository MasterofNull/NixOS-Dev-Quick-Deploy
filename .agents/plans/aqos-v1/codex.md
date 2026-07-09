### 1. Scores
WS1: 9 — Contracts, canon compilation, and hot-reload config directly address D2/D4/D5/D6 and are the right zero-runtime-risk foundation, but the PRD should stage the "every config" acceptance target.
WS2: 8 — Event-log A2A with projections fixes the PULSE/RESUME and stale-registry failure classes, but exactly-once semantics over Redis Streams need sharper wording around idempotent effects.
WS3: 8 — Kernel extraction and capability manifests are necessary to break the coordinator god-service and activate dormant F2.5 work, but the coordinator "<15 files" acceptance risks becoming cosmetic unless paired with dependency boundaries.
WS4: 8 — One `aq` entrypoint is the correct answer to 131-binary sprawl, with usage-logged shims preserving migration safety.
WS5: 9 — End-to-end traces, metrics SSOT, and SLOs strongly match the harness principle that unmanaged/blank observability is a defect.
WS6: 7 — The console plan covers the right operator questions and CLI/UI parity, but frontend rewrite risk is high until OpenAPI contracts and tracing are stable.
WS7: 8 — Postgres, memory v2, lineage, backup, and retention close real data-plane gaps, but migration from current scattered stores needs an explicit dual-write/read-reconcile phase.
WS8: 9 — Eval-gated prompts/profiles/models and local capability-envelope KPIs preserve the product soul: using remote capability to improve local models.
WS9: 9 — CapabilityLease enforcement, egress allowlists, signing, SOPS lifecycle, and incident response make the zero-trust agent model testable instead of conventional.
WS10: 8 — Hermetic CI, test consolidation, releases, migrations, and docs productization are essential, but the 419-script triage needs prioritization rules to avoid becoming a sink.

### 2. Top 3 amendments
1. Add an explicit schema adoption ladder for WS1: "critical runtime configs first, then config/ inventory classes, then long-tail legacy files," with deferral records for files that cannot be schema-validated in the first pass; this keeps the 100% CI target while preventing Beat 1 from stalling on all 107 config files.
2. Define WS2 exactly-once as "at-least-once delivery plus idempotent handlers, idempotency keys, and monotonic state transitions"; Redis Streams cannot by itself guarantee exactly-once side effects, and the PRD should make the executable invariant clear.
3. Add WS3 dependency-boundary acceptance criteria: coordinator decomposition passes import-boundary checks and every re-homed capability declares contracts, owner, health probe, kill switch, and lease scope; file count alone will not prove a real kernel/userland split.

### 3. Risks the PRD underweights
The migration-state risk is larger than the PRD implies. WS2 makes PULSE.log and RESUME.json projections instead of primary stores, but current agents and rules still require direct file writes; the transition must define a compatibility period where direct writes are either rejected, bridged, or detected as drift, or mixed authority will recreate the clobber class under a new architecture.

The PRD underweights operator continuity during the CLI and console rewrites. WS4 and WS6 are product-critical, but the operator currently depends on many scripts, dashboard fields, and phase habits; usage telemetry, command aliases, and "old command to new command" diagnostics should be required so discoverability improves without breaking muscle memory.

The PRD underweights test-environment cost on APU-class hardware. WS10 calls for hermetic Nix devShell plus ephemeral services and WS5/WS8 add tracing/evals, but the plan should budget runtime, RAM, and service count per validation tier so CI quality does not exceed the local machine's practical envelope.

### 4. Slice claims
1.1: claim — Codex should own the typed `contracts/` scaffold and pydantic models because PLAN.md assigns structural typed code to Codex and WS1 depends on it.
1.2: claim — Config-loader architecture is a Codex-fit shared library slice and depends on 1.1 contracts.
1.3: pass — Switchboard live-system adoption is assigned to Claude and needs integration/live-test ownership.
1.4: pass — Canon compiler touches agent instruction generation and parity propagation, which PLAN.md assigns to Claude.
1.5: pass — Config inventory validation is explicitly a bounded local/Qwen pass after 1.1.
1.6: pass — Research on JSON-Schema export and NATS readiness is assigned to Antigravity.
2.1: claim — Redis Streams event log, signed envelopes, and idempotency keys match Codex's structural service role and depend on 1.1.
2.2: pass — PULSE/RESUME projector changes shared coordination surfaces and is assigned to Claude.
2.3: claim — Delegation registry v2 is a state-machine/service implementation aligned with Codex and depends on 2.1.
2.4: pass — Antigravity inbox bridge belongs to the IDE/OAuth lane.
2.5: pass — SOPS key wiring and privileged audit integration are assigned to Claude.
2.6: pass — Per-agent migration is explicitly all-lanes; Codex should participate later but not claim the whole slice now.
3.1: pass — F2.5 live APU wiring is assigned to Claude and can start early as an integration slice.
3.2: claim — Kernel package extraction for policy, leases, scheduler, routing, and registries is structural code assigned to Codex.
3.3: claim — Codex should co-own the capability manifest schema and review local's bounded re-home edits.
3.4: pass — `aq capability` lifecycle is assigned to Claude after 3.3.
3.5: pass — Remaining extension batches are local-led with Codex review, not a primary Codex claim.

### 5. Verdict
RATIFY-WITH-AMENDMENTS — The PRD is directionally correct and grounded in current repo deficits, with the highest-impact fixes being tighter migration semantics, staged schema adoption, and enforceable kernel boundaries.
