# AQ-OS v1 — Phased Plan & Delegation Matrix

**PRD**: `.agent/PROJECT-AQOS-PRD.md` · **Status**: awaiting ratification round `aqos-v1`
**Owner**: claude-fable-5 (orchestrator) · **Date**: 2026-07-09
**Cycle cadence**: one beat per dev cycle; every beat closes under the Activation Gate (Rule 15).

## Beat structure (strangler migration — PRD §8)

### Beat 0 — Ratification round (next cycle, first action)
- Dispatch `aq-collab-round --round aqos-v1` with `.agents/plans/aqos-v1/ROUND-PROMPT.md` to all four lanes (claude, codex, antigravity, local — local mandatory, aggregation stays open for late fold-in).
- Each lane: critique PRD, score workstreams 1-10, propose amendments, claim slices from the matrix below.
- Aggregate → AGGREGATE.md → consensus ≥3/4 ratifies → amend PRD → Beat 1 starts.

### Beat 1 — WS1 Contracts & Canon Compiler (zero runtime risk)
| Slice | Description | Agent | Depends |
|-------|-------------|-------|---------|
| 1.1 | `contracts/` tree scaffold + pydantic models for: A2A envelope, delegation record, payload, event | codex | — |
| 1.2 | Config-loader lib (schema-validate, env overlay, SIGHUP/inotify hot-reload) | codex | 1.1 |
| 1.3 | Switchboard adopts loader (kills restart-to-apply; live-test profile edit <5s) | claude | 1.2 |
| 1.4 | Canon compiler: `canon/` source → 5 agent .md files + switchboard cards + prompt blocks; fable-parity contract migrates first; drift = build failure | claude | — |
| 1.5 | Schema-validation CI check for all 107 `config/` files (report → fix-or-defer list) | local (Qwen, bounded single-file passes) | 1.1 |
| 1.6 | Research: JSON-Schema vs pydantic-v2 export strategy; NATS-readiness of envelope design | antigravity (research lane) | — |

### Beat 2 — WS2 Event Bus & A2A v2
| Slice | Description | Agent | Depends |
|-------|-------------|-------|---------|
| 2.1 | Redis Streams event log + signed envelopes + idempotency keys | codex | 1.1 |
| 2.2 | Projector service: events → PULSE.log/RESUME.json projections (files become read-only surfaces) | claude | 2.1 |
| 2.3 | Delegation registry v2: heartbeat/lease state machine on the log; auto stale reconciliation (kill -9 → truth in 60s) | codex | 2.1 |
| 2.4 | Antigravity inbox bridge = consumer group (OAuth file-lane preserved, NO API keys) | antigravity | 2.1 |
| 2.5 | Envelope signing keys via SOPS; audit events for privileged actions | claude | 2.1 |
| 2.6 | Migration: agents emit events instead of writing PULSE/RESUME directly (per-agent shims) | all four | 2.2 |

### Beat 3 — WS3 Kernel & F2.5 Activation (closes standing HIGH)
| Slice | Description | Agent | Depends |
|-------|-------------|-------|---------|
| 3.1 | Wire scheduler.py/backpressure.py/model_tier.py into dispatch.py (F2.5 — dedicated slice, live-tested on APU) | claude | — (can start Beat 1) |
| 3.2 | Kernel package extraction: policy/leases, scheduler, routing, registries | codex | 2.1 |
| 3.3 | Capability manifest schema + re-home 10 highest-traffic coordinator extensions | codex+local | 3.2 |
| 3.4 | `aq capability` lifecycle (install/enable/disable/upgrade; deny-by-default intake path) | claude | 3.3 |
| 3.5 | Remaining 39 extensions re-homed in batches of ~10 | local (bounded, sequential single-edits) + codex review | 3.3 |

### Beat 4 — WS4 One CLI + WS5 Observability
| Slice | Description | Agent | Depends |
|-------|-------------|-------|---------|
| 4.1 | `aq` entrypoint (typer plugin arch) + first 10 nouns; middleware (context injection, audit, rate-limit) once | codex | 1.1 |
| 4.2 | 131 binaries → subcommands/shims (usage-logged for data-driven retirement); batched 20/slice | local + codex review | 4.1 |
| 4.3 | OTel tracing: CLI→bus→switchboard→model→tools→commit, one trace id | codex | 2.1 |
| 4.4 | Metrics SSOT + Prometheus export (tokens, cost, latency, success, queue, thermals) | claude | 4.3 |
| 4.5 | SLO definitions + burn alerting; health-spider probes → capability-declared checks | claude | 4.4 |
| 4.6 | Research: self-hosted trace UI choice (Jaeger vs Grafana Tempo vs custom console view) on APU budget | antigravity | — |

