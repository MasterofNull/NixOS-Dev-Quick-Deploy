#!/usr/bin/env python3
"""27-case focused contract suite for the read-only C0.3 authority checker.

All mutation occurs only inside temporary directories. The production registry,
collaboration state, telemetry, databases, and services are never written.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / "scripts" / "governance" / "check-state-authorities.py"
REGISTRY = REPO / "config" / "system-state-authorities.yaml"
SCHEMA = REPO / "config" / "schemas" / "system-state-authorities.schema.json"
FIXED_DATE = date(2026, 7, 18)

_FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        _FAILURES.append(message)


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_state_authorities", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _load_registry() -> dict:
    import yaml
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def _schema_errors(authority: dict) -> list[str]:
    import jsonschema
    registry = _load_registry()
    registry["authorities"] = [authority]
    validator = jsonschema.Draft7Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    return [error.message for error in validator.iter_errors(registry)]


def _pending_authority(condition: str = "SPLIT_BRAIN") -> dict:
    authority = copy.deepcopy(_load_registry()["authorities"][0])
    authority["current_condition"] = condition
    authority["selected_target_authority"] = None
    for key in ("adjudication_status", "transition_owner", "decision_provenance",
                "rollback_boundary"):
        authority.pop(key, None)
    return authority


def _write_decision(root: Path, name: str = "owner-decision.md") -> tuple[str, str]:
    source = root / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("owner decision evidence\n", encoding="utf-8")
    return source.relative_to(root).as_posix(), hashlib.sha256(source.read_bytes()).hexdigest()


def _adjudicated_authority(root: Path, condition: str = "SPLIT_BRAIN") -> dict:
    authority = _pending_authority(condition)
    source_path, source_sha = _write_decision(root)
    authority.update({
        "adjudication_status": "ADJUDICATED",
        "selected_target_authority": "coordinator-owned-state",
        "transition_owner": "Platform Operations",
        "decision_provenance": {
            "decision_id": "foundation-a.owner-20260717",
            "authority": "OWNER",
            "decided_by": "Repository Owner Alice",
            "decision_date": "2026-07-17",
            "source_path": source_path,
            "source_sha256": source_sha,
        },
        "rollback_boundary": {
            "owner": "Platform Operations",
            "trigger": "divergence exceeds zero confirmed writes",
            "action": "stop transition and retain the declared legacy authority",
            "authority_during_rollback": "declared legacy authority",
        },
        "resolution_deadline": "2026-12-31",
    })
    return authority


def _adjudication_findings(mod, root: Path, authority: dict,
                           check_date: date = FIXED_DATE) -> tuple[list[dict], set[str]]:
    original_root = mod.REPO_ROOT
    try:
        mod.REPO_ROOT = root
        findings: list[dict] = []
        blocked = mod._validate_adjudications([authority], findings, check_date)
        return findings, blocked
    finally:
        mod.REPO_ROOT = original_root


def _semantic_run(mod, mode: str, *, strict: bool, check_date: date):
    """Run semantic fixtures without inheriting the test runner's lifetime RSS peak."""
    original_peak_rss = mod._peak_rss_mib
    try:
        mod._peak_rss_mib = lambda: 0.0
        return mod.run(mode, strict=strict, check_date=check_date)
    finally:
        mod._peak_rss_mib = original_peak_rss


def _run_temp_registry(mod, root: Path, registry: dict,
                       check_date: date = FIXED_DATE) -> tuple[dict, list[dict], int]:
    import yaml
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    registry_path = config_dir / "system-state-authorities.yaml"
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    original_root, original_registry = mod.REPO_ROOT, mod.REGISTRY_PATH
    original_tracked, original_changed = mod._git_tracked, mod._git_changed
    try:
        mod.REPO_ROOT = root
        mod.REGISTRY_PATH = registry_path
        mod._git_tracked = lambda: []
        mod._git_changed = lambda: []
        return _semantic_run(mod, "full", strict=False, check_date=check_date)
    finally:
        mod.REPO_ROOT, mod.REGISTRY_PATH = original_root, original_registry
        mod._git_tracked, mod._git_changed = original_tracked, original_changed


