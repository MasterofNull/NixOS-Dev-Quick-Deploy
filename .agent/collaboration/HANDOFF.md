# Handoff Memo - 2026-05-19 Staff Engineer Edge Harness PRD

## MAEAH A2A/signoff/acceptance slice — Codex, 2026-05-19

**Status:** Implementation complete; final tier0 validation blocked by live QA phase 0 failures unrelated to the edited files.
**Last Action (Codex):** Added Ed25519 Agent Card proof generation to `openai_a2a_handlers.py`, registered canonical `POST /a2a/tasks/send`, wrote the Q7 CPU-only fallback queue-buffer sign-off, and added `scripts/testing/maeah-acceptance-tests.sh` for the ten AM-C5 gates.
**Validation:** `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/extensions/openai_a2a_handlers.py` PASS; `bash -n scripts/testing/maeah-acceptance-tests.sh` PASS; A2A proof smoke with temp `A2A_SIGNING_KEY_PATH` PASS; `git diff --check` PASS; `jq empty .agent/collaboration/PENDING.json` PASS. `scripts/governance/tier0-validation-gate.sh --pre-commit` BLOCKED at QA phase 0. Direct `scripts/ai/aq-qa 0` evidence: 65 passed, 2 failed; failures are `0.1.2 no AI units in failed state` due `llama-cpp-model-fetch.service` failed, and `0.4.1 llama-server /health` empty status at `http://127.0.0.1:8080/health`.
**Next Step:** Fix or clear the live llama/model-fetch health failures, rerun tier0, then stage only the MAEAH A2A/signoff/acceptance files for commit.
**Context Bloat:** Low

**Status:** Complete. Staff Engineer PRD created at `.agents/plans/multi-agent-edge-harness/PRD-STAFF-ENG-CODEX.md`.
**Last Action (Codex):** Wrote the greenfield PRD from the Senior Staff Software Engineer lens, covering API contracts, data models, OpenAI-compatible/A2A/MCP/Admin APIs, model lifecycle state machine, hot-swap/rollback behavior, OTel integration, security boundaries, comparison hooks, and test strategy.
**Validation:** `jq empty .agent/collaboration/PENDING.json` PASS; mandatory section search PASS; generated PRD ASCII scan PASS. `scripts/governance/tier0-validation-gate.sh --pre-commit` BLOCKED by existing `aq-qa 0` failure: `0.4.1 llama-server /health` returned empty status for `http://127.0.0.1:8080/health` while the rest of phase 0 passed.
**Next Step:** Aggregate CTO, VP Eng, Staff Eng, and Edge AI PRDs into `.agents/plans/multi-agent-edge-harness/COMBINED-PRD.md` after the remaining role PRDs are available.
**Context Bloat:** Low

# Handoff Memo — 2026-05-19 Phase 59.0

**Status:** Phase 59.0 hardening complete. Full `aq-qa all` is green: **169 passed, 0 failed, 2 skipped**. Tier0 pre-commit gate is green: **14/14 PASS**.
**Last Action (Codex):** Fixed retrieval acceptance contract drift by keeping `avg_collection_count` present and surfacing `metadata_missing` when old route_search audit rows lack producer metadata. Fixed `test-agent-safety.sh` command quoting/`set -e` behavior so adversarial curl checks complete and the safety smoke exits 0 when all rows pass.
**Open Issues:** Route-search audit producer still should emit real `retrieval_collection_count`; current `avg_collection_count=0.0` indicates metadata missing, not measured breadth. RAG recall remains around 59.7%, so retrieval quality tuning is still the next substantive Phase 59 target.
**Next Step:** Start Phase 59.1: emit real route_search retrieval metadata at the producer, then tune RAG/domain retrieval toward the 80%+ target with measured before/after evidence.
**Context Bloat:** Medium

# Handoff Memo — 2026-05-19 Phase 58B.9

**Status:** Collaboration/routing/mobile-web hygiene complete. `aq-collaborate list` no longer fails on `postgres/ai_context`; it defaults to `aidb/aidb` and falls back to durable collaboration files when DB collaboration views are absent. Delegation registry stale rows reconciled with `scripts/ai/aq-delegation-registry`. Phase 58B routing audit added and passing. Mobile-web Lighthouse posture clarified: fixture mode is valid for promoted validation plumbing; real Lighthouse is required before any future mobile-web default transition.
**Last Action (Codex):** Fixed explicit security routing precedence, narrowed over-broad `implement`/scientific regression signals, added `scripts/testing/phase58b-routing-audit.py`, updated mobile-web PRD/instructions, and marked dead `running` delegation rows as `stale`.
**Open Issues:** `aq-qa all` still has two broader hardening failures reported by team/Codex context: `1.5.3` retrieval acceptance metrics missing `avg_collection_count`, and `5.8.2` agent safety smoke nonzero exit despite visible PASS rows. Gemini strategy attempts still exited without final output and were marked stale/failed.
**Next Step:** Start Phase 59.0 by fixing observability contract drift and safety-smoke exit inconsistency before deeper RAG/domain adoption work.
**Context Bloat:** Medium

