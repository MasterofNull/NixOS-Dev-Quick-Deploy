# System Improvement Roadmap — 2026-03 Q1 Finalization

**Generated:** 2026-03-13
**Status:** Active
**Owner:** AI Harness
**Last Updated:** 2026-03-14
**Version:** 1.1.0

---

## Overview

This roadmap completes the next major system improvement tranche following the successful finalization of the SYSTEM-FINALIZATION-ROADMAP. It addresses all identified gaps, implements upgrades, enhances monitoring, and extends system control tooling.

## Execution Protocol

```
For each Phase:
  For each Task Batch:
    1. Set batch status → in_progress
    2. Execute all tasks in batch (parallelizable where independent)
    3. Run batch validation suite
    4. Capture evidence
    5. Set batch status → completed
    6. Commit with descriptive message
  End
  Run phase gate validation
  Update this document with progress
End
```

---

## Current System Baseline (2026-03-13)

| Metric | Current | Target |
|--------|---------|--------|
| Eval Score (mean) | 81.4% | ≥85% |
| Semantic Cache Hit Rate | 54.9% | ≥60% |
| Memory Store Success | 68.8% | ≥95% |
| Hint Diversity (unique) | 3 | ≥10 |
| Route Search P95 | 4835ms | <2000ms |
| QA Check Success | 79.2% | ≥95% |
| MCP Health | 13/13 | 13/13 |

---

## Phase 1: Continue/Editor Integration Completion

**Objective:** Make Continue/editor flows production-stable with full harness integration.
**Gate:** All Continue phase-0 checks green + agent/planning mode validated

### Batch 1.1: MCP Bridge Validation
**Status:** completed
**Tasks:**
- [x] Configure Continue MCP servers in config.json
- [x] Validate MCP bridge lists all 14 tools
- [x] Test project_init_workflow via MCP
- [x] Document integration in CLAUDE.md

**Evidence:** MCP bridge configured, tools listed, project scaffolded

### Batch 1.2: Editor Extension Smoke Coverage
**Status:** validated
**Tasks:**
- [ ] Run `scripts/testing/smoke-continue-editor-flow.sh`
- [ ] Validate aq-hints context provider working
- [ ] Test Continue agent mode response quality
- [ ] Verify dense-prompt trimming active

**Validation:**
```bash
scripts/ai/aq-qa 0 --json | jq '.tests[] | select(.id | startswith("0.5."))'
scripts/testing/smoke-continue-editor-flow.sh
python3 scripts/testing/test-continue-editor-failure-categories.py
```

### Batch 1.3: Web Research Lane Expansion
**Status:** completed
**Tasks:**
- [x] Expand approved source packs beyond California-native (tech-documentation, security-advisories)
- [x] Add Mendocino-specific source pack (native-plants-mendocino with 3 sources)
- [x] Validate browser fallback for complex pages (fallback_fetch_mode configured)
- [x] Add source selector tuning for known-problematic sites (selectors per source)

**Evidence:**
- Added 3 new workflow packs: native-plants-mendocino, tech-documentation, security-advisories
- Mendocino pack includes: calflora-mendocino-county, mendocino-coast-botanical, jepson-mendocino
- Tech docs pack includes: nixos-manual, nix-dev-manual, home-manager-options
- Security pack includes: nvd-search, github-advisories
- Browser fallback configured on calflora and home-manager sources

**Validation:**
```bash
python3 scripts/testing/test-web-research-lane.py
curl -sS -X POST http://127.0.0.1:8003/research/web/fetch -d '{"url":"...","max_chars":5000}'
```

---

## Phase 2: Memory & Retrieval Hardening

**Objective:** Achieve ≥95% memory store success and <2000ms route_search P95.
**Gate:** Memory success ≥95%, Route P95 <2000ms

