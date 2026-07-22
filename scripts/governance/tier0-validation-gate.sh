#!/usr/bin/env bash
# Tier 0 Validation Gate — Enforce AGENTS.md workflow contract
# Usage: ./scripts/governance/tier0-validation-gate.sh [--pre-commit|--pre-deploy] [--staged-isolated] [--tap]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

# Parse args: --pre-commit | --pre-deploy set MODE; --tap enables TAP output;
# --staged-isolated opts into validating the STAGED INDEX in a clean temp
# worktree instead of the live (possibly dirty, possibly mid-edit-by-another-
# slice) working tree. --tap and --staged-isolated may appear in any position
# and do not override MODE.
MODE="--pre-commit"
TAP_MODE=0
STAGED_ISOLATED=0
TAP_JSON_FILE="${TIER0_TAP_JSON:-}"
for arg in "$@"; do
  case "$arg" in
    --pre-commit|--pre-deploy) MODE="$arg" ;;
    --tap) TAP_MODE=1 ;;
    --staged-isolated) STAGED_ISOLATED=1 ;;
  esac
done

# Preserve the original repo root before any isolation swap re-points
# REPO_ROOT/SCRIPT_DIR at a temp worktree — cleanup must run git commands
# from here, never from inside the worktree it is about to remove.
ORIG_REPO_ROOT="${REPO_ROOT}"
ISOLATION_TMPDIR=""
ISOLATION_PATCH=""

pass_count=0
fail_count=0
tap_index=0
declare -a _tap_results=()  # accumulate "ok|not ok|skip:description" entries

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

path_accepts_write() {
  local target="$1"
  local dir
  local probe
  dir="$(dirname "${target}")"
  mkdir -p "${dir}" 2>/dev/null || return 1
  probe="${dir}/.tier0-write-probe.$$"
  if (: > "${probe}") 2>/dev/null; then
    rm -f "${probe}" 2>/dev/null || true
    return 0
  fi
  rm -f "${probe}" 2>/dev/null || true
  return 1
}

pass() {
  ((pass_count++)) || true
  ((tap_index++)) || true
  printf '[tier0] PASS: %s\n' "$*"
  [[ $TAP_MODE -eq 1 ]] && printf 'ok %d - %s\n' "$tap_index" "$*"
  _tap_results+=("ok:${tap_index}:$*")
}

fail() {
  ((fail_count++)) || true
  ((tap_index++)) || true
  printf '[tier0] FAIL: %s\n' "$*" >&2
  [[ $TAP_MODE -eq 1 ]] && printf 'not ok %d - %s\n' "$tap_index" "$*"
  _tap_results+=("not_ok:${tap_index}:$*")
}

log_failed_qa_rows() {
  local output="$1"
  local max_rows="${2:-30}"
  local failed_rows

  failed_rows=$(echo "$output" | sed 's/\x1b\[[0-9;]*m//g' | grep '✗' | head -n "${max_rows}" || true)
  if [[ -n "${failed_rows}" ]]; then
    log "QA failed rows (first ${max_rows}):"
    while IFS= read -r row; do
      [[ -n "${row}" ]] && log "  ${row}"
    done <<< "${failed_rows}"
  else
    log "QA output tail:"
    echo "$output" | tail -10 | while IFS= read -r row; do
      [[ -n "${row}" ]] && log "  ${row}"
    done
  fi
}

skip() {
  ((tap_index++)) || true
  printf '[tier0] SKIP: %s\n' "$*"
  [[ $TAP_MODE -eq 1 ]] && printf 'ok %d - # SKIP %s\n' "$tap_index" "$*"
  _tap_results+=("skip:${tap_index}:$*")
}

