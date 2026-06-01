#!/usr/bin/env bash
# Regression test for tier0.d/check-color-echo.sh staged-blob behavior.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/governance/tier0.d/check-color-echo.sh"
FIXTURE="${REPO_ROOT}/tmp-tier0-color-echo-fixture.sh"

cleanup() {
  git -C "${REPO_ROOT}" reset -q -- "${FIXTURE}" 2>/dev/null || true
  rm -f "${FIXTURE}"
}
trap cleanup EXIT

cd "${REPO_ROOT}"

esc='\\033'
{
  echo '#!/usr/bin/env bash'
  echo "printf \"${esc}[31mred${esc}[0m\\n\""
} >"${FIXTURE}"
git add "${FIXTURE}"

cat >"${FIXTURE}" <<'EOF'
#!/usr/bin/env bash
printf "clean\n"
EOF

if "${SCRIPT}" --pre-commit >/tmp/tier0-color-echo-staged.out 2>&1; then
  echo "FAIL: staged raw ANSI sequence was not detected" >&2
  cat /tmp/tier0-color-echo-staged.out >&2
  exit 1
fi

{
  echo '#!/usr/bin/env bash'
  echo "printf \"${esc}[31mred${esc}[0m\\n\" # ok-raw-echo"
} >"${FIXTURE}"
git add "${FIXTURE}"

if ! "${SCRIPT}" --pre-commit >/tmp/tier0-color-echo-allowed.out 2>&1; then
  echo "FAIL: ok-raw-echo exception should allow staged raw ANSI sequence" >&2
  cat /tmp/tier0-color-echo-allowed.out >&2
  exit 1
fi

echo "PASS: tier0 color-echo extension validates staged blob content"
