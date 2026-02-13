#!/usr/bin/env bash
#
# SOPS/Age Secrets Management
# Purpose: Encrypt, decrypt, and manage secrets using SOPS with age encryption
# Version: 6.1.0
#
# Requires: sops, age (both available via nixpkgs)
#
# ============================================================================

: "${SOPS_AGE_KEY_FILE:=${HOME}/.config/sops/age/keys.txt}"
: "${SECRETS_DIR:=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/ai-stack/kubernetes/secrets}"

# ============================================================================
# Check SOPS/Age prerequisites
# ============================================================================
sops_available() {
    command -v sops >/dev/null 2>&1 && command -v age >/dev/null 2>&1
}

sops_key_exists() {
    [[ -f "$SOPS_AGE_KEY_FILE" ]]
}

# ============================================================================
# Get the public key from the age key file
# ============================================================================
sops_get_public_key() {
    if ! sops_key_exists; then
        echo "Age key file not found: $SOPS_AGE_KEY_FILE" >&2
        return 1
    fi

    grep '^# public key:' "$SOPS_AGE_KEY_FILE" | awk '{print $NF}'
}

# ============================================================================
# Generate a new age key pair (only if one doesn't exist)
# ============================================================================
sops_init_key() {
    if sops_key_exists; then
        if declare -F print_info >/dev/null 2>&1; then
            print_info "Age key already exists at $SOPS_AGE_KEY_FILE"
        fi
        return 0
    fi

    if ! command -v age-keygen >/dev/null 2>&1; then
        echo "age-keygen not found. Install age first." >&2
        return 1
    fi

    mkdir -p "$(dirname "$SOPS_AGE_KEY_FILE")"
    age-keygen -o "$SOPS_AGE_KEY_FILE" 2>/dev/null
    chmod 600 "$SOPS_AGE_KEY_FILE"

    if declare -F print_success >/dev/null 2>&1; then
        print_success "Generated new age key at $SOPS_AGE_KEY_FILE"
    fi
}

# ============================================================================
# Create .sops.yaml config in project root
# ============================================================================
sops_init_config() {
    local project_root="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
    local sops_config="${project_root}/.sops.yaml"
    local public_key

    public_key=$(sops_get_public_key) || return 1

    if [[ -f "$sops_config" ]]; then
        if declare -F print_info >/dev/null 2>&1; then
            print_info ".sops.yaml already exists"
        fi
        return 0
    fi

    cat > "$sops_config" <<EOF
# SOPS configuration for NixOS Quick Deploy secrets
# Age public key: ${public_key}
creation_rules:
  - path_regex: ai-stack/kubernetes/secrets/.*\.enc\.yaml$
    age: ${public_key}
  - path_regex: ai-stack/kubernetes/secrets/.*\.enc\.json$
    age: ${public_key}
  - path_regex: .*secrets\.sops\.yaml$
    age: ${public_key}
EOF

    if declare -F print_success >/dev/null 2>&1; then
        print_success "Created .sops.yaml with age key: ${public_key}"
    fi
}