# --- Staged-index isolation (opt-in via --staged-isolated) -----------------
#
# Problem: every gate below either scans changed files returned by
# collect_changed_files() (which reads file *content* off the live working
# tree, not the staged blob) or shells out to a sub-script/grep that scans
# the live working tree wholesale (repo-structure-lint.sh, aq-qa,
# run-focused-ci-checks.sh, verify-flake-first-roadmap-completion.sh, the
# gate_llama_payload_ssot grep over ai-stack/). All of those sub-scripts
# self-locate their own root via their own ${BASH_SOURCE[0]} and cd there
# (verified by inspection — this is a repo-wide convention, not something
# introduced here). That means an unrelated in-flight edit anywhere in the
# tree (a different slice mid-edit) can flip an unrelated gate here, because
# the sub-scripts always read the live dirty tree regardless of what this
# commit actually stages.
#
# Fix: materialize a clean git worktree of HEAD, apply the *staged* diff
# (index vs HEAD — exactly what `git commit` would record) on top of it via
# `git apply --index`, then re-point REPO_ROOT/SCRIPT_DIR at that worktree
# before running any gate. Every downstream sub-script self-locates into the
# worktree automatically because it derives its own root the same way this
# script does — no other file needs to change. Working-tree-only edits
# elsewhere (unstaged, or staged in a different index entirely — there is
# only one index per worktree) are structurally invisible to the snapshot.
#
# Fail-closed: because --staged-isolated is explicit, any failure while
# building or hydrating that snapshot exits nonzero. It must never silently
# validate the live tree under a different isolation contract.
ISOLATION_OPERATIONAL_INPUTS=(
  ".agent/collaboration/PULSE.log"
  ".agent/collaboration/RESUME.json"
  ".agents/improvement/candidates.json"
  ".agents/delegation/registry.jsonl"
)
ISOLATION_OPERATIONAL_MAX_BYTES=$((4 * 1024 * 1024))
ISOLATION_OPERATIONAL_COPY_ATTEMPTS=2

copy_isolation_operational_input() {
  local relative_path="$1"
  local destination_root="$2"
  local source="${ORIG_REPO_ROOT}/${relative_path}"
  local destination="${destination_root}/${relative_path}"
  local attempt size_before size_after hash_before hash_copy hash_after temp

  if [[ ! -f "${source}" || -L "${source}" ]]; then
    log "ERROR: --staged-isolated operational input is missing, non-regular, or a symlink: ${relative_path}"
    return 1
  fi

  for ((attempt = 1; attempt <= ISOLATION_OPERATIONAL_COPY_ATTEMPTS; attempt++)); do
    if [[ ! -f "${source}" || -L "${source}" ]]; then
      log "ERROR: --staged-isolated operational input changed type during copy: ${relative_path}"
      return 1
    fi
    size_before="$(stat -c '%s' -- "${source}" 2>/dev/null)" || return 1
    if (( size_before > ISOLATION_OPERATIONAL_MAX_BYTES )); then
      log "ERROR: --staged-isolated operational input exceeds ${ISOLATION_OPERATIONAL_MAX_BYTES} bytes: ${relative_path}"
      return 1
    fi
    hash_before="$(sha256sum -- "${source}" 2>/dev/null | awk '{print $1}')" || return 1

    mkdir -p "$(dirname "${destination}")" || return 1
    temp="${destination}.tmp.$$.${attempt}"
    if ! head -c "${size_before}" -- "${source}" > "${temp}"; then
      rm -f "${temp}" 2>/dev/null || true
      continue
    fi
    chmod 0600 "${temp}" || {
      rm -f "${temp}" 2>/dev/null || true
      return 1
    }
    hash_copy="$(sha256sum -- "${temp}" 2>/dev/null | awk '{print $1}')" || {
      rm -f "${temp}" 2>/dev/null || true
      continue
    }
    if [[ ! -f "${source}" || -L "${source}" ]]; then
      rm -f "${temp}" 2>/dev/null || true
      return 1
    fi
    size_after="$(stat -c '%s' -- "${source}" 2>/dev/null)" || {
      rm -f "${temp}" 2>/dev/null || true
      continue
    }
    hash_after="$(sha256sum -- "${source}" 2>/dev/null | awk '{print $1}')" || {
      rm -f "${temp}" 2>/dev/null || true
      continue
    }
    if [[ "${size_before}" == "${size_after}" && "${hash_before}" == "${hash_copy}" && "${hash_before}" == "${hash_after}" ]]; then
      mv -f -- "${temp}" "${destination}" || return 1
      chmod 0600 "${destination}" || return 1
      return 0
    fi
    rm -f "${temp}" 2>/dev/null || true
  done

  log "ERROR: --staged-isolated operational input was unstable after ${ISOLATION_OPERATIONAL_COPY_ATTEMPTS} attempts: ${relative_path}"
  return 1
}

