#!/usr/bin/env python3
"""C0 executable tests for the pure durable dispatch contract."""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "scripts/ai/lib/agent_dispatch_contract.py"
ENVELOPE_SCHEMA = REPO / "config/schemas/agent-dispatch-envelope.schema.json"
POLICY_SCHEMA = REPO / "config/schemas/agent-dispatch-policy.schema.json"
POLICY = REPO / "config/agent-dispatch-policy.json"
FIXTURE = REPO / "scripts/testing/fixtures/agent-dispatch-contract-golden.json"
spec = importlib.util.spec_from_file_location("agent_dispatch_contract_c0", MODULE)
assert spec and spec.loader
contract = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = contract
spec.loader.exec_module(contract)


class AgentDispatchContractC0(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.envelope_schema = json.loads(ENVELOPE_SCHEMA.read_text(encoding="utf-8"))
        cls.policy_schema = json.loads(POLICY_SCHEMA.read_text(encoding="utf-8"))
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.request = cls.fixture["request"]

    def status(self) -> dict:
        return contract.initial_status(self.request, task_id="claude:c0-golden-1", fencing_epoch=7)

    def test_01_schemas_policy_and_each_envelope_are_closed(self) -> None:
        Draft202012Validator.check_schema(self.envelope_schema)
        Draft202012Validator.check_schema(self.policy_schema)
        contract.validate_policy(self.policy, self.policy_schema)
        contract.validate_document(self.request, self.envelope_schema, max_bytes=65536)
        for key in ("unknown", "prompt", "argv", "raw_error"):
            bad = json.loads(json.dumps(self.request)); bad[key] = "canary"
            with self.assertRaises(contract.ContractError):
                contract.validate_document(bad, self.envelope_schema, max_bytes=65536)

        adapter = {
            "schema_version": "aq.dispatch.adapter.v1", "adapter": "antigravity",
            "capabilities": self.policy["required_capabilities"], "network_boundary": "declared_remote",
            "credential_boundary": "runtime_secret", "progress_evidence": "inbox_receipt",
            "concurrency_limit": 2, "cancellation_ownership": "lease_and_fence",
        }
        status = self.status()
        ack = {"schema_version": "aq.dispatch.ack.v1", "task_id": status["task_id"],
               "idempotency_key": self.request["idempotency_key"], "revision": 0, "state": "queued",
               "adapter": "claude", "contract_version": contract.CONTRACT_VERSION, "reason": None}
        event = {"schema_version": "aq.dispatch.event.v1", "event_id": "event:c0-1", "task_id": status["task_id"],
                 "revision": 0, "state": "queued", "reason": None, "observed_epoch": 1784232000}
        failure = {"schema_version": "aq.dispatch.failure.v1", "task_id": status["task_id"],
                   "reason": "provider_transient", "disposition": "retry", "retry_after_seconds": 30,
                   "evidence_codes": ["provider_exit_transient"]}
        for document in (ack, status, event, adapter, failure):
            contract.validate_document(document, self.envelope_schema, max_bytes=65536)
            bad = dict(document); bad["unknown"] = True
            with self.assertRaisesRegex(contract.ContractError, "schema_invalid"):
                contract.validate_document(bad, self.envelope_schema, max_bytes=65536)

    def test_02_idempotent_admission_and_exactly_one_start_grant(self) -> None:
        first, is_new = contract.admit_request(self.request, {}, task_id="claude:c0-golden-1", fencing_epoch=7)
        self.assertTrue(is_new)
        duplicate, is_new = contract.admit_request(
            self.request, {self.request["idempotency_key"]: first}, task_id="claude:other", fencing_epoch=9,
        )
        self.assertFalse(is_new); self.assertEqual(duplicate, first)
        starting, grant = contract.authorize_start(first, self.policy, expected_revision=0,
                                                   expected_fencing_epoch=7, lease_owner="adapter:claude-1")
        self.assertTrue(grant); self.assertEqual((starting["revision"], starting["attempt"]), (1, 1))
        with self.assertRaisesRegex(contract.ContractError, "cas_revision_mismatch"):
            contract.authorize_start(first, self.policy, expected_revision=1,
                                     expected_fencing_epoch=7, lease_owner="adapter:claude-2")

    def test_03_cas_fence_lease_and_terminal_replay(self) -> None:
        starting, _ = contract.authorize_start(self.status(), self.policy, expected_revision=0,
                                               expected_fencing_epoch=7, lease_owner="adapter:claude-1")
        running = contract.transition_status(starting, "running", self.policy, expected_revision=1,
                                             expected_fencing_epoch=7, expected_lease_owner="adapter:claude-1",
                                             lease_owner="adapter:claude-1")
        done = contract.transition_status(running, "done", self.policy, expected_revision=2,
                                          expected_fencing_epoch=7, expected_lease_owner="adapter:claude-1",
                                          lease_owner=None)
        self.assertEqual(contract.transition_status(done, "done", self.policy, expected_revision=3,
                                                    expected_fencing_epoch=7, expected_lease_owner=None), done)
        with self.assertRaisesRegex(contract.ContractError, "terminal_transition_forbidden"):
            contract.transition_status(done, "failed", self.policy, expected_revision=3,
                                       expected_fencing_epoch=7, expected_lease_owner=None)

    def test_04_uncertain_restart_never_respawns(self) -> None:
        stale = contract.reconcile_uncertain(self.status(), executor_proven_terminal=False,
                                             expected_revision=0, expected_fencing_epoch=7,
                                             expected_lease_owner=None, policy=self.policy)
        self.assertEqual((stale["state"], stale["reason"]), ("stale", "executor_lost"))
        with self.assertRaises(contract.ContractError):
            contract.authorize_start(stale, self.policy, expected_revision=1,
                                     expected_fencing_epoch=7, lease_owner="adapter:claude-1")

    def test_05_failure_taxonomy_retry_park_and_hard_close(self) -> None:
        self.assertEqual(contract.classify_failure("provider_transient", 30, self.policy)["next_state"], "queued")
        self.assertEqual(contract.classify_failure("quota_parked", 7200, self.policy)["next_state"], "parked")
        self.assertEqual(contract.classify_failure("auth_failed", None, self.policy)["next_state"], "failed")
        with self.assertRaisesRegex(contract.ContractError, "retry_delay_invalid"):
            contract.classify_failure("provider_transient", 301, self.policy)

    def test_06_park_requires_epoch_and_preserves_lane(self) -> None:
        starting, _ = contract.authorize_start(self.status(), self.policy, expected_revision=0,
                                               expected_fencing_epoch=7, lease_owner="adapter:claude-1")
        running = contract.transition_status(starting, "running", self.policy, expected_revision=1,
                                             expected_fencing_epoch=7, expected_lease_owner="adapter:claude-1",
                                             lease_owner="adapter:claude-1")
        parked = contract.transition_status(running, "parked", self.policy, expected_revision=2,
                                            expected_fencing_epoch=7, expected_lease_owner="adapter:claude-1",
                                            lease_owner=None, reason="quota_parked", earliest_resume_epoch=1784239200)
        self.assertEqual((parked["state"], parked["adapter"], parked["earliest_resume_epoch"]),
                         ("parked", "claude", 1784239200))

    def test_07_golden_vectors_are_complete_and_deterministic(self) -> None:
        required = {"caller_parent_death", "background_pid_disappearance", "zero_byte_exit",
                    "supervisor_stderr_before_log", "shell_metacharacters", "duplicate_idempotency_key",
                    "stale_cas", "fence_loss", "pid_namespace_mismatch", "daemon_restart_uncertain_executor",
                    "short_transient_retry", "long_quota_parking", "auth_policy_hard_failure",
                    "cancellation_ownership_mismatch", "oversized_envelope", "unknown_fields", "privacy_canaries"}
        self.assertEqual({item["name"] for item in self.fixture["vectors"]}, required)
        self.assertEqual(json.loads(json.dumps(self.fixture, sort_keys=True)), self.fixture)

    def test_08_golden_errors_privacy_size_and_metacharacters(self) -> None:
        with self.assertRaisesRegex(contract.ContractError, "envelope_too_large"):
            contract.validate_document(self.request, self.envelope_schema, max_bytes=8)
        with self.assertRaisesRegex(contract.ContractError, "privacy_field_forbidden"):
            contract.assert_private({"prompt": "PROMPT_CANARY secret-token"})
        vector = next(item for item in self.fixture["vectors"] if item["name"] == "shell_metacharacters")
        self.assertEqual(vector["value"], "$(touch /tmp/nope); `id`; a'b\"c")
        imports = {node.names[0].name for node in ast.walk(ast.parse(MODULE.read_text())) if isinstance(node, ast.Import)}
        self.assertFalse(imports.intersection({"subprocess", "os"}))

    def test_09_contract_health_separates_adapters_and_coverage(self) -> None:
        adapters = [{"adapter": lane, "capabilities": self.policy["required_capabilities"]}
                    for lane in self.policy["adapters"]]
        healthy = contract.contract_health(self.policy, adapters,
                                           {"aq_qa": True, "agent_ops": True, "web_dashboard": True})
        self.assertEqual(healthy["verdict"], "healthy")
        blocked = contract.contract_health(self.policy, adapters[:-1],
                                           {"aq_qa": True, "agent_ops": True, "web_dashboard": False})
        self.assertEqual(blocked["verdict"], "blocked")
        self.assertEqual(blocked["adapter_health"]["antigravity"], "blocked")


if __name__ == "__main__":
    unittest.main(verbosity=2)
