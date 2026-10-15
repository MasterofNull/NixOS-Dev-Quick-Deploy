"""AUTH-S0: Host/Origin/content-type guard (middleware/http_guard.py).

Hermetic: in-process aiohttp app, no network beyond the loopback test server.
"""

import base64
import json
import logging
import os
import unittest
from unittest import mock

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from middleware.http_guard import create_http_guard_middleware

PORT = "8003"  # logical service port; rebound to the test server port in setUp


async def _ok(request):
    return web.json_response({"ok": True})


class HttpGuardTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        env = {"MCP_SERVER_PORT": PORT, "AQ_COORD_HTTP_GUARD": "enforce"}
        self._env = mock.patch.dict(os.environ, env)
        self._env.start()
        for k in ("AQ_COORD_ALLOWED_HOSTS", "AQ_COORD_ALLOWED_ORIGINS"):
            os.environ.pop(k, None)
        app = web.Application(middlewares=[create_http_guard_middleware()])
        app.router.add_get("/hints", _ok)
        app.router.add_post("/memory/store", _ok)
        app.router.add_get("/ws", self._ws)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        os.environ["MCP_SERVER_PORT"] = str(self.client.port)
        self.port = self.client.port

    @staticmethod
    async def _ws(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.close()
        return ws

    async def asyncTearDown(self):
        await self.client.close()
        self._env.stop()

    async def _req(self, method, path, **kw):
        r = await self.client.request(method, path, **kw)
        return r.status, await r.text()

    async def test_evil_host_rejected(self):
        status, body = await self._req("GET", "/hints", headers={"Host": "evil.example.com"})
        self.assertEqual(status, 421)
        data = json.loads(body)
        self.assertEqual(data["error"], "host_not_allowed")
        self.assertTrue(data["hint"])

    async def test_loopback_hosts_accepted(self):
        for host in ("127.0.0.1", "localhost", f"127.0.0.1:{self.port}", f"localhost:{self.port}", f"[::1]:{self.port}", "[::1]"):
            status, _ = await self._req("GET", "/hints", headers={"Host": host})
            self.assertEqual(status, 200, host)

    async def test_loopback_name_wrong_port_rejected(self):
        status, _ = await self._req("GET", "/hints", headers={"Host": "localhost:1"})
        self.assertEqual(status, 421)

    async def test_extra_host_allowed_via_env(self):
        with mock.patch.dict(os.environ, {"AQ_COORD_ALLOWED_HOSTS": "nixos.lan:8003"}):
            status, _ = await self._req("GET", "/hints", headers={"Host": "nixos.lan:8003"})
        self.assertEqual(status, 200)

    async def test_evil_origin_post_rejected(self):
        status, body = await self._req(
            "POST", "/memory/store", data="{}",
            headers={"Origin": "http://evil.example.com", "Content-Type": "application/json"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["error"], "origin_not_allowed")

    async def test_evil_origin_get_rejected(self):
        status, _ = await self._req("GET", "/hints", headers={"Origin": "null"})
        self.assertEqual(status, 403)

    async def test_own_loopback_origin_allowed(self):
        status, _ = await self._req(
            "POST", "/memory/store", data="{}",
            headers={"Origin": f"http://127.0.0.1:{self.port}", "Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)

    async def test_no_origin_json_post_accepted(self):
        status, _ = await self._req("POST", "/memory/store", json={"a": 1})
        self.assertEqual(status, 200)

    async def test_text_plain_post_rejected(self):
        status, body = await self._req(
            "POST", "/memory/store", data='{"a":1}', headers={"Content-Type": "text/plain"})
        self.assertEqual(status, 415)
        self.assertEqual(json.loads(body)["error"], "content_type_not_json")

    async def test_form_post_rejected(self):
        status, _ = await self._req("POST", "/memory/store", data={"a": "1"})
        self.assertEqual(status, 415)

    async def test_bodyless_post_allowed(self):
        status, _ = await self._req("POST", "/memory/store")
        self.assertEqual(status, 200)

    async def test_sec_fetch_cross_site_post_rejected(self):
        status, body = await self._req("POST", "/memory/store", json={},
                                       headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["error"], "cross_site_request")

    async def test_shadow_logs_but_allows(self):
        with mock.patch.dict(os.environ, {"AQ_COORD_HTTP_GUARD": "shadow"}):
            with self.assertLogs("hybrid-coordinator.http_guard", level=logging.WARNING) as cm:
                status, _ = await self._req("GET", "/hints", headers={"Host": "evil.example.com"})
        self.assertEqual(status, 200)
        joined = "\n".join(cm.output)
        self.assertIn("would_reject", joined)
        self.assertIn("reason=host_not_allowed", joined)
        self.assertIn("evil.example.com", joined)

    async def test_enforce_logs_rejection(self):
        with self.assertLogs("hybrid-coordinator.http_guard", level=logging.WARNING) as cm:
            await self._req("GET", "/hints", headers={"Host": "evil.example.com"})
        self.assertIn("rejected reason=host_not_allowed method=GET path=/hints", "\n".join(cm.output))

    async def test_off_allows_everything(self):
        with mock.patch.dict(os.environ, {"AQ_COORD_HTTP_GUARD": "off"}):
            status, _ = await self._req(
                "POST", "/memory/store", data="x",
                headers={"Host": "evil.example.com", "Origin": "http://evil.example.com",
                         "Content-Type": "text/plain", "Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 200)

    async def test_invalid_mode_fails_closed(self):
        with mock.patch.dict(os.environ, {"AQ_COORD_HTTP_GUARD": "bogus"}):
            status, _ = await self._req("GET", "/hints", headers={"Host": "evil.example.com"})
        self.assertEqual(status, 421)

    async def test_noncanonical_hosts_rejected(self):
        for host in ("localhost.", "127.0.0.1.", "[::ffff:127.0.0.1]", "127.1", "2130706433"):
            status, _ = await self._req("GET", "/hints", headers={"Host": host})
            self.assertEqual(status, 421, host)

    async def test_empty_port_host_allowed(self):
        status, _ = await self._req("GET", "/hints", headers={"Host": "localhost:"})
        self.assertEqual(status, 200)

    async def test_chunked_text_plain_post_rejected(self):
        async def gen():
            yield b'{"a":'
            yield b'1}'
        status, _ = await self._req("POST", "/memory/store", data=gen(),
                                    headers={"Content-Type": "text/plain"})
        self.assertEqual(status, 415)

    async def test_noncanonical_origin_rejected(self):
        for origin in (f"HTTP://127.0.0.1:{self.port}/", f"http://127.0.0.1:{self.port}/",
                       f"HTTP://127.0.0.1:{self.port}"):
            status, _ = await self._req("GET", "/hints", headers={"Origin": origin})
            self.assertEqual(status, 403, origin)

    async def test_ambiguous_content_types_rejected(self):
        for ctype in ("application/json, text/plain", "text/plain; application/json"):
            status, _ = await self._req("POST", "/memory/store", data="{}",
                                        headers={"Content-Type": ctype})
            self.assertEqual(status, 415, ctype)

    async def test_websocket_foreign_origin_rejected(self):
        r = await self.client.request("GET", "/ws", headers={
            "Origin": "http://evil.example.com", "Connection": "Upgrade", "Upgrade": "websocket",
            "Sec-WebSocket-Version": "13", "Sec-WebSocket-Key": base64.b64encode(os.urandom(16)).decode()})
        self.assertEqual(r.status, 403)

    async def test_websocket_no_origin_upgrades(self):
        ws = await self.client.ws_connect("/ws")
        await ws.close()

    async def test_sec_fetch_cross_site_get_rejected(self):
        status, _ = await self._req("GET", "/hints", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 403)

    async def test_sec_fetch_same_origin_and_none_allowed(self):
        for v in ("same-origin", "same-site", "none"):
            status, _ = await self._req("GET", "/hints", headers={"Sec-Fetch-Site": v})
            self.assertEqual(status, 200, v)

    async def test_startup_warning_in_shadow_and_off(self):
        for mode in ("shadow", "off"):
            with mock.patch.dict(os.environ, {"AQ_COORD_HTTP_GUARD": mode}):
                with self.assertLogs("hybrid-coordinator.http_guard", level=logging.WARNING) as cm:
                    create_http_guard_middleware()
            self.assertIn(f"mode={mode}", "\n".join(cm.output))

    async def test_no_startup_warning_in_enforce(self):
        with self.assertNoLogs("hybrid-coordinator.http_guard", level=logging.WARNING):
            create_http_guard_middleware()

    async def test_unknown_port_fails_closed_at_startup(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MCP_SERVER_PORT", None)
            os.environ.pop("PORT", None)
            with self.assertRaises(RuntimeError):
                create_http_guard_middleware()
            os.environ["AQ_COORD_HTTP_GUARD"] = "off"
            create_http_guard_middleware()  # explicit kill switch still starts


if __name__ == "__main__":
    unittest.main()
