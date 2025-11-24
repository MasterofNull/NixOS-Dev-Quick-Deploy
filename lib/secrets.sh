#!/usr/bin/env bash
#
# NixOS Quick Deploy - Secrets Management Library
# Version: 5.0.0 (sops-nix integration)
# Purpose: Manage encrypted secrets using sops-nix and age
#
# ============================================================================
# OVERVIEW
# ============================================================================
# This library provides functions for managing secrets using sops-nix:
# - Age key generation and management
# - Secret encryption/decryption
# - Migration from plain text to encrypted secrets
# - Secret validation and rotation
#
# Dependencies:
#   - age (encryption tool)
#   - sops (secret management)
#   - jq (JSON processing)
#
# ============================================================================

# Ensure required functions from other libraries are available
if ! declare -F log >/dev/null 2>&1; then
    echo "ERROR: secrets.sh requires logging.sh to be loaded first" >&2
    exit 1
fi

# ============================================================================
# CONFIGURATION
# ============================================================================

readonly SOPS_AGE_KEY_DIR="${HOME}/.config/sops/age"
readonly SOPS_AGE_KEY_FILE="${SOPS_AGE_KEY_DIR}/keys.txt"
readonly SECRETS_STATE_DIR="${STATE_DIR}/secrets"
readonly SECRETS_BACKUP_DIR="${SECRETS_STATE_DIR}/backups"
readonly PLAIN_SECRETS_DIR="${HOME}/.cache/nixos-quick-deploy/preferences"

# ============================================================================
# Helper Utilities
# ============================================================================

ensure_secrets_dependency() {
    local command_name="$1"
    local nix_attr="${2:-}"
    local friendly_name="${3:-$command_name}"
    local flake_ref="${4:-}"

    if command -v "$command_name" >/dev/null 2>&1; then
        return 0
    fi

    if [[ -n "$nix_attr" && -x "$(command -v nix-env 2>/dev/null || true)" ]]; then
        log INFO "Installing ${friendly_name} via nix-env ($nix_attr)..."
        if nix-env -iA "$nix_attr" 2>&1 | tee -a "$LOG_FILE"; then
            return 0
        fi
        log WARNING "nix-env failed to install ${friendly_name}"
    fi

    if [[ -n "$flake_ref" && -x "$(command -v nix 2>/dev/null || true)" ]]; then
        log INFO "Installing ${friendly_name} via nix profile install ($flake_ref)..."
        if nix profile install --accept-flake-config "$flake_ref" 2>&1 | tee -a "$LOG_FILE"; then
            return 0
        fi
        log WARNING "nix profile failed to install ${friendly_name}"
    fi

    log ERROR "${friendly_name} is required but was not installed automatically. Install it manually (e.g., nix profile install --accept-flake-config ${flake_ref:-nixpkgs#$command_name}) and rerun."
    return 1
}

# ============================================================================
# AGE KEY MANAGEMENT
# ============================================================================

# Generate a new age key if one doesn't exist
# Returns: 0 on success, 1 on failure
generate_age_key() {
    log INFO "Generating age encryption key"

    if [[ -f "$SOPS_AGE_KEY_FILE" ]]; then
        log WARNING "Age key already exists at $SOPS_AGE_KEY_FILE"
        return 0
    fi

    # Create key directory
    mkdir -p "$SOPS_AGE_KEY_DIR"
    chmod 700 "$SOPS_AGE_KEY_DIR"

    # Generate new age key
    if ! command -v age-keygen >/dev/null 2>&1; then
        log WARNING "age-keygen not found. Attempting to install age tooling automatically."
        if ! ensure_secrets_dependency "age-keygen" "nixpkgs.age" "age (age-keygen)" "nixpkgs#age"; then
            log ERROR "age-keygen not found. Install age package first."
            return 1
        fi
    fi

    if age-keygen -o "$SOPS_AGE_KEY_FILE" 2>&1 | tee -a "$LOG_FILE"; then
        chmod 600 "$SOPS_AGE_KEY_FILE"
        log INFO "Age key generated successfully"
        return 0
    else
        log ERROR "Failed to generate age key"
        return 1
    fi
}

