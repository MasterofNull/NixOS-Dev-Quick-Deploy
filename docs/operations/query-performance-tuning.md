# Query Performance Tuning - Operations Guide

**Status:** Active
**Owner:** AI Harness Team
**Last Updated:** 2026-03-20

**For System Operators and DevOps Engineers**

## Quick Start

### Check Current Performance

```bash
# Get performance metrics
curl http://localhost:8889/api/search/performance/metrics | jq

# Check for slow queries
curl http://localhost:8889/api/search/performance/slow-queries | jq

# Get optimization recommendations
curl http://localhost:8889/api/search/performance/recommendations | jq
```

### Run Performance Benchmark

```bash
cd /path/to/repo
./scripts/testing/benchmark-query-performance.sh
```

## Common Performance Issues

### Issue 1: High Query Latency (P95 > 600ms)

**Symptoms:**
- Dashboard shows P95 > 600ms
- User complaints about slow searches
- Alerts firing for high latency

**Quick Diagnosis:**
```bash
# Check profiler data
curl http://localhost:8889/api/search/performance/profile | jq '.slow_queries'

# Check component breakdown
curl http://localhost:8889/api/search/performance/profile | jq '.component_baselines'
```

**Quick Fixes:**

1. **Increase HNSW ef_search (if recall allows):**
```yaml
# config/query-performance.yaml
vector_search:
  hnsw:
    ef_search: 64  # Lower from 128
```

2. **Enable/increase cache:**
```yaml
query_cache:
  memory:
    size: 2000  # Increase from 1000
```

3. **Optimize batch size:**
```yaml
query_batching:
  optimal_batch_size: 15  # Reduce from 20
  max_wait_ms: 30.0  # Reduce from 50ms
```

4. **Warm caches on startup:**
```bash
curl -X POST http://localhost:8889/api/search/cache/warm
```

**Long-term Solutions:**
- Review HNSW index parameters
- Add more resources (CPU/RAM)
- Consider index sharding
- Optimize query patterns

### Issue 2: Low Cache Hit Rate (< 40%)

**Symptoms:**
- Cache hit rate below 40%
- High backend load
- Redundant computations

**Quick Diagnosis:**
```bash
# Check cache stats
curl http://localhost:8889/api/search/cache/stats | jq
```

**Quick Fixes:**

1. **Increase cache size:**
```yaml
query_cache:
  memory:
    size: 2000
  redis:
    ttl_seconds: 7200  # 2 hours instead of 1
```

2. **Enable cache warming:**
```yaml
query_cache:
  warming:
    enabled: true
```

3. **Optimize query normalization:**
Review query patterns - are similar queries being treated as different?

**Long-term Solutions:**
- Analyze query patterns
- Implement smarter query normalization
- Increase Redis capacity
- Consider distributed caching

### Issue 3: Poor Batch Efficiency (< 60%)

**Symptoms:**
- Batch efficiency below 60%
- Underutilized batching
- Suboptimal throughput

**Quick Diagnosis:**
```bash
# Check batch metrics
curl http://localhost:8889/api/search/performance/metrics | jq '.batching'
```

**Quick Fixes:**

1. **Enable auto-tuning:**
```yaml
query_batching:
  auto_tune:
    enabled: true
```

2. **Adjust batch size:**
```yaml
query_batching:
  optimal_batch_size: 25  # Increase
  max_wait_ms: 75.0  # Allow more batching time
```

3. **Check query arrival patterns:**
If queries arrive sporadically, batching may not be beneficial.

### Issue 4: Memory Usage Too High

**Symptoms:**
- Memory usage > 500MB above baseline
- OOM warnings
- Slow cache operations

**Quick Diagnosis:**
```bash
# Check cache sizes
curl http://localhost:8889/api/search/cache/stats | jq '.memory_cache.size'
```

**Quick Fixes:**

1. **Reduce cache sizes:**
```yaml
query_cache:
  memory:
    size: 500  # Reduce from 1000
vector_search:
  query_cache:
    size: 500  # Reduce from 1000
```

