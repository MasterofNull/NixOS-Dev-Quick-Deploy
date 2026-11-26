#!/usr/bin/env python3
"""Regression: aq-prompt-eval defers (exit 75) after consecutive inference timeouts."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "scripts" / "ai" / "aq-prompt-eval"
spec = importlib.util.spec_from_loader("aq_prompt_eval_defer", SourceFileLoader("aq_prompt_eval_defer", str(PATH)))
if spec is None or spec.loader is None:
    raise SystemExit("ERROR: unable to load aq-prompt-eval module")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def run(outcomes: list[bool]) -> tuple[int, int, str]:
    """outcomes: True = success, False = timeout. Cycles last outcome once exhausted."""
    calls: list[int] = []

    def fake(*_a, **_k):
        i = len(calls)
        calls.append(1)
        ok = outcomes[i] if i < len(outcomes) else False
        if not ok:
            raise TimeoutError("simulated timeout")
        return "yes", 1.0

    err = io.StringIO()
    with mock.patch.object(mod, "wait_for_llama_ready", lambda *_a, **_k: True), \
            mock.patch.object(mod, "llm_call", fake), tempfile.TemporaryDirectory() as tmp, \
            redirect_stdout(io.StringIO()), redirect_stderr(err):
        reg = Path(tmp) / "registry.yaml"
        reg.write_text((ROOT / "ai-stack" / "prompts" / "registry.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        code = mod.run_eval(registry_path=reg, target_id=None, dry_run=True, verbose=False, model="local")
    return code, len(calls), err.getvalue()


def run_with_state(successes: int, failure: Exception) -> tuple[int, str, dict, dict, bool]:
    """Real (non-dry) run: `successes` passing calls, then `failure` forever, state via AQ_PROMPT_EVAL_STATE."""
    calls: list[int] = []

    def fake(*_a, **_k):
        calls.append(1)
        if len(calls) > successes:
            raise failure
        return "yes", 1.0

    seed = {"untouched-sentinel": {"mean_score": 0.25, "last_evaluated": "2000-01-01"}}
    err = io.StringIO()
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.yaml"
        reg.write_text((ROOT / "ai-stack" / "prompts" / "registry.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        state = Path(tmp) / "override" / "state.json"
        state.parent.mkdir()
        state.write_text(json.dumps(seed), encoding="utf-8")
        with mock.patch.dict(os.environ, {"AQ_PROMPT_EVAL_STATE": str(state)}), \
                mock.patch.object(mod, "wait_for_llama_ready", lambda *_a, **_k: True), \
                mock.patch.object(mod, "llm_call", fake), \
                mock.patch.object(mod, "score_response", lambda *_a, **_k: (True, [])), \
                redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = mod.run_eval(registry_path=reg, target_id=None, dry_run=False, verbose=False, model="local")
        default_written = reg.with_name("eval-state.json").exists()
        return code, err.getvalue(), seed, json.loads(state.read_text(encoding="utf-8")), default_written


def first_prompts(count: int) -> list[str]:
    import yaml

    registry = yaml.safe_load((ROOT / "ai-stack" / "prompts" / "registry.yaml").read_text(encoding="utf-8"))
    return [e["id"] for e in registry["prompts"] if mod.CANONICAL_TESTS.get(e["id"])][:count]


def main() -> int:
    code, n, err = run([False, False, False])
    assert code == 75, f"3 consecutive timeouts must exit 75, got {code}"
    assert n == 3, f"must stop after 3 calls, made {n}"
    assert "deferring after 3 consecutive timeouts" in err, err
    print("PASS: 3 consecutive timeouts -> exit 75 after exactly 3 calls")

    code, n, _ = run([False, True, False, False, True, True, True, True, True, True, True, True, True, True, True, True])
    assert code != 75, "timeout,success,timeout,timeout must not defer"
    assert n > 4, f"run must continue past the interleaved timeouts, made {n}"
    print("PASS: timeout,success,timeout,timeout -> no deferral")

    done = first_prompts(4)
    successes = sum(len(mod.CANONICAL_TESTS[pid]) for pid in done)

    code, err, seed, state, default_written = run_with_state(0, TimeoutError("simulated timeout"))
    assert code == 75, f"timeout-only run must defer, got {code}"
    assert state == seed, f"timeout-only run must not change AQ_PROMPT_EVAL_STATE: {state}"
    assert not default_written, "override must keep the default eval-state.json untouched"
    print("PASS: timeout-only run leaves AQ_PROMPT_EVAL_STATE unchanged")

    code, err, seed, state, default_written = run_with_state(successes, TimeoutError("simulated timeout"))
    assert code == 75, f"late timeout streak must defer, got {code}"
    assert set(state) == set(seed) | set(done), f"only completed prompts may be scored: {sorted(state)}"
    assert all(state[pid]["mean_score"] == 1.0 for pid in done), state
    assert state["untouched-sentinel"] == seed["untouched-sentinel"], state
    assert not default_written, "override must keep the default eval-state.json untouched"
    print("PASS: deferral writes only completed scores to AQ_PROMPT_EVAL_STATE")

    code, err, seed, state, _ = run_with_state(successes, urllib.error.URLError(ConnectionRefusedError("refused")))
    assert "ABORT 3 consecutive transport errors" in err, err
    assert code == 1, f"non-timeout breaker must exit 1 despite earlier successful prompts, got {code}"
    assert set(state) == set(seed) | set(done), f"completed scores must survive the abort: {sorted(state)}"
    print("PASS: non-timeout breaker exits 1 after earlier successful prompts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