# Handoff Memo — 2026-05-19

**Status:** Post-rebuild resume complete. Harness health verified (`aq-qa 0`: 67/67 PASS). Phase 58B real-use adoption evidence recorded in `.agents/plans/phase-58b-real-use-adoption-log.md`. Systems-software is currently the only `default` Phase 58B domain; the other five remain `promoted` opt-in.
**Last Action (Codex):** Checked aq-prime/session/memory, inspected delegation registry and collaboration files, verified endpoints, ran one bounded adoption task per Phase 58B domain, fixed systems-software shellcheck findings in `scripts/ai/aq-qa`, and hardened agent tool-use docs/config around Gemini yolo mode and Local/Qwen `run_shell_command` alias.
**Open Issues:** `aq-collaborate list` is blocked by Postgres auth for `postgres`; some older delegation registry rows still show stale `running` state; Gemini strategy check-in `gemini-20260518-192021-a3ldf1` exited without final output and is marked failed/incomplete; mobile-web still uses fixture Lighthouse mode.
**Next Step:** Fix collaboration/delegation registry hygiene first, then run a routing audit for the five promoted-but-not-default domains and decide whether mobile-web should gain real Lighthouse CLI support or keep fixture mode as validation-only.
**Context Bloat:** Medium

# Handoff Memo — 2026-05-18

**Status:** Phase 58B + post-rebuild hardening complete. All 6 domains `promoted`; AIDB namespaces seeded (11–100 docs each); dashboard header card eval/hints restored; agent tool waste eliminated system-wide; aq-qa 67/67 PASS.
**Last Action (2026-05-18):** (1) Fixed dashboard eval_latest_pct/hint_adoption_pct (commit e985b804) — _aq_report_snapshot() now reads persisted snapshot, never spawns aq-report inline. (2) Eliminated agent tool waste: Gemini default→yolo mode, Codex stdin fix, Local/Qwen run_shell_command alias. (3) All 6 domain dev shells verified post-rebuild. (4) AIDB seeded: security-findings (20), nix-systems-patterns (100), embedded-hardware (14), mobile-web (11), scientific-research (12), gis-systems (12).
**Next Step:** (a) nixos-rebuild switch required from terminal to deploy shell_tools.py changes for local/Qwen agent. (b) Route one real task through each promoted domain and monitor P0/P1 regressions. (c) Consider per-domain default slices later; do **not** default all domains automatically.
**Context Bloat:** Medium

## Phase 58B.0 reviewer verdict

Verdict: **PASS**

Acceptance evidence checked:
- six PRDs have `**Status:** Implemented — Phase 58A capability expansion`
- mobile-web PRD uses an on-demand Lighthouse npm hint and contains no `nodePackages.lighthouse`
- GIS PRD explicitly says standalone `pkgs.postgis` is not used and references `postgresqlPackages.postgis` only for service configuration
- PRDs state AIDB seeding remains pending or follow-on before validation/promotion
- PRDs contain no `not yet provisioned` wording for live tools such as ShellCheck v0.11 or the embedded toolchain

## Codex acceptance review — domain PRDs

Verdict: **PASS after revision**

The initial review found stale PRD drift (all six still marked `Proposed`, superseded package references for mobile-web/gis, and ambiguous AIDB timing). Those issues have been corrected in the PRDs. The set now matches the implemented architecture and the accepted domain template.

| Domain PRD | Verdict | Notes |
|---|---|---|
| security-systems | PASS | Tooling state corrected; validation boundary clarified |
| systems-software | PASS | ShellCheck state corrected; AIDB seeding moved to pre-validation evidence |
| embedded-hardware | PASS | Tool availability corrected; validation boundary clarified |
| mobile-web | PASS | Lighthouse / Playwright nixpkgs references corrected |
| scientific-research | PASS | Implemented shell vs future workflow evidence clarified |
| gis-systems | PASS | `spatialite-tools` / `postgresqlPackages.postgis` distinction corrected |

## Domain registry summary