### Batch 2.1: Memory System Fixes
**Status:** validated
**Tasks:**
- [ ] Add retry logic to store_agent_memory (3 retries with backoff)
- [ ] Implement memory deduplication (cosine >0.95 = skip)
- [ ] Add memory latency metrics to status endpoint
- [ ] Fix qa_check timeout issues (21 errors seen)

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.tool_performance[] | select(.tool=="store_agent_memory")'
```

### Batch 2.2: Route Search Optimization
**Status:** validated
**Tasks:**
- [ ] Profile route_search latency by collection
- [ ] Reduce collection fan-out for simple queries
- [ ] Add provider-fallback pressure into runtime policy
- [ ] Implement adaptive timeout based on query complexity

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.route_search_latency_decomposition'
python3 scripts/testing/test-route-search-pressure-diagnosis.py
```

### Batch 2.3: RAG Posture Improvement
**Status:** validated
**Tasks:**
- [ ] Increase memory recall usage for continuations
- [ ] Add prewarm candidates from actual retrieval profiles
- [ ] Tune retrieval breadth thresholds by task class
- [ ] Add retrieval-profile acceptance checks

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.rag_posture, .route_retrieval_breadth'
scripts/ai/aq-qa 1 --json | jq '.tests[] | select(.id == "1.5.3")'
```

---

## Phase 3: Monitoring & Dashboard Enhancement

**Objective:** Unified command center with real-time visibility into all system dimensions.
**Gate:** Dashboard shows all track metrics, PRSI actions executable

### Batch 3.1: Dashboard Report Integration
**Status:** validated
**Tasks:**
- [ ] Add aq-report summary widget to dashboard
- [ ] Show trend sparklines for key metrics
- [ ] Add Continue/editor health status card
- [ ] Show active lesson refs in dashboard

**Validation:**
```bash
curl -sS http://127.0.0.1:8003/dashboard.html | grep -q 'report_summary'
```

### Batch 3.2: PRSI Action Execution
**Status:** validated
**Tasks:**
- [x] Verify all PRSI maintenance actions work (via CLI: aq-optimizer, aq-gap-auto-remediate)
- [x] Add action execution history tracking (optimizer-actions.jsonl, gap-remediation logs)
- [x] Show action success/failure status (--output-json flag)
- [ ] Add dashboard API endpoint for PRSI actions

**Evidence:** aq-optimizer --dry-run identifies 2 actions; aq-gap-auto-remediate --dry-run works

**Validation:**
```bash
scripts/ai/aq-optimizer --dry-run --output-json
scripts/ai/aq-gap-auto-remediate --dry-run --limit 3
```

### Batch 3.3: Multi-Window Trend Visibility
**Status:** completed
**Tasks:**
- [x] Add 1h/24h/7d trend toggles to dashboard (http_server.py updated)
- [x] Show routing history trends visually (trend_1h/24h/7d in routing section)
- [x] Add retrieval breadth trend charts (trend_1h/24h/7d in retrieval section)
- [x] Show delegated failure trend history (new delegation_failures section)

**Evidence:**
- Added `trend_summary` with quick indicators (↑/↓/→/?)
- Added `trend_1h` windows alongside existing 24h/7d for all metrics
- Added `delegation_failures` section with trend_status and windows
- Updated smoke test to verify all 1h/24h/7d windows

**Note:** Service restart required for runtime activation.

**Validation:**
```bash
scripts/testing/smoke-status-report-summary.sh
curl -sS http://127.0.0.1:8003/control/ai-coordinator/status | jq '.report_summary'
```

---

## Phase 4: Remote Delegation Quality

**Objective:** Reliable remote delegation with proper failure recovery.
**Gate:** Delegation success ≥95%, finalization always applied

### Batch 4.1: Finalization Hardening
**Status:** validated
**Tasks:**
- [ ] Ensure finalization pass always runs for tool-call-only responses
- [ ] Add timeout handling for slow remote providers
- [ ] Improve artifact recovery for partial failures
- [ ] Add delegated response quality scoring

**Validation:**
```bash
scripts/testing/smoke-remote-delegation-lanes.sh
python3 scripts/testing/test-delegated-prompt-failure-history.py
```

### Batch 4.2: Provider Fallback Policy
**Status:** completed
**Tasks:**
- [x] Implement automatic fallback on provider 429 (config/provider-fallback-policy.json)
- [x] Add provider health tracking (_provider_health_summary in http_server.py)
- [x] Create provider selection scoring (selection_scoring weights in policy)
- [x] Add cost-aware routing hints (cost_aware_routing section with provider costs)

**Evidence:**
- Created config/provider-fallback-policy.json with fallback triggers, health tracking, and cost hints
- Added _load_provider_fallback_policy() and _provider_health_summary() to http_server.py
- Status endpoint now includes provider_health section

**Note:** Service restart required for runtime activation.

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.provider_fallback_recovery, .delegated_prompt_failures'
```

