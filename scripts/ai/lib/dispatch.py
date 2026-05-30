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

    def build_llama_payload(messages, *, max_tokens=None, temperature=0.3,
                             stream=False, role=None, **extra):  # type: ignore
        _max = max_tokens or int(os.environ.get("LLAMA_MAX_TOKENS", str(AGENT_TASK_MAX_TOKENS)))
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
            "temperature": temperature,
            "max_tokens": _max,
            "chat_template_kwargs": {"enable_thinking": False},
            # Anti-loop guardrails: penalise token repetition so the model
            # doesn't get stuck cycling the same phrase.  Values are mild —
            # enough to prevent runaway loops without distorting reasoning.
            "repeat_penalty": 1.08,
            "repeat_last_n": 64,
            "frequency_penalty": 0.05,
            # Always request usage stats so callers can observe actual spend.
            "stream_options": {"include_usage": True},
        }
        if stream:
            payload["stream"] = True
        payload.update(extra)
        return payload


from task_config import TaskConfig  # type: ignore  # noqa: E402
from task_registry import TaskRegistry  # type: ignore  # noqa: E402
from slot_scheduler import wait_for_slot  # type: ignore  # noqa: E402


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
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
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


# ── runners ──────────────────────────────────────────────────────────────────

class DirectRunner:
    """POST directly to llama.cpp /v1/chat/completions with SSE streaming.

    Uses build_llama_payload() — role injected into system message.
    Slot pre-poll via slot_scheduler.wait_for_slot().
    """

    def run(self, config: TaskConfig, prompt: str, output_file: Path) -> bool:
        """Return True on success, False on failure. Writes result to output_file."""
        wait_for_slot(config.llama_url, config.timeout_secs)

        messages = [{"role": "user", "content": prompt}]
        payload = build_llama_payload(
            messages,
            max_tokens=config.max_tokens,
            stream=True,
            role=config.role,
        )

        req = urllib.request.Request(
            f"{config.llama_url}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=config.timeout_secs) as resp:
                full_text: list[str] = []
                tokens_in = tokens_out = 0
                # After first byte we have the slot; switch to per-line timeout
                resp.fp.raw._sock.settimeout(config.timeout_secs)
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        # Usage chunk (include_usage=True) has choices:[] — handle independently
                        choices = chunk.get("choices") or []
                        if choices:
                            content = choices[0].get("delta", {}).get("content", "")
                            if content:
                                full_text.append(content)
                        usage = chunk.get("usage") or {}
                        if usage:
                            tokens_in = usage.get("prompt_tokens", tokens_in)
                            tokens_out = usage.get("completion_tokens", tokens_out)
                    except (json.JSONDecodeError, KeyError):
                        pass

            result = "".join(full_text)
            output_file.write_text(result)
            if tokens_in or tokens_out:
                Path(str(output_file) + ".usage.json").write_text(
                    json.dumps({"tokens_in": tokens_in, "tokens_out": tokens_out})
                )
            # Emit agent_step_complete to feed training ingest pipeline.
            # training_ingest.py reads this event type from hybrid-events.jsonl;
            # without it samples_added stays 0 for direct-mode dispatches.
            _emit_training_event(prompt, result, tokens_in, tokens_out, config.role)
            return True

        except urllib.error.HTTPError as e:
            output_file.write_text(f"HTTP {e.code}: {e.read().decode()}")
            return False
        except Exception as e:
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


class AgentRunner:
    """Delegate to aq-agent-loop (keeps its own Python entry point)."""

    def __init__(self, script_dir: Path):
        self.agent_loop = script_dir / "aq-agent-loop"

    def run(self, config: TaskConfig, prompt: str, output_file: Path) -> bool:
        if not self.agent_loop.exists():
            output_file.write_text(f"Error: aq-agent-loop not found at {self.agent_loop}")
            return False
        cmd = [
            sys.executable, str(self.agent_loop),
            "--task", prompt,
            "--output", str(output_file),
            "--timeout", str(config.timeout_secs),
            "--role", config.role,
        ]
        result = subprocess.run(cmd)
        return result.returncode == 0


# ── service check ─────────────────────────────────────────────────────────────

def _service_ok(url: str, name: str) -> bool:
    """Return True if GET <url>/health returns 200."""
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


# ── dispatch core ─────────────────────────────────────────────────────────────

def dispatch_task(
    config: TaskConfig,
    prompt: str,
    task_id: str,
    output_file: Path,
    registry: TaskRegistry,
    script_dir: Path,
) -> bool:
    """Run a task: registry append → service check → runner → registry update.

    Returns True on success, False on failure.
    Writes result (or error text) to output_file regardless of outcome.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

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

    # Select and run runner
    runners = {
        "direct": DirectRunner(),
        "hybrid": HybridRunner(),
        "ralph":  RalphRunner(),
        "agent":  AgentRunner(script_dir),
    }
    runner = runners[config.mode]
    success = runner.run(config, prompt, output_file)

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
    d.add_argument("--role",          required=True)
    d.add_argument("--prompt",        required=True)
    d.add_argument("--timeout",       type=int, default=300)
    d.add_argument("--max-tokens",    type=int, default=None)
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

    return parser


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

    # delegate subcommand
    assert args.subcmd == "delegate"

    resolved_mode = classify_mode(args.prompt) if args.mode == "auto" else args.mode
    # Token budget resolution:
    #   1. Explicit --max-tokens CLI flag → absolute override
    #   2. classify_tokens() signal match (tiny/small/large) → task-appropriate budget
    #   3. None from classify_tokens → pass None so TaskConfig reads DIRECT_MAX_TOKENS
    #      env var (set by the caller shell) then falls back to mode default.
    # This ensures that `DIRECT_MAX_TOKENS=8192 delegate-to-local ...` is always
    # honoured and not silently capped by the heuristic's 800-token default.
    resolved_tokens = args.max_tokens if args.max_tokens is not None \
        else classify_tokens(args.prompt, resolved_mode)
    # resolved_tokens=None means TaskConfig._resolve_tokens() will read env vars.

    config = TaskConfig.from_args(
        mode=resolved_mode,
        role=args.role,
        timeout_secs=args.timeout,
        max_tokens=resolved_tokens,
        llama_url=args.llama_url,
        hybrid_url=args.hybrid_url,
        ralph_url=args.ralph_url,
    )

    script_dir = Path(args.script_dir) if args.script_dir else _HERE.parent
    output_file = Path(args.output)

    success = dispatch_task(
        config=config,
        prompt=args.prompt,
        task_id=args.task_id,
        output_file=output_file,
        registry=registry,
        script_dir=script_dir,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
