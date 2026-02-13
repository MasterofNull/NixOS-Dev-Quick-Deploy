# Token Optimization Analysis
## Understanding Remote Agent Token Consumption

**Date:** January 23, 2026
**Goal:** Reduce Anthropic API token usage by optimizing local AI stack

---

## Architecture Overview

```
Remote Agent (Claude Code, etc.)
    ↕ MCP Protocol
    └─ Anthropic API (costs money)

Local AI Stack (your hardware - free)
    ├─ llama.cpp (local LLM - free)
    ├─ Hybrid Coordinator (context filtering)
    ├─ Qdrant (vector DB)
    └─ Redis (caching)
```

**The Problem:** Local AI stack is sending TOO MUCH context or requiring TOO MANY round-trips, causing remote agents to consume excessive API tokens.

---

## Feature Analysis

### ✅ GOOD Features (Reduce Remote Token Usage)

#### 1. Context Compression (`context_compression.py`)
**What it does:**
- Compresses retrieved context to fit token budgets
- Sorts by relevance, keeps only best matches
- Strategies: truncate, summarize, hybrid

**Token Impact:**
```python
# Example: 5000 tokens of context compressed to 1000 tokens
contexts = get_from_vector_db(query)  # Returns 5000 tokens
compressed = compressor.compress_to_budget(contexts, max_tokens=1000)
# Remote agent only receives 1000 tokens
# SAVINGS: 4000 tokens per query
```

**Verdict:** ✅ **KEEP - This is excellent!**

**Optimization Opportunity:**
- Currently uses 4 chars = 1 token estimate (line 30)
- Could use tiktoken for more accurate counting
- Could add more aggressive compression modes

---

#### 2. Progressive Disclosure (`progressive_disclosure.py`)
**What it does:**
- Three disclosure levels:
  - **Overview:** 100-300 tokens (capability categories only)
  - **Detailed:** 300-800 tokens (capabilities with examples)
  - **Comprehensive:** 800-2000 tokens (full specs)

**Token Impact:**
```python
# Remote agent starts with minimal info
response = await discover(level="overview")  # Only 200 tokens
# If needed, requests more detail
response = await discover(level="detailed", categories=["rag"])  # 500 tokens
# Total: 700 tokens instead of 2000 tokens upfront
# SAVINGS: 1300 tokens when remote agent doesn't need full detail
```

**Verdict:** ✅ **KEEP - This is exactly what we want!**

**Current Status:** ✅ Implemented and working

---

#### 3. Semantic Caching (Redis)
**What it does:**
- Caches responses to similar queries
- Avoids re-processing same requests

**Token Impact:**
```python
# First query: Full processing
response = await get_context("NixOS error")  # 1500 tokens sent to remote

# Second similar query: Cached
response = await get_context("NixOS errors")  # 0 tokens (cache hit)
# SAVINGS: 1500 tokens on cache hit
```

**Verdict:** ✅ **KEEP - Expand cache coverage**

**Optimization Opportunity:**
- Increase cache TTL (currently varies by endpoint)
- Implement smarter cache invalidation
- Add cache warming for common queries

---

### ❌ BAD Features (Increase Remote Token Usage)

#### 1. Query Expansion (`query_expansion.py`) **← MAJOR ISSUE**
**What it does:**
- Expands 1 query into 3-5 queries
- Example: "NixOS error" → ["NixOS error", "NixOS issue", "NixOS problem", "NixOS failure", "NixOS exception"]
- Searches vector DB with ALL expanded queries
- Returns combined results

**Token Impact:**
```python
# Without query expansion:
contexts = search_vector_db("NixOS error")  # Returns 1000 tokens

# With query expansion (current):
queries = expand_query("NixOS error")  # ['NixOS error', 'NixOS issue', 'NixOS problem', ...]
contexts = []
for q in queries:  # 5 queries
    contexts += search_vector_db(q)  # 1000 tokens each
# Returns 5000 tokens total
# Remote agent has to process 5x more data
# WASTE: 4000 unnecessary tokens
```

**Verdict:** ❌ **DISABLE - This is killing remote token budget**

**Why it exists:**
- Improves recall (finds more relevant docs)
- Useful for local-only use cases

**Why it's bad for remote agents:**
- Returns 3-5x more context than needed
- Most expanded queries are redundant
- Remote agent pays for processing ALL results

**Recommendation:**
- ❌ DISABLE by default
- ⚠️ Make opt-in for specific use cases
- ✅ Use smarter expansion (max 2 expansions, not 5)

