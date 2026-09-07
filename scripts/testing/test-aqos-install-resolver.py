#!/usr/bin/env python3
"""Focused tests for the trusted AQ-OS install-plan resolver."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts/ai/lib/aqos_install_resolver.py"
CLI = ROOT / "scripts/ai/aqos-install-resolve"
SCHEMA = json.loads((ROOT / "config/schemas/aqos-install-plan-v1.schema.json").read_text())
MODULE_BYTES = (ROOT / "config/aqos-module-catalog-v1.json").read_bytes()
MODULES = json.loads(MODULE_BYTES)
AI_BYTES = (ROOT / "config/aqos-ai-fit-policy-catalog-v1.json").read_bytes()


def load():
    spec = importlib.util.spec_from_file_location("aqos_install_resolver", LIB)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source() -> dict:
    return {"oid_algorithm": "sha1", "git_commit": "a" * 40, "git_tree": "b" * 40,
            "clean_worktree": True, "flake_lock_sha256": "c" * 64,
            "nix_system": "x86_64-linux", "flake_installable": "path:/repo#nixosConfigurations.host",
            "host_target": "host"}


def hw() -> dict:
    return {"schema_version": 2, "cpu": {"architecture": "x86_64", "model": "test", "cores": 8, "threads": 16},
            "ram": {"total_bytes": 32 * 1024**3},
            "gpu": {"outcome": "detected", "devices": [{"bdf": "0000:01:00.0", "pci_class": "0x030000",
                                                            "vendor_id": "0x10de", "device_id": "0x2482"}]}}


def request() -> dict:
    return {"artifact_type": "request_plan", "schema_version": "aqos-install-plan/v1",
            "selection": {"golden_profile": "profile.ai-dev", "roles": ["role.gaming"],
                          "include_local_ai": True}, "host_target": "host"}


def test_jcs_utf16_order_and_guards() -> None:
    r = load()
    assert r.parse_json_strict('{"params_b":0.6}') == {"params_b": 0.6}
    assert r.jcs_bytes({"\ue000": 1, "\U00010000": 2}) == '{"𐀀":2,"":1}'.encode()
    assert r.jcs_bytes({"b": 1, "a": True}) == b'{"a":true,"b":1}'
    for bad in ({"n": 1.5}, {"n": 2**60}):
        try:
            r.jcs_bytes(bad)
            raise AssertionError("unsafe number accepted")
        except r.ResolverError:
            pass
    try:
        r.jcs_bytes({"\ud800": 1})
        raise AssertionError("lone-surrogate key accepted")
    except r.ResolverError as exc:
        assert exc.reason == "unicode_invalid"


def test_cli_surface() -> None:
    result = subprocess.run([sys.executable, str(CLI), "--help"], cwd=ROOT, check=True,
                            capture_output=True, text=True)
    assert "--flake-installable" in result.stdout
    assert "--adapter" in result.stdout


def test_cross_adapter_byte_parity_and_projection() -> None:
    r = load()
    base = request()
    sources = [
        r.normalize_adapter("manual", base),
        r.normalize_adapter("guided", {"answers": base["selection"], "host_target": "host"}),
        r.normalize_adapter("ai", {"proposal": base["selection"], "host_target": "host"}),
        r.normalize_adapter("legacy", {"profile": "ai-dev", "roles": ["role.gaming"],
                                        "include_local_ai": True, "host": "host"}),
    ]
    locks = [r.resolve_plan(item, hw(), MODULES, MODULE_BYTES, AI_BYTES, SCHEMA, source()) for item in sources]
    wires = [r.jcs_bytes(item) for item in locks]
    assert len(set(wires)) == 1
    assert locks[0]["selection"]["roles"] == ["role.ai-stack", "role.desktop", "role.gaming"]
    projection = r.compile_projection(locks[0], MODULES)
    assert projection["executor"]["executable"] is False
    assert projection["executor"]["blocked_reason"] == "fieldset-and-execution-verifier-not-active"
    assert projection["executor"]["argv"][:5] == ["/repo/nixos-quick-deploy.sh", "--host", "host", "--profile", "ai-dev"]
    assert projection["executor"]["argv"][-4:] == [
        "--skip-model-selection", "--skip-ai-secrets-bootstrap", "--skip-home-switch", "--build-only"]
    assert projection["executor"]["env"] == {}
    assert projection["nix"]["nixos_target"] == "host"
    assert projection["nix"]["mySystem"]["roles.desktop.enable"] is True


def test_provenance_does_not_change_semantic_lock() -> None:
    r = load()
    base = request()
    with_extra = dict(base)
    with_extra["provenance"] = {"ui": "guided"}
    try:
        r.resolve_plan(with_extra, hw(), MODULES, MODULE_BYTES, AI_BYTES, SCHEMA, source())
        raise AssertionError("semantic provenance accepted")
    except r.ResolverError as exc:
        assert exc.reason == "schema_invalid"


def test_default_golden_profile_is_locked_but_not_executable_before_p1() -> None:
    r = load()
    req = {"artifact_type": "request_plan", "schema_version": "aqos-install-plan/v1", "host_target": "host"}
    lock = r.resolve_plan(req, hw(), MODULES, MODULE_BYTES, AI_BYTES, SCHEMA, source())
    assert lock["selection"]["golden_profile"] == "aqos-workstation"
    projection = r.compile_projection(lock, MODULES)
    assert projection["executor"]["entrypoint"] == "/repo/nixos-quick-deploy.sh"
    assert projection["executor"]["executable"] is False
    assert projection["executor"]["blocked_reason"] == "profile-not-active-until-p1"
    assert projection["executor"]["argv"][-1] == "--build-only"


def test_unknown_role_and_not_advised_ai_fail_closed() -> None:
    r = load()
    bad = request()
    bad["selection"] = dict(bad["selection"], roles=["role.missing"])
    no_ram = hw()
    no_ram["ram"] = {"total_bytes": None}
    for req, evidence, reason in (
        (bad, hw(), "role_unknown"),
        (request(), no_ram, "local_ai_not_advised"),
    ):
        try:
            r.resolve_plan(req, evidence, MODULES, MODULE_BYTES, AI_BYTES, SCHEMA, source())
            raise AssertionError("unsafe request accepted")
        except r.ResolverError as exc:
            assert exc.reason == reason


def test_fit_binding_rejects_unknown_or_stale_evidence() -> None:
    r = load()
    digest = r.sha256_bytes(AI_BYTES)
    evidence_digest = r.sha256_bytes(r.jcs_bytes(r._ai_evidence_material(hw())))
    valid = {"verdict": "limited", "ai_fit_policy_catalog_sha256": digest,
             "hardware_evidence_sha256": evidence_digest}
    r._validate_fit_result(valid, hw(), digest)
    for changed, reason in (
        (dict(valid, verdict="arbitrary"), "ai_fit_verdict_invalid"),
        (dict(valid, hardware_evidence_sha256="0" * 64), "ai_fit_hardware_mismatch"),
    ):
        try:
            r._validate_fit_result(changed, hw(), digest)
            raise AssertionError("forged fit accepted")
        except r.ResolverError as exc:
            assert exc.reason == reason


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_source_identity_dirty_target_and_drift_fail_closed() -> None:
    r = load()
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "test@example.invalid")
        _git(repo, "config", "user.name", "Test")
        (repo / "flake.lock").write_text("{}\n")
        (repo / "flake.nix").write_text("{}\n")
        _git(repo, "add", "flake.lock", "flake.nix")
        _git(repo, "commit", "-qm", "fixture")
        installable = f"path:{repo}#nixosConfigurations.host"
        system = lambda: "x86_64-linux"
        identity = r.collect_source_identity(repo, "host", "x86_64-linux", installable, lambda _: True, system)
        r.verify_source_identity(identity, repo, lambda _: True, system)
        try:
            r.collect_source_identity(repo, "host", "x86_64-linux", installable, lambda _: False, system)
            raise AssertionError("missing target accepted")
        except r.ResolverError as exc:
            assert exc.reason == "flake_target_unavailable"
        (repo / "flake.lock").write_text('{"changed":true}\n')
        try:
            r.verify_source_identity(identity, repo, lambda _: True, system)
            raise AssertionError("dirty/drifted source accepted")
        except r.ResolverError as exc:
            assert exc.reason == "source_dirty"
        _git(repo, "add", "flake.lock")
        _git(repo, "commit", "-qm", "drift")
        try:
            r.verify_source_identity(identity, repo, lambda _: True, system)
            raise AssertionError("committed source drift accepted")
        except r.ResolverError as exc:
            assert exc.reason == "source_identity_mismatch"
        try:
            r.collect_source_identity(repo, "host", "aarch64-linux", installable, lambda _: True, system)
            raise AssertionError("Nix system mismatch accepted")
        except r.ResolverError as exc:
            assert exc.reason == "nix_system_mismatch"


def main() -> int:
    test_jcs_utf16_order_and_guards()
    test_cli_surface()
    test_cross_adapter_byte_parity_and_projection()
    test_provenance_does_not_change_semantic_lock()
    test_default_golden_profile_is_locked_but_not_executable_before_p1()
    test_unknown_role_and_not_advised_ai_fail_closed()
    test_fit_binding_rejects_unknown_or_stale_evidence()
    test_source_identity_dirty_target_and_drift_fail_closed()
    print("test-aqos-install-resolver: ok 8/8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
