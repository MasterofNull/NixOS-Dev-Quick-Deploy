#!/usr/bin/env python3
"""Unit tests for aq-a2a-audit — decision parsing, filtering, summary."""
import json
import sys
import tempfile
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
mod = SourceFileLoader("aq_a2a_audit", str(ROOT / "scripts" / "ai" / "aq-a2a-audit")).load_module()


def _fail(m):
    print(f"FAIL: {m}"); sys.exit(1)


def test_decision_parsing():
    cases = [
        ({"direction": "outbound", "secret_findings": ["openai_key"]}, "FLAGGED"),
        ({"direction": "outbound", "secret_findings": []}, "CLEAN"),
        ({"direction": "policy", "summary": "action-policy BLOCK: mode=yolo ..."}, "BLOCK"),
        ({"direction": "policy", "summary": "action-policy ALLOW: mode=safe ..."}, "ALLOW"),
        ({"direction": "budget", "summary": "dispatch-budget WARN: agent 'codex' ..."}, "WARN"),
        # outbound decision is findings-based, NOT summary-text based: no findings => CLEAN
        ({"direction": "outbound", "summary": "BLOCKED"}, "CLEAN"),
    ]
    for rec, want in cases:
        got = mod._decision(rec)
        if got != want:
            _fail(f"_decision({rec}) = {got}, want {want}")
    print("PASS  decision parsing (outbound/policy/budget)")


def test_duration_parser():
    if mod._parse_duration("30m") != 1800 or mod._parse_duration("2h") != 7200 \
            or mod._parse_duration("1d") != 86400:
        _fail("duration parse wrong")
    try:
        mod._parse_duration("5x"); _fail("bad duration should raise")
    except Exception:
        pass
    print("PASS  duration parser (30m/2h/1d + reject)")


def _write(entries):
    p = Path(tempfile.mkdtemp()) / "a2a-audit.log"
    with open(p, "w") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")
    return p


def test_summary_counts():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    recs = [
        {"ts": now, "direction": "outbound", "to": "codex", "secret_findings": ["openai_key"]},
        {"ts": now, "direction": "outbound", "to": "codex", "secret_findings": []},
        {"ts": now, "direction": "policy", "to": "gemini", "summary": "action-policy BLOCK: x"},
        {"ts": now, "direction": "budget", "to": "codex", "summary": "dispatch-budget WARN: y"},
    ]
    s = mod._summary(recs)
    if s["total"] != 4:
        _fail(f"total should be 4: {s}")
    if s["by_decision"].get("FLAGGED") != 1 or s["by_decision"].get("BLOCK") != 1 \
            or s["by_decision"].get("WARN") != 1 or s["by_decision"].get("CLEAN") != 1:
        _fail(f"decision counts wrong: {s['by_decision']}")
    if s["secret_findings"].get("openai_key") != 1:
        _fail(f"findings wrong: {s['secret_findings']}")
    print("PASS  summary counts (direction/decision/findings)")


def test_load_skips_bad_lines():
    p = _write([{"ts": "x", "direction": "policy", "summary": "action-policy ALLOW: z"}])
    with open(p, "a") as fh:
        fh.write("not json\n\n")
    recs = mod._load(p)
    if len(recs) != 1:
        _fail(f"malformed lines should be skipped: {len(recs)}")
    print("PASS  loader skips malformed/blank lines")


def test_missing_log_empty():
    if mod._load(Path("/nonexistent/a2a-audit.log")) != []:
        _fail("missing log should return []")
    print("PASS  missing log -> []")


if __name__ == "__main__":
    test_decision_parsing()
    test_duration_parser()
    test_summary_counts()
    test_load_skips_bad_lines()
    test_missing_log_empty()
    print("\n5/5 aq-a2a-audit tests passed")
