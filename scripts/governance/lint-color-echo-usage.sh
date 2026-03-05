#!/usr/bin/env bash
set -euo pipefail

# lint-color-echo-usage.sh
# Detect echo statements that print ANSI color variables without `-e`.
# Only checks known color variable names to avoid false positives on normal
# uppercase environment-variable interpolation.

USE_STAGED=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --staged) USE_STAGED=1; shift ;;
    *) printf 'Unknown arg: %s\n' "$1" >&2; exit 2 ;;
  esac
done

if ! command -v rg >/dev/null 2>&1; then
  printf 'ERROR: ripgrep (rg) is required\n' >&2
  exit 2
fi

color_vars='(RED|GREEN|YELLOW|BLUE|MAGENTA|CYAN|WHITE|BLACK|BOLD|NC)'
pattern="echo[[:space:]]+\"[^\"]*\\$\\{${color_vars}\\}"

gather_targets() {
  if [[ "$USE_STAGED" -eq 1 ]]; then
    git diff --cached --name-only --diff-filter=ACM | rg -N '\.(sh|bash)$' || true
  else
    git ls-files '*.sh' '*.bash' ':!:deprecated/**' || true
  fi
}

issues=0
mapfile -t targets < <(gather_targets)
for file in "${targets[@]}"; do
  [[ -f "$file" ]] || continue
  offending="$(rg -n --pcre2 "$pattern" "$file" | rg -v 'echo[[:space:]]*-e[[:space:]]+' || true)"
  if [[ -n "$offending" ]]; then
    printf '✗ %s has color echo statements missing -e:\n' "$file" >&2
    printf '%s\n' "$offending" >&2
    issues=1
  fi
done

if [[ "$issues" -ne 0 ]]; then
  cat >&2 <<'EOF'
Color echo lint failed.
Fix options:
  1) change to `echo -e "...${GREEN}...${NC}..."`
  2) prefer `printf '%b\n' "${GREEN}...${NC}"`
EOF
  exit 1
fi

printf 'Color echo lint passed.\n'
