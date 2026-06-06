#!/usr/bin/env bash
set -euo pipefail

# smoke-ide-adapter-compat.sh
# Phase 50: IDE Adapter Compatibility Gate
#
# Validates that each IDE-facing integration surface is wired correctly:
#   - Continue extension (coordinator ingress, MCP, context bridge)
#   - VS Code / VSCodium (Claude Code extension, Codex chatgpt extension, Gemini)
#   - CLI agents reachable from user PATH (claude, codex, gemini)
#   - Coordinator health from IDE perspective (HTTP, auth, /query surface)
#
# Exit codes:
#   0 — all critical checks passed (warnings allowed)
#   1 — one or more critical checks failed

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

COORDINATOR_PORT="${HYBRID_COORDINATOR_PORT:-8003}"
COORDINATOR_URL="${HYBRID_COORDINATOR_URL:-http://127.0.0.1:${COORDINATOR_PORT}}"

pass()  { echo "[PASS] $*"; ((PASS_COUNT+=1)); }
fail()  { echo "[FAIL] $*" >&2; ((FAIL_COUNT+=1)); FAILED_ITEMS+=("$*"); }
warn()  { echo "[WARN] $*" >&2; ((WARN_COUNT+=1)); }
info()  { echo "[INFO] $*"; }
section() { echo ""; echo "── $* ──────────────────────────────────"; }

PASS_COUNT=0; FAIL_COUNT=0; WARN_COUNT=0
FAILED_ITEMS=()

primary_user="${AQ_PRIMARY_USER:-${SUDO_USER:-${USER:-$(id -un)}}}"
primary_home="${AQ_PRIMARY_HOME:-$(getent passwd "${primary_user}" 2>/dev/null | cut -d: -f6 || echo "${HOME}")}"
export PATH="${primary_home}/.npm-global/bin:${primary_home}/.local/bin:${primary_home}/.nix-profile/bin:${PATH}"

# ── Section 1: Continue extension wiring ──────────────────────────────────────
section "Continue extension adapter"

CONTINUE_CONFIG="${primary_home}/.continue/config.json"
if [[ -f "$CONTINUE_CONFIG" ]]; then
    pass "Continue config present: ${CONTINUE_CONFIG}"
    # Check that coordinator model entry exists
    if python3 -c "
import json, sys
d = json.load(open('$CONTINUE_CONFIG'))
models = d.get('models', [])
titles = [m.get('title','') for m in models]
found = any('coordinator' in t.lower() or 'hybrid' in t.lower() or 'local' in t.lower() for t in titles)
sys.exit(0 if found else 1)
" 2>/dev/null; then
        pass "Continue config has local/coordinator model entry"
    else
        warn "Continue config has no coordinator/local model entry (check config.json models)"
    fi
    # Check context length is set
    if python3 -c "
import json, sys
d = json.load(open('$CONTINUE_CONFIG'))
models = d.get('models', [])
ok = any(m.get('contextLength', 0) >= 8000 for m in models)
sys.exit(0 if ok else 1)
" 2>/dev/null; then
        pass "Continue config: contextLength ≥ 8000 set on at least one model"
    else
        warn "Continue config: no model with contextLength ≥ 8000"
    fi
else
    warn "Continue config not found at ${CONTINUE_CONFIG}"
fi

# Check coordinator ingress smoke script exists
if [[ -x "${REPO_ROOT}/scripts/testing/smoke-continue-coordinator-ingress.sh" ]]; then
    pass "Continue→coordinator ingress smoke script present and executable"
else
    warn "smoke-continue-coordinator-ingress.sh missing or not executable"
fi

# ── Section 2: CLI agent reachability ─────────────────────────────────────────
section "IDE CLI agent reachability"

check_cli() {
    local name="$1" cmd="$2"
    if command -v "$cmd" >/dev/null 2>&1; then
        pass "CLI reachable: ${name} ($(command -v "$cmd"))"
    else
        warn "CLI not found in PATH: ${name} (${cmd}) — IDE extension may not work"
    fi
}

check_cli "claude"  "claude"
check_cli "codex"   "codex"
check_cli "gemini"  "gemini"
check_cli "aider"   "aider"

# aq-* scripts
check_cli "aqd"     "${REPO_ROOT}/scripts/ai/aqd"
check_cli "aq-qa"   "${REPO_ROOT}/scripts/ai/aq-qa"

# ── Section 3: Coordinator HTTP surface (IDE perspective) ─────────────────────
section "Coordinator IDE-facing HTTP surface"

http_check() {
    local label="$1" url="$2"
    if curl -sf --max-time 8 "$url" >/dev/null 2>&1; then
        pass "${label}: ${url}"
    else
        fail "${label} unreachable: ${url}"
    fi
}

if curl -sf --max-time 5 "${COORDINATOR_URL}/health" >/dev/null 2>&1; then
    pass "Coordinator reachable: ${COORDINATOR_URL}/health"
    http_check "Query endpoint"         "${COORDINATOR_URL}/query" 2>/dev/null || true
    http_check "Workflow blueprints"    "${COORDINATOR_URL}/workflow/blueprints"
    http_check "Graph templates"        "${COORDINATOR_URL}/workflow/graph/templates"
    http_check "Budget policy"          "${COORDINATOR_URL}/control/budget/policy"
    http_check "Fleet summary"          "${COORDINATOR_URL}/control/fleet/summary"
else
    warn "Coordinator not reachable at ${COORDINATOR_URL} — skipping HTTP surface checks (stack not running)"
fi

