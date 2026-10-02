#!/usr/bin/env python3
"""aq-approval-ask-hook forces a prompt for owner-decision commands only."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parents[2] / "scripts" / "ai" / "aq-approval-ask-hook"

ASK = [
    "scripts/ai/aq-approve approve 1 3 --tag abc --door chat",
    "cd /repo && aq-approve dismiss 4 --tag abc",
    "aq-approve deny 2 --tag abc",
    "aq-approve attn-1234abcd",
    "/repo/scripts/automation/prsi-orchestrator.py verify --id x --by owner",
    "python3 scripts/automation/prsi-orchestrator.py approve --id x --by owner",
    "aq-rsi approve --bind x",
    "python3 scripts/automation/prsi-orchestrator.py rsi-requeue --id x",
]
PASS = ["aq-approve", "aq-approve --summary", "aq-approve list --json", "prsi-orchestrator.py list", "true"]


def decision(command: str, log: str) -> str:
    out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"tool_input": {"command": command}}),
                         capture_output=True, text=True, env=dict(os.environ, AQ_APPROVAL_HOOK_LOG=log)).stdout.strip()
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else "pass"


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        log = str(Path(tmp) / "hook.log")
        bad = [c for c in ASK if decision(c, log) != "ask"] + [c for c in PASS if decision(c, log) != "pass"]
        fired = len(Path(log).read_text().splitlines())
    if bad or fired != len(ASK):
        print(f"FAIL: misclassified {bad}; fired={fired}/{len(ASK)}")
        return 1
    print("PASS: approval ask-hook prompts for owner decisions only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
