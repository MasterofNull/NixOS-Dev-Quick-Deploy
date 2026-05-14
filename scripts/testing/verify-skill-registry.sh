#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# verify-skill-registry.sh — Phase 40 (PAR-008) Trust Verification
#
# Verify a skill registry index.json against a detached signature using a
# trusted public key.  Also supports checking against a trust-roots config
# to prevent unrecognised keys from being used as verification anchors.
#
# Usage:
#   verify-skill-registry.sh [INDEX] [SIG] [PUBKEY]
#   verify-skill-registry.sh --trust-roots <trust-roots.json> [INDEX] [SIG] [PUBKEY]
#   verify-skill-registry.sh --help
#
# Defaults (when not provided):
#   INDEX   — ${ROOT}/dist/skills/index.json
#   SIG     — ${INDEX}.sig
#   PUBKEY  — ${ROOT}/config/keys/skill-registry-public.pem
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    sed -n '/^# Usage/,/^# ---/p' "$0" | sed 's/^# \?//'
    exit 0
}

TRUST_ROOTS_FILE=""
POSITIONAL=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --trust-roots) TRUST_ROOTS_FILE="$2"; shift 2 ;;
        --help|-h)     usage ;;
        *)             POSITIONAL+=("$1"); shift ;;
    esac
done

INDEX_PATH="${POSITIONAL[0]:-${ROOT}/dist/skills/index.json}"
SIG_PATH="${POSITIONAL[1]:-${INDEX_PATH}.sig}"
PUBKEY_PATH="${POSITIONAL[2]:-${ROOT}/config/keys/skill-registry-public.pem}"

# Default trust-roots file
if [[ -z "$TRUST_ROOTS_FILE" ]]; then
    TRUST_ROOTS_FILE="${TRUST_ROOTS_FILE:-${SKILL_REGISTRY_TRUST_ROOTS:-${ROOT}/config/keys/skill-registry-trust-roots.json}}"
fi

echo "━━━ Skill Registry Trust Verification ━━━"
echo "  index:       ${INDEX_PATH}"
echo "  signature:   ${SIG_PATH}"
echo "  public key:  ${PUBKEY_PATH}"
[[ -n "$TRUST_ROOTS_FILE" ]] && echo "  trust roots: ${TRUST_ROOTS_FILE}"
echo ""

# 1. Prerequisites
if ! command -v openssl >/dev/null 2>&1; then
    echo -e "${RED}ERROR:${NC} openssl is required but not found in PATH" >&2
    exit 1
fi

if [[ ! -f "$INDEX_PATH" ]]; then
    echo -e "${RED}ERROR:${NC} index not found: $INDEX_PATH" >&2
    exit 1
fi

if [[ ! -f "$SIG_PATH" ]]; then
    echo -e "${RED}ERROR:${NC} signature not found: $SIG_PATH" >&2
    exit 1
fi

if [[ ! -f "$PUBKEY_PATH" ]]; then
    echo -e "${RED}ERROR:${NC} public key not found: $PUBKEY_PATH" >&2
    exit 1
fi

# 2. Trust-roots check: verify the public key fingerprint is in the trusted set
if [[ -f "$TRUST_ROOTS_FILE" ]]; then
    KEY_FP="$(openssl pkey -pubin -in "$PUBKEY_PATH" -outform DER 2>/dev/null \
              | openssl dgst -sha256 -hex 2>/dev/null | awk '{print $2}' || true)"
    if [[ -z "$KEY_FP" ]]; then
        echo -e "${RED}ERROR:${NC} could not compute public key fingerprint" >&2
        exit 1
    fi
    if ! python3 - "$TRUST_ROOTS_FILE" "$KEY_FP" <<'PYEOF'
import json, sys
roots_file, fp = sys.argv[1], sys.argv[2]
data = json.load(open(roots_file))
trusted = [str(r.get("fingerprint_sha256","")).lower() for r in data.get("trusted_keys",[])]
active  = [t for t in trusted if t and data.get("trusted_keys",[])[trusted.index(t)].get("status","active") == "active"]
if fp.lower() in active:
    sys.exit(0)
sys.stderr.write(f"fingerprint not in active trust set: {fp}\n")
sys.exit(1)
PYEOF
    then
        echo -e "${RED}FAIL:${NC} public key fingerprint not in trust roots — key may be untrusted or revoked" >&2
        exit 1
    fi
    echo -e "${GREEN}PASS:${NC} public key fingerprint verified against trust roots"
else
    echo -e "${YELLOW}WARN:${NC} trust-roots file not found — skipping trust-set check (single-key verification only)"
fi

# 3. Signature verification
if openssl dgst -sha256 -verify "$PUBKEY_PATH" -signature "$SIG_PATH" "$INDEX_PATH" >/dev/null 2>&1; then
    echo -e "${GREEN}PASS:${NC} signature verified (SHA-256 RSA)"
else
    echo -e "${RED}FAIL:${NC} signature verification FAILED — index may be tampered" >&2
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}OK: registry index is trusted and unmodified.${NC}"
