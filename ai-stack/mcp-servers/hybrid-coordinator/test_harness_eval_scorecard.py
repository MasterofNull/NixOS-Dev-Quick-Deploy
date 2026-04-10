#!/usr/bin/env python3

import asyncio
import importlib.util
import os
from pathlib import Path
import sys


_HARNESS_EVAL_PATH = Path(__file__).with_name("harness_eval.py")
os.environ["AI_STRICT_ENV"] = "false"
sys.path.insert(0, str(_HARNESS_EVAL_PATH.parent))
sys.path.insert(0, str(_HARNESS_EVAL_PATH.parent.parent))
_SPEC = importlib.util.spec_from_file_location("hybrid_harness_eval_real", _HARNESS_EVAL_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_scorecard_includes_recent_failed_case_diagnostics():
    async def fake_route_search(**_kwargs):
        return {"response": "", "results": {"combined_results": []}}

    harness_stats = {
        "total_runs": 0,
        "passed": 0,
        "failed": 0,
        "failure_taxonomy": {},
        "last_run_at": None,
        "scorecards_generated": 0,
    }
    hybrid_stats = {"capability_discovery": {}}
    _MODULE.Config.AI_HARNESS_EVAL_ENABLED = True
    _MODULE.Config.AI_HARNESS_EVAL_TIMEOUT_S = 5.0
    _MODULE.Config.AI_HARNESS_EVAL_TIMEOUT_HARD_CAP_S = 5.0
    _MODULE.Config.AI_HARNESS_MAX_LATENCY_MS = 3000
    _MODULE.Config.AI_HARNESS_MIN_ACCEPTANCE_SCORE = 0.7
    _MODULE.Config.AI_PROMPT_CACHE_POLICY_ENABLED = True
    _MODULE.Config.AI_SPECULATIVE_DECODING_ENABLED = False
    _MODULE.Config.AI_SPECULATIVE_DECODING_MODE = "disabled"
    _MODULE.Config.AI_CONTEXT_COMPRESSION_ENABLED = True

    _MODULE.init(
        route_search_fn=fake_route_search,
        record_telemetry_fn=lambda *_args, **_kwargs: None,
        harness_stats=harness_stats,
        hybrid_stats=hybrid_stats,
    )

    result = asyncio.run(
        _MODULE.run_harness_evaluation(
            query="check lesson ref parity smoke harness eval",
            expected_keywords=["lesson", "parity"],
        )
    )

    assert result["passed"] is False
    assert result["failure_category"] == "empty_response"

    scorecard = _MODULE.build_harness_scorecard()
    failures = scorecard["failures"]

    assert failures["analysis_ready"] is True
    assert failures["taxonomy"]["empty_response"] == 1
    assert failures["recent_failed_cases"][0]["failure_category"] == "empty_response"
    assert "Check model availability" in failures["recent_failed_cases"][0]["suggested_fix"]
