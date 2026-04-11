# Memory System Performance

**Status:** Active baseline
**Last Updated:** 2026-04-11
**Scope:** AI harness memory benchmarking for Slice 4.4

## Summary

This report captures the current local-development benchmark baseline for the memory system and records the regression checks wired into CI. It builds on the Phase 1 benchmark harness rather than replacing it.

## Method

Commands used:

```bash
python ai-stack/aidb/benchmarks/aq-benchmark recall --all --corpus ai-stack/aidb/benchmarks/memory-benchmark-corpus.json
python ai-stack/aidb/benchmarks/aq-benchmark perf --latency --throughput --storage --memory --corpus ai-stack/aidb/benchmarks/memory-benchmark-corpus.json --queries 100 --duration 3
python scripts/testing/memory-regression-tests.py
```

Test environment:

- Repository root execution on local development host
- In-memory JSON fact store via `scripts/ai/aq-memory`
- Corpus: `ai-stack/aidb/benchmarks/memory-benchmark-corpus.json`

## Current Baseline

The current harness uses simple text matching over an isolated in-memory JSON fact store for benchmark runs. This means the numbers below reflect the development harness, not a production pgvector-backed deployment.

| Metric | Result | Notes |
|--------|--------|-------|
| Baseline recall accuracy | 65.49% | Current keyword-matching development baseline |
| Metadata-enhanced recall | 67.25% | Slight improvement vs baseline |
| Temporal recall | 66.20% | Similar to baseline on current corpus |
| Warm-cache p95 latency | 0.21 ms | Measured with `100` benchmark queries |
| Throughput | 4,838.17 qps | Measured over a `1s` local regression run |
| Storage overhead ratio | 13.05x | JSON persistence overhead vs raw content bytes |

These were captured from the current local harness using the benchmark corpus and isolated temporary storage.

## MemPalace Comparison

This project is benchmarked against MemPalace conceptually, not via a shared executable harness. The current comparison is therefore capability-relative rather than apples-to-apples:

- MemPalace is the design reference for high-recall memory retrieval and layered organization.
- This harness currently benchmarks a development-mode fact store and search path, so direct recall/latency parity claims would be overstated.
- The useful comparison today is directional: the repo now has a repeatable benchmark corpus, a runnable harness, and CI regression coverage, which were the missing operational pieces for Slice 4.4.

## Recommendations

1. Add a production-backed benchmark mode that runs against PostgreSQL + pgvector instead of the JSON store.
2. Capture benchmark artifacts in CI so trend lines can be compared across commits.
3. Extend regression checks with explicit storage-efficiency thresholds once the production store baseline is stable.
4. Add a dedicated comparison script for MemPalace-style corpus runs when a normalized external baseline is available.

## Regression Coverage

The regression runner is `scripts/testing/memory-regression-tests.py`.

CI entrypoint:

- `.github/workflows/memory-benchmarks.yml`

This gives Slice 4.4 a stable validation surface instead of leaving benchmarking as an ad hoc manual task.
