#!/usr/bin/env python3
"""Static regression checks for aq-qa rolling progress artifacts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQ_QA = ROOT / "scripts/ai/aq-qa"
AQ_QA_BASH = ROOT / "scripts/ai/_aq-qa-bash"
QA = ROOT / "scripts/ai/_aq-qa-bash"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    wrapper = AQ_QA.read_text(encoding="utf-8")
    bash = AQ_QA_BASH.read_text(encoding="utf-8")
    qa = QA.read_text(encoding="utf-8")

    require("AQ_QA_PROGRESS_JSON" in wrapper, "wrapper must export progress JSON path")
    require("AQ_QA_PROGRESS_JSONL" in wrapper, "wrapper must export progress JSONL path")
    require('${REPO_ROOT}/.agent/qa' in wrapper, "default progress dir must be writable agent state")
    require("_qa_progress_emit" in bash, "bash runner missing progress emitter")
    require("import agent_run_events as events" in bash, "bash progress emitter must use canonical agent-run events")
    require('events.emit_event(' in bash, "bash progress emitter must append canonical validation events")
    require('"validation"' in bash, "QA progress must be emitted as validation events")
    require("_qa_progress_start" in bash, "bash runner missing progress start")
    require("_qa_progress_stop" in bash, "bash runner missing progress stop")
    require('"phase_start" "$LAYER_FILTER" "$PHASE"' in bash, "runner must emit phase_start immediately")
    require("AQ_QA_PROGRESS_HEARTBEAT_SECONDS" in bash, "missing heartbeat interval knob")
    require("_qa_progress_start \"$layer\" \"$id\" \"$desc\"" in bash, "_check must start progress")
    require("0.10.33" in qa, "phase-0 QA missing heartbeat regression check")

    print("ok aq-qa progress heartbeat wiring")


if __name__ == "__main__":
    main()
