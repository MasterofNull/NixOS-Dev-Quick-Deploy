#!/usr/bin/env python3
"""Regression: aq-prompt-eval defers (exit 75) after consecutive inference timeouts."""

from __future__ import annotations

import importlib.util
import io
import tempfile
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