**Configuration:**
```bash
# .env
QUERY_EXPANSION_ENABLED=false  # Disable by default
QUERY_EXPANSION_MAX=2  # If enabled, max 2 expansions (not 5)
```

---

#### 2. Remote LLM Feedback (`remote_llm_feedback.py`) **← CREATES LOOPS**
**What it does:**
- Allows remote agents to report confidence and request more context
- Creates feedback loops: Remote → Local → Remote → Local

**Token Impact:**
```python
# Turn 1: Initial query
remote_agent → local_stack: "Find NixOS error solutions"
local_stack → remote_agent: 1500 tokens of context

# Turn 2: Remote agent uses Anthropic API to process
remote_agent → anthropic_api: 1500 tokens  # $$$ COST

# Turn 3: Remote agent requests more (via feedback API)
remote_agent → local_stack: "I need more detail on systemd"
local_stack → remote_agent: 1500 tokens more

# Turn 4: Remote agent processes again
remote_agent → anthropic_api: 3000 tokens total  # $$$ MORE COST

# Total Anthropic API usage: 3000 tokens (2 round-trips)
# vs 1500 tokens (1 round-trip)
# WASTE: 1500 additional tokens per feedback loop
```

**Verdict:** ❌ **DISABLE by default - Make opt-in only**

**Why it exists:**
- Enables "Recursive Language Model" pattern
- Allows remote agents to iteratively refine context

**Why it's bad:**
- Each feedback loop = 1 additional Anthropic API call
- Doubles or triples token usage
- Most queries don't need this

**Recommendation:**
- ❌ DISABLE by default
- ⚠️ Only enable if remote agent explicitly requests it
- ✅ Add cost warning when enabled

**Configuration:**
```bash
# .env
REMOTE_LLM_FEEDBACK_ENABLED=false  # Disable by default
```

---

### ⚠️ NEUTRAL Features (Need Optimization)

#### 1. Multi-Turn Context Manager (`multi_turn_context.py`)
**What it does:**
- Tracks session state across multiple requests
- Avoids re-sending same context (GOOD)
- But uses QueryExpansionReranking (BAD)

**Token Impact:**
```python
# GOOD: Deduplication
# Turn 1:
contexts = get_context(query="NixOS error")  # Sends 1500 tokens
session.context_sent = ["ctx1", "ctx2", "ctx3"]

# Turn 2:
contexts = get_context(query="systemd issue",
                       previous_context_ids=["ctx1", "ctx2", "ctx3"])
# Only sends NEW contexts (500 tokens), not duplicates
# SAVINGS: 1000 tokens (avoided re-sending)

# BAD: Uses query expansion
# Line 96: self.query_expander = QueryExpansionReranking(llama_cpp_url)
# This means each turn does 3-5x query expansion
# WASTE: Negates the savings from deduplication
```

**Verdict:** ⚠️ **KEEP but fix query expansion**

**Recommendation:**
- ✅ KEEP session tracking and deduplication
- ❌ DISABLE query expansion within multi-turn context
- ✅ Use simple semantic search instead

**Configuration:**
```bash
# .env
MULTI_TURN_CONTEXT_ENABLED=true  # Keep this
MULTI_TURN_QUERY_EXPANSION=false  # Disable query expansion within it
```

---

#### 2. Continuous Learning (`continuous_learning.py`)
**What it does:**
- Runs in background
- Extracts patterns from telemetry
- Generates fine-tuning datasets
- Improves local LLM over time

**Token Impact:**
```python
# Direct impact: 0 (runs in background, doesn't affect queries)
# Indirect impact: Potentially reduces tokens long-term if learning improves filtering

# HOWEVER: Pattern extraction may use query expansion internally
# Need to verify this
```

**Verdict:** ⚠️ **KEEP but monitor**

**Questions:**
- Does pattern extraction use query expansion? (Need to check)
- Is the learning actually improving context filtering?
- Or is it just collecting data without improving results?

**Recommendation:**
- ✅ KEEP continuous learning
- ❌ DISABLE pattern extraction if it uses query expansion
- 📊 ADD metrics to track if learning is improving results

**Configuration:**
```bash
# .env
CONTINUOUS_LEARNING_ENABLED=true  # Keep background learning
PATTERN_EXTRACTION_ENABLED=false  # Disable if it uses query expansion
PATTERN_EXTRACTION_USE_EXPANSION=false  # Ensure no expansion
```

