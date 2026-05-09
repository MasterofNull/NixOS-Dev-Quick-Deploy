#!/usr/bin/env bash
# Purpose: Validate aq-feedback-loop output contract.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOL="${ROOT_DIR}/scripts/ai/aq-feedback-loop"
TMP_JSON="$(mktemp)"
TMP_FEEDBACK="$(mktemp)"
trap 'rm -f "${TMP_JSON}" "${TMP_FEEDBACK}"' EXIT

cat > "${TMP_FEEDBACK}" <<'EOF'
The agent reports context pressure, health-gate needs, noisy memory writes, and
asks for a standardized remote task JSON schema.
EOF

python3 "${TOOL}" \
  --task "act on local agent feedback for context injection, health gating, remote task schema, and evidence-first introspection" \
  --feedback-file "${TMP_FEEDBACK}" \
  --format json > "${TMP_JSON}"

python3 - "${TMP_JSON}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

if payload.get("recommended_scope") != "context-offload":
    print("ERROR: feedback loop did not prefer context-offload scope", file=sys.stderr)
    raise SystemExit(1)

artifacts = payload.get("artifact_paths", {})
if not artifacts.get("prd", "").endswith("LOCAL-AGENT-FEEDBACK-EXECUTION-LOOP-PRD-2026-05.md"):
    print("ERROR: feedback loop did not expose the expected PRD path", file=sys.stderr)
    raise SystemExit(1)
if not artifacts.get("plan", "").endswith("phase-29-feedback-driven-agent-loop.md"):
    print("ERROR: feedback loop did not expose the expected plan path", file=sys.stderr)
    raise SystemExit(1)

workstreams = {item["id"] for item in payload.get("workstreams", [])}
expected = {
    "context-injection-preflight",
    "health-gated-execution",
    "remote-task-schema",
    "evidence-first-introspection",
}
if workstreams != expected:
    print("ERROR: feedback loop workstreams drifted", file=sys.stderr)
    raise SystemExit(1)

signals = set(payload.get("feedback_signals", []))
for signal in ("context-pressure", "health-gating", "memory-discipline", "remote-contracts"):
    if signal not in signals:
        print(f"ERROR: feedback signal missing: {signal}", file=sys.stderr)
        raise SystemExit(1)

starter_commands = payload.get("starter_commands", [])
for command in ("aq-context-bootstrap", "aq-qa 0 --json", "aq-report --since=1h --format=json", "aq-context-manage checkpoint"):
    if not any(command in item for item in starter_commands):
        print(f"ERROR: starter command missing: {command}", file=sys.stderr)
        raise SystemExit(1)
assist_profiles = payload.get("context_assist_profiles", [])
if assist_profiles != ["embedded-assist"]:
    print("ERROR: feedback loop did not surface embedded-assist as the compact helper lane", file=sys.stderr)
    raise SystemExit(1)

preflight = payload.get("preflight_commands", [])
if not preflight:
    print("ERROR: feedback loop did not emit explicit preflight commands", file=sys.stderr)
    raise SystemExit(1)
if preflight[0].startswith("aq-context-bootstrap"):
    print("ERROR: feedback loop did not prioritize continuation recall ahead of generic bootstrap", file=sys.stderr)
    raise SystemExit(1)
for command in ("aq-qa 0 --json", "aq-report --since=1h --format=json", "aq-memory search", "aq-context-manage summary", "aq-context-manage check"):
    if not any(command in item for item in preflight):
        print(f"ERROR: preflight command missing: {command}", file=sys.stderr)
        raise SystemExit(1)

phases = [item.get("phase") for item in payload.get("execution_loop", [])]
if not phases or phases[0] != "preflight":
    print("ERROR: feedback loop did not make preflight the first execution phase", file=sys.stderr)
    raise SystemExit(1)

validation = payload.get("validation_commands", [])
if "python3 scripts/testing/check-feedback-loop.sh" not in validation:
    print("ERROR: validation contract missing self-check", file=sys.stderr)
    raise SystemExit(1)

print("PASS: feedback loop validated")
PY
