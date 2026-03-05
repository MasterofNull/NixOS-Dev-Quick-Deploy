#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
INDEX_PATH="${1:-${ROOT}/dist/skills/index.json}"
PRIVATE_KEY="${2:-${ROOT}/config/keys/skill-registry-private.pem}"
SIG_PATH="${3:-${INDEX_PATH}.sig}"

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl is required for signing but not found in PATH" >&2
  exit 1
fi

if [[ ! -f "$INDEX_PATH" ]]; then
  echo "ERROR: index not found: $INDEX_PATH" >&2
  exit 1
fi
if [[ ! -f "$PRIVATE_KEY" ]]; then
  echo "ERROR: private key not found: $PRIVATE_KEY" >&2
  echo "Generate one with:" >&2
  echo "  openssl genpkey -algorithm RSA -out \"$PRIVATE_KEY\" -pkeyopt rsa_keygen_bits:3072" >&2
  exit 1
fi

openssl dgst -sha256 -sign "$PRIVATE_KEY" -out "$SIG_PATH" "$INDEX_PATH"
chmod 0644 "$SIG_PATH"
echo "Signed registry index:"
echo "  index: $INDEX_PATH"
echo "  sig:   $SIG_PATH"
