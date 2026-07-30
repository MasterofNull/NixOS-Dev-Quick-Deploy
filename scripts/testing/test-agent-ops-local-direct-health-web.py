#!/usr/bin/env python3
"""Offline C0.6-T TUI/API/frontend privacy and Service Coverage contract tests."""
from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
import io
import asyncio
import json
import subprocess
import sys
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[2]
TUI = REPO / "scripts/ai/aq-tui-dashboard"
BACKEND = REPO / "dashboard/backend/api/routes/aistack.py"
FRONTEND = REPO / "assets/dashboard.js"
SCHEMA = REPO / "config/schemas/agent-ops-local-direct-health.schema.json"

loader = SourceFileLoader("c06t_tui", str(TUI))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec and spec.loader
tui = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tui
spec.loader.exec_module(tui)
sys.path.insert(0, str(REPO / "dashboard/backend"))
sys.path.insert(0, str(REPO))
from dashboard.backend.api.routes import aistack  # noqa: E402


def evidence(tests, age=0):
    return SimpleNamespace(age_seconds=age, payload={"results": {"tests": tests}})


def unavailable_payload():
    return {
        "schema_version": "aq.local-direct-health.v1", "assessment": "not_assessed",
        "health": "unavailable", "source_freshness": "unavailable",
        "deadline_health": "unavailable",
        "phase_counts": {key: None for key in ("queue", "prefill", "generation", "cleanup", "terminal")},
        "oldest_queue_age_s": None, "oldest_prefill_age_s": None,
        "oldest_generation_age_s": None, "active_deadline_count": None,
        "expired_active_count": None, "minimum_remaining_ms": None,
        "timeout_counts": {key: None for key in ("queue", "prefill", "generation", "cleanup")},
        "generation_silence_exceeded_count": None, "stale_owner_count": None,
        "reconciliation_count": None, "output_incomplete_count": None,
        "budget_mismatch_count": None, "terminal_convergence_gap_count": None,
        "coverage": {"projection": "healthy", "phase0": "unavailable", "web_dashboard": "unavailable"},
        "reason_codes": ["source_not_instrumented", "coverage_incomplete"],
    }


def healthy_payload():
    return {
        "schema_version": "aq.local-direct-health.v1", "assessment": "assessed",
        "health": "healthy", "source_freshness": "fresh", "deadline_health": "healthy",
        "phase_counts": {key: 0 for key in ("queue", "prefill", "generation", "cleanup", "terminal")},
        "oldest_queue_age_s": 0, "oldest_prefill_age_s": 0, "oldest_generation_age_s": 0,
        "active_deadline_count": 0, "expired_active_count": 0, "minimum_remaining_ms": 0,
        "timeout_counts": {key: 0 for key in ("queue", "prefill", "generation", "cleanup")},
        "generation_silence_exceeded_count": 0, "stale_owner_count": 0,
        "reconciliation_count": 0, "output_incomplete_count": 0,
        "budget_mismatch_count": 0, "terminal_convergence_gap_count": 0,
        "coverage": {"projection": "healthy", "phase0": "healthy", "web_dashboard": "healthy"},
        "reason_codes": ["healthy"],
    }