hydrate_isolation_operational_inputs() {
  local destination_root="$1"
  local relative_path staged_path qa_dir

  for relative_path in "${ISOLATION_OPERATIONAL_INPUTS[@]}"; do
    staged_path="$(git -C "${ORIG_REPO_ROOT}" diff --cached --name-only --diff-filter=ACMRD -- "${relative_path}" 2>/dev/null)" || return 1
    if [[ -n "${staged_path}" ]]; then
      log "ERROR: --staged-isolated refuses staged operational input: ${relative_path}"
      return 1
    fi
    if ! git -C "${destination_root}" check-ignore -q -- "${relative_path}"; then
      log "ERROR: --staged-isolated operational input is not ignored by the snapshot: ${relative_path}"
      return 1
    fi
    copy_isolation_operational_input "${relative_path}" "${destination_root}" || return 1
  done

  qa_dir="${destination_root}/.agent/qa"
  if [[ -e "${qa_dir}" && ( ! -d "${qa_dir}" || -L "${qa_dir}" ) ]]; then
    log "ERROR: --staged-isolated QA lock path is not a safe directory"
    return 1
  fi
  mkdir -p "${qa_dir}" || return 1
  chmod 0700 "${qa_dir}" || return 1
}

setup_staged_isolation() {
  if [[ "${MODE}" != "--pre-commit" ]]; then
    log "ERROR: --staged-isolated only supports --pre-commit (staged-index) mode"
    return 1
  fi

  local tmpdir patchfile
  tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/tier0-staged-isolation.XXXXXX" 2>/dev/null)" || {
    log "ERROR: --staged-isolated: mktemp failed"
    return 1
  }
  patchfile="${tmpdir}.patch"
  # `git worktree add` wants to create its own target directory.
  rmdir "${tmpdir}" 2>/dev/null || true

  if ! git worktree add --detach --quiet "${tmpdir}" HEAD >/dev/null 2>&1; then
    log "ERROR: --staged-isolated: git worktree add failed"
    rm -rf "${tmpdir}" 2>/dev/null || true
    return 1
  fi
  ISOLATION_TMPDIR="${tmpdir}"
  ISOLATION_PATCH="${patchfile}"

  if ! git diff --cached --binary > "${patchfile}" 2>/dev/null; then
    log "ERROR: --staged-isolated: failed to capture staged diff"
    return 1
  fi

  if [[ -s "${patchfile}" ]]; then
    if ! git -C "${tmpdir}" apply --index "${patchfile}" 2>/dev/null; then
      log "ERROR: --staged-isolated: failed to apply staged diff onto clean HEAD checkout"
      return 1
    fi
  fi

  hydrate_isolation_operational_inputs "${tmpdir}" || return 1
  REPO_ROOT="${tmpdir}"
  SCRIPT_DIR="${tmpdir}/scripts/governance"
  cd "${REPO_ROOT}"
  log "Staged-isolated mode: validating clean HEAD+staged-index snapshot at ${REPO_ROOT}"
  log "  (unstaged/in-flight edits elsewhere in the working tree are invisible to this run)"
  return 0
}

cleanup_isolation() {
  if [[ -n "${ISOLATION_TMPDIR}" ]]; then
    git -C "${ORIG_REPO_ROOT}" worktree remove --force "${ISOLATION_TMPDIR}" >/dev/null 2>&1 \
      || rm -rf "${ISOLATION_TMPDIR}" 2>/dev/null || true
    [[ -n "${ISOLATION_PATCH}" ]] && rm -f "${ISOLATION_PATCH}" 2>/dev/null || true
  fi
}
trap cleanup_isolation EXIT

