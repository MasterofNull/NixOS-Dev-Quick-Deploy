#!/usr/bin/env python3
"""Regression checks for RSI R1 training-loop trust gates."""

from __future__ import annotations

import importlib.machinery
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-local-training-loop"


def load_module():
    loader = importlib.machinery.SourceFileLoader("aq_local_training_loop_trust_test", str(MODULE_PATH))
    return loader.load_module()


def main() -> int:
    mod = load_module()
    with tempfile.TemporaryDirectory(prefix="training-loop-trust-") as tmp:
        spool = Path(tmp) / "training-samples.jsonl"
        os.environ["AQ_TRAINING_SAMPLES"] = str(spool)
        spool.write_text(
            json.dumps(
                {
                    "kind": "failure_sample",
                    "failure_class": "eval_low_score",
                    "prompt": "same prompt",
                    "bad_output": "bad",
                    "corrected_output": "",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        assert mod._pending_eval_low_score_correction_exists("same prompt") is True
        assert mod._pending_eval_low_score_correction_exists("different prompt") is False
    print("PASS: training-loop skips duplicate pending eval_low_score corrections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