# Extract public key from age private key
# Returns: Public key string on stdout, empty on failure
get_age_public_key() {
    if [[ ! -f "$SOPS_AGE_KEY_FILE" ]]; then
        log ERROR "Age key file not found: $SOPS_AGE_KEY_FILE"
        return 1
    fi

    # Extract public key from private key file
    local public_key
    public_key=$(grep "^# public key:" "$SOPS_AGE_KEY_FILE" 2>/dev/null | awk '{print $NF}')

    if [[ -z "$public_key" ]]; then
        log ERROR "Failed to extract public key from $SOPS_AGE_KEY_FILE"
        return 1
    fi

    echo "$public_key"
}

# Verify age key is valid and accessible
# Returns: 0 if valid, 1 otherwise
verify_age_key() {
    if [[ ! -f "$SOPS_AGE_KEY_FILE" ]]; then
        log ERROR "Age key file not found"
        return 1
    fi

    if [[ ! -r "$SOPS_AGE_KEY_FILE" ]]; then
        log ERROR "Age key file not readable"
        return 1
    fi

    local public_key
    public_key=$(get_age_public_key)

    if [[ -z "$public_key" ]]; then
        log ERROR "Invalid age key format"
        return 1
    fi

    log INFO "Age key verified: ${public_key:0:20}..."
    return 0
}

# ============================================================================
# SECRET MIGRATION
# ============================================================================

# Backup existing plain text secrets before migration
# Returns: 0 on success, 1 on failure
backup_plain_secrets() {
    log INFO "Backing up plain text secrets"

    mkdir -p "$SECRETS_BACKUP_DIR"

    local backup_timestamp
    backup_timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_dir="${SECRETS_BACKUP_DIR}/plain-secrets-${backup_timestamp}"

    if [[ -d "$PLAIN_SECRETS_DIR" ]]; then
        if cp -r "$PLAIN_SECRETS_DIR" "$backup_dir" 2>&1 | tee -a "$LOG_FILE"; then
            log INFO "Plain secrets backed up to: $backup_dir"
            return 0
        else
            log ERROR "Failed to backup plain secrets"
            return 1
        fi
    else
        log WARNING "No plain secrets directory found at $PLAIN_SECRETS_DIR"
        return 0
    fi
}

