import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_executor import LocalAgentExecutor, Task, TaskStatus


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class _FakeAsyncClient:
    responses = []
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        if not self.responses:
            raise AssertionError("No fake response configured")
        return self.responses.pop(0)


class LocalAgentExecutorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.executor = LocalAgentExecutor(enable_fallback=True)

    def test_select_remote_profile_prefers_reasoning_for_quality_critical(self):
        task = Task(
            id="quality-task",
            objective="analyze the routing design tradeoffs",
            quality_critical=True,
        )
        self.assertEqual(self.executor._select_remote_profile(task), "remote-reasoning")

    def test_select_remote_profile_prefers_coding_for_patch_work(self):
        task = Task(
            id="code-task",
            objective="implement a retry patch for the fallback path",
        )
        self.assertEqual(self.executor._select_remote_profile(task), "remote-coding")

    async def test_fallback_to_remote_uses_delegate_endpoint_before_query(self):
        import agent_executor as module

        task = Task(
            id="delegate-first",
            objective="implement a routing patch",
            context={"file": "agent_executor.py"},
        )

        original_client = module.httpx.AsyncClient
        fake_client = _FakeAsyncClient
        fake_client.calls = []
        fake_client.responses = [
            _FakeResponse(200, {"result": {"content": "delegated answer"}}),
        ]
        module.httpx.AsyncClient = fake_client
        try:
            result = await self.executor._fallback_to_remote(task)
        finally:
            module.httpx.AsyncClient = original_client

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.result, "delegated answer")
        self.assertEqual(len(fake_client.calls), 1)
        self.assertTrue(
            fake_client.calls[0]["url"].endswith("/control/ai-coordinator/delegate")
        )
        self.assertEqual(fake_client.calls[0]["json"]["profile"], "remote-coding")

    async def test_fallback_to_remote_uses_query_compatibility_path_after_delegate_failure(self):
        import agent_executor as module

        task = Task(
            id="compat-fallback",
            objective="summarize harness status",
            context={"service": "hybrid-coordinator"},
        )

        original_client = module.httpx.AsyncClient
        fake_client = _FakeAsyncClient
        fake_client.calls = []
        fake_client.responses = [
            _FakeResponse(503, {"error": "delegate unavailable"}),
            _FakeResponse(200, {"response": "query fallback answer"}),
        ]
        module.httpx.AsyncClient = fake_client
        try:
            result = await self.executor._fallback_to_remote(task)
        finally:
            module.httpx.AsyncClient = original_client

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.result, "query fallback answer")
        self.assertEqual(len(fake_client.calls), 2)
        self.assertTrue(fake_client.calls[1]["url"].endswith("/query"))


if __name__ == "__main__":
    unittest.main()
