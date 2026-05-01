#!/usr/bin/env python3

import asyncio
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path

import httpx


MODULE_PATH = Path(__file__).with_name("local_agent_runtime.py")


def _load_runtime(**env_overrides):
    env_defaults = {
        "AGENT_ID": "test-agent",
        "AGENT_ROLE": "coder",
        "AGENT_SYSTEM_PROMPT": "You are a local runtime.",
        "AGENT_TASK": "Answer briefly.",
        "AGENT_STATE_FILE": "",
        "AGENT_MAX_TOKENS": "64",
        "AGENT_TEMPERATURE": "0",
        "AGENT_TIMEOUT": "15",
        "AGENT_THINKING_MODE": "off",
        "AGENT_NO_THINK_PREFIX": "",
        "AGENT_STOP_SEQUENCES": json.dumps(["<stop>"]),
        "AGENT_TOOLS_ENABLED": "false",
        "AGENT_MAX_TOOL_ROUNDS": "1",
        "AGENT_STREAMING": "false",
        "SWITCHBOARD_URL": "http://switchboard.test",
        "LLAMA_CPP_URL": "http://llama.test",
        "HYBRID_URL": "http://hybrid.test",
    }
    env_defaults.update(env_overrides)
    previous = {key: os.environ.get(key) for key in env_defaults}
    try:
        for key, value in env_defaults.items():
            os.environ[key] = value
        spec = importlib.util.spec_from_file_location(
            f"local_agent_runtime_test_{os.urandom(4).hex()}",
            MODULE_PATH,
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}",
                request=httpx.Request("POST", "http://test"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self._payload


class _FakeStreamResponse:
    def __init__(self, lines, status_code=200):
        self._lines = list(lines)
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}",
                request=httpx.Request("POST", "http://test"),
                response=httpx.Response(self.status_code),
            )

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamContext:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAsyncClient:
    def __init__(self, *, post_plan=None, stream_plan=None):
        self.post_plan = list(post_plan or [])
        self.stream_plan = list(stream_plan or [])
        self.post_calls = []
        self.stream_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None, headers=None, timeout=None):
        self.post_calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        action = self.post_plan.pop(0)
        if isinstance(action, Exception):
            raise action
        return action

    def stream(self, method, url, json=None, headers=None):
        self.stream_calls.append({"method": method, "url": url, "json": json, "headers": headers})
        action = self.stream_plan.pop(0)
        if isinstance(action, Exception):
            raise action
        return _FakeStreamContext(action)


def test_post_completion_falls_back_to_llama_and_strips_tool_payload():
    module = _load_runtime(AGENT_TOOLS_ENABLED="true")
    fake_client = _FakeAsyncClient(
        post_plan=[
            httpx.ConnectError("switchboard unavailable"),
            _FakeResponse({"choices": [{"message": {"content": "fallback answer"}, "finish_reason": "stop"}]}),
        ]
    )
    state = {"id": "test-agent"}

    response = asyncio.run(
        module._post_completion_with_fallback(
            fake_client,
            payload=module._build_inference_payload([{"role": "user", "content": "Use tools"}]),
            headers={"X-AI-Profile": "local-tool-calling", "X-AI-Route": "local"},
            state=state,
        )
    )

    assert response.json()["choices"][0]["message"]["content"] == "fallback answer"
    assert fake_client.post_calls[0]["url"] == "http://switchboard.test/v1/chat/completions"
    assert fake_client.post_calls[1]["url"] == "http://llama.test/v1/chat/completions"
    assert fake_client.post_calls[1]["headers"] == {}
    assert "tools" not in fake_client.post_calls[1]["json"]
    assert "tool_choice" not in fake_client.post_calls[1]["json"]
    assert state["fallback_backend"] == "llama.cpp"
    assert state["fallback_reason"] == "switchboard_unreachable"


def test_run_streaming_falls_back_to_llama_when_switchboard_is_unreachable():
    module = _load_runtime(AGENT_STREAMING="true")
    fake_client = _FakeAsyncClient(
        stream_plan=[
            httpx.ConnectError("switchboard unavailable"),
            _FakeStreamResponse(
                [
                    'data: {"choices":[{"delta":{"content":"hello "},"finish_reason":null}]}',
                    'data: {"choices":[{"delta":{"content":"world"},"finish_reason":null}]}',
                    "data: [DONE]",
                ]
            ),
        ]
    )
    module.httpx.AsyncClient = lambda timeout: fake_client
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        asyncio.run(module.run())

    lines = [json.loads(line) for line in stdout.getvalue().strip().splitlines()]
    assert lines[0] == {"t": "hello ", "done": False}
    assert lines[1] == {"t": "world", "done": False}
    assert lines[-1]["ok"] is True
    assert lines[-1]["content"] == "hello world"
    assert fake_client.stream_calls[0]["url"] == "http://switchboard.test/v1/chat/completions"
    assert fake_client.stream_calls[1]["url"] == "http://llama.test/v1/chat/completions"
    assert fake_client.stream_calls[1]["headers"] == {}

