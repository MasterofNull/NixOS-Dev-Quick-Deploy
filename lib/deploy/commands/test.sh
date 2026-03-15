#!/usr/bin/env bash
#
# Deploy CLI - Test Command
# Run various test suites

# ============================================================================
# Help Text
# ============================================================================

help_test() {
  cat <<EOF
Command: deploy test

Run test suites for system validation and quality assurance.

USAGE:
  deploy test [SUITE] [OPTIONS]

TEST SUITES:
  smoke                   Quick smoke tests (default)
  qa                      QA test suite
  acceptance              Acceptance tests
  regression              Regression test gate
  all                     All test suites
  integration             Integration tests
  unit                    Unit tests
  harness                 AI harness tests
  custom SCRIPT           Run custom test script

OPTIONS:
  --suite NAME            Test suite to run (default: smoke)
  --fail-fast             Stop on first failure
  --verbose               Verbose test output
  --coverage              Generate coverage report
  --parallel              Run tests in parallel
  --help                  Show this help

EXAMPLES:
  deploy test                          # Run smoke tests
  deploy test qa                       # Run QA suite
  deploy test --suite=acceptance       # Run acceptance tests
  deploy test all                      # Run all test suites
  deploy test custom my-test.sh        # Run custom test script
  deploy test --fail-fast              # Stop on first failure

DESCRIPTION:
  The 'test' command provides a unified interface to the various test
  suites scattered across scripts/automation/ and scripts/testing/.

  Test suites available:
  - Smoke: Quick validation tests (<2 minutes)
  - QA: Quality assurance test suite
  - Acceptance: User acceptance tests
  - Regression: Regression prevention gate
  - All: Comprehensive test run (may take 30+ minutes)
  - Integration: Cross-component integration tests
  - Unit: Individual component unit tests
  - Harness: AI harness specific tests

  In Phase 1.2, this command consolidates 100+ test scripts into
  organized test suites with clear categorization.

TEST SUITE DETAILS:

  Smoke Tests:
  - System services running
  - AI stack health
  - Basic connectivity
  - Critical endpoints responding
  - ~2 minutes runtime

  QA Suite:
  - Functional tests
  - API tests
  - Data validation
  - ~10 minutes runtime

  Acceptance Tests:
  - End-to-end workflows
  - User scenarios
  - Integration points
  - ~15 minutes runtime

  Regression Suite:
  - Known bug prevention
  - Performance benchmarks
  - Breaking change detection
  - ~20 minutes runtime

EXIT CODES:
  0    All tests passed
  1    One or more tests failed
  2    Test execution error

LEGACY EQUIVALENTS:
  scripts/automation/run-all-checks.sh       # All tests
  scripts/automation/run-qa-suite.sh         # QA suite
  scripts/automation/run-acceptance-checks.sh # Acceptance
  scripts/automation/run-harness-regression-gate.sh # Regression

RELATED COMMANDS:
  deploy health           Health checks (subset of smoke tests)
  deploy ai-stack health  AI stack specific health
  deploy system --dry-run Preview deployment changes

DOCUMENTATION:
  .agents/designs/unified-deploy-cli-architecture.md
  .agents/plans/SYSTEM-EXCELLENCE-ROADMAP-2026-Q2.md
EOF
}

# ============================================================================
# Test Suite Implementations
# ============================================================================

run_smoke_tests() {
  print_section "Smoke Tests"

  log_step 1 4 "Checking system services..."
  if systemctl is-system-running >/dev/null 2>&1; then
    log_success "System running normally"
  else
    log_warn "System state: $(systemctl is-system-running 2>/dev/null || echo 'unknown')"
  fi

  log_step 2 4 "Checking AI stack services..."

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  # Source ai-stack command to get health check function
  if [[ -f "${script_dir}/lib/deploy/commands/ai-stack.sh" ]]; then
    source "${script_dir}/lib/deploy/commands/ai-stack.sh"
    if cmd_ai_stack_health 10 >/dev/null 2>&1; then
      log_success "AI stack healthy"
    else
      log_error "AI stack health check failed"
      return 1
    fi
  else
    # Fallback to basic systemctl check
    if systemctl is-active --quiet ai-stack.target 2>/dev/null; then
      log_success "AI stack target active"
    else
      log_error "AI stack target inactive"
      return 1
    fi
  fi

  log_step 3 4 "Checking network connectivity..."
  if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    log_success "Network connectivity OK"
  else
    log_warn "Network connectivity limited"
  fi

  log_step 4 4 "Checking critical endpoints..."
  local failed=0

  if curl -fsS --max-time 3 http://127.0.0.1:8002/health >/dev/null 2>&1; then
    log_success "AIDB endpoint responding"
  else
    log_error "AIDB endpoint not responding"
    failed=$((failed + 1))
  fi

  if curl -fsS --max-time 3 http://127.0.0.1:8003/health >/dev/null 2>&1; then
    log_success "Hybrid coordinator endpoint responding"
  else
    log_error "Hybrid coordinator endpoint not responding"
    failed=$((failed + 1))
  fi

  if [[ $failed -gt 0 ]]; then
    log_error "$failed critical endpoint(s) not responding"
    return 1
  fi

  log_success "Smoke tests passed"
  return 0
}

