# AI Harness Performance Optimization - Refactored Prompt

**Date:** 2026-04-09
**Based On:** Local agent analysis and aq-report findings
**Target:** Reduce reasoning latency by 50%+ (P95: 26,963ms → <13,500ms)

---

## Structured Optimization Prompt

### Objective
Optimize AI harness performance by reducing reasoning latency, specifically targeting:
- `route_search`: P95 = 22,544ms
- `ai_coordinator_delegate`: P95 = 29,875ms (28.6% success rate)
- `recall_agent_memory`: P95 = 4,336ms

### Constraints
1. **No broad reasoning** for format/lookup queries
   - Direct lookups should bypass reasoning entirely
   - Use cached results when available (current hit rate: 75.1%)
2. **Context limit**: 1024 tokens maximum per query
   - Current: unlimited (causing bloat)
   - Target: lean context with progressive disclosure
3. **Token plan**: 600 tokens per response (lean mode)
4. **Safety**: Maintain 100% success rate for critical paths

### Context

**Current Performance (7d window):**
```
Tool                    P50ms   P95ms    Success%  Volume
route_search             1315  22,544     100.0%     865
ai_coordinator_delegate   228  29,875      28.6%       7
recall_agent_memory        39   4,336     100.0%     320
hints                     147     288     100.0%    4171
```

**Known Gaps:**
- Lesson ref parity smoke harness eval (needs import to AIDB)
- High variance in delegation (71.4% failure rate)
- Route search doing full semantic search even for simple lookups

**System Health:**
- ✅ 100% local routing (no remote overhead)
- ✅ 75.1% cache hit rate
- ✅ Continue/Editor: 100% healthy
- ❌ Delegation success: only 28.6%

### Validation Criteria
1. Reasoning latency reduced by **at least 50%** (P95 < 13,500ms)
2. Measured across **305+ calls** minimum
3. Success rate maintained at **≥95%** for all tools
4. Cache hit rate improved to **≥80%**

### Route
**Primary:** codex (integration + optimization)
**Support:** qwen (implementation if needed)

### Implementation Strategy

**Phase 1: Fast-Path Optimization (Week 1)**
1. Add direct lookup bypass for route_search
   - Pattern matching for simple queries
   - Cache-first strategy
   - Fallback to semantic search only if needed

2. Fix ai_coordinator_delegate failures
   - Add retry logic with exponential backoff
   - Better error handling
   - Validate session state before delegation

**Phase 2: Context Reduction (Week 1-2)**
1. Implement 1024-token context limit
   - Use multi-layer loading (L0-L3) from Phase 1.5
   - Progressive disclosure based on query type
   - Compact representations for common data

2. Optimize recall_agent_memory
   - Pre-filter by metadata before vector search
   - Limit results to top-K most relevant
   - Use temporal validity to prune stale facts

**Phase 3: Knowledge Import & Validation (Week 2)**
1. Import missing knowledge
   ```bash
   # Import lesson ref parity data
   curl -X POST http://127.0.0.1:8002/api/knowledge/import \
     -H "Content-Type: application/json" \
     -d '{
       "query": "lesson ref parity smoke harness eval",
       "source": "harness-eval-logs",
       "confidence": 0.9
     }'
   ```

2. Validate with aq-qa and aq-report
   ```bash
   # Baseline measurement
   aq-report --since=1d --format=json > baseline.json

   # Run optimization
   # ... apply changes ...

   # Post-optimization measurement
   aq-report --since=1d --format=json > optimized.json

   # Compare
   python3 scripts/ai/compare-reports.py baseline.json optimized.json
   ```

---

## Expected Outcomes

### Performance Targets
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| route_search P95 | 22,544ms | <10,000ms | 56%+ |
| delegate P95 | 29,875ms | <15,000ms | 50%+ |
| recall P95 | 4,336ms | <2,000ms | 54%+ |
| Success rate | 28.6% (delegate) | >95% | 233%+ |
| Cache hit rate | 75.1% | >80% | 6%+ |

### Code Changes Required
1. `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
   - Add fast-path routing for simple queries
   - Implement context size limits

2. `ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py`
   - Optimize hint generation
   - Use compact representations

3. `ai-stack/aidb/temporal_query.py`
   - Add metadata pre-filtering
   - Implement top-K result limiting

4. `ai-stack/mcp-servers/hybrid-coordinator/workflow_executor.py`
   - Add delegation retry logic
   - Better error recovery

---

## Automation Script

See: `scripts/ai/optimize-and-validate.sh` (to be created)

---

## References
- [aq-report output](../../.agent/workflows/aq-report-2026-04-09.txt)
- [Phase 1.5: Multi-Layer Loading](../../.agents/plans/MASTER-ROADMAP-2026-04-09.md#phase-15)
- [Workflow Executor Integration](../../docs/architecture/workflow-executor-integration.md)
