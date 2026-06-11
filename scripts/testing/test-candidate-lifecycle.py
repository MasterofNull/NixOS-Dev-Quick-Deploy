#!/usr/bin/env python3
"""Phase 150 Slice 1: verify CandidateLifecycleManager state machine, defaults, and transitions."""
import sys
import os
import json
import tempfile
import shutil
from pathlib import Path

# Add project root to path to import CandidateLifecycleManager
sys.path.append("/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents")
from candidate_lifecycle import CandidateLifecycleManager

def test_lifecycle():
    tmpdir = tempfile.mkdtemp()
    try:
        cand_file = Path(tmpdir) / "candidates.json"
        initial_data = [
            {"id": "C1", "name": "Candidate One"},
            {"id": "C2", "name": "Candidate Two"}
        ]
        with open(cand_file, "w") as f:
            json.dump(initial_data, f)

        manager = CandidateLifecycleManager(cand_file)
        candidates = manager.load()

        # Verify defaults
        for cand in candidates:
            assert cand["state"] == "proposed"
            assert cand["trust_score"] == 0.0
            assert cand["relevance"] == 0.5
            assert "governance" in cand
            assert "eval_results" in cand
            assert cand["lifecycle_log"] == []

        # Transition
        manager.transition("C1", "evaluating", by="test-user", note="Starting evaluation")
        c1 = next(c for c in manager.candidates if c["id"] == "C1")
        assert c1["state"] == "evaluating"
        assert len(c1["lifecycle_log"]) == 1
        assert c1["lifecycle_log"][0]["from_state"] == "proposed"
        assert c1["lifecycle_log"][0]["to_state"] == "evaluating"
        assert c1["lifecycle_log"][0]["by"] == "test-user"

        # Trust score clamping
        manager.set_trust_score("C1", 1.5)
        assert c1["trust_score"] == 1.0
        manager.set_trust_score("C2", -0.5)
        c2 = next(c for c in manager.candidates if c["id"] == "C2")
        assert c2["trust_score"] == 0.0

        # get_by_state
        proposed = manager.get_by_state("proposed")
        evaluating = manager.get_by_state("evaluating")
        assert len(proposed) == 1
        assert len(evaluating) == 1
        assert proposed[0]["id"] == "C2"
        assert evaluating[0]["id"] == "C1"

        print("Test CandidateLifecycleManager: PASSED")
        sys.exit(0)

    except Exception as e:
        print(f"Test CandidateLifecycleManager: FAILED - {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        shutil.rmtree(tmpdir)

if __name__ == "__main__":
    test_lifecycle()
