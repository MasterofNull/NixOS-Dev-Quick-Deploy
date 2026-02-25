# NixOS Quick Deploy - Secrets Encryption Error Fix Guide

## Error Summary

Three related errors occurring on fresh NixOS installation:

1. **failed to encrypt secrets.yaml**
2. **failed to prepare encrypted secrets.yaml for sops-nix**
3. **failed to generate NixOS system configuration**

## Root Cause Analysis

### Error Chain

The errors follow this sequence:

```
Phase 3 Configuration Generation
    ↓
generate_nixos_system_config() [lib/config.sh:3199]
    ↓
render_sops_secrets_file() [lib/config.sh:2022]
    ↓
├─ init_sops() [lib/secrets.sh:250]
│  └─ Missing dependencies: age-keygen, sops
│
├─ render_sops_config_file() [lib/config.sh:2128]
│  └─ Missing .sops.yaml template OR age key
│
└─ encrypt_secrets_file() [lib/secrets.sh:280]
   └─ Missing sops binary OR invalid .sops.yaml
```

### Specific Root Causes

#### 1. Missing Dependencies

On a fresh NixOS install, required tools may not be available:

- **age-keygen** - Encryption key generation tool
- **sops** - Secret Operations tool for encryption
- **jq** - JSON processor (used for validation)

**Location in code**: [lib/secrets.sh:99-105, 265-271](lib/secrets.sh)

```bash
# lib/secrets.sh:99-105
if ! command -v age-keygen >/dev/null 2>&1; then
    log WARNING "age-keygen not found. Attempting to install age tooling automatically."
    if ! ensure_secrets_dependency "age-keygen" "nixpkgs.age" "age (age-keygen)" "nixpkgs#age"; then
        log ERROR "age-keygen not found. Install age package first."
        return 1
    fi
fi
```

**Why it fails**:
- `ensure_secrets_dependency()` tries `nix-env -iA` then `nix profile install`
- On fresh install, nix may not have channels initialized
- Network issues or nix store not ready

#### 2. Missing Age Key

If age key doesn't exist and generation fails:

**Location**: [lib/secrets.sh:86-115](lib/secrets.sh)

```bash
# lib/secrets.sh:107-114
if age-keygen -o "$SOPS_AGE_KEY_FILE" 2>&1 | tee -a "$LOG_FILE"; then
    chmod 600 "$SOPS_AGE_KEY_FILE"
    log INFO "Age key generated successfully"
    return 0
else
    log ERROR "Failed to generate age key"
    return 1
fi
```

**Why it fails**:
- Directory permissions on `~/.config/sops/age/`
- Disk space issues
- age-keygen binary corrupted or incompatible

#### 3. Missing or Invalid .sops.yaml Template

**Location**: [lib/config.sh:2138-2143](lib/config.sh)

```bash
# lib/config.sh:2138-2143
local sops_template="${SCRIPT_DIR}/templates/.sops.yaml"
local sops_target="${destination_dir}/.sops.yaml"

if [[ ! -f "$sops_template" ]]; then
    print_error "sops configuration template not found: $sops_template"
    return 1
fi
```

**Why it fails**:
- Template file missing from templates directory
- SCRIPT_DIR variable not set correctly
- File permissions prevent reading

#### 4. Encryption Failure

**Location**: [lib/secrets.sh:280-307](lib/secrets.sh)

```bash
# lib/secrets.sh:300-306
if sops -e -i "$secrets_file" 2>&1 | tee -a "$LOG_FILE"; then
    log INFO "Secrets file encrypted successfully"
    return 0
else
    log ERROR "Failed to encrypt secrets file"
    return 1
fi
```

**Why it fails**:
- `SOPS_AGE_KEY_FILE` environment variable not exported
- Invalid .sops.yaml configuration
- sops binary issues
- Permissions on secrets.yaml file

#### 5. Missing Placeholder Values

**Location**: [lib/config.sh:2109-2111](lib/config.sh)

```bash
if ! nix_verify_no_placeholders "$secrets_target" "secrets.yaml" "GITEA_[A-Z_]+_PLACEHOLDER" "HUGGINGFACE_TOKEN_PLACEHOLDER" "USER_PASSWORD_HASH_PLACEHOLDER"; then
    return 1
fi
```

**Why it fails**:
- Required environment variables not set
- Placeholders not replaced in template
- Template substitution function failing

## Fix Solutions

### Solution 1: Pre-install Required Dependencies

Add to Phase 1 (System Initialization) to ensure dependencies exist before Phase 3:

```bash
# phases/phase-01-system-initialization.sh

install_secrets_dependencies() {
    print_info "Installing secrets management dependencies..."

    # Install age for encryption
    if ! command -v age-keygen >/dev/null 2>&1; then
        print_info "Installing age..."
        nix-env -iA nixpkgs.age || nix profile install nixpkgs#age
    fi

    # Install sops for secret management
    if ! command -v sops >/dev/null 2>&1; then
        print_info "Installing sops..."
        nix-env -iA nixpkgs.sops || nix profile install nixpkgs#sops
    fi

    # Install jq for JSON processing
    if ! command -v jq >/dev/null 2>&1; then
        print_info "Installing jq..."
        nix-env -iA nixpkgs.jq || nix profile install nixpkgs#jq
    fi

    print_success "Secrets dependencies installed"
}
```