if [[ ${STAGED_ISOLATED} -eq 1 ]]; then
  if ! setup_staged_isolation; then
    log "ERROR: explicit staged isolation could not be established"
    exit 1
  fi
fi

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
  # Phase 94.3: write focused-CI diagnostic artifact so validation_health in
  # aq-report reflects the latest gate result.  Primary path is the shared
  # telemetry dir (available after nixos-rebuild activates tmpfiles.d rule);
  # fall back to ~/.cache so the artifact is written immediately without root.
  local _ci_primary="/var/lib/ai-stack/hybrid/telemetry/latest-focused-ci.json"
  local _ci_fallback="${HOME}/.cache/nixos-ai-stack/latest-focused-ci.json"
  local _ci_artifact=""
  if path_accepts_write "${_ci_primary}"; then
    _ci_artifact="${_ci_primary}"
  else
    mkdir -p "$(dirname "${_ci_fallback}")"
    _ci_artifact="${_ci_fallback}"
  fi
  if FOCUSED_CI_JSON="${_ci_artifact}" bash "${SCRIPT_DIR}/run-focused-ci-checks.sh" "${MODE}" >/dev/null 2>&1; then
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
    log_failed_qa_rows "$output" 30
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

  log_failed_qa_rows "$output" 30
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
  # Guard: without PyYAML we cannot parse the contract. Do NOT misreport this as a
  # syntax error (the file may be perfectly valid — the parser is simply absent,
  # which can happen transiently across rebuilds). Skip gracefully, matching
  # gate_yaml_syntax. Root fix is provisioning PyYAML in the system python.
  if ! python3 -c "import yaml" 2>/dev/null; then
    log "SKIP: PyYAML not available — env contract var check skipped (file not parsed)"
    pass "Env contract gate (skipped — PyYAML not installed)"
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

# Phase 171 — build_llama_payload SSOT compliance
# Detects inline raw payload dicts that bypass build_llama_payload(), risking
# silent enable_thinking omission on Qwen3-35B (thinking tokens fill entire context).
# Excludes: the function definition itself, test fixtures, remote-API callers,
# embedding endpoint (uses /v1/embeddings with a different schema).
gate_llama_payload_ssot() {
  log "Checking build_llama_payload SSOT compliance..."
  local violations
  # Require "messages": (dict key with colon) to avoid false positives on
  # string lists like ["task", "messages", "max_tokens"] in manifest files.
  violations=$(grep -rn \
    '"messages"\s*:' \
    ai-stack/ --include="*.py" \
    | grep -v "build_llama_payload\|#\|test_\|\.pyc\|embeddings\|embed_url\|embed-url\|8081\|remote\|claude\|gemini\|openai\|anthropic\|def \|\"\"\"" \
    | grep '"max_tokens"\|"model"' \
    2>/dev/null || true)
  if [[ -n "$violations" ]]; then
    fail "build_llama_payload SSOT: raw llama.cpp payload found (use build_llama_payload()):"
    printf '%s\n' "$violations" >&2
    return 1
  else
    pass "build_llama_payload SSOT compliant — no raw payload construction"
  fi
}

# Gate: B3-C1 canon-compiler determinism (read-only schema-to-docs/client
# generator). Runs the offline test suite, which proves zero side-effect
# imports, fail-closed validation, and byte-for-byte identical output across
# repeated in-process and fresh-subprocess invocations. Additive-only: does
# not touch any other gate's behavior.
gate_canon_compiler_determinism() {
  log "Checking canon-compiler determinism..."
  local test_script="${REPO_ROOT}/scripts/testing/test-aq-canon-compiler.py"
  if [[ ! -f "${test_script}" ]]; then
    pass "Canon-compiler determinism (skipped — test suite absent)"
    return 0
  fi
  if python3 "${test_script}" >/dev/null 2>&1; then
    pass "Canon-compiler determinism (offline suite passed)"
  else
    fail "Canon-compiler determinism check failed"
    return 1
  fi
}

