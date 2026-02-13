#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS_DIR="${SECRETS_DIR:-${SCRIPT_DIR}/ai-stack/kubernetes/secrets}"
BUNDLE="${SECRETS_BUNDLE:-${SECRETS_DIR}/secrets.sops.yaml}"

usage() {
  cat <<USAGE
Usage: $0 [all|KEY...]

Rotates secrets in the SOPS bundle:
  - "all" or no args rotates every key
  - Provide specific keys to rotate only those

Examples:
  $0 all
  $0 postgres_password grafana_admin_password

Notes:
  - Requires sops + age and a valid age key at ~/.config/sops/age/keys.txt
  - After rotation, re-apply secrets to K3s (Phase 9 or kubectl create secret ...)
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -f "$BUNDLE" ]]; then
  echo "[ERROR] Secrets bundle not found: $BUNDLE" >&2
  exit 1
fi

if ! command -v sops >/dev/null 2>&1 || ! command -v age >/dev/null 2>&1; then
  echo "[ERROR] sops/age not found in PATH" >&2
  exit 1
fi

AGE_KEY_FILE="${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}"
if [[ ! -f "$AGE_KEY_FILE" ]]; then
  echo "[ERROR] Age key missing: $AGE_KEY_FILE" >&2
  exit 1
fi

public_key="$(grep '^# public key:' "$AGE_KEY_FILE" | awk '{print $NF}')"
if [[ -z "$public_key" ]]; then
  echo "[ERROR] Unable to read age public key from $AGE_KEY_FILE" >&2
  exit 1
fi

rotate_all=true
rotate_keys=()
if [[ $# -gt 0 && "$1" != "all" ]]; then
  rotate_all=false
  rotate_keys=("$@")
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

decrypted_json="${tmp_dir}/secrets.json"
updated_json="${tmp_dir}/secrets.updated.json"

sops -d --output-type json "$BUNDLE" > "$decrypted_json"

python3 - <<'PY' "$decrypted_json" "$updated_json" "${rotate_all}" "${rotate_keys[@]}"
import json
import secrets
import sys

src_path = sys.argv[1]
dst_path = sys.argv[2]
rotate_all = sys.argv[3].lower() == "true"
rotate_keys = set(sys.argv[4:])

with open(src_path, "r", encoding="utf-8") as f:
    data = json.load(f)

def gen_value(key: str) -> str:
    if "password" in key:
        return secrets.token_urlsafe(24)
    return secrets.token_hex(32)

for key in list(data.keys()):
    if rotate_all or key in rotate_keys:
        data[key] = gen_value(key)

with open(dst_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=True)
PY

sops --encrypt \
  --age "$public_key" \
  --input-type json \
  --output-type yaml \
  --filename-override "$BUNDLE" \
  "$updated_json" > "$BUNDLE"

echo "[OK] Rotated secrets in $BUNDLE"
