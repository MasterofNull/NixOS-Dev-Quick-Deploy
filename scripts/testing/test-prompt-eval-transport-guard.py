#!/usr/bin/env python3
# Regression for aq-prompt-eval transport-guard behavior.

"""Regression for aq-prompt-eval transport-guard behavior."""

from __future__ import annotations

import importlib.util
import tempfile
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

        ns = vars(aq_prompt_eval)  # module globals: avoids attribute-assignment lint/type noise
        original_wait = aq_prompt_eval.wait_for_llama_ready
        original_llm_call = aq_prompt_eval.llm_call
        try:
            aq_prompt_eval.wait_for_llama_ready = lambda *_args, **_kwargs: True

            def failing_llm_call(*_args, **_kwargs):
                raise TimeoutError("simulated timeout")

            calls = []

            def counting_failing_call(*_args, **_kwargs):
                calls.append(1)
                raise TimeoutError("simulated timeout")

            kw = dict(registry_path=tmp_registry, target_id=None, dry_run=False, verbose=False, model="local")
            # Busy slot: the run defers after N consecutive failures instead of burning one timeout per case.
            ns["llm_call"] = counting_failing_call
            deferred = aq_prompt_eval.run_eval(**kw)
            assert_true(deferred == aq_prompt_eval.EXIT_DEFERRED == 75, f"expected deferral exit 75, got {deferred}")
            assert_true(len(calls) == aq_prompt_eval.DEFER_AFTER, f"expected {aq_prompt_eval.DEFER_AFTER} calls, got {len(calls)}")
            assert_true(tmp_registry.read_text(encoding="utf-8") == original_text, "deferred run must not write scores")

            # Deferral disabled: the original transport-failure behaviour (exit 1, registry untouched).
            ns["DEFER_AFTER"] = 0
            ns["llm_call"] = failing_llm_call
            exit_code = aq_prompt_eval.run_eval(**{**kw, "target_id": "route_search_synthesis"})
        finally:
            ns["DEFER_AFTER"] = 3
            aq_prompt_eval.wait_for_llama_ready = original_wait
            aq_prompt_eval.llm_call = original_llm_call

        updated_text = tmp_registry.read_text(encoding="utf-8")
        assert_true(exit_code == 1, "transport errors should make aq-prompt-eval fail")
        assert_true(updated_text == original_text, "transport errors should not rewrite registry scores")

    print("PASS: aq-prompt-eval preserves registry entries on transport/runtime failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