| Domain | Shell | AIDB namespace | Profile | State |
|---|---|---|---|---|
| security-systems | `.#security` | security-findings | remote-reasoning / local-tool-calling | promoted |
| systems-software | `.#systems` | nix-systems-patterns | local-tool-calling | promoted |
| embedded-hardware | `.#embedded` | embedded-hardware-patterns | remote-reasoning | promoted |
| mobile-web | `.#mobile-web` | mobile-web-patterns | remote-reasoning | promoted |
| scientific-research | `.#scientific` | scientific-research-patterns | remote-reasoning | promoted |
| gis-systems | `.#gis` | gis-systems-patterns | local-tool-calling | promoted |

## Correct next transition path

Per `docs/architecture/capability-lifecycle.md`, domains must not skip from `implemented` to `candidate`.

Required order:
1. **implemented** — current state
2. **validated** — requires domain health evidence, representative workflow evidence, AIDB namespace completion where declared, and review-gate PASS where required
3. **candidate** — orchestrator opt-in decision
4. **promoted** — after soak period and no P0/P1 regressions

## Validation evidence currently known

- `aq-qa 0`: reported `67/67 PASS` in latest team handoff
- Codex rerun of tier0 pre-commit gate: `14/14 PASS`, including QA phase 0 `65 checks`
- Gemini review gate: **PASS** — `.agents/delegation/outputs/gemini-20260518-150453-tcswtz.log`
- Candidate soak: **PASS** — `.agents/plans/phase-58b-candidate-soak-log.md`
- all 6 domain health checks: reported PASS
- dev shells verified by team post-rebuild; Codex independently revalidated:
  - `.#embedded` — PASS
  - `.#scientific` — PASS
  - `.#gis` — PASS
  - `.#mobile-web` — validation still in progress / dependency-heavy
- `shellcheck` and `trivy` reported present in the system profile
- AIDB namespace seed evidence from live `GET /documents?project=<namespace>&limit=1000`:
  - `security-findings`: 19 documents
  - `nix-systems-patterns`: 347 documents
  - `embedded-hardware-patterns`: 13 documents
  - `mobile-web-patterns`: 10 documents
  - `scientific-research-patterns`: 11 documents
  - `gis-systems-patterns`: 11 documents
- Representative workflow evidence:
  - `security-systems`: PASS — Bandit + local Semgrep rule on safe sample source
  - `systems-software`: PASS — Nix parse + statix/deadnix + shellcheck fixture
  - `embedded-hardware`: PASS — Verilator lint of tiny Verilog module
  - `gis-systems`: PASS — GeoJSON CRS validation, EPSG:3857 transform, GDAL PNG generation
  - `scientific-research`: PASS — Snakemake CSV → deterministic summary → Pandoc PDF, repeated with identical numerical output
  - `mobile-web`: PASS / partial — deterministic MASA harness emitted Lighthouse-shaped JSON and MASVS static scan PASS; real Lighthouse binary still absent and `.#mobile-web` remains dependency-heavy/silent

## Outstanding operational work

1. Decide whether any promoted domain should become `default` routing behavior.
   - Decision recorded: **no bulk default** — see `.agents/plans/phase-58b-default-routing-decision.md`.
2. Route one real task through each promoted domain.
3. Decide whether real Lighthouse CLI should be required before defaulting mobile-web or can remain a promoted enhancement item.
4. Continue monitoring for P0/P1 regressions during actual opt-in use.

## Files added or reconciled by Codex in this continuation

- `.agent/CODEX.md`
- `.agents/plans/phase-58b-domain-prd-reconciliation.md`
- updated six domain PRDs to reflect implemented truth
- updated 58A review-plan statuses to reflect completed Codex acceptance
- `nix/home/base.nix` fix for VSCodium theme convergence
- `config/domain-knowledge-seeds.json`
- `scripts/data/seed-domain-knowledge.py`
- `scripts/automation/aidb-reindex.sh` now includes capability-domain seeding
- `scripts/data/ingest-project-knowledge.py` default AIDB URL now uses `127.0.0.1` to match the bound service and avoid `localhost` timeout ambiguity
- `.agents/plans/phase-58b-domain-validation-workflows.md`
- `.agents/plans/phase-58b-domain-validation-evidence.md`
- `scripts/ai/aq-collaborate` retargeted from removed `ai-stack/agentic-patterns` to `lib/l4-coord/agents` and repaired `start`
- `scripts/testing/mobile-web-masa-harness.py`
- `.agents/plans/phase-58b-review-package.md`
- `config/capability-lifecycle-registry.json` states advanced to `candidate` for all six Phase 58A domains after Gemini PASS and Codex orchestrator decision
- `.agents/plans/phase-58b-candidate-soak-log.md`
- `config/capability-lifecycle-registry.json` states advanced to `promoted` for all six Phase 58A domains after candidate soak PASS
- `.agents/plans/phase-58b-default-routing-decision.md`

---

