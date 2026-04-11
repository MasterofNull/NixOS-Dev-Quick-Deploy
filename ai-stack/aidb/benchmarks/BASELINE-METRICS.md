# Baseline Performance Metrics

**Date:** 2026-04-11
**Version:** 1.0
**System:** Phase 1 Slice 1.5 - Memory Benchmark Harness

---

## Executive Summary

This document establishes baseline performance metrics for the AI memory system implemented in Phase 1 (Slices 1.2-1.5). The benchmark harness measures recall accuracy, query latency, throughput, and storage efficiency using a comprehensive corpus of 550 fact-query pairs across 5 categories.

### Key Results

| Metric | Baseline | Target | Status |
|--------|----------|--------|--------|
| **Recall Accuracy (Baseline)** | TBD | 85%+ | TBD |
| **Recall Accuracy (Metadata)** | TBD | 90%+ | TBD |
| **Query Latency (p95)** | TBD | <500ms | TBD |
| **Throughput** | TBD | 50+ qps | TBD |
| **Storage Efficiency** | TBD | <2x AIDB | TBD |

*Note: Actual benchmark results will be populated when run on production system with full fact database.*

---

## System Configuration

### Hardware
- **Platform:** NixOS (Linux 6.19.3)
- **CPU:** TBD (to be populated from actual benchmark run)
- **Memory:** 32GB RAM (system)
- **Storage:** SSD

### Software Stack
- **Python:** 3.11+
- **Database:** JSON file storage (development), PostgreSQL + pgvector (production)
- **Search:** Keyword matching (baseline), Vector embeddings (production)
- **Memory System:** Multi-layer loading (L0-L3) with temporal validity

### Configuration
- **Fact Store:** In-memory JSON (`~/.aidb/temporal_facts.json`)
- **Embedding Model:** text-embedding-3-small (1536 dims) - when available
- **Index Type:** Linear scan (development), HNSW (production)

---

## Benchmark Corpus Statistics

### Overview
- **Version:** 1.0
- **Total Pairs:** 550
- **Created:** 2026-04-11

### Category Breakdown

| Category | Count | Description |
|----------|-------|-------------|
| **Decisions** | 110 | Architecture decisions and technical choices |
| **Preferences** | 100 | User and system preferences |
| **Discoveries** | 150 | Technical learnings and insights |
| **Events** | 100 | Significant project events and milestones |
| **Advice** | 90 | Best practices and recommendations |

### Query Characteristics
- **Queries per Fact:** 3-4 paraphrased variants
- **Query Types:**
  - Direct content match ("What database are we using?")
  - Partial keyword ("JWT expiry time")
  - Semantic paraphrase ("How long do tokens last?")
  - Topic-based ("authentication token configuration")

---

## Recall Accuracy Results

### Test Strategy

We measure recall accuracy using three strategies:

1. **Baseline:** Semantic search only (no metadata filtering)
2. **Metadata-Enhanced:** Semantic search + project/topic/type filters
3. **Temporal:** Time-constrained queries (valid_at filtering)

### Metrics

- **Accuracy:** Percentage of queries where expected fact appears in top-N results
- **MRR (Mean Reciprocal Rank):** Average of 1/rank for found facts
  - MRR = 1.0: All facts rank #1
  - MRR = 0.5: Average rank is #2
  - MRR > 0.7: Considered good performance

### Baseline Results (Semantic Only)

```
Strategy: Baseline (no metadata filtering)
Limit: Top 10 results per query

Accuracy:  TBD%
MRR:       TBD

Category Breakdown:
- Decisions:    TBD% (MRR: TBD)
- Preferences:  TBD% (MRR: TBD)
- Discoveries:  TBD% (MRR: TBD)
- Events:       TBD% (MRR: TBD)
- Advice:       TBD% (MRR: TBD)

Target: 85%+ accuracy
Status: TBD
```

### Metadata-Enhanced Results