def test_01_production_registry_is_content_bound_adjudicated() -> None:
    mod = _load_checker()
    registry = _load_registry()
    expected_ids = {
        "planning-round", "delegation-lifecycle", "intent-resume", "workflow-run-task",
        "qa-effectiveness", "routing-model-execution", "learning-eval", "memory-rag",
        "configuration", "dashboard-operator",
    }
    check({row["id"] for row in registry["authorities"]} == expected_ids,
          "production registry authority IDs changed")
    check(all(row.get("adjudication_status") == "ADJUDICATED"
              for row in registry["authorities"]),
          "production registry must contain ten adjudicated rows")
    check(all(row["current_condition"] == "SPLIT_BRAIN"
              for row in registry["authorities"]),
          "owner adjudication must not rewrite observed SPLIT_BRAIN conditions")
    check(registry["meta"]["cycle1_authority"] == "NOT_AUTHORIZED",
          "owner adjudication must not authorize Cycle 1")
    expected_source_sha = "3c05728f8011db002b8c1504757dd1b43421f151268718a0c275219ccd15bc7a"
    check(all(row["decision_provenance"]["decision_id"] ==
              "foundation-a-authority-targets-20260718" and
              row["decision_provenance"]["source_sha256"] == expected_source_sha
              for row in registry["authorities"]),
          "production adjudications are not content-bound to the accepted owner decision")
    meta, _, code = _semantic_run(mod, "incremental", strict=False, check_date=FIXED_DATE)
    check(code == 0, f"adjudicated production registry run failed with {code}")
    check(meta["adjudication_counts"] == {"PENDING": 0, "ADJUDICATED": 10},
          f"production adjudication counts are wrong: {meta['adjudication_counts']}")


def test_02_production_registry_retains_convergence_only_blockers() -> None:
    mod = _load_checker()
    meta, findings, code = _semantic_run(
        mod, "incremental", strict=False, check_date=FIXED_DATE
    )
    check(code == 0, f"production blocker-dimension run failed with {code}")
    check(meta["owner_decision_blocker_count"] == 0,
          "accepted owner decisions must clear all owner-decision blockers")
    check(meta["observed_convergence_blocker_count"] == 10,
          "expected 10 convergence-blocked rows")
    check(meta["blocker_count"] == 10, "expected 10 aggregate convergence blockers")
    check(all(not f["owner_decision_blocker"] and f["observed_convergence_blocker"]
              for f in findings if f["kind"] == "condition_split_brain"),
          "adjudicated SPLIT_BRAIN findings must be convergence-only blockers")


def test_03_pending_all_adjudication_fields_absent_valid() -> None:
    check(not _schema_errors(_pending_authority()), "PENDING/absent adjudication fields must validate")


def test_04_pending_non_null_target_rejected() -> None:
    authority = _pending_authority()
    authority["selected_target_authority"] = "invented-target"
    check(bool(_schema_errors(authority)), "PENDING with selected target must fail schema")


def test_05_pending_transition_provenance_or_rollback_rejected() -> None:
    values = {
        "transition_owner": "Someone",
        "decision_provenance": {},
        "rollback_boundary": {},
    }
    for key, value in values.items():
        authority = _pending_authority()
        authority[key] = value
        check(bool(_schema_errors(authority)), f"PENDING with {key} must fail schema")


def test_06_adjudicated_split_brain_structurally_valid() -> None:
    with tempfile.TemporaryDirectory() as td:
        authority = _adjudicated_authority(Path(td), "SPLIT_BRAIN")
        check(not _schema_errors(authority), "ADJUDICATED + SPLIT_BRAIN must be schema-valid")
        check(authority["current_condition"] == "SPLIT_BRAIN", "observation was rewritten")


def test_07_adjudicated_unknown_remains_unconverged() -> None:
    mod = _load_checker()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        authority = _adjudicated_authority(root, "UNKNOWN")
        findings, blocked = _adjudication_findings(mod, root, authority)
        mod._condition_findings([authority], findings, blocked)
        condition = next(f for f in findings if f["kind"] == "condition_unknown")
        check(condition["observed_convergence_blocker"], "UNKNOWN must remain unconverged")
        check(not condition["owner_decision_blocker"], "valid adjudication must clear decision dimension")


def test_08_adjudicated_unowned_remains_unconverged() -> None:
    mod = _load_checker()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        authority = _adjudicated_authority(root, "UNOWNED")
        findings, blocked = _adjudication_findings(mod, root, authority)
        mod._condition_findings([authority], findings, blocked)
        condition = next(f for f in findings if f["kind"] == "condition_unowned")
        check(condition["observed_convergence_blocker"], "UNOWNED must remain unconverged")
        check(authority["current_condition"] == "UNOWNED", "UNOWNED observation was rewritten")


