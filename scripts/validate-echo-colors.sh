#!/usr/bin/env bash
# =============================================================================
# NixOS Dev Quick Deploy - Echo Color Validation
# =============================================================================
# This helper verifies that our CI environment (and local shells) can render
# ANSI colour sequences correctly when produced via common shell utilities.
# Several of the project scripts rely on colourised output for readability; if
# these checks fail the logs would become noisy and difficult to scan.
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TOTAL_CHECKS=0
FAILED_CHECKS=0

PAYLOAD_LITERAL='\033[0;31mTEST\033[0m'
EXPECTED_PAYLOAD="$(printf '%b' "$PAYLOAD_LITERAL")"
EXPECTED_HEX_NO_NL="$(printf '%s' "$EXPECTED_PAYLOAD" | od -An -tx1 -v | tr -s '[:space:]' ' ' | sed -e 's/^ //' -e 's/ $//')"
EXPECTED_HEX_WITH_NL="$(printf '%s\n' "$EXPECTED_PAYLOAD" | od -An -tx1 -v | tr -s '[:space:]' ' ' | sed -e 's/^ //' -e 's/ $//')"

print_header() {
    printf '%b\n' "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    printf '%b\n' "${BLUE}$1${NC}"
    printf '%b\n' "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_check() {
    printf '%b' "  ${BLUE}•${NC} $1... "
}

print_success() {
    printf '%b\n' "${GREEN}ok${NC}"
}

print_failure() {
    printf '%b\n' "${RED}failed${NC}"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
}

normalise_hex() {
    tr -s '[:space:]' ' ' | sed -e 's/^ //' -e 's/ $//'
}

check_output_matches() {
    local description="$1"
    local expected_hex="$2"
    shift 2
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    print_check "$description"

    local hex_output
    if ! hex_output=$("$@" | od -An -tx1 -v | normalise_hex); then
        print_failure
        printf '    Unable to capture output from %s\n' "$description"
        return
    fi

    if [[ "$hex_output" == "$expected_hex" ]]; then
        print_success
    else
        print_failure
        printf '    Expected: %s\n' "$expected_hex"
        printf '    Received: %s\n' "$hex_output"
    fi
}

check_echo_dash_e_support() {
    check_output_matches "builtin echo -e" "$EXPECTED_HEX_WITH_NL" bash -c "echo -e '$PAYLOAD_LITERAL'"
}

check_command_printf() {
    check_output_matches "printf '%b'" "$EXPECTED_HEX_NO_NL" bash -c "printf '%b' '$PAYLOAD_LITERAL'"
    check_output_matches "printf '%b\\\\n'" "$EXPECTED_HEX_WITH_NL" bash -c "printf '%b\\n' '$PAYLOAD_LITERAL'"
}

check_bin_echo() {
    if command -v /bin/echo >/dev/null 2>&1; then
        check_output_matches "/bin/echo -e" "$EXPECTED_HEX_WITH_NL" /bin/bash -c "echo -e '$PAYLOAD_LITERAL'"
    else
        printf '  ${YELLOW}!${NC} /bin/echo not found; skipping dedicated check.\n'
    fi
}

main() {
    print_header "Validating ANSI colour support"
    printf 'Expected payload (visible): %bTEST%b\n' "${RED}" "${NC}"
    printf 'Expected hex without newline: %s\n' "$EXPECTED_HEX_NO_NL"
    printf 'Expected hex with newline   : %s\n\n' "$EXPECTED_HEX_WITH_NL"

    check_echo_dash_e_support
    check_command_printf
    check_bin_echo

    printf '\n'
    if (( FAILED_CHECKS > 0 )); then
        printf '%b\n' "${RED}✗ Detected ${FAILED_CHECKS} failing colour validation checks (of ${TOTAL_CHECKS}).${NC}"
        printf '%b\n' "${RED}  -> Please switch scripts to use printf or install a POSIX compliant echo.${NC}"
        return 1
    fi

    printf '%b\n' "${GREEN}✓ All ${TOTAL_CHECKS} colour validation checks passed.${NC}"
}

main "$@"