```
Strategy: Metadata-Enhanced (semantic + filters)
Limit: Top 10 results per query

Accuracy:  TBD%
MRR:       TBD

Category Breakdown:
- Decisions:    TBD% (MRR: TBD)
- Preferences:  TBD% (MRR: TBD)
- Discoveries:  TBD% (MRR: TBD)
- Events:       TBD% (MRR: TBD)
- Advice:       TBD% (MRR: TBD)

Target: 90%+ accuracy
Status: TBD
```

### Temporal Results

```
Strategy: Temporal (valid_at filtering)
Limit: Top 10 results per query

Accuracy:  TBD%
MRR:       TBD

Target: 85%+ accuracy
Status: TBD
```

### Analysis

**Expected Results:**
- Baseline accuracy should be 70-85% with simple keyword matching
- Metadata filtering should improve accuracy by 10-15 percentage points
- Temporal filtering adds minimal overhead while maintaining accuracy

**Observations:**
- TBD (to be filled after actual benchmark run)

---

## Performance Results

### Latency Distribution

#### Warm Cache

```
Test: Query Latency (warm cache)
Queries: 1000

p50:  TBD ms
p95:  TBD ms
p99:  TBD ms
min:  TBD ms
max:  TBD ms
mean: TBD ms

Target: p95 < 500ms
Status: TBD
```

#### Cold Cache

```
Test: Query Latency (cold cache)
Queries: 1000

p50:  TBD ms
p95:  TBD ms
p99:  TBD ms

Comparison to warm cache:
- p50 overhead: TBD ms
- p95 overhead: TBD ms
```

### Throughput

```
Test: Query Throughput
Duration: 10 seconds

Throughput: TBD queries/sec
Total Queries: TBD

Target: 50+ qps
Status: TBD
```

### Concurrency Performance

#### 10 Workers

```
Test: Concurrent Queries
Workers: 10
Queries per Worker: 100

Overall QPS: TBD qps
Median p50:  TBD ms
Median p95:  TBD ms

Comparison to single-threaded:
- QPS multiplier: TBD x
- Latency overhead: TBD ms
```

#### 50 Workers

```
Test: Concurrent Queries
Workers: 50
Queries per Worker: 50

Overall QPS: TBD qps
Median p50:  TBD ms
Median p95:  TBD ms
```

### Storage Efficiency

```
Test: Storage Efficiency
Fact Count: TBD

File Size:        TBD MB
Avg Fact Size:    TBD bytes
Compression:      TBD x (JSON overhead)

Target: < 2x raw content size
Status: TBD
```

### Memory Usage

```
Test: Memory Usage

Baseline:         TBD MB
After Load:       TBD MB
After Queries:    TBD MB

Load Increase:    TBD MB
Query Increase:   TBD MB
```

---

## Target Comparison

### Targets Met ✅

- TBD

### Targets Not Met ❌

- TBD

### Recommendations

TBD (based on actual results)

---

## Implementation Details

### Benchmark Harness Components

1. **Corpus Generator** (`memory-benchmark-corpus.json`)
   - 550 fact-query pairs across 5 categories
   - Realistic queries with paraphrasing
   - Expected rank annotations

2. **Recall Accuracy** (`recall_accuracy.py`)
   - Three test strategies (baseline, metadata, temporal)
   - MRR calculation
   - Category-level breakdown

3. **Performance Suite** (`performance_bench.py`)
   - Latency percentiles (p50, p95, p99)
   - Throughput measurement
   - Concurrency testing
   - Storage efficiency
   - Memory profiling

4. **CLI Tool** (`aq-benchmark`)
   - Unified benchmark execution
   - Result reporting (text, HTML, JSON)
   - Target validation

### Running Benchmarks

```bash
# Full benchmark suite
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/aidb
./benchmarks/aq-benchmark run --corpus benchmarks/memory-benchmark-corpus.json

# Recall accuracy only
./benchmarks/aq-benchmark recall --all

# Performance only
./benchmarks/aq-benchmark perf --all

# Generate HTML report
./benchmarks/aq-benchmark report results/benchmark-YYYYMMDD-HHMMSS.json --format html
```

