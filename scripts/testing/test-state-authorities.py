#!/usr/bin/env python3
"""Focused, isolated tests for the C0.3 state-authority registry + bounded checker.

Frozen filename (Intent-Lock): scripts/testing/test-state-authorities.py

These tests touch NO production collaboration/telemetry/registry/database state. The
undeclared-writer, exclusion, and truncation cases run against synthetic fixtures in a
tempdir with the checker's REPO_ROOT monkeypatched, so they never create production debt.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / "scripts" / "governance" / "check-state-authorities.py"
REGISTRY = REPO / "config" / "system-state-authorities.yaml"
SCHEMA = REPO / "config" / "schemas" / "system-state-authorities.schema.json"

_FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        _FAILURES.append(msg)


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_state_authorities", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _load_registry():
    import yaml
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def test_registry_schema_valid() -> None:
    reg = _load_registry()
    check(isinstance(reg, dict) and "meta" in reg and "authorities" in reg,
          "registry missing meta/authorities")
    try:
        import jsonschema
        jsonschema.validate(reg, json.loads(SCHEMA.read_text()))
    except ImportError:
        pass  # structural fallback below still runs
    except Exception as exc:  # noqa: BLE001
        check(False, f"registry fails schema: {str(exc)[:200]}")


def test_registry_contract() -> None:
    """No invented singleton; projections rebuildable; shims fully owned; bounds honored."""
    reg = _load_registry()
    meta = reg["meta"]
    auths = reg["authorities"]
    check(meta.get("cycle1_authority") == "NOT_AUTHORIZED",
          "meta.cycle1_authority must be NOT_AUTHORIZED (discovery confers no storage authority)")
    check(len(auths) <= 128, f"registry has {len(auths)} objects > 128 ceiling")
    scan = meta.get("scan", {})
    check(scan.get("file_cap", 99999) <= 8000, "scan.file_cap must be <= 8000")
    check(len(scan.get("exclusions", [])) >= 1, "scan.exclusions must be explicit and non-empty")
    for a in auths:
        aid = a.get("id")
        check(a.get("current_condition") in ("SINGLE", "SPLIT_BRAIN", "UNKNOWN", "UNOWNED"),
              f"{aid}: bad current_condition")
        if a.get("current_condition") != "SINGLE":
            check(a.get("selected_target_authority") is None,
                  f"{aid}: non-SINGLE must not invent a selected_target_authority")
        for p in a.get("projections", []):
            check(bool(str(p.get("rebuild_source", "")).strip()),
                  f"{aid}: projection {p.get('name')} lacks rebuild_source")
        for s in a.get("shims", []):
            for k in ("owner", "telemetry", "deadline"):
                check(bool(str(s.get(k, "")).strip()),
                      f"{aid}: shim {s.get('name')} missing {k}")
        # Every authority carries an adjudicator/recovery owner and resolution deadline.
        check(bool(str(a.get("adjudicator", "")).strip()), f"{aid}: missing adjudicator")
        check(bool(str(a.get("resolution_deadline", "")).strip()), f"{aid}: missing resolution_deadline")


def test_checker_full_run_shape_and_budget() -> None:
    mod = _load_checker()
    meta, findings, code = mod.run("full", strict=False)
    check(code == 0, f"full run should exit 0 for healthy discovery, got {code}")
    check(isinstance(meta, dict) and isinstance(findings, list), "output not {meta, findings}")
    # Blocker count == number of non-SINGLE conditions + any undeclared-writer/truncation findings.
    reg = _load_registry()
    non_single = sum(1 for a in reg["authorities"] if a["current_condition"] != "SINGLE")
    check(meta["blocker_count"] >= non_single,
          f"blocker_count {meta['blocker_count']} < non-SINGLE conditions {non_single}")
    check(meta["error_count"] == 0, f"unexpected structural errors: {meta['error_count']}")
    check(meta["files_scanned"] <= meta["file_cap"] <= 8000, "scan exceeded file cap")
    check(meta["budget"]["ok"] is True, f"budget breached: {meta['budget']}")
    check(meta["budget"]["duration_seconds"] <= 15.0, "full run exceeded 15s")
    check(meta["cycle1_authority"] == "NOT_AUTHORIZED", "meta must assert NOT_AUTHORIZED")


def test_machine_output_is_exact_contract() -> None:
    """--machine prints exactly a JSON object with keys {meta, findings}."""
    import subprocess
    out = subprocess.run([sys.executable, str(CHECKER), "--machine"],
                         capture_output=True, text=True, cwd=str(REPO))
    check(out.returncode == 0, f"--machine exit {out.returncode}")
    doc = json.loads(out.stdout)
    check(set(doc.keys()) == {"meta", "findings"},
          f"machine output keys {set(doc.keys())} != {{meta, findings}}")


def test_incremental_mode_bounded() -> None:
    mod = _load_checker()
    meta, findings, code = mod.run("incremental", strict=False)
    check(code in (0, 1), f"incremental exit {code}")
    check(meta["mode"] == "incremental", "mode not incremental")
    check(meta["budget"]["duration_seconds"] <= 10.0, "incremental exceeded 10s")


def test_undeclared_writer_fixture_fails() -> None:
    """A synthetic tracked-like file that writes a declared store must be reported."""
    mod = _load_checker()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        mod.REPO_ROOT = root  # isolate the scan under a tempdir
        # Code write of a declared store -> must be flagged.
        (root / "rogue_writer.py").write_text(
            'p = open("registry.jsonl", "a")\np.write("x")\n', encoding="utf-8")
        # Prose/comment mentioning the same store -> must NOT be flagged.
        (root / "doc_only.nix").write_text(
            '      description = "owns registry.jsonl and appends via open()";\n', encoding="utf-8")
        auths = [{
            "id": "delegation-lifecycle",
            "observed_writers": [],
            "writer_signatures": [{"store_token": "registry.jsonl", "write_tokens": ["open(", "write"]}],
        }]
        findings: list[dict] = []
        mod._scan_undeclared_writers(auths, ["rogue_writer.py", "doc_only.nix"], findings)
        uw = [f for f in findings if f["kind"] == "undeclared_writer"]
        check(any(f["path"] == "rogue_writer.py" for f in uw),
              "undeclared code writer was not reported (fixture must fail closed)")
        check(all(f["path"] != "doc_only.nix" for f in uw),
              "prose/description line was wrongly reported as a writer")
        check(all(f["blocks_ratification"] for f in uw),
              "undeclared writer must block ratification")


def test_exclusions_do_not_create_production_debt() -> None:
    mod = _load_checker()
    reg = _load_registry()
    excl = reg["meta"]["scan"]["exclusions"]
    check(mod._excluded("scripts/testing/test-foo.py", excl), "test paths must be excluded")
    check(mod._excluded("docs/architecture/x.md", excl), "docs must be excluded")
    check(mod._excluded("assets/app.min.js", excl), "generated .min.js must be excluded")
    check(not mod._excluded("scripts/ai/aq-collab-round", excl),
          "production script must NOT be excluded")


def test_truncation_is_degraded_and_bounded() -> None:
    """Force a tiny cap and assert truncation is reported (DEGRADED) but still bounded."""
    mod = _load_checker()
    original = mod.FILE_CAP_CEILING
    try:
        mod.FILE_CAP_CEILING = 5
        meta, findings, code = mod.run("full", strict=False)
        check(meta["truncated"] is True, "truncation flag not set at tiny cap")
        check(meta["files_scanned"] <= 5, "scan not bounded to tiny cap")
        check(any(f["kind"] == "scan_truncated" for f in findings),
              "scan_truncated finding missing")
        check(any(f["kind"] == "scan_truncated" and f["blocks_ratification"] for f in findings),
              "truncation must block ratification")
    finally:
        mod.FILE_CAP_CEILING = original


def test_checker_is_read_only() -> None:
    """The checker never writes: no --snapshot argument, no file side effects."""
    import subprocess
    src = CHECKER.read_text(encoding="utf-8")
    check('add_argument("--snapshot"' not in src and "add_argument('--snapshot'" not in src,
          "checker must not register a --snapshot write argument")
    for token in ("write_text(", ".replace(", "mkdir("):
        check(token not in src, f"checker must not write files (found {token!r})")
    with tempfile.TemporaryDirectory() as td:
        rej = subprocess.run([sys.executable, str(CHECKER), "--machine", "--snapshot", str(Path(td) / "x.json")],
                             capture_output=True, text=True, cwd=str(REPO))
        check(rej.returncode == 2, "--snapshot must be rejected as an unknown argument")
        check(not (Path(td) / "x.json").exists(), "checker must not create any snapshot file")


def test_explain_known_and_unknown() -> None:
    import subprocess
    ok = subprocess.run([sys.executable, str(CHECKER), "--explain", "planning-round"],
                        capture_output=True, text=True, cwd=str(REPO))
    check(ok.returncode == 0 and '"id": "planning-round"' in ok.stdout,
          "--explain of a known object failed")
    bad = subprocess.run([sys.executable, str(CHECKER), "--explain", "does-not-exist"],
                         capture_output=True, text=True, cwd=str(REPO))
    check(bad.returncode == 2, "--explain of unknown object must exit 2")


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
    print(f"PASS: {len(tests)} state-authority checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
