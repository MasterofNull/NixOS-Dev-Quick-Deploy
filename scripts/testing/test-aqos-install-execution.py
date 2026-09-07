#!/usr/bin/env python3
"""Adversarial tests for inert AQ-OS execution-authorization verification."""

from __future__ import annotations

import copy
import hashlib
import hmac
import importlib.util
import json
import os
import runpy
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = ROOT / "scripts/ai/lib"
sys.path.insert(0, str(LIB_DIR))

import aqos_install_execution as execution  # noqa: E402
import aqos_install_resolver as resolver  # noqa: E402

SCHEMA = json.loads((ROOT / "config/schemas/aqos-install-plan-v1.schema.json").read_text())
MODULE_BYTES = (ROOT / "config/aqos-module-catalog-v1.json").read_bytes()
MODULES = resolver.parse_json_strict(MODULE_BYTES)
AI_BYTES = (ROOT / "config/aqos-ai-fit-policy-catalog-v1.json").read_bytes()
FIELDSET_BYTES = (ROOT / "config/aqos-mysystem-fieldset-v1.json").read_bytes()
KEY = b"k" * 32
NOW = datetime(2026, 9, 7, 12, 5, tzinfo=timezone.utc)


def source() -> dict:
    return {"oid_algorithm": "sha1", "git_commit": "a" * 40, "git_tree": "b" * 40,
            "clean_worktree": True, "flake_lock_sha256": "c" * 64,
            "nix_system": "x86_64-linux", "flake_installable": "path:/repo#nixosConfigurations.host",
            "host_target": "host"}


def hardware() -> dict:
    return {"schema_version": 2,
            "cpu": {"architecture": "x86_64", "model": "test", "cores": 8, "threads": 16},
            "ram": {"total_bytes": 32 * 1024**3},
            "gpu": {"outcome": "detected", "devices": [], "present": False}}


def artifacts() -> tuple[dict, dict, dict]:
    request = {"artifact_type": "request_plan", "schema_version": "aqos-install-plan/v1",
               "selection": {"golden_profile": "profile.gaming", "roles": ["role.gaming"],
                             "include_local_ai": False}, "host_target": "host"}
    lock = resolver.resolve_plan(
        request, hardware(), MODULES, MODULE_BYTES, AI_BYTES, FIELDSET_BYTES, SCHEMA, source())
    projection = resolver.compile_projection(lock, MODULES, FIELDSET_BYTES)
    receipt = {
        "artifact_type": "execution_authorization_receipt",
        "schema_version": "aqos-install-plan/v1",
        "resolved_plan_sha256": resolver.sha256_bytes(resolver.jcs_bytes(lock)),
        "source_identity_sha256": resolver.sha256_bytes(resolver.jcs_bytes(lock["source_identity"])),
        "projection_sha256": resolver.sha256_bytes(resolver.jcs_bytes(projection)),
        "hardware_identity_sha256": lock["hardware_summary"]["hardware_identity_sha256"],
        "authorized_action": "build-only",
        "issued_at": "2026-09-07T12:00:00Z",
        "expires_at": "2026-09-07T12:10:00Z",
        "nonce": "1" * 32,
        "signing_key_id": "local.operator.v1",
        "mac_algorithm": "hmac-sha256",
    }
    receipt["mac_hmac_sha256"] = hmac.new(KEY, resolver.jcs_bytes(receipt), hashlib.sha256).hexdigest()
    assert receipt["mac_hmac_sha256"] == "3bd24febaa0e0fe77114c48aea0f10214e25913bcd68991442e240dc5986e589"
    return lock, projection, receipt


def verify(lock: dict, projection: dict, receipt: dict, *, hw: dict | None = None,
           module_bytes: bytes = MODULE_BYTES, fieldset_bytes: bytes = FIELDSET_BYTES,
           now: datetime = NOW, key_provider=None, source_verifier=None) -> dict:
    return execution.verify_execution_evidence(
        lock, projection, receipt, hw or hardware(), SCHEMA, module_bytes, AI_BYTES, fieldset_bytes,
        "/repo", key_provider or (lambda key_id: KEY if key_id == "local.operator.v1" else None),
        now, source_verifier or (lambda expected, repo: None),
    )


def expect_reason(reason: str, callback) -> None:
    try:
        callback()
        raise AssertionError(f"expected {reason}")
    except execution.ExecutionVerificationError as exc:
        assert exc.reason == reason, (exc.reason, reason)


def test_positive_is_verified_but_activation_blocked() -> None:
    lock, projection, receipt = artifacts()
    result = verify(lock, projection, receipt)
    assert result["verified"] is True
    assert result["status"] == "activation_blocked"
    assert result["executable"] is False
    assert "argv" not in result and "env" not in result


def test_every_bound_component_rejects_tamper() -> None:
    lock, projection, receipt = artifacts()
    for field in ("resolved_plan_sha256", "source_identity_sha256", "projection_sha256",
                  "hardware_identity_sha256"):
        changed = dict(receipt, **{field: "0" * 64})
        changed["mac_hmac_sha256"] = hmac.new(
            KEY, resolver.jcs_bytes({k: v for k, v in changed.items() if k != "mac_hmac_sha256"}),
            hashlib.sha256).hexdigest()
        expect_reason("receipt_binding_mismatch", lambda changed=changed: verify(lock, projection, changed))
    changed = dict(receipt, nonce="2" * 32)
    expect_reason("receipt_mac_invalid", lambda: verify(lock, projection, changed))


