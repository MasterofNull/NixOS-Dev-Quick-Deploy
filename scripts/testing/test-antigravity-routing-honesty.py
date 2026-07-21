#!/usr/bin/env python3
"""test-antigravity-routing-honesty.py — hermetic, offline regression test.

Slice: antigravity-routing-consolidation
Spec:  .agents/plans/antigravity-lane-restoration/ROUTING-CONSOLIDATION-SPEC.md
Basis: .agents/plans/antigravity-lane-restoration/ROUTING-FIX-PROPOSAL.md (D1/D2)

Asserts the fix for two defects:

  D1 — aq-antigravity-agent used to run with enable_fallback=True, so a failed
       remote/Antigravity call silently degraded into a hybrid-coordinator RAG
       search (`LocalAgentExecutor._fallback_to_remote`'s `/query` path) and
       returned that as a fake COMPLETED "result". This test proves a
       reviewer/analysis task now surfaces an explicit FAILED status with a
       plain error string, and that `_fallback_to_remote` (the RAG-dressing
       code path) is never reached.

  D2 — delegate-to-antigravity's module docstring advertised the keyed
       switchboard route (Google AI Studio API key) as a working Antigravity
       lane. This test proves that stale guidance is gone and the docstring
       names the sanctioned lane, aq-collab-round.

No real network call, switchboard, or binary is used — everything here runs
against in-process objects and static source text.
"""

import asyncio
import importlib.machinery
import importlib.util
import re
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LOCAL_AGENTS = _REPO_ROOT / "ai-stack" / "local-agents"
_BUILTIN_TOOLS = _LOCAL_AGENTS / "builtin_tools"
_AI_SCRIPTS = _REPO_ROOT / "scripts" / "ai"

