#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANAGER="${ROOT_DIR}/scripts/governance/manage-secrets.sh"

if [[ ! -x "${MANAGER}" ]]; then
  echo "Missing secrets manager wrapper: ${MANAGER}" >&2
  exit 1
fi

echo "scripts/data/generate-api-secrets.sh is a compatibility shim over scripts/governance/manage-secrets.sh." >&2
exec "${MANAGER}" "$@" init --include-optional
