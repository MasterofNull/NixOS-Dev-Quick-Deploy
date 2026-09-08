#!/usr/bin/env python3
"""Flow tests for the guided install (P1) — hardware-honest AI + non-destructive."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUIDED = REPO / "scripts" / "ai" / "aqos-guided-install"
AIFIT = REPO / "scripts" / "ai" / "lib" / "ai_fit.py"
CATALOG = REPO / "config" / "aqos-ai-fit-policy-catalog-v1.json"
GIB = 1024**3


def load(path, name):
    # SourceFileLoader handles the extensionless `aqos-guided-install` script too.
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    loader.exec_module(m)
    return m


def _cat():
    fit = load(AIFIT, "ai_fit")
    return fit.load_catalog(CATALOG)  # (catalog, digest)


def _hw(ram_bytes, *, present=False, outcome="none", mem=None, vendor=None, vram=None):
    primary = {"memory_type": mem, "vendor_id": vendor, "vram_total_bytes": vram} if present else None
    return {"schema_version": 2, "ram": {"total_bytes": ram_bytes},
            "gpu": {"present": present, "outcome": outcome, "devices": [{}] if present else [], "primary": primary}}


def test_ai_off_by_default_when_not_advised():
    g = load(GUIDED, "guided")
    cat, dig = _cat()
    hw = _hw(2 * GIB)  # too small -> not_advised
    r = g.run(hw, cat, dig, host_target="h", ai_choice=None)
    assert r["ai"]["verdict"] == "not_advised"
    assert r["request"]["selection"]["include_local_ai"] is False


def test_ai_on_by_default_when_recommended():
    g = load(GUIDED, "guided")
    cat, dig = _cat()
    hw = _hw(64 * GIB, present=True, outcome="detected", mem="dedicated", vendor="0x10de", vram=24 * GIB)
    r = g.run(hw, cat, dig, host_target="h", ai_choice=None)
    assert r["ai"]["verdict"] == "recommended"
    assert r["request"]["selection"]["include_local_ai"] is True
    assert r["ai"]["recommended_model"]


def test_explicit_yes_on_weak_hw_warns_but_honors():
    g = load(GUIDED, "guided")
    cat, dig = _cat()
    hw = _hw(2 * GIB)  # not_advised
    r = g.run(hw, cat, dig, host_target="h", ai_choice="yes")
    assert r["request"]["selection"]["include_local_ai"] is True
    assert r["ai"]["warning"] and "NOT ADVISED" in r["ai"]["warning"]


def test_request_is_resolver_guided_shape():
    g = load(GUIDED, "guided")
    req = g.build_guided_request("myhost", True, roles=["role.gaming"])
    assert req["artifact_type"] == "request_plan"
    assert req["schema_version"] == "aqos-install-plan/v1"
    assert req["selection"]["golden_profile"] == "aqos-workstation"
    assert req["selection"]["include_local_ai"] is True
    assert req["selection"]["roles"] == ["role.gaming"]
    assert req["host_target"] == "myhost"


def test_flow_is_non_destructive():
    """run() touches no disk; the CLI writes ONLY the --out request file, nothing else."""
    g = load(GUIDED, "guided")
    cat, dig = _cat()
    hw = _hw(32 * GIB, present=True, outcome="detected", mem="shared", vendor="0x1002")
    with tempfile.TemporaryDirectory() as d:
        before = set(Path(d).iterdir())
        g.run(hw, cat, dig, host_target="h", ai_choice="no")  # pure core -> no writes at all
        assert set(Path(d).iterdir()) == before
        # CLI with --out writes exactly one file (the request), and nothing else in the dir
        out = Path(d) / "req.json"
        hwf = Path(d) / "hw.json"; hwf.write_text(json.dumps(hw))
        rc = g.main(["--hardware", str(hwf), "--out", str(out), "--host-target", "h", "--ai", "no", "--json"])
        assert rc == 0 and out.exists()
        assert set(p.name for p in Path(d).iterdir()) == {"req.json", "hw.json"}
        assert json.loads(out.read_text())["selection"]["include_local_ai"] is False


def main() -> int:
    test_ai_off_by_default_when_not_advised()
    test_ai_on_by_default_when_recommended()
    test_explicit_yes_on_weak_hw_warns_but_honors()
    test_request_is_resolver_guided_shape()
    test_flow_is_non_destructive()
    print("test-aqos-guided-install: ok 5/5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
