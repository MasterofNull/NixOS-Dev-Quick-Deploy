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

# 4f. The class behind the individual cases above: a number-bearing fallback in any
# display write. Matches `x || <number>`, `x ?? "<number-ish>"`, `cond ? v : "<number-ish>"`,
# literal arguments to setText/fwRow/textContent, and hand-typed numbers in the HTML of ids
# the script writes. Zero counts (`|| 0`, `?? 0`) are not matched here: they are tracked as a
# separate, larger class (see the evidence file) and each remaining one needs its own source check.
ALLOW = [
    # (regex on the matched text, reason it is not a measurement)
    (r"\|\|\s*(800|500|400)\b", "SVG canvas width/height default (layout size)"),
    (r"\|\|\s*1(?![\d.])", "divisor guard against division by zero"),
    (r"\|\|\s*3(?![\d.])", "graph node radius default (layout size)"),
    (r"\|\|\s*\"v1\"", "API version label default, not a measurement"),
    (r"\|\|\s*\"7d\"", "selected time-window default, not a measurement"),
    (r"\?\?\s*2(?![\d.])", "fail-closed severity rank for an unknown lane, not displayed as a value"),
    (r"\?\s*1000\s*:\s*2000", "poll cadence in ms"),
    (r"\?\s*10\s*:\s*8", "font size"),
    (r"\?\s*[\"']1[\"']\s*:\s*[\"']\.45[\"']", "CSS opacity"),
    (r"\?\s*[\"']700[\"']\s*:\s*[\"']600[\"']", "CSS font weight"),
    (r"\"0 vulns\"", "zero branch taken only when vulnMeasured is true"),
    (r"\"0 alerts\"", "zero branch taken only when alertTotal is a measured number"),
    (r"\"0 Pending\"|\bPending`", "count of a fetched list; unavailable handled in the else branch"),
    (r"fwRow\(\"(Promoted Lessons|Events)\",\s*\"0\"", "empty list after an explicit `if (!d) unavailable` guard"),
    (r"\"0 (runs|lanes)\"", "empty list after an explicit fetched-and-ok guard"),
    (r"textContent\s*=\s*\"0\"", "agent pool badge shown only after the `!d` unavailable guard"),
    (r"textContent\s*===\s*\"0\"", "comparison, not a write"),
    (r"var\(--|rgba\(", "CSS colour value in a ternary, not displayed text"),
    (r"D3_LOADING", "transient loading label replaced when the chart renders"),
    (r"/mcp/v2|Phase 68|JSON-RPC 2\.0", "static protocol/endpoint label on the MCP card, not a measurement"),
]
NUMISH = r"""(?:"[^"\n<>#;]*\d[^"\n<>#;]*"|'[^'\n<>#;]*\d[^'\n<>#;]*')"""
NONZERO = r"(?:[1-9]\d*(?:\.\d+)?|0\.\d*[1-9]\d*)\b"
patterns = [
    ("fallback literal", rf"(?:\|\||\?\?)\s*(?:{NUMISH}|{NONZERO})"),
    ("ternary false-branch literal", rf"[^?.]\?\s[^?:;\n]*?:\s*(?:{NUMISH}|{NONZERO})\s*(?:[;,)\]}}]|$)"),
    ("literal display argument", rf"\b(?:setText|fwRow)\(\s*[\"'][\w-]+[\"']\s*,\s*{NUMISH}\s*[,)]"),
    ("literal textContent", rf"\.textContent\s*=\s*{NUMISH}"),
]
class_hits = 0
allowlisted = 0
for label, pat in patterns:
    for m in re.finditer(pat, JS, flags=re.M):
        text = m.group(0)
        if any(re.search(rx, text) for rx, _ in ALLOW):
            allowlisted += 1
            continue
        class_hits += 1
        fail(f"dashboard.js:{line_of(JS, m.start())} {label}: {text.strip()[:70]!r}")
# HTML: any id the script writes must not ship a number-bearing value (a failed fetch would leave it as a reading).
JS_IDS_ALL = set(re.findall(r"""["'`#]([A-Za-z][\w-]{2,})["'`]""", JS)) | set(re.findall(r"#([A-Za-z][\w-]+)", JS))
HTML_LABELS = {"tabSubmenuOverview", "tabSubmenuHistory"}  # tab titles ("All 14 Raw Sensors"), not values
for source, name in ((HTML, "dashboard.html"), (STREAM, "stream-card.html")):
    for m in re.finditer(r"""<\w+[^>]*\bid="([^"]+)"[^>]*>([^<]*)<""", source):
        ident, text = m.group(1), m.group(2).strip()
        if ident in JS_IDS_ALL and ident not in HTML_LABELS and re.search(r"\d", text) and "${" not in text:
            fail(f"{name}:{line_of(source, m.start())} #{ident} is written by script but ships {text[:40]!r}")
print(f"class scan: {class_hits} unallowlisted and {allowlisted} allowlisted JS fallback hits")

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
