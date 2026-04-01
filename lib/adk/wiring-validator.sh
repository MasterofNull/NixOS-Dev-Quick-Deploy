#!/usr/bin/env bash
# lib/adk/wiring-validator.sh
#
# Purpose: Validate ADK integration configurations for declarative compliance
#
# Status: production
# Owner: ai-harness
# Last Updated: 2026-03-20
#
# Features:
# - Validate ADK integration configurations
# - Check for hardcoded values (ports, URLs, secrets)
# - Verify Nix option ownership
# - Ensure declarative compliance
# - Generate compliance reports
# - Integration with CI/CD pipeline

set -euo pipefail

# Declarative paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NIX_DIR="${REPO_ROOT}/nix"
REPORTS_DIR="${REPO_ROOT}/.agent/adk/reports"

# Configuration
VERBOSE="${VERBOSE:-0}"
STRICT_MODE="${STRICT_MODE:-1}"

# Validation patterns
HARDCODED_PORT_PATTERN='[^$]:[0-9]{2,5}[^0-9]'
HARDCODED_URL_PATTERN='https?://[^$][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
HARDCODED_SECRET_PATTERN='(password|secret|key|token)[[:space:]]*=[[:space:]]*["\047][^"\047$]'

# Logging utilities
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" >&2
}

log_verbose() {
    if [[ "${VERBOSE}" -eq 1 ]]; then
        log "$@"
    fi
}

log_error() {
    log "ERROR: $*"
}

log_warning() {
    log "WARNING: $*"
}

# Ensure reports directory exists
mkdir -p "${REPORTS_DIR}"

