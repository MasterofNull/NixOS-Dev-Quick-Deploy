#!/usr/bin/env python3
"""Regression checks for training-loop improvement-proposal quality gating."""

from __future__ import annotations

import importlib.machinery
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-local-training-loop"

FAILING = [{
    "case_id": "c1", "score": 0.2,
    "missing_keywords": ["hybrid-coordinator", "qdrant"],
    "prompt_excerpt": "Which service does embedding retrieval for the harness?",
    "response_excerpt": "It uses some vector store behind an API.",
}]
GOOD = {
    "root_cause": "The model answers generically because the system prompt never names the hybrid coordinator.",
    "change_type": "system_prompt",
    "change_description": "Add one sentence to the system prompt naming hybrid-coordinator and qdrant as retrieval backends.",
    "expected_keyword_gains": ["Hybrid-Coordinator"],
    "confidence": 0.7,
}


def main() -> int:
    mod = importlib.machinery.SourceFileLoader("aq_ltl_quality_test", str(MODULE_PATH)).load_module()

    junk = {
        "root_cause": "ai-stack/mcp-servers/hybrid-coordinator/route_handler.py (score=26.89, source=keyword)",
        "change_description": "ai-stack/mcp-servers/hybrid-coordinator/route_handler.py (score=26.89, source=keyword)",
        "expected_keyword_gains": [],
    }
    ok, reasons = mod._validate_proposal(junk, FAILING)
    assert not ok and "confidence_missing_or_out_of_range" in reasons, reasons
    assert "root_cause_is_retrieval_line" in reasons and "expected_keyword_gains_empty" in reasons

    assert mod._validate_proposal(GOOD, FAILING) == (True, [])

    no_conf = {k: v for k, v in GOOD.items() if k != "confidence"}
    assert not mod._validate_proposal(no_conf, FAILING)[0]
    assert "confidence_below_threshold" in mod._validate_proposal({**GOOD, "confidence": 0.5}, FAILING)[1]

    bad_gain = {**GOOD, "expected_keyword_gains": ["redis"]}
    assert "expected_keyword_gains_not_in_missing_keywords" in mod._validate_proposal(bad_gain, FAILING)[1]
    assert "change_type_invalid" in mod._validate_proposal({**GOOD, "change_type": "model_swap"}, FAILING)[1]

    assert mod._parse_improvements("Here are some ideas:\n\n- do a thing\n- another") is None
    assert mod._parse_improvements("[not json]") is None
    parsed = mod._parse_improvements("```json\n" + json.dumps([GOOD]) + "\n```")
    assert parsed == [GOOD]

    prompt = mod._generate_improvement_prompt(FAILING, {})
    assert FAILING[0]["prompt_excerpt"] in prompt and FAILING[0]["response_excerpt"] in prompt
    assert "JSON array only" in prompt

    title = mod._proposal_title("word " * 60)
    assert len(title) <= 120 and not title.endswith("wor")

    with tempfile.TemporaryDirectory(prefix="training-loop-quality-") as tmp:
        path = Path(tmp) / "optimization_proposals.jsonl"
        assert mod._pending_proposal_keys(path) == set()
        rec = {"status": "pending", "change_type": GOOD["change_type"],
               "title": "x", "evidence": {"root_cause": GOOD["root_cause"].upper()}}
        path.write_text(json.dumps(rec) + "\n" + json.dumps({**rec, "status": "rejected",
                        "change_type": "profile"}) + "\n", encoding="utf-8")
        keys = mod._pending_proposal_keys(path)
        assert (GOOD["change_type"], mod._norm_text(GOOD["root_cause"])) in keys
        assert len(keys) == 1

    print("training-loop proposal quality checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
