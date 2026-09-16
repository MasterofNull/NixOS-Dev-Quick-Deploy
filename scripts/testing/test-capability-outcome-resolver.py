#!/usr/bin/env python3
"""Focused, side-effect-free contract tests for aq-capability-gap --query."""

import importlib.util
import json
import subprocess
import sys
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/ai/aq-capability-gap"
LOADER = SourceFileLoader("capability_gap", str(SOURCE))
SPEC = importlib.util.spec_from_loader("capability_gap", LOADER)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(MODULE)
HELPER = MODULE._capability_outcomes_helper()


def outcome(outcome_id: str, aliases: list[str], status: str = "equivalent", **overrides: object) -> dict:
    value = {
        "id": outcome_id,
        "aliases": aliases,
        "kind": "skill",
        "domains": ["x"],
        "evidence_paths": [],
        "authority": "native",
        "status": status,
        "qa": "q",
        "visibility": "v",
    }
    value.update(overrides)
    return value


def query(catalog: Path, value: str, domain: str = "") -> tuple[int, dict]:
    command = [str(SOURCE), "--query", value, "--catalog", str(catalog), "--format", "json"]
    if domain:
        command.extend(["--domain", domain])
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout)


if len(sys.argv) > 1:
    if sys.argv[1:] != ["--smoke"]:
        raise SystemExit("usage: test-capability-outcome-resolver.py [--smoke]")
    exit_code, result = query(ROOT / "config/capability-gap-catalog.json", "tier0")
    assert exit_code == 0 and result["verdict"] == "equivalent" and result["candidates"]
    exit_code, result = query(ROOT / "config/capability-gap-catalog.json", "install external")
    assert exit_code == 0 and result["verdict"] == "denied" and result["candidates"]
    print("PASS: capability outcome resolver integration smoke")
    raise SystemExit(0)


with tempfile.TemporaryDirectory() as temp_dir:
    temp = Path(temp_dir)
    catalog_path = temp / "catalog.json"
    catalog = {
        "version": "test",
        "capabilities": [],
        "outcomes": [
            outcome("canonical", ["alias"], evidence_paths=["scripts/ai/aq-capability-gap"]),
            outcome("other", ["alias"], "partial", kind="role"),
            outcome("partial-only", ["partial"], "partial"),
            outcome("blocked", ["alias"], "denied", authority="denied"),
            outcome("stale", ["stale"], evidence_paths=["no/such/path"]),
        ]
    }
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    assert MODULE.resolve_outcomes(catalog, "canonical", "")["verdict"] == "equivalent"
    assert MODULE.resolve_outcomes(catalog, "canonical", "wrong")["verdict"] == "missing"
    assert MODULE.resolve_outcomes(catalog, "partial", "x")["verdict"] == "partial"
    assert MODULE.resolve_outcomes(catalog, "alias", "")["verdict"] == "denied"
    assert MODULE.resolve_outcomes(catalog, "blocked", "")["verdict"] == "denied"
    assert MODULE.resolve_outcomes(catalog, "stale", "")["verdict"] == "unverified"
    assert MODULE.resolve_outcomes(catalog, "none", "")["verdict"] == "missing"
    assert MODULE.resolve_outcomes(catalog, "canonical", "") == MODULE.resolve_outcomes(catalog, "canonical", "")
    exit_code, result = query(catalog_path, "partial", "x")
    assert exit_code == 0 and result["verdict"] == "partial"

    before = catalog_path.read_bytes()
    MODULE.resolve_outcomes(catalog, "canonical", "")
    assert catalog_path.read_bytes() == before

    original_root = MODULE.REPO_ROOT
    isolated_root = temp / "repo"
    outside = temp / "outside"
    isolated_root.mkdir()
    outside.mkdir()
    (outside / "sentinel").write_text("unchanged", encoding="utf-8")
    (isolated_root / "escape").symlink_to(outside, target_is_directory=True)
    MODULE.REPO_ROOT = isolated_root
    _, symlink_issues = MODULE.evidence_state(["escape/sentinel"])
    MODULE.REPO_ROOT = original_root
    assert symlink_issues[0]["reason"] == "evidence_path_escapes_repository"
    assert (outside / "sentinel").read_text(encoding="utf-8") == "unchanged"

    duplicate = {
        "version": "test",
        "capabilities": [],
        "outcomes": [outcome("same", ["one"]), outcome("same", ["two"])],
    }
    try:
        MODULE.resolve_outcomes(duplicate, "same", "")
    except ValueError as error:
        assert "duplicate" in str(error)
    else:
        raise AssertionError("duplicate outcome ids must fail closed")

    malformed = [
        [],
        {"outcomes": "not-a-list"},
        {"version": "test", "capabilities": [], "outcomes": ["not-an-object"]},
    ]
    for index, payload in enumerate(malformed):
        bad_catalog = temp / f"malformed-{index}.json"
        bad_catalog.write_text(json.dumps(payload), encoding="utf-8")
        exit_code, result = query(bad_catalog, "canonical")
        assert exit_code == 2
        assert result["verdict"] == "unverified" and result["state"] == "ERROR"

    oversized = temp / "oversized.json"
    oversized.write_bytes(b" " * (MODULE.MAX_OUTCOME_CATALOG_BYTES + 1))
    exit_code, result = query(oversized, "canonical")
    assert exit_code == 2 and result["reason"] == "catalog_byte_limit"

    too_many = temp / "too-many.json"
    too_many.write_text(
        json.dumps({"version": "test", "capabilities": [], "outcomes": [outcome(f"item-{index}", [f"a-{index}"]) for index in range(257)]}),
        encoding="utf-8",
    )
    try:
        HELPER.load_outcome_catalog(too_many)
    except ValueError as error:
        assert str(error) == "catalog_schema_invalid"
    else:
        raise AssertionError("257 outcomes must fail schema validation")

    for value, domain in (("x" * 129, ""), ("canonical", "x" * 129)):
        try:
            MODULE.resolve_outcomes(catalog, value, domain)
        except ValueError as error:
            assert "128 characters" in str(error)
        else:
            raise AssertionError("overlong query or domain must fail")

    invalid_outcomes = [
        outcome("bad-status", ["bad-status"], status="ready"),
        outcome("bad-authority", ["bad-authority"], authority="ready"),
        outcome("bad-aliases", []),
        outcome("bad-domains", ["bad-domains"], domains=[]),
        outcome("unsafe-path", ["unsafe-path"], evidence_paths=["../outside"]),
        outcome("unknown-field", ["unknown-field"], extra="not-declared"),
    ]
    for index, invalid in enumerate(invalid_outcomes):
        try:
            HELPER.validate_outcome_catalog({"version": "test", "capabilities": [], "outcomes": [invalid]})
        except ValueError as error:
            assert str(error) == "catalog_schema_invalid"
        else:
            raise AssertionError(f"invalid schema entry {index} was accepted")

    deeply_nested = temp / "deeply-nested.json"
    deeply_nested.write_text("[" * 1500 + "]" * 1500, encoding="utf-8")
    exit_code, result = query(deeply_nested, "canonical")
    assert exit_code == 2
    assert result["state"] == "ERROR"
    assert result["reason"] in {"catalog_invalid_json", "catalog_schema_invalid"}

print("PASS: capability outcome resolver")
