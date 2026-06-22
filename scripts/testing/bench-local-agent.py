#!/usr/bin/env python3
"""Local agent benchmark — 13 tests across reasoning / tool-use / code-gen / coherence.

Usage:
  bench-local-agent [--quick] [--dim DIMENSION] [--json] [--no-attention]

  --quick      run dimensions A+B only (7 tests, ~6 min)
  --dim D      run only one dimension (reasoning|tool_use|code_gen|coherence)
  --json       write results JSON to stdout (machine-readable)
  --no-attention  skip attention queue push even on regression

Results saved to $LLAMA_BENCHMARK_RUNS_DIR (default: .agents/bench/llama/).
Promotion/demotion checked against config/bench-promotion-criteria.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, quantiles
from typing import Any

_REPO_ROOT = Path(os.environ.get("REPO_ROOT", Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ai" / "lib"))

_LLAMA_URL  = os.environ.get("LLAMA_URL",  "http://127.0.0.1:8080")
_EMBED_URL  = os.environ.get("EMBED_URL",  "http://127.0.0.1:8081")
_BENCH_DIR  = Path(os.environ.get("LLAMA_BENCHMARK_RUNS_DIR",
                                   _REPO_ROOT / ".agents" / "bench" / "llama"))
_CRIT_PATH  = _REPO_ROOT / "config" / "bench-promotion-criteria.json"
_TIMEOUT    = int(os.environ.get("BENCH_TIMEOUT", "180"))
_MODEL      = os.environ.get("BENCH_MODEL", "qwen3.6-35b-mtp-q5")
_SOURCE     = "bench-local-agent"

# ── llama.cpp helpers ──────────────────────────────────────────────────────────

_TOOL_SCHEMA_READ_FILE = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file from the repository",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute file path"}},
            "required": ["path"],
        },
    },
}

_TOOL_SCHEMA_QUERY_AIDB = {
    "type": "function",
    "function": {
        "name": "query_aidb",
        "description": "Search the AIDB knowledge base for bug patterns and solutions",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "collection": {
                    "type": "string",
                    "enum": ["error-solutions", "best-practices", "skills-patterns", "codebase-context"],
                },
            },
            "required": ["query", "collection"],
        },
    },
}

_TOOL_SCHEMA_SHELL = {
    "type": "function",
    "function": {
        "name": "run_shell",
        "description": "Run a shell command and return stdout",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "working_dir": {"type": "string"},
            },
            "required": ["command"],
        },
    },
}

_TOOL_SCHEMA_GIT_COMMIT = {
    "type": "function",
    "function": {
        "name": "git_commit",
        "description": "Commit staged changes",
        "parameters": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
}


def _post(payload: dict, timeout: int = _TIMEOUT) -> tuple[dict, float]:
    payload.setdefault("model", _MODEL)
    payload.setdefault("chat_template_kwargs", {"enable_thinking": False})
    payload.setdefault("frequency_penalty", 0.0)
    payload.setdefault("temperature", 0.1)
    payload.setdefault("stream", False)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{_LLAMA_URL}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read())
        elapsed = time.monotonic() - t0
        return resp, elapsed
    except urllib.error.URLError as e:
        raise RuntimeError(f"llama.cpp unreachable: {e}") from e


def _message(resp: dict) -> dict:
    return resp["choices"][0]["message"]


def _content(resp: dict) -> str:
    return _message(resp).get("content") or ""


def _tool_calls(resp: dict) -> list[dict]:
    return _message(resp).get("tool_calls") or []


def _first_tool(resp: dict) -> tuple[str, dict] | tuple[None, None]:
    tcs = _tool_calls(resp)
    if not tcs:
        return None, None
    tc = tcs[0]["function"]
    try:
        args = json.loads(tc.get("arguments") or "{}")
    except json.JSONDecodeError:
        args = {}
    return tc["name"], args


def _tok_count(resp: dict) -> int:
    return resp.get("usage", {}).get("completion_tokens", 0)


# ── individual test evaluators ─────────────────────────────────────────────────

def _score_A1_nix_constraint(resp: dict, elapsed: float) -> tuple[int, str]:
    """A1: Explain why n_gpu_layers > 12 is unsafe on this system. Max 3 pts."""
    text = _content(resp).lower()
    pts = 0
    notes = []
    if any(w in text for w in ["vram", "gpu memory", "renoir", "apu"]):
        pts += 1; notes.append("+1 VRAM/APU mention")
    if re.search(r"4\s*gb|4gb|4 gigabyte|shared memory", text):
        pts += 1; notes.append("+1 4GB constraint")
    if any(w in text for w in ["crash", "oom", "out of memory", "exceed", "overflow", "swap"]):
        pts += 1; notes.append("+1 consequence named")
    if "<think>" in _content(resp) or "</think>" in _content(resp):
        pts = max(0, pts - 1); notes.append("-1 think leak")
    return pts, "; ".join(notes) or "no relevant content"


def _score_A2_sops_failure_mode(resp: dict, elapsed: float) -> tuple[int, str]:
    """A2: Explain why a sops.secrets key mismatch crashes the whole AI stack. Max 3 pts."""
    text = _content(resp).lower()
    pts = 0
    notes = []
    if any(w in text for w in ["activation", "activationscript", "setupsecrets", "boot"]):
        pts += 1; notes.append("+1 activation time")
    if any(w in text for w in ["/run/secrets", "manifest", "key mismatch", "missing key"]):
        pts += 1; notes.append("+1 manifest/secrets dir")
    if any(w in text for w in ["cascade", "dependency", "service", "downstream", "all"]):
        pts += 1; notes.append("+1 cascade effect")
    return pts, "; ".join(notes) or "no relevant content"


def _score_A3_frequency_penalty(resp: dict, elapsed: float) -> tuple[int, str]:
    """A3: Why does frequency_penalty truncate JSON output from llama.cpp. Max 3 pts."""
    text = _content(resp).lower()
    pts = 0
    notes = []
    if any(w in text for w in ["cumulative", "penalty", "logit", "count", "occurrence"]):
        pts += 1; notes.append("+1 cumulative penalty mechanism")
    if any(w in text for w in ["quote", '"', "quotation mark", "repeated token", "eos"]):
        pts += 1; notes.append('+1 " token identified')
    if any(w in text for w in ["0.0", "disable", "set to zero", "repeat_penalty", "repeat_last_n"]):
        pts += 1; notes.append("+1 fix named")
    return pts, "; ".join(notes) or "no relevant content"


def _score_A4_role_tool_vs_function(resp: dict, elapsed: float) -> tuple[int, str]:
    """A4: Why must tool result messages use role:'tool' not role:'function'. Max 3 pts."""
    text = _content(resp).lower()
    pts = 0
    notes = []
    if any(w in text for w in ["chat template", "template", "qwen", "jinja"]):
        pts += 1; notes.append("+1 chat template context")
    if any(w in text for w in ["silently drop", "ignored", "not recognized", "unknown role"]):
        pts += 1; notes.append("+1 silent drop behavior")
    if any(w in text for w in ["hallucinate", "hallucination", "never sees", "tool result"]):
        pts += 1; notes.append("+1 hallucination consequence")
    return pts, "; ".join(notes) or "no relevant content"


def _score_B1_read_file_tool(resp: dict, elapsed: float) -> tuple[int, str]:
    """B1: Call read_file for a specific path. Max 3 pts."""
    name, args = _first_tool(resp)
    if name is None:
        return 0, "no tool call"
    pts = 0
    notes = []
    if name == "read_file":
        pts += 1; notes.append("+1 correct tool")
    path = args.get("path", "")
    if "local-model-config" in path or "options.nix" in path:
        pts += 1; notes.append("+1 plausible path")
    if path.startswith("/") or path.startswith("~"):
        pts += 1; notes.append("+1 absolute path")
    return pts, "; ".join(notes)


def _score_B2_aidb_collection(resp: dict, elapsed: float) -> tuple[int, str]:
    """B2: Call query_aidb with correct collection for AppArmor errors. Max 3 pts."""
    name, args = _first_tool(resp)
    if name is None:
        return 0, "no tool call"
    pts = 0
    notes = []
    if name == "query_aidb":
        pts += 1; notes.append("+1 correct tool")
    coll = args.get("collection", "")
    if coll == "error-solutions":
        pts += 1; notes.append("+1 correct collection")
    elif coll in ("best-practices", "skills-patterns"):
        pts += 1; notes.append(f"+1 acceptable collection ({coll})")
    query = args.get("query", "").lower()
    if any(w in query for w in ["apparmor", "sqlite", "lock", "eperm", "eacces"]):
        pts += 1; notes.append("+1 specific query")
    return pts, "; ".join(notes)


def _score_B3_shell_tool_safe(resp: dict, elapsed: float) -> tuple[int, str]:
    """B3: Use run_shell for health check — must not call rm/dd/curl with side effects. Max 3 pts."""
    name, args = _first_tool(resp)
    if name is None:
        return 0, "no tool call"
    pts = 0
    notes = []
    if name == "run_shell":
        pts += 1; notes.append("+1 correct tool")
    cmd = args.get("command", "")
    # safe read-only commands
    if any(w in cmd for w in ["systemctl status", "aq-qa", "journalctl", "curl.*localhost", "ss -", "netstat"]):
        pts += 1; notes.append("+1 safe command")
    # destructive patterns = deduct
    if any(w in cmd for w in ["rm ", "dd ", "mkfs", "> /", "DROP TABLE", "curl.*-X POST.*:8"]):
        pts = max(0, pts - 1); notes.append("-1 destructive")
    if cmd:
        pts = min(pts + 1, 3)  # credit for emitting any command
        notes.append("+1 command emitted")
    return pts, "; ".join(notes)


def _score_B4_commit_message_format(resp: dict, elapsed: float) -> tuple[int, str]:
    """B4: Emit a git_commit call with correct conventional commit format. Max 3 pts."""
    name, args = _first_tool(resp)
    if name is None:
        return 0, "no tool call"
    pts = 0
    notes = []
    if name == "git_commit":
        pts += 1; notes.append("+1 correct tool")
    msg = args.get("message", "")
    if re.match(r"^(feat|fix|docs|refactor|chore|test|ci|perf|style)\([^)]+\): .+", msg):
        pts += 1; notes.append("+1 conventional commit")
    if "Co-Authored-By:" in msg or "co-authored-by:" in msg.lower():
        pts += 1; notes.append("+1 Co-Authored-By trailer")
    return pts, "; ".join(notes)


def _score_C1_python_async_pattern(resp: dict, elapsed: float) -> tuple[int, str]:
    """C1: Write correct async file-read handler (asyncio.to_thread pattern). Max 3 pts."""
    text = _content(resp)
    pts = 0
    notes = []
    if "async def" in text:
        pts += 1; notes.append("+1 async def")
    if "asyncio.to_thread" in text or "run_in_executor" in text:
        pts += 1; notes.append("+1 to_thread/executor")
    if "open(" in text and ("await" in text or "async with" in text):
        pts += 1; notes.append("+1 awaited IO")
    elif "open(" in text and "asyncio.to_thread" in text:
        pts += 1; notes.append("+1 sync IO in to_thread")
    return pts, "; ".join(notes) or "no code produced"


def _score_C2_nix_module_snippet(resp: dict, elapsed: float) -> tuple[int, str]:
    """C2: Write a valid NixOS module snippet with options.nix port reference. Max 3 pts."""
    text = _content(resp)
    pts = 0
    notes = []
    if "{ config, lib, pkgs" in text or "{ lib," in text:
        pts += 1; notes.append("+1 module header")
    if "options." in text or "lib.mkOption" in text:
        pts += 1; notes.append("+1 option definition")
    if "config." in text or "cfg." in text:
        pts += 1; notes.append("+1 config reference")
    # penalize hardcoded port numbers inside string literals
    if re.search(r'"[0-9]{4,5}"', text) and "options.nix" not in text and "PORT" not in text:
        pts = max(0, pts - 1); notes.append("-1 hardcoded port")
    return pts, "; ".join(notes) or "no nix code produced"


def _score_C3_python_apparmor_rule(resp: dict, elapsed: float) -> tuple[int, str]:
    """C3: Write a Python function that generates an AppArmor file rule string. Max 3 pts."""
    text = _content(resp)
    pts = 0
    notes = []
    if "def " in text and "return" in text:
        pts += 1; notes.append("+1 function definition")
    if re.search(r"rw[k]?|rwk", text):
        pts += 1; notes.append("+1 rwk permissions")
    if "rw" in text and "k" in text:
        pts += 0; notes.append("~rwk present")
    # Check for 'c' mode which is invalid in AppArmor
    if re.search(r"\brwkc\b|\bwc\b", text):
        pts = max(0, pts - 1); notes.append("-1 invalid 'c' mode")
    if "sqlite" in text.lower() or ".db" in text:
        pts += 1; notes.append("+1 sqlite/db context")
    return pts, "; ".join(notes) or "no code produced"


def _score_D1_multi_turn_coherence(responses: list[dict], elapsed_total: float) -> tuple[int, str]:
    """D1: Multi-turn: remembers a fact set 2 turns ago. Max 3 pts. (pass pre-built resp list)"""
    if len(responses) < 3:
        return 0, "insufficient turns"
    last = _content(responses[-1]).lower()
    pts = 0
    notes = []
    # The planted fact is: "llama.cpp port = 8080, max tokens 180"
    if "8080" in last:
        pts += 1; notes.append("+1 port recalled")
    if any(w in last for w in ["180", "token", "budget"]):
        pts += 1; notes.append("+1 token budget recalled")
    if not any(w in last for w in ["don't remember", "do not know", "no context", "wasn't"]):
        pts += 1; notes.append("+1 no hallucinated forgetting")
    return pts, "; ".join(notes)


def _score_D2_no_think_leak(resp: dict, elapsed: float) -> tuple[int, str]:
    """D2: Confirm no <think> tokens leak into final output. Max 3 pts (0 or 3)."""
    text = _content(resp)
    if "<think>" in text or "</think>" in text:
        return 0, "FAIL: think tokens leaked"
    if re.search(r"<\|im_start\|>|<\|im_end\|>", text):
        return 0, "FAIL: chat template tokens leaked"
    toks = _tok_count(resp)
    # Baseline: responded at all with non-empty content
    if not text.strip():
        return 1, "WARN: empty response"
    return 3, f"+3 clean output ({toks} tok)"


# ── test registry ──────────────────────────────────────────────────────────────

def _build_tests(model: str) -> list[dict]:
    """Return ordered test spec list. Each entry has id, dim, prompt, tools, max_score, evaluator."""
    base = {"model": model, "max_tokens": 400, "temperature": 0.1}

    def _t(tid, dim, prompt, evaluator, max_score=3, tools=None, extra=None):
        return {
            "id": tid, "dim": dim, "prompt": prompt, "evaluator": evaluator,
            "max_score": max_score, "tools": tools or [], "extra": extra or {},
            **base,
        }

    return [
        _t("A1", "reasoning",
           "Explain in 2-3 sentences why setting --n-gpu-layers above 12 is unsafe on this system. "
           "The system has a Renoir APU with 4 GB shared VRAM.",
           _score_A1_nix_constraint),
        _t("A2", "reasoning",
           "Explain why a mismatch between sops.secrets keys in secrets.nix and the actual SOPS "
           "encrypted YAML file causes the entire AI stack to be down at boot, not just the affected service.",
           _score_A2_sops_failure_mode),
        _t("A3", "reasoning",
           "Explain the mechanism by which a non-zero frequency_penalty setting in a llama.cpp request "
           "causes dense JSON output to be truncated around line 59-61.",
           _score_A3_frequency_penalty),
        _t("A4", "reasoning",
           "When an agent loop returns a tool result to Qwen3-35B via the llama.cpp /v1/chat/completions "
           "API, which role field must the message use, and what happens if the wrong value is used?",
           _score_A4_role_tool_vs_function),
        _t("B1", "tool_use",
           "Read the file at /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/local-model-config.yaml "
           "to check what model is configured.",
           _score_B1_read_file_tool,
           tools=[_TOOL_SCHEMA_READ_FILE]),
        _t("B2", "tool_use",
           "Search for known AppArmor SQLite lock errors and their fixes in the knowledge base.",
           _score_B2_aidb_collection,
           tools=[_TOOL_SCHEMA_QUERY_AIDB]),
        _t("B3", "tool_use",
           "Run a shell command to check whether the ai-hybrid-coordinator service is currently active "
           "and what port it is listening on.",
           _score_B3_shell_tool_safe,
           tools=[_TOOL_SCHEMA_SHELL]),
        _t("B4", "tool_use",
           "Commit the staged changes with a message describing a fix for the frequency_penalty "
           "truncation bug in dispatch.py. Follow the project commit format with Co-Authored-By.",
           _score_B4_commit_message_format,
           tools=[_TOOL_SCHEMA_GIT_COMMIT]),
        _t("C1", "code_gen",
           "Write a Python async aiohttp handler that reads a large JSONL audit log file without "
           "blocking the event loop. Show only the function body, no explanation.",
           _score_C1_python_async_pattern),
        _t("C2", "code_gen",
           "Write a minimal NixOS module snippet that exposes a port option for a new service, "
           "sourcing the default from the central options.nix. No hardcoded port numbers.",
           _score_C2_nix_module_snippet),
        _t("C3", "code_gen",
           "Write a Python function `apparmor_sqlite_rule(db_path: str) -> str` that returns a "
           "valid AppArmor file rule string for a SQLite database path. Include read, write, and "
           "file-lock permissions. Do NOT include the 'c' (create) permission keyword.",
           _score_C3_python_apparmor_rule),
        # D1 is a multi-turn test — handled specially in run_d1_multiturn()
        _t("D2", "coherence",
           "What is the purpose of the nix/modules/core/options.nix file in this NixOS flake? "
           "Answer in one sentence, no preamble.",
           _score_D2_no_think_leak),
    ]


# ── multi-turn test D1 ─────────────────────────────────────────────────────────

def run_d1_multiturn(model: str, timeout: int) -> dict:
    """Run a 3-turn conversation. Turn 1 plants a fact, turn 2 distracts, turn 3 recalls."""
    messages = [
        {"role": "user",
         "content": "For this session, remember: llama.cpp is on port 8080 and the local agent "
                    "token budget ceiling is 180 tokens. Confirm you have noted this."},
    ]
    resps = []
    total_elapsed = 0.0

    # Turn 1
    resp, el = _post({"messages": messages, "max_tokens": 80, "model": model})
    resps.append(resp)
    total_elapsed += el
    messages.append({"role": "assistant", "content": _content(resp)})

    # Turn 2 — distractor
    messages.append({"role": "user",
                     "content": "What is the difference between AppArmor `ix` and `Ux` transitions?"})
    resp, el = _post({"messages": messages, "max_tokens": 200, "model": model})
    resps.append(resp)
    total_elapsed += el
    messages.append({"role": "assistant", "content": _content(resp)})

    # Turn 3 — recall
    messages.append({"role": "user",
                     "content": "What port is llama.cpp on, and what is the token budget ceiling "
                                "I mentioned two turns ago?"})
    resp, el = _post({"messages": messages, "max_tokens": 120, "model": model})
    resps.append(resp)
    total_elapsed += el

    score, note = _score_D1_multi_turn_coherence(resps, total_elapsed)
    return {
        "id": "D1",
        "dim": "coherence",
        "score": score,
        "max_score": 3,
        "elapsed_s": round(total_elapsed, 1),
        "completion_tokens": sum(_tok_count(r) for r in resps),
        "note": note,
        "final_content": _content(resps[-1])[:200],
    }


# ── runner ─────────────────────────────────────────────────────────────────────

def run_test(spec: dict) -> dict:
    payload = {
        "messages": [{"role": "user", "content": spec["prompt"]}],
        "max_tokens": spec.get("max_tokens", 400),
        "temperature": spec.get("temperature", 0.1),
        "model": spec["model"],
    }
    if spec.get("tools"):
        payload["tools"] = spec["tools"]

    try:
        resp, elapsed = _post(payload, timeout=_TIMEOUT)
    except RuntimeError as e:
        return {
            "id": spec["id"], "dim": spec["dim"], "score": 0,
            "max_score": spec["max_score"], "elapsed_s": 0.0,
            "completion_tokens": 0, "note": f"ERROR: {e}",
            "final_content": "",
        }

    score, note = spec["evaluator"](resp, elapsed)
    return {
        "id": spec["id"],
        "dim": spec["dim"],
        "score": score,
        "max_score": spec["max_score"],
        "elapsed_s": round(elapsed, 1),
        "completion_tokens": _tok_count(resp),
        "note": note,
        "final_content": _content(resp)[:200] if not _tool_calls(resp)
                         else json.dumps(_first_tool(resp))[:200],
    }


# ── scoring + promotion logic ──────────────────────────────────────────────────

def _compute_scores(results: list[dict]) -> dict:
    dims: dict[str, dict] = {}
    for r in results:
        d = r["dim"]
        if d not in dims:
            dims[d] = {"score": 0, "max": 0}
        dims[d]["score"] += r["score"]
        dims[d]["max"] += r["max_score"]
    for d, v in dims.items():
        v["pct"] = round(v["score"] / v["max"], 3) if v["max"] else 0.0
    total_score = sum(v["score"] for v in dims.values())
    total_max   = sum(v["max"]   for v in dims.values())
    return {
        "dims": dims,
        "total_score": total_score,
        "total_max": total_max,
        "overall_pct": round(total_score / total_max, 3) if total_max else 0.0,
    }


def _check_promotion(scores: dict, criteria: dict) -> dict:
    prom = criteria["promotion"]
    dem  = criteria["demotion"]
    dims = scores["dims"]
    overall = scores["overall_pct"]

    reasons_pass, reasons_fail = [], []

    def _chk(dim, key_prom, key_dem):
        if dim not in dims:
            return  # dimension not tested in this run — skip
        pct = dims[dim].get("pct", 0.0)
        prom_thr = prom.get(key_prom, 0.0)
        dem_thr  = dem.get(key_dem, 0.0)
        if pct >= prom_thr:
            reasons_pass.append(f"{dim}={pct:.0%} >= {prom_thr:.0%}")
        elif pct < dem_thr:
            reasons_fail.append(f"{dim}={pct:.0%} < demotion floor {dem_thr:.0%}")
        else:
            reasons_fail.append(f"{dim}={pct:.0%} below promotion {prom_thr:.0%}")

    _chk("reasoning",  "reasoning_pct_min",  "reasoning_pct_floor")
    _chk("tool_use",   "tool_use_pct_min",   "tool_use_pct_floor")
    _chk("code_gen",   "code_gen_pct_min",   "code_gen_pct_floor")
    _chk("coherence",  "coherence_pct_min",  "coherence_pct_floor")

    promote = (
        not reasons_fail
        and overall >= prom.get("overall_pct_min", 0.72)
    )
    demote = any(
        dims[d].get("pct", 0.0) < dem.get(f"{d}_pct_floor", 0.0)
        for d in ("reasoning", "tool_use", "code_gen", "coherence")
        if d in dims
    ) or overall < dem.get("overall_pct_floor", 0.55)

    return {
        "promote": promote,
        "demote": demote,
        "reasons_pass": reasons_pass,
        "reasons_fail": reasons_fail,
        "overall_pct": overall,
    }


def _load_last_run(bench_dir: Path) -> dict | None:
    runs = sorted(bench_dir.glob("run-*.json"))
    if not runs:
        return None
    try:
        return json.loads(runs[-1].read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _check_regression(current: dict, previous: dict | None, threshold: float = 0.10) -> list[str]:
    if not previous:
        return []
    regressions = []
    prev_dims = previous.get("scores", {}).get("dims", {})
    curr_dims = current.get("dims", {})
    for dim, cv in curr_dims.items():
        prev_pct = prev_dims.get(dim, {}).get("pct", 0.0)
        if prev_pct - cv["pct"] >= threshold:
            regressions.append(f"{dim}: {prev_pct:.0%} → {cv['pct']:.0%}")
    return regressions


# ── attention queue push ───────────────────────────────────────────────────────

def _push_alert(verdict: dict, regressions: list[str], run_id: str) -> None:
    try:
        from attention_queue import push
    except ImportError:
        return
    lines = []
    if verdict["demote"]:
        lines.append("LOCAL AGENT DEMOTION THRESHOLD HIT:")
        lines += [f"  {r}" for r in verdict["reasons_fail"]]
    if regressions:
        lines.append("SCORE REGRESSION vs PREVIOUS RUN:")
        lines += [f"  {r}" for r in regressions]
    if not lines:
        return
    detail_text = "\n".join(lines) + f"\n\nRun ID: {run_id}\nOverall: {verdict['overall_pct']:.0%}"
    push(
        source=_SOURCE,
        severity="critical" if verdict["demote"] else "high",
        autonomy_boundary="human_gate",
        title=f"bench-local-agent: {'demotion' if verdict['demote'] else 'regression'} detected",
        detail=detail_text,
        proposed_action="Review bench run, check for model regression or config change. "
                        "Run: python3 scripts/testing/bench-local-agent.py --json to confirm.",
        ttl_s=3600,
    )


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--quick",        action="store_true", help="Run A+B dims only (7 tests)")
    p.add_argument("--dim",          choices=["reasoning", "tool_use", "code_gen", "coherence"],
                   help="Run one dimension only")
    p.add_argument("--json",         action="store_true", help="Machine-readable output to stdout")
    p.add_argument("--no-attention", action="store_true", help="Skip attention queue push")
    p.add_argument("--model",        default=_MODEL, help="Model name for completions")
    args = p.parse_args()

    model = args.model
    tests = _build_tests(model)

    # filter by dimension
    if args.dim:
        tests = [t for t in tests if t["dim"] == args.dim]
    elif args.quick:
        tests = [t for t in tests if t["dim"] in ("reasoning", "tool_use")]

    skip_d1 = args.dim not in (None, "coherence") or args.quick

    _BENCH_DIR.mkdir(parents=True, exist_ok=True)
    run_ts  = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id  = f"run-{run_ts}"
    started = time.monotonic()

    results = []
    total = len(tests) + (0 if skip_d1 else 1)
    idx   = 0

    for spec in tests:
        idx += 1
        if not args.json:
            print(f"[{idx}/{total}] {spec['id']} {spec['dim']} … ", end="", flush=True)
        r = run_test(spec)
        results.append(r)
        if not args.json:
            bar  = "█" * r["score"] + "░" * (r["max_score"] - r["score"])
            tok_s = f"{r['completion_tokens']/r['elapsed_s']:.1f} tok/s" if r["elapsed_s"] else "ERR"
            print(f"{r['score']}/{r['max_score']} [{bar}] {r['elapsed_s']:.0f}s {tok_s}")
            print(f"          {r['note'][:90]}")

    if not skip_d1:
        idx += 1
        if not args.json:
            print(f"[{idx}/{total}] D1 coherence (multi-turn) … ", end="", flush=True)
        r = run_d1_multiturn(model, _TIMEOUT)
        results.append(r)
        if not args.json:
            bar = "█" * r["score"] + "░" * (r["max_score"] - r["score"])
            print(f"{r['score']}/{r['max_score']} [{bar}] {r['elapsed_s']:.0f}s")
            print(f"          {r['note'][:90]}")

    wall_s  = time.monotonic() - started
    latencies = [r["elapsed_s"] for r in results if r["elapsed_s"] > 0]
    p95     = quantiles(latencies, n=20)[18] if len(latencies) >= 5 else max(latencies or [0])
    scores  = _compute_scores(results)

    criteria = {}
    if _CRIT_PATH.exists():
        try:
            criteria = json.loads(_CRIT_PATH.read_text())
        except json.JSONDecodeError:
            pass

    verdict    = _check_promotion(scores, criteria) if criteria else {}
    prev_run   = _load_last_run(_BENCH_DIR)
    regressions = _check_regression(scores, prev_run, threshold=criteria.get("regression_alert", {}).get("score_drop_pct", 0.10))

    run_record = {
        "run_id":     run_id,
        "model":      model,
        "started_at": run_ts,
        "wall_s":     round(wall_s, 1),
        "latency_p95_s": round(p95, 1),
        "results":    results,
        "scores":     scores,
        "verdict":    verdict,
        "regressions": regressions,
    }
    out_path = _BENCH_DIR / f"{run_id}.json"
    out_path.write_text(json.dumps(run_record, indent=2))

    if args.json:
        json.dump(run_record, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"\n── Results ─────────────────────────────────────")
        print(f"  Total:     {scores['total_score']}/{scores['total_max']} ({scores['overall_pct']:.0%})")
        for dim, v in scores["dims"].items():
            bar = "█" * v["score"] + "░" * (v["max"] - v["score"])
            print(f"  {dim:<12} {v['score']}/{v['max']} [{bar}] {v['pct']:.0%}")
        print(f"  Wall time: {wall_s:.0f}s   p95 latency: {p95:.0f}s")
        if verdict:
            if verdict["promote"]:
                print(f"\n  VERDICT: ✓ PROMOTION criteria met ({scores['overall_pct']:.0%} >= 72%)")
                print(f"           Note: requires {criteria['promotion']['required_consecutive_runs']} consecutive passing runs")
            elif verdict["demote"]:
                print(f"\n  VERDICT: ✗ DEMOTION floor hit")
                for r in verdict["reasons_fail"]:
                    print(f"           {r}")
            else:
                print(f"\n  VERDICT: ~ Below promotion, above demotion floor")
                for r in verdict["reasons_fail"]:
                    print(f"           {r}")
        if regressions:
            print(f"\n  REGRESSIONS vs previous run:")
            for r in regressions:
                print(f"           {r}")
        print(f"\n  Saved: {out_path}")

    if not args.no_attention and (verdict.get("demote") or regressions):
        _push_alert(verdict, regressions, run_id)

    return 0 if not verdict.get("demote") else 1


if __name__ == "__main__":
    sys.exit(main())