### Interpreting Results

**Recall Accuracy:**
- **Accuracy ≥ 90%:** Excellent - facts reliably retrieved
- **Accuracy 80-90%:** Good - minor tuning recommended
- **Accuracy < 80%:** Poor - significant improvements needed

**MRR:**
- **MRR ≥ 0.8:** Excellent - facts rank at top
- **MRR 0.6-0.8:** Good - facts in top 3
- **MRR < 0.6:** Poor - facts buried in results

**Latency:**
- **p95 < 300ms:** Excellent - very responsive
- **p95 300-500ms:** Good - meets target
- **p95 > 500ms:** Poor - optimization required

**Throughput:**
- **QPS ≥ 100:** Excellent - high capacity
- **QPS 50-100:** Good - meets target
- **QPS < 50:** Poor - scaling issues

---

## Comparison to Production

### Development vs Production

| Aspect | Development | Production | Impact |
|--------|------------|------------|--------|
| **Storage** | JSON files | PostgreSQL + pgvector | 10-100x faster |
| **Search** | Keyword match | Vector embeddings | 20-30% accuracy gain |
| **Index** | Linear scan | HNSW index | 100-1000x faster |
| **Cache** | In-memory | Redis/pgvector cache | 5-10x faster |

**Expected Production Improvements:**
- **Recall Accuracy:** +15-25% with embeddings
- **Latency:** 50-100x faster with HNSW index
- **Throughput:** 100-1000x with database parallelism
- **Storage:** Similar efficiency (JSON vs PostgreSQL overhead comparable)

---

## Next Steps

1. **Run Baseline Benchmarks**
   - Execute full benchmark suite with current implementation
   - Document actual results in this file
   - Identify optimization opportunities

2. **Vector Search Integration**
   - Implement embedding generation pipeline
   - Add pgvector integration
   - Re-run benchmarks to measure improvement

3. **Performance Optimization**
   - Add result caching for repeated queries
   - Implement batch embedding generation
   - Optimize metadata filtering queries

4. **Continuous Benchmarking**
   - Add benchmark CI/CD pipeline
   - Track metrics over time
   - Alert on regression

5. **Production Migration**
   - Deploy PostgreSQL + pgvector
   - Migrate from JSON to database storage
   - Implement HNSW indexing
   - Measure production performance

---

## Appendix: Benchmark Reproducibility

### Prerequisites

```bash
# Python dependencies
pip install -r requirements.txt  # (to be created)

# Fact store with test data
aq-memory add "Test fact" --project test --topic test
```

### Running Full Suite

```bash
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/aidb

# Run all benchmarks
./benchmarks/aq-benchmark run \
  --corpus benchmarks/memory-benchmark-corpus.json \
  --output results/baseline-$(date +%Y%m%d).json

# Generate report
./benchmarks/aq-benchmark report \
  results/baseline-$(date +%Y%m%d).json \
  --format html \
  --output results/baseline-report.html
```

### Environment Variables

None required for baseline benchmarks.

For production benchmarks with embeddings:
```bash
export OPENAI_API_KEY="your-key"  # For embedding generation
export POSTGRES_URL="postgresql://..."  # For pgvector testing
```

---

## Changelog

- **2026-04-11:** Initial baseline metrics document created
- **TBD:** Actual benchmark results populated
- **TBD:** Production comparison data added

---

## References

- [Phase 1 Slice 1.5 Plan](/.agents/plans/phase-1-slice-1.5-benchmark-harness.md)
- [Temporal Facts Implementation](/ai-stack/aidb/temporal_facts.py)
- [Temporal Query API](/ai-stack/aidb/temporal_query.py)
- [Memory CLI Tool](/scripts/ai/aq-memory)
- [MemPalace Benchmark Approach](https://github.com/daveshap/MemPalace) (inspiration)
