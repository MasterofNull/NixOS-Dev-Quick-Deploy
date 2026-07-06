#!/usr/bin/env python3
"""Regression: QualityConsensus persists active_sessions across processes.

The expert-team debate: agents submit reviews via separate `aq-collaborate review`
invocations, then `decide` computes consensus. That requires active_sessions to
survive across process boundaries (they were in-memory only). Verifies the full
cross-instance round-trip incl. VoteType enum reconstruction.
"""
import sys
import tempfile
import asyncio
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib" / "l4-coord" / "agents"))

import quality_consensus as qc  # noqa: E402


def _fail(m):
    print(f"FAIL: {m}"); sys.exit(1)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="consensus-persist-"))

    for cls in ("Review", "ConsensusSession"):
        if not hasattr(getattr(qc, cls), "from_dict"):
            _fail(f"{cls}.from_dict missing")

    # Instance A: reviewer 1 opens the debate + votes.
    a = qc.QualityConsensus(state_dir=tmp)
    sid = a.get_or_create_session(artifact_id="item-1", team_id="t", required_reviewers=2)
    a.submit_review(session_id=sid, reviewer_id="gemini", vote=qc.VoteType.APPROVE, confidence=0.8)

    # Instance B (separate process): must see the SAME session by artifact id, add vote 2.
    b = qc.QualityConsensus(state_dir=tmp)
    sid_b = b.get_or_create_session(artifact_id="item-1", team_id="t", required_reviewers=2)
    if sid_b != sid:
        _fail(f"cross-instance session not reused: {sid} != {sid_b}")
    sess = b.active_sessions[sid_b]
    if len(sess.reviews) != 1:
        _fail(f"reloaded session lost review (have {len(sess.reviews)})")
    if not isinstance(sess.reviews[0].vote, qc.VoteType):
        _fail(f"vote not reconstructed as VoteType: {type(sess.reviews[0].vote)}")
    b.submit_review(session_id=sid_b, reviewer_id="codex", vote=qc.VoteType.APPROVE, confidence=0.9)

    # Instance C: decide reaches consensus from the 2 persisted reviews.
    c = qc.QualityConsensus(state_dir=tmp)
    sid_c = next((s for s, ss in c.active_sessions.items() if ss.artifact_id == "item-1"), None)
    if not sid_c:
        _fail("session not found in third instance")
    if len(c.active_sessions[sid_c].reviews) != 2:
        _fail("third instance did not see both reviews")
    result = asyncio.run(c.evaluate_consensus(sid_c))
    if result is None or not hasattr(result, "to_dict"):
        _fail("evaluate_consensus did not return a ConsensusResult")

    print("PASS: cross-process consensus persistence + VoteType round-trip + decide "
          f"(session={sid[:8]}, reviews=2)")


if __name__ == "__main__":
    main()