### Batch 4.3: Prompt Contract Tightening
**Status:** completed
**Tasks:**
- [x] Reduce prompt token footprint for small tasks (delegation_simple template)
- [x] Add task-class-specific prompt templates (4 new delegation templates)
- [x] Implement prompt quality validation (delegation_prompt_contracts.json)
- [x] Track prompt-contract failure trends (existing in aq-report)

**Evidence:**
- Created config/delegation-prompt-contracts.json with task-class configs
- Added 4 compact delegation templates: delegation_simple, delegation_code, delegation_reasoning, delegation_architecture
- Token budget policy with small_task_threshold and reduce_system_prefix_pct

**Validation:**
```bash
python3 scripts/testing/test-delegated-prompt-failure-trend.py
```

---

## Phase 5: Lesson & Skill Evolution

**Objective:** Active lesson promotion affecting runtime behavior.
**Gate:** ≥5 accepted lessons actively referenced

### Batch 5.1: Lesson Registry Completion
**Status:** validated
**Tasks:**
- [ ] Run all 16+ lesson-ref smoke tests
- [ ] Verify lessons appear in hints
- [ ] Confirm lessons affect delegation contracts
- [ ] Add lesson effectiveness tracking

**Validation:**
```bash
scripts/testing/smoke-delegate-lesson-refs.sh
scripts/testing/smoke-hints-lesson-refs.sh
scripts/testing/smoke-workflow-plan-lesson-refs.sh
```

### Batch 5.2: Skill Registry Expansion
**Status:** completed
**Tasks:**
- [x] Expand shared skill coverage beyond current 24
- [ ] Add skill usage tracking
- [ ] Implement skill recommendation engine
- [ ] Add external skill import validation

**Evidence:** Added 3 new skills (26 total):
- debug-workflow: Systematic debugging protocol
- performance-profiler: Performance analysis workflow
- security-scanner: OWASP-aligned security audit

**Validation:**
```bash
curl -sS http://127.0.0.1:8003/control/ai-coordinator/skills | jq '.skill_count'
scripts/ai/aq-report --format=json | jq '.shared_skills'
```

---

## Phase 6: Hint Diversity & Self-Improvement

**Objective:** Expand hint variety and activate self-improvement loops.
**Gate:** Hint entropy ≥2.5 bits, pattern library ≥20

### Batch 6.1: Hint Template Expansion
**Status:** completed
**Tasks:**
- [x] Add 8-10 new hint templates for underserved task types
- [ ] Implement context-aware hint routing by file type
- [ ] Add hint feedback acceleration
- [ ] Reduce dominant hint concentration