def test_09_adjudicated_without_target_rejected() -> None:
    with tempfile.TemporaryDirectory() as td:
        authority = _adjudicated_authority(Path(td))
        authority["selected_target_authority"] = None
        check(bool(_schema_errors(authority)), "ADJUDICATED without target must fail schema")


def test_10_adjudicated_missing_each_required_field_rejected() -> None:
    with tempfile.TemporaryDirectory() as td:
        base = _adjudicated_authority(Path(td))
        for key in ("transition_owner", "decision_provenance", "rollback_boundary",
                    "resolution_deadline"):
            authority = copy.deepcopy(base)
            authority.pop(key)
            check(bool(_schema_errors(authority)), f"ADJUDICATED missing {key} must fail schema")


def test_11_unknown_adjudication_status_rejected() -> None:
    authority = _pending_authority()
    authority["adjudication_status"] = "APPROVED"
    check(bool(_schema_errors(authority)), "unknown adjudication status must fail schema")


def test_12_decision_provenance_is_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        authority = _adjudicated_authority(Path(td))
        authority["decision_provenance"]["model_vote"] = "consensus"
        check(bool(_schema_errors(authority)), "extra decision_provenance property must fail")


def test_13_rollback_boundary_is_closed() -> None:
    mod = _load_checker()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        authority = _adjudicated_authority(root)
        authority["rollback_boundary"]["command"] = "restore-every-writer"
        check(bool(_schema_errors(authority)), "extra rollback_boundary property must fail")
        base = _adjudicated_authority(root)
        for key in ("owner", "trigger", "action", "authority_during_rollback"):
            blank = copy.deepcopy(base)
            blank["rollback_boundary"][key] = " \t "
            check(bool(_schema_errors(blank)), f"whitespace-only rollback {key} must fail schema")
            findings, blocked = _adjudication_findings(mod, root, blank)
            check(blank["id"] in blocked, f"whitespace-only rollback {key} passed checker")
            check(any(f["kind"] == "adjudication_incomplete" for f in findings),
                  f"whitespace-only rollback {key} lacked incomplete finding")
        findings, blocked = _adjudication_findings(mod, root, base)
        check(base["id"] not in blocked, f"nonblank rollback contract was rejected: {findings}")


def test_14_invalid_provenance_scalars_and_calendar_rejected() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base = _adjudicated_authority(root)
        invalid = {
            "decision_id": "NO",
            "authority": "MODEL_CONSENSUS",
            "decision_date": "2026/07/17",
            "source_sha256": "abc",
        }
        for key, value in invalid.items():
            authority = copy.deepcopy(base)
            authority["decision_provenance"][key] = value
            check(bool(_schema_errors(authority)), f"invalid {key} must fail schema")
        authority = copy.deepcopy(base)
        authority["decision_provenance"]["decision_date"] = "2026-02-30"
        findings, _ = _adjudication_findings(_load_checker(), root, authority)
        check(any(f["kind"] == "adjudication_provenance_invalid" for f in findings),
              "invalid calendar date must produce provenance blocker")


def test_15_provenance_path_and_digest_attacks_blocked() -> None:
    mod = _load_checker()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base = _adjudicated_authority(root)
        (root / "directory-source").mkdir()
        (root / "link-source").symlink_to(root / "owner-decision.md")
        attacks = [
            ("/etc/passwd", base["decision_provenance"]["source_sha256"]),
            ("../escape.md", base["decision_provenance"]["source_sha256"]),
            ("missing.md", base["decision_provenance"]["source_sha256"]),
            ("link-source", base["decision_provenance"]["source_sha256"]),
            ("directory-source", base["decision_provenance"]["source_sha256"]),
            ("owner-decision.md", "0" * 64),
        ]
        for source_path, source_sha in attacks:
            authority = copy.deepcopy(base)
            authority["decision_provenance"]["source_path"] = source_path
            authority["decision_provenance"]["source_sha256"] = source_sha
            findings, blocked = _adjudication_findings(mod, root, authority)
            check(authority["id"] in blocked, f"attack {source_path!r} did not block row")
            check(any(f["kind"] == "adjudication_provenance_invalid" for f in findings),
                  f"attack {source_path!r} lacked provenance finding")