## Phase 59.1 — route_search telemetry-backed retrieval breadth (Codex, 2026-05-19)

### Completed

- `scripts/ai/aq-report` now folds `HYBRID_TELEMETRY_PATH` (`/var/lib/ai-stack/hybrid/telemetry/hybrid-events.jsonl` by default) route_search events into audit analysis as audit-like entries.
- Retrieval breadth reporting now distinguishes total route calls from measured route calls and reports source coverage:
  - `measured_route_calls`
  - `telemetry_route_calls`
  - `source_counts`
- Added `scripts/testing/test-aq-report-route-telemetry.py` to prove legacy metadata-less audit rows no longer mask telemetry-backed collection-count evidence.

### Live evidence

`aq-report --since=24h --format=json` now reports measured retrieval breadth from telemetry:

- recent `route_retrieval_breadth.avg_collection_count`: `1.07`
- recent `measured_route_calls`: `326`
- recent `telemetry_route_calls`: `326`
- diagnosis: `healthy`

### Validation

- `python3 -m py_compile scripts/ai/aq-report scripts/testing/test-aq-report-route-telemetry.py scripts/testing/test-retrieval-breadth-history.py` — PASS
- `python3 scripts/testing/test-aq-report-route-telemetry.py` — PASS
- `python3 scripts/testing/test-retrieval-breadth-history.py` — PASS
- `aq-report --since=24h --format=json` — PASS
- `aq-qa 1` — PASS (`11 passed · 0 failed`)
- `aq-qa all` — PASS (`169 passed · 0 failed · 2 skipped`)
- `scripts/governance/tier0-validation-gate.sh --pre-commit` — PASS (`14 passed · 0 failed`)

### Next recommended slice

Use the now-measured telemetry baseline to tune RAG quality directly: compare low-recall query classes against selected retrieval profiles, then adjust collection/profile selection only where measured recall or breadth justifies it.

## Tool friction fix — aq-commit-facts endpoint fallback (Codex, 2026-05-19)

While storing Phase 59.1 commit facts, `aq-commit-facts` hit an unbound `HYBRID_COORDINATOR_URL` because `config/service-endpoints.sh` exports `HYBRID_URL`. Codex patched the script to default `HYBRID_COORDINATOR_URL` from `HYBRID_URL` and replaced brittle grep-based JSON extraction with JSONDecoder-based extraction.

Validation:
- `bash -n scripts/ai/aq-commit-facts` — PASS
- `shellcheck scripts/ai/aq-commit-facts` — PASS
- `scripts/governance/tier0-validation-gate.sh --pre-commit` — PASS (`14 passed · 0 failed`)

---

## Phase 59.2 — Memory recall contract diagnosis/fix (Codex, 2026-05-19)

### Finding

`aq-memory-recall-benchmark --json` currently reports `1/20` probes passing on the live service. The dominant implementation issue found in repo code is contract drift introduced by MemoryBroker integration:

- `/memory/recall` with omitted/null `memory_types` used to search all typed memory collections, but the broker path searched only `semantic`.
- `recall_agent_memory` stripped payload metadata from returned rows, so `/api/memory/facts?scope=...` could not filter stored facts by scope.
- `/api/memory/facts` looked only at `context`, not `metadata`, making it fragile across recall row shapes.

### Completed repo fix

- `knowledge/memory_context_handlers.py` now treats omitted/null `memory_types` as all typed memory collections and combines/dedupes top results.
- `knowledge/memory_manager.py` now preserves sanitized payload metadata as both `metadata` and `context` in recall rows.
- `http_server.py` now accepts either `context` or `metadata` for facts scope filtering.
- Added `scripts/testing/test-memory-recall-broker-contract.py` for this contract.

### Validation

- `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/knowledge/memory_context_handlers.py ai-stack/mcp-servers/hybrid-coordinator/knowledge/memory_manager.py ai-stack/mcp-servers/hybrid-coordinator/http_server.py scripts/testing/test-memory-recall-broker-contract.py` — PASS
- `python3 scripts/testing/test-memory-recall-broker-contract.py` — PASS
- `scripts/governance/tier0-validation-gate.sh --pre-commit` — PASS (`14 passed · 0 failed`)

### Deployment note

The live benchmark will not reflect this repo fix until the hybrid coordinator service is rebuilt/restarted from this revision. After deployment, rerun `scripts/ai/aq-memory-recall-benchmark --json`; if recall remains below target, the next likely bottleneck is sparse memory corpus coverage, not handler contract drift.

---

## Multi-Agent Edge Harness Combined PRD Sign-Off (Codex, 2026-05-19)

### Completed

