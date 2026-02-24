#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# lint-skills-podman.sh — Detect podman-first patterns in skill/doc files.
#
# Phase 28.3.3 — K3s-First AI Service Management
#
# Usage:
#   scripts/lint-skills-podman.sh [--warn-only] [DIR...]
#
# Checks for:
#   - Direct 'podman' commands in skill markdown/YAML files
#   - 'docker run' / 'docker-compose' references where K3s should be used
#   - References to podman socket / podman.service in AI stack docs
#
# Exit codes:
#   0 — no podman-first patterns found (or --warn-only)
#   1 — podman-first patterns found
# ---------------------------------------------------------------------------
set -euo pipefail

WARN_ONLY=0
SEARCH_DIRS=()

info()  { printf '\033[0;32m[lint-skills] %s\033[0m\n' "$*"; }
warn()  { printf '\033[0;33m[lint-skills] WARN: %s\033[0m\n' "$*" >&2; }
fail()  { printf '\033[0;31m[lint-skills] FAIL: %s\033[0m\n' "$*" >&2; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --warn-only) WARN_ONLY=1; shift ;;
        --help|-h)
            cat <<'HELP'
Usage: scripts/lint-skills-podman.sh [--warn-only] [DIR...]

Scans skill/doc files for podman-first patterns that should use K3s.
Default dirs: ai-stack/agents/skills/ docs/ README.md AGENTS.md

Options:
  --warn-only    Print findings but exit 0 (non-blocking)
  DIR...         Additional directories or files to scan
HELP
            exit 0 ;;
        *) SEARCH_DIRS+=("$1"); shift ;;
    esac
done

# Default scan targets.
if [[ ${#SEARCH_DIRS[@]} -eq 0 ]]; then
    SEARCH_DIRS=()
    [[ -d "ai-stack/agents/skills" ]] && SEARCH_DIRS+=("ai-stack/agents/skills")
    [[ -d "docs" ]]                   && SEARCH_DIRS+=("docs")
    [[ -f "README.md" ]]              && SEARCH_DIRS+=("README.md")
    [[ -f "AGENTS.md" ]]              && SEARCH_DIRS+=("AGENTS.md")
fi

# ── Pattern definitions ───────────────────────────────────────────────────────
# Each entry: "PATTERN|DESCRIPTION|IS_ALWAYS_BAD"
# IS_ALWAYS_BAD=1 → error even if not in an AI-stack context.
# IS_ALWAYS_BAD=0 → only flag when adjacent to AI service context.
declare -A PATTERNS=(
    ["podman run"]="Direct 'podman run' for AI service (use kubectl rollout)"
    ["podman start"]="Direct 'podman start' for AI service (use kubectl)"
    ["podman stop"]="Direct 'podman stop' for AI service (use kubectl scale)"
    ["podman ps"]="'podman ps' for AI stack inspection (use kubectl get pods)"
    ["podman logs"]="'podman logs' for AI service (use kubectl logs)"
    ["docker run"]="'docker run' reference (use kubectl)"
    ["docker-compose"]="docker-compose reference (K3s/kustomize is the runtime)"
    ["podman-tcp.service"]="podman-tcp socket reference (podman is legacy for AI services)"
    ["systemctl.*podman"]="podman systemd unit reference (AI services use K3s)"
)

FINDINGS=0
SCANNED=0

# ── Scan ─────────────────────────────────────────────────────────────────────
for target in "${SEARCH_DIRS[@]}"; do
    while IFS= read -r file; do
        [[ -f "$file" ]] || continue
        # Only scan text files.
        mime=$(file --brief --mime-type "$file" 2>/dev/null || echo "")
        [[ "$mime" == text/* ]] || continue

        (( SCANNED++ )) || true
        lineno=0
        while IFS= read -r line; do
            (( lineno++ )) || true
            for pattern in "${!PATTERNS[@]}"; do
                if echo "$line" | grep -qiE "$pattern"; then
                    desc="${PATTERNS[$pattern]}"
                    fail "${file}:${lineno}: [podman-first] ${desc}"
                    fail "  Line: ${line:0:120}"
                    (( FINDINGS++ )) || true
                fi
            done
        done < "$file"
    done < <(find "$target" -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.yml" -o -name "*.txt" \) 2>/dev/null || true)
done

# ── Summary ───────────────────────────────────────────────────────────────────
info "Scanned ${SCANNED} files."

if [[ "${FINDINGS}" -gt 0 ]]; then
    warn "${FINDINGS} podman-first pattern(s) found."
    warn "Replace with K3s equivalents:"
    warn "  podman run <img>          →  kubectl run / kubectl apply"
    warn "  podman ps                 →  kubectl get pods -n ai-stack"
    warn "  podman logs <id>          →  kubectl logs -n ai-stack <pod>"
    warn "  podman stop <id>          →  kubectl scale deploy/<svc> --replicas=0"

    if [[ "${WARN_ONLY}" -eq 1 ]]; then
        warn "Lint findings reported (--warn-only: exiting 0)."
        exit 0
    fi
    exit 1
else
    info "No podman-first patterns found. K3s-first guidance is consistent."
fi
