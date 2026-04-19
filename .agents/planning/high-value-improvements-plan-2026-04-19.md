# High-Value AI Harness Improvements - Implementation Plan

**Date:** 2026-04-19
**Status:** Ready for Execution
**Priority:** P0 - Critical Path
**Owner:** Orchestrator (Claude Sonnet 4.5)

---

## Executive Summary

This plan identifies and sequences the highest-value improvements to the AI harness based on:
1. Current roadmap analysis ([ai-harness-enhancement-roadmap.md](.agents/planning/plans/ai-harness-enhancement-roadmap.md))
2. System state assessment (session-primer-summary.json)
3. Recent performance optimizations (route search 47s → 9s)
4. User-reported prompt understanding issues

**Total Estimated Effort:** 6-8 weeks
**Parallelization Opportunities:** Up to 3 agents can work concurrently on independent slices

---

## Priority 1: Phase 0 - Layer 1 Front-Door Routing (CRITICAL)

**Objective:** Make the local harness the stable first contact point for all human-to-LLM requests

**Why This is Highest Value:**
- Foundation for all other improvements
- Currently missing - no front-door routing layer
- Enables consistent routing policy across all entry points
- Reduces complexity for end users

**Success Criteria:**
- [ ] `Explore`, `Plan`, and `default` aliases map to harness profiles
- [ ] Local orchestrator handles all incoming requests
- [ ] Route selection is deterministic and auditable
- [ ] Integration with existing coordinator lanes works
- [ ] Documentation complete

### Slice 0.1: Route Alias Mapping System

**Owner:** qwen (implementation)
**Estimated Effort:** 3-4 days
**Priority:** P0 (blocks others)

**Scope:**
1. Create route alias mapping configuration in `config/route-aliases.json`
2. Implement alias resolver in hybrid coordinator
3. Map OpenClaude-style routes to existing harness profiles:
   - `default` → `default`
   - `Explore` → `default`
   - `Plan` → `default`
   - `Implementation` → `remote-coding`
   - `Reasoning` → `remote-reasoning`
   - `ToolCalling` → `local-tool-calling`
   - `Continuation` → `default`

**Deliverables:**
- [ ] `config/route-aliases.json` - Alias configuration
- [ ] `ai-stack/mcp-servers/hybrid-coordinator/route_aliases.py` - Resolver
- [ ] Unit tests for alias resolution
- [ ] Integration tests with coordinator

**Validation:**
- All aliases resolve correctly
- Backward compatibility preserved
- Performance: < 10ms overhead per request
- All tests pass

**Files:**
- Create: `config/route-aliases.json`
- Create: `ai-stack/mcp-servers/hybrid-coordinator/route_aliases.py`
- Create: `ai-stack/mcp-servers/hybrid-coordinator/tests/test_route_aliases.py`
- Update: `ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator.py`

**Commands:**
```bash
# Test
python -m pytest ai-stack/mcp-servers/hybrid-coordinator/tests/test_route_aliases.py -v

# Smoke test
curl -X POST http://127.0.0.1:8003/route \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "route_alias": "Explore"}' | jq
```

---

### Slice 0.2: Front-Door Request Handler

**Owner:** qwen (implementation)
**Estimated Effort:** 2-3 days
**Priority:** P0
**Depends on:** Slice 0.1

**Scope:**
1. Implement unified request ingress endpoint
2. Add request validation and sanitization
3. Integrate with route alias resolver
4. Add request logging and telemetry
5. Implement rate limiting (basic)

**Deliverables:**
- [ ] `/v1/orchestrate` unified endpoint
- [ ] Request validation middleware
- [ ] Integration with alias resolver
- [ ] Telemetry hooks

**Validation:**
- Requests route correctly through aliases
- Invalid requests rejected with clear errors
- Telemetry data captured
- All tests pass

**Files:**
- Update: `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
- Create: `ai-stack/mcp-servers/hybrid-coordinator/request_handler.py`
- Create: `ai-stack/mcp-servers/hybrid-coordinator/tests/test_request_handler.py`

**Commands:**
```bash
# Test
python -m pytest ai-stack/mcp-servers/hybrid-coordinator/tests/test_request_handler.py -v

