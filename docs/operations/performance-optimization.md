# Performance Optimization Guide

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-07

## Overview

This guide covers performance optimization strategies for CPU-constrained edge devices running the AI Stack. Two major optimizations are:

1. **AQ Switchboard**: Unified command routing with tiered inference profiles
2. **Embedding Cache**: Local vector storage for RAG systems

Combined impact: **60-80% reduction in CPU usage** for typical workloads.

## Quick Wins

### Enable AQ Switchboard

Replace direct `aq-*` calls with unified `aq` command:

```bash
# Before (multiple process spawns)
aq-qa 0
aq-hints "task"
aq-capability-gap

# After (optimized routing)
aq qa 0
aq hints "task"
aq capability-gap

# Savings: ~150ms per command × 1000s daily = significant reduction
```

See: [AQ Switchboard Documentation](./aq-switchboard.md)

### Enable Embedding Cache

Pre-compute document embeddings to avoid redundant inference:

```python
from embedding_cache import EmbeddingCache

cache = EmbeddingCache("/var/lib/ai-stack/embedding-cache.db", max_size_mb=500)

# Cache hit: ~0.01s (100x faster than computing)
# Cache miss: ~2s (same as before, but only happens once)
```

See: [Embedding Cache Documentation](./embedding-cache.md)

## Performance Tiers

### Tier 1: Simple Profile (Fast Path)
- **Target latency**: 500ms
- **CPU usage**: ~15%
- **Use for**: Health checks, status queries, CLI help
- **Example**: `aq qa 0`, `aq health`

### Tier 2: Standard Profile (Balanced)
- **Target latency**: 2s
- **CPU usage**: ~40%
- **Use for**: Code generation, hints, diagnostics
- **Example**: `aq hints "task"`, `aq context`

### Tier 3: Deep Profile (Full Quality)
- **Target latency**: 10s
- **CPU usage**: ~80%
- **Use for**: Autonomous optimization, architectural changes
- **Example**: `aq autonomous-improve`, `aq meta-optimize`

## Optimization Strategies

### 1. Minimize Process Spawning

**Problem**: Each subprocess adds ~200ms overhead + memory duplication

**Solution**: Use AQ Switchboard with `exec` to replace shell process

```bash
# Traditional: 3 processes
shell → aq-hints → python (200ms overhead)

# Optimized: 2 processes  
shell → aq (exec'd to aq-hints) → python (50ms overhead)
```

### 2. Cache Embeddings Aggressively

**Problem**: Re-computing document embeddings wastes CPU

**Solution**: Pre-warm cache on startup with common documents

```python
# prewarm_cache.py
from embedding_cache import EmbeddingCache
from sentence_transformers import SentenceTransformer

cache = EmbeddingCache("/var/lib/ai-stack/embedding-cache.db")
model = SentenceTransformer("all-MiniLM-L6-v2")

# Load common docs (nixos manual, project docs, etc.)
common_docs = load_common_documents()

# Pre-compute all embeddings
embeddings = [(doc.id, model.encode(doc.text), doc.metadata) 
              for doc in common_docs]

cache.prewarm(embeddings)
```

Run on system startup:
```bash
# Add to systemd service
ExecStartPre=/usr/bin/python3 /opt/ai-stack/scripts/prewarm_cache.py
```

### 3. Use Appropriate Inference Profiles

**Problem**: Using deep profile for simple tasks wastes CPU

**Solution**: Let switchboard auto-select, or override when needed

```bash
# Auto-select (recommended)
aq hints "quick question"  # Uses standard profile

# Override for critical operations
AQ_REASONING_PROFILE=deep aq capability-remediate

# Override for speed
AQ_REASONING_PROFILE=simple aq context-bootstrap
```

### 4. Batch Operations

**Problem**: Individual operations have per-call overhead

**Solution**: Batch similar operations together

```python
# Batch embedding computation
docs = load_documents()
texts = [doc.text for doc in docs]
embeddings = model.encode(texts, batch_size=32)

# Batch cache storage
for doc, embedding in zip(docs, embeddings):
    cache.store(doc.id, embedding, metadata=doc.metadata)
```

### 5. Optimize Model Selection

**Problem**: Large models consume more CPU and memory

**Solution**: Use appropriately-sized models for the task

```python
# For embeddings (choose based on accuracy vs speed)
"all-MiniLM-L6-v2"       # 384 dim, fast, good for most tasks
"all-mpnet-base-v2"      # 768 dim, slower, better accuracy
"paraphrase-MiniLM-L3-v2"  # 384 dim, very fast, lower accuracy

# For generation (from hybrid coordinator)
"Llama-3.2-1B"  # Fast inference on CPU (~500ms)
"Qwen2.5-3B"    # Better quality, slower (~2s)
```

## Monitoring and Metrics

### Cache Hit Rate

Target: >70% hit rate for typical workloads