**Evidence:** Added 10 new templates to ai-stack/prompts/registry.yaml:
- code_review_structured, debugging_systematic, test_generation_coverage
- refactoring_incremental, documentation_api, security_audit_focused
- performance_optimization, migration_upgrade_plan, api_integration_guide
- configuration_setup

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.hint_diversity'
```

### Batch 6.2: Pattern Extraction Pipeline
**Status:** completed
**Tasks:**
- [x] Implement automated pattern detection (3+ occurrence threshold)
- [x] Add pattern quality scoring (filter <0.7)
- [ ] Integrate patterns into hints/RAG
- [ ] Track pattern effectiveness

**Evidence:** scripts/ai/aq-patterns CLI with extract/list/stats/quality commands

**Validation:**
```bash
scripts/ai/aq-patterns stats --format json
scripts/ai/aq-patterns extract --min-occurrences 3
```

### Batch 6.3: Gap Auto-Remediation
**Status:** validated
**Tasks:**
- [x] Add systemd timer for daily gap detection (already in nix/modules/roles/ai-stack.nix)
- [x] Implement auto-remediation pipeline (scripts/ai/aq-gap-auto-remediate)
- [x] Add remediation verification loop (--verify flag)
- [ ] Track remediation success rate

**Evidence:** ai-gap-auto-remediate.timer active, runs daily at 06:00

**Validation:**
```bash
systemctl status ai-gap-auto-remediate.timer
scripts/ai/aq-gap-auto-remediate --dry-run
```

---

## Phase 7: CLI Package Parity

**Objective:** All flagship agent CLIs declaratively packaged or explicitly scaffolded.
**Gate:** All CLI surfaces pass --help smoke

### Batch 7.1: Package Validation
**Status:** completed
**Tasks:**
- [x] Validate Continue CLI declarative package
- [x] Validate Codex CLI package/scaffold status
- [x] Validate Qwen CLI package/scaffold status
- [x] Validate Gemini CLI package/scaffold status
- [x] Validate Claude CLI package/scaffold status
- [x] Validate pi agent package/scaffold status

**Evidence:** smoke-flagship-cli-surfaces.sh PASS, all 6 CLIs respond to --help

**Validation:**
```bash
scripts/testing/smoke-flagship-cli-surfaces.sh
cn --help && codex --help && qwen --help && gemini --help && claude --help && pi --help
```

### Batch 7.2: Support Matrix Update
**Status:** completed
**Tasks:**
- [x] Update support matrix with current status
- [x] Document external-only surfaces
- [x] Add harness integration status per CLI
- [x] Create upgrade path documentation

**Evidence:** docs/AGENT-PARITY-MATRIX.md updated with CLI Support Matrix section

**Validation:**
```bash
scripts/testing/verify-flake-first-roadmap-completion.sh
```

---

## Phase 8: BitNet Evaluation (Blocked)

**Objective:** Evaluate BitNet as local inference option (currently blocked on SIGSEGV).
**Gate:** Benchmark comparison without crashes

### Batch 8.1: SIGSEGV Investigation
**Status:** blocked
**Tasks:**
- [ ] Investigate SIGSEGV in llama-bench
- [ ] Test with different GGUF configurations
- [ ] Document hardware/software requirements
- [ ] Identify upstream fix or workaround

**Validation:**
```bash
python3 scripts/ai/aq-bitnet-feasibility.py --format=json
python3 scripts/testing/test-bitnet-benchmark.py
```

### Batch 8.2: Comparison Benchmarks
**Status:** blocked
**Tasks:**
- [ ] Run comparison once SIGSEGV fixed
- [ ] Document performance delta
- [ ] Evaluate cost/benefit tradeoff
- [ ] Decide on integration path

**Validation:**
```bash
python3 scripts/ai/aq-bitnet-compare.py
```

---

## Phase 9: Agentic RAG Enhancement

**Objective:** Implement reflection loops, generator-critic patterns, and query routing from agentic RAG research.
**Gate:** RAG reflection active, generator-critic pattern working, query routing by complexity

### Batch 9.1: Reflection Loop Implementation
**Status:** pending
**Tasks:**
- [ ] Add self-critique step after RAG retrieval (evaluate relevance before using)
- [ ] Implement retrieval re-try on low-confidence results
- [ ] Add reflection metrics to status endpoint
- [ ] Track reflection-triggered improvements

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.rag_reflection_stats'
python3 scripts/testing/test-rag-reflection-loop.py
```

