#!/usr/bin/env python3
"""
Continuous learning proposal persistence regression test.

Purpose: ensure optimization proposals serialize cleanly into JSONL telemetry.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("AI_STRICT_ENV", "false")
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers"))
sys.path.insert(0, str(ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator"))

if "structlog" not in sys.modules:
    sys.modules["structlog"] = types.SimpleNamespace(
        get_logger=lambda: types.SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
            debug=lambda *args, **kwargs: None,
        )
    )

from continuous_learning import ContinuousLearningPipeline, OptimizationProposal  # noqa: E402


class DummySettings:
    pass


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="continuous-learning-proposals-") as tmpdir:
        os.environ["DATA_DIR"] = tmpdir
        pipeline = ContinuousLearningPipeline(DummySettings(), None, None)
        proposal = OptimizationProposal(
            proposal_id="proposal-test",
            proposal_type="timeout_adjustment",
            title="Increase timeout budget for smoke",
            rationale="Observed repeated timeout failures during smoke validation.",
            recommended_action="Increase timeout budget by 20% for long-running smoke tasks.",
            evidence={"timeout_signals": 3},
            created_at=datetime.now(timezone.utc),
        )

        proposal_hash = pipeline._proposal_hash(proposal)
        pipeline._record_proposal(proposal, proposal_hash)

        assert proposal_hash in pipeline.proposal_hashes
        assert pipeline.proposals_path.exists()

        lines = pipeline.proposals_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["proposal_hash"] == proposal_hash
        assert payload["proposal_id"] == "proposal-test"
        assert isinstance(payload["created_at"], str)
        assert "T" in payload["created_at"]

    print("PASS: continuous learning proposal persistence serializes datetimes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
