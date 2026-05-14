#!/usr/bin/env bash
# check-audit-integrity.sh — Verify audit log presence and recent activity.
#
# Standard: Hospital/Classified Security Baseline (Phase 36)
# Checks:
# 1. Audit log directory exists with correct permissions.
# 2. Critical audit files (tool-audit.jsonl, agent-commands.jsonl) exist.
# 3. Recent activity check (files updated in the last 24h).
# 4. Truncation check (file size > 0).

set -euo pipefail

LOG_DIR="/var/log/nixos-ai-stack"
CRITICAL_FILES=("tool-audit.jsonl" "agent-commands.jsonl" "hint-audit.jsonl")
FAILED=0

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}PASS:${NC} $1"; }
log_fail() { echo -e "${RED}FAIL:${NC} $1"; FAILED=1; }

echo "━━━ Audit Log Integrity Check ━━━"

# 1. Directory Check
if [[ ! -d "$LOG_DIR" ]]; then
    log_fail "Audit log directory missing: $LOG_DIR"
else
    log_pass "Audit log directory exists."
    
    # Check permissions (should be 0750 or 0770)
    PERMS=$(stat -c "%a" "$LOG_DIR")
    if [[ "$PERMS" != "750" && "$PERMS" != "770" ]]; then
        log_fail "Incorrect directory permissions: $PERMS (expected 750 or 770)"
    else
        log_pass "Directory permissions valid ($PERMS)."
    fi
fi

# 2. File Checks
for file in "${CRITICAL_FILES[@]}"; do
    FILE_PATH="$LOG_DIR/$file"
    if [[ ! -f "$FILE_PATH" ]]; then
        log_fail "Critical audit file missing: $file"
        continue
    fi
    
    # Check size
    SIZE=$(stat -c "%s" "$FILE_PATH")
    if [[ "$SIZE" -eq 0 ]]; then
        log_fail "Audit file is empty: $file"
    else
        log_pass "Audit file present and non-empty: $file"
    fi
    
    # Check recent activity (last 24h)
    # Using find without command substitution in the shell call to avoid security blocks
    # We just want to know if it matches the criteria
    if find "$FILE_PATH" -mmin -1440 | grep -q .; then
        log_pass "Recent activity detected in $file."
    else
        echo -e "${RED}WARN:${NC} No activity in $file for >24h (might be idle, but check service status)."
    fi
done

if [[ $FAILED -eq 1 ]]; then
    exit 1
fi
log_pass "All critical audit integrity checks passed."
exit 0
