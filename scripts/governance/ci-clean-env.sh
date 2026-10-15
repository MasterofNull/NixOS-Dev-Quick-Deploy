#!/usr/bin/env bash
# Runs run-ci-checks.sh inside a throwaway venv holding ONLY config/ci-python-requirements.txt
# (CI's bare python env). Usage: ci-clean-env.sh <run-ci-checks.sh args>  e.g. --all --only <id>
# Env: CI_CLEAN_ENV_REQS overrides the requirements file; PIP_FIND_LINKS/PIP_INDEX_URL honoured
# (offline: point PIP_FIND_LINKS at a wheelhouse). Fails loudly if venv or pip install is impossible.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REQS="${CI_CLEAN_ENV_REQS:-${ROOT}/config/ci-python-requirements.txt}"
[[ -f "${REQS}" ]] || { echo "FAIL: requirements file not found: ${REQS}" >&2; exit 1; }
[[ $# -gt 0 ]] || { echo "usage: ci-clean-env.sh --all|--changed [--only <id>]" >&2; exit 2; }
VENV="$(mktemp -d "${TMPDIR:-/tmp}/ci-clean-env-XXXXXX")"
# Throwaway venv: removes exactly the mktemp path created above on exit (not a repo path).
trap 'rm -rf -- "${VENV}"' EXIT
python3 -m venv "${VENV}" >&2 || { echo "FAIL: cannot create venv with $(command -v python3) (python3 -m venv unavailable)" >&2; exit 1; }
if ! "${VENV}/bin/python" -m pip install -q --disable-pip-version-check -r "${REQS}" >&2; then
  echo "FAIL: could not install CI requirements (${REQS}); offline? set PIP_FIND_LINKS to a wheelhouse. NOT running checks (no silent pass)." >&2
  exit 1
fi
echo "ci-clean-env: venv ${VENV} with: $(grep -Ev '^\s*(#|$)' "${REQS}" | tr '\n' ' ')" >&2
rc=0
PATH="${VENV}/bin:${PATH}" VIRTUAL_ENV="${VENV}" "${ROOT}/scripts/governance/run-ci-checks.sh" "$@" || rc=$?
exit "${rc}"
