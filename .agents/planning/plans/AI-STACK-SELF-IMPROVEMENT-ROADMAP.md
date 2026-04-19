# AI Stack Self-Improvement Roadmap

**Generated:** 2026-03-09
**Version:** 1.0.0
**Target:** World-Class AI Development Environment

---

## Overview

This roadmap implements recursive self-improvement loops that fully utilize the AI harness capabilities to achieve cutting-edge performance. Each phase builds on the previous, creating compounding improvements.

## Current State Analysis (2026-03-09)

### Strengths (Leverage These)
- MCP Health: **13/13 services healthy**
- Eval trend: **83.2% mean, 100% latest** (rising)
- Hint adoption: **71.7%** (above 70% target)
- Semantic cache: **32.1%** hit rate (above 30% target)
- Routing efficiency: **88.9% local** (minimizing remote costs)
- Advanced parity suite: **PASS**

### Improvement Opportunities (Address These)
1. **Latency outliers**: `run_harness_eval` P95 at 232s (historical)
2. **Hint diversity**: Only 2.04 effective hints (low entropy)
3. **Memory storage**: `store_agent_memory` 61.5% success rate
4. **Pattern extraction**: Not automated
5. **Fine-tuning pipeline**: Manual, not continuous
6. **Knowledge gaps**: Top gaps not being auto-remediated
7. **Counterfactual sampling**: Under-utilized at 8% rate

---

## Self-Improvement Loop Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRSI ORCHESTRATOR LOOP                       │
│                                                                 │
│  ┌─────────┐    ┌──────────┐    ┌────────────┐    ┌─────────┐ │
│  │ OBSERVE │ →  │ ANALYZE  │ →  │ SYNTHESIZE │ →  │ EXECUTE │ │
│  └─────────┘    └──────────┘    └────────────┘    └─────────┘ │
│       ↑                                                  │     │
│       └──────────────── FEEDBACK ───────────────────────┘     │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                         DATA LAYER                              │
│  ┌──────────┐  ┌────────────┐  ┌───────────┐  ┌────────────┐  │
│  │  Qdrant  │  │ PostgreSQL │  │   Redis   │  │ Prometheus │  │
│  │ Vectors  │  │   Scores   │  │   Cache   │  │   Metrics  │  │
│  └──────────┘  └────────────┘  └───────────┘  └────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    AMPLIFICATION LAYER                          │
│  ┌───────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ Pattern       │  │ Knowledge    │  │ Fine-Tuning        │  │
│  │ Extraction    │  │ Gap Auto-Fix │  │ Data Generation    │  │
│  └───────────────┘  └──────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 21.1: Hint Diversity Expansion

**Gate:** Hint entropy ≥ 2.5 bits (currently 1.03)

### Task 21.1.1: Hint Template Expansion
**Status:** pending
**Tooling:** `scripts/ai/aq-hints`, bandit tuning
**Action:**
- Analyze current dominant hints (registry_query_expansion_nixos at 67%)
- Create 8-10 new specialized hint templates
- Categories: debugging, refactoring, testing, documentation, security, performance
**Success Criteria:**
- [ ] Unique hints ≥ 10 (currently 3)
- [ ] Dominant share < 40% (currently 67%)
- [ ] Effective hints ≥ 5 (currently 2.04)
**Evidence:** `aq-report` showing improved entropy

### Task 21.1.2: Context-Aware Hint Routing
**Status:** pending
**Tooling:** `ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py`
**Action:**
- Add file-type based hint routing (`.nix` → nix hints, `.py` → python hints)
- Add task-type routing (fix/add/refactor detection)
- Implement hint freshness decay
**Success Criteria:**
- [ ] Hints contextualized by file type
- [ ] Task-type detection accuracy ≥ 80%
**Evidence:** Test suite for hint routing

### Task 21.1.3: Hint Feedback Loop Acceleration
**Status:** pending
**Tooling:** `hints_feedback` endpoint
**Action:**
- Add automatic feedback submission on tool success/failure
- Track hint → outcome correlation
- Prune consistently low-performing hints
**Success Criteria:**
- [ ] Feedback captured for ≥ 90% of hint usages
- [ ] Low-performing hints identified and pruned
**Evidence:** Feedback coverage metric in `aq-report`

---

## Phase 21.2: Memory System Hardening

**Gate:** `store_agent_memory` success rate ≥ 95%

### Task 21.2.1: Memory Storage Retry Logic
**Status:** pending
**Tooling:** `ai-stack/mcp-servers/hybrid-coordinator/agent_memory.py`
**Action:**
- Add exponential backoff retry for Qdrant writes
- Add transaction logging for failed stores
- Implement async queue for batch writes
**Success Criteria:**
- [ ] Write success rate ≥ 95% (currently 61.5%)
- [ ] P95 write latency < 500ms
**Evidence:** Prometheus metrics for memory write success

