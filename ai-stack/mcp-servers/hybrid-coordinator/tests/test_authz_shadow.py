"""agent-auth AUTH-S2 (DESIGN 8.1): policy engine and shadow authorization. Hermetic."""

import copy
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from middleware import authz
from middleware.authz import Policy, PolicyError, create_authz_middleware, explain, load_policy, shadow_expired

POLICY_PATH = Path(__file__).resolve().parents[4] / "config" / "agent-auth-policy.json"


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy(str(POLICY_PATH))

    def test_hash_logged_and_set(self):
        self.assertEqual(len(self.policy.sha256), 64)

    def test_longest_prefix_wins(self):
        self.assertEqual(self.policy.match("POST", "/control/safety/gate")[0], "safety.tighten")
        self.assertEqual(self.policy.match("GET", "/control/safety/state")[0], "safety.read")
        self.assertEqual(self.policy.match("POST", "/control/safety/register-hook")[0], "safety.loosen")
        self.assertEqual(self.policy.match("GET", "/control/agents/x")[0], "orchestrate")
        self.assertEqual(self.policy.match("GET", "/control/whatever")[0], "read.status")

    def test_method_match(self):
        self.assertEqual(self.policy.match("POST", "/memory/store")[0], "memory.write")
        self.assertEqual(self.policy.match("GET", "/memory/recall")[0], "read.hints")
        self.assertEqual(self.policy.match("GET", "/control/ai-coordinator/status")[0], "read.status")
        self.assertEqual(self.policy.match("POST", "/control/ai-coordinator/delegate")[0], "orchestrate")

    def test_unknown_route_falls_to_admin_denied_for_non_owner(self):
        scope, prefix = self.policy.match("POST", "/definitely/not/a/route")
        self.assertEqual((scope, prefix), ("admin", ""))
        for cls in ("owner-agent", "legacy-loopback", "unknown"):
            self.assertFalse(self.policy.allows(cls, scope))
        self.assertTrue(self.policy.allows("api-key", scope))

    def test_public_paths(self):
        self.assertEqual(self.policy.match("GET", "/health")[0], "public")
        self.assertTrue(self.policy.allows("unknown", "public"))

    def test_legacy_loopback_research_would_deny(self):
        d = explain(self.policy, "POST", "/research/web/fetch", "legacy-loopback")
        self.assertEqual((d["scope"], d["decision"]), ("research.fetch", "would-deny"))
        self.assertIn("hint", d["guidance"])
        self.assertEqual(explain(self.policy, "POST", "/research/web/fetch", "owner-agent")["decision"], "allow")

    def test_validation_rejects_bad_policies(self):
        base = json.loads(POLICY_PATH.read_text())

        def mutated(fn):
            data = copy.deepcopy(base)
            fn(data)
            return data

        cases = {
            "scope without guidance": lambda d: d["scopes"]["qa.run"].pop("hint"),
            "rule undeclared scope": lambda d: d["rules"].append({"scope": "nope", "prefixes": ["/z"]}),
            "class undeclared scope": lambda d: d["classes"]["owner-agent"].append("nope"),
            "self_service not strict subset": lambda d: d.update(self_service={"p": list(d["classes"]["owner-agent"])}),
        }
        for name, fn in cases.items():
            with self.subTest(name), self.assertRaises(PolicyError):
                Policy(mutated(fn))
        Policy(mutated(lambda d: d.update(self_service={"p": ["read.hints"]})))

    def test_shadow_expiry(self):
        self.assertTrue(shadow_expired("shadow", "2026-01-01", date(2026, 1, 2)))
        self.assertFalse(shadow_expired("shadow", "2026-01-01", date(2026, 1, 1)))
        self.assertFalse(shadow_expired("off", "2026-01-01", date(2027, 1, 1)))
        self.assertFalse(shadow_expired("shadow", "garbage", date(2027, 1, 1)))


async def _ok(request):
    return web.json_response({"ok": True})


class ShadowMiddlewareTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.audit = os.path.join(self.tmp.name, "agent-auth.jsonl")
        authz.STATE.decisions.clear()
        authz.STATE.would_deny.clear()

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def _client(self, mode):
        app = web.Application(middlewares=[create_authz_middleware(
            policy=load_policy(str(POLICY_PATH)), mode=mode, audit_path=self.audit)])
        for path in ("/hints", "/research/web/fetch", "/nowhere", "/health"):
            app.router.add_route("*", path, _ok)
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        return client

    def _rows(self):
        if not os.path.exists(self.audit):
            return []
        return [json.loads(line) for line in Path(self.audit).read_text().splitlines()]

    async def test_shadow_never_blocks_and_flags_research_from_legacy(self):
        c = await self._client("shadow")
        r = await c.post("/research/web/fetch", json={})
        self.assertEqual(r.status, 200)
        hdr = r.headers["X-AQ-Would-Deny"]
        self.assertTrue(hdr.startswith("scope=research.fetch;id=d-"))
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["decision"], rows[0]["caller_class"], rows[0]["scope"]),
                         ("would-deny", "legacy-loopback", "research.fetch"))
        self.assertNotIn("authorization", json.dumps(rows[0]).lower())

    async def test_allowed_read_has_no_header_or_row(self):
        c = await self._client("shadow")
        r = await c.get("/hints")
        self.assertEqual(r.status, 200)
        self.assertNotIn("X-AQ-Would-Deny", r.headers)
        self.assertEqual(self._rows(), [])

    async def test_unknown_route_would_deny_for_legacy(self):
        c = await self._client("shadow")
        r = await c.post("/nowhere")
        self.assertIn("scope=admin", r.headers["X-AQ-Would-Deny"])

    async def test_off_is_passthrough(self):
        c = await self._client("off")
        r = await c.post("/research/web/fetch")
        self.assertEqual(r.status, 200)
        self.assertNotIn("X-AQ-Would-Deny", r.headers)
        self.assertEqual(self._rows(), [])

    async def test_enforce_mode_blocks_unauthorized_post(self):
        # Under AUTH-S5, enforce mode actively rejects unauthorized calls with 403
        c = await self._client("enforce")
        r = await c.post("/research/web/fetch")
        self.assertEqual(r.status, 403)
        body = await r.json()
        self.assertEqual(body.get("error"), "forbidden")
        self.assertEqual(body.get("reason"), "policy_denied")

    async def test_decision_error_never_500s(self):
        policy = load_policy(str(POLICY_PATH))

        def boom(method, path):
            raise RuntimeError("boom")

        policy.match = boom
        app = web.Application(middlewares=[create_authz_middleware(policy=policy, mode="shadow", audit_path=self.audit)])
        app.router.add_get("/hints", _ok)
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        before = authz.STATE.shadow_errors
        for _ in range(3):
            self.assertEqual((await client.get("/hints")).status, 200)
        self.assertEqual(authz.STATE.shadow_errors, before + 3)

    async def test_audit_write_failure_never_500s(self):
        bad = os.path.join(self.tmp.name, "dir-as-file")
        os.mkdir(bad)
        c = await self._client("shadow")  # policy ok
        app = web.Application(middlewares=[create_authz_middleware(
            policy=load_policy(str(POLICY_PATH)), mode="shadow", audit_path=bad)])
        app.router.add_route("*", "/research/web/fetch", _ok)
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        self.assertEqual((await client.post("/research/web/fetch")).status, 200)

    async def test_effective_mode_gauges_on_policy_degrade(self):
        os.environ["AQ_AGENT_AUTH_POLICY"] = os.path.join(self.tmp.name, "missing.json")
        self.addCleanup(os.environ.pop, "AQ_AGENT_AUTH_POLICY", None)
        create_authz_middleware(mode="shadow", audit_path=self.audit)
        snap = authz.STATE.snapshot()
        self.assertEqual((snap["configured_mode"], snap["mode"]), ("shadow", "off"))
        if authz.AUTH_EFFECTIVE_MODE is not None:
            self.assertEqual(authz.AUTH_EFFECTIVE_MODE.labels("shadow", "off")._value.get(), 1)
            self.assertEqual(authz.AUTH_POLICY_ERROR._value.get(), 1)
        create_authz_middleware(policy=load_policy(str(POLICY_PATH)), mode="shadow", audit_path=self.audit)
        self.assertEqual(authz.STATE.snapshot()["mode"], "shadow")
        if authz.AUTH_POLICY_ERROR is not None:
            self.assertEqual(authz.AUTH_POLICY_ERROR._value.get(), 0)

    async def test_missing_policy_degrades_to_off_not_crash(self):
        os.environ["AQ_AGENT_AUTH_POLICY"] = os.path.join(self.tmp.name, "missing.json")
        self.addCleanup(os.environ.pop, "AQ_AGENT_AUTH_POLICY", None)
        app = web.Application(middlewares=[create_authz_middleware(mode="shadow", audit_path=self.audit)])
        app.router.add_get("/hints", _ok)
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        self.assertEqual((await client.get("/hints")).status, 200)
        self.assertEqual(authz.STATE.mode, "off")
        self.assertTrue(authz.STATE.snapshot()["policy_error"])
        authz.STATE.policy_error = ""

    async def test_stats_snapshot(self):
        c = await self._client("shadow")
        await c.post("/research/web/fetch")
        await c.post("/research/web/fetch")
        snap = authz.STATE.snapshot()
        self.assertEqual(snap["would_deny"][0], {"caller_class": "legacy-loopback", "scope": "research.fetch", "count": 2})
        self.assertEqual(len(snap["policy_sha256"]), 64)

    async def test_admin_endpoints(self):
        app = web.Application()
        app.router.add_get("/admin/v1/auth/stats", authz.handle_auth_stats)
        app.router.add_get("/admin/v1/auth/explain", authz.handle_auth_explain)
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        authz.STATE.policy = load_policy(str(POLICY_PATH))
        self.assertEqual((await client.get("/admin/v1/auth/stats")).status, 200)
        r = await client.get("/admin/v1/auth/explain", params={"path": "/research/web/fetch", "method": "POST"})
        self.assertEqual((await r.json())["decision"], "would-deny")
        self.assertEqual((await client.get("/admin/v1/auth/explain")).status, 400)


if __name__ == "__main__":
    unittest.main()