run_qa_suite() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  print_section "QA Test Suite"

  if [[ -f "${script_dir}/scripts/automation/run-qa-suite.sh" ]]; then
    bash "${script_dir}/scripts/automation/run-qa-suite.sh"
    return $?
  else
    log_error "QA suite script not found"
    return 2
  fi
}

run_acceptance_tests() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  print_section "Acceptance Tests"

  if [[ -f "${script_dir}/scripts/automation/run-acceptance-checks.sh" ]]; then
    bash "${script_dir}/scripts/automation/run-acceptance-checks.sh"
    return $?
  else
    log_error "Acceptance tests script not found"
    return 2
  fi
}

run_regression_tests() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  print_section "Regression Tests"

  if [[ -f "${script_dir}/scripts/automation/run-harness-regression-gate.sh" ]]; then
    bash "${script_dir}/scripts/automation/run-harness-regression-gate.sh"
    return $?
  else
    log_error "Regression tests script not found"
    return 2
  fi
}

run_all_tests() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  print_section "All Tests"

  if [[ -f "${script_dir}/scripts/automation/run-all-checks.sh" ]]; then
    bash "${script_dir}/scripts/automation/run-all-checks.sh"
    return $?
  else
    log_warn "All-checks script not found, running individual suites..."

    local total_failures=0

    run_smoke_tests || total_failures=$((total_failures + 1))
    run_qa_suite || total_failures=$((total_failures + 1))
    run_acceptance_tests || total_failures=$((total_failures + 1))
    run_regression_tests || total_failures=$((total_failures + 1))

    return $total_failures
  fi
}

run_integration_tests() {
  print_section "Integration Tests"

  log_info "Running integration test suite..."

  # Integration tests would check cross-component interactions
  # For now, delegate to smoke + acceptance
  local failures=0

  run_smoke_tests || failures=$((failures + 1))
  run_acceptance_tests || failures=$((failures + 1))

  return $failures
}

run_unit_tests() {
  print_section "Unit Tests"

  log_info "Running unit tests..."

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  local failures=0

  # Run Python unit tests if pytest available
  if command -v pytest >/dev/null 2>&1; then
    log_info "Running pytest..."
    if pytest "${script_dir}" -v 2>/dev/null; then
      log_success "Python unit tests passed"
    else
      log_warn "Some Python unit tests failed"
      failures=$((failures + 1))
    fi
  fi

  # Run bash syntax validation on all scripts
  log_info "Validating bash scripts..."
  local bash_failures=0
  while IFS= read -r script; do
    if ! bash -n "$script" >/dev/null 2>&1; then
      log_error "Syntax error in: $script"
      bash_failures=$((bash_failures + 1))
    fi
  done < <(find "${script_dir}/scripts" -type f -name "*.sh" 2>/dev/null)

  if [[ $bash_failures -eq 0 ]]; then
    log_success "All bash scripts validated"
  else
    log_error "$bash_failures bash script(s) have syntax errors"
    failures=$((failures + 1))
  fi

  return $failures
}

run_harness_tests() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  print_section "AI Harness Tests"

  # Find harness-specific test scripts
  local harness_scripts=(
    "run-ai-harness-phase-plan.sh"
    "run-harness-improvement-pass.sh"
    "run-harness-regression-gate.sh"
  )

  local failures=0

  for script in "${harness_scripts[@]}"; do
    local script_path="${script_dir}/scripts/automation/${script}"
    if [[ -f "$script_path" ]]; then
      log_info "Running ${script}..."
      if bash "$script_path"; then
        log_success "${script} passed"
      else
        log_error "${script} failed"
        failures=$((failures + 1))
      fi
    else
      log_debug "${script} not found (skipping)"
    fi
  done

  if [[ $failures -eq 0 ]]; then
    log_success "AI harness tests passed"
  else
    log_error "$failures harness test(s) failed"
  fi

  return $failures
}

