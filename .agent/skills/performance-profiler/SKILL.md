---
name: performance-profiler
description: Performance analysis and optimization workflow. Use when investigating slow operations, profiling code, or optimizing resource usage.
---

# Skill: performance-profiler

## Description
Provides systematic performance analysis patterns for identifying bottlenecks and optimizing code. Focuses on measurement-driven optimization with clear before/after metrics.

## When to Use
- Investigating slow API responses
- Profiling CPU or memory usage
- Optimizing database queries
- Reducing latency in critical paths
- Capacity planning and scaling decisions

## Performance Analysis Protocol

### Phase 1: Baseline Measurement
Always measure before optimizing.

```bash
# API latency baseline
for i in {1..10}; do
  curl -w "%{time_total}\n" -o /dev/null -s http://127.0.0.1:8003/health
done | awk '{sum+=$1} END {print "Avg:", sum/NR, "s"}'

# Service resource baseline
systemctl show <service>.service --property=MemoryCurrent,CPUUsageNSec
```

### Phase 2: Identify Bottleneck Type

| Type | Symptoms | Tools |
|------|----------|-------|
| CPU-bound | High CPU%, slow computation | `top`, `py-spy`, `perf` |
| Memory-bound | High memory, GC pauses | `memory_profiler`, `tracemalloc` |
| I/O-bound | Wait time, blocking calls | `strace`, `iotop`, `async` |
| Network-bound | Latency, connection delays | `curl -w`, `tcpdump` |

### Phase 3: Profiling

#### Python Profiling
```bash
# CPU profiling
python3 -m cProfile -s cumtime <script.py> | head -30

# Line profiling (install line_profiler)
kernprof -l -v <script.py>

# Memory profiling
python3 -m memory_profiler <script.py>

# Live profiling
py-spy top --pid $(pgrep -f <process>)
py-spy record -o profile.svg --pid $(pgrep -f <process>)
```

#### System Profiling
```bash
# Process stats
pidstat -p $(pgrep <process>) 1 10

# I/O stats
iotop -p $(pgrep <process>)

# System calls
strace -c -p $(pgrep <process>)
```

### Phase 4: Common Optimizations

#### Database Queries
```bash
# PostgreSQL slow query log
psql -U ai_user -d aidb -c "SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Explain analyze
psql -U ai_user -d aidb -c "EXPLAIN ANALYZE <your-query>;"
```

#### Caching
```bash
# Check Redis cache stats
redis-cli info stats | grep -E "keyspace_hits|keyspace_misses"

# Calculate hit rate
redis-cli info stats | awk -F: '/keyspace/ {print $1, $2}'
```

#### Connection Pooling
```bash
# Check connection count
ss -s
psql -U ai_user -d aidb -c "SELECT count(*) FROM pg_stat_activity;"
```

### Phase 5: Verify Improvement

```bash
# Re-run baseline measurement
for i in {1..10}; do
  curl -w "%{time_total}\n" -o /dev/null -s http://127.0.0.1:8003/health
done | awk '{sum+=$1} END {print "Avg:", sum/NR, "s"}'

# Compare with baseline
echo "Baseline: X.XXs -> New: Y.YYs = Z% improvement"
```

## Quick Commands

### Service Performance
```bash
# Memory usage by service
systemctl show ai-*.service --property=MemoryCurrent | sort -t= -k2 -h

# CPU usage snapshot
top -b -n 1 | grep -E "ai-|llama|python"

# Service timing
systemd-analyze blame | head -10
```

### AI Stack Specific
```bash
# Route search latency
scripts/ai/aq-report --format=json | jq '.route_search_latency_decomposition.overall_p95_ms'

# Semantic cache performance
scripts/ai/aq-report --format=json | jq '.semantic_cache_hit_rate'

# LLM inference latency
curl -sS http://127.0.0.1:8080/health | jq '.stats'
```

### Load Testing
```bash
# Simple concurrent requests
seq 10 | xargs -P 10 -I {} curl -s -o /dev/null -w "%{time_total}\n" http://127.0.0.1:8003/health

# With timing summary
ab -n 100 -c 10 http://127.0.0.1:8003/health
```

## Optimization Checklist

- [ ] Measure baseline before any changes
- [ ] Identify bottleneck type (CPU/memory/I/O/network)
- [ ] Profile to find specific hot spots
- [ ] Apply targeted fix (not premature optimization)
- [ ] Verify improvement with same measurement
- [ ] Document results and rollback plan

## Token Efficiency Rules
1. Always measure first - don't optimize without data.
2. Fix one bottleneck at a time to isolate impact.
3. Use profilers over manual inspection.
4. Target the highest-impact bottleneck first (80/20 rule).
5. Keep optimization changes minimal and reversible.
