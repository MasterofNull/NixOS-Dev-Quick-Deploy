#!/usr/bin/env bash
#
# run-all-checks.sh
# Aggregate runner for core validation scripts:
#   - scripts/system-health-check.sh
#   - scripts/test_services.sh
#   - scripts/test_real_world_workflows.sh
#

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

HEALTH_SCRIPT="$SCRIPT_DIR/scripts/system-health-check.sh"
SERVICES_SCRIPT="$SCRIPT_DIR/scripts/test_services.sh"
WORKFLOWS_SCRIPT="$SCRIPT_DIR/scripts/test_real_world_workflows.sh"

print_usage() {
    cat <<EOF
Usage: $(basename "$0") [--detailed]

Runs the main validation scripts in sequence:
  1) system-health-check.sh
  2) test_services.sh
  3) test_real_world_workflows.sh

Options:
  --detailed   Pass --detailed to system-health-check.sh
  -h, --help   Show this help text
EOF
}

main() {
    local detailed=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --detailed)
                detailed=true
                shift
                ;;
            -h|--help)
                print_usage
                exit 0
                ;;
            *)
                echo "[ERROR] Unknown option: $1" >&2
                echo "" >&2
                print_usage
                exit 1
                ;;
        esac
    done

    local overall_exit=0

    # 1) System health check
    if [[ -x "$HEALTH_SCRIPT" ]]; then
        echo "=== Running system-health-check.sh ==="
        if [[ "$detailed" == true ]]; then
            if "$HEALTH_SCRIPT" --detailed; then
                echo ">>> system-health-check.sh: OK"
            else
                echo ">>> system-health-check.sh: FAILED"
                overall_exit=1
            fi
        else
            if "$HEALTH_SCRIPT"; then
                echo ">>> system-health-check.sh: OK"
            else
                echo ">>> system-health-check.sh: FAILED"
                overall_exit=1
            fi
        fi
        echo
    else
        echo ">>> Skipping system-health-check.sh (not found or not executable at $HEALTH_SCRIPT)"
        overall_exit=1
    fi

    # 2) Service tests
    if [[ -x "$SERVICES_SCRIPT" ]]; then
        echo "=== Running test_services.sh ==="
        if "$SERVICES_SCRIPT"; then
            echo ">>> test_services.sh: OK"
        else
            echo ">>> test_services.sh: FAILED"
            overall_exit=1
        fi
        echo
    else
        echo ">>> Skipping test_services.sh (not found or not executable at $SERVICES_SCRIPT)"
        overall_exit=1
    fi

    # 3) Workflow tests
    if [[ -x "$WORKFLOWS_SCRIPT" ]]; then
        echo "=== Running test_real_world_workflows.sh ==="
        if "$WORKFLOWS_SCRIPT"; then
            echo ">>> test_real_world_workflows.sh: OK"
        else
            echo ">>> test_real_world_workflows.sh: FAILED"
            overall_exit=1
        fi
        echo
    else
        echo ">>> Skipping test_real_world_workflows.sh (not found or not executable at $WORKFLOWS_SCRIPT)"
        overall_exit=1
    fi

    if [[ $overall_exit -eq 0 ]]; then
        echo "All checks completed successfully."
    else
        echo "One or more checks reported issues. See output above."
    fi

    exit "$overall_exit"
}

main "$@"