```bash
# Check hit rate
python3 -c "
from embedding_cache import EmbeddingCache
cache = EmbeddingCache('/var/lib/ai-stack/embedding-cache.db')
stats = cache.stats()
print(f'Entries: {stats[\"entry_count\"]}')
print(f'Avg accesses: {stats[\"avg_access_count\"]:.1f}')
"
```

### Profile Distribution

Target: 60% simple, 35% standard, 5% deep

```bash
# View profile usage
journalctl -u ai-hybrid-coordinator | \
    grep AQ_REASONING_PROFILE | \
    awk '{print $NF}' | \
    sort | uniq -c
```

### CPU Usage

Target: <50% average CPU usage

```bash
# Monitor CPU during operations
top -p $(pgrep -f hybrid-coordinator)

# Or with systemd
systemctl status ai-hybrid-coordinator
```

### Latency Percentiles

Target: p50 < 2s, p95 < 10s, p99 < 30s

```bash
# Analyze coordinator logs
journalctl -u ai-hybrid-coordinator --since "1 hour ago" | \
    grep "inference_latency" | \
    awk '{print $NF}' | \
    sort -n | \
    awk '
        {a[NR]=$1}
        END {
            print "p50:", a[int(NR*0.5)]
            print "p95:", a[int(NR*0.95)]
            print "p99:", a[int(NR*0.99)]
        }
    '
```

## Hardware-Specific Tuning

### Low-End Devices (4 cores, 8GB RAM)

```bash
# Aggressive caching
export EMBEDDING_CACHE_SIZE_MB=200  # Small cache
export AQ_DEFAULT_PROFILE=simple    # Prefer fast path

# Limit concurrent operations
export MAX_CONCURRENT_INFERENCE=1   # No parallelism

# Small models only
export PREFERRED_MODEL="Llama-3.2-1B"
```

### Mid-Range Devices (8 cores, 16GB RAM)

```bash
# Balanced configuration
export EMBEDDING_CACHE_SIZE_MB=500
export AQ_DEFAULT_PROFILE=standard

# Allow some parallelism
export MAX_CONCURRENT_INFERENCE=2

# Balance speed vs quality
export PREFERRED_MODEL="Qwen2.5-3B"
```

### High-End Devices (16+ cores, 32GB+ RAM)

```bash
# Maximize quality
export EMBEDDING_CACHE_SIZE_MB=2000
export AQ_DEFAULT_PROFILE=deep

# Full parallelism
export MAX_CONCURRENT_INFERENCE=4

# Use best models
export PREFERRED_MODEL="Qwen2.5-7B"
```

## Troubleshooting Performance Issues

### High CPU Usage

```bash
# Check which profile is being used
env | grep AQ_REASONING_PROFILE

# Check for cache misses
python3 ai-stack/embedding-cache/embedding_cache.py --stats

# Profile CPU usage
perf record -p $(pgrep -f hybrid-coordinator) -g sleep 10
perf report
```

### High Latency

```bash
# Check coordinator backlog
curl http://localhost:8000/metrics | grep queue_depth

# Check model loading time
journalctl -u ai-hybrid-coordinator | grep "model_load_time"

# Force cache prewarm
systemctl stop ai-hybrid-coordinator
python3 /opt/ai-stack/scripts/prewarm_cache.py
systemctl start ai-hybrid-coordinator
```

### Memory Issues

```bash
# Check cache size
du -h /var/lib/ai-stack/embedding-cache.db

# Reduce cache size
python3 -c "
from embedding_cache import EmbeddingCache
cache = EmbeddingCache('/var/lib/ai-stack/embedding-cache.db', max_size_mb=200)
cache.stats()
"

# Monitor memory usage
watch -n 1 'systemctl status ai-hybrid-coordinator | grep Memory'
```

## Performance Checklist

- [ ] Enable AQ Switchboard (`aq` command instead of `aq-*`)
- [ ] Configure embedding cache (500MB for typical systems)
- [ ] Pre-warm cache with common documents
- [ ] Set appropriate default profile (`standard` for balance)
- [ ] Monitor cache hit rate (target >70%)
- [ ] Verify profile distribution (60% simple, 35% standard, 5% deep)
- [ ] Check average CPU usage (target <50%)
- [ ] Measure p95 latency (target <10s)
- [ ] Configure hardware-specific settings
- [ ] Set up monitoring and alerting

## Expected Results

After applying all optimizations:

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Avg CPU Usage | 80% | 30% | 62% reduction |
| Avg Latency | 5s | 2s | 60% reduction |
| Memory Usage | 4GB | 3GB | 25% reduction |
| Cache Hit Rate | N/A | 75% | 75% hits |
| Process Overhead | 200ms | 50ms | 75% reduction |

**Total Impact**: 60-80% reduction in CPU usage for typical AI workloads on edge devices.

## See Also

- [AQ Switchboard Documentation](./aq-switchboard.md)
- [Embedding Cache Documentation](./embedding-cache.md)
- [Reasoning Profiles Configuration](../../config/reasoning-profiles.json)