### Beat 5 — WS6 Console (Experience Plane)
| Slice | Description | Agent | Depends |
|-------|-------------|-------|---------|
| 5.1 | OpenAPI-first refactor of dashboard backend; generated TS client | codex | 1.1 |
| 5.2 | SPA scaffold (framework per ratification; impeccable/frontend-design standards; design tokens light+dark) | antigravity (design) + codex (build) | 5.1 |
| 5.3 | Views wave 1: Fleet, Runs (trace waterfall), Approvals (HITL queue) | codex | 5.2, 4.3 |
| 5.4 | Views wave 2: Evals, Models, Cost, Memory, Backlog kanban, Topology | codex+claude | 5.3 |
| 5.5 | CLI/UI parity audit — every mutating view has its `aq` twin | local (audit checklist) | 5.4 |

### Beat 6 — WS7 Data Plane + WS8 RSI Industrialization
| Slice | Description | Agent | Depends |
|-------|-------------|-------|---------|
| 6.1 | Postgres system-of-record schema + Alembic migrations + retention policies | codex | 2.1 |
| 6.2 | Backup + restore DRILL (documented, executed, timed) | claude | 6.1 |
| 6.3 | Memory service v2: one query API over episodic/semantic/procedural/identity with provenance+freshness | codex | 6.1 |
| 6.4 | Eval service: golden sets per capability; scorecards; CI regression gates | claude+local (local generates candidate tasks; claude curates) | 6.1 |
| 6.5 | Prompt/profile registry (versioned, A/B, one-command rollback) | codex | 1.2 |
| 6.6 | Training DAG formalization + local capability-envelope KPI dashboard (weekly re-measure) | claude | 6.4 |

### Beat 7 — WS9 Security + WS10 Release
| Slice | Description | Agent | Depends |
|-------|-------------|-------|---------|
| 7.1 | Threat model (STRIDE over 4 planes; OWASP-agentic mapped to executable checks) | antigravity (draft) + claude (review) | — |
| 7.2 | CapabilityLease enforcement at bus+tool layer; egress allowlists per capability | codex | 3.2 |
| 7.3 | Supply chain: pinning policy, capability signing, SBOM, CI secret scan | claude | 3.4 |
| 7.4 | Red-team exercise: prompt-injection → exfil attempt must be lease/egress-blocked with audit trail | antigravity (attack) + claude (verify) | 7.2 |
| 7.5 | CI pipeline (hermetic Nix devShell + ephemeral services); tier0 = local mirror of CI | codex | 1.5 |
| 7.6 | Test triage: 419 scripts → pytest/harness_qa/archive; coverage floor | local (triage batches) + codex (suite structure) | 7.5 |
| 7.7 | Semver v1.0 release: changelog, migration scripts, install profiles, clean-machine install drill, docs site from canon | claude | all |

## Delegation defaults (role-matrix aligned)
- **claude** (orchestrator/reviewer): integration slices, live-system wiring, acceptance gates, commits.
- **codex** (implementer, headless): structural/typed code, services, CI. Stdin `< /dev/null`, prompts via temp file.
- **antigravity/gemini** (research/design lane, IDE-OAuth inbox): research, design drafts, threat modeling, attack simulation. Switchboard `X-AI-Profile: remote-free` fallback `local-coding`.
- **local/Qwen** (bounded implementer — MEASURED envelope: single-command/single-edit): audits, checklists, batched single-file passes, candidate generation. Every beat includes local slices; failures logged as WS8 training targets. Never skipped.

## Standing rules for every slice
PRD gate (PULSE plan line) → implement → live-test → tier0 → Activation-Gate attestation → commit (verbose message) → PULSE/RESUME update. Issues found → issues-backlog (Rule 11). Archive, never delete (Rule 12). Nix declaration lands same-cycle as any runtime change (Rule 13).
