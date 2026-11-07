#!/usr/bin/env python3
"""Regression: the dashboard must never show a number it did not measure.

Policy "blank `--` = bug, never fake a pass": a failed or missing source reads
as unavailable. Fails if a protected id is written a numeric literal (the old
`.catch(() => setText("healthScore", "98"))` pattern), if a `?? <number>`
default stands in for a missing metric, if a protected HTML id still ships a
hand-typed value, if a retired lane is shown as live, or if the backend
reports "available/zero" for a failed read.
"""

from __future__ import annotations

import asyncio
import re
import sys
import tempfile
from pathlib import Path

# DASHBOARD_TRUTH_ROOT lets the test be pointed at an exported tree (to prove it fails on old code).
import os
ROOT = Path(os.environ.get("DASHBOARD_TRUTH_ROOT") or Path(__file__).resolve().parents[2])
JS = (ROOT / "assets" / "dashboard.js").read_text(encoding="utf-8")
HTML = (ROOT / "dashboard.html").read_text(encoding="utf-8")
STREAM = (ROOT / "assets" / "cockpit" / "stream-card.html").read_text(encoding="utf-8")
DELEG = (ROOT / "assets" / "modules" / "local-agent-delegation.html").read_text(encoding="utf-8")
AISTACK = (ROOT / "dashboard" / "backend" / "api" / "routes" / "aistack.py").read_text(encoding="utf-8")
MODELS = (ROOT / "dashboard" / "backend" / "api" / "routes" / "models.py").read_text(encoding="utf-8")

# Ids the sweep found writing literals as if measured.
JS_IDS = [
    "healthScore", "kpiHealthScore", "execSwarmHealth", "vCacheHit", "vLatP95",
    "histCurLat", "histCurCtx", "vLogicDiscipline", "kpiUptime", "vStack",
    "vIntentUnknown", "kpiTokSaved", "kpiLocalPct", "kpiCacheHit", "kpiEval",
    "kpiHintPct", "execLocalRatio", "kpiVectors", "kpiPgLat", "kpiRedisLat",
    "kpiQdrant", "kpiCoord", "intelHeroSovereignty", "intelHeroPrecision",
    "decideEngineStatus", "decidePsiDrift", "decideCalibrationStatus",
    "ragHarmfulness", "ragRerankMrr", "ragCompRecall", "ragHandoffParity",
    "ragSampleCount", "evalSamples", "evalRunCount",
]
# Ids whose HTML must not carry a hand-typed value.
HTML_IDS = [
    "execGovernanceScore", "histCurGates", "secHeroBadge", "secHeroGates",
    "opsHeroBadge", "opsHeroServices", "spiderHeroBadge", "spiderHeroLayers",
    "fleetHeroConsensus", "ragSampleCount", "cockpitStreamState", "decideEngineStatus", "decidePsiDrift",
    "decideCalibrationStatus", "cockpitLaneBadge", "metric-tokens", "metric-latency",
]
METRIC_FIELDS = [
    "llm_routing_local_pct", "embedding_cache_hit_rate_pct", "eval_latest_pct",
    "hint_adoption_pct", "context_precision_pct", "context_precision",
]

failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


# 1. setText(<protected id>, <literal with a digit>)
for m in re.finditer(r"""setText\(\s*["'](\w+)["']\s*,\s*(["'`])((?:(?!\2).)*)\2\s*\)""", JS):
    ident, lit = m.group(1), m.group(3)
    if ident in JS_IDS and re.search(r"\d", lit) and "${" not in lit:
        fail(f"dashboard.js:{line_of(JS, m.start())} setText({ident!r}, {lit!r}) writes a literal as if measured")

# 2. gauges written a numeric literal
for m in re.finditer(r"updateRadialGauge\(\s*\"(circleGauge(?:Health|Sov|Ctx))\"\s*,\s*\"\w+\"\s*,\s*(\d+)", JS):
    fail(f"dashboard.js:{line_of(JS, m.start())} updateRadialGauge({m.group(1)}) writes literal {m.group(2)}")

# 3. numeric defaults standing in for missing metrics
for f in METRIC_FIELDS:
    for m in re.finditer(rf"\b{f}\s*(?:\?\?|\|\|)\s*(?:[\w.]+\s*(?:\?\?|\|\|)\s*)*\d", JS):
        fail(f"dashboard.js:{line_of(JS, m.start())} `{f} ?? <number>` default shows an unmeasured value")
for m in re.finditer(r"hs\.score\s*!=\s*null\s*\?[^:\n]+:\s*\d", JS):
    fail(f"dashboard.js:{line_of(JS, m.start())} health score falls back to a number")
for m in re.finditer(r"\bquery_ok_n\s*\?\?\s*[1-9]", JS):
    fail(f"dashboard.js:{line_of(JS, m.start())} query_ok_n defaults to a number")

# 4. protected ids must not ship a hand-typed value in HTML
for source, name in ((HTML, "dashboard.html"), (STREAM, "stream-card.html")):
    for ident in HTML_IDS:
        for m in re.finditer(rf"""id="{re.escape(ident)}"[^>]*>([^<]*)<""", source):
            text = m.group(1).strip()
            if re.search(r"\d", text) or text in {"NOMINAL", "Optimal", "Active (T0/T1)"}:
                fail(f"{name}:{line_of(source, m.start())} #{ident} ships hand-typed value {text!r}")