# ============================================================================
# Encrypt all plaintext secrets into a single SOPS bundle
# ============================================================================
# Reads individual secret files from SECRETS_DIR and creates
# a single encrypted YAML bundle (secrets.sops.yaml)
# ============================================================================
sops_encrypt_secrets_bundle() {
    local secrets_dir="${1:-$SECRETS_DIR}"
    local output="${secrets_dir}/secrets.sops.yaml"
    local public_key

    if ! sops_available; then
        echo "sops or age not found in PATH" >&2
        return 1
    fi

    public_key=$(sops_get_public_key) || return 1

    # Build a JSON object from individual secret files
    local json_obj="{"
    local first=true
    local count=0

    for secret_file in "$secrets_dir"/*; do
        [[ -f "$secret_file" ]] || continue
        local basename
        basename=$(basename "$secret_file")

        # Skip already-encrypted files and non-secret files
        case "$basename" in
            *.sops.yaml|*.sops.json|*.enc.*|.gitkeep|README*) continue ;;
        esac

        local value
        value=$(cat "$secret_file" 2>/dev/null) || continue

        if [[ "$first" == "true" ]]; then
            first=false
        else
            json_obj+=","
        fi

        # Escape the value for JSON
        local escaped_value
        escaped_value=$(printf '%s' "$value" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip()))')

        json_obj+="\"${basename}\":${escaped_value}"
        count=$((count + 1))
    done

    json_obj+="}"

    if [[ $count -eq 0 ]]; then
        echo "No secret files found in $secrets_dir" >&2
        return 1
    fi

    # Encrypt using sops with age
    printf '%s' "$json_obj" | sops --encrypt \
        --age "$public_key" \
        --input-type json \
        --output-type yaml \
        --filename-override "$output" \
        /dev/stdin > "$output"

    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        echo "SOPS encryption failed (exit: $exit_code)" >&2
        return 1
    fi

    if declare -F print_success >/dev/null 2>&1; then
        print_success "Encrypted $count secrets into $output"
    fi

    echo "$output"
}

# ============================================================================
# Decrypt the secrets bundle to a temporary directory
# ============================================================================
# Returns the path to the decrypted JSON file on stdout.
# Caller is responsible for cleaning up with sops_cleanup_decrypted.
# ============================================================================
sops_decrypt_bundle() {
    local bundle="${1:-${SECRETS_DIR}/secrets.sops.yaml}"

    if [[ ! -f "$bundle" ]]; then
        echo "Secrets bundle not found: $bundle" >&2
        return 1
    fi

    if ! sops_available; then
        echo "sops not found in PATH" >&2
        return 1
    fi

    local tmp_dir
    tmp_dir=$(mktemp -d) || return 1
    chmod 700 "$tmp_dir"

    local decrypted="${tmp_dir}/secrets.json"

    if ! sops --decrypt --output-type json "$bundle" > "$decrypted" 2>/dev/null; then
        rm -rf "$tmp_dir"
        echo "Failed to decrypt secrets bundle" >&2
        return 1
    fi

    chmod 600 "$decrypted"
    echo "$decrypted"
}

# ============================================================================
# Read a single secret from a decrypted bundle
# ============================================================================
sops_get_secret() {
    local key="$1"
    local decrypted_json="$2"

    if [[ ! -f "$decrypted_json" ]]; then
        echo "Decrypted bundle not found: $decrypted_json" >&2
        return 1
    fi

    jq -r --arg key "$key" '.[$key] // empty' "$decrypted_json"
}

# ============================================================================
# Clean up decrypted secrets from disk
# ============================================================================
sops_cleanup_decrypted() {
    local path="$1"

    if [[ -z "$path" ]]; then
        return 0
    fi

    # If path is a file, remove its parent temp dir
    if [[ -f "$path" ]]; then
        local dir
        dir=$(dirname "$path")
        local tmp_root="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"
        if [[ "$dir" == "${tmp_root}"/* ]]; then
            rm -rf "$dir"
        else
            rm -f "$path"
        fi
    elif [[ -d "$path" ]]; then
        local tmp_root="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"
        if [[ "$path" == "${tmp_root}"/* ]]; then
            rm -rf "$path"
        fi
    fi
}

# ============================================================================
# Remove plaintext secret files after encryption
# ============================================================================
sops_remove_plaintext_secrets() {
    local secrets_dir="${1:-$SECRETS_DIR}"
    local removed=0

    for secret_file in "$secrets_dir"/*; do
        [[ -f "$secret_file" ]] || continue
        local basename
        basename=$(basename "$secret_file")

        case "$basename" in
            *.sops.yaml|*.sops.json|*.enc.*|.gitkeep|README*) continue ;;
        esac

        rm -f "$secret_file"
        removed=$((removed + 1))
    done

    if declare -F print_info >/dev/null 2>&1; then
        print_info "Removed $removed plaintext secret files from $secrets_dir"
    fi
}

# ============================================================================
# Full setup: init key, config, encrypt, remove plaintext
# ============================================================================
sops_full_setup() {
    local secrets_dir="${1:-$SECRETS_DIR}"

    if ! sops_available; then
        if declare -F print_warning >/dev/null 2>&1; then
            print_warning "sops/age not available — skipping secrets encryption"
        fi
        return 0
    fi

    sops_init_key || return 1
    sops_init_config || return 1

    local bundle
    bundle=$(sops_encrypt_secrets_bundle "$secrets_dir") || return 1

    # Verify we can decrypt before removing plaintext
    local decrypted
    decrypted=$(sops_decrypt_bundle "$bundle") || {
        if declare -F print_error >/dev/null 2>&1; then
            print_error "Encryption verification failed — keeping plaintext secrets"
        fi
        return 1
    }

    # Verify all keys are present
    local key_count
    key_count=$(jq 'keys | length' "$decrypted" 2>/dev/null || echo "0")
    sops_cleanup_decrypted "$decrypted"

    if [[ "$key_count" -eq 0 ]]; then
        if declare -F print_error >/dev/null 2>&1; then
            print_error "Decrypted bundle has no keys — keeping plaintext secrets"
        fi
        return 1
    fi

    sops_remove_plaintext_secrets "$secrets_dir"

    if declare -F print_success >/dev/null 2>&1; then
        print_success "Secrets encrypted and plaintext removed ($key_count secrets)"
    fi
}
