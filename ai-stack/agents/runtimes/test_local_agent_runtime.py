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


class _FakeProcess:
    def __init__(self, stdout=b"", stderr=b"", returncode=0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self.killed = False

    async def communicate(self):
        return self._stdout, self._stderr

    def kill(self):
        self.killed = True


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
    assert fake_client.post_calls[1]["json"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert state["fallback_backend"] == "llama.cpp"
    assert state["fallback_reason"] == "switchboard_timeout_or_unreachable"

def test_build_inference_payload_disables_thinking_when_runtime_is_off():
    module = _load_runtime(AGENT_THINKING_MODE="off")

    payload = module._build_inference_payload([{"role": "user", "content": "Answer briefly."}])

    assert payload["chat_template_kwargs"] == {"enable_thinking": False}


def test_build_inference_payload_omits_thinking_override_when_runtime_is_on():
    module = _load_runtime(AGENT_THINKING_MODE="on")

    payload = module._build_inference_payload([{"role": "user", "content": "Reason carefully."}])

    assert "chat_template_kwargs" not in payload


def test_run_streaming_falls_back_to_llama_when_switchboard_is_unreachable(monkeypatch):
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
    # Safely mock AsyncClient using monkeypatch
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: fake_client)
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


def test_run_reports_named_timeout_for_empty_timeout_exceptions(monkeypatch):
    module = _load_runtime()
    # Provide two timeouts: one for switchboard, one for the direct llama.cpp fallback
    fake_client = _FakeAsyncClient(post_plan=[httpx.ReadTimeout(""), httpx.ReadTimeout("")])
    
    # Safely mock AsyncClient using monkeypatch
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: fake_client)
    
    stdout = io.StringIO()
    stderr = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            asyncio.run(module.run())
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected local agent runtime to exit on timeout")

    payload = json.loads(stderr.getvalue().strip())
    assert payload["error"] == "local_agent_timeout"


def test_run_harness_cli_executes_aq_qa_with_json_default():
    module = _load_runtime(AGENT_TOOLS_ENABLED="true")
    calls = []

    async def _fake_create_subprocess_exec(*cmd, **kwargs):
        calls.append({"cmd": list(cmd), "kwargs": kwargs})
        return _FakeProcess(stdout=b'{"status":"ok","passed":41}', stderr=b"", returncode=0)

    module.asyncio.create_subprocess_exec = _fake_create_subprocess_exec
    module._build_cli_exec_env = lambda: {"PATH": "/test/bin"}

    result = asyncio.run(module._run_harness_cli("aq-qa", []))
    payload = json.loads(result)

    assert payload["tool"] == "aq-qa"
    assert payload["status"] == "ok"
    assert payload["parsed"]["passed"] == 41
    assert calls[0]["cmd"][1:] == ["0", "--json"]


def test_dispatch_tool_supports_feedback_loop_cli():
    module = _load_runtime(AGENT_TOOLS_ENABLED="true")

    async def _fake_run_harness_cli(tool, args):
        return json.dumps({"tool": tool, "args": args, "status": "ok"})

    module._run_harness_cli = _fake_run_harness_cli

    result = asyncio.run(
        module._dispatch_tool(
            _FakeAsyncClient(),
            "run_harness_cli",
            {"tool": "aq-feedback-loop", "args": ["--task", "inspect local agent state", "--format", "json"]},
        )
    )
    payload = json.loads(result)

    assert payload["tool"] == "aq-feedback-loop"
    assert payload["args"] == ["--task", "inspect local agent state", "--format", "json"]


def test_dispatch_tool_supports_context_manage_summary_cli():
    module = _load_runtime(AGENT_TOOLS_ENABLED="true")

    async def _fake_run_harness_cli(tool, args):
        return json.dumps({"tool": tool, "args": args, "status": "ok"})

    module._run_harness_cli = _fake_run_harness_cli

    result = asyncio.run(
        module._dispatch_tool(
            _FakeAsyncClient(),
            "run_harness_cli",
            {"tool": "aq-context-manage", "args": ["summary", "--task", "resume current slice", "--json"]},
        )
    )
    payload = json.loads(result)

    assert payload["tool"] == "aq-context-manage"
    assert payload["args"] == ["summary", "--task", "resume current slice", "--json"]


def test_run_harness_cli_rejects_unsafe_arguments():
    module = _load_runtime(AGENT_TOOLS_ENABLED="true")

    try:
        asyncio.run(module._run_harness_cli("aq-qa", ["0;rm -rf /"]))
    except ValueError as exc:
        assert "unsafe harness CLI argument" in str(exc) or "unsupported aq-qa phase" in str(exc)
    else:
        raise AssertionError("expected unsafe aq-qa argument to be rejected")


def test_validate_harness_cli_accepts_hints_and_context_summary():
    module = _load_runtime(AGENT_TOOLS_ENABLED="true")

    args, timeout_seconds = module._validate_harness_cli("aq-hints", ["resume local agent state", "--format=json", "--agent=codex"])
    assert args == ["resume local agent state", "--format=json", "--agent=codex"]
    assert timeout_seconds == 60.0

    args, timeout_seconds = module._validate_harness_cli("aq-context-manage", ["summary", "--task", "resume local agent state", "--json"])
    assert args == ["summary", "--task", "resume local agent state", "--json"]
    assert timeout_seconds == 90.0

    args, timeout_seconds = module._validate_harness_cli("aq-introspection-validate", ["--text", "Observed signals qa green and evidence sources aq qa 0 json", "--format=json"])
    assert args == ["--text", "Observed signals qa green and evidence sources aq qa 0 json", "--format=json"]
    assert timeout_seconds == 30.0


def test_phase_30_6_bootstrap_injection_constants_and_helper():
    module = _load_runtime(AGENT_INJECT_BOOTSTRAP="true", AGENT_BOOTSTRAP_TIMEOUT="20")
    
    assert isinstance(module.AGENT_INJECT_BOOTSTRAP, bool)
    assert module.AGENT_INJECT_BOOTSTRAP is True
    assert isinstance(module.BOOTSTRAP_TIMEOUT, float)
    assert module.BOOTSTRAP_TIMEOUT == 20.0
    
    # Verify helper does not raise and returns a string (likely empty in test env)
    res = module._run_bootstrap_preamble("test task")
    assert isinstance(res, str)


def test_compress_tool_output_truncates_long_output():
    module = _load_runtime()
    long = "x" * 2000
    compressed = module._compress_tool_output(long, max_chars=100)
    assert len(compressed) < 200  # allows for truncation notice overhead
    assert "truncated" in compressed


def test_compress_tool_output_passes_short_output():
    module = _load_runtime()
    short = "hello world"
    assert module._compress_tool_output(short, max_chars=100) == short