class LocalDirectHealthWebTests(unittest.TestCase):
    def test_01_qa_evidence_exact_mapping_and_300_second_boundary(self):
        tests = [
            {"layer": 5, "id": "0.10.42", "status": "PASS",
             "description": "local-direct lifecycle route contract"},
            {"layer": 5, "id": "0.10.43", "status": "SKIP",
             "description": "local-direct Agent Ops card visibility"},
        ]
        value = tui.read_local_direct_coverage(lambda: evidence(tests, 300))
        self.assertEqual(value, {"projection": "healthy", "phase0": "healthy", "web_dashboard": "unavailable"})
        stale = tui.read_local_direct_coverage(lambda: evidence(tests, 300.001))
        self.assertEqual(stale["phase0"], "unavailable")

    def test_02_missing_duplicate_unknown_or_details_fail_closed(self):
        route = {"layer": 5, "id": "0.10.42", "status": "PASS",
                 "description": "local-direct lifecycle route contract"}
        card = {"layer": 5, "id": "0.10.43", "status": "PASS",
                "description": "local-direct Agent Ops card visibility"}
        invalid = [
            [],
            [route, route],
            [{**route, "status": "ERROR"}, card],
            [{**route, "details": []}, card],
            [{key: value for key, value in route.items() if key != "layer"}, card],
            [{**route, "layer": True}, card],
            [{**route, "description": "drift"}, card],
        ]
        for tests in invalid:
            with self.subTest(tests=tests):
                value = tui.read_local_direct_coverage(lambda: evidence(tests))
                self.assertIn("blocked", value.values())

    def test_03_tui_mode_emits_only_sanitized_closed_object(self):
        payload = unavailable_payload()
        with mock.patch.object(sys, "argv", ["aq-tui-dashboard", "--local-direct-health-json"]), \
             mock.patch.object(tui, "read_agent_ops_projection", return_value={"local_direct_health": payload}), \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(tui.main(), 0)
        rendered = output.getvalue()
        Draft202012Validator(json.loads(SCHEMA.read_text())).validate(json.loads(rendered))
        for canary in ("prompt", "/tmp/private", "pid", "argv", "https://private", "credential"):
            self.assertNotIn(canary, rendered)

    def test_04_backend_is_fixed_argv_bounded_cached_and_no_registry_reader(self):
        source = BACKEND.read_text(encoding="utf-8")
        section = source[source.index("_LOCAL_DIRECT_FIELDS"):source.index('@router.get("/agent-ops/status")')]
        self.assertIn('@router.get("/agent-ops/local-direct-health")', section)
        self.assertIn('"--local-direct-health-json"', section)
        self.assertIn("asyncio.create_subprocess_exec", section)
        self.assertIn("asyncio.wait_for", section)
        self.assertIn("_LOCAL_DIRECT_HEALTH_MAX_BYTES", section)
        self.assertIn("_LOCAL_DIRECT_HEALTH_REFRESH", section)
        self.assertIn("_bounded_local_direct_output", section)
        self.assertIn("asyncio.shield", section)
        self.assertNotIn("registry.jsonl", section)
        self.assertNotIn("shell=True", section)

    def test_05_frontend_uses_existing_loader_fixed_maps_and_no_blank_sentinel(self):
        source = FRONTEND.read_text(encoding="utf-8")
        start = source.index("function composeAgentOpsStatus(d, local)")
        end = source.index("// ─── INTELLIGENCE: AGENT LESSONS", start)
        section = source[start:end]
        self.assertIn('apiFetch("/agent-ops/local-direct-health")', section)
        self.assertIn("Local Direct Lifecycle", section)
        self.assertIn("Not instrumented", section)
        self.assertIn("coordinator.available !== false", section)
        self.assertIn("!Array.isArray(d)", section)
        self.assertIn("!Array.isArray(local)", section)
        self.assertNotIn("setInterval", section)
        self.assertNotIn('"--"', section)
        self.assertNotIn("local.innerHTML", section)
        self.assertNotIn("if (!d) {", section)

    def test_05b_frontend_fallback_local_and_severity_cross_product_is_executable(self):
        source = FRONTEND.read_text(encoding="utf-8")
        start = source.index("function composeAgentOpsStatus(d, local)")
        end = source.index("\n}\n\nasync function loadAgentOpsStatus()", start) + 2
        helper = source[start:end]
        coordinators = [
            None, "malformed", [], {"available": False}, {"available": True},
            {"available": True, "drift_score": 0.5},
            {"available": True, "alert_active": True},
        ]
        locals_ = [
            None, "malformed", [], {"health": "healthy"}, {"health": "degraded"},
            {"health": "unavailable"}, {"health": "blocked"},
        ]
        script = (
            f"{helper}\n"
            f"const coordinators = {json.dumps(coordinators)};\n"
            f"const locals = {json.dumps(locals_)};\n"
            "const out = [];\n"
            "for (const d of coordinators) for (const local of locals) {\n"
            "  const s = composeAgentOpsStatus(d, local);\n"
            "  out.push({available:s.coordinatorAvailable, local:s.localHealth,"
            "coordinatorSeverity:s.coordinatorSeverity,localSeverity:s.localSeverity,severity:s.severity});\n"
            "}\nprocess.stdout.write(JSON.stringify(out));"
        )
        run = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)
        matrix = json.loads(run.stdout)
        self.assertEqual(len(matrix), len(coordinators) * len(locals_))
        local_levels = [1, 1, 1, 0, 1, 1, 2]
        coordinator_levels = [1, 1, 1, 1, 0, 1, 2]
        for c_index, expected_coordinator in enumerate(coordinator_levels):
            for l_index, expected_local in enumerate(local_levels):
                value = matrix[c_index * len(locals_) + l_index]
                self.assertEqual(value["coordinatorSeverity"], expected_coordinator)
                self.assertEqual(value["localSeverity"], expected_local)
                self.assertEqual(value["severity"], max(expected_coordinator, expected_local))
        self.assertFalse(matrix[2 * len(locals_)]["available"], "array coordinator must reject")
        self.assertEqual(matrix[2]["local"], "unavailable", "array local state must reject")

    def test_06_phase0_ids_are_ordinary_and_unique(self):
        source = (REPO / "scripts/testing/harness_qa/phases/phase0.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("def _check_local_direct_health_contract"), 1)
        self.assertEqual(source.count("def _check_local_direct_health_card"), 1)
        self.assertIn('"0.10.42"', source)
        self.assertIn('"0.10.43"', source)
        self.assertNotIn("details=", source[source.index("def _check_local_direct_health_contract"):])
        self.assertEqual(source.count('"local-direct lifecycle route contract"'), 1)
        self.assertEqual(source.count('"local-direct Agent Ops card visibility"'), 1)
        section = source[source.index("def _check_local_direct_health_contract"):
                         source.index("def _check_local_direct_health_card")]
        self.assertLess(section.index("for checker in checkers"), section.index("if ctx.dashboard_safe"))
        card_section = source[source.index("def _check_local_direct_health_card"):
                              source.index("def _check_workflow_shadow_contract")]
        for reviewed in (section, card_section):
            self.assertIn("nix/modules/core/options.nix", reviewed)
            self.assertIn("commandCenterApi = lib.mkOption", reviewed)
            self.assertNotIn("8889", reviewed)

    def test_06b_recursive_privacy_canaries_absent_from_every_rendering_boundary(self):
        combined = "\n".join(path.read_text(encoding="utf-8") for path in (FRONTEND, SCHEMA))
        payload = json.dumps(unavailable_payload())
        for canary in ("private-task", "/tmp/private", "secret-token", "https://private",
                       "raw_provider_error", "Authorization", "argv", "credential"):
            self.assertNotIn(canary, payload)
        self.assertNotIn("local_direct.producer", combined)


class LocalDirectBackendAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        aistack._LOCAL_DIRECT_HEALTH_CACHE.update(
            accepted_at=0.0, source_age_s=None, payload_bytes=None,
        )
        aistack._LOCAL_DIRECT_HEALTH_REFRESH = None

    class Proc:
        def __init__(self, stdout=b"", stderr=b"", *, running=False):
            self.stdout = asyncio.StreamReader(); self.stdout.feed_data(stdout); self.stdout.feed_eof()
            self.stderr = asyncio.StreamReader(); self.stderr.feed_data(stderr); self.stderr.feed_eof()
            self.returncode = None if running else 0
            self.terminated = self.killed = self.waited = False
        def terminate(self): self.terminated = True; self.returncode = -15
        def kill(self): self.killed = True; self.returncode = -9
        async def wait(self): self.waited = True; return self.returncode

    async def test_07_subprocess_acceptance_and_malformed_stale_cache(self):
        with mock.patch.object(aistack.asyncio, "create_subprocess_exec",
                               return_value=self.Proc(json.dumps(healthy_payload()).encode())) as launch:
            first = await aistack._refresh_local_direct_health()
        self.assertEqual((first["schema_version"], first["source_freshness"]),
                         ("aq.local-direct-health.v1", "fresh"))
        self.assertEqual(launch.call_args.args[-1], "--local-direct-health-json")

        with mock.patch.object(aistack.asyncio, "create_subprocess_exec",
                               return_value=self.Proc(b'{"private_path":"/tmp/canary"}')):
            stale = await aistack._refresh_local_direct_health()
        self.assertEqual((stale["source_freshness"], stale["health"]), ("stale", "degraded"))
        Draft202012Validator(json.loads(SCHEMA.read_text())).validate(stale)
        self.assertNotIn("canary", json.dumps(stale))

    async def test_08_route_coalesces_concurrent_refreshes(self):
        result = unavailable_payload()
        gate = asyncio.Event()
        async def refresh():
            await gate.wait()
            return result
        with mock.patch.object(aistack, "_refresh_local_direct_health", side_effect=refresh) as call:
            first = asyncio.create_task(aistack.get_local_direct_health())
            second = asyncio.create_task(aistack.get_local_direct_health())
            await asyncio.sleep(0)
            gate.set()
            self.assertEqual(await first, result)
            self.assertEqual(await second, result)
        self.assertEqual(call.call_count, 1)

    async def test_09_cache_boundaries_and_schema_valid_final_response(self):
        accepted = healthy_payload()
        encoded = json.dumps(accepted).encode()
        aistack._LOCAL_DIRECT_HEALTH_CACHE.update(
            accepted_at=100.0, source_age_s=0.0, payload_bytes=encoded,
        )
        with mock.patch.object(aistack.time, "monotonic", return_value=110.0):
            at_ten = aistack._local_direct_effective_cache(aistack.time.monotonic())
        self.assertEqual(at_ten["source_freshness"], "fresh")
        with mock.patch.object(aistack.time, "monotonic", return_value=110.001):
            stale = aistack._local_direct_effective_cache(aistack.time.monotonic())
        self.assertEqual((stale["source_freshness"], stale["health"]), ("stale", "degraded"))
        with mock.patch.object(aistack.time, "monotonic", return_value=160.0):
            at_sixty = aistack._local_direct_effective_cache(aistack.time.monotonic())
        self.assertEqual(at_sixty["assessment"], "assessed")
        with mock.patch.object(aistack.time, "monotonic", return_value=160.001):
            expired = aistack._local_direct_effective_cache(aistack.time.monotonic())
        self.assertEqual(expired["assessment"], "not_assessed")
        Draft202012Validator(json.loads(SCHEMA.read_text())).validate(expired)

    async def test_09b_fast_path_uses_the_same_effective_age_projection(self):
        accepted = healthy_payload()
        aistack._LOCAL_DIRECT_HEALTH_CACHE.update(
            accepted_at=100.0, source_age_s=10.0,
            payload_bytes=json.dumps(accepted).encode(),
        )
        with mock.patch.object(aistack.time, "monotonic", return_value=100.001):
            value = await aistack.get_local_direct_health()
        self.assertEqual((value["source_freshness"], value["health"]), ("stale", "degraded"))
        self.assertEqual(accepted["source_freshness"], "fresh", "cached evidence must not mutate")

    async def test_09c_effective_age_never_improves_worse_health_reason_or_coverage(self):
        blocked = healthy_payload()
        blocked.update(health="blocked", deadline_health="blocked", reason_codes=["budget_mismatch_observed"])
        blocked["budget_mismatch_count"] = 1
        blocked["coverage"]["phase0"] = "blocked"
        aistack._LOCAL_DIRECT_HEALTH_CACHE.update(
            accepted_at=100.0, source_age_s=10.0,
            payload_bytes=json.dumps(blocked).encode(),
        )
        stale = aistack._local_direct_effective_cache(100.001)
        expired = aistack._local_direct_effective_cache(150.001)
        self.assertEqual(stale["health"], "blocked")
        self.assertIn("budget_mismatch_observed", stale["reason_codes"])
        self.assertEqual(expired["health"], "blocked")
        self.assertEqual(expired["coverage"]["phase0"], "blocked")
        self.assertIn("budget_mismatch_observed", expired["reason_codes"])
        self.assertTrue(all(value is None for value in expired["phase_counts"].values()))

    async def test_10_combined_output_max_plus_one_terminates_and_reaps(self):
        raw = json.dumps(unavailable_payload()).encode()
        exact = raw + b" " * (aistack._LOCAL_DIRECT_HEALTH_MAX_BYTES - len(raw))
        proc = self.Proc(exact)
        deadline = aistack.time.monotonic() + 2.0
        self.assertEqual(len(await aistack._bounded_local_direct_output(proc, deadline)), len(exact))
        over = self.Proc(exact, b"x", running=True)
        with self.assertRaisesRegex(ValueError, "oversize"):
            await aistack._bounded_local_direct_output(over, deadline)
        await aistack._terminate_local_direct_child(over, deadline)
        self.assertTrue(over.waited)
        self.assertTrue(over.terminated or over.killed)

    async def test_11_cancelled_waiter_does_not_cancel_shared_refresh(self):
        result = unavailable_payload(); gate = asyncio.Event()
        async def refresh():
            await gate.wait(); return result
        with mock.patch.object(aistack, "_refresh_local_direct_health", side_effect=refresh) as call:
            first = asyncio.create_task(aistack.get_local_direct_health())
            second = asyncio.create_task(aistack.get_local_direct_health())
            await asyncio.sleep(0); first.cancel()
            with self.assertRaises(asyncio.CancelledError): await first
            gate.set(); self.assertEqual(await second, result)
        self.assertEqual(call.call_count, 1)

    async def test_12_validator_rejects_mixed_null_boolean_and_false_healthy(self):
        vectors = []
        mixed = healthy_payload(); mixed["active_deadline_count"] = None; vectors.append(mixed)
        boolean = healthy_payload(); boolean["phase_counts"]["queue"] = True; vectors.append(boolean)
        coverage = healthy_payload(); coverage["coverage"]["phase0"] = "unavailable"; vectors.append(coverage)
        anomaly = healthy_payload(); anomaly["stale_owner_count"] = 1; vectors.append(anomaly)
        for vector in vectors:
            self.assertFalse(aistack._local_direct_payload_valid(vector))

    async def test_13_numeric_boundary_and_schema_parity_matrix(self):
        schema = json.loads(SCHEMA.read_text())
        validator = Draft202012Validator(schema)
        self.assertTrue(aistack._local_direct_payload_valid(healthy_payload()))
        validator.validate(healthy_payload())
        scalar_limits = {
            "oldest_queue_age_s": 31_536_000,
            "oldest_prefill_age_s": 31_536_000,
            "oldest_generation_age_s": 31_536_000,
            "minimum_remaining_ms": 86_400_000,
            "active_deadline_count": 1_000_000,
        }
        for field, maximum in scalar_limits.items():
            accepted = healthy_payload(); accepted["health"] = "degraded"; accepted["reason_codes"] = ["source_stale"]
            accepted[field] = maximum
            self.assertTrue(aistack._local_direct_payload_valid(accepted), field)
            validator.validate(accepted)
            for bad in (maximum + 1, -1, True, float("inf")):
                rejected = json.loads(json.dumps(accepted)); rejected[field] = bad
                self.assertFalse(aistack._local_direct_payload_valid(rejected), (field, bad))
                self.assertTrue(list(validator.iter_errors(rejected)), (field, bad))

    async def test_14_refresh_cancellation_terminates_and_reaps_owned_child(self):
        proc = self.Proc(running=True)
        # Replace EOF-fed readers with open readers so refresh remains inside bounded reads.
        proc.stdout = asyncio.StreamReader(); proc.stderr = asyncio.StreamReader()
        with mock.patch.object(aistack.asyncio, "create_subprocess_exec", return_value=proc):
            task = asyncio.create_task(aistack._refresh_local_direct_health())
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(proc.waited)
        self.assertTrue(proc.terminated or proc.killed)

    async def test_15_unconfirmed_reap_is_an_integrity_failure(self):
        proc = self.Proc(running=True)
        async def never_wait():
            await asyncio.Event().wait()
        proc.wait = never_wait
        with self.assertRaisesRegex(RuntimeError, "local_direct_cleanup_unconfirmed"):
            await aistack._terminate_local_direct_child(proc, aistack.time.monotonic() + 0.01)

    async def test_16_deadline_boundaries_and_nonreturning_child_controls_are_bounded(self):
        deadline = 50.0
        with mock.patch.object(aistack.time, "monotonic", side_effect=[49.999, 50.0, 50.001]):
            self.assertGreater(aistack._local_direct_remaining(deadline), 0)
            with self.assertRaises(asyncio.TimeoutError):
                aistack._local_direct_remaining(deadline)
            with self.assertRaises(asyncio.TimeoutError):
                aistack._local_direct_remaining(deadline)

        terminate_hangs = self.Proc(running=True)
        terminate_hangs.terminate = lambda: threading.Event().wait()
        started = asyncio.get_running_loop().time()
        with self.assertRaisesRegex(RuntimeError, "local_direct_cleanup_unconfirmed"):
            await aistack._terminate_local_direct_child(
                terminate_hangs, aistack.time.monotonic() + 0.03,
            )
        self.assertLess(asyncio.get_running_loop().time() - started, 0.2)

        kill_hangs = self.Proc(running=True)
        kill_hangs.terminate = lambda: None
        async def wait_forever():
            await asyncio.Event().wait()
        kill_hangs.wait = wait_forever
        kill_hangs.kill = lambda: threading.Event().wait()
        started = asyncio.get_running_loop().time()
        with self.assertRaisesRegex(RuntimeError, "local_direct_cleanup_unconfirmed"):
            await aistack._terminate_local_direct_child(
                kill_hangs, aistack.time.monotonic() + 0.03,
            )
        self.assertLess(asyncio.get_running_loop().time() - started, 0.2)

    async def test_17_spawn_and_read_boundaries_consume_only_remaining_budget(self):
        async def never_spawn(*args, **kwargs):
            await asyncio.Event().wait()
        started = asyncio.get_running_loop().time()
        with mock.patch.object(aistack.asyncio, "create_subprocess_exec", side_effect=never_spawn), \
             mock.patch.object(aistack, "_local_direct_remaining", return_value=0.01):
            value = await aistack._refresh_local_direct_health()
        self.assertEqual(value["assessment"], "not_assessed")
        self.assertLess(asyncio.get_running_loop().time() - started, 0.2)

        proc = self.Proc(running=True)
        proc.stdout = asyncio.StreamReader()
        proc.stderr = asyncio.StreamReader()
        started = asyncio.get_running_loop().time()
        with mock.patch.object(aistack.asyncio, "create_subprocess_exec", return_value=proc), \
             mock.patch.object(aistack, "_local_direct_remaining", return_value=0.01):
            value = await aistack._refresh_local_direct_health()
        self.assertEqual(value["assessment"], "not_assessed")
        self.assertTrue(proc.waited)
        self.assertLess(asyncio.get_running_loop().time() - started, 0.2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
