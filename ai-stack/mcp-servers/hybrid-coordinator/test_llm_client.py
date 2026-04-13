import asyncio
import unittest
from unittest.mock import patch

from llm_client import LLMClient


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _RecordingAsyncClient:
    def __init__(self, response_payload):
        self.response_payload = response_payload
        self.calls = []

    async def post(self, url, headers=None, json=None):
        self.calls.append(
            {
                "url": url,
                "headers": headers or {},
                "json": json or {},
            }
        )
        return _FakeResponse(self.response_payload)


class LLMClientLocalTests(unittest.TestCase):
    def test_init_local_uses_switchboard_v1_base(self):
        with patch("llm_client.httpx.AsyncClient", return_value=_RecordingAsyncClient({})):
            with patch.dict("os.environ", {"SWITCHBOARD_URL": "http://127.0.0.1:8085"}, clear=False):
                client = LLMClient(provider="local")

        self.assertEqual(client.base_url, "http://127.0.0.1:8085/v1")
        self.assertEqual(client.local_profile, "continue-local")
        self.assertEqual(client.local_tool_profile, "local-tool-calling")

    def test_create_message_routes_local_prompt_via_continue_local(self):
        recorder = _RecordingAsyncClient(
            {
                "id": "chatcmpl-local",
                "model": "continue-local-model",
                "choices": [
                    {
                        "message": {"content": "LLM_CLIENT_OK"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 7,
                    "completion_tokens": 3,
                    "total_tokens": 10,
                },
            }
        )

        with patch("llm_client.httpx.AsyncClient", return_value=recorder):
            client = LLMClient(provider="local", base_url="http://switchboard.local")
            response = asyncio.run(
                client.create_message(
                    prompt="Reply with exactly LLM_CLIENT_OK",
                    system="Be exact.",
                    max_tokens=32,
                    temperature=0,
                )
            )

        self.assertEqual(response.content, "LLM_CLIENT_OK")
        self.assertEqual(response.usage["total_tokens"], 10)
        self.assertEqual(response.model, "continue-local-model")
        self.assertEqual(len(recorder.calls), 1)
        self.assertEqual(
            recorder.calls[0]["url"],
            "http://switchboard.local/v1/chat/completions",
        )
        self.assertEqual(
            recorder.calls[0]["headers"]["X-AI-Profile"],
            "continue-local",
        )
        self.assertEqual(
            recorder.calls[0]["json"]["messages"][0],
            {"role": "system", "content": "Be exact."},
        )

    def test_create_message_routes_tools_via_local_tool_calling(self):
        recorder = _RecordingAsyncClient(
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": "{\"path\":\"README.md\"}",
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 5,
                    "total_tokens": 16,
                },
            }
        )

        with patch("llm_client.httpx.AsyncClient", return_value=recorder):
            client = LLMClient(provider="local", base_url="http://switchboard.local/v1")
            response = asyncio.run(
                client.create_message(
                    prompt="Use a tool",
                    tools=[{"name": "read_file"}],
                    max_tokens=64,
                    temperature=0.1,
                )
            )

        self.assertEqual(response.stop_reason, "tool_calls")
        self.assertEqual(
            response.tool_calls,
            [{"id": "call_1", "name": "read_file", "input": {"path": "README.md"}}],
        )
        self.assertEqual(
            recorder.calls[0]["headers"]["X-AI-Profile"],
            "local-tool-calling",
        )
        self.assertEqual(
            recorder.calls[0]["json"]["tools"],
            [{"name": "read_file"}],
        )


if __name__ == "__main__":
    unittest.main()