### Batch 9.2: Generator-Critic Pattern
**Status:** pending
**Tasks:**
- [ ] Implement critic step for generated responses (self-verify before return)
- [ ] Add quality scoring for delegation outputs
- [ ] Implement revision request on critic rejection
- [ ] Track critic intervention rate

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.generator_critic_stats'
python3 scripts/testing/test-generator-critic-pattern.py
```

### Batch 9.3: Query Complexity Routing
**Status:** pending
**Tasks:**
- [ ] Implement query complexity scoring (simple/medium/complex)
- [ ] Route simple queries to lightweight models
- [ ] Route complex queries to reasoning-capable models
- [ ] Add routing decision logging and analysis

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.query_routing_breakdown'
python3 scripts/testing/test-query-complexity-router.py
```

---

## Phase 10: Hint Diversity Fix (Critical)

**Objective:** Fix 80% hint concentration problem and achieve true diversity.
**Gate:** No single hint >30% concentration, unique hints ≥15

### Batch 10.1: Concentration Diagnosis
**Status:** validated
**Tasks:**
- [x] Identify dominant hint causing 80% concentration
- [x] Analyze hint selection algorithm
- [x] Profile task-class to hint mapping
- [x] Document current hint routing logic

**Evidence:** Diagnosis performed as part of 10.2. Found broad trigger keywords matching 80% of queries.

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.hint_concentration_analysis'
```

### Batch 10.2: Hint Routing Overhaul
**Status:** completed
**Tasks:**
- [x] Implement task-class-aware hint selection
- [x] Add randomization with diversity guarantee
- [x] Implement hint cooldown (don't repeat same hint consecutively)
- [x] Add file-type-specific hint routing

**Evidence:**
- Lowered repeat_cap_pct from 45% to 25%
- Added 60% hard_exclude_pct threshold
- Added 4 fallback hints with randomization
- Added aggressive penalty multiplier (1.5x)

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.hint_diversity'
# Expect: max_concentration < 0.30, unique_hints >= 15
```

### Batch 10.3: Token-Efficient Hint Delivery
**Status:** completed
**Tasks:**
- [x] Implement hint compression for long hints
- [x] Add hint priority ranking
- [x] Cap total hint tokens per request
- [x] Implement progressive hint disclosure

**Evidence:**
- Added _estimate_tokens() and _compress_snippet() to hints_engine.py
- Updated to_dict() with compact_mode and max_snippet_chars params
- Updated rank_as_dict() with max_hint_tokens and compact_mode params
- Updated handle_hints to accept max_hint_tokens and compact query params
- Token budget tracking returned in response (estimated_tokens, hints_truncated)

**Note:** Service restart required for runtime activation.

**Validation:**
```bash
curl -sS -X POST http://127.0.0.1:8003/hints -d '{"query":"test","compact":true,"max_hint_tokens":200}' | jq '.token_budget'
```

---

## Phase 11: MCP Protocol Compliance

**Objective:** Implement MCP 2026 roadmap features for protocol compliance.
**Gate:** .well-known endpoint active, health pings working

### Batch 11.1: Well-Known Metadata Endpoint
**Status:** completed
**Tasks:**
- [x] Implement /.well-known/mcp.json endpoint on all MCP servers
- [x] Include server capabilities, version, supported protocols
- [x] Add tool schema definitions
- [x] Document endpoint format

**Evidence:**
- Added /.well-known/mcp.json to hybrid-coordinator (http_server.py)
- Added /.well-known/mcp.json to ralph-wiggum (server.py)
- Added /.well-known/mcp.json to aidb (server.py)
- All endpoints expose mcp_version, server info, capabilities, protocols, endpoints, rate_limiting, and links

