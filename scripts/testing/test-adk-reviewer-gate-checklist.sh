#!/usr/bin/env bash
# Purpose: verify the ADK discovery workflow generates a reviewer-gate checklist tied to active roadmap phases.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "${ROOT}/lib/adk/implementation-discovery.sh"

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

gaps_file="${tmpdir}/capability-gaps.json"
parity_file="${tmpdir}/parity-scorecard.json"
output_file="${tmpdir}/reviewer-gate-checklist.md"

cat >"${gaps_file}" <<'EOF'
{
  "total_gaps": 2,
  "gaps": [
    {"feature": "Reflect and retry plugin", "priority": "high", "release": "v1.1.0"},
    {"feature": "Session state delta transport", "priority": "medium", "release": "v1.1.0"}
  ]
}
EOF

cat >"${parity_file}" <<'EOF'
{
  "overall_parity": 0.817,
  "categories": {
    "workflow": {
      "capabilities": [
        {"name": "reviewer_gates", "status": "adopted", "notes": "Full reviewer gate integration"},
        {"name": "reflect_retry_plugin", "status": "deferred", "notes": "Candidate for internal retry policy layer"}
      ]
    },
    "observability": {
      "capabilities": [
        {"name": "agent_tool_traces", "status": "adapted", "notes": "Needs canonical trace/eval envelope"}
      ]
    }
  }
}
EOF

generate_reviewer_gate_checklist "${gaps_file}" "${parity_file}" "${output_file}" >/dev/null

grep -q '^# ADK Reviewer-Gate Checklist' "${output_file}"
grep -q 'scripts/testing/smoke-agent-harness-parity.sh' "${output_file}"
grep -q 'scripts/testing/smoke-focused-parity.sh' "${output_file}"
grep -q '\*\*Phase 4\*\*' "${output_file}"
grep -q '\*\*Phase 6\*\*' "${output_file}"
grep -q '\*\*Phase 11\*\*' "${output_file}"
grep -q 'Phase-Scoped Immediate Checks' "${output_file}"
grep -q 'scripts/ai/aq-report --since=1h --format=json' "${output_file}"
grep -q 'scripts/ai/aq-qa 0 --json' "${output_file}"
grep -q 'reflect_retry_plugin' "${output_file}"
grep -q 'agent_tool_traces' "${output_file}"
grep -q 'Reflect and retry plugin' "${output_file}"

echo "PASS: ADK discovery reviewer-gate checklist ties release gaps to roadmap phases and validation commands"