for _p in (str(_LOCAL_AGENTS), str(_BUILTIN_TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FAILURES: list[str] = []


def _check(label: str, cond: bool, detail: str = ""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {label}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(label)


# ── D1: agent/executor honesty ──────────────────────────────────────────────

def test_reviewer_task_fails_honestly_not_rag():
    import agent_executor as ae

    # Mirror aq-antigravity-agent's exact executor construction (enable_fallback
    # is the field the fix flips False->True->False; offline_mode/allow_degraded
    # match the script verbatim) so this test tracks the real dispatch path.
    executor = ae.LocalAgentExecutor(
        tool_registry=ae.get_registry(),
        fallback_endpoint="http://127.0.0.1:8003",
        llama_endpoint="http://127.0.0.1:8080",
        enable_fallback=False,
        offline_mode=False,
        allow_degraded_local_execution=False,
    )

    fallback_calls = {"n": 0}

    async def _tripwire(task):
        # If this is ever invoked, the RAG-dressing path (agent_executor.py
        # LocalAgentExecutor._fallback_to_remote, which POSTs /query and marks
        # a coordinator RAG hit as TaskStatus.COMPLETED) was reached — exactly
        # what D1 forbids for a reviewer/analysis task.
        fallback_calls["n"] += 1
        raise AssertionError("_fallback_to_remote reached — RAG fallback path not gated off")

    executor._fallback_to_remote = _tripwire  # type: ignore[method-assign]

    task = ae.Task(
        id="test-antigravity-honesty",
        objective="review the claim-receipt slice",
        role="reviewer",
        force_remote=True,
    )

    result = asyncio.run(executor.execute_task(task, ae.AgentType.AGENT))

    _check(
        "reviewer task ends in explicit FAILED status (not COMPLETED)",
        result.status == ae.TaskStatus.FAILED,
        f"got status={result.status}",
    )
    _check(
        "RAG fallback path (_fallback_to_remote) was never invoked",
        fallback_calls["n"] == 0,
        f"invoked {fallback_calls['n']} time(s)",
    )
    _check(
        "failure carries a real error string, not empty/None",
        isinstance(result.error, str) and len(result.error) > 0,
        f"error={result.error!r}",
    )
    _check(
        "result is not populated with RAG/keyword-hit content",
        result.result is None,
        f"result={result.result!r}",
    )
    # RAG search-hit output (hybrid-coordinator /query) characteristically
    # returns file/score-shaped content. Guard against that shape leaking
    # into the error text too.
    rag_markers = ("score", "\"file\"", "'file'", "similarity")
    err_lower = (result.error or "").lower()
    _check(
        "error text has no RAG-result markers (score/file/similarity)",
        not any(m in err_lower for m in rag_markers),
        f"error={result.error!r}",
    )


def test_aq_antigravity_agent_source_sets_enable_fallback_false():
    src = (_AI_SCRIPTS / "aq-antigravity-agent").read_text()
    _check(
        "aq-antigravity-agent source sets enable_fallback=False",
        re.search(r"enable_fallback\s*=\s*False", src) is not None,
        "enable_fallback=False not found in source",
    )
    _check(
        "aq-antigravity-agent source no longer sets enable_fallback=True",
        re.search(r"enable_fallback\s*=\s*True", src) is None,
        "stale enable_fallback=True still present",
    )


# ── D2: delegate-to-antigravity docstring + messaging ───────────────────────

def _load_delegate_module():
    # delegate-to-antigravity has no .py suffix, so spec_from_file_location can't
    # infer a loader from the extension alone — use SourceFileLoader explicitly
    # (same pattern as scripts/ai/aq-antigravity-agent's own dispatch-budget
    # loader). The module only executes top-level def/const statements at
    # import time (its `if __name__ == "__main__"` guard keeps main() from
    # running), so this is a safe, offline import — no subprocess, no network.
    path = _AI_SCRIPTS / "delegate-to-antigravity"
    loader = importlib.machinery.SourceFileLoader("delegate_to_antigravity_under_test", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_docstring_no_studio_key_guidance_names_aq_collab_round():
    mod = _load_delegate_module()
    doc = mod.__doc__ or ""

    _check(
        "docstring does not advise a Google AI Studio API key",
        "Google AI Studio API key" not in doc,
        "stale 'Google AI Studio API key' guidance still present",
    )
    _check(
        "docstring does not tell the reader the secret 'must hold' a key",
        "must hold a Google AI Studio" not in doc,
    )
    _check(
        "docstring names aq-collab-round as the sanctioned lane",
        "aq-collab-round" in doc,
    )
    _check(
        "docstring states the keyed lane is not sanctioned/non-functional by policy",
        any(kw in doc for kw in ("NOT the sanctioned", "non-functional", "policy-forbidden")),
    )


def test_run_switchboard_exhaustion_message_names_aq_collab_round():
    src = (_AI_SCRIPTS / "delegate-to-antigravity").read_text()
    # Locate the terminal "all profiles exhausted" failure write and confirm
    # it points at the sanctioned lane rather than silently returning "failed".
    m = re.search(
        r'all profiles exhausted[^"\n]*"\s*\)?\s*\n(?:\s*"[^"\n]*"\s*\n?)*',
        src,
    )
    _check(
        "'all profiles exhausted' failure block found in source",
        m is not None,
    )
    if m:
        block = m.group(0)
        _check(
            "exhaustion failure message names aq-collab-round",
            "aq-collab-round" in block,
            block,
        )


def test_loop_dispatch_failure_names_aq_collab_round():
    src = (_AI_SCRIPTS / "delegate-to-antigravity").read_text()
    # The --loop dispatch (background + --wait) forks/execs aq-antigravity-agent;
    # on a non-zero return code the wrapper must say where the real lane is.
    loop_block_match = re.search(r"if loop:.*?(?=\n    # Register before dispatch)", src, re.S)
    _check(
        "--loop dispatch block found in source",
        loop_block_match is not None,
    )
    if loop_block_match:
        block = loop_block_match.group(0)
        _check(
            "--loop dispatch block checks the agent subprocess return code",
            "returncode" in block,
        )
        _check(
            "--loop dispatch failure message names aq-collab-round",
            block.count("aq-collab-round") >= 2,  # background branch + wait branch
            block,
        )


# ── credential grep guard (defense in depth; acceptance also greps the diff) ─

def test_no_credential_language_added_to_either_file():
    for fname in ("aq-antigravity-agent", "delegate-to-antigravity"):
        src = (_AI_SCRIPTS / fname).read_text()
        # It's fine to *mention* that keys must never be added; it is not fine
        # to instruct the reader to set/rotate/store one.
        forbidden = re.search(
            r"(set|export|configure)\s+(the\s+)?(api[_-]?key|secret)",
            src,
            re.I,
        )
        _check(
            f"{fname}: no instruction to set/export/configure a credential",
            forbidden is None,
            f"matched: {forbidden.group(0) if forbidden else ''}",
        )


def main() -> int:
    with tempfile.TemporaryDirectory():
        test_reviewer_task_fails_honestly_not_rag()
        test_aq_antigravity_agent_source_sets_enable_fallback_false()
        test_docstring_no_studio_key_guidance_names_aq_collab_round()
        test_run_switchboard_exhaustion_message_names_aq_collab_round()
        test_loop_dispatch_failure_names_aq_collab_round()
        test_no_credential_language_added_to_either_file()

    print()
    if FAILURES:
        print(f"FAIL {len(FAILURES)} check(s) failed: {FAILURES}")
        return 1
    print("PASS all antigravity routing honesty checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
