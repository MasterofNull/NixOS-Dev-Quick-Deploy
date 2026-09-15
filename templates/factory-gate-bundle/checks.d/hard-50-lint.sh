#!/usr/bin/env bash
set -euo pipefail
command_template='{{LINT_CMD}}'
if [[ "${command_template}" == *'{{'* ]]; then
  if [[ "${FACTORY_LINT_NOT_APPLICABLE:-0}" == "1" ]]; then
    echo "NOT_APPLICABLE: LINT explicitly disabled by FACTORY_LINT_NOT_APPLICABLE=1"
    exit 0
  fi
  echo "UNCONFIGURED: render {{LINT_CMD}} or explicitly set FACTORY_LINT_NOT_APPLICABLE=1"
  exit 3
fi
exec sh -c "${command_template}"
