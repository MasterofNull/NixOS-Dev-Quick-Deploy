#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/hyperd/Documents/NixOS-Dev-Quick-Deploy}"
INDEX_PATH="${1:-${ROOT}/dist/skills/index.json}"
PUBLIC_KEY="${2:-${ROOT}/config/keys/skill-registry-public.pem}"
SIG_PATH="${3:-${INDEX_PATH}.sig}"

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl is required for signature verification but not found in PATH" >&2
  exit 1
fi

if [[ ! -f "$INDEX_PATH" ]]; then
  echo "ERROR: index not found: $INDEX_PATH" >&2
  exit 1
fi
if [[ ! -f "$PUBLIC_KEY" ]]; then
  echo "ERROR: public key not found: $PUBLIC_KEY" >&2
  echo "Generate from private key with:" >&2
  echo "  openssl rsa -in <private.pem> -pubout -out \"$PUBLIC_KEY\"" >&2
  exit 1
fi
if [[ ! -f "$SIG_PATH" ]]; then
  echo "ERROR: signature not found: $SIG_PATH" >&2
  exit 1
fi

if openssl dgst -sha256 -verify "$PUBLIC_KEY" -signature "$SIG_PATH" "$INDEX_PATH" >/dev/null 2>&1; then
  echo "[PASS] registry signature verified"
else
  echo "[FAIL] registry signature verification failed" >&2
  exit 1
fi