- Reviewed `.agents/plans/multi-agent-edge-harness/COMBINED-PRD.md` against `.agents/plans/multi-agent-edge-harness/PRD-STAFF-ENG-CODEX.md`.
- Wrote `.agents/plans/multi-agent-edge-harness/SIGNOFF-CODEX.md`.
- Verdict: `APPROVE WITH AMENDMENTS`.

### Required amendments captured

- Normalize API contracts: `/v1/responses`, `/admin/v1/*`, and canonical A2A discovery/task endpoints.
- Correct security wording: loopback does not imply unauthenticated admin/lifecycle/tool access; signed or quarantined Agent Cards are required for networked mesh peers.
- Replace "typed Python dataclass schemas" with versioned JSON Schema/OpenAPI contracts and runtime-language types.
- Preserve explicit model lifecycle states including `downloaded`, `verified`, `warming`, `candidate`, and `failed`.
- Carry forward the concrete Staff Engineer test matrix as normative acceptance criteria.

### Validation

- `jq empty .agent/collaboration/PENDING.json` — PASS
- Required sign-off sections present — PASS

---

## Phase C — MLFQ Scheduler Implementation (Codex, 2026-05-19)

### Completed

- Added `ai-stack/mcp-servers/hybrid-coordinator/mlfq_scheduler.py` with typed `WorkloadDescriptor` and `TaskHandle` dataclasses.
- Implemented three-level asyncio-native MLFQ queues, token admission, thermal-tier admission gates, zombie reaping, task cancellation, AIMD backpressure events, and a singleton `get_scheduler()`.
- Wired `http_server.py` so `/query` and `/api/query` submit query work through the scheduler.
- Added `GET /admin/v1/scheduler/status`.
- Added scheduler startup and cleanup hooks for aiohttp.

### Validation

- `python3 -c "import ast; ast.parse(open('ai-stack/mcp-servers/hybrid-coordinator/mlfq_scheduler.py').read()); print('OK')"` — PASS
- `python3 -c "import ast; ast.parse(open('ai-stack/mcp-servers/hybrid-coordinator/http_server.py').read()); print('OK')"` — PASS
- `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/mlfq_scheduler.py ai-stack/mcp-servers/hybrid-coordinator/http_server.py` — PASS
- Scheduler smoke test with L0 execution and critical-tier L2 rejection — PASS
- `git diff --check` — PASS
- `jq empty .agent/collaboration/PENDING.json` — PASS
- `scripts/governance/tier0-validation-gate.sh --pre-commit` — BLOCKED by live `llama-server /health` returning 503 `Loading model` at `http://127.0.0.1:8080/health`.

### Commit Status

No commit was created because the repo validation gate explicitly failed and reported `Do NOT commit or deploy until all gates pass`. Rerun tier0 after llama-cpp finishes warming, then stage only the Phase C hunks plus `mlfq_scheduler.py` and commit with:

`feat(maeah): Phase C MLFQ scheduler with thermal coupling stub`

---

## MAEAH model lifecycle/dashboard continuation (Codex, 2026-05-20)

### Context

The system rebuild/switch completed, but the main local agent and llama server are currently down and being worked on. Live gates that depend on llama/local-agent were intentionally deferred.

### Completed repo-only continuation

- Preserved and validated the active model lifecycle/dashboard slice:
  - resumable model downloads with partial `.tmp` preservation
  - failed-model reset back to `verified` when local file exists
  - user-defined model add/delete API support
  - dashboard add-model form and failed-model retry/delete actions
  - Qwen3.6 MTP Q4/Q5 catalog refinements
  - sudoers entries for dashboard-triggered llama-cpp restart/status
  - MAEAH acceptance Gate 7 corrected to inspect the current module-level restart/llama-args implementation instead of a stale class method path

### Validation completed without live llama/local-agent

- `python3 -m py_compile` on changed Python files — PASS
- `bash -n scripts/testing/maeah-acceptance-tests.sh` — PASS
- `git diff --check` — PASS
- `nix-instantiate --parse nix/modules/services/command-center-dashboard.nix` — PASS
- model lifecycle/catalog static smoke — PASS

### Deferred live validation

Rerun when llama/local-agent are back:

```bash
aq-qa 0
scripts/ai/aq-memory-recall-benchmark --json
bash scripts/testing/maeah-acceptance-tests.sh --verbose
```

Do not use these static-only results as runtime promotion evidence.

---

## MAEAH AM-C1 / AM-C2 API surface normalization (Codex, 2026-05-20)

### Context

The main local agent and llama server remain down/under maintenance, so this slice avoided live inference-dependent checks.

### Completed

