"""
dispatch — Single Python entry point for all local task delegation.

Phase 74D — replaces run_direct / run_hybrid / run_ralph inline Python heredocs
in the old 674-line delegate-to-local bash script.

All runners use build_llama_payload() from shared/llm_config.py (SSOT).
Role injection is consistent across modes via the system-message path.

Usage (called by the delegate-to-local bash shim):
    python3 dispatch.py delegate --task-id ID --output FILE --mode MODE \\
        --role ROLE --prompt TEXT --timeout N --max-tokens N \\
        --delegation-dir DIR --llama-url URL --hybrid-url URL --ralph-url URL \\
        --script-dir DIR

    python3 dispatch.py list       --delegation-dir DIR
    python3 dispatch.py status ID  --delegation-dir DIR
    python3 dispatch.py check  ID  --delegation-dir DIR
    python3 dispatch.py cancel ID  --delegation-dir DIR
    python3 dispatch.py kill-all   --delegation-dir DIR
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

# ── path: shared/llm_config.py ───────────────────────────────────────────────
# dispatch.py lives at scripts/ai/lib/dispatch.py
# REPO_ROOT = scripts/ai/lib/../../.. = repo root
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent.parent
_SHARED = _REPO_ROOT / "ai-stack" / "mcp-servers" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

try:
    from llm_config import build_llama_payload, AGENT_TASK_MAX_TOKENS  # type: ignore
except ImportError:
    # Fallback: inline minimal implementation so dispatch works even when
    # the shared module path isn't resolvable (e.g. test environments).
    AGENT_TASK_MAX_TOKENS = 1200

    def build_llama_payload(messages, *, max_tokens=None, temperature=None,
                             stream=False, role=None, task_type=None, **extra):  # type: ignore
        # Inline fallback: minimal task_type profile support.
        # Mirrors the TASK_PROFILES in shared/llm_config.py.
        _FALLBACK_PROFILES = {
            "structured": {"temperature": 0.0,  "frequency_penalty": 0.0,  "enable_thinking": False},
            "lookup":     {"temperature": 0.1,  "frequency_penalty": 0.0,  "enable_thinking": False},
            "code":       {"temperature": 0.15, "frequency_penalty": 0.0,  "enable_thinking": False},
            "reasoning":  {"temperature": 0.5,  "frequency_penalty": 0.05, "enable_thinking": False},
            "agent":      {"temperature": 0.3,  "frequency_penalty": 0.0,  "enable_thinking": False},
        }
        _profile = _FALLBACK_PROFILES.get(task_type or "code", _FALLBACK_PROFILES["code"])
        _max = max_tokens or int(os.environ.get("LLAMA_MAX_TOKENS", str(AGENT_TASK_MAX_TOKENS)))
        _temperature = temperature if temperature is not None else _profile["temperature"]
        _freq_penalty = extra.pop("frequency_penalty", _profile["frequency_penalty"])
        _enable_thinking = _profile["enable_thinking"]
        msgs = list(messages)
        if role:
            _role_prompts = {
                "orchestrator": "[Role: orchestrator] Open/close sessions, assign slices, accept work, commit integration. You may route other agents.",
                "architect":    "[Role: architect] Draft architecture docs, flag risks, write PRDs. Requires orchestrator review before commit.",
                "implementer":  "[Role: implementer] Execute assigned slice only. Validate output. Propose commit. Do not re-scope goals.",
                "reviewer":     "[Role: reviewer] Explicit pass/fail verdict against criteria. Do not review your own work.",
            }
            prefix = _role_prompts.get(role, "")
            if prefix:
                sys_idx = next((i for i, m in enumerate(msgs) if m.get("role") == "system"), None)
                if sys_idx is not None:
                    msgs[sys_idx] = {"role": "system", "content": prefix + "\n\n" + msgs[sys_idx]["content"]}
                else:
                    msgs.insert(0, {"role": "system", "content": prefix})
        payload = {
            "messages": msgs,
            "temperature": _temperature,
            "max_tokens": _max,
            "chat_template_kwargs": {"enable_thinking": _enable_thinking},
            "repeat_penalty": 1.08,
            "repeat_last_n": 64,
            "frequency_penalty": _freq_penalty,
            "stream_options": {"include_usage": True},
        }
        if stream:
            payload["stream"] = True
        payload.update(extra)
        return payload


from task_config import TaskConfig  # type: ignore  # noqa: E402
from task_registry import TaskRegistry  # type: ignore  # noqa: E402
from slot_scheduler import wait_for_slot  # type: ignore  # noqa: E402


# ── Phase 163: local inference budget + visibility ───────────────────────────
# Calibration constant for timeout scaling in direct-mode tasks.
# At 1.0 tok/s (Renoir APU measured floor), a 1200-tok task needs ≥1260s.
# Override via env: LOCAL_TOK_PER_SEC=1.5 delegate-to-local --task-id ...
_LOCAL_TOK_PER_SEC = float(os.environ.get("LOCAL_TOK_PER_SEC", "1.0"))


def _scale_timeout(explicit_timeout: int, max_tokens: int) -> int:
    """Compute timeout from token budget so long tasks aren't killed prematurely.

    Formula: max(explicit_timeout, ceil(max_tokens / LOCAL_TOK_PER_SEC) + 60)
    The 60s headroom covers connection setup and final SSE flush.

    Only applied to direct-mode llama.cpp tasks — HybridRunner / RalphRunner /
    AgentRunner manage their own timeouts independent of token budgets.
    """
    computed = math.ceil(max_tokens / _LOCAL_TOK_PER_SEC) + 60
    return max(explicit_timeout, computed)


def _write_progress(
    progress_file: Path,
    tokens_out: int,
    max_tokens: int,
    elapsed_s: float,
    tok_per_sec: float,
    eta_s: Optional[float],
    status: str,
) -> None:
    """Atomically update a .progress.json sidecar for dispatch.py watch to read.

    Uses write-then-rename so readers never see a partial file.
    Silently no-ops on any I/O error — never blocks the main inference path.
    """
    data: dict = {
        "status": status,
        "tokens_out": tokens_out,
        "max_tokens": max_tokens,
        "elapsed_s": round(elapsed_s, 1),
        "tok_per_sec": round(tok_per_sec, 2),
    }
    if eta_s is not None:
        data["eta_s"] = round(eta_s, 0)
    try:
        tmp = progress_file.with_suffix(".progress.tmp")
        tmp.write_text(json.dumps(data))
        tmp.rename(progress_file)
    except Exception:
        pass


# ── training telemetry ────────────────────────────────────────────────────────

_TELEMETRY_DIR = Path(os.environ.get("TELEMETRY_DIR", "/var/lib/ai-stack/hybrid/telemetry"))
_HYBRID_EVENTS = _TELEMETRY_DIR / "hybrid-events.jsonl"
# User-writable spool for agent_step_complete events emitted by delegate-to-local.
# The service telemetry dir is owned by the systemd user — user-space dispatches
# write here instead. training_ingest.py reads both paths.
_USER_EVENTS_SPOOL = _HERE.parent.parent.parent / ".agents" / "telemetry" / "hybrid-events.jsonl"


def _emit_training_event(
    query: str,
    response: str,
    tokens_in: int,
    tokens_out: int,
    role: Optional[str],
) -> None:
    """Append an agent_step_complete event so training_ingest.py can pick it up.

    Writes to the service telemetry dir when writable (systemd context), otherwise
    falls back to the user-space spool at .agents/telemetry/hybrid-events.jsonl.
    training_ingest.py reads both paths.
    """
    if not response:
        return
    import datetime
    event = json.dumps({
        "event_type": "agent_step_complete",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "query": query,
        "response": response,
        "latency_ms": tokens_out * 600 if tokens_out else 1000,  # ~600ms/tok estimate
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "role": role,
        "source": "delegate-direct",
    })
    # Try service telemetry dir first (production), fall back to user spool.
    targets = [_HYBRID_EVENTS, _USER_EVENTS_SPOOL]
    for target in targets:
        # Skip only when parent exists but isn't writable — we can't create it.
        # When parent is absent, attempt mkdir inside the try block.
        if target.parent.exists() and not os.access(str(target.parent), os.W_OK):
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "a", encoding="utf-8") as fh:
                fh.write(event + "\n")
            return
        except Exception:
            continue


# ── token budget heuristic ───────────────────────────────────────────────────

_TINY_SIGNALS   = frozenset(["one-liner", "one line", "one sentence", "briefly",
                              "in one word", "yes or no", "true or false", "reply with",
                              "respond with exactly", "say:", "ping"])
_SMALL_SIGNALS  = frozenset(["one paragraph", "short answer", "briefly explain",
                              "summarize in", "list 3", "list three", "list 5",
                              "list five", "in 2-3 sentences", "concisely"])
_LARGE_SIGNALS  = frozenset([
    "full implementation", "complete the", "write all",
    "implement the entire", "detailed analysis", "comprehensive review",
    "multi-step", "full plan", "write a script", "write a function",
    # design / prd / report tasks — these require full document output
    "design document", "design doc", "produce a complete", "opinionated design",
    "complete design", "full design", "expert review", "architecture review",
    "complete report", "full report", "detailed report", "map every",
    "all sections", "every file", "every section", "phase 8",
])


def classify_tokens(prompt: str, mode: str = "direct") -> Optional[int]:
    """Return a suggested max_tokens budget from prompt size signals.

    Returns None to defer to the env-var / mode-default chain in task_config.
    Only overrides when the prompt contains explicit size signals.

    Budget tiers (at ~1-2 tok/s on Renoir APU):
      tiny  : 150   — one-liners, pings, yes/no, exact-reply tasks
      small : 400   — paragraph, short list, brief summary
      large : 4096  — full implementation, design docs, detailed analysis
      none  : None  — no signal detected; defer to DIRECT_MAX_TOKENS env → mode default

    IMPORTANT: Returns None when no signal is present so that an explicit
    DIRECT_MAX_TOKENS env var (set by the caller) is honoured rather than
    being silently overridden by a hardcoded 800-token default.
    """
    p = prompt.lower()
    if any(k in p for k in _TINY_SIGNALS):
        return 150
    if any(k in p for k in _SMALL_SIGNALS):
        return 400
    if any(k in p for k in _LARGE_SIGNALS):
        return 4096
    # No signal detected — return None so task_config reads DIRECT_MAX_TOKENS
    # or falls back to the mode default (direct=4096).  Never hard-code 800
    # here: that caps design-doc tasks without the caller knowing.
    return None


# ── Phase 74E: mode auto-selection ───────────────────────────────────────────

_AGENT_KEYWORDS = frozenset([
    "create file", "edit file", "write file", "delete file",
    "git commit", "git add", "git push", "commit ", "push branch",
    "run tests", "run the test", "execute ", "install ", "write to file",
])
_HYBRID_KEYWORDS = frozenset([
    "what is the current", "current state", "current status",
    "retrieve from", "search for", "look up", "rag ", " rag?",
    "what does the codebase", "find in the repo",
])
_RALPH_KEYWORDS = frozenset([
    "return as json", "output as json", "json schema", "structured output",
    "strict format", "output format:", "respond with json",
])


def classify_mode(prompt: str) -> str:
    """Auto-select dispatch mode from prompt intent heuristics (Phase 74E).

    Priority: ralph > agent > hybrid > direct.
    Errors toward direct (fastest) — only escalates when clear signals present.

    Examples:
        classify_mode("Write a sort function") -> "direct"
        classify_mode("What is the current hybrid-coordinator status?") -> "hybrid"
        classify_mode("Create file main.py and add this code") -> "agent"
        classify_mode("Return the config as JSON schema") -> "ralph"
    """
    p = prompt.lower()
    if any(k in p for k in _RALPH_KEYWORDS):
        return "ralph"
    if any(k in p for k in _AGENT_KEYWORDS):
        return "agent"
    if any(k in p for k in _HYBRID_KEYWORDS):
        return "hybrid"
    return "direct"


# ── Phase 162: task-type auto-classification ──────────────────────────────────
# Separate from mode classification: mode = WHERE to route, task_type = HOW to
# configure the payload (temperature, frequency_penalty, enable_thinking).

_TASK_REASONING_SIGNALS = frozenset([
    "analyze", "architect", "design document", "design doc",
    "explain why", "compare and contrast", "compare the",
    "tradeoff", "trade-off", "evaluate ", "investigate",
    "diagnose", "recommend", "advise ", "what are the implications",
    "what is the impact", "security audit", "architectural review",
    "architectural", "design decision", "assess the",
    "explain the difference", "why does ", "pros and cons",
])

_TASK_CODE_SIGNALS = frozenset([
    "implement", "write a function", "write code", "write a script",
    "write the ", "fix the", "fix a ", "refactor", "add feature",
    "add method", "create module", "debug ", "write test",
    "add endpoint", "create class", "build the ", "add the ",
])


def classify_task_type(prompt: str, mode: str = "direct") -> str:
    """Map prompt + dispatch mode to a modal task profile name (Phase 162).

    Profiles: structured, lookup, code, reasoning, agent
    Mode-driven overrides take priority over keyword matching.
    Defaults to 'code' when no signal is detected (most common direct task).

    Examples:
        classify_task_type("Return as JSON", "direct")           -> "structured"
        classify_task_type("Analyze the architecture", "direct") -> "reasoning"
        classify_task_type("Write a function to sort", "direct") -> "code"
        classify_task_type("yes or no", "direct")                -> "lookup"
        classify_task_type("any prompt", "ralph")                -> "structured"
        classify_task_type("any prompt", "agent")                -> "agent"
    """
    if mode == "ralph":
        return "structured"
    if mode == "agent":
        return "agent"
    p = prompt.lower()
    if any(k in p for k in _RALPH_KEYWORDS):
        return "structured"
    if any(k in p for k in _TINY_SIGNALS):
        return "lookup"
    if any(k in p for k in _TASK_REASONING_SIGNALS):
        return "reasoning"
    if any(k in p for k in _TASK_CODE_SIGNALS):
        return "code"
    return "code"


# ── harness grounding supplement ─────────────────────────────────────────────

_GROUNDING_FILE = Path(os.environ.get(
    "HARNESS_GROUNDING_FILE",
    str(_REPO_ROOT / "config" / "local-agent-grounding.md"),
))

def _load_grounding() -> str:
    """Load harness grounding supplement from file. Returns '' if absent."""
    try:
        return _GROUNDING_FILE.read_text().strip()
    except OSError:
        return ""

def _prepend_grounding(messages: list, config) -> list:  # type: ignore[type-arg]
    """Insert grounding as a system message if the grounding file exists.

    Safe to call even when file is absent — returns messages unchanged.
    If a system message already exists (e.g. from role injection), the grounding
    is prepended to it rather than inserted as a second system message.
    """
    grounding = _load_grounding()
    if not grounding:
        return messages
    msgs = list(messages)
    sys_idx = next((i for i, m in enumerate(msgs) if m.get("role") == "system"), None)
    if sys_idx is not None:
        msgs[sys_idx] = {
            "role": "system",
            "content": grounding + "\n\n" + msgs[sys_idx]["content"],
        }
    else:
        msgs.insert(0, {"role": "system", "content": grounding})
    return msgs

def _augment_prompt_with_grounding(prompt: str) -> str:
    """Prepend grounding text to a prompt string (used by AgentRunner --task path)."""
    grounding = _load_grounding()
    if not grounding:
        return prompt
    return f"[HARNESS CONTEXT]\n{grounding}\n[/HARNESS CONTEXT]\n\n{prompt}"


# ── runners ──────────────────────────────────────────────────────────────────

class DirectRunner:
    """POST directly to llama.cpp /v1/chat/completions with SSE streaming.

    Uses build_llama_payload() — role injected into system message.
    Slot pre-poll via slot_scheduler.wait_for_slot().
    """

    def run(self, config: TaskConfig, prompt: str, output_file: Path) -> bool:
        """Return True on success, False on failure. Writes result to output_file.

        Phase 163: incremental writes — each SSE content chunk is written and
        flushed immediately so observers (dispatch.py watch, tail -f) see output
        in real time rather than waiting for the full response to complete.
        A .progress.json sidecar is updated every 10 tokens for live metrics.
        """
        wait_for_slot(config.llama_url, config.timeout_secs)

        messages = _prepend_grounding([], config)
        messages.append({"role": "user", "content": prompt})
        payload = build_llama_payload(
            messages,
            max_tokens=config.max_tokens,
            stream=True,
            role=config.role,
            task_type=config.task_type,
        )

        req = urllib.request.Request(
            f"{config.llama_url}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        progress_file = Path(str(output_file) + ".progress.json")
        _start = time.monotonic()

        try:
            with urllib.request.urlopen(req, timeout=config.timeout_secs) as resp:
                tokens_in = tokens_out = 0
                _stream_toks = 0  # content-chunk count; proxy for tokens_out mid-stream
                resp.fp.raw._sock.settimeout(config.timeout_secs)
                # Phase 163: open file at stream start — write each content chunk
                # immediately so tail -f / dispatch.py watch sees live output.
                with open(output_file, "w", encoding="utf-8") as out_fh:
                    for raw_line in resp:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            # Usage chunk (include_usage=True) has choices:[] — independent
                            choices = chunk.get("choices") or []
                            if choices:
                                content = choices[0].get("delta", {}).get("content", "")
                                if content:
                                    out_fh.write(content)
                                    out_fh.flush()
                                    _stream_toks += 1
                            usage = chunk.get("usage") or {}
                            if usage:
                                tokens_in = usage.get("prompt_tokens", tokens_in)
                                tokens_out = usage.get("completion_tokens", tokens_out)
                            # Progress sidecar: update every 10 content tokens
                            if _stream_toks > 0 and _stream_toks % 10 == 0:
                                elapsed = time.monotonic() - _start
                                tps = _stream_toks / elapsed if elapsed > 0 else 0.0
                                eta = (config.max_tokens - _stream_toks) / tps if tps > 0 else None
                                _write_progress(progress_file, _stream_toks, config.max_tokens,
                                                elapsed, tps, eta, "running")
                        except (json.JSONDecodeError, KeyError):
                            pass

            final_toks = tokens_out or _stream_toks
            elapsed = time.monotonic() - _start
            tps = final_toks / elapsed if elapsed > 0 and final_toks > 0 else 0.0
            _write_progress(progress_file, final_toks, config.max_tokens, elapsed, tps, None, "done")

            result = output_file.read_text() if output_file.exists() else ""
            if tokens_in or final_toks:
                Path(str(output_file) + ".usage.json").write_text(
                    json.dumps({"tokens_in": tokens_in, "tokens_out": final_toks})
                )
            # Emit agent_step_complete to feed training ingest pipeline.
            _emit_training_event(prompt, result, tokens_in, final_toks, config.role)
            return True

        except urllib.error.HTTPError as e:
            elapsed = time.monotonic() - _start
            _write_progress(progress_file, 0, config.max_tokens, elapsed, 0.0, None, "failed")
            output_file.write_text(f"HTTP {e.code}: {e.read().decode()}")
            return False
        except Exception as e:
            elapsed = time.monotonic() - _start
            _write_progress(progress_file, 0, config.max_tokens, elapsed, 0.0, None, "failed")
            # Preserve any partial output that streamed before the failure
            if output_file.exists() and output_file.stat().st_size > 0:
                try:
                    with open(output_file, "a", encoding="utf-8") as fh:
                        fh.write(f"\n\n[Error: {e}]")
                except Exception:
                    pass
            else:
                output_file.write_text(f"Error: {e}")
            return False


class HybridRunner:
    """POST to hybrid-coordinator /query. Role passed in request body."""

    def run(self, config: TaskConfig, prompt: str, output_file: Path) -> bool:
        payload = json.dumps({
            "query": prompt,
            "mode": "auto",
            "prefer_local": True,
            "limit": 1,
            "role": config.role,
        }).encode()
        req = urllib.request.Request(
            f"{config.hybrid_url}/query",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=config.timeout_secs) as resp:
                data = json.loads(resp.read().decode())
                result = (
                    data.get("response") or data.get("answer")
                    or data.get("result") or json.dumps(data, indent=2)
                )
                output_file.write_text(result)
                usage = data.get("usage") or data.get("token_usage") or {}
                if usage:
                    Path(str(output_file) + ".usage.json").write_text(json.dumps({
                        "tokens_in":  usage.get("prompt_tokens") or usage.get("input_tokens"),
                        "tokens_out": usage.get("completion_tokens") or usage.get("output_tokens"),
                    }))
            return True
        except urllib.error.HTTPError as e:
            output_file.write_text(f"HTTP {e.code}: {e.read().decode()}")
            return False
        except Exception as e:
            output_file.write_text(f"Error: {e}")
            return False


class RalphRunner:
    """POST to ralph-wiggum /task endpoint."""

    def run(self, config: TaskConfig, prompt: str, output_file: Path) -> bool:
        payload = json.dumps({"prompt": prompt}).encode()
        req = urllib.request.Request(
            f"{config.ralph_url}/task",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=config.timeout_secs) as resp:
                data = json.loads(resp.read().decode())
                result = (
                    data.get("response") or data.get("result")
                    or json.dumps(data, indent=2)
                )
                output_file.write_text(result)
            return True
        except urllib.error.HTTPError as e:
            output_file.write_text(f"HTTP {e.code}: {e.read().decode()}")
            return False
        except Exception as e:
            output_file.write_text(f"Error: {e}")
            return False


# _AGENT_WALL_CLOCK_SECS: hard-cap override. When set, this overrides the
# dynamic computation. Used for ops/debug. Default: 0 (= use dynamic formula).
_AGENT_WALL_CLOCK_OVERRIDE = int(os.environ.get("AGENT_WALL_CLOCK_SECS", "0"))

# RUNAWAY_HARD_CAP: absolute maximum wall-clock for any agent task (3 hours).
# Prevents true runaway agents from holding a slot indefinitely. Any task
# exceeding this is considered a runaway and terminated.
_RUNAWAY_HARD_CAP_SECS = 10800


def _compute_agent_wall_clock(timeout_secs: int, max_calls: int) -> int:
    """Compute dynamic wall-clock timeout for an agent task.

    Scales with max_calls and chunk_timeout so each call has time to complete
    one full prefill + generation cycle without being killed prematurely.

    Formula:
      chunk_timeout = max(900, timeout_secs × 2)   (silence before per-call timeout)
      gen_budget    = 1200s                          (AGENT_TASK_MAX_TOKENS / 1 tok/s floor)
      per_call      = chunk_timeout + gen_budget
      wall_clock    = min(per_call × max_calls + 120, RUNAWAY_HARD_CAP_SECS)

    The env var AGENT_WALL_CLOCK_SECS overrides this calculation when non-zero.
    """
    if _AGENT_WALL_CLOCK_OVERRIDE > 0:
        return _AGENT_WALL_CLOCK_OVERRIDE
    chunk_timeout = max(900.0, timeout_secs * 2)
    per_call = chunk_timeout + 1200  # worst-case prefill silence + generation
    computed = int(per_call * max_calls) + 120
    return min(computed, _RUNAWAY_HARD_CAP_SECS)


class AgentRunner:
    """Delegate to aq-agent-loop (keeps its own Python entry point)."""

    def __init__(self, script_dir: Path):
        self.agent_loop = script_dir / "aq-agent-loop"

    def run(self, config: TaskConfig, prompt: str, output_file: Path,
            max_calls: int = 50) -> bool:
        if not self.agent_loop.exists():
            output_file.write_text(f"Error: aq-agent-loop not found at {self.agent_loop}")
            return False
        wall_clock = _compute_agent_wall_clock(config.timeout_secs, max_calls)
        grounded_prompt = _augment_prompt_with_grounding(prompt)
        cmd = [
            sys.executable, str(self.agent_loop),
            "--task", grounded_prompt,
            "--output", str(output_file),
            "--timeout", str(config.timeout_secs),
            "--max-calls", str(max_calls),
            "--role", config.role,
        ]
        if getattr(config, "tool_manifest", "full") != "full":
            cmd += ["--tool-manifest", config.tool_manifest]
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            if not output_file.exists():
                output_file.write_text(
                    "Agent task started; waiting for aq-agent-loop output.\n",
                    encoding="utf-8",
                )
            _write_progress(
                Path(str(output_file) + ".progress.json"),
                tokens_out=0,
                max_tokens=config.max_tokens,
                elapsed_s=0.0,
                tok_per_sec=0.0,
                eta_s=None,
                status="agent-loop-started",
            )
            result = subprocess.run(cmd, timeout=wall_clock)
            return result.returncode == 0
        except subprocess.TimeoutExpired as _te:
            # Include last-known progress state in the timeout message for debugging.
            # The progress sidecar is written after each tool call by aq-agent-loop.
            progress_path = Path(str(output_file) + ".progress.json")
            progress_snippet = ""
            try:
                progress_snippet = f"\nLast progress: {progress_path.read_text()[:400]}"
            except Exception:
                pass
            output_file.write_text(
                f"Agent wall-clock timeout after {wall_clock}s "
                f"(dynamic: {max_calls} calls × {config.timeout_secs}s timeout)."
                f"{progress_snippet}"
            )
            return False


# ── service check ─────────────────────────────────────────────────────────────

def _service_ok(url: str, name: str) -> bool:
    """Return True if GET <url>/health returns 200."""
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


# ── embedded-assist pre-context ──────────────────────────────────────────────

def _detect_code_lang(prompt: str) -> str:
    """Return primary code language detected from prompt keywords, or '' for general."""
    p = prompt[:400].lower()
    if any(k in p for k in ("nix ", ".nix", "nixos", "flake", "pkgs.", "lib.", "mkmodule")):
        return "nix"
    if any(k in p for k in ("def ", "class ", "import ", "async def", ".py", "python")):
        return "python"
    if any(k in p for k in ("#!/bin/bash", "#!/usr/bin/env bash", ".sh", "systemd", "nixos-rebuild")):
        return "bash"
    return ""


def _embedded_assist_prefetch(prompt: str, switchboard_url: str, timeout: float = 8.0) -> str:
    """Query embedded-assist for relevant skill/pattern context before main inference.

    Makes a compact call to the switchboard with the embedded-assist profile.
    Returns a formatted context block, or "" on any failure (never blocks main task).

    Called automatically when mode="direct" to inject coding pattern context.
    Short timeout (8s) — if the model is busy, we skip and proceed without.
    """
    if not switchboard_url:
        return ""
    lang = _detect_code_lang(prompt)
    prompt_lower = prompt[:300].lower()
    is_debug = any(k in prompt_lower for k in ("debug", "error", "traceback", "fail", "broken", "fix"))
    if is_debug:
        lang_hint = f" ({lang.upper()} context)" if lang else ""
        query = (
            f"For this debugging task{lang_hint}: state (1) the most likely root cause and (2) the first diagnostic step. "
            f"≤80 words:\n{prompt[:200]}"
        )
    elif lang:
        query = (
            f"For this {lang.upper()} task: state (1) the critical constraint to respect and (2) the first concrete step. "
            f"≤80 words:\n{prompt[:200]}"
        )
    else:
        query = (
            f"Identify 2 critical rules or patterns most relevant to this task. "
            f"Be concise (≤80 words total):\n{prompt[:200]}"
        )
    # Switchboard forces stream=True for local targets regardless of the request value.
    # Send stream=True explicitly so is_stream is set before the override, ensuring a
    # proper SSE response that we can parse line-by-line (not truncated 2-chunk SSE).
    payload = {
        "messages": [{"role": "user", "content": query}],
        "max_tokens": 120,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "frequency_penalty": 0.0,
    }
    try:
        req = urllib.request.Request(
            f"{switchboard_url}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "X-AI-Profile": "embedded-assist",
                "X-AI-Route": "local",
            },
            method="POST",
        )
        chunks: list[str] = []
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        chunks.append(content)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
        text = "".join(chunks).strip()
        if not text:
            return ""
        return f"[embedded-assist context]\n{text}\n[/embedded-assist context]\n\n"
    except Exception:
        return ""


# ── code validation ───────────────────────────────────────────────────────────

def _validate_code_blocks(result_text: str) -> str:
    """Extract and syntax-validate Python and Bash code blocks from result.

    Returns a compact validation report appended to the output, or "".
    Uses py_compile for Python blocks and bash -n for Bash blocks.
    """
    import re, tempfile
    lines = result_text.splitlines()
    blocks: list[tuple[str, str]] = []
    in_block = False
    lang = ""
    buf: list[str] = []

    for line in lines:
        if not in_block:
            m = re.match(r"^```(\w+)", line)
            if m:
                lang = m.group(1).lower()
                in_block = True
                buf = []
        else:
            if line.startswith("```"):
                if buf:
                    blocks.append((lang, "\n".join(buf)))
                in_block = False
                buf = []
                lang = ""
            else:
                buf.append(line)

    if not blocks:
        return ""

    reports: list[str] = []
    for lang, code in blocks:
        if lang in ("python", "py"):
            with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
                f.write(code)
                fname = f.name
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", fname],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode != 0:
                    err = (result.stderr or "unknown error").strip()[:200]
                    reports.append(f"Python syntax ERROR: {err}")
                else:
                    reports.append("Python syntax: OK")
            except Exception as e:
                reports.append(f"Python syntax check failed: {e}")
            finally:
                Path(fname).unlink(missing_ok=True)
        elif lang in ("bash", "sh", "shell"):
            with tempfile.NamedTemporaryFile(suffix=".sh", mode="w", delete=False) as f:
                f.write(code)
                fname = f.name
            try:
                result = subprocess.run(
                    ["bash", "-n", fname],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode != 0:
                    err = (result.stderr or "unknown error").strip()[:200]
                    reports.append(f"Bash syntax ERROR: {err}")
                else:
                    reports.append("Bash syntax: OK")
            except Exception as e:
                reports.append(f"Bash syntax check failed: {e}")
            finally:
                Path(fname).unlink(missing_ok=True)
        elif lang == "nix":
            with tempfile.NamedTemporaryFile(suffix=".nix", mode="w", delete=False) as f:
                f.write(code)
                fname = f.name
            try:
                result = subprocess.run(
                    ["nix-instantiate", "--parse", fname],
                    capture_output=True, text=True, timeout=8,
                )
                if result.returncode != 0:
                    err = (result.stderr or "unknown error").strip()[:200]
                    reports.append(f"Nix syntax ERROR: {err}")
                else:
                    reports.append("Nix syntax: OK")
            except FileNotFoundError:
                pass  # nix-instantiate not available, skip silently
            except Exception as e:
                reports.append(f"Nix syntax check failed: {e}")
            finally:
                Path(fname).unlink(missing_ok=True)

    if not reports:
        return ""
    return "\n\n---\n[code-validation]\n" + "\n".join(reports) + "\n[/code-validation]"


# ── dispatch core ─────────────────────────────────────────────────────────────

def dispatch_task(
    config: TaskConfig,
    prompt: str,
    task_id: str,
    output_file: Path,
    registry: TaskRegistry,
    script_dir: Path,
    pre_registered: bool = False,
    max_calls: int = 50,
) -> bool:
    """Run a task: registry append → service check → runner → registry update.

    Returns True on success, False on failure.
    Writes result (or error text) to output_file regardless of outcome.

    pre_registered: if True, skip the initial registry.append / record_dispatch
    (caller already wrote them before any blocking operation).
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if not pre_registered:
        # Registry: append running entry with our own PID
        registry.append(
            task_id=task_id,
            description=prompt,
            output_file=str(output_file),
            mode=config.mode,
            role=config.role,
            pid=os.getpid(),
        )
        # Cross-session persistence
        registry.record_dispatch(
            task_id=task_id,
            agent=f"local-{config.mode}",
            output_file=str(output_file),
            objective=prompt,
        )

    # Service availability pre-check
    _service_urls = {
        "direct": (config.llama_url,  "llama.cpp"),
        "ralph":  (config.ralph_url,  "ralph-wiggum"),
        "hybrid": (config.hybrid_url, "hybrid-coordinator"),
        "agent":  (config.llama_url,  "llama.cpp"),
    }
    url, svc_name = _service_urls[config.mode]
    if not _service_ok(url, svc_name):
        msg = f"Error: {svc_name} is not reachable at {url}/health"
        output_file.write_text(msg)
        registry.update_status(task_id, "failed")
        registry.record_completion(task_id, "failed")
        return False

    # Embedded-assist pre-context for direct/coding tasks.
    # Makes a short embedded-assist call to inject relevant skill/pattern context
    # before the main inference. Skips gracefully if switchboard is unavailable.
    swb_url = os.environ.get("SWITCHBOARD_URL", "http://127.0.0.1:8085")
    if config.mode == "direct":
        ea_context = _embedded_assist_prefetch(prompt, swb_url)
        if ea_context:
            prompt = ea_context + prompt

    # Select and run runner
    runners = {
        "direct": DirectRunner(),
        "hybrid": HybridRunner(),
        "ralph":  RalphRunner(),
        "agent":  AgentRunner(script_dir),
    }
    runner = runners[config.mode]
    _run_kwargs = {"max_calls": max_calls} if config.mode == "agent" else {}
    success = runner.run(config, prompt, output_file, **_run_kwargs)

    # Code validation: append syntax check report to output for direct-mode tasks.
    if success and config.mode == "direct" and output_file.exists():
        try:
            result_text = output_file.read_text()
            validation = _validate_code_blocks(result_text)
            if validation:
                output_file.write_text(result_text + validation)
        except Exception:
            pass

    # Update token usage sidecar if present
    usage_file = Path(str(output_file) + ".usage.json")
    if usage_file.exists():
        try:
            usage = json.loads(usage_file.read_text())
            registry.update_tokens(
                task_id,
                usage.get("tokens_in"),
                usage.get("tokens_out"),
            )
            usage_file.unlink(missing_ok=True)
        except Exception:
            pass

    status = "done" if success else "failed"
    registry.update_status(task_id, status)
    registry.record_completion(task_id, status)
    return success


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dispatch.py")
    sub = parser.add_subparsers(dest="subcmd", required=True)

    # delegate subcommand
    d = sub.add_parser("delegate", help="Dispatch a local task")
    d.add_argument("--task-id",       required=True)
    d.add_argument("--output",        required=True)
    d.add_argument("--mode",          default="auto",
                   choices=["auto", "agent", "hybrid", "direct", "ralph"],
                   help="Routing mode; 'auto' runs classify_mode() heuristic (default)")
    d.add_argument("--task-type",     default=None,
                   choices=["auto", "structured", "lookup", "code", "reasoning", "agent"],
                   help="Modal payload profile; None/'auto' runs classify_task_type() (default)")
    d.add_argument("--role",          required=True)
    d.add_argument("--prompt",        required=True)
    d.add_argument("--timeout",       type=int, default=300)
    d.add_argument("--max-tokens",    type=int, default=None)
    d.add_argument("--max-calls",     type=int, default=50,
                   help="Max tool calls for agent mode [default: 50]")
    d.add_argument("--tool-manifest", default="full",
                   choices=["full", "self-improvement"],
                   help="Tool set for agent mode: 'full' (29 tools) or 'self-improvement' (6 tools) [default: full]")
    d.add_argument("--delegation-dir", required=True)
    d.add_argument("--llama-url",     default="http://127.0.0.1:8080")
    d.add_argument("--hybrid-url",    default="http://127.0.0.1:8003")
    d.add_argument("--ralph-url",     default="http://127.0.0.1:8004")
    d.add_argument("--script-dir",    default=None)

    # subcommands that act on the registry
    for name in ("list", "kill-all"):
        p = sub.add_parser(name)
        p.add_argument("--delegation-dir", required=True)

    for name in ("status", "check", "cancel"):
        p = sub.add_parser(name)
        p.add_argument("task_id")
        p.add_argument("--delegation-dir", required=True)

    # watch subcommand — Phase 163: live tail of running task output + progress
    w = sub.add_parser("watch", help="Tail a running task with live progress metrics")
    w.add_argument("task_id")
    w.add_argument("--delegation-dir", required=True)
    w.add_argument("--interval", type=float, default=2.0,
                   help="Poll interval in seconds (default: 2)")

    return parser


