# Performance Testing Procedures
Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-03-05


## Benchmark Suite

Run:
```bash
scripts/performance/run-performance-benchmark-suite.sh
```

Outputs:
- `artifacts/perf-bench/latest.json`
- `artifacts/perf-bench/latest.md`

## Regression Criteria

Track these KPIs per run window:
- routing local/remote split
- semantic cache hit rate
- eval latest/trend
- tool latency (`p95_ms`) and success rate (`ok_pct`)

## Suggested Gates

- Cache hit rate should not regress by more than 10 points without an approved exception.
- Any critical tool with `ok_pct < 95%` requires follow-up remediation.
- Sustained p95 growth for `route_search`/`run_harness_eval` requires optimization ticket.

## Post-Deploy Validation

```bash
scripts/testing/check-mcp-health.sh
scripts/ai/aq-report --since=7d --format=text
scripts/performance/run-performance-benchmark-suite.sh
```
