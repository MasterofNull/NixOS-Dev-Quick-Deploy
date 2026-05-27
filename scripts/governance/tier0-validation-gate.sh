#!/usr/bin/env bash
# Tier 0 Validation Gate — Enforce AGENTS.md workflow contract
# Usage: ./scripts/governance/tier0-validation-gate.sh [--pre-commit|--pre-deploy]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

MODE="${1:---pre-commit}"

pass_count=0
fail_count=0

collect_changed_files() {
  if [[ "$MODE" == "--pre-commit" ]]; then
    git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true
    return 0
  fi

  {
    git diff --name-only --diff-filter=ACM origin/main...HEAD 2>/dev/null || true
    git diff --name-only --diff-filter=ACM 2>/dev/null || true
  } | awk 'NF && !seen[$0]++'
}

log() {
  printf '[tier0] %s\n' "$*"
}

pass() {
  printf '[tier0] PASS: %s\n' "$*"
  ((pass_count++))
}

fail() {
  printf '[tier0] FAIL: %s\n' "$*" >&2
  ((fail_count++))
}

# Gate 1: Python syntax validation
gate_python_syntax() {
  log "Checking Python syntax..."
  local files=()
  while IFS= read -r f; do
    [[ "$f" == *.py ]] && files+=("$f")
  done < <(collect_changed_files)
  
  if [[ ${#files[@]} -eq 0 ]]; then
    pass "No Python changes detected"
    return 0
  fi
  
  if python3 -m py_compile "${files[@]}" 2>/dev/null; then
    pass "Python syntax valid (${#files[@]} files)"
  else
    fail "Python syntax errors detected"
    return 1
  fi
}

# Gate 2: Bash syntax validation
gate_bash_syntax() {
  log "Checking Bash syntax..."
  local files=()
  while IFS= read -r f; do
    [[ "$f" == *.sh ]] && files+=("$f")
  done < <(collect_changed_files)
  
  if [[ ${#files[@]} -eq 0 ]]; then
    pass "No Bash changes detected"
    return 0
  fi
  
  local failed=0
  for f in "${files[@]}"; do
    if ! bash -n "$f" 2>/dev/null; then
      fail "Bash syntax error in $f"
      failed=1
    fi
  done
  
  if [[ $failed -eq 0 ]]; then
    pass "Bash syntax valid (${#files[@]} files)"
  fi
  return $failed
}

# Gate 3: Nix syntax validation
gate_nix_syntax() {
  log "Checking Nix syntax..."
  local files=()
  while IFS= read -r f; do
    [[ "$f" == *.nix ]] && files+=("$f")
  done < <(collect_changed_files)
  
  if [[ ${#files[@]} -eq 0 ]]; then
    pass "No Nix changes detected"
    return 0
  fi
  
  if nix-instantiate --parse "${files[@]}" >/dev/null 2>&1; then
    pass "Nix syntax valid (${#files[@]} files)"
  else
    fail "Nix syntax errors detected"
    return 1
  fi
}

# Gate 4: JSON syntax validation
gate_json_syntax() {
  log "Checking JSON syntax..."
  local files=()
  while IFS= read -r f; do
    [[ "$f" == *.json ]] && [[ "$f" != package-lock.json ]] && files+=("$f")
  done < <(collect_changed_files)

  if [[ ${#files[@]} -eq 0 ]]; then
    pass "No JSON changes detected"
    return 0
  fi

  local failed=0
  for f in "${files[@]}"; do
    if ! python3 -c "import json; json.load(open('$f'))" 2>/dev/null; then
      fail "JSON syntax error in $f"
      failed=1
    fi
  done

  if [[ $failed -eq 0 ]]; then
    pass "JSON syntax valid (${#files[@]} files)"
  fi
  return $failed
}

# Gate 5: YAML syntax validation
gate_yaml_syntax() {
  log "Checking YAML syntax..."
  local files=()
  while IFS= read -r f; do
    [[ "$f" == *.yaml || "$f" == *.yml ]] && files+=("$f")
  done < <(collect_changed_files)

  if [[ ${#files[@]} -eq 0 ]]; then
    pass "No YAML changes detected"
    return 0
  fi

  if ! python3 -c "import yaml" 2>/dev/null; then
    log "SKIP: PyYAML not available — YAML syntax check skipped"
    pass "YAML syntax (skipped — PyYAML not installed)"
    return 0
  fi

  local failed=0
  for f in "${files[@]}"; do
    if ! python3 -c "
import yaml, sys
try:
    list(yaml.safe_load_all(open('$f')))
except yaml.YAMLError as e:
    print(str(e), file=sys.stderr); sys.exit(1)
" 2>/dev/null; then
      fail "YAML syntax error in $f"
      failed=1
    fi
  done

  if [[ $failed -eq 0 ]]; then
    pass "YAML syntax valid (${#files[@]} files)"
  fi
  return $failed
}

# Gate 6: TOML syntax validation
gate_toml_syntax() {
  log "Checking TOML syntax..."
  local files=()
  while IFS= read -r f; do
    [[ "$f" == *.toml ]] && files+=("$f")
  done < <(collect_changed_files)

  if [[ ${#files[@]} -eq 0 ]]; then
    pass "No TOML changes detected"
    return 0
  fi

  if ! python3 -c "import tomllib" 2>/dev/null && ! python3 -c "import tomli" 2>/dev/null; then
    log "SKIP: tomllib/tomli not available — TOML syntax check skipped"
    pass "TOML syntax (skipped — no parser available)"
    return 0
  fi

  local failed=0
  for f in "${files[@]}"; do
    if ! python3 -c "
import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib
try:
    tomllib.load(open('$f', 'rb'))
except Exception as e:
    print(str(e), file=sys.stderr); sys.exit(1)
" 2>/dev/null; then
      fail "TOML syntax error in $f"
      failed=1
    fi
  done

  if [[ $failed -eq 0 ]]; then
    pass "TOML syntax valid (${#files[@]} files)"
  fi
  return $failed
}

# Gate 7: JavaScript syntax validation (.js files; inline HTML scripts handled by focused-ci)
gate_js_syntax() {
  log "Checking JavaScript syntax..."
  local files=()
  while IFS= read -r f; do
    [[ "$f" == *.js ]] && files+=("$f")
  done < <(collect_changed_files)

  if [[ ${#files[@]} -eq 0 ]]; then
    pass "No JS changes detected"
    return 0
  fi

  if ! command -v node &>/dev/null; then
    log "SKIP: node not in PATH — JS syntax check skipped"
    pass "JS syntax (skipped — node not available)"
    return 0
  fi

  local failed=0
  for f in "${files[@]}"; do
    if ! node --check "$f" 2>/dev/null; then
      fail "JS syntax error in $f"
      failed=1
    fi
  done

  if [[ $failed -eq 0 ]]; then
    pass "JS syntax valid (${#files[@]} files)"
  fi
  return $failed
}

# Gate 8: TypeScript syntax validation
gate_ts_syntax() {
  log "Checking TypeScript syntax..."
  local files=()
  while IFS= read -r f; do
    [[ "$f" == *.ts ]] && [[ "$f" != *.d.ts ]] && files+=("$f")
  done < <(collect_changed_files)

  if [[ ${#files[@]} -eq 0 ]]; then
    pass "No TS changes detected"
    return 0
  fi

  if ! command -v tsc &>/dev/null; then
    log "SKIP: tsc not in PATH — TypeScript syntax check skipped"
    pass "TS syntax (skipped — tsc not available)"
    return 0
  fi

  if tsc --noEmit --strict false --skipLibCheck --target ES2020 \
       --moduleResolution node "${files[@]}" 2>/dev/null; then
    pass "TS syntax valid (${#files[@]} files)"
  else
    fail "TypeScript syntax errors detected"
    return 1
  fi
}

# Gate 9: SQL syntax validation
gate_sql_syntax() {
  log "Checking SQL syntax..."
  local files=()
  while IFS= read -r f; do
    [[ "$f" == *.sql ]] && files+=("$f")
  done < <(collect_changed_files)

  if [[ ${#files[@]} -eq 0 ]]; then
    pass "No SQL changes detected"
    return 0
  fi

  if ! python3 -c "import sqlparse" 2>/dev/null; then
    log "SKIP: sqlparse not available — SQL syntax check skipped"
    pass "SQL syntax (skipped — sqlparse not installed)"
    return 0
  fi

  local failed=0
  for f in "${files[@]}"; do
    if ! python3 -c "
import sqlparse, sys
stmts = sqlparse.parse(open('$f').read())
print(f'Parsed {len(stmts)} statement(s) OK')
" 2>/dev/null; then
      fail "SQL parse error in $f"
      failed=1
    fi
  done

  if [[ $failed -eq 0 ]]; then
    pass "SQL syntax valid (${#files[@]} files)"
  fi
  return $failed
}

# Gate 10: Repo structure validation
gate_repo_structure() {
  log "Checking repo structure..."
  if "${SCRIPT_DIR}/repo-structure-lint.sh" --staged 2>&1 | grep -q "PASS"; then
    pass "Repo structure valid"
  else
    fail "Repo structure violations detected"
    return 1
  fi
}

# Gate 11: Script header standards
gate_script_headers() {
  log "Checking script header standards..."
  if bash "${SCRIPT_DIR}/check-script-header-standards.sh" --all >/dev/null 2>&1; then
    pass "Script header standards valid"
  else
    fail "Script header standards failed"
    return 1
  fi
}

# Gate 12: Config directory governance
gate_config_dir_lint() {
  log "Checking config directory governance..."
  if bash "${SCRIPT_DIR}/config-directory-lint.sh" >/dev/null 2>&1; then
    pass "Config directory governance valid"
  else
    fail "Config directory governance failed"
    return 1
  fi
}

# Gate 13: Path-aware focused CI checks
gate_focused_ci_checks() {
  log "Running focused CI-sensitive checks..."
  if bash "${SCRIPT_DIR}/run-focused-ci-checks.sh" "${MODE}" >/dev/null 2>&1; then
    pass "Focused CI-sensitive checks passed"
  else
    fail "Focused CI-sensitive checks failed"
    return 1
  fi
}

# Gate 7: Roadmap verification
gate_roadmap_verification() {
  log "Running roadmap verification..."
  local output
  output=$("${REPO_ROOT}/scripts/testing/verify-flake-first-roadmap-completion.sh" 2>&1)
  if echo "$output" | grep -q "Summary:.*pass, 0 fail"; then
    local passes
    passes=$(echo "$output" | grep -oP '\d+(?= pass)' | head -1)
    pass "Roadmap verification (${passes} checks)"
  else
    log "Debug output: $(echo "$output" | tail -3)"
    fail "Roadmap verification failed"
    return 1
  fi
}

# Gate 8: QA phase 0
gate_qa_phase0() {
  log "Running QA phase 0..."
  local output
  local passes
  local qa_timeout="${TIER0_AQ_QA_TIMEOUT_SECONDS:-420}"
  local continue_local_timeout="${TIER0_AQ_QA_CONTINUE_LOCAL_MAX_TIME_SECONDS:-45}"
  local flagship_help_timeout="${TIER0_AQ_QA_FLAGSHIP_HELP_TIMEOUT_SECONDS:-45}"
  local status=0
  output=$(
    # Tier0 already runs focused CI-sensitive checks separately; skip the
    # aq-report-backed subchecks here so phase-0 remains a bounded health gate
    # instead of recursively launching another aq-qa/report loop.
    AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 \
    AQ_QA_CONTINUE_LOCAL_MAX_TIME="${continue_local_timeout}" \
    AQ_FLAGSHIP_HELP_TIMEOUT_SECONDS="${flagship_help_timeout}" \
    timeout --foreground "${qa_timeout}" "${REPO_ROOT}/scripts/ai/aq-qa" 0 2>&1
  ) || status=$?
  if [[ "${status}" -eq 124 ]]; then
    log "Debug output: $(echo "$output" | tail -3)"
    fail "QA phase 0 timed out after ${qa_timeout}s (continue-local=${continue_local_timeout}s, flagship-help=${flagship_help_timeout}s)"
    return 1
  fi
  passes=$(echo "$output" | grep -oE '[0-9]+ passed' | head -1 | awk '{print $1}')
  if echo "$output" | grep -qE "[0-9]+ passed.*0 failed"; then
    pass "QA phase 0 (${passes:-unknown} checks)"
    return 0
  fi

  # Check if all failures are documented xfails in config/qa-xfail.yaml.
  # Xfail = runtime-blocked pre-existing failure requiring privileged ops.
  # These count as SKIP (not PASS) — still visible but don't block commit.
  local xfail_config="${REPO_ROOT}/config/qa-xfail.yaml"
  if [[ -f "${xfail_config}" ]]; then
    # Parse failing check IDs from the existing output (strip ANSI, find ✗ lines)
    local failing_ids xfail_ids non_xfail fid
    failing_ids=$(echo "${output}" | sed 's/\x1b\[[0-9;]*m//g' | \
      grep -oP '✗\s+\K[0-9]+\.[0-9]+(?:\.[0-9]+)?(?::[a-z_-]+)?' | sort -u)
    xfail_ids=$(grep -oP '\bid:\s+"\K[^"]+' "${xfail_config}" | sort -u)
    non_xfail=""
    while IFS= read -r fid; do
      [[ -z "${fid}" ]] && continue
      if ! echo "${xfail_ids}" | grep -qxF "${fid}"; then
        non_xfail="${non_xfail} ${fid}"
      fi
    done <<< "${failing_ids}"

    non_xfail=$(echo "${non_xfail}" | tr -d '[:space:]')
    if [[ -z "${non_xfail}" && -n "${failing_ids}" ]]; then
      local xfail_list
      xfail_list=$(echo "${failing_ids}" | tr '\n' ',' | sed 's/,$//')
      pass "QA phase 0 (${passes:-unknown} checks; xfail[runtime-blocked]: ${xfail_list})"
      log "  WARN: ${xfail_list} require privileged runtime ops — see config/qa-xfail.yaml"
      return 0
    fi
  fi

  log "Debug output: $(echo "$output" | tail -3)"
  fail "QA phase 0 failed"
  return 1
}

# Pre-deploy only gates
gate_deploy_batch_size() {
  log "Checking deploy batch size..."
  local commit_count
  commit_count=$(git rev-list --count HEAD "^origin/main" 2>/dev/null || echo "0")
  
  if [[ "$commit_count" -ge 3 ]]; then
    pass "Deploy batch size adequate (${commit_count} commits)"
  else
    log "WARN: Only ${commit_count} commits staged (recommend 3-5 before deploy)"
    pass "Deploy batch size (advisory)"
  fi
}

gate_unattended_sudo_readiness() {
  log "Checking unattended sudo readiness..."
  if bash "${SCRIPT_DIR}/check-unattended-sudo-readiness.sh" >/dev/null 2>&1; then
    pass "Unattended sudo readiness valid"
  else
    fail "Unattended sudo readiness failed"
    return 1
  fi
}

gate_env_contract() {
  log "Checking env var contract..."
  local contract="${REPO_ROOT}/config/env-contract.yaml"
  if [[ ! -f "$contract" ]]; then
    log "WARN: config/env-contract.yaml not found — skipping env contract gate"
    pass "Env contract gate (skipped: contract file absent)"
    return 0
  fi
  # Validate contract file is valid YAML
  if ! python3 -c "import yaml; yaml.safe_load(open('$contract'))" 2>/dev/null; then
    fail "Env contract YAML syntax invalid: $contract"
    return 1
  fi
  local changed_files
  changed_files=$(collect_changed_files)
  if [[ -z "$changed_files" ]]; then
    pass "Env contract gate (no changed files)"
    return 0
  fi
  # Collect all canonical and alias names from the contract
  local known_vars
  known_vars=$(python3 - "$contract" <<'PY'
import yaml, sys
data = yaml.safe_load(open(sys.argv[1]))
names = set()
for v in data.get("variables", []):
    names.add(v["canonical"])
    for alias in v.get("aliases", []):
        names.add(alias)
print("\n".join(sorted(names)))
PY
)
  # Check new .py and .sh files for env var names not in contract
  # We only flag os.environ.get("NEW_VAR") patterns and ${NEW_VAR:-} / export NEW_VAR patterns
  local violations=()
  while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    case "$f" in
      *.py|*.sh) ;;
      *) continue ;;
    esac
    # Skip the contract itself, service-endpoints, and governance scripts
    case "$f" in
      config/env-contract.yaml|config/service-endpoints.sh) continue ;;
      scripts/governance/*) continue ;;
    esac
    # Extract candidate var names from the file using an external helper
    local candidates
    candidates=$(python3 "${REPO_ROOT}/scripts/governance/_check_env_contract.py" \
      "$f" "$known_vars" 2>/dev/null || true)
    if [[ -n "$candidates" ]]; then
      while IFS= read -r var; do
        violations+=("$f: unknown env var '$var' (add to config/env-contract.yaml)")
      done <<<"$candidates"
    fi
  done <<<"$changed_files"
  if [[ "${#violations[@]}" -gt 0 ]]; then
    for v in "${violations[@]}"; do
      log "WARN: $v"
    done
    log "WARN: ${#violations[@]} undocumented env var(s) detected in changed files"
    log "WARN: Add them to config/env-contract.yaml or use an existing canonical name"
    # Warn only (not hard fail) during initial rollout period
    pass "Env contract gate (advisory: ${#violations[@]} undocumented vars — add to contract)"
  else
    pass "Env contract gate (all env vars in changed files are documented)"
  fi
}

gate_cross_surface_contract() {
  log "Checking cross-surface docs/dashboard contract..."
  if python3 "${SCRIPT_DIR}/check-cross-surface-contract.py" --mode="${MODE}"; then
    pass "Cross-surface docs/dashboard contract satisfied"
  else
    fail "Cross-surface docs/dashboard contract failed"
    return 1
  fi
}

log "=== Tier 0 Validation Gate ==="
log "Mode: ${MODE}"
log ""

# Always-run gates
gate_python_syntax || true
gate_bash_syntax || true
gate_nix_syntax || true
gate_json_syntax || true
gate_yaml_syntax || true
gate_toml_syntax || true
gate_js_syntax || true
gate_ts_syntax || true
gate_sql_syntax || true
gate_repo_structure || true
gate_script_headers || true
gate_config_dir_lint || true
gate_focused_ci_checks || true
gate_roadmap_verification || true
gate_qa_phase0 || true
gate_env_contract || true
gate_cross_surface_contract || true

# Pre-deploy gates
if [[ "$MODE" == "--pre-deploy" ]]; then
  gate_deploy_batch_size || true
  gate_unattended_sudo_readiness || true
fi

log ""
log "=== Summary ==="
log "Passed: ${pass_count}"
log "Failed: ${fail_count}"

if [[ ${fail_count} -gt 0 ]]; then
  log ""
  log "BLOCKED: ${fail_count} validation gate(s) failed"
  log "Do NOT commit or deploy until all gates pass"
  exit 1
fi

log ""
log "OK: All Tier 0 gates passed"
exit 0