### Solution 2: Initialize Secrets Early

Add explicit secrets initialization in Phase 2 (after backup, before config generation):

```bash
# Add to Phase 2 or early Phase 3

initialize_secrets_infrastructure() {
    print_section "Secrets Infrastructure Setup"

    # Create directories
    mkdir -p "$SOPS_AGE_KEY_DIR"
    chmod 700 "$SOPS_AGE_KEY_DIR"

    # Generate age key if missing
    if [[ ! -f "$SOPS_AGE_KEY_FILE" ]]; then
        print_info "Generating age encryption key..."
        if ! age-keygen -o "$SOPS_AGE_KEY_FILE"; then
            print_error "Failed to generate age key"
            return 1
        fi
        chmod 600 "$SOPS_AGE_KEY_FILE"
        print_success "Age key generated"
    fi

    # Verify key
    local public_key
    public_key=$(grep "^# public key:" "$SOPS_AGE_KEY_FILE" | awk '{print $NF}')
    if [[ -z "$public_key" ]]; then
        print_error "Invalid age key format"
        return 1
    fi

    print_info "Age public key: ${public_key:0:20}..."
    print_success "Secrets infrastructure ready"
}
```

### Solution 3: Add Comprehensive Error Handling

Enhance `render_sops_secrets_file()` with better diagnostics:

```bash
render_sops_secrets_file() {
    local backup_dir="$1"
    local backup_timestamp="$2"

    # Validate environment
    print_info "Validating secrets environment..."

    if [[ -z "${HM_CONFIG_DIR:-}" ]]; then
        print_error "HM_CONFIG_DIR is undefined"
        return 1
    fi

    if [[ -z "${SCRIPT_DIR:-}" ]]; then
        print_error "SCRIPT_DIR is undefined"
        return 1
    fi

    # Check templates exist
    local secrets_template="${SCRIPT_DIR}/templates/secrets.yaml"
    local sops_template="${SCRIPT_DIR}/templates/.sops.yaml"

    if [[ ! -f "$secrets_template" ]]; then
        print_error "Missing template: $secrets_template"
        print_info "Available templates:"
        ls -la "${SCRIPT_DIR}/templates/" || true
        return 1
    fi

    if [[ ! -f "$sops_template" ]]; then
        print_error "Missing template: $sops_template"
        return 1
    fi

    # Check dependencies
    print_info "Checking secrets dependencies..."
    for cmd in age-keygen sops jq; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            print_error "Required command missing: $cmd"
            print_info "Install with: nix profile install nixpkgs#$cmd"
            return 1
        fi
        print_info "  ✓ $cmd found at $(command -v $cmd)"
    done

    # Initialize sops (generates age key if needed)
    print_info "Initializing sops..."
    if ! init_sops; then
        print_error "Failed to initialize sops"
        print_info "Check age key at: $SOPS_AGE_KEY_FILE"
        return 1
    fi

    # Generate .sops.yaml config
    print_info "Generating .sops.yaml configuration..."
    if ! render_sops_config_file "$HM_CONFIG_DIR" "$backup_dir" "$backup_timestamp"; then
        print_error "Failed to generate .sops.yaml"
        return 1
    fi

    # Verify .sops.yaml exists
    if [[ ! -f "${HM_CONFIG_DIR}/.sops.yaml" ]]; then
        print_error ".sops.yaml not created at ${HM_CONFIG_DIR}/.sops.yaml"
        return 1
    fi

    # Rest of the function continues...
    # (copy template, replace placeholders, encrypt, validate)

    # IMPORTANT: Export SOPS_AGE_KEY_FILE before encryption
    export SOPS_AGE_KEY_FILE

    # Encrypt with verbose error handling
    print_info "Encrypting secrets.yaml..."
    local secrets_target="${HM_CONFIG_DIR}/secrets.yaml"

    if ! sops -e -i "$secrets_target" 2>&1 | tee -a "$LOG_FILE"; then
        print_error "Encryption failed"
        print_info "SOPS_AGE_KEY_FILE=$SOPS_AGE_KEY_FILE"
        print_info "Secrets file: $secrets_target"
        print_info ".sops.yaml location: ${HM_CONFIG_DIR}/.sops.yaml"

        # Show .sops.yaml content for debugging
        print_info ".sops.yaml contents:"
        cat "${HM_CONFIG_DIR}/.sops.yaml" | head -20

        return 1
    fi

    print_success "Secrets encrypted successfully"
    return 0
}
```

### Solution 4: Fallback for Missing Secrets

Allow deployment to continue with empty secrets if encryption fails:

```bash
# Add graceful degradation option

if [[ "${ALLOW_EMPTY_SECRETS:-false}" == "true" ]]; then
    print_warning "ALLOW_EMPTY_SECRETS enabled - using empty secrets file"
    cat > "${HM_CONFIG_DIR}/secrets.yaml" << 'EOF'
# Empty secrets file - fill manually with: sops secrets.yaml
gitea:
  secret_key: ""
  internal_token: ""
  lfs_jwt_secret: ""
  jwt_secret: ""
  admin_password: ""
huggingface:
  token: ""
user:
  password_hash: ""
EOF
    return 0
fi
```

### Solution 5: Automated Fix Script

Create a standalone diagnostic and fix script:

```bash
#!/usr/bin/env bash
# fix-secrets-encryption.sh

set -euo pipefail

echo "=== NixOS Quick Deploy - Secrets Encryption Fix ==="
echo

# Check current state
echo "Checking current environment..."

# Check dependencies
echo "1. Checking dependencies..."
for cmd in age-keygen sops jq; do
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "  ✓ $cmd: $(command -v $cmd)"
    else
        echo "  ✗ $cmd: NOT FOUND"
        echo "    Installing $cmd..."
        nix profile install "nixpkgs#$cmd" || nix-env -iA "nixpkgs.$cmd"
    fi
done

# Check age key
echo "2. Checking age encryption key..."
AGE_KEY_FILE="${HOME}/.config/sops/age/keys.txt"
if [[ -f "$AGE_KEY_FILE" ]]; then
    PUBLIC_KEY=$(grep "^# public key:" "$AGE_KEY_FILE" | awk '{print $NF}')
    echo "  ✓ Age key exists: ${PUBLIC_KEY:0:20}..."
else
    echo "  ✗ Age key missing"
    echo "    Generating new age key..."
    mkdir -p "$(dirname "$AGE_KEY_FILE")"
    chmod 700 "$(dirname "$AGE_KEY_FILE")"
    age-keygen -o "$AGE_KEY_FILE"
    chmod 600 "$AGE_KEY_FILE"
    PUBLIC_KEY=$(grep "^# public key:" "$AGE_KEY_FILE" | awk '{print $NF}')
    echo "  ✓ Generated: ${PUBLIC_KEY:0:20}..."
fi

# Check templates
echo "3. Checking templates..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/templates/secrets.yaml" ]]; then
    echo "  ✓ secrets.yaml template exists"
else
    echo "  ✗ secrets.yaml template missing"
    exit 1
fi

if [[ -f "${SCRIPT_DIR}/templates/.sops.yaml" ]]; then
    echo "  ✓ .sops.yaml template exists"
else
    echo "  ✗ .sops.yaml template missing"
    exit 1
fi

# Test encryption
echo "4. Testing encryption..."
TEST_FILE="/tmp/sops-test-$$"
echo "test_secret: hello" > "$TEST_FILE"

export SOPS_AGE_KEY_FILE="$AGE_KEY_FILE"

# Create test .sops.yaml
cat > "${TEST_FILE}.sops.yaml" << EOF
creation_rules:
  - age: >-
      $PUBLIC_KEY
EOF

if sops -e -i "$TEST_FILE" 2>&1; then
    if sops -d "$TEST_FILE" > /dev/null 2>&1; then
        echo "  ✓ Encryption test successful"
        rm -f "$TEST_FILE" "${TEST_FILE}.sops.yaml"
    else
        echo "  ✗ Decryption failed"
        rm -f "$TEST_FILE" "${TEST_FILE}.sops.yaml"
        exit 1
    fi
else
    echo "  ✗ Encryption failed"
    rm -f "$TEST_FILE" "${TEST_FILE}.sops.yaml"
    exit 1
fi

echo
echo "=== All checks passed! ==="
echo "You can now run the deployment script."
echo
echo "Age public key for reference:"
echo "  $PUBLIC_KEY"
```

## Testing the Fixes

1. **On the problematic host**, download the fix script:
   ```bash
   curl -O https://raw.githubusercontent.com/.../fix-secrets-encryption.sh
   chmod +x fix-secrets-encryption.sh
   ./fix-secrets-encryption.sh
   ```

2. **Then run deployment with verbose mode**:
   ```bash
   ./nixos-quick-deploy.sh --host nixos --profile ai-dev
   ```

3. **Check logs for detailed error output**:
   ```bash
   tail -f ~/.cache/nixos-quick-deploy/logs/deploy-*.log
   ```

## Prevention for Future Deployments

Add these checks to Phase 1:

1. Verify nix is fully initialized
2. Pre-install age and sops
3. Generate age key immediately
4. Test encryption before Phase 3
5. Add fallback for missing secrets

## Summary

The errors are caused by a dependency chain failure where:
- Required tools (age, sops) aren't installed on fresh systems
- Age encryption keys don't exist
- Template files can't be found
- Environment variables aren't properly exported

The fix requires ensuring all prerequisites exist BEFORE attempting configuration generation in Phase 3.
