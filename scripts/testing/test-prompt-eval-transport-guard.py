#!/usr/bin/env python3
# Regression for aq-prompt-eval transport-guard behavior.

"""Regression for aq-prompt-eval transport-guard behavior."""

from __future__ import annotations

import importlib.util
import tempfile
from unittest import mock
from importlib.machinery import SourceFileLoader
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQ_PROMPT_EVAL_PATH = ROOT / "scripts" / "ai" / "aq-prompt-eval"
AQ_PROMPT_EVAL_SPEC = importlib.util.spec_from_loader(
    "aq_prompt_eval_transport_guard",
    SourceFileLoader("aq_prompt_eval_transport_guard", str(AQ_PROMPT_EVAL_PATH)),
)
if AQ_PROMPT_EVAL_SPEC is None or AQ_PROMPT_EVAL_SPEC.loader is None:
    raise SystemExit("ERROR: unable to load aq-prompt-eval module")
aq_prompt_eval = importlib.util.module_from_spec(AQ_PROMPT_EVAL_SPEC)
AQ_PROMPT_EVAL_SPEC.loader.exec_module(aq_prompt_eval)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    source_registry = ROOT / "ai-stack" / "prompts" / "registry.yaml"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_registry = Path(tmpdir) / "registry.yaml"
        original_text = source_registry.read_text(encoding="utf-8")
        tmp_registry.write_text(original_text, encoding="utf-8")

        original_wait = aq_prompt_eval.wait_for_llama_ready
        original_llm_call = aq_prompt_eval.llm_call
        try:
            aq_prompt_eval.wait_for_llama_ready = lambda *_args, **_kwargs: True

            def failing_llm_call(*_args, **_kwargs):
                raise TimeoutError("simulated timeout")

            aq_prompt_eval.llm_call = failing_llm_call
            exit_code = aq_prompt_eval.run_eval(
                registry_path=tmp_registry,
                target_id="route_search_synthesis",
                dry_run=False,
                verbose=False,
                model="local",
            )
        finally:
            aq_prompt_eval.wait_for_llama_ready = original_wait
            aq_prompt_eval.llm_call = original_llm_call

        updated_text = tmp_registry.read_text(encoding="utf-8")
        assert_true(exit_code == 75, "consecutive timeouts should defer aq-prompt-eval (exit 75)")
        assert_true(updated_text == original_text, "transport errors should not rewrite registry scores")

    print("PASS: aq-prompt-eval preserves registry entries on transport/runtime failures")
    return breaker_check()


def breaker_check() -> int:
    """A saturated backend must stop the run after MAX_CONSECUTIVE_ERRORS calls, not after every case."""
    calls: list[int] = []

    def failing(*_a, **_k):
        calls.append(1)
        raise TimeoutError("simulated timeout")

    with mock.patch.object(aq_prompt_eval, "wait_for_llama_ready", lambda *_a, **_k: True), \
            mock.patch.object(aq_prompt_eval, "llm_call", failing), tempfile.TemporaryDirectory() as tmpdir:
        reg = Path(tmpdir) / "registry.yaml"
        reg.write_text((ROOT / "ai-stack" / "prompts" / "registry.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        exit_code = aq_prompt_eval.run_eval(registry_path=reg, target_id=None, dry_run=True, verbose=False, model="local")
    assert_true(exit_code == 75, "a timeout-saturated run must defer with exit 75")
    assert_true(len(calls) == aq_prompt_eval.MAX_CONSECUTIVE_ERRORS, f"breaker should stop after {aq_prompt_eval.MAX_CONSECUTIVE_ERRORS} calls, made {len(calls)}")
    print("PASS: aq-prompt-eval stops calling a saturated backend after the consecutive-error limit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
