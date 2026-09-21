#!/usr/bin/env python3
"""Unit coverage for the declarative project payload manifest foundation."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
import project_payload_manifest as payload  # noqa: E402

MANIFEST = ROOT / "templates/agentic-workflow/project-payload-manifest.json"


def expect_error(document: dict, fragment: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "manifest.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        try:
            payload.load_manifest(path)
        except payload.ManifestError as exc:
            assert fragment in str(exc), exc
        else:
            raise AssertionError(f"expected error containing {fragment!r}")


def expect_resolve_error(document: dict, repository_root: Path, fragment: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "manifest.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        try:
            payload.resolve_inventory(path, repository_root, "greenfield")
        except payload.ManifestError as exc:
            assert fragment in str(exc), exc
        else:
            raise AssertionError(f"expected resolve error containing {fragment!r}")


def expect_valid(document: dict) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "manifest.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        payload.load_manifest(path)


def main() -> None:
    document = payload.load_manifest(MANIFEST)
    inventory = payload.expected_inventory_parity(MANIFEST, ROOT)
    targets = [entry["target"] for entry in inventory]
    assert targets == sorted(targets)
    assert len(targets) == len(set(targets))
    assert {"project-init", "gate-bundle", "project-collaboration", "shared-engine"} <= {entry["functional_owner"] for entry in inventory}
    for fragment in ("commands", "intent-contract", "PROJECT-PRD", "settings", "collaboration", "gate-runner", "capability-manifest", "FACTORY-SKILL-CATALOG", "FACTORY-TOOL-ALLOWLIST", ".vscode/tasks.json", ".factory/pm-tracker/tracker.schema.json", ".factory/pm-tracker/sample-tracker.json"):
        assert any(fragment in target for target in targets), fragment
    capability_records = [entry for entry in inventory if entry["target"] == ".factory/capability-manifest.json"]
    assert len(capability_records) == 1
    assert capability_records[0]["connection"] == {
        "kind": "shared-engine-capability-record",
        "states": ["available", "unavailable", "unauthorized"],
        "interfaces": list(payload.CAPABILITY_INTERFACES),
    }
    source_paths = [entry["source"].get("path") for entry in inventory if "path" in entry["source"]]
    assert all((ROOT / source).exists() for source in source_paths)
    bundle_document = json.loads((ROOT / "templates/factory-gate-bundle/MANIFEST.json").read_text(encoding="utf-8"))
    required_gate_outputs = {
        item["install_target"]
        for item in bundle_document["files"]
        if item["bundle_path"] != "."
    }
    assert required_gate_outputs <= set(targets), required_gate_outputs - set(targets)
    forbidden = ("/run/secrets", "/home/", "PULSE.log", "RESUME.json", "HANDOFF.md", "PENDING.json", "RECOVERY.md")
    assert not any(any(token in str(entry["source"]) for token in forbidden) for entry in inventory)

    duplicate = json.loads(json.dumps(document))
    duplicate["inventory"].append(dict(duplicate["inventory"][0]))
    expect_error(duplicate, "duplicate target")
    absolute = json.loads(json.dumps(document))
    absolute["inventory"][0]["target"] = "/outside"
    expect_error(absolute, "must not be absolute")
    traversal = json.loads(json.dumps(document))
    traversal["inventory"][0]["source"]["path"] = "templates/../secrets/value"
    expect_error(traversal, "must not be absolute or traverse")
    invalid_enum = json.loads(json.dumps(document))
    invalid_enum["inventory"][0]["renderer"] = "copy-host"
    expect_error(invalid_enum, "unknown renderer")
    missing_connection = json.loads(json.dumps(document))
    next(entry for entry in missing_connection["inventory"] if entry["target"] == ".factory/capability-manifest.json").pop("connection")
    expect_error(missing_connection, "requires a typed connection")
    incomplete_connection = json.loads(json.dumps(document))
    next(entry for entry in incomplete_connection["inventory"] if entry["target"] == ".factory/capability-manifest.json")["connection"]["interfaces"].pop()
    expect_error(incomplete_connection, "interfaces must be typed and complete")
    exact_security_check = json.loads(json.dumps(document))
    exact_security_check["inventory"][0]["source"]["path"] = str(payload._SAFE_SECURITY_CHECK_SOURCE)
    expect_valid(exact_security_check)
    for forbidden_source in (
        "config/secrets.json",
        ".agent/history.json",
        ".agent/collaboration/PULSE.log.bak",
        "var/token-cache.json",
        "config/secrets.json/hard-20-secret-scan.sh",
        ".agent/history.json/payload.md",
        ".agent/collaboration/PULSE.log.bak/payload.md",
    ):
        forbidden = json.loads(json.dumps(document))
        forbidden["inventory"][0]["source"]["path"] = forbidden_source
        expect_error(forbidden, "forbidden secret/runtime content" if "secret" in forbidden_source or "token" in forbidden_source else "runtime history")
    missing = json.loads(json.dumps(document))
    missing["inventory"][0]["source"]["path"] = "templates/not-present"
    expect_resolve_error(missing, ROOT, "active source does not exist")
    with tempfile.TemporaryDirectory() as directory:
        sandbox = Path(directory)
        (sandbox / "inside").mkdir()
        (sandbox / "inside" / "source.txt").write_text("ok", encoding="utf-8")
        outside = sandbox.parent / "payload-manifest-outside.txt"
        outside.write_text("outside", encoding="utf-8")
        try:
            (sandbox / "escape").symlink_to(outside)
            escaped = json.loads(json.dumps(document))
            escaped["inventory"][0]["source"]["path"] = "escape"
            expect_resolve_error(escaped, sandbox, "active source escapes repository root")
        finally:
            outside.unlink(missing_ok=True)
    print(f"PASS project payload manifest: {len(inventory)} required targets")


if __name__ == "__main__":
    main()