def _cmd_watch(args: argparse.Namespace) -> int:
    """Phase 163: tail a running dispatch task with live progress metrics.

    Polls the output file for new content and the .progress.json sidecar for
    metrics. Exits when the task reaches done/failed status. Ctrl-C detaches
    cleanly without killing the background task.
    """
    delegation_dir = Path(args.delegation_dir)
    registry = TaskRegistry(delegation_dir)
    entry = registry.get(args.task_id)
    if not entry:
        print(f"Task {args.task_id!r} not found in registry.", file=sys.stderr)
        return 1

    output_path_str = entry.get("output_file", "")
    output_path = Path(output_path_str) if output_path_str else None
    progress_path = Path(str(output_path) + ".progress.json") if output_path else None
    interval = getattr(args, "interval", 2.0)
    pos = 0  # byte position in output file (tracks new bytes to display)

    print(f"[watch] task={args.task_id}", flush=True)
    if output_path:
        print(f"[watch] output={output_path}", flush=True)
    print("[watch] Ctrl-C to detach (task keeps running)", flush=True)
    print("-" * 60, flush=True)

    try:
        while True:
            # Stream new output
            if output_path and output_path.exists():
                try:
                    with open(output_path, "rb") as f:
                        f.seek(pos)
                        new_bytes = f.read()
                    if new_bytes:
                        sys.stdout.write(new_bytes.decode("utf-8", errors="replace"))
                        sys.stdout.flush()
                        pos += len(new_bytes)
                except Exception:
                    pass

            # Read progress sidecar
            prog = None
            if progress_path and progress_path.exists():
                try:
                    prog = json.loads(progress_path.read_text())
                except Exception:
                    pass

            status = "unknown"
            if prog:
                status = prog.get("status", "unknown")
                toks = prog.get("tokens_out", 0)
                max_t = prog.get("max_tokens", 0)
                pct = f"{100 * toks // max_t}%" if max_t else "?%"
                elapsed = prog.get("elapsed_s", 0)
                tps = prog.get("tok_per_sec", 0)
                eta = prog.get("eta_s")
                eta_str = f"  eta={int(eta)}s" if eta else ""
                print(
                    f"\n[progress] {status}  {toks}/{max_t} tok ({pct})"
                    f"  elapsed={elapsed:.0f}s  {tps:.1f} tok/s{eta_str}",
                    flush=True,
                )
            else:
                # Fall back to registry status when sidecar not yet created
                entry = registry.get(args.task_id)
                if entry:
                    status = entry.get("status", "unknown")

            if status in ("done", "failed"):
                print(f"\n[watch] complete: {status}", flush=True)
                return 0 if status == "done" else 1

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[watch] detached — task still running", flush=True)
        return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    delegation_dir = Path(args.delegation_dir)
    registry = TaskRegistry(delegation_dir)

    if args.subcmd == "list":
        registry.cmd_list()
        return 0

    if args.subcmd == "kill-all":
        return registry.cmd_kill_all()

    if args.subcmd == "status":
        return registry.cmd_status(args.task_id)

    if args.subcmd == "check":
        return registry.cmd_check(args.task_id)

    if args.subcmd == "cancel":
        return registry.cmd_cancel(args.task_id)

    if args.subcmd == "watch":
        return _cmd_watch(args)

    # delegate subcommand
    assert args.subcmd == "delegate"

    resolved_mode = classify_mode(args.prompt) if args.mode == "auto" else args.mode
    # Token budget resolution:
    #   1. Explicit --max-tokens CLI flag → absolute override
    #   2. classify_tokens() signal match (tiny/small/large) → task-appropriate budget
    #   3. None from classify_tokens → TaskConfig reads DIRECT_MAX_TOKENS env var
    #   4. Phase 163: profile max_tokens_hint → inserted before mode-global 4096 default
    # DIRECT_MAX_TOKENS=8192 set by the caller shell is always honoured (step 3 > step 4).
    resolved_tokens = args.max_tokens if args.max_tokens is not None \
        else classify_tokens(args.prompt, resolved_mode)
    # resolved_tokens=None means TaskConfig._resolve_tokens() will read env vars.

    # Phase 162: modal task profile — auto-classify if not explicitly provided.
    _cli_task_type = getattr(args, "task_type", None)
    resolved_task_type = (
        classify_task_type(args.prompt, resolved_mode)
        if (not _cli_task_type or _cli_task_type == "auto")
        else _cli_task_type
    )

    # Phase 163: fetch profile max_tokens_hint when no explicit/signal budget.
    # Falls back to None if llm_config import fails (keeps legacy chain intact).
    _tokens_hint: Optional[int] = None
    if resolved_tokens is None:
        try:
            from llm_config import get_task_profile as _gtp  # type: ignore
            _ph = _gtp(resolved_task_type)
            _tokens_hint = _ph.max_tokens_hint if _ph else None
        except Exception:
            pass

    config = TaskConfig.from_args(
        mode=resolved_mode,
        role=args.role,
        timeout_secs=args.timeout,
        max_tokens=resolved_tokens,
        llama_url=args.llama_url,
        hybrid_url=args.hybrid_url,
        ralph_url=args.ralph_url,
        task_type=resolved_task_type,
        max_tokens_hint=_tokens_hint,
        tool_manifest=getattr(args, "tool_manifest", "full"),
    )
    # Phase 163: scale timeout from token budget for direct-mode tasks.
    # Fixed 300s was killing code/reasoning tasks at ~300 tokens — half a function.
    if resolved_mode == "direct":
        config.timeout_secs = _scale_timeout(args.timeout, config.max_tokens)

    script_dir = Path(args.script_dir) if args.script_dir else _HERE.parent
    output_file = Path(args.output)

    # Phase 159: pre-register before any blocking operation so the task ID is
    # always retrievable via --status/--check even if dispatch_task() crashes
    # or the background process is OOM-killed before reaching registry.append().
    output_file.parent.mkdir(parents=True, exist_ok=True)
    registry.append(
        task_id=args.task_id,
        description=args.prompt,
        output_file=str(output_file),
        mode=resolved_mode,
        role=config.role,
        pid=os.getpid(),
    )
    registry.record_dispatch(
        task_id=args.task_id,
        agent=f"local-{resolved_mode}",
        output_file=str(output_file),
        objective=args.prompt,
    )
    # Phase 162: emit task_type + suggested_remote_profile to the output header
    # so orchestrators can see which switchboard profile to use for equivalent
    # remote delegations.
    try:
        from llm_config import get_task_profile  # type: ignore
        _profile = get_task_profile(resolved_task_type)
        if _profile:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            _header_file = output_file.with_suffix(".profile.json")
            import json as _json
            _header_file.write_text(_json.dumps({
                "task_type": resolved_task_type,
                "suggested_remote_profile": _profile.suggested_remote_profile,
                "temperature": _profile.temperature,
                "enable_thinking": _profile.enable_thinking,
            }))
    except Exception:
        pass

    success = dispatch_task(
        config=config,
        prompt=args.prompt,
        task_id=args.task_id,
        output_file=output_file,
        registry=registry,
        script_dir=script_dir,
        pre_registered=True,
        max_calls=getattr(args, "max_calls", 50),
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
