#!/usr/bin/env python3
"""Contract tests for the AQ-OS installer-owned mySystem field set."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIELDSET_PATH = ROOT / "config/aqos-mysystem-fieldset-v1.json"
CATALOG_PATH = ROOT / "config/aqos-module-catalog-v1.json"


def catalog_sources(catalog: dict) -> dict[str, set[str]]:
    sources: dict[str, set[str]] = {}
    for module in catalog["modules"]:
        for path in module.get("projected_mysystem_fields", []):
            sources.setdefault(path, set()).add(module["id"])
    return sources


def scoped_block(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    finish = text.index(end, begin + len(start))
    return text[begin:finish]


def declaration_in_scope(text: str, start: str, end: str, declaration: str) -> bool:
    try:
        return declaration in scoped_block(text, start, end)
    except ValueError:
        return False


def declared_paths(root: Path) -> set[str]:
    core = (root / "nix/modules/core/options.nix").read_text()
    hardware = scoped_block(core, "    hardware = {", "    kernel = {")
    deployment = scoped_block(core, "    deployment = {", "    disk = {")
    roles = scoped_block(core, "    roles = {", "    aiStack = {")
    declared = set()
    for leaf in ("cpuVendor", "gpuVendor", "igpuVendor", "systemRamGb", "storageType", "isMobile"):
        if f"      {leaf} = lib.mkOption" in hardware:
            declared.add(f"hardware.{leaf}")
    if "    profile = lib.mkOption" in core[:core.index("    hardware = {")]:
        declared.add("profile")
    if "      rootFsckMode = lib.mkOption" in deployment:
        declared.add("deployment.rootFsckMode")
    for dotted in ("aiStack.enable", "gaming.enable", "mobile.enable", "server.enable",
                   "desktop.enable", "virtualization.enable"):
        if f"      {dotted} = lib.mkOption" in roles:
            declared.add(f"roles.{dotted}")
    for role, file_name in (("cppDev", "cpp-dev.nix"), ("kernelDev", "kernel-dev.nix")):
        text = (root / "nix/modules/roles" / file_name).read_text()
        anchor = f"options.mySystem.roles.{role} = {{"
        if anchor in text and "    enable = lib.mkOption" in text[text.index(anchor):]:
            declared.add(f"roles.{role}.enable")
    return declared


def main() -> int:
    fieldset = json.loads(FIELDSET_PATH.read_text())
    catalog = json.loads(CATALOG_PATH.read_text())
    assert set(fieldset) == {"contract_version", "activation", "default_rule", "fields"}
    assert fieldset["contract_version"] == "aqos-mysystem-fieldset/v1"
    assert fieldset["activation"] == "p0-inert"
    fields = fieldset["fields"]
    paths = [entry["path"] for entry in fields]
    assert paths == sorted(paths) and len(paths) == len(set(paths))
    for entry in fields:
        assert set(entry) == {"path", "authority", "value_kind", "source_catalog_ids", "reason"}
        assert entry["authority"] in {"user-intent", "detector", "expert-only"}
        assert entry["value_kind"] in {"enum", "bool", "int"}
        assert entry["source_catalog_ids"] and entry["reason"]

    catalog_fields = sorted({path for module in catalog["modules"]
                             for path in module.get("projected_mysystem_fields", [])})
    assert paths == catalog_fields, (paths, catalog_fields)
    expected_sources = catalog_sources(catalog)
    for entry in fields:
        assert set(entry["source_catalog_ids"]) == expected_sources[entry["path"]], entry["path"]
    # Negative oracle: removing or substituting a valid-but-unrelated module ID
    # must not satisfy exact provenance.
    assert set(fields[0]["source_catalog_ids"][:-1]) != expected_sources[fields[0]["path"]]
    assert {"profile.ai-dev"} != expected_sources["hardware.cpuVendor"]

    by_path = {entry["path"]: entry for entry in fields}
    assert by_path["roles.mobile.enable"]["authority"] == "expert-only"
    assert by_path["deployment.rootFsckMode"]["authority"] == "expert-only"
    assert by_path["hardware.isMobile"]["authority"] == "detector"
    assert by_path["hardware.systemRamGb"]["source_catalog_ids"] == [
        "hw.platform.ram-tuning", "hw.platform.zram"]
    forbidden_prefixes = ("aiStack.", "disk.", "secrets.", "secureboot.",
                          "sshAuthorizedKeys", "primaryUser")
    assert not any(path.startswith(forbidden_prefixes) for path in paths)

    # Verify exact declaration scopes, not generic leaf-name occurrence.
    assert declared_paths(ROOT) == set(paths)
    wrong_scope = ("    hardware = {\n    kernel = {\n    roles = {\n"
                   "      cpuVendor = lib.mkOption { };\n    aiStack = {")
    assert not declaration_in_scope(
        wrong_scope, "    hardware = {", "    kernel = {", "      cpuVendor = lib.mkOption")

    # Resolver projection keys must remain a subset and activation must stay
    # visibly fail-closed until the execution verifier slice exists.
    resolver = (ROOT / "scripts/ai/lib/aqos_install_resolver.py").read_text()
    assert 'executable = False' in resolver
    assert 'fieldset-and-execution-verifier-not-active' in resolver
    print(f"test-aqos-mysystem-fieldset: ok fields={len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
