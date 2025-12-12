#!/usr/bin/env bash
#
# Python Runtime Management
# Purpose: Detect and provision Python interpreter for deployment scripts
# Version: 4.0.0
#
# ============================================================================
# DEPENDENCIES
# ============================================================================
#
# Required Libraries:
#   - lib/logging.sh → log() function
#   - lib/user-interaction.sh → print_* functions
#
# Required Variables:
#   - PYTHON_BIN → Array to store python command (defined in config/variables.sh:558)
#
# Exports:
#   - ensure_python_runtime() → Detect or provision Python interpreter
#   - run_python() → Execute Python with detected interpreter
#   - generate_hex_secret() → Generate hex secrets using Python
#   - generate_password() → Generate passwords using Python
#
# ============================================================================

# ============================================================================
# Ensure Python Runtime Available
# ============================================================================
# Purpose: Detect Python interpreter or provision via nix shell
# Returns:
#   0 - Python available
#   1 - Python unavailable
#
# Sets global PYTHON_BIN array to appropriate command
# Tries in order:
#   1. Cached PYTHON_BIN (if still valid)
#   2. python3 in PATH
#   3. python in PATH
#   4. nix shell with ephemeral python3
# ============================================================================
ensure_python_runtime() {
    # If PYTHON_BIN is cached, verify it's still accessible before using it
    if [ ${#PYTHON_BIN[@]} -gt 0 ]; then
        # Test if the cached python is still working
        if "${PYTHON_BIN[@]}" --version >/dev/null 2>&1; then
            return 0
        fi
        # Cached python is no longer valid, reset and re-detect
        PYTHON_BIN=()
        hash -r 2>/dev/null || true
    fi

    # Try python3 command
    if command -v python3 >/dev/null 2>&1; then
        local python3_path
        python3_path=$(command -v python3)
        if [ -x "$python3_path" ]; then
            PYTHON_BIN=(python3)
            return 0
        fi
        hash -r 2>/dev/null || true
    fi

    # Try python command
    if command -v python >/dev/null 2>&1; then
        local python_path
        python_path=$(command -v python)
        if [ -x "$python_path" ]; then
            PYTHON_BIN=(python)
            return 0
        fi
        hash -r 2>/dev/null || true
    fi

    # Fallback: Use nix shell for ephemeral Python
    if command -v nix >/dev/null 2>&1; then
        PYTHON_BIN=(nix shell nixpkgs#python3 -c python3)
        print_warning "python3 not found in PATH – using ephemeral nix shell" >&2
        return 0
    fi

    # No Python available
    print_error "python3 is required but not available."
    print_error "Install python3 or ensure it is on PATH before rerunning."
    return 1
}

# ============================================================================
# Run Python Command
# ============================================================================
# Purpose: Execute Python ensuring runtime is available
# Parameters:
#   $@ - Arguments to pass to Python
# Returns:
#   Python exit code
# ============================================================================
run_python() {
    ensure_python_runtime || return 1
    "${PYTHON_BIN[@]}" "$@"
}

# ============================================================================
# Generate Hex Secret
# ============================================================================
# Purpose: Generate cryptographically secure hex string
# Parameters:
#   $1 - Number of bytes (default: 32)
# Returns:
#   0 - Success (prints hex string to stdout)
#   1 - Failure
# ============================================================================
# Hex/password utilities rely on python's secrets/random modules instead of
# openssl to avoid extra dependencies; they also respect the resolved
# PYTHON_BIN so we don't re-run detection.
generate_hex_secret() {
    local bytes="${1:-32}"

    if ! ensure_python_runtime; then
        return 1
    fi

    "${PYTHON_BIN[@]}" - "$bytes" <<'PY'
import secrets
import sys

try:
    bytes_count = int(sys.argv[1])
except (IndexError, ValueError):
    bytes_count = 32

if bytes_count < 1:
    bytes_count = 32

print(secrets.token_hex(bytes_count))
PY
}

# ============================================================================
# Generate Password
# ============================================================================
# Purpose: Generate cryptographically secure password
# Parameters:
#   $1 - Password length (default: 20)
# Returns:
#   0 - Success (prints password to stdout)
#   1 - Failure
# ============================================================================
generate_password() {
    local length="${1:-20}"

    if ! ensure_python_runtime; then
        return 1
    fi

    "${PYTHON_BIN[@]}" - "$length" <<'PY'
import secrets
import string
import sys

try:
    length = int(sys.argv[1])
except (IndexError, ValueError):
    length = 20

if length < 1:
    length = 20

# Use URL-safe characters (alphanumeric + _ and -)
alphabet = string.ascii_letters + string.digits + "_-"
password = ''.join(secrets.choice(alphabet) for _ in range(length))
print(password)
PY
}