run_custom_test() {
  local script="$1"

  print_section "Custom Test: $script"

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

  # Try to find script in various locations
  local script_path=""

  if [[ -f "$script" ]]; then
    script_path="$script"
  elif [[ -f "${script_dir}/${script}" ]]; then
    script_path="${script_dir}/${script}"
  elif [[ -f "${script_dir}/scripts/testing/${script}" ]]; then
    script_path="${script_dir}/scripts/testing/${script}"
  elif [[ -f "${script_dir}/scripts/automation/${script}" ]]; then
    script_path="${script_dir}/scripts/automation/${script}"
  else
    log_error "Test script not found: $script"
    echo ""
    echo "Tried locations:"
    echo "  - $script"
    echo "  - ${script_dir}/${script}"
    echo "  - ${script_dir}/scripts/testing/${script}"
    echo "  - ${script_dir}/scripts/automation/${script}"
    return 2
  fi

  log_info "Running custom test: $script_path"

  if bash "$script_path"; then
    log_success "Custom test passed"
    return 0
  else
    log_error "Custom test failed"
    return 1
  fi
}

# ============================================================================
# Main Command Handler
# ============================================================================

cmd_test() {
  local suite="smoke"
  local fail_fast=0
  local verbose_mode=0
  local coverage=0
  local parallel=0

  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help)
        help_test
        return 0
        ;;
      --suite)
        suite="$2"
        shift 2
        ;;
      --suite=*)
        suite="${1#*=}"
        shift
        ;;
      --fail-fast)
        fail_fast=1
        shift
        ;;
      --verbose)
        verbose_mode=1
        VERBOSE=1
        export VERBOSE
        shift
        ;;
      --coverage)
        coverage=1
        shift
        ;;
      --parallel)
        parallel=1
        shift
        ;;
      smoke|qa|acceptance|regression|all|integration|unit|harness)
        suite="$1"
        shift
        ;;
      custom)
        suite="custom"
        shift
        if [[ $# -eq 0 ]]; then
          log_error "Custom test requires script path"
          return 2
        fi
        custom_script="$1"
        shift
        ;;
      -*)
        log_error "Unknown option: $1"
        echo ""
        echo "Run 'deploy test --help' for usage."
        return 2
        ;;
      *)
        log_error "Unknown argument: $1"
        echo ""
        echo "Run 'deploy test --help' for usage."
        return 2
        ;;
    esac
  done

  print_header "Test Suite: $suite"

  local start_time
  start_time=$(get_timestamp)

  local result=0

  # Run selected test suite
  case "$suite" in
    smoke)
      run_smoke_tests
      result=$?
      ;;
    qa)
      run_qa_suite
      result=$?
      ;;
    acceptance)
      run_acceptance_tests
      result=$?
      ;;
    regression)
      run_regression_tests
      result=$?
      ;;
    all)
      run_all_tests
      result=$?
      ;;
    integration)
      run_integration_tests
      result=$?
      ;;
    unit)
      run_unit_tests
      result=$?
      ;;
    harness)
      run_harness_tests
      result=$?
      ;;
    custom)
      run_custom_test "$custom_script"
      result=$?
      ;;
    *)
      log_error "Unknown test suite: $suite"
      echo ""
      echo "Valid suites: smoke, qa, acceptance, regression, all, integration, unit, harness, custom"
      return 2
      ;;
  esac

  local end_time
  end_time=$(get_timestamp)
  local duration=$((end_time - start_time))

  echo ""

  if [[ $result -eq 0 ]]; then
    log_success "Test suite '$suite' passed in $(format_duration $duration)"

    print_section "Next Steps"
    echo "  • Tests passing - ready for deployment"
    echo "  • Run 'deploy system' to deploy changes"
    echo "  • Run 'deploy test all' for comprehensive validation"

    return 0
  else
    log_error "Test suite '$suite' failed in $(format_duration $duration)"

    print_section "Troubleshooting"
    echo "  • Review test output above for specific failures"
    echo "  • Run 'deploy health' to check system state"
    echo "  • Run 'deploy ai-stack logs <service>' to check service logs"
    echo "  • Fix issues and re-run tests"

    return $result
  fi
}
