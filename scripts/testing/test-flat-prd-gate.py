#!/usr/bin/env python3
"""Regression checks for the flat model-team PRD gate."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts" / "ai" / "aq-flat-prd-gate"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_gate(*args: str, repo_root: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(GATE), "--repo-root", str(repo_root), "--machine", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def write(path: Path, text: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_repo_gate_installed() -> None:
    proc = run_gate()
    assert_true(proc.returncode == 0, proc.stdout + proc.stderr)
    payload = json.loads(proc.stdout)
    assert_true(payload["ok"] is True, "repo-level flat PRD gate should pass")
    assert_true(payload["feature_flags"]["multi_agent_collaboration"] is True, "local-agent collaboration flag should be enabled")
    assert_true(payload["feature_flags"]["collaborative_workflows"] is True, "workflow collaboration flag should be enabled")
    assert_true("proposal_candidate" in payload["modes_supported"], "mode detector should expose proposal_candidate")
    assert_true("consensus_synthesis" in payload["modes_supported"], "mode detector should expose consensus_synthesis")


def test_topic_gate_blocks_missing_consensus() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / ".agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md", (ROOT / ".agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md").read_text(encoding="utf-8"))
        write(repo / ".agents/prompts/GEMINI_WORKFLOW_REMEDIATION_HANDOFF.md")
        write(repo / "config/local-agent-config.yaml", "multi_agent_collaboration: true\n")
        write(repo / "config/workflow-automation.yaml", "collaborative_workflows: true\n")
        write(repo / ".agents/plans/model-proposals/tokenomics/codex-proposal.md")

        proc = run_gate("--topic", "tokenomics", repo_root=repo)
        assert_true(proc.returncode == 1, "single proposal with no reviews/consensus must fail")
        payload = json.loads(proc.stdout)
        assert_true(any("expected >=2 independent proposals" in item for item in payload["failures"]), "proposal count failure expected")


def test_topic_gate_accepts_consensus_package() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / ".agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md", (ROOT / ".agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md").read_text(encoding="utf-8"))
        write(repo / ".agents/prompts/GEMINI_WORKFLOW_REMEDIATION_HANDOFF.md")
        write(repo / "config/local-agent-config.yaml", "multi_agent_collaboration: true\n")
        write(repo / "config/workflow-automation.yaml", "collaborative_workflows: true\n")
        write(repo / ".agents/plans/model-proposals/tokenomics/codex-proposal.md")
        write(repo / ".agents/plans/model-proposals/tokenomics/local-proposal.md")
        write(repo / ".agents/plans/model-proposals/tokenomics/reviews/codex-on-local.md")
        write(repo / ".agents/plans/model-proposals/tokenomics/reviews/local-on-codex.md")
        write(repo / ".agents/plans/tokenomics-CONSENSUS-PRD.md")
        write(repo / ".agents/plans/tokenomics-SLICE-BACKLOG.md")
        write(repo / ".agents/plans/tokenomics-DECISION-LOG.md")

        proc = run_gate("--topic", "tokenomics", repo_root=repo)
        assert_true(proc.returncode == 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        assert_true(payload["topic"]["proposal_count"] == 2, "proposal count should be recorded")
        assert_true(payload["topic"]["review_count"] == 2, "review count should be recorded")
        assert_true(
            all(mode in payload["topic"]["modes"].values() for mode in ("proposal_candidate", "cross_review", "consensus_synthesis")),
            "topic mode detector should classify proposals, reviews, and synthesis artifacts",
        )


def test_repo_gate_blocks_disabled_rollout_flags() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / ".agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md", (ROOT / ".agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md").read_text(encoding="utf-8"))
        write(repo / ".agents/prompts/GEMINI_WORKFLOW_REMEDIATION_HANDOFF.md")
        write(repo / "config/local-agent-config.yaml", "multi_agent_collaboration: false\n")
        write(repo / "config/workflow-automation.yaml", "collaborative_workflows: false\n")

        proc = run_gate(repo_root=repo)
        assert_true(proc.returncode == 1, "disabled rollout flags must fail once flat collaboration is enabled")
        payload = json.loads(proc.stdout)
        assert_true(any("multi_agent_collaboration must be true" in item for item in payload["failures"]), "local flag failure expected")
        assert_true(any("collaborative_workflows must be true" in item for item in payload["failures"]), "workflow flag failure expected")


def test_topic_gate_blocks_self_review() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        write(repo / ".agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md", (ROOT / ".agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md").read_text(encoding="utf-8"))
        write(repo / ".agents/prompts/GEMINI_WORKFLOW_REMEDIATION_HANDOFF.md")
        write(repo / "config/local-agent-config.yaml", "multi_agent_collaboration: true\n")
        write(repo / "config/workflow-automation.yaml", "collaborative_workflows: true\n")
        write(repo / ".agents/plans/model-proposals/tokenomics/codex-proposal.md")
        write(repo / ".agents/plans/model-proposals/tokenomics/local-proposal.md")
        write(repo / ".agents/plans/model-proposals/tokenomics/reviews/codex-on-codex.md")
        write(repo / ".agents/plans/model-proposals/tokenomics/reviews/local-on-codex.md")
        write(repo / ".agents/plans/tokenomics-CONSENSUS-PRD.md")
        write(repo / ".agents/plans/tokenomics-SLICE-BACKLOG.md")
        write(repo / ".agents/plans/tokenomics-DECISION-LOG.md")

        proc = run_gate("--topic", "tokenomics", repo_root=repo)
        assert_true(proc.returncode == 1, "self-review must fail")
        payload = json.loads(proc.stdout)
        assert_true(any("self-review is not allowed" in item for item in payload["failures"]), "self-review failure expected")


def main() -> int:
    test_repo_gate_installed()
    test_topic_gate_blocks_missing_consensus()
    test_topic_gate_accepts_consensus_package()
    test_repo_gate_blocks_disabled_rollout_flags()
    test_topic_gate_blocks_self_review()
    print("PASS: flat PRD gate enforces proposal/review/consensus artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