# ── Section 4: VS Code / VSCodium extension wiring ────────────────────────────
section "VS Code / VSCodium extension wiring"

check_vscode_ext() {
    local label="$1" ext_id="$2"
    if command -v codium >/dev/null 2>&1; then
        if codium --list-extensions 2>/dev/null | grep -qi "$(echo "$ext_id" | cut -d. -f2)"; then
            pass "VSCodium extension installed: ${label} (${ext_id})"
        else
            warn "VSCodium extension not installed: ${label} (${ext_id})"
        fi
    elif command -v code >/dev/null 2>&1; then
        if code --list-extensions 2>/dev/null | grep -qi "$(echo "$ext_id" | cut -d. -f2)"; then
            pass "VS Code extension installed: ${label} (${ext_id})"
        else
            warn "VS Code extension not installed: ${label} (${ext_id})"
        fi
    else
        warn "Neither codium nor code in PATH — skipping extension check for ${label}"
    fi
}

check_vscode_ext "Claude Code"      "anthropics.claude-code"
check_vscode_ext "Continue"         "continue.continue"
check_vscode_ext "Gemini Code Assist" "google.geminicodeassist"
check_vscode_ext "Codex (ChatGPT)"  "openai.chatgpt"

# ── Section 5: MCP adapter config surface ─────────────────────────────────────
section "MCP adapter config surface"

MCP_CONFIG="${primary_home}/.claude/settings.json"
if [[ -f "$MCP_CONFIG" ]]; then
    pass "Claude Code settings.json present"
    if python3 -c "
import json, sys
d = json.load(open('$MCP_CONFIG'))
mcps = d.get('mcpServers', {})
sys.exit(0 if mcps else 1)
" 2>/dev/null; then
        MCP_COUNT=$(python3 -c "import json; d=json.load(open('$MCP_CONFIG')); print(len(d.get('mcpServers',{})))" 2>/dev/null || echo 0)
        pass "MCP servers configured in settings.json: ${MCP_COUNT}"
        if python3 -c "
import json, sys
d = json.load(open('$MCP_CONFIG'))
mcps = d.get('mcpServers', {})
args = mcps.get('hybrid-coordinator', {}).get('args') or []
sys.exit(0 if args and args[0].endswith('/scripts/ai/mcp-bridge-hybrid.py') else 1)
" 2>/dev/null; then
            pass "Claude settings expose local hybrid-coordinator MCP bridge"
        else
            fail "Claude settings missing local hybrid-coordinator MCP bridge"
        fi
        if python3 -c "
import json, sys
d = json.load(open('$MCP_CONFIG'))
bad = []
for name, cfg in (d.get('mcpServers') or {}).items():
    command = cfg.get('command', '')
    args = cfg.get('args') or []
    env = cfg.get('env') or {}
    if command == 'npx':
        bad.append(name)
    if command == 'nix' and any(str(arg).startswith('github:') for arg in args):
        bad.append(name)
    if env.get('GITHUB_PERSONAL_ACCESS_TOKEN') == 'set-me':
        bad.append(name)
if bad:
    print(','.join(bad))
    sys.exit(1)
" 2>/dev/null; then
            pass "Claude settings MCP entries avoid startup package fetches/placeholders"
        else
            fail "Claude settings contain startup-fetching or placeholder MCP entries"
        fi
    else
        warn "No mcpServers entries in Claude Code settings.json"
    fi
else
    warn "Claude Code settings.json not found at ${MCP_CONFIG}"
fi

SHARED_MCP_CONFIG="${primary_home}/.mcp/config.json"
if [[ -f "$SHARED_MCP_CONFIG" ]]; then
    pass "Shared MCP config present: ${SHARED_MCP_CONFIG}"
    if python3 -c "
import json, sys
d = json.load(open('$SHARED_MCP_CONFIG'))
mcps = d.get('mcpServers', {})
args = mcps.get('hybrid-coordinator', {}).get('args') or []
sys.exit(0 if args and args[0].endswith('/scripts/ai/mcp-bridge-hybrid.py') else 1)
" 2>/dev/null; then
        pass "Shared MCP config exposes local hybrid-coordinator MCP bridge"
    else
        fail "Shared MCP config missing local hybrid-coordinator MCP bridge"
    fi
    if python3 -c "
import json, sys
d = json.load(open('$SHARED_MCP_CONFIG'))
bad = []
for name, cfg in (d.get('mcpServers') or {}).items():
    command = cfg.get('command', '')
    args = cfg.get('args') or []
    env = cfg.get('env') or {}
    if command == 'npx':
        bad.append(name)
    if command == 'nix' and any(str(arg).startswith('github:') for arg in args):
        bad.append(name)
    if env.get('GITHUB_PERSONAL_ACCESS_TOKEN') == 'set-me':
        bad.append(name)
if bad:
    print(','.join(bad))
    sys.exit(1)
" 2>/dev/null; then
        pass "Shared MCP entries avoid startup package fetches/placeholders"
    else
        fail "Shared MCP config contains startup-fetching or placeholder MCP entries"
    fi
else
    warn "Shared MCP config not found at ${SHARED_MCP_CONFIG}"
fi

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
echo " IDE Adapter Compatibility Gate — Summary"
printf " PASS: %d  WARN: %d  FAIL: %d\n" "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT"
echo "══════════════════════════════════════════════════════"

if [[ $FAIL_COUNT -gt 0 ]]; then
    echo "FAILED checks:"
    for item in "${FAILED_ITEMS[@]}"; do
        echo "  - ${item}"
    done
    exit 1
fi

echo "All critical IDE adapter checks passed (warnings may require manual verification)."