# 4b. static health/objective claims shipped before live data arrives
for word in ("HOMEOSTASIS: OPTIMAL", "Executing SOTA", "STREAMING ACTIVE"):
    for source, name in ((HTML, "dashboard.html"), (STREAM, "stream-card.html")):
        for m in re.finditer(re.escape(word), source):
            fail(f"{name}:{line_of(source, m.start())} ships static claim {word!r}")
for m in re.finditer(r"""state\s*\|\|\s*["']OPTIMAL["']|textContent\s*=\s*["']HOMEOSTASIS: OPTIMAL["']""", JS):
    fail(f"dashboard.js:{line_of(JS, m.start())} homeostasis defaults to OPTIMAL")

# 4c. a measured quality score is shown raw: never rescaled, floored or capped
for m in re.finditer(r"\bcalibrat\w*\s*[=(]", JS):
    fail(f"dashboard.js:{line_of(JS, m.start())} calibration function rescales a measured score")
for m in re.finditer(r"Math\.min\(\s*0\.9\d*\s*,", JS):
    fail(f"dashboard.js:{line_of(JS, m.start())} caps a score below 1 (Math.min(0.9x, ...))")
for m in re.finditer(r"\b0\.[7-9]\d*\s*\+\s*Math\.min\(\s*0\.\d+\s*,", JS):
    fail(f"dashboard.js:{line_of(JS, m.start())} lifts a score to a floor (0.7x + ...)")

# 4d. gauge text must not fall back to a number
for m in re.finditer(r"textContent\s*\|\|\s*[\"']\d", JS):
    fail(f"dashboard.js:{line_of(JS, m.start())} gauge text falls back to a number")

# 4e. limits/targets are not invented when the response omits them
for m in re.finditer(r"\b(?:threshold_mb|hot_max_mb|target)\s*\|\|\s*\d", JS):
    fail(f"dashboard.js:{line_of(JS, m.start())} limit/target defaults to a number")

# 5. retired Antigravity lane shown as live
for text, name in ((HTML, "dashboard.html"), (STREAM, "stream-card.html"), (DELEG, "local-agent-delegation.html")):
    for m in re.finditer(r"antigravity", text, flags=re.I):
        fail(f"{name}:{line_of(text, m.start())} retired Antigravity lane is shown")

# 6. calls to routes that do not exist
if re.search(r"apiFetch\(\s*[\"']/status[\"']", JS):
    fail("dashboard.js fetches GET /api/status, which no route serves")
if "approvals/quick-approve" in JS:
    fail("dashboard.js posts to /control/ai-coordinator/approvals/quick-approve, which no route serves")

# 7. backend: failure must not read as ok/zero
m = re.search(r"async def get_scheduler_queue.*?(?=\n@router|\Z)", AISTACK, flags=re.S)
if not m or re.search(r"except[^\n]*:\s*\n\s*return \{\"available\": True", m.group(0)):
    fail("get_scheduler_queue returns available=True from its except branch")
m = re.search(r"def _count_text_records.*?(?=\ndef )", AISTACK, flags=re.S)
if not m or re.search(r"return 0\b", m.group(0)):
    fail("_count_text_records returns 0 for an unreadable file")
m = re.search(r"async def get_drops_status.*?(?=\n@router|\Z)", AISTACK, flags=re.S)
if not m or re.search(r"except OSError:\s*\n\s*return 0", m.group(0)) or "daemon_active = False" in m.group(0):
    fail("get_drops_status maps a failed read to 0/False")
m = re.search(r"async def get_aistack_metrics.*?(?=\n@router|\Z)", AISTACK, flags=re.S)
if not m or re.search(r"(llm_routing_local_pct|hint_adoption_pct)[^\n]*else 100\.0", m.group(0)):
    fail("/api/metrics substitutes 100.0 for an unmeasured percentage")
if not re.search(r"def _stub_catalog\(.*?\"available\"\] = False", MODELS, flags=re.S):
    fail("_stub_catalog output is not marked available=False")


# 8. behaviour: unreadable scheduler state reports unavailable with the error class
async def scheduler_behaviour() -> None:
    sys.path.insert(0, str(ROOT / "dashboard" / "backend"))
    try:
        from api.routes import aistack  # noqa: WPS433
    except Exception as exc:  # backend deps absent: static checks above still apply
        print(f"SKIP behaviour check: cannot import aistack ({type(exc).__name__})")
        return
    with tempfile.TemporaryDirectory() as tmp:
        original = aistack._repo_root
        aistack._repo_root = lambda: Path(tmp)
        try:
            out = await aistack.get_scheduler_queue()
        finally:
            aistack._repo_root = original
    if out.get("available") is not False or out.get("depth") is not None or not out.get("error"):
        fail(f"get_scheduler_queue with no state file returned {out!r}")


asyncio.run(scheduler_behaviour())

if failures:
    print("FAIL: false values reachable on the dashboard")
    for item in failures:
        print(f"  - {item}")
    sys.exit(1)
print("PASS: no false dashboard values found")