---

## Token Budget Configuration

### Current Default Token Budgets

| Endpoint | Current Default | Status |
|----------|----------------|--------|
| `get_context` | 2000 tokens | ⚠️ Too high |
| Progressive Disclosure (overview) | 300 tokens | ✅ Good |
| Progressive Disclosure (detailed) | 800 tokens | ✅ Good |
| Progressive Disclosure (comprehensive) | 2000 tokens | ⚠️ Too high |
| Multi-turn context | 2000 tokens | ⚠️ Too high |

### Recommended Token Budgets

| Endpoint | Recommended | Reasoning |
|----------|------------|-----------|
| `get_context` | 1000 tokens | Most queries don't need 2000 |
| Progressive Disclosure (overview) | 200 tokens | Even less upfront |
| Progressive Disclosure (detailed) | 600 tokens | Reduce by 25% |
| Progressive Disclosure (comprehensive) | 1500 tokens | Reduce by 25% |
| Multi-turn context | 1000 tokens | Match get_context |

**Estimated Savings:** 40-50% reduction in tokens per query

---

## Optimization Plan

### Phase 1: Immediate Wins (Day 1)

**1. Disable Query Expansion**
```bash
# ai-stack/compose/.env
QUERY_EXPANSION_ENABLED=false
```
**Expected Savings:** 60-70% reduction (queries currently return 3-5x more data)

**2. Disable Remote LLM Feedback**
```bash
# ai-stack/compose/.env
REMOTE_LLM_FEEDBACK_ENABLED=false
```
**Expected Savings:** Eliminates 1-2 extra round-trips per query = 50-100% reduction

**3. Reduce Default Token Budgets**
```bash
# ai-stack/compose/.env
DEFAULT_MAX_TOKENS=1000  # Down from 2000
PROGRESSIVE_DISCLOSURE_OVERVIEW_MAX=200  # Down from 300
PROGRESSIVE_DISCLOSURE_DETAILED_MAX=600  # Down from 800
PROGRESSIVE_DISCLOSURE_COMPREHENSIVE_MAX=1500  # Down from 2000
```
**Expected Savings:** 40-50% reduction per query

**Total Expected Savings (Phase 1):** 70-80% reduction in remote token usage

---

### Phase 2: Optimization (Week 1-2)

**1. Improve Context Compression**
- Use tiktoken for accurate token counting (currently uses 4 chars = 1 token estimate)
- Add more aggressive compression modes
- Implement extractive summarization using local llama.cpp

**2. Expand Caching**
- Increase cache TTL from 1 hour to 24 hours for stable content
- Implement query normalization for better cache hits
- Add cache warming for common queries

**3. Optimize Multi-Turn Context**
- Disable query expansion within multi-turn sessions
- Implement smarter deduplication (semantic similarity, not just ID matching)
- Add token budget tracking per session

**4. Monitor Continuous Learning**
- Add metrics: Does learning improve context relevance?
- Measure: Are learned patterns reducing context size?
- If yes: Keep. If no: Disable pattern extraction.

---

### Phase 3: Advanced Optimization (Week 3-4)

**1. Implement Context Ranking**
- Use local llama.cpp to rank contexts by relevance
- Send only top-N results to remote agent
- Remote agent gets best results, not all results

**2. Add Context Streaming**
- Send context in chunks, not all at once
- Remote agent can request stop when it has enough
- Saves tokens when agent doesn't need full context

**3. Implement Query Intent Classification**
- Use local llama.cpp to classify query intent
- Route different intents to different context strategies
- Example: "What is X?" → Send definition only (100 tokens)
- Example: "How to fix X?" → Send solution (500 tokens)
- Example: "Deep dive on X" → Send comprehensive (1500 tokens)

---

## Measurement & Validation

### Metrics to Track

**Before Optimization:**
- Average tokens per query sent to remote agent
- Number of round-trips per task
- Cache hit rate
- Remote agent satisfaction (does it have enough context?)

**After Optimization:**
- Same metrics as above
- Token savings per query
- Token savings per day
- Cost savings (if using paid API)

### Success Criteria

- ✅ 70%+ reduction in tokens per query
- ✅ No increase in round-trips (ideally decrease)
- ✅ Cache hit rate >40%
- ✅ Remote agent still gets sufficient context (quality not degraded)

---

## Configuration Summary

### Environment Variables to Add/Change