def test_16_valid_content_bound_provenance_passes() -> None:
    mod = _load_checker()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        authority = _adjudicated_authority(root)
        findings, blocked = _adjudication_findings(mod, root, authority)
        check(authority["id"] not in blocked, f"valid provenance blocked: {findings}")
        check(not any(f["kind"] == "adjudication_provenance_invalid" for f in findings),
              "valid provenance produced invalid finding")


def test_17_decided_by_frozen_normalization_and_placeholders() -> None:
    mod = _load_checker()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base = _adjudicated_authority(root)
        placeholders = [
            "ＯＷＮＥＲ", " System---Owner ", "system___owner", "To Be Determined", "N/A", "DECIDER",
            "unassigned", "Dr. UNKNOWN, Esq.", "TBD", "none", "still pending review",
        ]
        for identity in placeholders:
            authority = copy.deepcopy(base)
            authority["decision_provenance"]["decided_by"] = identity
            findings, blocked = _adjudication_findings(mod, root, authority)
            check(authority["id"] in blocked, f"placeholder {identity!r} was accepted")
            check(any(f["kind"] == "adjudication_placeholder_decided_by" for f in findings),
                  f"placeholder {identity!r} lacked frozen finding")
        authority = copy.deepcopy(base)
        authority["decision_provenance"]["decided_by"] = "  Alice---Example, Repository Owner  "
        findings, blocked = _adjudication_findings(mod, root, authority)
        check(authority["id"] not in blocked, f"concrete identity was rejected: {findings}")


def test_18_placeholder_transition_and_rollback_owners_blocked() -> None:
    mod = _load_checker()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base = _adjudicated_authority(root)
        for path, value in (("transition_owner", "UNASSIGNED"),
                            ("rollback_owner", "pending")):
            authority = copy.deepcopy(base)
            if path == "transition_owner":
                authority[path] = value
            else:
                authority["rollback_boundary"]["owner"] = value
            findings, blocked = _adjudication_findings(mod, root, authority)
            check(authority["id"] in blocked, f"placeholder {path} was accepted")
            check(any(f["kind"] == "adjudication_incomplete" for f in findings),
                  f"placeholder {path} lacked incomplete finding")
        concrete = copy.deepcopy(base)
        concrete["transition_owner"] = "Pending Migration Review Team"
        findings, blocked = _adjudication_findings(mod, root, concrete)
        check(concrete["id"] not in blocked,
              f"named owner containing ordinary word 'pending' was rejected: {findings}")


def test_19_injected_utc_date_future_is_distinct() -> None:
    mod = _load_checker()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        future = _adjudicated_authority(root)
        future["decision_provenance"]["decision_date"] = "2026-07-19"
        findings, _ = _adjudication_findings(mod, root, future, FIXED_DATE)
        date_kinds = [f["kind"] for f in findings if "date" in f["kind"] or "chronology" in f["kind"]]
        check(date_kinds == ["adjudication_decision_date_future"],
              f"future decision did not emit exactly the future-date kind: {date_kinds}")
        current = _adjudicated_authority(root)
        findings, blocked = _adjudication_findings(mod, root, current, FIXED_DATE)
        check(current["id"] not in blocked, f"decision on injected date rejected: {findings}")


def test_20_decision_after_deadline_emits_chronology() -> None:
    mod = _load_checker()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        authority = _adjudicated_authority(root)
        authority["decision_provenance"]["decision_date"] = "2026-07-16"
        authority["resolution_deadline"] = "2026-07-15"
        findings, blocked = _adjudication_findings(mod, root, authority, FIXED_DATE)
        check(authority["id"] in blocked, "invalid chronology did not block owner decision")
        check(any(f["kind"] == "adjudication_chronology_invalid" for f in findings),
              "chronology finding missing")


def test_21_expired_deadline_is_integrity_only_and_read_only() -> None:
    mod = _load_checker()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        authority = _adjudicated_authority(root)
        authority["decision_provenance"]["decision_date"] = "2026-07-01"
        authority["resolution_deadline"] = "2026-07-16"
        before = copy.deepcopy(authority)
        findings, blocked = _adjudication_findings(mod, root, authority, FIXED_DATE)
        expired = [f for f in findings if f["kind"] == "adjudication_deadline_expired"]
        check(authority["id"] not in blocked, "expiry must not become owner-decision dimension")
        check(len(expired) == 1 and expired[0]["blocks_ratification"], "expiry blocker missing")
        check(not expired[0]["owner_decision_blocker"] and
              not expired[0]["observed_convergence_blocker"],
              "expiry dimensions must both be false")
        check(authority == before, "deadline validation mutated authority row")