- Added `POST /v1/responses` compatibility shim in `extensions/openai_a2a_handlers.py`.
  - Accepts common Responses API `input` shapes.
  - Routes through current `/v1/chat/completions` switchboard surface until native Responses support exists.
  - Emits `X-OpenAI-Responses-Compat: chat-completions-shim` to avoid overstating parity.
- Added canonical `/admin/v1/models/*` dashboard route aliases while preserving `/api/models/*` compatibility aliases.
- Tightened `/admin/v1/models/*` mutating auth so loopback alone is not enough; requires `X-Dashboard-Internal: 1` or a valid `X-API-Key`.
- Updated A2A static contract test to inspect the real extracted implementation file.
- Added `scripts/testing/test-maeah-api-surface-contract.py` for AM-C1/AM-C2 regression coverage.

### Validation completed without live llama/local-agent

- `python3 -m py_compile` on changed Python/test files — PASS
- `python3 scripts/testing/test-maeah-api-surface-contract.py` — PASS
- `python3 scripts/testing/test-a2a-compat.py` — PASS
- `git diff --check` — PASS
- `scripts/governance/repo-structure-lint.sh` — PASS

### Deferred live validation

When the stack is back:

```bash
curl -sS -X POST http://127.0.0.1:8003/v1/responses -H 'Content-Type: application/json' -d '{"model":"local","input":"ping"}'
curl -sS http://127.0.0.1:8889/admin/v1/models
curl -sS -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8889/admin/v1/models/nonexistent/promote
```

Expected: `/v1/responses` returns Responses-shaped JSON once switchboard/llama are healthy; admin GET is reachable; mutating admin without auth is rejected.

---

## MAEAH AM-C3 schema/OpenAPI contract artifacts (Codex, 2026-05-20)

### Completed

- Added `config/schemas/maeah/model-entry.schema.json`.
  - Captures durable lifecycle states: `available`, `downloading`, `downloaded`, `verified`, `warming`, `candidate`, `active`, `retiring`, `archived`, `failed`.
  - Captures llama args, SLA tier, download/progress fields, user-defined marker, and audit log shape.
- Added `config/schemas/maeah/lifecycle-event.schema.json`.
  - Defines replay/audit event envelope `maeah.lifecycle-event.v1`.
- Added `docs/api/maeah-openapi.yaml`.
  - Documents `/v1/responses`, A2A canonical routes, `/admin/v1/models/*`, and `/admin/v1/scheduler/status`.
  - Marks `/v1/responses` as a compatibility shim via `X-OpenAI-Responses-Compat`.
  - Documents `X-API-Key` and `X-Dashboard-Internal` security schemes.
- Added `scripts/testing/test-maeah-contract-artifacts.py` to keep these artifacts present and internally consistent.

### Validation

- JSON schema syntax — PASS
- OpenAPI YAML syntax — PASS
- `python3 scripts/testing/test-maeah-contract-artifacts.py` — PASS
- `python3 -m py_compile scripts/testing/test-maeah-contract-artifacts.py` — PASS
- `git diff --check` — PASS

### Next recommended contract work

Use these schemas as the source for generated/runtime type checks. Expand OpenAPI once hardware state, scheduler queue detail, trace browsing, and `/v1/responses` native behavior stabilize.

---

## MAEAH ModelEntry schema implementation alignment gate (Codex, 2026-05-20)

### Completed

- Added `scripts/testing/test-maeah-model-registry-schema.py`.
- The test checks that:
  - `ModelState` enum exactly matches the `model-entry.schema.json` lifecycle state enum.
  - every built-in catalog entry normalized through `_default_entry()` has required schema fields.
  - SLA tier, version, GGUF filename, audit log, and key llama args are structurally valid.

### Validation

- `python3 -m py_compile scripts/testing/test-maeah-model-registry-schema.py` — PASS
- `python3 scripts/testing/test-maeah-contract-artifacts.py` — PASS
- `python3 scripts/testing/test-maeah-model-registry-schema.py` — PASS (`7` built-ins checked)
- `git diff --check` — PASS

### Next recommended gate work

Promote MAEAH contract checks into focused CI once the local stack is stable and the team is ready for these to become mandatory rather than repo-only parity checks.

---

## MAEAH `edgeai` CLI facade (Codex, 2026-05-20)

### Completed

- Added `scripts/ai/edgeai` as the first MAEAH CLI facade over normalized APIs.
- Supported commands:
  - `edgeai doctor [--json]`
  - `edgeai models list [--json]`
  - `edgeai models download|promote|rollback|reset <model-id>`
  - `edgeai a2a card validate [--json]`
  - `edgeai mcp tools list [--json]`
  - `edgeai traces tail [--last N] [--json]`