# Integration test
curl -X POST http://127.0.0.1:8003/v1/orchestrate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test query", "route": "Explore"}' | jq
```

---

### Slice 0.3: Documentation & CLI Integration

**Owner:** qwen (documentation)
**Estimated Effort:** 1-2 days
**Priority:** P1
**Depends on:** Slice 0.2

**Scope:**
1. Document front-door routing system
2. Update LOCAL-AGENT-HARNESS-PRIMER.md
3. Update CLI tools to use new endpoint
4. Create usage examples

**Deliverables:**
- [ ] `docs/architecture/front-door-routing.md`
- [ ] Updated LOCAL-AGENT-HARNESS-PRIMER.md
- [ ] CLI integration examples

**Validation:**
- Documentation complete and accurate
- Examples tested and working
- CLI tools functional

**Files:**
- Create: `docs/architecture/front-door-routing.md`
- Update: `.agent/LOCAL-AGENT-HARNESS-PRIMER.md`
- Update: `scripts/ai/local-orchestrator`

---

## Priority 2: Local Agent Prompt Understanding Fix (CRITICAL)

**Objective:** Optimize system prompt and routing for Gemma 4 E4B model

**Why This is High Value:**
- User-reported issue: agent "not being able to execute and understand prompts"
- Gemma 4 E4B (7.5B quantized) has limitations with complex instructions
- Current system prompt is 216 lines - may be too verbose
- Direct impact on user experience

**Root Causes Identified:**
1. System prompt complexity (216 lines, multiple JSON schemas)
2. Model size limitations (7.5B vs 70B+ models)
3. Potential context window issues
4. Routing layer adding complexity

### Slice 1.1: System Prompt Optimization

**Owner:** claude (architecture + writing)
**Estimated Effort:** 2-3 days
**Priority:** P0

**Scope:**
1. Analyze current system prompt effectiveness
2. Create simplified version optimized for Gemma 4
3. Test with sample queries
4. Create A/B test framework
5. Document optimization guidelines

**Deliverables:**
- [ ] `ai-stack/local-orchestrator/system-prompt-v2-optimized.md` - Simplified prompt
- [ ] `ai-stack/local-orchestrator/system-prompt-evaluation.md` - Analysis doc
- [ ] A/B test results
- [ ] Optimization guidelines

**Validation:**
- Prompt length < 100 lines
- Test queries succeed at 90%+ rate
- Maintains all critical capabilities
- Performance improves vs baseline

**Files:**
- Create: `ai-stack/local-orchestrator/system-prompt-v2-optimized.md`
- Create: `docs/architecture/system-prompt-optimization.md`
- Create: `scripts/testing/test-prompt-effectiveness.py`

**Optimization Strategy:**
```markdown
BEFORE: 216 lines with detailed JSON schemas, multiple examples
AFTER: ~80 lines with:
- Core identity (10 lines)
- Essential tools (20 lines)
- Routing rules (15 lines)
- Response format (15 lines)
- Critical constraints (20 lines)
```

---

### Slice 1.2: Context Injection Optimization

**Owner:** qwen (implementation)
**Estimated Effort:** 2-3 days
**Priority:** P0
**Depends on:** Slice 1.1

**Scope:**
1. Implement progressive context loading
2. Add context relevance filtering
3. Optimize context compression
4. Implement context caching

**Deliverables:**
- [ ] Progressive context loader
- [ ] Relevance filtering system
- [ ] Context cache with TTL
- [ ] Performance benchmarks

**Validation:**
- Context size reduced by 40%+
- Relevance score > 0.8 for injected context
- Cache hit rate > 60%
- Response time improves by 30%+

**Files:**
- Create: `ai-stack/local-orchestrator/context_optimizer.py`
- Update: `ai-stack/local-orchestrator/orchestrator.py`
- Create: `ai-stack/local-orchestrator/tests/test_context_optimizer.py`

---

### Slice 1.3: Prompt Understanding Validation Suite

**Owner:** codex (testing)
**Estimated Effort:** 2-3 days
**Priority:** P1
**Depends on:** Slice 1.1, Slice 1.2

**Scope:**
1. Create comprehensive test corpus (100+ prompts)
2. Build automated evaluation framework
3. Benchmark before/after optimization
4. Document regression test suite

**Deliverables:**
- [ ] Test corpus in `test-data/prompt-understanding-corpus.json`
- [ ] Automated evaluation script
- [ ] Baseline vs optimized comparison
- [ ] CI integration

**Validation:**
- 100+ test prompts covering all use cases
- Automated scoring framework
- Improvement > 25% in understanding metrics
- Tests run in CI

**Files:**
- Create: `test-data/prompt-understanding-corpus.json`
- Create: `scripts/testing/evaluate-prompt-understanding.py`
- Update: `.github/workflows/prompt-understanding-tests.yml`

---

## Priority 3: Complete Phase 2.3 - Workflow Executor (HIGH)

**Objective:** Finish workflow executor implementation to enable deterministic task execution

**Why This is High Value:**
- Already partially implemented (parser done, executor in progress)
- Enables automated workflow execution
- Reduces manual orchestration overhead
- Foundation for Phase 3 (parallel execution)

**Status:**
- Slice 2.2 (Parser) ✅ Complete
- Slice 2.3 (Executor) ⏳ In Progress (blocked by remote rate limits)

### Slice 2.3-Resume: Complete Workflow Executor

**Owner:** qwen (implementation)
**Estimated Effort:** 4-5 days
**Priority:** P0
**Current Blocker:** Remote rate limits - Use local fallback

**Scope:**
1. Complete executor node handlers (agent, bash, approval, loop)
2. Implement context passing between nodes
3. Add error handling and recovery
4. Complete run state persistence
5. Test with local-only execution paths

**Deliverables:**
- [ ] Complete `ai-stack/workflows/executor.py`
- [ ] Complete `ai-stack/workflows/nodes.py`
- [ ] Complete `ai-stack/workflows/context.py`
- [ ] Complete `ai-stack/workflows/persistence.py`
- [ ] Integration tests (local execution only)

**Validation:**
- All node types execute correctly
- Context flows between nodes
- Errors handled gracefully
- State persists across failures
- Local-only execution passes all tests

**Files:**
- Update: `ai-stack/workflows/executor.py`
- Update: `ai-stack/workflows/nodes.py`
- Update: `ai-stack/workflows/context.py`
- Update: `ai-stack/workflows/persistence.py`
- Create: `ai-stack/workflows/tests/test_executor_complete.py`

**Local Fallback Strategy:**
Use `harness-rpc.js agent-spawn` for local sub-agent execution instead of remote delegation:
```bash
node scripts/ai/harness-rpc.js agent-spawn \
  --role coordinator \
  --task "bounded task" \
  --max-tokens 512 \
  --timeout 20