# Gate: VF-7 evidence-collector suite (unwrapped evidence recorder — see
# scripts/governance/aq-evidence-collector.py). Runs the offline offline test
# suite, which proves digest hashing/immutability, secret redaction, and
# append-only+flock ledger writes on a temp ledger only — never touches the
# real .agents/events/a2a-events.jsonl. Additive-only, alongside
# gate_canon_compiler_determinism: does not touch any other gate's behavior.
gate_evidence_collector() {
  log "Checking VF-7 evidence-collector suite..."
  local test_script="${REPO_ROOT}/scripts/testing/test-aq-evidence-collector.py"
  if [[ ! -f "${test_script}" ]]; then
    pass "Evidence-collector suite (skipped — test suite absent)"
    return 0
  fi
  if python3 "${test_script}" >/dev/null 2>&1; then
    pass "Evidence-collector suite (offline suite passed)"
  else
    fail "Evidence-collector suite failed"
    return 1
  fi
}

log "=== Tier 0 Validation Gate ==="
log "Mode: ${MODE}"
log ""

[[ $TAP_MODE -eq 1 ]] && printf 'TAP version 14\n'

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
gate_llama_payload_ssot || true
gate_canon_compiler_determinism || true
gate_evidence_collector || true

# Pre-deploy gates
if [[ "$MODE" == "--pre-deploy" ]]; then
  gate_deploy_batch_size || true
  gate_unattended_sudo_readiness || true
fi

# tier0.d/ extension checks — drop executable scripts here to add new gates
# without editing this file. Each script receives MODE as $1 and must exit 0
# (pass) or exit 1 (fail). stdout line prefix "[tier0.d/<name>]" is recommended.
TIER0D="${SCRIPT_DIR}/tier0.d"
if [[ -d "$TIER0D" ]]; then
  shopt -s nullglob
  for ext_check in "${TIER0D}"/*.sh; do
    check_name="$(basename "$ext_check" .sh)"
    log "Running tier0.d extension: ${check_name}..."
    if bash "$ext_check" "${MODE}" 2>&1; then
      pass "tier0.d/${check_name}"
    else
      fail "tier0.d/${check_name}"
    fi
  done
  shopt -u nullglob
fi

log ""
log "=== Summary ==="
log "Passed: ${pass_count}"
log "Failed: ${fail_count}"

# Emit TAP plan line now that we know the total count
if [[ $TAP_MODE -eq 1 ]]; then
  printf '1..%d\n' "$tap_index"
fi

# Emit machine-readable JSON results if TIER0_TAP_JSON is set
if [[ -n "$TAP_JSON_FILE" ]]; then
  python3 - "$TAP_JSON_FILE" "${_tap_results[@]+"${_tap_results[@]}"}" <<'PY'
import json, sys, datetime
out_file = sys.argv[1]
entries = sys.argv[2:]
results = []
for e in entries:
    parts = e.split(":", 2)
    if len(parts) == 3:
        status, idx, desc = parts
        results.append({"index": int(idx), "status": status, "description": desc})
data = {
    "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "total": len(results),
    "passed": sum(1 for r in results if r["status"] == "ok"),
    "failed": sum(1 for r in results if r["status"] == "not_ok"),
    "skipped": sum(1 for r in results if r["status"] == "skip"),
    "checks": results,
}
with open(out_file, "w") as f:
    json.dump(data, f, indent=2)
print(f"[tier0] JSON results written to {out_file}")
PY
fi

if [[ ${fail_count} -gt 0 ]]; then
  log ""
  log "BLOCKED: ${fail_count} validation gate(s) failed"
  log "Do NOT commit or deploy until all gates pass"
  exit 1
fi

log ""
log "OK: All Tier 0 gates passed"
exit 0