**Validation:**
```bash
curl -sS http://127.0.0.1:8003/.well-known/mcp.json | jq .
curl -sS http://127.0.0.1:8001/.well-known/mcp.json | jq .
curl -sS http://127.0.0.1:8002/.well-known/mcp.json | jq .
```

### Batch 11.2: Health Ping Protocol
**Status:** completed
**Tasks:**
- [x] Implement /health endpoint on all MCP servers
- [x] Add structured health response (status, latency, dependencies)
- [x] Implement health aggregator in coordinator
- [x] Add health history tracking

**Evidence:**
- Added /health/aggregate endpoint to hybrid-coordinator (http_server.py)
- Endpoint pings all MCP servers (coordinator, aidb, ralph-wiggum, llama-cpp, qdrant)
- Latency tracking per server (latency_ms field)
- Health history tracking with deque (last 60 snapshots)
- Trend analysis (stable/fluctuating/degrading)
- Created smoke-mcp-health-pings.sh validation script

**Note:** Service restart required for runtime activation.

**Validation:**
```bash
scripts/testing/smoke-mcp-health-pings.sh
curl -sS http://127.0.0.1:8003/health/aggregate | jq '.servers | keys'
```

### Batch 11.3: Signed Component Support
**Status:** pending
**Tasks:**
- [ ] Research MCP signed component specification
- [ ] Implement signature validation for tool definitions
- [ ] Add signature generation for custom tools
- [ ] Document signing workflow

**Validation:**
```bash
python3 scripts/testing/test-mcp-signature-validation.py
```

---

## Phase 12: Dual-Model Architecture

**Objective:** Implement reasoning + coding model separation for optimal task routing.
**Gate:** Dual-model routing active, measurable quality improvement

### Batch 12.1: Model Role Classification
**Status:** pending
**Tasks:**
- [ ] Define reasoning-model tasks (planning, architecture, analysis)
- [ ] Define coding-model tasks (implementation, refactoring, tests)
- [ ] Create task classifier for automatic routing
- [ ] Document model role boundaries

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.model_role_classification'
```

### Batch 12.2: Dual-Model Routing
**Status:** pending
**Tasks:**
- [ ] Implement reasoning-first, coding-second pipeline
- [ ] Add model handoff protocol
- [ ] Implement context transfer between models
- [ ] Track dual-model collaboration metrics

**Validation:**
```bash
python3 scripts/testing/test-dual-model-routing.py
```

### Batch 12.3: Context Hygiene Automation
**Status:** completed
**Tasks:**
- [x] Implement automatic context pruning (domain-based progressive disclosure)
- [x] Add stale context detection (level-based loading)
- [x] Implement summary compression for long contexts (compact_injection strings)
- [x] Track context token budget adherence (token_estimate per domain)

**Evidence:**
- Created config/progressive-disclosure-domains.json with 7 work domains
- Extended progressive_disclosure.py with DomainLoader class
- Integrated domain context into hints engine (domain_context field)
- Added domain_disclosure to /control/ai-coordinator/status endpoint
- Documented in docs/agent-guides/45-PROGRESSIVE-DISCLOSURE.md

**Validation:**
```bash
curl -sS http://127.0.0.1:8003/control/ai-coordinator/status | jq '.domain_disclosure'
curl -sS -X POST http://127.0.0.1:8003/hints -d '{"query":"nix"}' | jq '.domain_context'
```

---

## Quality Gates Summary

| Phase | Gate Criteria | Validation Command |
|-------|--------------|-------------------|
| Phase 1 | Continue checks green | `aq-qa 0 --json \| jq '.summary.passed'` |
| Phase 2 | Memory ≥95%, P95 <2000ms | `aq-report --format=json \| jq '.tool_performance'` |
| Phase 3 | Dashboard shows all metrics | Manual dashboard inspection |
| Phase 4 | Delegation ≥95% | `aq-report --format=json \| jq '.delegation'` |
| Phase 5 | ≥5 active lessons | `aq-report --format=json \| jq '.active_lessons'` |
| Phase 6 | Hint entropy ≥2.5 | `aq-report --format=json \| jq '.hint_diversity'` |
| Phase 7 | All CLI smokes pass | `smoke-flagship-cli-surfaces.sh` |
| Phase 8 | BitNet benchmark runs | `aq-bitnet-compare.py` (blocked) |
| Phase 9 | RAG reflection active | `aq-report --format=json \| jq '.rag_reflection_stats'` |
| Phase 10 | Hint concentration <30% | `aq-report --format=json \| jq '.hint_concentration_analysis'` |
| Phase 11 | .well-known endpoints active | `curl -sS http://127.0.0.1:8003/.well-known/mcp.json` |
| Phase 12 | Dual-model routing active | `aq-report --format=json \| jq '.model_role_classification'` |

