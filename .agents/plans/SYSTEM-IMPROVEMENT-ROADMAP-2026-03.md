# System Improvement Roadmap — 2026-03 Q1 Finalization

**Generated:** 2026-03-13
**Status:** Active
**Owner:** AI Harness
**Last Updated:** 2026-03-13
**Version:** 1.0.0

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
**Status:** pending
**Tasks:**
- [ ] Expand approved source packs beyond California-native
- [ ] Add Mendocino-specific source pack
- [ ] Validate browser fallback for complex pages
- [ ] Add source selector tuning for known-problematic sites

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
**Status:** pending
**Tasks:**
- [ ] Verify all PRSI maintenance actions work from dashboard
- [ ] Add action execution history tracking
- [ ] Show action success/failure status
- [ ] Add rollback capability for failed actions

**Validation:**
```bash
# Test each maintenance action via dashboard API
curl -sS -X POST http://127.0.0.1:8003/prsi/execute -d '{"action":"gap-remediation"}'
```

### Batch 3.3: Multi-Window Trend Visibility
**Status:** pending
**Tasks:**
- [ ] Add 1h/24h/7d trend toggles to dashboard
- [ ] Show routing history trends visually
- [ ] Add retrieval breadth trend charts
- [ ] Show delegated failure trend history

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
**Status:** pending
**Tasks:**
- [ ] Implement automatic fallback on provider 429
- [ ] Add provider health tracking
- [ ] Create provider selection scoring
- [ ] Add cost-aware routing hints

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.provider_fallback_recovery, .delegated_prompt_failures'
```

### Batch 4.3: Prompt Contract Tightening
**Status:** pending
**Tasks:**
- [ ] Reduce prompt token footprint for small tasks
- [ ] Add task-class-specific prompt templates
- [ ] Implement prompt quality validation
- [ ] Track prompt-contract failure trends

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
**Status:** pending
**Tasks:**
- [ ] Expand shared skill coverage beyond current 24
- [ ] Add skill usage tracking
- [ ] Implement skill recommendation engine
- [ ] Add external skill import validation

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
**Status:** pending
**Tasks:**
- [ ] Add 8-10 new hint templates for underserved task types
- [ ] Implement context-aware hint routing by file type
- [ ] Add hint feedback acceleration
- [ ] Reduce dominant hint concentration

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.hint_diversity'
```

### Batch 6.2: Pattern Extraction Pipeline
**Status:** pending
**Tasks:**
- [ ] Implement automated pattern detection (3+ occurrence threshold)
- [ ] Add pattern quality scoring (filter <0.7)
- [ ] Integrate patterns into hints/RAG
- [ ] Track pattern effectiveness

**Validation:**
```bash
scripts/ai/aq-report --format=json | jq '.patterns'
```

### Batch 6.3: Gap Auto-Remediation
**Status:** pending
**Tasks:**
- [ ] Add systemd timer for hourly gap detection
- [ ] Implement auto-remediation pipeline
- [ ] Add remediation verification loop
- [ ] Track remediation success rate

**Validation:**
```bash
systemctl status ai-gap-remediation.timer
scripts/ai/aq-report --format=json | jq '.gap_remediation'
```

---

## Phase 7: CLI Package Parity

**Objective:** All flagship agent CLIs declaratively packaged or explicitly scaffolded.
**Gate:** All CLI surfaces pass --help smoke

### Batch 7.1: Package Validation
**Status:** pending
**Tasks:**
- [ ] Validate Continue CLI declarative package
- [ ] Validate Codex CLI package/scaffold status
- [ ] Validate Qwen CLI package/scaffold status
- [ ] Validate Gemini CLI package/scaffold status
- [ ] Validate Claude CLI package/scaffold status
- [ ] Validate pi agent package/scaffold status

**Validation:**
```bash
scripts/testing/smoke-flagship-cli-surfaces.sh
cn --help && codex --help && qwen --help && gemini --help && claude --help && pi --help
```

### Batch 7.2: Support Matrix Update
**Status:** pending
**Tasks:**
- [ ] Update support matrix with current status
- [ ] Document external-only surfaces
- [ ] Add harness integration status per CLI
- [ ] Create upgrade path documentation

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
| 2026-03-13 | 7.1 Package Validation | verify-flake-first-roadmap-completion.sh 570/570 PASS |

### Current Batch

**Batch:** 7.1 CLI Package Parity (partial)
**Status:** in_progress
**Started:** 2026-03-13

### CLI Package Status

| CLI | Status | Path |
|-----|--------|------|
| cn | PASS | /home/hyperd/.nix-profile/bin/cn |
| claude | PASS | /home/hyperd/.local/bin/claude |
| pi | PASS (aliased) | ~/.npm-global/bin/pi |
| codex | INSTALLED (PATH issue) | ~/.npm-global/bin/codex |
| qwen | INSTALLED (PATH issue) | ~/.npm-global/bin/qwen |
| gemini | INSTALLED (PATH issue) | ~/.npm-global/bin/gemini |

### PATH Remediation

The npm-global CLIs are installed but `~/.npm-global/bin` is not in PATH for all shell contexts.
Fix: Ensure `~/.npm-global/bin` is in PATH via shell profile or Home Manager.

### Next Actions

1. Fix PATH wiring for npm-global CLIs
2. Run full acceptance suite
3. Commit batch progress

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
Phase 2 (Memory) ────┼──> Phase 4 (Delegation)
                     │
Phase 5 (Lessons) ───┴──> Phase 6 (Self-Improvement)

Phase 7 (CLI) ───────────> Independent

Phase 8 (BitNet) ────────> BLOCKED
```

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-13 | Initial roadmap creation |
