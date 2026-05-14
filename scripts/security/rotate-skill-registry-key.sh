#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# rotate-skill-registry-key.sh — Phase 40 (PAR-008) Key Rotation + Revocation
#
# Rotates the skill registry signing key:
#   1. Generates a new RSA-3072 private key + public key
#   2. Archives the old key pair with a timestamp
#   3. Re-signs the registry index if it exists
#   4. Updates config/keys/skill-registry-trust-roots.json:
#      - marks old fingerprint as revoked
#      - adds new fingerprint as active
#
# Usage:
#   rotate-skill-registry-key.sh [--dry-run] [--index INDEX_PATH]
#
# Output:
#   config/keys/skill-registry-private.pem  (new private key)
#   config/keys/skill-registry-public.pem   (new public key)
#   config/keys/archive/skill-registry-private-<ts>.pem
#   config/keys/archive/skill-registry-public-<ts>.pem
#   config/keys/skill-registry-trust-roots.json (updated)
#   dist/skills/index.json.sig              (re-signed, if index exists)
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

DRY_RUN=0
INDEX_PATH="${ROOT}/dist/skills/index.json"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --index)   INDEX_PATH="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: rotate-skill-registry-key.sh [--dry-run] [--index INDEX_PATH]"
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

KEYS_DIR="${ROOT}/config/keys"
ARCHIVE_DIR="${KEYS_DIR}/archive"
PRIVATE_KEY="${KEYS_DIR}/skill-registry-private.pem"
PUBLIC_KEY="${KEYS_DIR}/skill-registry-public.pem"
TRUST_ROOTS="${KEYS_DIR}/skill-registry-trust-roots.json"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

if ! command -v openssl >/dev/null 2>&1; then
    echo -e "${RED}ERROR:${NC} openssl is required but not found in PATH" >&2
    exit 1
fi

echo "━━━ Skill Registry Key Rotation ━━━"
[[ "$DRY_RUN" -eq 1 ]] && echo -e "${YELLOW}[DRY RUN — no files will be written]${NC}"
echo ""

run() {
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "  [dry-run] $*"
    else
        "$@"
    fi
}

# 1. Archive old keys
if [[ -f "$PRIVATE_KEY" || -f "$PUBLIC_KEY" ]]; then
    echo "Archiving existing key pair..."
    run mkdir -p "$ARCHIVE_DIR"
    [[ -f "$PRIVATE_KEY" ]] && run cp "$PRIVATE_KEY" "${ARCHIVE_DIR}/skill-registry-private-${TS}.pem"
    [[ -f "$PUBLIC_KEY" ]]  && run cp "$PUBLIC_KEY"  "${ARCHIVE_DIR}/skill-registry-public-${TS}.pem"
    echo -e "${GREEN}PASS:${NC} old keys archived to ${ARCHIVE_DIR}/"
else
    echo "No existing keys found — generating initial key pair."
fi

# 2. Compute old fingerprint (before replacing)
OLD_FP=""
if [[ -f "$PUBLIC_KEY" ]]; then
    OLD_FP="$(openssl pkey -pubin -in "$PUBLIC_KEY" -outform DER 2>/dev/null \
              | openssl dgst -sha256 -hex 2>/dev/null | awk '{print $2}' || true)"
fi

# 3. Generate new key pair
echo "Generating new RSA-3072 key pair..."
run mkdir -p "$KEYS_DIR"
if [[ "$DRY_RUN" -eq 0 ]]; then
    openssl genpkey -algorithm RSA -out "$PRIVATE_KEY" -pkeyopt rsa_keygen_bits:3072 2>/dev/null
    chmod 0600 "$PRIVATE_KEY"
    openssl pkey -in "$PRIVATE_KEY" -pubout -out "$PUBLIC_KEY" 2>/dev/null
    chmod 0644 "$PUBLIC_KEY"
fi
echo -e "${GREEN}PASS:${NC} new key pair generated: ${PRIVATE_KEY}"

# 4. Compute new fingerprint
NEW_FP=""
if [[ "$DRY_RUN" -eq 0 && -f "$PUBLIC_KEY" ]]; then
    NEW_FP="$(openssl pkey -pubin -in "$PUBLIC_KEY" -outform DER 2>/dev/null \
              | openssl dgst -sha256 -hex 2>/dev/null | awk '{print $2}' || true)"
fi

# 5. Update trust-roots.json
echo "Updating trust roots..."
if [[ "$DRY_RUN" -eq 0 ]]; then
    python3 - "$TRUST_ROOTS" "$OLD_FP" "$NEW_FP" "$TS" <<'PYEOF'
import json, sys
from pathlib import Path

trust_roots_path = Path(sys.argv[1])
old_fp = sys.argv[2]
new_fp = sys.argv[3]
ts     = sys.argv[4]

if trust_roots_path.exists():
    data = json.loads(trust_roots_path.read_text())
else:
    data = {"version": "1.0", "trusted_keys": []}

trusted = data.setdefault("trusted_keys", [])

# Revoke old key
if old_fp:
    for entry in trusted:
        if entry.get("fingerprint_sha256", "").lower() == old_fp.lower():
            entry["status"] = "revoked"
            entry["revoked_at"] = ts

# Add new key
if new_fp:
    trusted.append({
        "fingerprint_sha256": new_fp,
        "status": "active",
        "added_at": ts,
        "algorithm": "RSA-3072",
        "purpose": "skill-registry-signing",
    })

data["last_rotation"] = ts
trust_roots_path.parent.mkdir(parents=True, exist_ok=True)
trust_roots_path.write_text(json.dumps(data, indent=2))
print(f"trust roots updated: {trust_roots_path}")
PYEOF
fi
echo -e "${GREEN}PASS:${NC} trust roots updated: ${TRUST_ROOTS}"

# 6. Re-sign index if present
if [[ -f "$INDEX_PATH" ]]; then
    echo "Re-signing registry index..."
    SIG_PATH="${INDEX_PATH}.sig"
    if [[ "$DRY_RUN" -eq 0 ]]; then
        openssl dgst -sha256 -sign "$PRIVATE_KEY" -out "$SIG_PATH" "$INDEX_PATH"
        chmod 0644 "$SIG_PATH"
    fi
    echo -e "${GREEN}PASS:${NC} index re-signed: ${SIG_PATH}"
else
    echo -e "${YELLOW}WARN:${NC} index not found (${INDEX_PATH}) — skipping re-sign"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}Key rotation complete.${NC}"
[[ -n "$NEW_FP" ]] && echo "  New fingerprint: ${NEW_FP}"
echo ""
echo "Next steps:"
echo "  1. Distribute ${PUBLIC_KEY} to all install nodes"
echo "  2. Update SKILL_REGISTRY_TRUST_ROOTS env var to point to ${TRUST_ROOTS}"
echo "  3. Run: scripts/testing/verify-skill-registry.sh --trust-roots ${TRUST_ROOTS}"
