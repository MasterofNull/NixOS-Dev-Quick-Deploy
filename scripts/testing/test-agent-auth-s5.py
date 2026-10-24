#!/usr/bin/env python3
"""
Unit tests for AUTH-S5 (Enforcement per family, guided deny bodies, lockdown mode).
"""

import os
import sys
import tempfile
import unittest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

# Environment setup
os.environ["AI_STRICT_ENV"] = "false"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ai-stack", "mcp-servers", "hybrid-coordinator")))

import middleware.authz as authz
from middleware.auth import AUTH_CONTEXT_KEY


class TestAgentAuthS5Enforce(AioHTTPTestCase):
    async def get_application(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        audit_file = os.path.join(self.tmpdir.name, "audit.jsonl")

        app = web.Application()

        async def handle_get(req):
            return web.json_response({"status": "ok", "method": "GET"})

        async def handle_post(req):
            return web.json_response({"status": "ok", "method": "POST"})

        app.router.add_get("/hints", handle_get)
        app.router.add_post("/memory/store", handle_post)
        app.router.add_post("/workflow/run/start", handle_post)

        @web.middleware
        async def inject_caller(request, handler):
            request[AUTH_CONTEXT_KEY] = {"mode": "loopback"}
            return await handler(request)

        mw = authz.create_authz_middleware(mode="enforce", audit_path=audit_file)
        app.middlewares.append(inject_caller)
        app.middlewares.append(mw)
        return app

    async def asyncTearDown(self):
        await super().asyncTearDown()
        self.tmpdir.cleanup()

    async def test_enforce_allows_sanctioned_route(self):
        resp = await self.client.get("/hints")
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data.get("status"), "ok")

    async def test_enforce_denies_restricted_route_with_guided_deny(self):
        resp = await self.client.post("/workflow/run/start")
        self.assertEqual(resp.status, 403)
        data = await resp.json()
        self.assertEqual(data.get("error"), "forbidden")
        self.assertEqual(data.get("reason"), "policy_denied")
        self.assertIn("guided_deny", data)
        self.assertIn("why", data["guided_deny"])


class TestAgentAuthS5Lockdown(AioHTTPTestCase):
    async def get_application(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        audit_file = os.path.join(self.tmpdir.name, "audit.jsonl")

        app = web.Application()

        async def handle_get(req):
            return web.json_response({"status": "ok"})

        async def handle_post(req):
            return web.json_response({"status": "ok"})

        app.router.add_get("/health", handle_get)
        app.router.add_post("/memory/store", handle_post)

        @web.middleware
        async def inject_caller(request, handler):
            request[AUTH_CONTEXT_KEY] = {"mode": "loopback"}
            return await handler(request)

        mw = authz.create_authz_middleware(mode="lockdown", audit_path=audit_file)
        app.middlewares.append(inject_caller)
        app.middlewares.append(mw)
        return app

    async def asyncTearDown(self):
        await super().asyncTearDown()
        self.tmpdir.cleanup()

    async def test_lockdown_allows_reads(self):
        resp = await self.client.get("/health")
        self.assertEqual(resp.status, 200)

    async def test_lockdown_blocks_writes(self):
        resp = await self.client.post("/memory/store")
        self.assertEqual(resp.status, 403)
        data = await resp.json()
        self.assertEqual(data.get("reason"), "lockdown_active")
        self.assertIn("guided_deny", data)


if __name__ == "__main__":
    unittest.main()
