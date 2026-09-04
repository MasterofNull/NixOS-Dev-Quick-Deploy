#!/usr/bin/env python3
"""Validator for the AQ-OS installer module catalog.

The catalog (config/aqos-module-catalog-v1.json) is data; this module enforces the
invariants the tracker requires for p0-module-catalog:

- Completeness vs the ACTUAL import wiring (nix/modules/hardware/default.nix +
  nix/modules/roles/default.nix + nix/modules/profiles/*.nix). An imported module
  with no catalog entry, or a catalog entry pointing at a module that is not
  imported / not on disk, fails closed.
- Deterministic ordering (category, then id).
- Dependency/conflict closure: every referenced id exists in the catalog.
- Projection resolution: every mySystem.* field the catalog projects (support
  predicate option, alt_options, configured_by, projected_mysystem_fields) is
  actually referenced in the Nix tree, so the installer can never project a dead
  option.

The exact catalog file bytes are hashed (sha256); that digest binds into the
resolved install-plan lock as catalog_digests.module_catalog_sha256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

CATALOG_PATH = Path("config/aqos-module-catalog-v1.json")
_IMPORT_RE = re.compile(r"\./[A-Za-z0-9._/-]+\.nix")


def load_catalog(path: Path | str = CATALOG_PATH) -> tuple[dict[str, Any], str]:
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _parse_imports(default_nix: Path, prefix: str) -> set[str]:
    """Extract repo-relative module paths from a Nix `imports = [ ./... ];` list."""
    if not default_nix.exists():
        return set()
    text = default_nix.read_text()
    return {prefix + rel[2:] for rel in _IMPORT_RE.findall(text)}


def enumerate_imports(repo_root: Path | str = Path(".")) -> set[str]:
    """The set of installer-selectable module paths actually wired into the system."""
    repo = Path(repo_root)
    paths: set[str] = set()
    paths |= _parse_imports(repo / "nix/modules/hardware/default.nix", "nix/modules/hardware/")
    paths |= _parse_imports(repo / "nix/modules/roles/default.nix", "nix/modules/roles/")
    profiles_dir = repo / "nix/modules/profiles"
    if profiles_dir.is_dir():
        for p in profiles_dir.glob("*.nix"):
            paths.add(f"nix/modules/profiles/{p.name}")
    return paths


def _mysystem_reference_blob(repo_root: Path) -> str:
    """Concatenated text of the Nix module tree, for projection-resolution checks."""
    root = Path(repo_root) / "nix" / "modules"
    parts: list[str] = []
    for f in sorted(root.rglob("*.nix")):
        try:
            parts.append(f.read_text(errors="replace"))
        except Exception:
            continue
    return "\n".join(parts)


def _field_resolves(field: str, blob: str) -> bool:
    """A field resolves if it (or a specific parent) is consumed in the Nix tree.

    Direct consumption (cfg.a.b.c) is the primary signal. Some options are read
    through an intermediate binding (e.g. `kdev = cfg.roles.kernelDev; kdev.enable`),
    so a parent path is accepted too -- but only when the parent still has >= 2
    segments, so a generic top-level parent like `cfg.hardware` can never rubber-
    stamp a mislabeled leaf (that drift must fail closed)."""
    def consumed(f: str) -> bool:
        return any(token in blob for token in (
            f"cfg.{f}", f"config.mySystem.{f}", f"mySystem.{f}"))
    if consumed(field):
        return True
    parts = field.split(".")
    if len(parts) >= 3:
        return consumed(".".join(parts[:-1]))
    return False


def validate(catalog: dict[str, Any], repo_root: Path | str = Path(".")) -> list[str]:
    """Return a list of issue strings; empty means the catalog is valid."""
    repo = Path(repo_root)
    issues: list[str] = []
    modules = catalog.get("modules", [])

    ids = [m["id"] for m in modules]
    id_set = set(ids)
    if len(ids) != len(id_set):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        issues.append(f"duplicate catalog ids: {dupes}")

    # Deterministic ordering: (category, id).
    ordered = sorted(modules, key=lambda m: (m["category"], m["id"]))
    if [m["id"] for m in modules] != [m["id"] for m in ordered]:
        issues.append("modules are not in deterministic (category, id) order")

    # Completeness vs actual imports (profiles + roles + hardware only; other
    # categories are not import-wired and are checked for on-disk existence).
    import_backed = {"profile", "role", "hardware-cpu", "hardware-gpu", "platform"}
    imported = enumerate_imports(repo)
    cataloged_paths = {m["module_path"] for m in modules if m["category"] in import_backed}
    missing = imported - cataloged_paths
    for p in sorted(missing):
        issues.append(f"imported module has no catalog entry (drift): {p}")
    phantom = cataloged_paths - imported
    for p in sorted(phantom):
        issues.append(f"catalog entry is not imported anywhere (phantom): {p}")

    # On-disk existence of every module_path.
    for m in modules:
        if not (repo / m["module_path"]).exists():
            issues.append(f"module_path does not exist on disk: {m['id']} -> {m['module_path']}")

    # Dependency / conflict closure.
    for m in modules:
        for rel in ("deps", "conflicts"):
            for ref in m.get(rel, []):
                if ref not in id_set:
                    issues.append(f"{m['id']} {rel} references unknown id: {ref}")

    # Multi-GPU: hardware-gpu entries must not exclude each other (iGPU + dGPU coexist).
    gpu_ids = {m["id"] for m in modules if m["category"] == "hardware-gpu"}
    for m in modules:
        if m["category"] == "hardware-gpu":
            bad = gpu_ids & set(m.get("conflicts", []))
            if bad:
                issues.append(f"{m['id']} falsely conflicts with other GPU vendors: {sorted(bad)}")

    # Projection resolution: every projected mySystem field is referenced in the tree.
    blob = _mysystem_reference_blob(repo)
    for m in modules:
        fields: set[str] = set(m.get("projected_mysystem_fields", []))
        pred = m.get("support_predicate", {})
        if pred.get("option"):
            fields.add(pred["option"])
        fields |= set(pred.get("alt_options", []))
        fields |= set(pred.get("configured_by", []))
        for field in sorted(fields):
            if not _field_resolves(field, blob):
                issues.append(f"{m['id']} projects unresolved mySystem field: {field}")

    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the AQ-OS installer module catalog.")
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--digest", action="store_true", help="print the catalog sha256 and exit")
    args = parser.parse_args(argv)

    catalog, digest = load_catalog(args.catalog)
    if args.digest:
        print(digest)
        return 0

    issues = validate(catalog, args.repo_root)
    if issues:
        print(f"FAIL: {len(issues)} module-catalog issue(s):")
        for i in issues:
            print(f"  - {i}")
        return 1
    print(f"PASS: module catalog valid ({len(catalog['modules'])} modules) sha256={digest[:12]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
