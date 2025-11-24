#!/usr/bin/env bash
#
# fix-secrets-encryption.sh
# Purpose: Diagnose and fix secrets encryption issues in NixOS Quick Deploy
# Version: 1.0.0
#
# Usage: ./scripts/fix-secrets-encryption.sh [--install-deps] [--regenerate-key]
#

set -euo pipefail

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGE_KEY_DIR="${HOME}/.config/sops/age"
AGE_KEY_FILE="${AGE_KEY_DIR}/keys.txt"
HM_CONFIG_DIR="${HOME}/.config/home-manager"

# Options
INSTALL_DEPS=false
REGENERATE_KEY=false

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --install-deps)
                INSTALL_DEPS=true
                shift
                ;;
            --regenerate-key)
                REGENERATE_KEY=true
                shift
                ;;
            -h|--help)
                cat << EOF
Usage: $0 [OPTIONS]

Diagnose and fix secrets encryption issues in NixOS Quick Deploy.

OPTIONS:
    --install-deps      Force install/reinstall required dependencies
    --regenerate-key    Regenerate age encryption key (backs up old key)
    -h, --help          Show this help message

EXAMPLES:
    $0                          # Run diagnostics
    $0 --install-deps           # Install missing dependencies
    $0 --regenerate-key         # Generate new encryption key
EOF
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
}

check_dependency() {
    local cmd="$1"
    local package="${2:-$cmd}"

    if command -v "$cmd" >/dev/null 2>&1; then
        log_success "$cmd found at $(command -v $cmd)"
        return 0
    else
        log_warning "$cmd not found"
        if [[ "$INSTALL_DEPS" == "true" ]]; then
            log_info "Installing $cmd..."
            if nix profile install "nixpkgs#$package" 2>/dev/null || nix-env -iA "nixpkgs.$package" 2>/dev/null; then
                log_success "$cmd installed successfully"
                return 0
            else
                log_error "Failed to install $cmd"
                return 1
            fi
        else
            log_info "Run with --install-deps to install automatically"
            return 1
        fi
    fi
}

check_age_key() {
    if [[ -f "$AGE_KEY_FILE" ]] && [[ "$REGENERATE_KEY" != "true" ]]; then
        local public_key
        public_key=$(grep "^# public key:" "$AGE_KEY_FILE" 2>/dev/null | awk '{print $NF}')
        if [[ -n "$public_key" ]]; then
            log_success "Age key exists: ${public_key:0:20}..." >&2
            echo "$public_key"
            return 0
        else
            log_warning "Age key file exists but format is invalid" >&2
            if [[ "$REGENERATE_KEY" != "true" ]]; then
                log_info "Run with --regenerate-key to create new key" >&2
                return 1
            fi
        fi
    fi

    if [[ "$REGENERATE_KEY" == "true" ]] || [[ ! -f "$AGE_KEY_FILE" ]]; then
        log_info "Generating new age encryption key..." >&2

        # Backup existing key if present
        if [[ -f "$AGE_KEY_FILE" ]]; then
            local backup_file="${AGE_KEY_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
            cp "$AGE_KEY_FILE" "$backup_file"
            log_info "Backed up existing key to: $backup_file" >&2
        fi

        # Create directory
        mkdir -p "$AGE_KEY_DIR"
        chmod 700 "$AGE_KEY_DIR"

        # Generate key (redirect age-keygen output to stderr)
        if age-keygen -o "$AGE_KEY_FILE" >&2; then
            chmod 600 "$AGE_KEY_FILE"
            local public_key
            public_key=$(grep "^# public key:" "$AGE_KEY_FILE" | awk '{print $NF}')
            log_success "Age key generated: ${public_key:0:20}..." >&2
            echo "$public_key"
            return 0
        else
            log_error "Failed to generate age key" >&2
            return 1
        fi
    fi

    return 1
}

check_templates() {
    local all_found=true

    if [[ ! -f "${SCRIPT_DIR}/templates/secrets.yaml" ]]; then
        log_error "Missing: ${SCRIPT_DIR}/templates/secrets.yaml"
        all_found=false
    else
        log_success "secrets.yaml template exists"
    fi

    if [[ ! -f "${SCRIPT_DIR}/templates/.sops.yaml" ]]; then
        log_error "Missing: ${SCRIPT_DIR}/templates/.sops.yaml"
        all_found=false
    else
        log_success ".sops.yaml template exists"
    fi

    if [[ "$all_found" == "false" ]]; then
        log_error "Missing template files - ensure you have complete NixOS Quick Deploy"
        return 1
    fi

    return 0
}

