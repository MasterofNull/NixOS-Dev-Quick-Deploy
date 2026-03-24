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

color_vars='(RED|GREEN|YELLOW|BLUE|MAGENTA|CYAN|WHITE|BLACK|BOLD|NC)'
pattern="echo[[:space:]]+\"[^\"]*\\$\\{${color_vars}\\}"

have_rg() {
  command -v rg >/dev/null 2>&1
}

filter_shell_files() {
  if have_rg; then
    rg -N '\.(sh|bash)$' || true
  else
    grep -E '\.(sh|bash)$' || true
  fi
}

find_offending_echoes() {
  local file="$1"
  if have_rg; then
    rg -n --pcre2 "$pattern" "$file" | rg -v 'echo[[:space:]]*-e[[:space:]]+' || true
  else
    grep -En 'echo[[:space:]]+"[^"]*\$\{(RED|GREEN|YELLOW|BLUE|MAGENTA|CYAN|WHITE|BLACK|BOLD|NC)\}' "$file" \
      | grep -Ev 'echo[[:space:]]*-e[[:space:]]+' || true
  fi
}

gather_targets() {
  if [[ "$USE_STAGED" -eq 1 ]]; then
    git diff --cached --name-only --diff-filter=ACM | filter_shell_files
  else
    git ls-files '*.sh' '*.bash' ':!:archive/deprecated/**' || true
  fi
}

issues=0
mapfile -t targets < <(gather_targets)
for file in "${targets[@]}"; do
  [[ -f "$file" ]] || continue
  offending="$(find_offending_echoes "$file")"
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
