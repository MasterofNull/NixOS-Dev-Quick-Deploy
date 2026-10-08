#!/usr/bin/env python3
"""ECC P1 operator diagnostics: degraded/unverified behavior. Temp dirs only, no live state."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("ecc_diagnostics", ROOT / "scripts/ai/lib/ecc_diagnostics.py")
ED = importlib.util.module_from_spec(spec)
sys.modules["ecc_diagnostics"] = ED
spec.loader.exec_module(ED)
CLI = ROOT / "scripts/ai/aq-ecc-diagnostics"


def test_memory_recall():
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        assert ED.memory_recall_section([t / "absent"])["status"] == "unverified"
        assert ED.memory_recall_section([t])["reason"] == "no_records_scanned"
        (t / "a.md").write_text("fact\n")
        assert ED.memory_recall_section([t])["status"] == "ok"
        (t / "empty.md").write_text("  \n")
        (t / "bad.md").write_bytes(b"\xff\xfe\x00")
        (t / "big.md").write_text("x" * (ED.MAX_RECORD_BYTES + 1))
        os.symlink(t / "a.md", t / "link.md")
        r = ED.memory_recall_section([t])
        assert r["status"] == "degraded"
        assert (r["malformed"], r["oversize"], r["symlinks"]) == (2, 1, 1), r
        old = ED.MAX_FILES
        ED.MAX_FILES = 1
        try:
            assert ED.memory_recall_section([t])["truncated"] is True
        finally:
            ED.MAX_FILES = old


def test_missing_repo_is_unverified_not_pass():
    with tempfile.TemporaryDirectory() as d:
        doc = ED.collect(Path(d), memory_dirs=[])
        for name in ("outcomes", "projection", "lifecycle", "memory_recall", "eval_dimensions"):
            assert doc["sections"][name]["status"] == "unverified", (name, doc["sections"][name])
        assert doc["status"] == "unverified"
        assert set(doc["sections"]["eval_dimensions"]["unverified"]) == set(ED.EVAL_DIMENSIONS)


def test_lifecycle_states():
    with tempfile.TemporaryDirectory() as d:
        bad = Path(d) / "state.json"
        bad.write_text("{not json")
        assert ED.lifecycle_section(ROOT, str(bad))["status"] == "unverified"
        assert ED.lifecycle_section(ROOT, None)["reason"] == "dormant_no_state_observed"
        good = Path(d) / "ok.json"
        tel = {"handlers": {"h": {"count": 2, "failures": 1, "latency_avg_ms": 1, "latency_max_ms": 2}},
               "disabled": [], "queue_depth": 0, "totals": {"recursion_suppressed": 0, "rejected": 0}}
        good.write_text(json.dumps({"telemetry": tel}))
        r = ED.lifecycle_section(ROOT, str(good))
        assert r["status"] == "degraded" and r["failures"] == 1, r


def test_eval_dimension_gap_detected():
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        for name, (rel, marker) in ED.EVAL_DIMENSIONS.items():
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(marker if name != "cancellation" else "nothing")
        r = ED.eval_dimensions_section(repo)
        assert r["unverified"] == ["cancellation"] and r["status"] == "unverified"


def test_worst_wins_and_cli_exit_codes():
    p = subprocess.run([sys.executable, str(CLI), "--format", "json", "--memory-dir", "/nonexistent-ecc-p1"],
                       capture_output=True, text=True, check=False)
    doc = json.loads(p.stdout)
    assert doc["sections"]["memory_recall"]["status"] == "unverified"
    ranks = {"ok": 0, "unverified": 1, "degraded": 2}
    assert ranks[doc["status"]] == max(ranks[s["status"]] for s in doc["sections"].values())
    assert p.returncode == {"ok": 0, "unverified": 3, "degraded": 1}[doc["status"]]
    assert "ECC diagnostics:" in ED.render_text(doc)


def test_dashboard_summary_never_raises():
    s = ED.dashboard_summary(Path("/nonexistent-ecc-p1-repo"))
    assert s["available"] is True and s["status"] == "unverified"


def main() -> int:
    for t in (test_memory_recall, test_missing_repo_is_unverified_not_pass, test_lifecycle_states,
              test_eval_dimension_gap_detected, test_worst_wins_and_cli_exit_codes,
              test_dashboard_summary_never_raises):
        t()
    print("PASS: ECC diagnostics (6 checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
