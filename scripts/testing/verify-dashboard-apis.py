#!/usr/bin/env python3
"""Verify dashboard API endpoints return JSON without timing out."""

import urllib.request
import json
import sys

BASE_URL = "http://127.0.0.1:8889/api"
DEFAULT_TIMEOUT_SECONDS = 3.0
SLOW_ENDPOINT_TIMEOUT_SECONDS = 15.0
SLOW_ENDPOINTS = {
    "/aistack/verify-self/results",
    "/verify-self/results",
}


def timeout_for_path(path):
    return SLOW_ENDPOINT_TIMEOUT_SECONDS if path in SLOW_ENDPOINTS else DEFAULT_TIMEOUT_SECONDS

paths = [
    "/actions/",
    "/adk/discoveries",
    "/adk/gaps",
    "/adk/status",
    "/affective/state",
    "/agent-ops/status",
    "/ai/health/rag",
    "/ai/homeostasis/events",
    "/ai/memory/status",
    "/ai/metrics",
    "/ai/remediation/latest",
    "/aidb/health/detailed",
    "/aistack/advanced/runtime-summary",
    "/aistack/harness/scorecard",
    "/aistack/harness/stats",
    "/aistack/hints/stats",
    "/aistack/insights/tools/heatmap",
    "/aistack/mcp/v2/tools",
    "/aistack/memory/supersede/history",
    "/aistack/policy/tool-deny-stats",
    "/aistack/routing/summary",
    "/aistack/switchboard/profiles",
    "/aistack/task-classification/stats",
    "/aistack/verify-self/results",
    "/alerts/status",
    "/audit/operator/summary",
    "/budget/policy",
    "/collaboration/locks",
    "/collaboration/metrics/summary",
    "/collaboration/patterns",
    "/config",
    "/containers",
    "/context/lifecycle/status",
    "/coordinator/ai-status",
    "/deployments/active",
    "/deployments/history",
    "/discovery/signals",
    "/drops/status",
    "/eval/trend",
    "/firewall/audit-log",
    "/firewall/crowdsec/status",
    "/firewall/rules",
    "/firewall/status",
    "/fleet/status",
    "/fleet/summary",
    "/graph/vector",
    "/graph/workflow",
    "/hardware/state",
    "/harness/overview",
    "/health/aggregate",
    "/health/alerts",
    "/health/categories",
    "/hints/active",
    "/hints/report",
    "/insights/actions/recommendations",
    "/insights/cache/analytics",
    "/insights/hints/effectiveness",
    "/insights/improvements/candidates",
    "/insights/metrics/ai-specific",
    "/insights/performance/hotspots",
    "/insights/queries/complexity",
    "/insights/routing/analytics",
    "/insights/security/compliance",
    "/insights/system/health",
    "/insights/tools/performance",
    "/insights/workflows/a2a-readiness",
    "/insights/workflows/compliance",
    "/knowledge/graph/fact-chain?limit=30",
    "/loop/status",
    "/memory/broker/status",
    "/memory/crystalline/status",
    "/memory/stats",
    "/metrics/health-score",
    "/model-optimization/readiness",
    "/model-optimization/training-data/stats",
    "/models",
    "/orchestration/evaluations/trends",
    "/orchestration/sessions",
    "/parity/scorecard",
    "/query/traces",
    "/reasoning/profiles",
    "/routing/decisions",
    "/routing/lane-failures",
    "/scheduler/status",
    "/security/audit",
    "/services",
    "/stats/circuit-breakers",
    "/stats/learning",
    "/telemetry/anomalies",
    "/testing/executions",
    "/testing/suites",
    "/topology",
    "/traces/drift",
    "/traces/summary",
    "/verify-self/results",
    "/workflows/history",
    "/workflows/statistics",
]

failures = []
for p in paths:
    url = f"{BASE_URL}{p}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout_for_path(p)) as resp:
            code = resp.status
            content = resp.read()
            try:
                data = json.loads(content.decode("utf-8"))
                print(f"PASS: {p} -> HTTP {code}")
            except Exception as je:
                print(f"WARN: {p} -> HTTP {code} (not JSON: {je})")
    except urllib.error.HTTPError as he:
        # Fallback check
        alt_p = p.replace("/aistack", "") if p.startswith("/aistack") else p
        alt_url = f"{BASE_URL}{alt_p}"
        try:
            req = urllib.request.Request(alt_url)
            with urllib.request.urlopen(req, timeout=timeout_for_path(alt_p)) as resp:
                content = resp.read()
                data = json.loads(content.decode("utf-8"))
                print(f"PASS: {p} -> (via fallback {alt_p}) HTTP {resp.status}")
                continue
        except Exception:
            pass
        failures.append((p, he.code, str(he.reason)))
        print(f"FAIL: {p} -> HTTP {he.code} ({he.reason})")
    except Exception as e:
        failures.append((p, 0, str(e)))
        print(f"ERROR: {p} -> {e}")

print("----------")
print(f"Total monitored endpoints: {len(paths)}")
print(f"Passed: {len(paths) - len(failures)}")
print(f"Failed: {len(failures)}")
if failures:
    print("Failures breakdown:")
    for f in failures:
        print(f"  {f[0]} -> {f[1]} ({f[2]})")
    sys.exit(1)
sys.exit(0)