```bash
# ai-stack/compose/.env

# Query Expansion (DISABLE - major token waste)
QUERY_EXPANSION_ENABLED=false
QUERY_EXPANSION_MAX_EXPANSIONS=2  # If re-enabled, limit to 2 not 5

# Remote LLM Feedback (DISABLE - creates loops)
REMOTE_LLM_FEEDBACK_ENABLED=false

# Multi-Turn Context (KEEP but optimize)
MULTI_TURN_CONTEXT_ENABLED=true
MULTI_TURN_QUERY_EXPANSION=false  # Disable expansion within sessions

# Token Budgets (REDUCE defaults)
DEFAULT_MAX_TOKENS=1000  # Down from 2000
PROGRESSIVE_DISCLOSURE_OVERVIEW_MAX=200
PROGRESSIVE_DISCLOSURE_DETAILED_MAX=600
PROGRESSIVE_DISCLOSURE_COMPREHENSIVE_MAX=1500

# Context Compression (KEEP and improve)
CONTEXT_COMPRESSION_ENABLED=true
CONTEXT_COMPRESSION_STRATEGY=hybrid  # truncate|summarize|hybrid

# Caching (EXPAND)
REDIS_CACHE_TTL_SECONDS=86400  # 24 hours for stable content
SEMANTIC_CACHE_SIMILARITY_THRESHOLD=0.95

# Continuous Learning (KEEP but monitor)
CONTINUOUS_LEARNING_ENABLED=true
PATTERN_EXTRACTION_ENABLED=false  # Disable until verified it helps
```

---

## Implementation Checklist

### Day 1: Emergency Optimization
- [ ] Add `QUERY_EXPANSION_ENABLED=false` to .env
- [ ] Add `REMOTE_LLM_FEEDBACK_ENABLED=false` to .env
- [ ] Update default token budgets in .env
- [ ] Restart services
- [ ] Measure baseline vs optimized token usage

### Week 1: Code Changes
- [ ] Modify `multi_turn_context.py` to respect `MULTI_TURN_QUERY_EXPANSION` flag
- [ ] Modify `server.py` to use new default token budgets
- [ ] Modify `progressive_disclosure.py` to use new max tokens
- [ ] Add token usage tracking middleware
- [ ] Create metrics dashboard

### Week 2: Validation
- [ ] Compare token usage: before vs after
- [ ] Validate remote agent still gets sufficient context
- [ ] Monitor cache hit rates
- [ ] Measure round-trips per task
- [ ] Document results

---

## Expected Results

### Token Usage Per Query

| Scenario | Before | After | Savings |
|----------|--------|-------|---------|
| Simple query | 2000 tokens | 600 tokens | 70% |
| Medium query | 3500 tokens | 1000 tokens | 71% |
| Complex query | 5000 tokens | 1500 tokens | 70% |
| With query expansion | 8000 tokens | 1000 tokens | 87% |
| With feedback loop | 10000 tokens | 1500 tokens | 85% |

**Average Savings:** 70-85% reduction in tokens sent to remote agents

### Cost Impact (Example)

Assuming Claude Sonnet 4 pricing: $3.00 / 1M input tokens

**Before Optimization:**
- 1000 queries/day × 5000 tokens/query = 5M tokens/day
- Cost: $15/day = $450/month

**After Optimization:**
- 1000 queries/day × 1000 tokens/query = 1M tokens/day
- Cost: $3/day = $90/month

**Monthly Savings:** $360 (80% reduction)

---

## Questions & Answers

**Q: Won't disabling query expansion hurt retrieval quality?**
A: Possibly, but the trade-off is worth it. Query expansion returns 3-5x more context, but most of it is redundant. We can compensate by:
- Using better embeddings models
- Improving vector search parameters (HNSW)
- Using local llama.cpp to rerank results

**Q: What if remote agent needs more context?**
A: Use progressive disclosure! Remote agent can:
1. Start with overview (200 tokens)
2. Request detailed (600 tokens) if needed
3. Request comprehensive (1500 tokens) if still needed
This gives remote agent control while defaulting to minimal context.

**Q: How do we know if optimization is working?**
A: Track these metrics:
- Tokens per query (should decrease 70%+)
- Round-trips per task (should stay same or decrease)
- Task completion rate (should stay same)
- Remote agent error rate (should stay same)

If token usage decreases WITHOUT increasing errors/round-trips, optimization is working.

---

**Status:** Ready for implementation
**Next Steps:** Execute Day 1 optimizations (disable query expansion, disable feedback loops, reduce token budgets)