- Added Nix wrapper so `edgeai` is exposed with the other AI harness CLIs.
- Added `scripts/testing/test-edgeai-cli-contract.sh`.
- Offline behavior is explicit: commands emit JSON error envelopes rather than shell tracebacks when services are down.

### Validation

- `bash -n scripts/ai/edgeai scripts/testing/test-edgeai-cli-contract.sh` — PASS
- `scripts/testing/test-edgeai-cli-contract.sh` — PASS
- `nix-instantiate --parse nix/modules/roles/ai-stack.nix` — PASS
- `git diff --check` — PASS

### Deferred live validation

When llama/local-agent are back:

```bash
edgeai doctor --json
edgeai models list --json
edgeai a2a card validate --json
edgeai mcp tools list --json
edgeai traces tail --last 1 --json
```

Next CLI expansion should add `edgeai chat` and richer model mutation UX once live APIs are stable.

---

## MAEAH `edgeai chat` command (Codex, 2026-05-20)

### Completed

- Extended `scripts/ai/edgeai` with:
  - `edgeai chat [--model MODEL] [--json] <prompt...>`
- The command calls normalized `POST /v1/responses` and prints `output_text` by default.
- Offline behavior remains structured JSON error output for scriptability while llama/local-agent are down.
- Updated `scripts/testing/test-edgeai-cli-contract.sh` to cover help text and offline chat JSON behavior.

### Validation

- `bash -n scripts/ai/edgeai scripts/testing/test-edgeai-cli-contract.sh` — PASS
- `scripts/testing/test-edgeai-cli-contract.sh` — PASS
- `git diff --check` — PASS

### Deferred live validation

When services recover:

```bash
edgeai chat --json "Say pong"
edgeai chat --model local "Say pong"
```

---

## MAEAH focused CI registry promotion (Codex, 2026-05-20)

### Completed

Added path-aware focused CI entries in `config/validation-check-registry.json` for:

- `maeah-api-surface-contract`
- `maeah-contract-artifacts`
- `maeah-model-registry-schema`
- `edgeai-cli-contract`

These keep the repo-only MAEAH parity checks attached to the files they protect instead of relying on manual recall.

### Validation

- `jq empty config/validation-check-registry.json` — PASS
- `python3 scripts/testing/test-maeah-api-surface-contract.py` — PASS
- `python3 scripts/testing/test-maeah-contract-artifacts.py` — PASS
- `python3 scripts/testing/test-maeah-model-registry-schema.py` — PASS
- `scripts/testing/test-edgeai-cli-contract.sh` — PASS
- `git diff --check` — PASS


---

## MAEAH `edgeai models add/delete` CLI slice (Codex, 2026-05-20)

### Completed

- Extended `scripts/ai/edgeai` with user-defined model catalog operations:
  - `edgeai models add --id ID --name NAME --repo REPO --file FILE [options]`
  - `edgeai models add --from-json PATH`
  - `edgeai models delete <model-id>`
- Normalized offline mutation behavior for model lifecycle commands so failed dashboard calls emit JSON error envelopes instead of raw curl output.
- Updated `scripts/testing/test-edgeai-cli-contract.sh` to cover help text and offline JSON behavior for add/delete/download.

### Validation

- `bash -n scripts/ai/edgeai scripts/testing/test-edgeai-cli-contract.sh` — PASS
- `scripts/testing/test-edgeai-cli-contract.sh` — PASS
- `python3 scripts/testing/test-maeah-api-surface-contract.py` — PASS
- `python3 scripts/testing/test-maeah-contract-artifacts.py` — PASS
- `python3 scripts/testing/test-maeah-model-registry-schema.py` — PASS
- `bash scripts/governance/check-script-header-standards.sh --all` — PASS
- `git diff --check` — PASS

### Deferred live validation

Local llama/local-agent services were reported down, so no live dashboard/coordinator calls were executed. When services recover, validate with a disposable user model:

```bash
edgeai models add --id local-smoke --name "Local Smoke" --repo org/repo --file model.gguf
edgeai models delete local-smoke
edgeai doctor --json
edgeai chat --json "Say pong"
```


---

## MAEAH `edgeai contracts check` CLI slice (Codex, 2026-05-20)

### Completed

- Added `edgeai contracts check [--json]` for repo-local MAEAH static contract validation.
- The command runs the normalized API surface, schema/OpenAPI artifact, and model registry schema checks without contacting llama/local-agent services.
- Updated `scripts/testing/test-edgeai-cli-contract.sh` so the CLI contract covers the new command.

### Validation

- `bash -n scripts/ai/edgeai scripts/testing/test-edgeai-cli-contract.sh` — PASS
- `scripts/ai/edgeai contracts check --json` — PASS
- `scripts/testing/test-edgeai-cli-contract.sh` — PASS
- `git diff --check` — PASS

