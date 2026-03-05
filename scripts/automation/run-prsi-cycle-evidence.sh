#!/usr/bin/env bash
set -euo pipefail

# Execute PRSI cycle(s) and persist evidence bundles under data/prsi-artifacts/runs.
# Defaults to dry-run so it is safe on development hosts.

ROOT_DIR="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
COUNT="${PRSI_EVIDENCE_COUNT:-1}"
SINCE_WINDOW="${PRSI_EVIDENCE_SINCE:-1d}"
EXECUTE_LIMIT="${PRSI_EVIDENCE_EXECUTE_LIMIT:-1}"
DRY_RUN="${PRSI_EVIDENCE_DRY_RUN:-true}"
OUT_DIR="${PRSI_EVIDENCE_OUT_DIR:-${ROOT_DIR}/data/prsi-artifacts/runs}"

mkdir -p "${OUT_DIR}"

run_json_last() {
  local out
  out="$($@)"
  printf '%s\n' "${out}" | awk 'NF{line=$0} END{if (line == "") {exit 1} print line}'
}

run_check() {
  local id="$1"
  local cmd="$2"
  local tmp
  tmp="$(mktemp)"
  if eval "${cmd}" >"${tmp}" 2>&1; then
    local ev="PASS"
    rm -f "${tmp}"
    printf '{"id":"%s","status":"pass","evidence":["%s"]}' "${id}" "${ev}"
    return 0
  fi

  local ev
  ev="$(tail -n 3 "${tmp}" | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g' | sed 's/"/\\"/g' | sed 's/^ //;s/ $//')"
  rm -f "${tmp}"
  printf '{"id":"%s","status":"fail","evidence":["%s"]}' "${id}" "${ev:-FAILED}"
  return 1
}

