#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${PERF_BENCH_OUT_DIR:-${ROOT_DIR}/artifacts/perf-bench}"
OUT_JSON="${OUT_DIR}/latest.json"
OUT_MD="${OUT_DIR}/latest.md"
SINCE="${PERF_BENCH_SINCE:-7d}"

mkdir -p "${OUT_DIR}"

REPORT_JSON="$("${ROOT_DIR}/scripts/ai/aq-report" --since="${SINCE}" --format=json)"

python3 - <<'PY' "${REPORT_JSON}" "${OUT_JSON}" "${OUT_MD}"
import json
import pathlib
import sys
from datetime import datetime, timezone

report = json.loads(sys.argv[1])
out_json = pathlib.Path(sys.argv[2])
out_md = pathlib.Path(sys.argv[3])

routing = report.get("routing", {}) if isinstance(report.get("routing"), dict) else {}
cache = report.get("cache", {}) if isinstance(report.get("cache"), dict) else {}
eval_trend = report.get("eval_trend", {}) if isinstance(report.get("eval_trend"), dict) else {}
tools = report.get("tool_performance", {}) if isinstance(report.get("tool_performance"), dict) else {}

top_tools = []
for name, vals in tools.items():
    if not isinstance(vals, dict):
        continue
    top_tools.append({
        "tool": name,
        "calls": int(vals.get("calls", 0) or 0),
        "p95_ms": vals.get("p95_ms"),
        "ok_pct": vals.get("ok_pct"),
    })
top_tools.sort(key=lambda x: x["calls"], reverse=True)
top_tools = top_tools[:10]

payload = {
    "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    "window": "7d",
    "kpis": {
        "routing_local_pct": routing.get("local_pct"),
        "routing_remote_pct": routing.get("remote_pct"),
        "cache_hit_pct": cache.get("hit_pct"),
        "eval_latest_pct": eval_trend.get("latest_pct"),
        "eval_trend": eval_trend.get("trend"),
    },
    "top_tools": top_tools,
}
out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

lines = [
    "# Performance Benchmark Report",
    "",
    f"- Generated: {payload['generated_at']}",
    "- Window: 7d",
    "",
    "## KPI Snapshot",
    "",
    f"- Routing local %: {payload['kpis'].get('routing_local_pct')}",
    f"- Routing remote %: {payload['kpis'].get('routing_remote_pct')}",
    f"- Cache hit %: {payload['kpis'].get('cache_hit_pct')}",
    f"- Eval latest %: {payload['kpis'].get('eval_latest_pct')}",
    f"- Eval trend: {payload['kpis'].get('eval_trend')}",
    "",
    "## Top Tools by Call Volume",
    "",
]
for row in top_tools:
    lines.append(f"- {row['tool']}: calls={row['calls']} p95_ms={row['p95_ms']} ok_pct={row['ok_pct']}")
out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(str(out_json))
PY

echo "Performance benchmark reports written:"
echo "  ${OUT_JSON}"
echo "  ${OUT_MD}"