### Task 21.2.2: Memory Deduplication
**Status:** pending
**Tooling:** Qdrant collection operations
**Action:**
- Implement semantic deduplication (cosine > 0.95 = duplicate)
- Add memory compression for large payloads
- Create periodic cleanup job
**Success Criteria:**
- [ ] No semantic duplicates in memory store
- [ ] Memory growth rate normalized
**Evidence:** Collection stats showing stable size

### Task 21.2.3: Memory Recall Optimization
**Status:** pending
**Tooling:** `recall_agent_memory` endpoint
**Action:**
- Add MMR (Maximal Marginal Relevance) for diverse recall
- Implement recency bias in scoring
- Add episodic vs semantic memory routing
**Success Criteria:**
- [ ] Recall P50 < 100ms (currently 163ms)
- [ ] Recall diversity score ≥ 0.7
**Evidence:** Latency metrics and diversity sampling

---

## Phase 21.3: Automated Pattern Extraction

**Gate:** Pattern library size ≥ 50 high-value patterns

### Task 21.3.1: Pattern Detection Pipeline
**Status:** pending
**Tooling:** New script `scripts/ai/aq-pattern-extract`
**Action:**
- Scan interaction history for recurring solutions
- Cluster similar solutions using embeddings
- Identify patterns with 3+ occurrences
**Success Criteria:**
- [ ] Automated daily pattern scan
- [ ] Patterns stored in `skills-patterns` collection
**Evidence:** Pattern extraction logs

### Task 21.3.2: Pattern Quality Scoring
**Status:** pending
**Tooling:** 5-factor value algorithm
**Action:**
- Score extracted patterns by complexity, reusability, novelty, confirmation, impact
- Filter patterns with score < 0.7
- Tag patterns by domain (nix, python, shell, etc.)
**Success Criteria:**
- [ ] All patterns have quality scores
- [ ] Low-quality patterns filtered out
**Evidence:** Quality distribution histogram

### Task 21.3.3: Pattern Integration Loop
**Status:** pending
**Tooling:** Hints engine, RAG context
**Action:**
- Auto-inject high-value patterns into hint generation
- Add patterns to RAG retrieval priority
- Track pattern usage and effectiveness
**Success Criteria:**
- [ ] Patterns surface in 30%+ of relevant queries
- [ ] Pattern-assisted queries show higher success rate
**Evidence:** Pattern usage telemetry

---

## Phase 21.4: Knowledge Gap Auto-Remediation

**Gate:** Top 10 gaps auto-remediated within 24h of detection

### Task 21.4.1: Gap Detection Automation
**Status:** pending
**Tooling:** `scripts/ai/aq-gaps`, `aq-report`
**Action:**
- Create systemd timer for hourly gap detection
- Prioritize gaps by frequency and impact
- Route high-priority gaps to remediation queue
**Success Criteria:**
- [ ] Gaps detected within 1 hour of occurrence
- [ ] Priority scoring for remediation order
**Evidence:** Gap detection timer logs

### Task 21.4.2: Auto-Remediation Pipeline
**Status:** pending
**Tooling:** `scripts/ai/aq-gap-import`, `aq-knowledge-import.sh`
**Action:**
- Automatically generate knowledge import for top gaps
- Use local LLM for initial remediation attempt
- Escalate to remote API for complex gaps
**Success Criteria:**
- [ ] 80% of gaps auto-remediated successfully
- [ ] Remediation latency < 24h for top 10 gaps
**Evidence:** Remediation success rate metric

### Task 21.4.3: Remediation Verification Loop
**Status:** pending
**Tooling:** `aq-report`, eval suite
**Action:**
- Re-evaluate queries that triggered gaps after remediation
- Track remediation effectiveness score
- Roll back ineffective remediations
**Success Criteria:**
- [ ] Remediation effectiveness ≥ 70%
- [ ] No regression in eval scores post-remediation
**Evidence:** Before/after eval comparison

---

## Phase 21.5: Fine-Tuning Data Pipeline

**Gate:** Fine-tuning dataset ≥ 1000 high-quality examples

### Task 21.5.1: Interaction Data Collection
**Status:** pending
**Tooling:** `interaction-history` Qdrant collection
**Action:**
- Ensure all interactions logged with full context
- Add structured metadata (llm_used, context_retrieved, outcome)
- Implement data quality validation
**Success Criteria:**
- [ ] 100% interaction capture rate
- [ ] Metadata completeness ≥ 95%
**Evidence:** Collection stats and validation logs

### Task 21.5.2: Training Example Generation
**Status:** pending
**Tooling:** `scripts/data/generate-fine-tuning-data.py`
**Action:**
- Filter interactions by value score ≥ 0.7
- Format as instruction/output pairs
- Add context field for RAG-augmented training
**Success Criteria:**
- [ ] ≥ 1000 examples generated
- [ ] Quality score distribution > 0.75 mean
**Evidence:** Dataset statistics

