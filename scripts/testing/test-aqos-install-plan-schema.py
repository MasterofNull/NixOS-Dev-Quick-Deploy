#!/usr/bin/env python3
"""Closed-contract tests for the AQ-OS install-plan v1 schema."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError


REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "config/schemas/aqos-install-plan-v1.schema.json"
GATE_PATH = REPO / "scripts/governance/tier0-validation-gate.sh"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
HASH = "a" * 64

REQUEST = {"artifact_type": "request_plan", "schema_version": "aqos-install-plan/v1"}
RESOLVED = {
    "artifact_type": "resolved_plan_lock",
    "schema_version": "aqos-install-plan/v1",
    "selection": {"golden_profile": "aqos-workstation", "roles": ["desktop"], "include_local_ai": False},
    "hardware_summary": {
        "summary_version": "hardware-summary/v1", "hardware_identity_sha256": HASH,
        "evidence_status": "sufficient", "gpu_count": 1,
    },
    "catalog_digests": {"module_catalog_sha256": HASH, "ai_fit_policy_catalog_sha256": "b" * 64},
    "source_identity": {
        "oid_algorithm": "sha256", "git_commit": "c" * 64, "git_tree": "d" * 64,
        "clean_worktree": True, "flake_lock_sha256": "e" * 64,
        "nix_system": "x86_64-linux", "flake_installable": ".#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel",
        "host_target": "hyperd-ai-dev",
    },
}
RECEIPT = {
    "artifact_type": "execution_authorization_receipt", "schema_version": "aqos-install-plan/v1",
    "resolved_plan_sha256": HASH, "hardware_identity_sha256": "b" * 64,
    "issued_at": "2026-09-04T12:00:00Z", "expires_at": "2026-09-04T12:15:00Z", "nonce": "c" * 32,
}


def assert_invalid(document: dict) -> None:
    with unittest.TestCase().assertRaises(ValidationError):
        VALIDATOR.validate(document)


class InstallPlanSchemaTest(unittest.TestCase):
    def test_schema_is_valid_and_all_object_boundaries_are_closed(self) -> None:
        Draft202012Validator.check_schema(SCHEMA)

        def visit(value: object) -> None:
            if isinstance(value, dict):
                if value.get("type") == "object":
                    self.assertIs(value.get("additionalProperties"), False, value)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(SCHEMA)

    def test_tier0_gate_triggers_for_every_contract_path(self) -> None:
        source = GATE_PATH.read_text(encoding="utf-8")
        start = source.index("gate_aqos_install_plan_schema()")
        end = source.index("# Gate 5:", start)
        gate = source[start:end]
        for path in (
            "config/schemas/aqos-install-plan-v1.schema.json",
            "scripts/testing/test-aqos-install-plan-schema.py",
            "scripts/governance/tier0-validation-gate.sh",
        ):
            self.assertIn(path, gate)
        self.assertIn("gate_aqos_install_plan_schema || true", source)

    def test_valid_artifacts(self) -> None:
        for artifact in (REQUEST, RESOLVED, RECEIPT):
            with self.subTest(artifact=artifact["artifact_type"]):
                VALIDATOR.validate(artifact)

    def test_request_defaults_are_omittable(self) -> None:
        request = copy.deepcopy(REQUEST)
        request["selection"] = {"include_local_ai": True}
        VALIDATOR.validate(request)

    def test_unknown_top_level_and_nested_fields_are_rejected(self) -> None:
        unknown_top = copy.deepcopy(REQUEST)
        unknown_top["unknown"] = True
        assert_invalid(unknown_top)
        unknown_nested = copy.deepcopy(RESOLVED)
        unknown_nested["selection"]["unknown"] = True
        assert_invalid(unknown_nested)

    def test_secret_bearing_fields_are_rejected(self) -> None:
        for field in ("secret", "token", "api_key", "password", "passphrase"):
            with self.subTest(field=field):
                artifact = copy.deepcopy(REQUEST)
                artifact[field] = "not-allowed"
                assert_invalid(artifact)

    def test_resolved_lock_requires_all_identity_and_catalog_bindings(self) -> None:
        for path in (
            ("hardware_summary",), ("catalog_digests",), ("source_identity",),
            ("catalog_digests", "module_catalog_sha256"),
            ("catalog_digests", "ai_fit_policy_catalog_sha256"),
            ("source_identity", "git_commit"), ("source_identity", "git_tree"),
            ("source_identity", "flake_lock_sha256"), ("source_identity", "nix_system"),
            ("source_identity", "flake_installable"), ("source_identity", "host_target"),
        ):
            with self.subTest(path=path):
                artifact = copy.deepcopy(RESOLVED)
                target = artifact
                for key in path[:-1]:
                    target = target[key]
                del target[path[-1]]
                assert_invalid(artifact)

    def test_dirty_source_and_malformed_identity_are_rejected(self) -> None:
        dirty = copy.deepcopy(RESOLVED)
        dirty["source_identity"]["clean_worktree"] = False
        assert_invalid(dirty)
        for field, value in (
            ("git_commit", "a" * 40), ("git_tree", "not-an-oid"),
            ("flake_lock_sha256", "a" * 63), ("nix_system", "not a nix system"),
            ("flake_installable", "missing-hash-target"), ("host_target", "host target"),
        ):
            with self.subTest(field=field):
                artifact = copy.deepcopy(RESOLVED)
                artifact["source_identity"][field] = value
                assert_invalid(artifact)

    def test_oid_algorithm_branches_are_explicit_and_length_bound(self) -> None:
        sha1 = copy.deepcopy(RESOLVED)
        sha1["source_identity"].update({
            "oid_algorithm": "sha1", "git_commit": "c" * 40, "git_tree": "d" * 40,
        })
        VALIDATOR.validate(sha1)
        for algorithm, length in (("sha1", 64), ("sha256", 40), ("sha512", 64)):
            with self.subTest(algorithm=algorithm, length=length):
                artifact = copy.deepcopy(RESOLVED)
                artifact["source_identity"].update({
                    "oid_algorithm": algorithm,
                    "git_commit": "c" * length,
                    "git_tree": "d" * length,
                })
                assert_invalid(artifact)

    def test_provenance_cannot_enter_semantic_lock(self) -> None:
        artifact = copy.deepcopy(RESOLVED)
        artifact["provenance"] = {"branch": "main"}
        assert_invalid(artifact)

    def test_receipt_cannot_masquerade_as_a_plan(self) -> None:
        artifact = copy.deepcopy(RECEIPT)
        artifact["selection"] = copy.deepcopy(RESOLVED["selection"])
        assert_invalid(artifact)
        masquerade = copy.deepcopy(RECEIPT)
        masquerade["artifact_type"] = "resolved_plan_lock"
        assert_invalid(masquerade)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(InstallPlanSchemaTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