def test_key_contract_and_closed_receipt() -> None:
    lock, projection, receipt = artifacts()
    expect_reason("signing_key_unknown", lambda: verify(lock, projection, receipt, key_provider=lambda _: None))
    expect_reason("signing_key_invalid", lambda: verify(lock, projection, receipt, key_provider=lambda _: b"short"))
    extra = dict(receipt, explanation="trust me")
    expect_reason("schema_invalid", lambda: verify(lock, projection, extra))
    try:
        resolver.parse_json_strict('{"artifact_type":"execution_authorization_receipt","nonce":"a","nonce":"b"}')
        raise AssertionError("duplicate receipt field accepted")
    except resolver.ResolverError as exc:
        assert exc.reason == "duplicate_json_key"


def test_timing_boundaries_fail_closed() -> None:
    lock, projection, receipt = artifacts()
    cases = (
        (dict(receipt, expires_at="2026-09-07T12:05:00Z"), "receipt_expired"),
        (dict(receipt, issued_at="2026-09-07T12:06:01Z"), "receipt_not_yet_valid"),
        (dict(receipt, expires_at="2026-09-07T13:00:01Z"), "receipt_ttl_exceeded"),
        (dict(receipt, expires_at="2026-09-07T11:59:59Z"), "receipt_window_invalid"),
    )
    for changed, reason in cases:
        changed["mac_hmac_sha256"] = hmac.new(
            KEY, resolver.jcs_bytes({k: v for k, v in changed.items() if k != "mac_hmac_sha256"}),
            hashlib.sha256).hexdigest()
        expect_reason(reason, lambda changed=changed: verify(lock, projection, changed))


def test_plan_projection_catalog_fieldset_and_hardware_drift() -> None:
    lock, projection, receipt = artifacts()
    changed_projection = copy.deepcopy(projection)
    changed_projection["nix"]["mySystem"]["deployment.rootFsckMode"] = "skip"
    expect_reason("projection_mismatch", lambda: verify(lock, changed_projection, receipt))
    expect_reason("catalog_digest_mismatch", lambda: verify(lock, projection, receipt, module_bytes=MODULE_BYTES + b"\n"))
    expect_reason("catalog_digest_mismatch", lambda: verify(lock, projection, receipt, fieldset_bytes=FIELDSET_BYTES + b"\n"))
    changed_hw = hardware()
    changed_hw["ram"] = {"total_bytes": 16 * 1024**3}
    expect_reason("hardware_identity_mismatch", lambda: verify(lock, projection, receipt, hw=changed_hw))


def test_fieldset_rejects_expert_and_unlisted_catalog_projection() -> None:
    lock, _, _ = artifacts()
    for field in ("deployment.rootFsckMode", "services.unlisted.enable"):
        catalog = copy.deepcopy(MODULES)
        entry = next(item for item in catalog["modules"] if item["id"] == "role.gaming")
        entry["projected_mysystem_fields"].append(field)
        try:
            resolver.compile_projection(lock, catalog, FIELDSET_BYTES)
            raise AssertionError(f"unsafe field accepted: {field}")
        except resolver.ResolverError as exc:
            assert exc.reason == "fieldset_authority_violation"


def test_source_verifier_is_mandatory_and_no_executor_is_called() -> None:
    lock, projection, receipt = artifacts()
    calls: list[tuple[dict, str]] = []
    verify(lock, projection, receipt, source_verifier=lambda expected, repo: calls.append((dict(expected), repo)))
    assert calls == [(source(), "/repo")]
    def reject_source(expected, repo):
        raise resolver.ResolverError("source_dirty", "dirty")
    expect_reason("source_dirty", lambda: verify(lock, projection, receipt, source_verifier=reject_source))
    assert projection["executor"]["argv"][0].endswith("nixos-quick-deploy.sh")


def test_cli_help() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "scripts/ai/aqos-install-verify"), "--help"],
                            cwd=ROOT, check=True, capture_output=True, text=True)
    assert "--authorization-key" in result.stdout and "--signing-key-id" in result.stdout
    assert "--hardware" not in result.stdout


def test_cli_secret_file_is_regular_private_and_bounded() -> None:
    load_secret = runpy.run_path(str(ROOT / "scripts/ai/aqos-install-verify"))["load_secret"]
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        key_path = directory / "key"
        key_path.write_bytes(KEY)
        os.chmod(key_path, 0o600)
        assert load_secret(key_path) == KEY
        os.chmod(key_path, 0o644)
        expect_reason("signing_key_permissions", lambda: load_secret(key_path))
        os.chmod(key_path, 0o600)
        link = directory / "link"
        link.symlink_to(key_path)
        expect_reason("signing_key_unavailable", lambda: load_secret(link))
        key_path.write_bytes(b"x" * 4097)
        expect_reason("signing_key_invalid", lambda: load_secret(key_path))


def main() -> int:
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in sorted(tests, key=lambda item: item.__name__):
        test()
    print(f"test-aqos-install-execution: ok {len(tests)}/{len(tests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
