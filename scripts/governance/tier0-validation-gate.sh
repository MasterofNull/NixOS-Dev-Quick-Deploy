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

# Gate 4: Repo structure validation
gate_repo_structure() {
  log "Checking repo structure..."
  if "${SCRIPT_DIR}/repo-structure-lint.sh" --staged 2>&1 | grep -q "PASS"; then
    pass "Repo structure valid"
  else
    fail "Repo structure violations detected"
    return 1
  fi
}

# Gate 5: Roadmap verification
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

# Gate 6: QA phase 0
gate_qa_phase0() {
  log "Running QA phase 0..."
  local output
  local passes
  output=$("${REPO_ROOT}/scripts/ai/aq-qa" 0 2>&1)
  if echo "$output" | grep -qE "[0-9]+ passed.*0 failed"; then
    passes=$(echo "$output" | grep -oE '[0-9]+ passed' | head -1 | awk '{print $1}')
    pass "QA phase 0 (${passes:-unknown} checks)"
  else
    log "Debug output: $(echo "$output" | tail -3)"
    fail "QA phase 0 failed"
    return 1
  fi
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

log "=== Tier 0 Validation Gate ==="
log "Mode: ${MODE}"
log ""

# Always-run gates
gate_python_syntax || true
gate_bash_syntax || true
gate_nix_syntax || true
gate_repo_structure || true
gate_roadmap_verification || true
gate_qa_phase0 || true

# Pre-deploy gates
if [[ "$MODE" == "--pre-deploy" ]]; then
  gate_deploy_batch_size || true
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