def test_22_complete_split_brain_retains_convergence_only_finding() -> None:
    mod = _load_checker()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        authority = _adjudicated_authority(root)
        findings, blocked = _adjudication_findings(mod, root, authority)
        mod._condition_findings([authority], findings, blocked)
        condition = next(f for f in findings if f["kind"] == "condition_split_brain")
        check(not condition["owner_decision_blocker"], "complete decision still marked pending")
        check(condition["observed_convergence_blocker"], "convergence blocker was cleared")
        check(condition["blocks_ratification"], "aggregate ratification gate was relaxed")
        check("target is adjudicated" in condition["detail"] and
              "until adjudicated" not in condition["detail"],
              f"convergence-only detail is false: {condition['detail']}")


def test_23_exact_stage_a_and_fully_adjudicated_counts() -> None:
    mod = _load_checker()
    meta, findings, code = _semantic_run(
        mod, "incremental", strict=False, check_date=FIXED_DATE
    )
    expected_production = {
        "authorities_total": 10,
        "condition_counts": {"SINGLE": 0, "SPLIT_BRAIN": 10, "UNKNOWN": 0, "UNOWNED": 0},
        "adjudication_counts": {"PENDING": 0, "ADJUDICATED": 10},
        "owner_decision_blocker_count": 0,
        "observed_convergence_blocker_count": 10,
        "blocker_count": 10,
        "error_count": 0,
    }
    check(code == 0, f"production checker exit {code}")
    for key, value in expected_production.items():
        check(meta[key] == value, f"production {key}={meta[key]!r}, expected {value!r}")
    required_finding_keys = {
        "kind", "object", "severity", "detail", "path", "line", "blocks_ratification",
        "owner_decision_blocker", "observed_convergence_blocker",
    }
    check(all(set(finding) == required_finding_keys for finding in findings),
          "finding additive key contract is not exact")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        registry = _load_registry()
        source_path, source_sha = _write_decision(root)
        adjudicated = []
        for row in registry["authorities"]:
            updated = copy.deepcopy(row)
            updated.update({
                "adjudication_status": "ADJUDICATED",
                "selected_target_authority": "owner-selected-target",
                "transition_owner": "Platform Operations",
                "decision_provenance": {
                    "decision_id": f"foundation-a.{row['id']}",
                    "authority": "OWNER",
                    "decided_by": "Repository Owner Alice",
                    "decision_date": "2026-07-17",
                    "source_path": source_path,
                    "source_sha256": source_sha,
                },
                "rollback_boundary": {
                    "owner": "Platform Operations",
                    "trigger": "any confirmed divergence",
                    "action": "stop transition and retain the legacy authority",
                    "authority_during_rollback": "declared legacy authority",
                },
                "resolution_deadline": "2026-12-31",
            })
            adjudicated.append(updated)
        registry["authorities"] = adjudicated
        full_meta, full_findings, full_code = _run_temp_registry(mod, root, registry)
        check(full_code == 0, f"fully adjudicated fixture exit {full_code}: {full_findings}")
        check(full_meta["adjudication_counts"] == {"PENDING": 0, "ADJUDICATED": 10},
              f"fully adjudicated counts wrong: {full_meta['adjudication_counts']}")
        check(full_meta["owner_decision_blocker_count"] == 0,
              "fully adjudicated fixture retained decision blockers")
        check(full_meta["observed_convergence_blocker_count"] == 10,
              "fully adjudicated fixture lost convergence blockers")
        check(full_meta["blocker_count"] == 10,
              f"fully adjudicated aggregate blockers changed: {full_meta['blocker_count']}")


def test_24_adjudication_never_grants_cycle1_authority() -> None:
    mod = _load_checker()
    meta, _, _ = _semantic_run(mod, "incremental", strict=False, check_date=FIXED_DATE)
    check(meta["cycle1_authority"] == "NOT_AUTHORIZED", "Stage A granted Cycle 1 authority")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        registry = _load_registry()
        registry["authorities"] = [_adjudicated_authority(root)]
        fixture_meta, _, _ = _run_temp_registry(mod, root, registry)
        check(fixture_meta["cycle1_authority"] == "NOT_AUTHORIZED",
              "adjudicated fixture granted Cycle 1 authority")