### Note

The command intentionally excludes `test-edgeai-cli-contract.sh` internally to avoid recursive self-invocation. The wrapper test still validates the contracts command separately.


---

## MAEAH live validation runbook (Codex, 2026-05-20)

### Completed

- Added `.agents/plans/multi-agent-edge-harness/LIVE-VALIDATION-RUNBOOK.md`.
- Captured the post-recovery runtime validation sequence:
  - repo-static contract gate,
  - surface health,
  - `/v1/responses` smoke,
  - user-defined model add/delete smoke,
  - full MAEAH acceptance and memory recall benchmark.
- Documented promotion criteria and failure handling so the team does not treat repo-static evidence as runtime readiness.

### Validation

- `python3 -m json.tool .agent/collaboration/PENDING.json` — PASS
- `git diff --check .agents/plans/multi-agent-edge-harness/LIVE-VALIDATION-RUNBOOK.md .agent/collaboration/PENDING.json` — PASS
- Manual runbook review — PASS: static-first, live checks explicitly deferred until service recovery.

### Deferred live validation

Run `.agents/plans/multi-agent-edge-harness/LIVE-VALIDATION-RUNBOOK.md` after llama.cpp/local model services recover.


---

## MAEAH live runbook static contract test (Codex, 2026-05-20)

### Completed

- Added `scripts/testing/test-maeah-live-runbook-contract.py`.
- The test verifies `.agents/plans/multi-agent-edge-harness/LIVE-VALIDATION-RUNBOOK.md` keeps required phases, safety warnings, promotion criteria, and current `edgeai` command references.
- Wired the new test into `edgeai contracts check --json`.
- Registered `maeah-live-runbook-contract` in `config/validation-check-registry.json` for focused static validation.

### Validation

- `python3 -m py_compile scripts/testing/test-maeah-live-runbook-contract.py` — PASS
- `python3 scripts/testing/test-maeah-live-runbook-contract.py` — PASS
- `bash -n scripts/ai/edgeai` — PASS
- `scripts/ai/edgeai contracts check --json` — PASS
- `scripts/testing/test-edgeai-cli-contract.sh` — PASS
- `jq empty config/validation-check-registry.json` — PASS
- `git diff --check` — PASS
- Bounded Tier 0 — PARTIAL: 13 PASS, QA phase 0 timed out because llama/local-agent are intentionally down.

### Deferred live validation

No live service calls were made. Continue using `edgeai contracts check --json` until llama.cpp/local model recover, then run the live validation runbook.


---

## MAEAH OpenAPI model mutation contract parity (Codex, 2026-05-20)

### Completed

- Updated `docs/api/maeah-openapi.yaml` to document user-defined model mutation parity:
  - `POST /admin/v1/models` request/response schema via `UserModelCreateRequest`.
  - `DELETE /admin/v1/models/{model_id}` for user-defined, non-active catalog entries.
  - explicit protection language for built-in and active models.
- Tightened `scripts/testing/test-maeah-contract-artifacts.py` so add/delete operations and response status contracts stay present.

### Validation

- `python3 -m py_compile scripts/testing/test-maeah-contract-artifacts.py` — PASS
- `python3 scripts/testing/test-maeah-contract-artifacts.py` — PASS
- `scripts/ai/edgeai contracts check --json` — PASS
- `git diff --check` — PASS
- Bounded Tier 0 — PARTIAL: 13 PASS, QA phase 0 timed out because llama/local-agent are intentionally down.

### Deferred live validation

After service recovery, validate `edgeai models add/delete` against the live dashboard admin API using the live validation runbook.


---

## MAEAH admin mutation auth static contract (Codex, 2026-05-20)

### Completed

- Strengthened `scripts/testing/test-maeah-api-surface-contract.py` with route-level checks for model lifecycle mutation handlers.
- Static coverage now verifies `_check_auth(request)` is present on:
  - download, promote, rollback, cancel, reset,
  - user-defined model add,
  - user-defined model delete.
- The test also asserts the add/delete route decorators exist.

### Validation

- `python3 -m py_compile scripts/testing/test-maeah-api-surface-contract.py` — PASS
- `python3 scripts/testing/test-maeah-api-surface-contract.py` — PASS
- `scripts/ai/edgeai contracts check --json` — PASS
- `git diff --check` — PASS
- Bounded Tier 0 — PARTIAL: 13 PASS, QA phase 0 timed out because llama/local-agent are intentionally down.

### Deferred live validation

After dashboard/coordinator recovery, run live negative/positive auth checks for `/admin/v1/models` mutations with and without `X-Dashboard-Internal` or `X-API-Key`.