### Task 21.5.3: Local Model Fine-Tuning Integration
**Status:** pending
**Tooling:** llama-cpp, Unsloth/LoRA
**Action:**
- Implement LoRA fine-tuning pipeline for local model
- Create evaluation suite for fine-tuned model
- Implement A/B testing framework
**Success Criteria:**
- [ ] Fine-tuned model shows ≥ 5% improvement on domain tasks
- [ ] No regression on general tasks
**Evidence:** Eval comparison fine-tuned vs base

---

## Phase 21.6: PRSI Feedback Amplification

**Gate:** Counterfactual sampling generating actionable insights

### Task 21.6.1: Counterfactual Sampling Rate Optimization
**Status:** pending
**Tooling:** `prsi-orchestrator.py`
**Action:**
- Increase counterfactual sample rate from 8% to 15%
- Focus sampling on high-variance action types
- Implement efficient dual-path execution
**Success Criteria:**
- [ ] ≥ 5 counterfactual samples per day (currently ~2)
- [ ] Sampling overhead < 10% of token budget
**Evidence:** Counterfactual log analysis

### Task 21.6.2: Outcome Comparison Analysis
**Status:** pending
**Tooling:** New script `scripts/ai/aq-counterfactual-analyze`
**Action:**
- Compare local vs remote outcomes on sampled queries
- Identify query categories where local underperforms
- Generate targeted improvement recommendations
**Success Criteria:**
- [ ] Comparison reports generated daily
- [ ] Improvement opportunities identified and tracked
**Evidence:** Counterfactual analysis reports

### Task 21.6.3: Budget-Aware Escalation
**Status:** pending
**Tooling:** PRSI policy configuration
**Action:**
- Implement dynamic token budget allocation
- Prioritize escalation for high-impact queries
- Add cost-benefit scoring for remote calls
**Success Criteria:**
- [ ] Budget utilization ≥ 90%
- [ ] High-impact queries never blocked by budget
**Evidence:** Budget utilization metrics

---

## Quality Gates Summary

| Phase | Gate | Validation Command |
|-------|------|-------------------|
| 21.1 | Hint entropy ≥ 2.5 bits | `aq-report --format=json \| jq '.hint_adoption.entropy_bits'` |
| 21.2 | Memory success ≥ 95% | `aq-report --format=json \| jq '.tool_performance.store_agent_memory.success_pct'` |
| 21.3 | Pattern library ≥ 50 | `curl localhost:6333/collections/skills-patterns \| jq '.result.points_count'` |
| 21.4 | Gap remediation < 24h | `aq-gaps --format=json \| jq '.avg_remediation_hours'` |
| 21.5 | Dataset ≥ 1000 examples | `wc -l ~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl` |
| 21.6 | Counterfactual insights | `aq-counterfactual-analyze --since=7d --format=json \| jq '.actionable_insights'` |

---

## Execution Protocol

```
For each Phase:
  For each Task:
    1. Set task status → in_progress
    2. Execute with suggested tooling
    3. Validate → Fix → Validate (loop until success)
    4. Capture evidence
    5. Set task status → completed
    6. Commit if significant
  End
  Run phase gate validation
  If gate fails: Fix → Validate → Commit → Re-check gate
End
```

---

## Self-Improvement Loop Triggers

### Automatic Triggers (Systemd Timers)
1. **Hourly**: Gap detection, hint feedback aggregation
2. **Daily**: Pattern extraction, counterfactual analysis, dataset generation
3. **Weekly**: Full eval suite, memory cleanup, fine-tuning check

### Event-Driven Triggers
1. **On Session End**: Store session learnings, update interaction history
2. **On Error**: Log error + attempted + correct solutions
3. **On Success**: Store solution, calculate value score, consider pattern extraction
4. **On Gate Fail**: Escalate, queue remediation action

---

## Expected Outcomes

After completing all phases:

1. **Hint System**: Diverse, context-aware hints with 70%+ adoption
2. **Memory System**: Reliable storage with semantic deduplication
3. **Pattern Library**: 50+ high-quality reusable patterns
4. **Knowledge Gaps**: Auto-remediated within 24h
5. **Fine-Tuning**: Continuous improvement of local model
6. **PRSI Loop**: Data-driven optimization decisions

**Target State**: A self-improving AI development environment that:
- Learns from every interaction
- Automatically fixes knowledge gaps
- Continuously improves local model performance
- Minimizes remote API costs while maximizing quality
- Provides world-class developer experience

---

## Commit Protocol

After each significant task completion:

```bash
git add <modified-files>
git commit -m "$(cat <<'EOF'
21.<phase>.<task>: <brief description>

- <change 1>
- <change 2>

Evidence: <validation output or reference>

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```