2. **Clear caches:**
```bash
curl -X POST http://localhost:8889/api/search/cache/clear \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'
```

3. **Use mmap for large indexes:**
```yaml
vector_search:
  memmap_threshold: 50000  # Lower threshold
```

## Performance Tuning Recipes

### Recipe 1: Optimize for Latency

**Goal:** Minimize P95 latency (target < 200ms)

```yaml
# config/query-performance.yaml
vector_search:
  hnsw:
    ef_search: 64  # Reduce search quality slightly
  query_cache:
    size: 2000  # Large cache

query_cache:
  memory:
    size: 2000
    ttl_seconds: 600  # 10 minutes

query_batching:
  optimal_batch_size: 10  # Small batches
  max_wait_ms: 20.0  # Low wait time
```

**Expected Results:**
- P95 latency: 150-200ms
- Cache hit rate: 70%+
- Slightly reduced recall (0.5-1%)

### Recipe 2: Optimize for Throughput

**Goal:** Maximize queries/second

```yaml
vector_search:
  hnsw:
    ef_search: 128
  query_cache:
    size: 1000

query_batching:
  optimal_batch_size: 50  # Large batches
  max_wait_ms: 100.0  # More batching time
  
embeddings:
  batch_size: 64  # Large embedding batches
```

**Expected Results:**
- Throughput: 200+ queries/second
- P95 latency: 400-500ms
- High batch efficiency (80%+)

### Recipe 3: Optimize for Accuracy

**Goal:** Maximize recall (> 98%)

```yaml
vector_search:
  hnsw:
    m: 32  # More connections
    ef_construct: 200
    ef_search: 256  # High search quality
    
query_cache:
  enabled: false  # Disable caching to ensure fresh results
```

**Expected Results:**
- Recall: 98%+
- P95 latency: 600-800ms
- Lower throughput

### Recipe 4: Balanced (Recommended Default)

**Goal:** Balance latency, throughput, and accuracy

```yaml
vector_search:
  hnsw:
    m: 16
    ef_construct: 100
    ef_search: 128
    
query_cache:
  memory:
    size: 1000
    ttl_seconds: 300
  redis:
    ttl_seconds: 3600
    
query_batching:
  optimal_batch_size: 20
  max_wait_ms: 50.0
```

**Expected Results:**
- P95 latency: 300-400ms
- Throughput: 100+ queries/second
- Recall: 95-97%
- Cache hit rate: 60%+

## Resource Planning

### Memory Requirements

| Configuration | Memory Overhead | Notes |
|--------------|----------------|-------|
| Minimal | +100MB | Small caches, no batching |
| Balanced | +250MB | Default configuration |
| High Performance | +500MB | Large caches, aggressive batching |

### CPU Requirements

| Workload | CPU Cores | Notes |
|----------|-----------|-------|
| Light (< 10 QPS) | 2 cores | Adequate for small deployments |
| Medium (10-50 QPS) | 4 cores | Recommended for production |
| Heavy (50-200 QPS) | 8+ cores | High-throughput scenarios |

### GPU Recommendations

For embedding generation:

| Use Case | GPU | Performance |
|----------|-----|-------------|
| Development | None (CPU) | 40 embeddings/sec |
| Production | NVIDIA T4 | 150 embeddings/sec |
| High-throughput | NVIDIA A100 | 500+ embeddings/sec |

## Monitoring Setup

### Key Metrics to Monitor

1. **Latency Percentiles:**
   - P50, P95, P99 query latency
   - Component-level breakdown
   - Trend over time

2. **Cache Performance:**
   - Hit rate (target > 60%)
   - Memory usage
   - Eviction rate

3. **Batch Performance:**
   - Batch efficiency (target > 75%)
   - Average batch size
   - Wait time distribution

4. **Resource Usage:**
   - CPU utilization
   - Memory consumption
   - GPU utilization (if applicable)

### Prometheus Metrics

Expose these metrics:

