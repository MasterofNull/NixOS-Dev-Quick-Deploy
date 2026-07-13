#!/usr/bin/env python3
"""Focused tests for the C0.3 dashboard governance projection.

Frozen filename (Intent-Lock): scripts/testing/test-dashboard-governance-projection.py

Asserts that the state-authority checker's published snapshot projects read-only onto the
EXISTING operator audit-integrity card (last check, age, blocker count) WITHOUT adding a new
route or runtime authority, that the projection is FAIL-CLOSED (any malformed / incomplete /
stale / wrong-identity snapshot degrades to available=false with null blockers — never an
invented zero), that the frontend renderer never coerces a missing blocker count to 0/OK,
that the read-only checker publishes nothing itself, and that the authorized Phase-0
integration is the sole atomic publisher (rejecting symlink targets). Uses synthetic snapshot
fixtures in a tempdir — it never mutates production dashboard/registry/telemetry state.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUDIT_PY = REPO / "dashboard" / "backend" / "api" / "routes" / "audit.py"
DASHBOARD_JS = REPO / "assets" / "dashboard.js"
CHECKER = REPO / "scripts" / "governance" / "check-state-authorities.py"
REGISTRY = REPO / "config" / "system-state-authorities.yaml"

_FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        _FAILURES.append(msg)


def _load_audit_module():
    backend = REPO / "dashboard" / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    mod = importlib.import_module("api.routes.audit")
    return importlib.reload(mod)


def _load_phase0():
    testing = REPO / "scripts" / "testing"
    if str(testing) not in sys.path:
        sys.path.insert(0, str(testing))
    return importlib.import_module("harness_qa.phases.phase0")


def _valid_meta(**over) -> dict:
    meta = {
        "slice": "C0.3",
        "artifact": "system-state-authorities",
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "registry_valid": True,
        "cycle1_authority": "NOT_AUTHORIZED",
        "blocker_count": 10,
        "authorities_total": 10,
        "condition_counts": {"SINGLE": 0, "SPLIT_BRAIN": 10, "UNKNOWN": 0, "UNOWNED": 0},
    }
    meta.update(over)
    return meta


def _write_snap(td: str, meta, findings=None, *, name="state-authorities-latest.json") -> Path:
    snap = Path(td) / name
    snap.write_text(json.dumps({"meta": meta, "findings": findings if findings is not None else []}),
                    encoding="utf-8")
    return snap


def _project(snap: Path) -> dict:
    mod = _load_audit_module()
    mod._STATE_AUTHORITY_SNAPSHOT = snap
    return mod._state_authorities_projection()


def _assert_unavailable(p: dict, label: str) -> None:
    check(p["available"] is False, f"{label}: must fail closed to available=False")
    check(p["blocker_count"] is None, f"{label}: must NOT fabricate a blocker count (got {p['blocker_count']})")
    check(p["cycle1_authority"] == "NOT_AUTHORIZED", f"{label}: default must still assert NOT_AUTHORIZED")


# --- Happy path ------------------------------------------------------------------------

def test_projection_reads_valid_snapshot() -> None:
    with tempfile.TemporaryDirectory() as td:
        snap = _write_snap(td, _valid_meta(
            blocker_count=7,
            condition_counts={"SINGLE": 3, "SPLIT_BRAIN": 7, "UNKNOWN": 0, "UNOWNED": 0},
        ))
        p = _project(snap)
        check(p["available"] is True, "valid snapshot should be available")
        check(p["blocker_count"] == 7, f"blocker_count not projected: {p['blocker_count']}")
        check(p["age_seconds"] is not None and p["age_seconds"] < 120,
              f"age_seconds implausible: {p['age_seconds']}")
        check(p["cycle1_authority"] == "NOT_AUTHORIZED",
              "projection must surface NOT_AUTHORIZED (no implicit storage authority)")
        check("aq-qa" in p["rebuild"] or "phase0" in p["rebuild"],
              "projection must name its rebuild source (the Phase-0 publisher)")


def test_projection_genuine_zero_is_ok() -> None:
    """A genuine integer 0 blocker count is a clean pass — the ONLY case that reads 0."""
    with tempfile.TemporaryDirectory() as td:
        snap = _write_snap(td, _valid_meta(
            blocker_count=0,
            condition_counts={"SINGLE": 10, "SPLIT_BRAIN": 0, "UNKNOWN": 0, "UNOWNED": 0},
        ))
        p = _project(snap)
        check(p["available"] is True, "valid zero-blocker snapshot should be available")
        check(p["blocker_count"] == 0, "genuine 0 must project as 0")


# --- Fail-closed fixtures --------------------------------------------------------------

def test_missing_snapshot_degrades() -> None:
    with tempfile.TemporaryDirectory() as td:
        p = _project(Path(td) / "does-not-exist.json")
        _assert_unavailable(p, "missing snapshot")


def test_corrupt_json_degrades() -> None:
    with tempfile.TemporaryDirectory() as td:
        snap = Path(td) / "corrupt.json"
        snap.write_text("{ not valid json", encoding="utf-8")
        _assert_unavailable(_project(snap), "corrupt json")


def test_incomplete_toplevel_degrades() -> None:
    with tempfile.TemporaryDirectory() as td:
        # findings key missing entirely
        snap = Path(td) / "s.json"
        snap.write_text(json.dumps({"meta": _valid_meta()}), encoding="utf-8")
        _assert_unavailable(_project(snap), "missing findings key")
        # extra top-level key
        snap.write_text(json.dumps({"meta": _valid_meta(), "findings": [], "extra": 1}), encoding="utf-8")
        _assert_unavailable(_project(snap), "extra top-level key")
        # findings not a list
        snap.write_text(json.dumps({"meta": _valid_meta(), "findings": {}}), encoding="utf-8")
        _assert_unavailable(_project(snap), "findings not a list")


def test_wrong_identity_degrades() -> None:
    with tempfile.TemporaryDirectory() as td:
        _assert_unavailable(_project(_write_snap(td, _valid_meta(slice="C0.2"))), "wrong slice")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(artifact="something-else"))), "wrong artifact")


def test_registry_invalid_degrades() -> None:
    with tempfile.TemporaryDirectory() as td:
        _assert_unavailable(_project(_write_snap(td, _valid_meta(registry_valid=False))), "registry_valid=false")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(registry_valid="true"))), "registry_valid truthy-string")


def test_wrong_cycle1_authority_degrades() -> None:
    with tempfile.TemporaryDirectory() as td:
        _assert_unavailable(_project(_write_snap(td, _valid_meta(cycle1_authority="AUTHORIZED"))),
                            "cycle1 AUTHORIZED must fail closed")


def test_bad_blocker_count_degrades() -> None:
    with tempfile.TemporaryDirectory() as td:
        m = _valid_meta()
        m.pop("blocker_count")
        _assert_unavailable(_project(_write_snap(td, m)), "missing blocker_count")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(blocker_count="7"))), "string blocker_count")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(blocker_count=7.0))), "float blocker_count")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(blocker_count=-1))), "negative blocker_count")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(blocker_count=True))), "bool blocker_count")


def test_bad_authorities_total_degrades() -> None:
    with tempfile.TemporaryDirectory() as td:
        _assert_unavailable(_project(_write_snap(td, _valid_meta(authorities_total=-5))), "negative authorities_total")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(authorities_total=None))), "null authorities_total")


def test_bad_condition_counts_degrades() -> None:
    with tempfile.TemporaryDirectory() as td:
        _assert_unavailable(_project(_write_snap(td, _valid_meta(condition_counts=[]))), "condition_counts list")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(condition_counts={"BOGUS": 1}))), "bad condition key")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(condition_counts={"SINGLE": -1}))), "negative cond val")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(condition_counts={"SINGLE": "1"}))), "string cond val")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(condition_counts={}))), "empty condition_counts")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(
            condition_counts={"SINGLE": 0, "SPLIT_BRAIN": 10, "UNKNOWN": 0},
        ))), "missing required condition key")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(
            condition_counts={"SINGLE": 1, "SPLIT_BRAIN": 10, "UNKNOWN": 0, "UNOWNED": 0},
        ))), "condition sum disagrees with authorities_total")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(blocker_count=0))),
                            "blocker_count below non-singleton authority count")


def test_bad_timestamp_degrades() -> None:
    with tempfile.TemporaryDirectory() as td:
        _assert_unavailable(_project(_write_snap(td, _valid_meta(run_at="not-a-date"))), "unparseable run_at")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(run_at="2026-07-12 10:00:00"))), "non-UTC run_at")
        _assert_unavailable(_project(_write_snap(td, _valid_meta(run_at=123))), "non-string run_at")
        stale = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3601))
        _assert_unavailable(_project(_write_snap(td, _valid_meta(run_at=stale))), "snapshot older than one hour")


def test_symlink_snapshot_degrades() -> None:
    with tempfile.TemporaryDirectory() as td:
        real = _write_snap(td, _valid_meta(), name="real.json")
        link = Path(td) / "state-authorities-latest.json"
        os.symlink(real, link)
        _assert_unavailable(_project(link), "symlinked snapshot")


# --- Structural: no new route, renderer present, no default-zero -----------------------

def test_no_new_route_added() -> None:
    """C0.3 must not add a runtime route: the audit router keeps exactly its 3 GET routes."""
    src = AUDIT_PY.read_text(encoding="utf-8")
    n = src.count("@router.")
    check(n == 3, f"audit.py has {n} @router routes; C0.3 must add none (expected 3)")
    check("state_authorities" in src and "_state_authorities_projection" in src,
          "audit integrity route must project state_authorities read-only")


def test_dashboard_renders_projection() -> None:
    js = DASHBOARD_JS.read_text(encoding="utf-8")
    check("stateAuthorityRows" in js, "dashboard.js missing stateAuthorityRows renderer")
    check("state_authorities" in js, "dashboard.js does not read state_authorities from the endpoint")
    check("State Auth Blockers" in js, "dashboard.js must show contested/unowned blocker count")


def test_dashboard_no_default_zero_blocker() -> None:
    """Frontend must NOT coerce a missing/unknown blocker count to 0 (which would read OK)."""
    js = DASHBOARD_JS.read_text(encoding="utf-8")
    # Extract the stateAuthorityRows body and assert the fail-open pattern is gone.
    start = js.find("function stateAuthorityRows")
    check(start >= 0, "stateAuthorityRows not found")
    body = js[start:start + 900]
    check("blocker_count ?? 0" not in body,
          "renderer still coerces missing blocker_count to 0 (fail-open)")
    check("Number.isInteger" in body,
          "renderer must integer-guard blocker_count before treating it as known")
    check("unknown (" in body,
          "renderer must render an unknown/degraded blocker state, not a silent zero")


# --- Read-only checker + Phase-0 is the sole publisher ---------------------------------

def test_checker_is_read_only_and_emits_contract() -> None:
    """The checker writes nothing; --machine emits exactly {meta, findings}; --snapshot is gone."""
    with tempfile.TemporaryDirectory() as td:
        # Run inside an empty cwd so any stray write would be visible; capture stdout contract.
        out = subprocess.run([sys.executable, str(CHECKER), "--machine"],
                             capture_output=True, text=True, cwd=str(REPO))
        check(out.returncode in (0, 1), f"--machine exit {out.returncode}: {out.stderr[:200]}")
        doc = json.loads(out.stdout)
        check(set(doc.keys()) == {"meta", "findings"}, "machine output is not {meta, findings}")
        check("run_at" in doc["meta"] and "blocker_count" in doc["meta"],
              "meta must carry run_at + blocker_count for the card")
        check(doc["meta"].get("slice") == "C0.3" and doc["meta"].get("artifact") == "system-state-authorities",
              "meta must carry slice/artifact identity for fail-closed projection")
        # --snapshot must no longer exist as an argument (read-only contract).
        rej = subprocess.run([sys.executable, str(CHECKER), "--machine", "--snapshot", str(Path(td) / "x.json")],
                             capture_output=True, text=True, cwd=str(REPO))
        check(rej.returncode == 2, "--snapshot must be rejected (argparse error) — checker is read-only")
        check(not (Path(td) / "x.json").exists(), "checker must not write any snapshot file")


def test_phase0_publisher_atomic_and_refuses_symlink() -> None:
    p0 = _load_phase0()
    doc = {"meta": _valid_meta(), "findings": []}
    encoded = json.dumps(doc, indent=2)
    check(p0._validate_state_authority_doc(doc) is None, "valid doc must pass phase0 validation")
    check(p0._validate_state_authority_doc({"meta": _valid_meta(blocker_count=-1), "findings": []}) is not None,
          "phase0 validation must reject negative blocker_count")
    check(p0._validate_state_authority_doc({"meta": _valid_meta(condition_counts={}), "findings": []}) is not None,
          "phase0 validation must reject missing condition keys")
    check(p0._validate_state_authority_doc({
        "meta": _valid_meta(
            condition_counts={"SINGLE": 1, "SPLIT_BRAIN": 10, "UNKNOWN": 0, "UNOWNED": 0},
        ),
        "findings": [],
    }) is not None, "phase0 validation must reject a condition total mismatch")
    check(p0._validate_state_authority_doc({"meta": _valid_meta(blocker_count=0), "findings": []}) is not None,
          "phase0 validation must reject blockers below the non-singleton count")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".agents" / "governance").mkdir(parents=True)
        err = p0._publish_state_authority_snapshot(root, encoded)
        check(err is None, f"publish should succeed under a clean root: {err}")
        target = root / ".agents" / "governance" / "state-authorities-latest.json"
        check(target.exists() and not target.is_symlink(), "publisher must write the fixed regular-file target")
        written = json.loads(target.read_text())
        check(written["meta"]["slice"] == "C0.3", "published content mismatch")
        # Replace target with a symlink -> publisher must refuse to write through it.
        os.unlink(target)
        os.symlink(root / "elsewhere.json", target)
        err2 = p0._publish_state_authority_snapshot(root, encoded)
        check(err2 is not None, "publisher must refuse a symlinked target")
        check(not (root / "elsewhere.json").exists(), "publisher must not write through the symlink")


def test_phase0_publisher_refuses_precreated_temp_symlink() -> None:
    p0 = _load_phase0()
    encoded = json.dumps({"meta": _valid_meta(), "findings": []}, indent=2)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gov = root / ".agents" / "governance"
        gov.mkdir(parents=True)
        redirected = root / "redirected.json"
        tmp = gov / f"state-authorities-latest.json.tmp.{os.getpid()}"
        os.symlink(redirected, tmp)
        err = p0._publish_state_authority_snapshot(root, encoded)
        check(err is not None, "publisher must refuse a pre-created temporary symlink")
        check(tmp.is_symlink(), "publisher must not delete a temporary path it did not create")
        check(not redirected.exists(), "publisher must not write through a temporary symlink")
        check(not (gov / "state-authorities-latest.json").exists(),
              "publisher must not replace the target after temporary-path refusal")


def test_shim_telemetry_and_deadline_present() -> None:
    import yaml
    reg = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    for a in reg["authorities"]:
        for s in a.get("shims", []):
            check(bool(str(s.get("owner", "")).strip()), f"{a['id']}: shim {s.get('name')} lacks owner")
            check(bool(str(s.get("telemetry", "")).strip()),
                  f"{a['id']}: shim {s.get('name')} lacks usage/divergence telemetry")
            check(bool(str(s.get("deadline", "")).strip()),
                  f"{a['id']}: shim {s.get('name')} lacks deadline")
    for a in reg["authorities"]:
        for p in a.get("projections", []):
            check(bool(str(p.get("rebuild_source", "")).strip()),
                  f"{a['id']}: projection {p.get('name')} lacks rebuild_source")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        try:
            t()
        except Exception as exc:  # noqa: BLE001
            _FAILURES.append(f"{t.__name__} raised {type(exc).__name__}: {exc}")
    if _FAILURES:
        print(f"FAIL ({len(_FAILURES)}):")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1
    print(f"PASS: {len(tests)} dashboard governance projection checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
