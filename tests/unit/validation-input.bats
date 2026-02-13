#!/usr/bin/env bats
#
# Unit tests for lib/validation-input.sh
#

load test_helper

TMP_ROOT="${TMPDIR:-/${TMP_FALLBACK:-tmp}}"

setup() {
    source "$LIB_DIR/validation-input.sh"
}

# ============================================================================
# validate_hostname
# ============================================================================

@test "validate_hostname: accepts simple hostname" {
    run validate_hostname "myhost"
    [[ "$status" -eq 0 ]]
}

@test "validate_hostname: accepts hostname with dots" {
    run validate_hostname "my.host.local"
    [[ "$status" -eq 0 ]]
}

@test "validate_hostname: accepts hostname with hyphens" {
    run validate_hostname "my-host"
    [[ "$status" -eq 0 ]]
}

@test "validate_hostname: rejects empty hostname" {
    run validate_hostname ""
    [[ "$status" -eq 1 ]]
}

@test "validate_hostname: rejects uppercase" {
    run validate_hostname "MyHost"
    [[ "$status" -eq 1 ]]
}

@test "validate_hostname: rejects leading hyphen" {
    run validate_hostname "-myhost"
    [[ "$status" -eq 1 ]]
}

@test "validate_hostname: rejects trailing hyphen" {
    run validate_hostname "myhost-"
    [[ "$status" -eq 1 ]]
}

@test "validate_hostname: rejects label > 63 chars" {
    local long_label
    long_label=$(printf 'a%.0s' {1..64})
    run validate_hostname "$long_label"
    [[ "$status" -eq 1 ]]
}

@test "validate_hostname: accepts label exactly 63 chars" {
    local label
    label=$(printf 'a%.0s' {1..63})
    run validate_hostname "$label"
    [[ "$status" -eq 0 ]]
}

# ============================================================================
# validate_username
# ============================================================================

@test "validate_username: accepts simple username" {
    run validate_username "alice"
    [[ "$status" -eq 0 ]]
}

@test "validate_username: accepts underscore prefix" {
    run validate_username "_svc"
    [[ "$status" -eq 0 ]]
}

@test "validate_username: accepts hyphens and digits" {
    run validate_username "user-01"
    [[ "$status" -eq 0 ]]
}

@test "validate_username: rejects empty" {
    run validate_username ""
    [[ "$status" -eq 1 ]]
}

@test "validate_username: rejects starting with digit" {
    run validate_username "1user"
    [[ "$status" -eq 1 ]]
}

@test "validate_username: rejects uppercase" {
    run validate_username "Alice"
    [[ "$status" -eq 1 ]]
}

@test "validate_username: rejects special characters" {
    run validate_username 'user;rm -rf /'
    [[ "$status" -eq 1 ]]
}

@test "validate_username: rejects > 32 chars" {
    local long_name
    long_name=$(printf 'a%.0s' {1..33})
    run validate_username "$long_name"
    [[ "$status" -eq 1 ]]
}

# ============================================================================
# validate_path
# ============================================================================

@test "validate_path: accepts absolute path" {
    run validate_path "/tmp"
    [[ "$status" -eq 0 ]]
}

@test "validate_path: rejects empty" {
    run validate_path ""
    [[ "$status" -eq 1 ]]
}

@test "validate_path: rejects path traversal" {
    run validate_path "${HOME}/../etc/passwd"
    [[ "$status" -eq 1 ]]
}

@test "validate_path: rejects command substitution \$()" {
    run validate_path "${TMP_ROOT}/\$(rm -rf /)"
    [[ "$status" -eq 1 ]]
}

@test "validate_path: rejects backtick command substitution" {
    run validate_path "${TMP_ROOT}/\`whoami\`"
    [[ "$status" -eq 1 ]]
}

@test "validate_path: rejects semicolons" {
    run validate_path "${TMP_ROOT}/foo;rm -rf /"
    [[ "$status" -eq 1 ]]
}

@test "validate_path: rejects pipe" {
    run validate_path "${TMP_ROOT}/foo|cat /etc/passwd"
    [[ "$status" -eq 1 ]]
}

# ============================================================================
# validate_integer
# ============================================================================

@test "validate_integer: accepts valid integer" {
    run validate_integer 42
    [[ "$status" -eq 0 ]]
}

@test "validate_integer: accepts negative integer" {
    run validate_integer -5 -10 100
    [[ "$status" -eq 0 ]]
}

@test "validate_integer: rejects non-numeric" {
    run validate_integer "abc"
    [[ "$status" -eq 1 ]]
}

@test "validate_integer: rejects below min" {
    run validate_integer 5 10 100
    [[ "$status" -eq 1 ]]
}

@test "validate_integer: rejects above max" {
    run validate_integer 200 0 100
    [[ "$status" -eq 1 ]]
}

@test "validate_integer: rejects empty" {
    run validate_integer ""
    [[ "$status" -eq 1 ]]
}

# ============================================================================
# validate_password_strength
# ============================================================================

@test "validate_password_strength: rejects short password" {
    run validate_password_strength "Short1!"
    [[ "$status" -eq 1 ]]
}

@test "validate_password_strength: rejects weak password (only lowercase)" {
    run validate_password_strength "abcdefghijklmnop"
    [[ "$status" -eq 1 ]]
}

@test "validate_password_strength: accepts strong password" {
    run validate_password_strength "MyStr0ng!Pass99"
    [[ "$status" -eq 0 ]]
}

@test "validate_password_strength: rejects empty" {
    run validate_password_strength ""
    [[ "$status" -eq 1 ]]
}

# ============================================================================
# validate_nix_attr
# ============================================================================

@test "validate_nix_attr: accepts simple attribute" {
    run validate_nix_attr "nixpkgs"
    [[ "$status" -eq 0 ]]
}

@test "validate_nix_attr: accepts dotted path" {
    run validate_nix_attr "nixpkgs.python3"
    [[ "$status" -eq 0 ]]
}

@test "validate_nix_attr: rejects shell metacharacters" {
    run validate_nix_attr 'nixpkgs;rm -rf /'
    [[ "$status" -eq 1 ]]
}

@test "validate_nix_attr: rejects empty" {
    run validate_nix_attr ""
    [[ "$status" -eq 1 ]]
}

# ============================================================================
# validate_k8s_namespace
# ============================================================================

@test "validate_k8s_namespace: accepts valid namespace" {
    run validate_k8s_namespace "ai-stack"
    [[ "$status" -eq 0 ]]
}

@test "validate_k8s_namespace: rejects uppercase" {
    run validate_k8s_namespace "AiStack"
    [[ "$status" -eq 1 ]]
}

@test "validate_k8s_namespace: rejects > 63 chars" {
    local long_ns
    long_ns=$(printf 'a%.0s' {1..64})
    run validate_k8s_namespace "$long_ns"
    [[ "$status" -eq 1 ]]
}

@test "validate_k8s_namespace: rejects leading hyphen" {
    run validate_k8s_namespace "-bad"
    [[ "$status" -eq 1 ]]
}

# ============================================================================
# sanitize_string
# ============================================================================

@test "sanitize_string: passes through clean input" {
    result=$(sanitize_string "hello world")
    [[ "$result" == "hello world" ]]
}

@test "sanitize_string: escapes single quotes" {
    result=$(sanitize_string "it's")
    [[ "$result" == *"\\'"* ]] || [[ "$result" == "it'\\''s" ]]
}