```

---

### Slice 2.4-Continue: Hybrid Coordinator Integration

**Owner:** codex (integration)
**Estimated Effort:** 3-4 days
**Priority:** P0
**Depends on:** Slice 2.3-Resume

**Scope:**
1. Complete coordinator integration from Phase 2.4 scope
2. Map workflow profiles to coordinator lanes
3. Add workflow execution endpoints
4. Test full stack integration

**Deliverables:**
- [ ] Complete coordinator integration
- [ ] Workflow endpoints functional
- [ ] Full stack integration tests
- [ ] Performance validation

**Validation:**
- Workflows execute through coordinator
- Profile mapping works correctly
- No regression in existing delegation
- Performance overhead < 10%

**Files:**
- Update: `ai-stack/mcp-servers/hybrid-coordinator/workflow_integration.py`
- Update: `scripts/ai/harness-rpc.js`
- Create: `ai-stack/workflows/tests/test_coordinator_integration_complete.py`

---

## Priority 4: Phase 1 Memory Foundation - Remaining Slices (MEDIUM)

**Objective:** Complete memory system implementation for enhanced context and recall

**Status:**
- Slice 1.1 ✅ Complete (Architecture)
- Slice 1.2, 1.3, 1.4, 1.5 - Ready for implementation
- Slice 1.6 - Documentation

**Note:** These can be executed in parallel with Priority 1-3 work

### Slice 1.2: Temporal Validity Implementation

**Owner:** qwen (implementation)
**Estimated Effort:** 5-6 days
**Priority:** P1

**Scope:** Implement temporal fact storage with validity windows and staleness detection

**Deliverables:**
- [ ] `ai-stack/aidb/temporal_facts.py`
- [ ] `ai-stack/aidb/temporal_query.py`
- [ ] Unit and integration tests
- [ ] Performance validation (< 100ms queries)

---

### Slice 1.3: Metadata Filtering System

**Owner:** qwen (implementation)
**Estimated Effort:** 4-5 days
**Priority:** P1
**Can run in parallel with:** Slice 1.2

**Scope:** Implement metadata tagging and filtering for improved search precision

**Deliverables:**
- [ ] `ai-stack/aidb/metadata_filter.py`
- [ ] Enhanced search API
- [ ] Performance tests
- [ ] 20%+ precision improvement validation

---

### Slice 1.4: Memory CLI Tool Suite

**Owner:** qwen (implementation)
**Estimated Effort:** 3-4 days
**Priority:** P1
**Depends on:** Slice 1.2, 1.3

**Scope:** Create `aq-memory` CLI for user-facing memory operations

**Deliverables:**
- [ ] `scripts/ai/aq-memory` CLI tool
- [ ] Bash completion
- [ ] Integration with aq-session-zero

---

### Slice 1.5: Memory Benchmark Harness

**Owner:** codex (testing)
**Estimated Effort:** 4-5 days
**Priority:** P1
**Depends on:** Slice 1.2, 1.3, 1.4

**Scope:** Create comprehensive benchmarking suite for memory system

**Deliverables:**
- [ ] Benchmark corpus (500+ fact-query pairs)
- [ ] Automated benchmark scripts
- [ ] Baseline metrics documentation
- [ ] CI integration

---

## Priority 5: Phase 3 - Execution Isolation (MEDIUM-LOW)

**Objective:** Enable parallel workflow execution via git worktree isolation

**Dependencies:** Phase 2 must be complete first

**Status:** Not started

**Slices:** 3.1 through 3.6 (see roadmap for details)

**Note:** Lower priority - defer until Phase 0, 2.3, and prompt fixes are complete

---

## Execution Strategy

### Parallelization Plan

**Week 1-2: Critical Foundation**
- Agent 1 (qwen): Slice 0.1 + 0.2 (Front-Door Routing)
- Agent 2 (claude): Slice 1.1 (System Prompt Optimization)
- Agent 3 (codex): Phase state assessment + validation prep

**Week 3-4: Core Improvements**
- Agent 1 (qwen): Slice 1.2 (Context Injection) + Slice 2.3-Resume (Workflow Executor)
- Agent 2 (qwen): Slice 1.2 (Temporal Validity)
- Agent 3 (codex): Slice 1.3 (Prompt Validation Suite)

**Week 5-6: Integration & Memory**
- Agent 1 (qwen): Slice 2.4-Continue (Coordinator Integration)
- Agent 2 (qwen): Slice 1.3 (Metadata Filtering) + Slice 1.4 (Memory CLI)
- Agent 3 (codex): Slice 1.5 (Benchmark Harness)

**Week 7-8: Polish & Validation**
- Agent 1 (qwen): Documentation for all slices
- Agent 2 (codex): Full integration testing
- Agent 3 (claude): Architecture review and optimization recommendations

### Delegation Protocol

For each slice:
1. **Prepare Context** - Gather relevant files, constraints, acceptance criteria
2. **Create Task Contract** - Define deliverables, validation, rollback
3. **Delegate to Agent** - Use appropriate agent profile (qwen/codex/claude)
4. **Validate Output** - Run tests, check syntax, verify acceptance criteria
5. **Approve & Commit** - Git commit with conventional format + Co-Authored-By trailer
6. **Update Progress** - Mark slice complete in tracking

### Validation Gates

Before marking any slice complete:
- [ ] All deliverables created
- [ ] Syntax checks pass (`bash -n`, `python -m py_compile`, `nix-instantiate`)
- [ ] Unit tests pass
- [ ] Integration tests pass (where applicable)
- [ ] Lint checks pass (`repo-structure-lint.sh --staged`)
- [ ] Git commit with evidence
- [ ] Documentation updated

---

## Risk Management

### High-Risk Areas

1. **System Prompt Optimization** - May reduce capabilities if oversimplified
   - Mitigation: A/B testing, incremental rollout, rollback plan

2. **Workflow Executor Complexity** - Error handling edge cases
   - Mitigation: Comprehensive test suite, local-only testing first

3. **Memory System Performance** - Temporal queries may be slow
   - Mitigation: Early benchmarking, index optimization, caching

### Rollback Plans

All changes use:
- Feature flags (can disable without code changes)
- Versioned system prompts (can revert)
- Git discipline (all changes committed with clear history)
- Validation gates (prevent broken code from merging)

---

## Success Metrics

### Phase 0 Success Criteria
- [ ] All route aliases functional
- [ ] Front-door routing handles 100% of requests
- [ ] Routing overhead < 10ms
- [ ] Zero regressions in existing functionality

### Prompt Understanding Success Criteria
- [ ] System prompt < 100 lines
- [ ] Test corpus success rate > 90%
- [ ] Context size reduced 40%+
- [ ] Response time improved 30%+

### Workflow Executor Success Criteria
- [ ] All node types execute correctly
- [ ] Local execution works without remote calls
- [ ] State persistence works
- [ ] Integration tests pass

### Memory System Success Criteria
- [ ] Recall accuracy > 85% (90%+ with metadata)
- [ ] Query latency < 500ms p95
- [ ] CLI tools functional
- [ ] Benchmark suite operational

---

## Next Steps

1. **Start with Priority 1 (Phase 0):** Front-door routing is the foundation
2. **Parallel Priority 2 (Prompt Fix):** Critical for user experience
3. **Resume Priority 3 (Workflow Executor):** Already in progress
4. **Background Priority 4 (Memory):** Can proceed in parallel
5. **Defer Priority 5 (Isolation):** Wait for Phase 2 completion

**Immediate Actions:**
```bash
# 1. Start Phase 0 Slice 0.1
# Delegate to qwen for route alias mapping implementation

# 2. Start Prompt Optimization Slice 1.1
# Delegate to claude for system prompt analysis and rewrite

# 3. Prepare validation infrastructure
# Delegate to codex for test framework setup
```

---

**Document Version:** 1.0.0
**Created:** 2026-04-19
**Owner:** Orchestrator (Claude Sonnet 4.5)
**Next Review:** After each priority completion
**Total Estimated Duration:** 6-8 weeks with 2-3 agents working in parallel