test_encryption() {
    log_info "Testing encryption/decryption..."

    local test_file="/tmp/sops-test-$$"
    local public_key="$1"

    # Create test file
    cat > "$test_file" << EOF
# Test secrets file
test:
  secret: "hello world"
  number: 42
EOF

    # Create test .sops.yaml
    cat > "/tmp/.sops-test-$$.yaml" << EOF
creation_rules:
  - age: >-
      $public_key
EOF

    # Export environment
    export SOPS_AGE_KEY_FILE="$AGE_KEY_FILE"
    export SOPS_AGE_RECIPIENTS="$public_key"

    # Test encryption
    cd /tmp
    if sops --config "/tmp/.sops-test-$$.yaml" -e -i "$test_file" 2>&1; then
        log_info "Encryption successful"

        # Test decryption
        if sops --config "/tmp/.sops-test-$$.yaml" -d "$test_file" > /dev/null 2>&1; then
            log_success "Encryption/decryption test passed"
            rm -f "$test_file" "/tmp/.sops-test-$$.yaml"
            return 0
        else
            log_error "Decryption failed"
            rm -f "$test_file" "/tmp/.sops-test-$$.yaml"
            return 1
        fi
    else
        log_error "Encryption failed"
        rm -f "$test_file" "/tmp/.sops-test-$$.yaml"
        return 1
    fi
}

generate_sops_config() {
    local public_key="$1"

    log_info "Generating .sops.yaml configuration..."

    mkdir -p "$HM_CONFIG_DIR"

    local sops_config="${HM_CONFIG_DIR}/.sops.yaml"

    if [[ -f "$sops_config" ]]; then
        if grep -q "$public_key" "$sops_config" 2>/dev/null; then
            log_success ".sops.yaml already contains current public key"
            return 0
        else
            log_warning ".sops.yaml exists but doesn't match current key"
            local backup="${sops_config}.backup.$(date +%Y%m%d_%H%M%S)"
            cp "$sops_config" "$backup"
            log_info "Backed up to: $backup"
        fi
    fi

    # Copy template
    if [[ -f "${SCRIPT_DIR}/templates/.sops.yaml" ]]; then
        cp "${SCRIPT_DIR}/templates/.sops.yaml" "$sops_config"
    else
        # Generate minimal config
        cat > "$sops_config" << EOF
creation_rules:
  - path_regex: .*secrets\.yaml$
    age: >-
      AGE_PUBLIC_KEY_PLACEHOLDER
EOF
    fi

    # Replace placeholder using Python for safe multi-line substitution
    python3 - "$sops_config" "$public_key" <<'PY'
import sys
import pathlib

config_file = pathlib.Path(sys.argv[1])
public_key = sys.argv[2]

text = config_file.read_text()
text = text.replace("AGE_PUBLIC_KEY_PLACEHOLDER", public_key)
config_file.write_text(text)
PY

    chmod 600 "$sops_config"

    if grep -qF "$public_key" "$sops_config"; then
        log_success ".sops.yaml generated at: $sops_config"
        return 0
    else
        log_error "Failed to generate .sops.yaml"
        return 1
    fi
}

print_summary() {
    local public_key="$1"

    cat << EOF

${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}
${GREEN}               Secrets Encryption Setup Complete                 ${NC}
${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}

${BLUE}Age Public Key:${NC}
  $public_key

${BLUE}Configuration Files:${NC}
  Age key:      $AGE_KEY_FILE
  SOPS config:  ${HM_CONFIG_DIR}/.sops.yaml

${BLUE}Environment Variables:${NC}
  export SOPS_AGE_KEY_FILE="$AGE_KEY_FILE"

${BLUE}Usage:${NC}
  # Edit encrypted secrets
  cd ${HM_CONFIG_DIR}
  sops secrets.yaml

  # Decrypt and view
  sops -d secrets.yaml

${BLUE}Next Steps:${NC}
  1. Run deployment: ./nixos-quick-deploy.sh
  2. Secrets will be automatically encrypted during Phase 3
  3. Edit secrets later with: sops ${HM_CONFIG_DIR}/secrets.yaml

${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}
EOF
}

main() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}    NixOS Quick Deploy - Secrets Encryption Diagnostic${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    parse_args "$@"

    local failed=false

    # Step 1: Check dependencies
    echo -e "${BLUE}[1/5] Checking Dependencies${NC}"
    echo
    if ! check_dependency "age-keygen" "age" || \
       ! check_dependency "sops" "sops" || \
       ! check_dependency "jq" "jq"; then
        log_error "Missing dependencies"
        if [[ "$INSTALL_DEPS" != "true" ]]; then
            log_info "Run with --install-deps to install automatically"
            exit 1
        fi
        failed=true
    fi
    echo

    # Step 2: Check age key
    echo -e "${BLUE}[2/5] Checking Age Encryption Key${NC}"
    echo
    public_key=$(check_age_key) || {
        log_error "Age key check failed"
        if [[ "$REGENERATE_KEY" != "true" ]]; then
            log_info "Run with --regenerate-key to generate new key"
        fi
        exit 1
    }
    echo

    # Step 3: Check templates
    echo -e "${BLUE}[3/5] Checking Template Files${NC}"
    echo
    if ! check_templates; then
        exit 1
    fi
    echo

    # Step 4: Generate .sops.yaml
    echo -e "${BLUE}[4/5] Generating SOPS Configuration${NC}"
    echo
    if ! generate_sops_config "$public_key"; then
        exit 1
    fi
    echo

    # Step 5: Test encryption
    echo -e "${BLUE}[5/5] Testing Encryption${NC}"
    echo
    if ! test_encryption "$public_key"; then
        exit 1
    fi
    echo

    # Print summary
    print_summary "$public_key"
}

main "$@"