def test_25_adjudication_does_not_suppress_integrity_blockers() -> None:
    mod = _load_checker()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        authority = _adjudicated_authority(root)
        rogue = root / "rogue.py"
        rogue.write_text('open("registry.jsonl", "a")\n', encoding="utf-8")
        authority["observed_writers"] = []
        authority["writer_signatures"] = [
            {"store_token": "registry.jsonl", "write_tokens": ["open("]}
        ]
        findings, blocked = _adjudication_findings(mod, root, authority)
        mod._condition_findings([authority], findings, blocked)
        original_root = mod.REPO_ROOT
        try:
            mod.REPO_ROOT = root
            mod._scan_undeclared_writers([authority], ["rogue.py"], findings)
        finally:
            mod.REPO_ROOT = original_root
        findings.append(mod._f("scan_truncated", "registry", "degraded", "fixture truncation",
                               blocks_ratification=True))
        check(any(f["kind"] == "undeclared_writer" and f["blocks_ratification"] for f in findings),
              "adjudication suppressed undeclared writer")
        check(any(f["kind"] == "scan_truncated" and f["blocks_ratification"] for f in findings),
              "adjudication suppressed scan truncation")


def test_26_machine_exit_budget_and_stdout_contract_regression() -> None:
    machine = subprocess.run([sys.executable, str(CHECKER), "--machine"],
                             capture_output=True, text=True, cwd=str(REPO))
    check(machine.returncode == 0, f"--machine exit {machine.returncode}: {machine.stderr[:200]}")
    payload = json.loads(machine.stdout)
    check(set(payload) == {"meta", "findings"}, f"top-level keys changed: {set(payload)}")
    check(machine.stderr == "", f"checker emitted stderr on healthy run: {machine.stderr[:200]}")
    meta = payload["meta"]
    check(meta["files_scanned"] <= meta["file_cap"] <= 8000, "file scan bound regressed")
    check(meta["budget"]["duration_seconds"] <= 15.0 and meta["budget"]["ok"],
          f"full budget regressed: {meta['budget']}")
    check(meta["output_bytes"] <= 5 * 1024 * 1024, "output budget regressed")
    strict = subprocess.run([sys.executable, str(CHECKER), "--machine", "--strict"],
                            capture_output=True, text=True, cwd=str(REPO))
    check(strict.returncode == 1, f"strict blockers must exit 1, got {strict.returncode}")
    incremental = subprocess.run([sys.executable, str(CHECKER), "--machine", "--changed"],
                                 capture_output=True, text=True, cwd=str(REPO))
    check(incremental.returncode == 0, f"incremental exit {incremental.returncode}")
    inc_meta = json.loads(incremental.stdout)["meta"]
    check(inc_meta["budget"]["duration_seconds"] <= 10.0, "incremental budget regressed")


def test_27_checker_source_is_read_only_and_has_no_runtime_io() -> None:
    source = CHECKER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_methods = {"write_text", "write_bytes", "mkdir", "unlink", "rename", "replace"}
    observed_forbidden = {
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden_methods
    }
    check(not observed_forbidden, f"checker contains file-write calls: {sorted(observed_forbidden)}")
    forbidden_fragments = (
        "requests.", "urllib.request", "http.client", "socket.socket", "sqlite3",
        "psycopg", "systemctl", "nixos-rebuild", "llama", "openai",
    )
    for fragment in forbidden_fragments:
        check(fragment not in source, f"checker contains forbidden runtime capability {fragment!r}")
    with tempfile.TemporaryDirectory() as td:
        destination = Path(td) / "snapshot.json"
        rejected = subprocess.run(
            [sys.executable, str(CHECKER), "--machine", "--snapshot", str(destination)],
            capture_output=True, text=True, cwd=str(REPO),
        )
        check(rejected.returncode == 2, "unknown snapshot write option must be rejected")
        check(not destination.exists(), "checker created a caller-selected output file")


def main() -> int:
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    check(len(tests) == 27, f"expected frozen 27-case matrix, discovered {len(tests)} tests")
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            _FAILURES.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if _FAILURES:
        print(f"FAIL ({len(_FAILURES)}):")
        for failure in _FAILURES:
            print(f"  - {failure}")
        return 1
    print(f"PASS: {len(tests)} state-authority checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