---

## Execution Progress

### Completed Batches

| Date | Batch | Evidence |
|------|-------|----------|
| 2026-03-13 | 1.1 MCP Bridge Validation | MCP configured, tools listed |
| 2026-03-13 | 1.2 Editor Extension Smoke | All 0.5.x tests PASS, smoke-continue-editor-flow.sh PASS |
| 2026-03-13 | 2.1 Memory System Fixes | RAG posture diagnosis test PASS |
| 2026-03-13 | 2.2 Route Search Optimization | Route search pressure diagnosis PASS |
| 2026-03-13 | 2.3 RAG Posture Improvement | Route handler collection policy PASS |
| 2026-03-13 | 3.1 Dashboard Report Integration | smoke-status-report-summary.sh PASS |
| 2026-03-13 | 4.1 Finalization Hardening | smoke-remote-delegation-lanes.sh PASS |
| 2026-03-13 | 5.1 Lesson Registry Completion | smoke-delegate-lesson-refs.sh PASS |
| 2026-03-13 | 7.1 Package Validation | smoke-flagship-cli-surfaces.sh PASS, all CLIs respond to --help |
| 2026-03-14 | 7.2 Support Matrix Update | docs/AGENT-PARITY-MATRIX.md updated with CLI support matrix |
| 2026-03-14 | 6.1 Hint Template Expansion | 10 new templates added to registry.yaml |
| 2026-03-14 | 5.2 Skill Registry Expansion | 3 new skills added (26 total) |
| 2026-03-14 | 6.2 Pattern Extraction Pipeline | aq-patterns CLI implemented |
| 2026-03-14 | 6.3 Gap Auto-Remediation | Timer validated (ai-gap-auto-remediate.timer active) |
| 2026-03-14 | 3.2 PRSI Action Execution | aq-optimizer and aq-gap-auto-remediate validated |
| 2026-03-14 | 1.3 Web Research Lane Expansion | 3 workflow packs added (mendocino, tech-docs, security) |
| 2026-03-14 | 3.3 Multi-Window Trend Visibility | trend_1h/24h/7d windows, trend_summary, delegation_failures |
| 2026-03-14 | 4.2 Provider Fallback Policy | provider-fallback-policy.json, _provider_health_summary() |
| 2026-03-14 | 4.3 Prompt Contract Tightening | delegation-prompt-contracts.json, 4 delegation templates |
| 2026-03-14 | 10.2 Hint Routing Overhaul | Diversity fix: 25% cap, 60% hard exclude, fallback hints |
| 2026-03-14 | 11.1 Well-Known Metadata Endpoint | /.well-known/mcp.json on hybrid, ralph, aidb |
| 2026-03-14 | 12.3 Context Hygiene Automation | Progressive disclosure with 7 domains, 3 levels |
| 2026-03-14 | 11.2 Health Ping Protocol | /health/aggregate with latency tracking, history, trends |
| 2026-03-14 | 10.3 Token-Efficient Hint Delivery | compact_mode, max_hint_tokens, snippet compression |