```yaml
# query_performance_latency_ms (histogram)
query_performance_latency_ms_bucket{le="50"} 245
query_performance_latency_ms_bucket{le="100"} 678
query_performance_latency_ms_bucket{le="500"} 950
query_performance_latency_ms_count 1000

# query_cache_hit_rate (gauge)
query_cache_hit_rate 0.65

# batch_efficiency (gauge)
batch_efficiency 0.78
```

### Alert Rules

```yaml
groups:
  - name: query_performance
    rules:
      - alert: HighQueryLatency
        expr: histogram_quantile(0.95, query_performance_latency_ms) > 600
        for: 5m
        annotations:
          summary: "P95 query latency above 600ms"

      - alert: LowCacheHitRate
        expr: query_cache_hit_rate < 0.40
        for: 10m
        annotations:
          summary: "Cache hit rate below 40%"

      - alert: LowBatchEfficiency
        expr: batch_efficiency < 0.60
        for: 15m
        annotations:
          summary: "Batch efficiency below 60%"
```

## Deployment Checklist

### Pre-Deployment

- [ ] Review configuration in `config/query-performance.yaml`
- [ ] Run performance benchmarks
- [ ] Verify resource availability (CPU, RAM, GPU)
- [ ] Set up monitoring and alerting
- [ ] Prepare rollback plan

### Post-Deployment

- [ ] Warm caches
- [ ] Monitor initial performance metrics
- [ ] Check for slow queries
- [ ] Verify cache hit rates
- [ ] Review batch efficiency
- [ ] Check resource usage
- [ ] Compare with baseline performance

### Rollback Procedure

If performance degrades:

1. **Immediate rollback:**
```yaml
features:
  enable_vector_optimization: false
  enable_query_caching: false
  enable_query_batching: false
```

2. **Restart services:**
```bash
systemctl restart ai-hybrid-coordinator
```

3. **Clear caches:**
```bash
curl -X POST http://localhost:8889/api/search/cache/clear -d '{"confirm": true}'
```

## Troubleshooting Decision Tree

```
Query Performance Issue?
│
├─ High Latency (P95 > 600ms)?
│  ├─ Check profiler slow queries
│  ├─ Review component breakdown
│  └─ Solutions: Lower ef_search, increase cache, optimize batching
│
├─ Low Cache Hit Rate (< 40%)?
│  ├─ Check cache stats
│  ├─ Review query patterns
│  └─ Solutions: Increase cache size/TTL, enable warming
│
├─ Poor Batch Efficiency (< 60%)?
│  ├─ Check batch metrics
│  ├─ Review query arrival patterns
│  └─ Solutions: Adjust batch size/wait time, enable auto-tune
│
└─ High Memory Usage?
   ├─ Check cache sizes
   ├─ Review memory allocation
   └─ Solutions: Reduce cache sizes, use mmap, clear caches
```

## Support and Escalation

### Self-Service Resources

1. Performance documentation: `docs/performance/query-retrieval-optimization.md`
2. Configuration guide: `config/query-performance.yaml`
3. Test suite: `scripts/testing/test-query-performance.py`
4. Benchmarks: `scripts/testing/benchmark-query-performance.sh`

### Escalation Path

1. **Level 1:** Check dashboard metrics and recommendations
2. **Level 2:** Run diagnostics and review logs
3. **Level 3:** Contact platform team with profiler data
4. **Level 4:** Escalate to engineering with benchmark results

## Quick Reference

### Configuration Files

- Main config: `config/query-performance.yaml`
- Feature toggles: `features` section
- Performance targets: `targets` section

### API Endpoints

- Metrics: `GET /api/search/performance/metrics`
- Slow queries: `GET /api/search/performance/slow-queries`
- Cache stats: `GET /api/search/cache/stats`
- Recommendations: `GET /api/search/performance/recommendations`

### Scripts

- Test suite: `scripts/testing/test-query-performance.py`
- Benchmarks: `scripts/testing/benchmark-query-performance.sh`

### Default Ports

- Hybrid Coordinator: 8003
- Dashboard API: 8889
- Redis: 6379
- Qdrant: 6333
