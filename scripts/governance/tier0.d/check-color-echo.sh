#!/usr/bin/env bash
# Tier0 extension: block raw ANSI color escape sequences in changed shell scripts.

set -euo pipefail

MODE="${1:---pre-commit}"
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}"

collect_changed_files() {
  if [[ "${MODE}" == "--pre-commit" ]]; then
    git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true
    return 0
  fi

  {
    git diff --name-only --diff-filter=ACM origin/main...HEAD 2>/dev/null || true
    git diff --name-only --diff-filter=ACM 2>/dev/null || true
  } | awk 'NF && !seen[$0]++'
}

files=()
while IFS= read -r f; do
  [[ -f "$f" ]] && [[ "$f" == *.sh ]] && files+=("$f")
done < <(collect_changed_files)

if [[ ${#files[@]} -eq 0 ]]; then
  echo "[tier0.d/check-color-echo] PASS: no shell script changes detected"
  exit 0
fi

found=0
for f in "${files[@]}"; do
  if [[ "${MODE}" == "--pre-commit" ]]; then
    content_cmd=(git show ":$f")
  else
    content_cmd=(cat "$f")
  fi

  if "${content_cmd[@]}" 2>/dev/null \
    | grep -nP 'echo\s+-[eE]\s+["'"'"'].*\\033\[|printf\s+["'"'"'].*\\033\[' \
    | grep -v '# ok-raw-echo' \
    | sed "s|^|${f}:|"; then
    found=1
  fi
done

if [[ $found -eq 1 ]]; then
  echo "[tier0.d/check-color-echo] FAIL: raw ANSI color codes found; use info()/warn()/die() wrappers or add '# ok-raw-echo' to intentional exceptions" >&2
  exit 1
fi

echo "[tier0.d/check-color-echo] PASS: no raw ANSI echo usage (${#files[@]} files checked)"