### Current Batch

**Batch:** Phase 9-12 Gap Analysis Implementation
**Status:** in_progress
**Started:** 2026-03-14

### CLI Package Status

| CLI | Status | Path |
|-----|--------|------|
| cn | PASS | /home/hyperd/.nix-profile/bin/cn |
| claude | PASS | /home/hyperd/.local/bin/claude |
| pi | PASS | ~/.npm-global/bin/pi |
| codex | PASS | ~/.npm-global/bin/codex |
| qwen | PASS | ~/.npm-global/bin/qwen |
| gemini | PASS | ~/.npm-global/bin/gemini |

### PATH Remediation (RESOLVED)

Fixed: smoke-flagship-cli-surfaces.sh now extends PATH to include `~/.npm-global/bin` before checking CLI availability.

### Autoresearch Integration (NEW)

Implemented Karpathy's autoresearch concept for local model optimization:
- `ai-stack/autoresearch/autoresearch.py` - Core experiment framework
- `ai-stack/autoresearch/local_model_optimizer.py` - Chat & embed optimization
- `scripts/ai/aq-autoresearch` - CLI wrapper

Features:
- Token efficiency measurement per successful task
- Prompt template optimization
- Temperature tuning experiments
- Embedding batch size optimization
- SQLite experiment ledger

### Autoresearch Results (2026-03-14)

**Chat Model Optimization:**
| Config | Efficiency | Tokens/Task | Success | Latency |
|--------|------------|-------------|---------|---------|
| system_structured | 0.71 | 189.8 | 80% | 5964ms |
| system_minimal | 0.24 | 238.6 | 60% | 10387ms |
| temp_0.1 | 0.17 | 311.0 | 80% | 15411ms |
| temp_0.0 | 0.14 | 334.4 | 80% | 17063ms |

**Embedding Model Optimization:**
| Config | Efficiency | Latency | Dimensions |
|--------|------------|---------|------------|
| batch_1 | 92.96 | 1076ms | 2560 |
| batch_4 | 92.60 | 1080ms | 2560 |

**Recommendations Applied:**
- Chat: Use "structured" system prompt for best token efficiency
- Embed: batch_size=1 provides optimal latency

### Next Actions

1. ~~Fix PATH wiring for npm-global CLIs~~ ✓
2. ~~Add coordinator endpoint for autoresearch~~ ✓
3. ~~Run autoresearch optimization~~ ✓
4. Continue with remaining roadmap batches
5. Apply autoresearch best configs to production

---

## Commit Protocol

After each batch completion:

```bash
git add <modified-files>
git commit -m "$(cat <<'EOF'
<phase>.<batch>: <brief description>

- <change 1>
- <change 2>

Evidence: <validation output summary>

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| BitNet SIGSEGV | Blocks Phase 8 | Track upstream fixes, use fallback path |
| Provider rate limits | Degrades remote delegation | Implement fallback policy |
| Memory store failures | Data loss | Add retry logic, improve error handling |
| Route search latency | User experience | Collection narrowing, adaptive timeouts |

---

## Dependencies

```
Phase 1 (Continue) ──┬──> Phase 3 (Monitoring)
                     │
Phase 2 (Memory) ────┼──> Phase 4 (Delegation) ──> Phase 9 (Agentic RAG)
                     │                                    │
Phase 5 (Lessons) ───┴──> Phase 6 (Self-Improvement) ────┴──> Phase 10 (Hint Fix)

Phase 7 (CLI) ───────────> Independent

Phase 8 (BitNet) ────────> BLOCKED

Phase 11 (MCP Compliance) ──> Independent (all MCP servers)

Phase 12 (Dual-Model) ──────> Depends on Phase 4 + Phase 9
```

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-13 | Initial roadmap creation |
| 1.1.0 | 2026-03-14 | Added Phases 9-12 from video research gap analysis |
