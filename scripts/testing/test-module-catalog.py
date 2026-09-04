#!/usr/bin/env python3
"""Tests for the AQ-OS installer module catalog + validator.

Covers p0-module-catalog: completeness vs actual imports (drift fails closed),
deterministic ordering, dependency closure, projection resolution (including that
a mislabeled parent cannot rubber-stamp a leaf), multi-GPU non-exclusivity, and
digest stability.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MC_PATH = REPO_ROOT / "scripts" / "ai" / "lib" / "module_catalog.py"
CATALOG_PATH = REPO_ROOT / "config" / "aqos-module-catalog-v1.json"
SCHEMA_PATH = REPO_ROOT / "config" / "schemas" / "aqos-module-catalog-v1.schema.json"


def load_mc():
    spec = importlib.util.spec_from_file_location("module_catalog", MC_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _has(issues, needle):
    return any(needle in i for i in issues)


def test_schema_and_digest() -> str:
    catalog = json.loads(CATALOG_PATH.read_text())
    schema = json.loads(SCHEMA_PATH.read_text())
    assert schema["properties"]["catalog_version"]["const"] == catalog["catalog_version"]
    for m in catalog["modules"]:
        for k in ("id", "category", "module_path", "support_predicate", "resource_cost",
                  "deps", "conflicts", "projected_mysystem_fields", "source"):
            assert k in m, (m.get("id"), k)
    try:
        import jsonschema  # type: ignore
        jsonschema.validate(catalog, schema)
    except ImportError:
        pass
    mc = load_mc()
    _, d1 = mc.load_catalog(CATALOG_PATH)
    assert d1 == hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest()
    return d1


def test_real_tree_is_valid() -> None:
    mc = load_mc()
    catalog, _ = mc.load_catalog(CATALOG_PATH)
    issues = mc.validate(catalog, REPO_ROOT)
    assert issues == [], issues


def test_completeness_covers_all_imports() -> None:
    mc = load_mc()
    catalog, _ = mc.load_catalog(CATALOG_PATH)
    imported = mc.enumerate_imports(REPO_ROOT)
    cataloged = {m["module_path"] for m in catalog["modules"]}
    assert imported and imported <= cataloged, sorted(imported - cataloged)


def test_missing_entry_fails_closed() -> None:
    mc = load_mc()
    catalog, _ = mc.load_catalog(CATALOG_PATH)
    broken = copy.deepcopy(catalog)
    broken["modules"] = [m for m in broken["modules"] if m["id"] != "hw.gpu.nvidia"]
    issues = mc.validate(broken, REPO_ROOT)
    assert _has(issues, "no catalog entry"), issues


def test_phantom_entry_fails_closed() -> None:
    mc = load_mc()
    catalog, _ = mc.load_catalog(CATALOG_PATH)
    broken = copy.deepcopy(catalog)
    ghost = copy.deepcopy(broken["modules"][0])
    ghost["id"] = "hw.gpu.ghost"
    ghost["category"] = "hardware-gpu"
    ghost["module_path"] = "nix/modules/hardware/gpu/ghost.nix"
    broken["modules"].append(ghost)
    issues = mc.validate(broken, REPO_ROOT)
    assert _has(issues, "phantom") or _has(issues, "does not exist on disk"), issues


def test_projection_drift_fails_closed() -> None:
    mc = load_mc()
    catalog, _ = mc.load_catalog(CATALOG_PATH)
    broken = copy.deepcopy(catalog)
    for m in broken["modules"]:
        if m["id"] == "hw.gpu.amd":
            m["projected_mysystem_fields"] = ["hardware.doesNotExist"]
    issues = mc.validate(broken, REPO_ROOT)
    assert _has(issues, "unresolved mySystem field"), issues


def test_mislabeled_parent_still_fails() -> None:
    # rootFsckMode really lives under mySystem.deployment; labeling it under
    # hardware must NOT be rubber-stamped by the generic `cfg.hardware` parent.
    mc = load_mc()
    catalog, _ = mc.load_catalog(CATALOG_PATH)
    broken = copy.deepcopy(catalog)
    for m in broken["modules"]:
        if m["id"] == "hw.platform.recovery":
            m["projected_mysystem_fields"] = ["hardware.rootFsckMode"]
    issues = mc.validate(broken, REPO_ROOT)
    assert _has(issues, "hardware.rootFsckMode"), issues


def test_dep_closure_fails_closed() -> None:
    mc = load_mc()
    catalog, _ = mc.load_catalog(CATALOG_PATH)
    broken = copy.deepcopy(catalog)
    broken["modules"][0]["deps"] = ["role.nonexistent"]
    issues = mc.validate(broken, REPO_ROOT)
    assert _has(issues, "references unknown id"), issues


def test_multi_gpu_not_exclusive() -> None:
    mc = load_mc()
    catalog, _ = mc.load_catalog(CATALOG_PATH)
    # Real tree: no GPU vendor conflicts with another (iGPU + dGPU coexist).
    assert mc.validate(catalog, REPO_ROOT) == []
    # A false GPU-vs-GPU conflict must fail closed.
    broken = copy.deepcopy(catalog)
    for m in broken["modules"]:
        if m["id"] == "hw.gpu.amd":
            m["conflicts"] = ["hw.gpu.intel"]
    issues = mc.validate(broken, REPO_ROOT)
    assert _has(issues, "falsely conflicts"), issues


def test_deterministic_order_enforced() -> None:
    mc = load_mc()
    catalog, _ = mc.load_catalog(CATALOG_PATH)
    broken = copy.deepcopy(catalog)
    broken["modules"] = list(reversed(broken["modules"]))
    issues = mc.validate(broken, REPO_ROOT)
    assert _has(issues, "deterministic"), issues


def test_cli_digest_matches() -> None:
    out = subprocess.run(
        [sys.executable, str(MC_PATH), "--digest", "--catalog", str(CATALOG_PATH)],
        cwd=REPO_ROOT, check=True, capture_output=True, text=True,
    )
    assert out.stdout.strip() == hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest()


def main() -> int:
    digest = test_schema_and_digest()
    test_real_tree_is_valid()
    test_completeness_covers_all_imports()
    test_missing_entry_fails_closed()
    test_phantom_entry_fails_closed()
    test_projection_drift_fails_closed()
    test_mislabeled_parent_still_fails()
    test_dep_closure_fails_closed()
    test_multi_gpu_not_exclusive()
    test_deterministic_order_enforced()
    test_cli_digest_matches()
    print(f"test-module-catalog: ok catalog_sha256={digest[:12]}… 11/11")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