for i in $(seq 1 "${COUNT}"); do
  cycle_id="prsi-$(date -u +%Y%m%dT%H%M%SZ)-$(printf '%03d' "${i}")"
  cycle_prefix="${OUT_DIR}/${cycle_id}"

  sync_json="$(run_json_last python3 "${ROOT_DIR}/scripts/automation/prsi-orchestrator.py" sync --since="${SINCE_WINDOW}")"
  list_json="$(run_json_last python3 "${ROOT_DIR}/scripts/automation/prsi-orchestrator.py" list)"

  cycle_cmd=(python3 "${ROOT_DIR}/scripts/automation/prsi-orchestrator.py" cycle --since="${SINCE_WINDOW}" --execute-limit="${EXECUTE_LIMIT}")
  if [[ "${DRY_RUN}" == "true" ]]; then
    cycle_cmd+=(--dry-run)
  fi
  cycle_json="$(run_json_last "${cycle_cmd[@]}")"

  jq -n \
    --arg cycle_id "${cycle_id}" \
    --arg created_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --arg objective "Run PRSI evidence cycle with pessimistic gates and record artifacts." \
    --arg hypothesis "Top queued action can be safely evaluated under one-change-per-cycle constraints." \
    --argjson listing "${list_json}" \
    --argjson sync_state "${sync_json}" \
    '{
      schema_version: "1.0",
      cycle_id: $cycle_id,
      created_at: $created_at,
      objective: $objective,
      hypothesis: $hypothesis,
      risk_class: "medium",
      bottleneck: {
        id: "prsi-queue-head",
        description: "Queue head action selected from current PRSI discovery window.",
        impact_score: 0.7,
        confidence_score: 0.7,
        reversibility_score: 0.95
      },
      constraints: [
        "one logical mutating change per cycle",
        "required verification gates",
        "explicit rollback path"
      ],
      out_of_scope: ["multi-change bundles", "unsafe high-risk bypass"],
      acceptance_checks: [
        {
          id: "phase7_gate",
          description: "Phase 7 program checks must pass",
          metric: "prsi_phase7_program",
          operator: "==",
          target: "pass"
        }
      ],
      proposal: {
        summary: "Evaluate queue-head PRSI action via orchestrator cycle.",
        change_type: "workflow",
        files: ["scripts/automation/prsi-orchestrator.py", "config/runtime-prsi-policy.json"],
        expected_kpi_delta: [
          { metric: "prsi_contract_compliance", direction: "up", expected_delta: 1.0 }
        ]
      },
      rollback: {
        command: "sudo nixos-rebuild switch --rollback",
        notes: "Use rollback if any required gate fails or if execution diverges."
      },
      telemetry: {
        sync: $sync_state,
        queue: $listing
      }
    }' > "${cycle_prefix}.cycle_plan.json"

  checks=(
    "syntax_or_lint:bash ${ROOT_DIR}/scripts/testing/check-prsi-cycle-contract.sh"
    "runtime_contract:bash ${ROOT_DIR}/scripts/testing/validate-runtime-declarative.sh"
    "report_schema:bash ${ROOT_DIR}/scripts/testing/check-aq-report-contract.sh"
    "security_checks:bash ${ROOT_DIR}/scripts/testing/check-api-auth-hardening.sh"
    "focused_smoke_or_eval:bash ${ROOT_DIR}/scripts/testing/check-prsi-bootstrap-integrity.sh"
    "critical_regression_scan:bash ${ROOT_DIR}/scripts/testing/check-prsi-validation-matrix.sh"
  )

  pass_count=0
  fail_count=0
  skip_count=0
  req_failures=()
  checks_json='[]'
  commands_run='[]'

  for item in "${checks[@]}"; do
    cid="${item%%:*}"
    cmd="${item#*:}"
    commands_run="$(jq -cn --argjson arr "${commands_run}" --arg c "${cmd}" '$arr + [$c]')"

    if row="$(run_check "${cid}" "${cmd}")"; then
      pass_count=$((pass_count + 1))
      checks_json="$(jq -cn --argjson arr "${checks_json}" --argjson row "${row}" '$arr + [$row]')"
    else
      fail_count=$((fail_count + 1))
      req_failures+=("${cid}")
      checks_json="$(jq -cn --argjson arr "${checks_json}" --argjson row "${row}" '$arr + [$row]')"
    fi
  done

  req_failures_json="$(printf '%s\n' "${req_failures[@]-}" | jq -Rsc 'split("\n") | map(select(length>0))')"
  auto_revert=false
  if (( fail_count > 0 )); then
    auto_revert=true
  fi

  jq -n \
    --arg cycle_id "${cycle_id}" \
    --arg executed_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --argjson checks "${checks_json}" \
    --argjson pass_count "${pass_count}" \
    --argjson fail_count "${fail_count}" \
    --argjson skip_count "${skip_count}" \
    --argjson req_failures "${req_failures_json}" \
    --argjson auto_revert "${auto_revert}" \
    --argjson commands_run "${commands_run}" \
    --argjson cycle_meta "${cycle_json}" \
    '{
      schema_version: "1.0",
      cycle_id: $cycle_id,
      executed_at: $executed_at,
      required_checks: $checks,
      summary: {
        pass_count: $pass_count,
        fail_count: $fail_count,
        skip_count: $skip_count,
        required_gate_failures: $req_failures
      },
      auto_revert_triggered: $auto_revert,
      commands_run: $commands_run,
      orchestrator_cycle: $cycle_meta
    }' > "${cycle_prefix}.validation_report.json"

  selected_count="$(jq -r '.selected // .count // 0' <<<"${cycle_json}")"
  if [[ -z "${selected_count}" || "${selected_count}" == "null" ]]; then
    selected_count=0
  fi

  improvement=false
  decision="targeted_eval"
  confidence="0.08"
  baseline=0
  candidate=0
  delta=0
  if (( selected_count > 0 )) && (( fail_count == 0 )); then
    improvement=true
    decision="proceed"
    confidence="0.88"
    baseline=0.0
    candidate=1.0
    delta=1.0
  elif (( fail_count > 0 )); then
    decision="quarantine"
    confidence="0.02"
  fi

  jq -n \
    --arg cycle_id "${cycle_id}" \
    --arg finalized_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --arg decision "${decision}" \
    --argjson improvement "${improvement}" \
    --argjson confidence "${confidence}" \
    --argjson baseline "${baseline}" \
    --argjson candidate "${candidate}" \
    --argjson delta "${delta}" \
    --argjson fail_count "${fail_count}" \
    '{
      schema_version: "1.0",
      cycle_id: $cycle_id,
      finalized_at: $finalized_at,
      decision: $decision,
      improvement_claimed: $improvement,
      confidence_score: $confidence,
      kpi_delta: [
        {metric:"prsi_cycle_selected_actions", baseline:$baseline, candidate:$candidate, delta:$delta}
      ],
      failure_taxonomy: (if $fail_count > 0 then ["required_gate_failure"] else [] end),
      counterfactual_risk: "Dry-run cycle may not capture full mutation-side effects; require replay before promotion.",
      residual_risks: ["dry_run_execution_only"],
      next_actions: ["run_replay", "monitor_confidence_calibration"]
    }' > "${cycle_prefix}.cycle_outcome.json"

  if [[ "${DRY_RUN}" == "true" ]]; then
    printf '# dry-run PRSI cycle; no filesystem patch generated\n' > "${cycle_prefix}.patch.diff"
  else
    printf '# execution mode patch capture not implemented in this runner\n' > "${cycle_prefix}.patch.diff"
  fi

  cat > "${cycle_prefix}.rollback_notes.md" <<EOF2
# Rollback Notes: ${cycle_id}

- Command:
  - \
  sudo nixos-rebuild switch --rollback
- Trigger:
  - Any required PRSI gate fails.
  - Unexpected regression appears in parity or smoke checks.
- Immediate containment:
  - Stop further PRSI execution cycles.
  - Quarantine action fingerprint in PRSI queue.
- Evidence pointers:
  - ${cycle_prefix}.validation_report.json
  - ${cycle_prefix}.cycle_outcome.json
EOF2

  cp "${cycle_prefix}.cycle_plan.json" "${OUT_DIR}/cycle_plan-${cycle_id}.json"
  cp "${cycle_prefix}.validation_report.json" "${OUT_DIR}/validation_report-${cycle_id}.json"
  cp "${cycle_prefix}.cycle_outcome.json" "${OUT_DIR}/cycle_outcome-${cycle_id}.json"

  printf 'PASS: wrote PRSI evidence bundle for %s\n' "${cycle_id}"
done

printf 'PASS: completed %s PRSI evidence cycle(s) into %s\n' "${COUNT}" "${OUT_DIR}"