# Extract secrets from plain text preference files
# Args: $1 - output YAML file
# Returns: 0 on success, 1 on failure
extract_plain_secrets() {
    local output_file="$1"

    log INFO "Extracting secrets from plain text files"

    # Check if plain secrets exist
    if [[ ! -d "$PLAIN_SECRETS_DIR" ]]; then
        log WARNING "No plain secrets to extract"
        return 0
    fi

    # Extract Hugging Face token
    local hf_token=""
    if [[ -f "${PLAIN_SECRETS_DIR}/huggingface-token.env" ]]; then
        hf_token=$(grep "HUGGINGFACEHUB_API_TOKEN=" "${PLAIN_SECRETS_DIR}/huggingface-token.env" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
    fi

    # Extract Gitea secrets from state directory
    local gitea_secret_key=""
    local gitea_internal_token=""
    local gitea_lfs_jwt=""
    local gitea_jwt=""

    if [[ -d "/var/lib/nixos-quick-deploy/secrets" ]]; then
        if [[ -f "/var/lib/nixos-quick-deploy/secrets/gitea-secret-key" ]]; then
            gitea_secret_key=$(cat "/var/lib/nixos-quick-deploy/secrets/gitea-secret-key" 2>/dev/null)
        fi
        if [[ -f "/var/lib/nixos-quick-deploy/secrets/gitea-internal-token" ]]; then
            gitea_internal_token=$(cat "/var/lib/nixos-quick-deploy/secrets/gitea-internal-token" 2>/dev/null)
        fi
    fi

    # Update secrets.yaml template with extracted values
    log INFO "Extracted secrets will be encrypted in next phase"

    # Store extracted secrets temporarily
    cat > "${SECRETS_STATE_DIR}/extracted-secrets.env" << EOF
HUGGINGFACE_TOKEN=${hf_token}
GITEA_SECRET_KEY=${gitea_secret_key}
GITEA_INTERNAL_TOKEN=${gitea_internal_token}
GITEA_LFS_JWT_SECRET=${gitea_lfs_jwt}
GITEA_JWT_SECRET=${gitea_jwt}
EOF

    chmod 600 "${SECRETS_STATE_DIR}/extracted-secrets.env"

    log INFO "Secrets extracted to temporary storage"
    return 0
}

# ============================================================================
# SOPS OPERATIONS
# ============================================================================

# Initialize sops for the project
# Returns: 0 on success, 1 on failure
init_sops() {
    log INFO "Initializing sops-nix"

    # Ensure age key exists
    if ! verify_age_key; then
        log INFO "Generating new age key"
        if ! generate_age_key; then
            return 1
        fi
    fi

    # Create secrets state directory
    mkdir -p "$SECRETS_STATE_DIR"

    # Verify sops is available
    if ! command -v sops >/dev/null 2>&1; then
        log WARNING "sops binary not found; attempting automatic installation."
        if ! ensure_secrets_dependency "sops" "nixpkgs.sops" "sops" "nixpkgs#sops"; then
            log ERROR "Failed to install sops"
            return 1
        fi
    fi

    log INFO "sops-nix initialized successfully"
    return 0
}

# Encrypt secrets file using sops
# Args: $1 - path to secrets file
# Returns: 0 on success, 1 on failure
encrypt_secrets_file() {
    local secrets_file="$1"

    if [[ ! -f "$secrets_file" ]]; then
        log ERROR "Secrets file not found: $secrets_file"
        return 1
    fi

    log INFO "Encrypting secrets file: $secrets_file"

    # Ensure SOPS_AGE_KEY_FILE is set for sops
    export SOPS_AGE_KEY_FILE

    # Check if file is already encrypted
    if grep -q "^sops:" "$secrets_file" 2>/dev/null; then
        log WARNING "File already encrypted: $secrets_file"
        return 0
    fi

    # Encrypt the file in-place
    if sops -e -i "$secrets_file" 2>&1 | tee -a "$LOG_FILE"; then
        log INFO "Secrets file encrypted successfully"
        return 0
    else
        log ERROR "Failed to encrypt secrets file"
        return 1
    fi
}

# Decrypt secrets file (for validation/debugging)
# Args: $1 - path to encrypted file
# Returns: Decrypted content on stdout
decrypt_secrets_file() {
    local secrets_file="$1"

    if [[ ! -f "$secrets_file" ]]; then
        log ERROR "Secrets file not found: $secrets_file"
        return 1
    fi

    export SOPS_AGE_KEY_FILE

    if sops -d "$secrets_file" 2>/dev/null; then
        return 0
    else
        log ERROR "Failed to decrypt secrets file"
        return 1
    fi
}

# Validate encrypted secrets file
# Args: $1 - path to secrets file
# Returns: 0 if valid, 1 otherwise
validate_encrypted_secrets() {
    local secrets_file="$1"

    log INFO "Validating encrypted secrets file"

    # Try to decrypt
    if decrypt_secrets_file "$secrets_file" > /dev/null 2>&1; then
        log INFO "Secrets file is valid and decryptable"
        return 0
    else
        log ERROR "Secrets file validation failed"
        return 1
    fi
}

# ============================================================================
# SECRET ROTATION
# ============================================================================

# Rotate Gitea secrets
# Returns: 0 on success, 1 on failure
rotate_gitea_secrets() {
    log INFO "Rotating Gitea secrets"

    # Generate new secrets
    local new_secret_key
    local new_internal_token
    local new_lfs_jwt
    local new_jwt

    new_secret_key=$(openssl rand -hex 32)
    new_internal_token=$(openssl rand -hex 80)
    new_lfs_jwt=$(openssl rand -hex 32)
    new_jwt=$(openssl rand -hex 32)

    # Update secrets file (this requires sops to be configured)
    log INFO "New Gitea secrets generated. Update secrets.yaml with:"
    log INFO "  secret_key: ${new_secret_key:0:20}..."
    log INFO "  internal_token: ${new_internal_token:0:20}..."

    return 0
}

# ============================================================================
# CLEANUP
# ============================================================================

# Securely delete plain text secrets after migration
# Returns: 0 on success, 1 on failure
cleanup_plain_secrets() {
    log WARNING "Cleaning up plain text secrets"

    # Ensure backup exists before cleanup
    if ! ls "${SECRETS_BACKUP_DIR}"/plain-secrets-* >/dev/null 2>&1; then
        log ERROR "No backup found. Refusing to delete plain secrets."
        log ERROR "Run backup_plain_secrets first."
        return 1
    fi

    # Securely delete preference files
    if [[ -d "$PLAIN_SECRETS_DIR" ]]; then
        log INFO "Securely deleting: $PLAIN_SECRETS_DIR"
        if shred -vfz -n 3 "${PLAIN_SECRETS_DIR}"/*.env 2>&1 | tee -a "$LOG_FILE"; then
            log INFO "Plain secrets securely deleted"
        else
            log WARNING "shred failed, using rm"
            rm -f "${PLAIN_SECRETS_DIR}"/*.env
        fi
    fi

    # Clean up /var/lib secrets (requires sudo)
    if [[ -d "/var/lib/nixos-quick-deploy/secrets" ]]; then
        log INFO "Cleaning up system secrets (requires sudo)"
        sudo shred -vfz -n 3 /var/lib/nixos-quick-deploy/secrets/* 2>&1 | tee -a "$LOG_FILE" || true
    fi

    log INFO "Plain text secrets cleanup complete"
    return 0
}

# ============================================================================
# MAIN WORKFLOW FUNCTIONS
# ============================================================================

# Complete secret migration workflow
# Returns: 0 on success, 1 on failure
migrate_secrets_to_sops() {
    log INFO "Starting secret migration to sops-nix"

    # Step 1: Initialize sops
    if ! init_sops; then
        log ERROR "Failed to initialize sops"
        return 1
    fi

    # Step 2: Backup plain secrets
    if ! backup_plain_secrets; then
        log ERROR "Failed to backup plain secrets"
        return 1
    fi

    # Step 3: Extract secrets
    mkdir -p "$SECRETS_STATE_DIR"
    if ! extract_plain_secrets "${SECRETS_STATE_DIR}/extracted-secrets.yaml"; then
        log ERROR "Failed to extract plain secrets"
        return 1
    fi

    log INFO "Secret migration prepared successfully"
    log INFO "Next steps:"
    log INFO "  1. Review extracted secrets in: ${SECRETS_STATE_DIR}/extracted-secrets.env"
    log INFO "  2. Secrets will be encrypted during next configuration generation"
    log INFO "  3. After verification, run cleanup_plain_secrets to remove old files"

    return 0
}

# Verify sops configuration is working
# Returns: 0 if working, 1 otherwise
verify_sops_configuration() {
    log INFO "Verifying sops configuration"

    # Check age key
    if ! verify_age_key; then
        return 1
    fi

    # Check sops binary
    if ! command -v sops >/dev/null 2>&1; then
        log ERROR "sops binary not found"
        return 1
    fi

    # Check if we can create a test encrypted file
    local test_file="/tmp/sops-test-$$"
    echo "test: secret" > "$test_file"

    export SOPS_AGE_KEY_FILE

    if sops -e -i "$test_file" 2>&1 | tee -a "$LOG_FILE"; then
        if sops -d "$test_file" > /dev/null 2>&1; then
            rm -f "$test_file"
            log INFO "sops configuration verified successfully"
            return 0
        fi
    fi

    rm -f "$test_file"
    log ERROR "sops configuration verification failed"
    return 1
}

log INFO "Secrets management library loaded (sops-nix v5.0.0)"
