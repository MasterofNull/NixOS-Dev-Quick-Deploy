#!/usr/bin/env bats
#
# Unit tests for lib/secrets-sops.sh
#

load test_helper

setup() {
  source "$LIB_DIR/secrets-sops.sh"

  TEST_ROOT="$(mktemp -d)"
  SECRETS_DIR="$TEST_ROOT/secrets"
  mkdir -p "$SECRETS_DIR"

  SOPS_AGE_KEY_FILE="$TEST_ROOT/age/keys.txt"
  mkdir -p "$(dirname "$SOPS_AGE_KEY_FILE")"

  if command -v age-keygen >/dev/null 2>&1; then
    age-keygen -o "$SOPS_AGE_KEY_FILE" >/dev/null 2>&1
  fi

  export SECRETS_DIR SOPS_AGE_KEY_FILE

  echo "test-secret-1" > "$SECRETS_DIR/aidb_api_key"
  echo "test-secret-2" > "$SECRETS_DIR/postgres_password"
}

teardown() {
  rm -rf "$TEST_ROOT"
}

@test "sops_get_public_key returns age public key" {
  skip_if_missing_tools
  run sops_get_public_key
  [[ "$status" -eq 0 ]]
  [[ "$output" == age* ]]
}

@test "sops_encrypt_secrets_bundle writes encrypted bundle" {
  skip_if_missing_tools
  run sops_encrypt_secrets_bundle "$SECRETS_DIR"
  [[ "$status" -eq 0 ]]
  [[ -f "$SECRETS_DIR/secrets.sops.yaml" ]]
  run grep -nE "^sops:" "$SECRETS_DIR/secrets.sops.yaml"
  [[ "$status" -eq 0 ]]
}

@test "sops_decrypt_bundle returns readable JSON" {
  skip_if_missing_tools
  run sops_encrypt_secrets_bundle "$SECRETS_DIR"
  [[ "$status" -eq 0 ]]
  decrypted="$(sops_decrypt_bundle "$SECRETS_DIR/secrets.sops.yaml")"
  [[ -f "$decrypted" ]]
  run sops_get_secret "aidb_api_key" "$decrypted"
  [[ "$status" -eq 0 ]]
  [[ "$output" == "test-secret-1" ]]
}

@test "sops_remove_plaintext_secrets deletes plaintext files" {
  skip_if_missing_tools
  run sops_remove_plaintext_secrets "$SECRETS_DIR"
  [[ "$status" -eq 0 ]]
  [[ ! -f "$SECRETS_DIR/aidb_api_key" ]]
  [[ ! -f "$SECRETS_DIR/postgres_password" ]]
}

skip_if_missing_tools() {
  if ! command -v sops >/dev/null 2>&1 || ! command -v age >/dev/null 2>&1 || ! command -v age-keygen >/dev/null 2>&1; then
    skip "sops/age not available"
  fi
}