# Check for hardcoded ports
check_hardcoded_ports() {
    local file="$1"
    local violations=()

    log_verbose "Checking for hardcoded ports in: ${file}"

    # Skip comments and look for port patterns
    while IFS= read -r line; do
        # Skip comment lines
        if [[ "$line" =~ ^[[:space:]]*# ]]; then
            continue
        fi

        # Check for hardcoded port pattern (not from config.mySystem.ports)
        if echo "$line" | grep -qP "${HARDCODED_PORT_PATTERN}" && \
           ! echo "$line" | grep -q 'config.mySystem.ports' && \
           ! echo "$line" | grep -q '\${toString' && \
           ! echo "$line" | grep -q 'example'; then
            violations+=("$line")
        fi
    done < "$file"

    if [[ ${#violations[@]} -gt 0 ]]; then
        return 1
    fi

    return 0
}

# Check for hardcoded URLs
check_hardcoded_urls() {
    local file="$1"
    local violations=()

    log_verbose "Checking for hardcoded URLs in: ${file}"

    while IFS= read -r line; do
        # Skip comment lines and examples
        if [[ "$line" =~ ^[[:space:]]*# ]] || echo "$line" | grep -q 'example'; then
            continue
        fi

        # Check for hardcoded HTTP(S) URLs (not from environment or config)
        if echo "$line" | grep -qE "${HARDCODED_URL_PATTERN}" && \
           ! echo "$line" | grep -qE '(config\.|env\.|example|EXAMPLE)'; then
            violations+=("$line")
        fi
    done < "$file"

    if [[ ${#violations[@]} -gt 0 ]]; then
        return 1
    fi

    return 0
}

# Check for hardcoded secrets
check_hardcoded_secrets() {
    local file="$1"
    local violations=()

    log_verbose "Checking for hardcoded secrets in: ${file}"

    while IFS= read -r line; do
        # Skip comment lines
        if [[ "$line" =~ ^[[:space:]]*# ]]; then
            continue
        fi

        # Check for hardcoded secrets (not from file paths or config)
        if echo "$line" | grep -qiE "${HARDCODED_SECRET_PATTERN}" && \
           ! echo "$line" | grep -qE '(File|file|PATH|config\.)'; then
            violations+=("REDACTED: secret found in line")
        fi
    done < "$file"

    if [[ ${#violations[@]} -gt 0 ]]; then
        return 1
    fi

    return 0
}

# Check Nix option ownership
check_nix_option_ownership() {
    local file="$1"

    log_verbose "Checking Nix option ownership in: ${file}"

    # Verify file contains proper option declarations
    if ! grep -q 'mkOption' "$file" 2>/dev/null; then
        log_verbose "No Nix options found (not a Nix module)"
        return 0
    fi

    # Check for proper option structure
    if ! grep -q 'type = ' "$file"; then
        log_warning "Nix options without type declarations in: ${file}"
        return 1
    fi

    # Check for descriptions
    if ! grep -q 'description = ' "$file"; then
        log_warning "Nix options without descriptions in: ${file}"
        if [[ "${STRICT_MODE}" -eq 1 ]]; then
            return 1
        fi
    fi

    return 0
}

# Validate environment injection patterns
check_environment_injection() {
    local file="$1"
    local has_env_config=0

    log_verbose "Checking environment injection patterns in: ${file}"

    # Check if file uses proper environment configuration
    if grep -q 'environment\.' "$file" || \
       grep -q 'extraEnv' "$file" || \
       grep -q 'config.mySystem' "$file"; then
        has_env_config=1
    fi

    # If it's a service definition, it should use environment
    if grep -q 'systemd.services' "$file" && [[ ${has_env_config} -eq 0 ]]; then
        log_warning "SystemD service without environment configuration: ${file}"
        if [[ "${STRICT_MODE}" -eq 1 ]]; then
            return 1
        fi
    fi

    return 0
}

# Validate service dependencies
check_service_dependencies() {
    local file="$1"

    log_verbose "Checking service dependencies in: ${file}"

    # Check if systemd service has proper dependencies
    if grep -q 'systemd.services' "$file"; then
        if ! grep -q 'after = ' "$file" && ! grep -q 'requires = ' "$file"; then
            log_verbose "SystemD service may be missing dependency declarations: ${file}"
        fi
    fi

    return 0
}

# Validate a single file
validate_file() {
    local file="$1"
    local violations=()
    local warnings=()

    log_verbose "Validating file: ${file}"

    # Check for hardcoded ports
    if ! check_hardcoded_ports "$file"; then
        violations+=("hardcoded_ports")
    fi

    # Check for hardcoded URLs
    if ! check_hardcoded_urls "$file"; then
        violations+=("hardcoded_urls")
    fi

    # Check for hardcoded secrets
    if ! check_hardcoded_secrets "$file"; then
        violations+=("hardcoded_secrets")
    fi

    # Check Nix option ownership (for .nix files)
    if [[ "$file" == *.nix ]]; then
        if ! check_nix_option_ownership "$file"; then
            warnings+=("nix_option_ownership")
        fi

        if ! check_environment_injection "$file"; then
            warnings+=("environment_injection")
        fi

        if ! check_service_dependencies "$file"; then
            warnings+=("service_dependencies")
        fi
    fi

    # Return validation result
    if [[ ${#violations[@]} -gt 0 ]]; then
        echo "FAIL:${file}:${violations[*]}"
        return 1
    elif [[ ${#warnings[@]} -gt 0 ]]; then
        echo "WARN:${file}:${warnings[*]}"
        return 0
    else
        echo "PASS:${file}"
        return 0
    fi
}

# Validate all ADK integration files
validate_all() {
    local target_dir="${1:-${NIX_DIR}}"
    local file_pattern="${2:-*.nix}"
    local results=()
    local pass_count=0
    local warn_count=0
    local fail_count=0

    log "Validating ADK integration files in: ${target_dir}"

    # Find all matching files
    local files=()
    while IFS= read -r file; do
        files+=("$file")
    done < <(find "$target_dir" -type f -name "$file_pattern" 2>/dev/null || true)

    if [[ ${#files[@]} -eq 0 ]]; then
        log_warning "No files found matching pattern: ${file_pattern}"
        return 0
    fi

    # Validate each file
    for file in "${files[@]}"; do
        local result
        result=$(validate_file "$file")
        results+=("$result")

        if [[ "$result" == PASS:* ]]; then
            pass_count=$((pass_count + 1))
        elif [[ "$result" == WARN:* ]]; then
            warn_count=$((warn_count + 1))
        else
            fail_count=$((fail_count + 1))
        fi
    done

    # Generate report
    generate_report "${results[@]}"

    # Summary
    log "Validation complete:"
    log "  Passed: ${pass_count}"
    log "  Warnings: ${warn_count}"
    log "  Failed: ${fail_count}"

    # Return failure if any files failed in strict mode
    if [[ ${fail_count} -gt 0 ]]; then
        return 1
    fi

    return 0
}

# Generate compliance report
generate_report() {
    local results=("$@")
    local report_file="${REPORTS_DIR}/wiring-validation-$(date +%Y%m%d-%H%M%S).json"

    log_verbose "Generating compliance report: ${report_file}"

    # Build JSON report
    local json='{"timestamp":"'$(date -Iseconds)'","results":['

    local first=1
    for result in "${results[@]}"; do
        local status="${result%%:*}"
        local remainder="${result#*:}"
        local file="${remainder%%:*}"
        local violations="${remainder#*:}"

        if [[ ${first} -eq 1 ]]; then
            first=0
        else
            json+=","
        fi

        json+="{\"file\":\"${file}\",\"status\":\"${status}\""

        if [[ "$violations" != "$file" ]]; then
            json+=",\"violations\":\"${violations}\""
        fi

        json+="}"
    done

    json+=']}'

    # Write report
    echo "$json" | python3 -m json.tool > "$report_file" 2>/dev/null || echo "$json" > "$report_file"

    log "Compliance report: ${report_file}"

    # Create latest symlink
    ln -sf "$(basename "$report_file")" "${REPORTS_DIR}/wiring-validation-latest.json"

    return 0
}

# Validate staged files (for pre-commit hook)
validate_staged() {
    log "Validating staged ADK integration files"

    # Get staged Nix files
    local staged_files=()
    while IFS= read -r file; do
        if [[ "$file" == *.nix ]] && [[ -f "$file" ]]; then
            staged_files+=("$file")
        fi
    done < <(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)

    if [[ ${#staged_files[@]} -eq 0 ]]; then
        log "No staged Nix files to validate"
        return 0
    fi

    local results=()
    local fail_count=0

    for file in "${staged_files[@]}"; do
        local result
        result=$(validate_file "$file")
        results+=("$result")

        if [[ "$result" == FAIL:* ]]; then
            fail_count=$((fail_count + 1))
            log_error "Validation failed: ${file}"
        fi
    done

    generate_report "${results[@]}"

    if [[ ${fail_count} -gt 0 ]]; then
        log_error "Staged files have declarative wiring violations"
        return 1
    fi

    log "All staged files passed validation"
    return 0
}

# CLI interface
main() {
    local mode="all"
    local target_dir="${NIX_DIR}"
    local pattern="*.nix"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --staged)
                mode="staged"
                shift
                ;;
            --dir)
                target_dir="$2"
                shift 2
                ;;
            --pattern)
                pattern="$2"
                shift 2
                ;;
            --verbose|-v)
                VERBOSE=1
                shift
                ;;
            --no-strict)
                STRICT_MODE=0
                shift
                ;;
            --help|-h)
                cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Validate ADK integration configurations for declarative compliance.

Options:
    --staged          Validate only staged git files
    --dir DIR         Target directory (default: nix/)
    --pattern PATTERN File pattern (default: *.nix)
    --verbose, -v     Enable verbose logging
    --no-strict       Disable strict mode (warnings don't fail)
    --help, -h        Show this help message

Examples:
    $(basename "$0")                     # Validate all Nix files
    $(basename "$0") --staged            # Validate staged files (pre-commit)
    $(basename "$0") --dir lib/adk       # Validate specific directory
    $(basename "$0") --pattern "adk*.nix" # Validate specific pattern

Validation Checks:
    - No hardcoded ports (use config.mySystem.ports)
    - No hardcoded URLs (use environment or config)
    - No hardcoded secrets (use *File options)
    - Proper Nix option declarations
    - Environment injection patterns
    - Service dependency declarations

Reports:
    Compliance reports: ${REPORTS_DIR}
EOF
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                log "Use --help for usage information"
                return 1
                ;;
        esac
    done

    case "$mode" in
        staged)
            validate_staged
            ;;
        all)
            validate_all "$target_dir" "$pattern"
            ;;
        *)
            log_error "Unknown mode: $mode"
            return 1
            ;;
    esac
}

# Execute if run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
