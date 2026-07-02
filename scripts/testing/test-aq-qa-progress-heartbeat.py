#!/usr/bin/env python3
"""Static regression checks for aq-qa rolling progress artifacts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AQ_QA = ROOT / "scripts/ai/aq-qa"
AQ_QA_BASH = ROOT / "scripts/ai/_aq-qa-bash"
QA = ROOT / "scripts/ai/_aq-qa-bash"
TIER0 = ROOT / "scripts/governance/tier0-validation-gate.sh"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    wrapper = AQ_QA.read_text(encoding="utf-8")
    bash = AQ_QA_BASH.read_text(encoding="utf-8")
    qa = QA.read_text(encoding="utf-8")
    tier0 = TIER0.read_text(encoding="utf-8")

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
    require("_check_timeout()" in bash, "runner must provide bounded checks for high-risk probes")
    require("_systemd_unit_state()" in bash, "bash QA must use systemctl show fallback")
    require("_tcp_port_open()" in bash, "bash QA must use socket port checks before ss fallback")
    require("_http_get()" in bash, "bash QA must provide Python HTTP fallback for curl probe failures")
    require("_check_http_output()" in bash, "bash QA must provide HTTP output checks with sandbox-denial handling")
    require('body="$(_http_get "$url" 5)"' in bash, "HTTP health checks must use fallback HTTP getter")
    require("HTTP probe denied in current sandbox" in bash, "HTTP probe denials must be explicit skips")
    require('_check_http_output 7 "0.5.1"' in bash, "switchboard profile checks must use HTTP output helper")
    require("host port probe denied in current sandbox" in bash, "port probe denials must be explicit skips")
    require("systemd probe denied in current sandbox" in bash, "systemd probe denials must be explicit skips")
    require('"switchboard exposes local-agent profile"' in bash, "0.5.1 must check current local-agent ingress")
    require('"Continue extension health gate" "retired' in bash, "retired Continue extension gate must be skipped")
    require("AQ_QA_FLAGSHIP_CLI_SURFACE_TIMEOUT_SECONDS" in bash, "flagship CLI aggregate timeout knob missing")
    require('_check_timeout 7 "0.6.1"' in bash, "flagship CLI smoke must be bounded")
    require("AQ_QA_DISCOVERY_OPPORTUNITY_TIMEOUT_SECONDS" in bash, "discovery scanner timeout knob missing")
    require('_check_timeout 1 "0.10.4"' in bash, "discovery scanner check must be bounded")
    require('if python3 -c "' in bash and 'push(\'qa-check\',\'low\',\'auto_ok\'' in bash,
            "attention queue QA probe must be guarded under set -e")
    require("0.10.33" in qa, "phase-0 QA missing heartbeat regression check")
    require("log_failed_qa_rows()" in tier0, "tier0 must summarize failed QA rows")
    require('log_failed_qa_rows "$output" 30' in tier0, "tier0 phase-0 failure path must log failed rows")

    print("ok aq-qa progress heartbeat wiring")


if __name__ == "__main__":
    main()
