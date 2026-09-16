#!/usr/bin/env python3
"""Regression checks for dashboard advanced runtime summary integration."""

from __future__ import annotations

import importlib
import asyncio
import os
import sys
import tempfile
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    production_module = (ROOT / "nix/modules/services/command-center-dashboard.nix").read_text(encoding="utf-8")
    requirements = (ROOT / "dashboard/backend/requirements.txt").read_text(encoding="utf-8")
    assert_true("      jsonschema\n" in production_module, "production dashboard Python must include schema validation")
    assert_true(any(line.startswith("jsonschema") for line in requirements.splitlines()), "development dashboard must declare schema validation")
    with tempfile.TemporaryDirectory(prefix="dashboard-advanced-runtime-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "context.db")
        os.environ["DASHBOARD_MODE"] = "test"

        dashboard_main = importlib.import_module("api.main")
        aistack_module = importlib.import_module("api.routes.aistack")
        dashboard_main = importlib.reload(dashboard_main)
        aistack_module = importlib.reload(aistack_module)

        class FakeResponse:
            def __init__(self, payload):
                self.status = 200
                self._payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            def raise_for_status(self):
                return None

            async def json(self):
                return self._payload

        class FakeClientSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            def get(self, url, headers=None, timeout=None):
                if url.endswith("/control/ai-coordinator/advanced-features/readiness"):
                    return FakeResponse(
                        {
                            "readiness": {
                                "phase_6_offloading": {
                                    "status": "implementation_exists",
                                    "quality_assessments": 14,
                                    "benchmarked_profiles": 3,
                                    "local_fallback_mode": "default",
                                },
                                "phase_7_efficiency": {
                                    "status": "implementation_exists",
                                    "ab_variants": 5,
                                    "compressions": 21,
                                    "tokens_saved": 830,
                                    "context_reuse_ready": True,
                                },
                                "phase_9_capability_gap": {
                                    "status": "implementation_exists",
                                    "remediation_artifacts_recorded": True,
                                },
                                "phase_10_learning": {
                                    "status": "implementation_exists",
                                },
                            }
                        }
                    )
                if url.endswith("/control/ai-coordinator/advanced-features/offloading/quality-profiles"):
                    return FakeResponse({"profiles": [{"agent_id": "a"}, {"agent_id": "b"}]})
                if url.endswith("/control/ai-coordinator/advanced-features/context/tier-stats"):
                    return FakeResponse({"total_selections": 17})
                if url.endswith("/control/ai-coordinator/advanced-features/capability-gap/stats"):
                    return FakeResponse({"total_gaps": 4, "failure_patterns": {"tool_missing": 2, "knowledge_missing": 1}})
                if url.endswith("/control/ai-coordinator/advanced-features/learning/stats"):
                    return FakeResponse({"total_signals": 11, "recommendation_count": 3, "high_confidence_recommendations": 1})
                raise AssertionError(f"unexpected URL: {url}")

        fake_session = FakeClientSession()

        async def fake_get_http_session():
            return fake_session

        aistack_module.get_http_session = fake_get_http_session

        ready_catalog = tmp_path / "capability-gap-catalog.json"
        ready_catalog.write_text(
            json.dumps(
                {
                    "version": "test",
                    "capabilities": [],
                    "outcomes": [
                        {
                            "id": "native",
                            "status": "equivalent",
                            "aliases": ["shared"],
                            "kind": "workflow",
                            "domains": ["qa"],
                            "authority": "native",
                            "qa": "fixture",
                            "visibility": "fixture",
                            "evidence_paths": ["scripts/ai/aq-capability-gap"],
                        },
                        {
                            "id": "partial",
                            "status": "partial",
                            "aliases": ["shared"],
                            "kind": "workflow",
                            "domains": ["qa"],
                            "authority": "native",
                            "qa": "fixture",
                            "visibility": "fixture",
                            "evidence_paths": [],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        catalog_summary = aistack_module._capability_outcome_catalog_summary(ready_catalog)
        assert_true(catalog_summary["available"], "valid outcome catalog should be available")
        assert_true(catalog_summary["counts"]["equivalent"] == 1, "catalog should count equivalent outcomes")
        assert_true(catalog_summary["counts"]["partial"] == 1, "catalog should count partial outcomes")
        assert_true(catalog_summary["counts"]["ambiguous"] == 1, "catalog should expose ambiguous aliases")
        assert_true(catalog_summary["evidence_scope"] == "metadata-only", "catalog must not claim runtime proof")
        missing_summary = aistack_module._capability_outcome_catalog_summary(tmp_path / "missing.json")
        assert_true(missing_summary["status"] == "unverified", "missing catalog must remain unverified")
        malformed_catalog = tmp_path / "malformed.json"
        malformed_catalog.write_text("[]", encoding="utf-8")
        malformed_summary = aistack_module._capability_outcome_catalog_summary(malformed_catalog)
        assert_true(malformed_summary["status"] == "unverified", "non-object catalog must fail closed")
        valid_payload = json.loads(ready_catalog.read_text(encoding="utf-8"))
        invalid_payloads = {}
        duplicate_payload = json.loads(json.dumps(valid_payload))
        duplicate_payload["outcomes"][1]["id"] = "native"
        invalid_payloads["duplicate-id"] = duplicate_payload
        too_many_payload = json.loads(json.dumps(valid_payload))
        too_many_payload["outcomes"] = [
            {**valid_payload["outcomes"][0], "id": f"item-{index}"}
            for index in range(257)
        ]
        invalid_payloads["too-many"] = too_many_payload
        missing_field_payload = json.loads(json.dumps(valid_payload))
        del missing_field_payload["outcomes"][0]["authority"]
        invalid_payloads["missing-authority"] = missing_field_payload
        for field, value in (("status", "PASS"), ("authority", "unknown"),
                             ("aliases", [""]), ("domains", [])):
            invalid_payload = json.loads(json.dumps(valid_payload))
            invalid_payload["outcomes"][0][field] = value
            invalid_payloads[f"invalid-{field}"] = invalid_payload
        for name, invalid_payload in invalid_payloads.items():
            invalid_catalog = tmp_path / f"{name}.json"
            invalid_catalog.write_text(json.dumps(invalid_payload), encoding="utf-8")
            invalid_summary = aistack_module._capability_outcome_catalog_summary(invalid_catalog)
            assert_true(invalid_summary["status"] == "unverified", f"{name} must fail closed")
            assert_true(not invalid_summary["available"], f"{name} must not report valid catalog")
        unsafe_catalog = tmp_path / "unsafe-catalog.json"
        unsafe_catalog.write_text(
            json.dumps({**valid_payload, "outcomes": [{
                **valid_payload["outcomes"][0],
                "evidence_paths": ["../../outside", "/etc/passwd"],
            }]}),
            encoding="utf-8",
        )
        unsafe_summary = aistack_module._capability_outcome_catalog_summary(unsafe_catalog)
        assert_true(unsafe_summary["status"] == "unverified", "unsafe evidence paths must fail schema validation")
        assert_true(not unsafe_summary["available"], "unsafe catalog must not report equivalent outcomes")

        payload = asyncio.run(aistack_module.get_advanced_runtime_summary())
        summary = payload.get("summary") or {}
        assert_true((summary.get("offloading") or {}).get("quality_profiles") == 2, "summary should count quality profiles")
        assert_true((summary.get("context_efficiency") or {}).get("tier_selections") == 17, "summary should preserve context tier selections")
        assert_true((summary.get("capability_gap") or {}).get("failure_patterns") == 2, "summary should count failure patterns")
        outcomes = (summary.get("capability_gap") or {}).get("outcomes") or {}
        assert_true(outcomes.get("available") is True, "runtime summary should expose the native outcome catalog")
        assert_true((outcomes.get("counts") or {}).get("denied") == 1, "runtime summary should expose denied outcomes")
        assert_true((summary.get("learning") or {}).get("signals_recorded") == 11, "summary should preserve learning signals")

        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        dashboard_js = (ROOT / "assets" / "dashboard.js").read_text(encoding="utf-8")
        assert_true('/assets/dashboard.js' in html, "dashboard should load the canonical client asset")
        assert_true("async function loadRuntimeDetails()" in dashboard_js, "dashboard should load advanced runtime details")
        assert_true('/aistack/advanced/runtime-summary' in dashboard_js, "dashboard should call advanced runtime summary route")
        assert_true('id="runtimeDetails"' in html, "dashboard should expose the runtime detail projection")
        assert_true('"· outcome catalog"' in dashboard_js, "dashboard should label outcome-catalog health")
        assert_true('"UNVERIFIED"' in dashboard_js, "dashboard must expose unavailable catalog evidence")
        assert_true('"· miss / deny / amb"' in dashboard_js, "dashboard should expose outcome verdict totals")

    print("PASS: dashboard advanced runtime summary integration present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
