#!/usr/bin/env bash
set -euo pipefail
command_template='{{FRESHNESS_CHECK_CMD}}'
if [[ "${command_template}" == *'{{'* ]]; then
  if [[ "${FACTORY_FRESHNESS_NOT_APPLICABLE:-0}" == "1" ]]; then
    echo "NOT_APPLICABLE: FRESHNESS explicitly disabled by FACTORY_FRESHNESS_NOT_APPLICABLE=1"
    exit 0
  fi
  echo "UNCONFIGURED: render {{FRESHNESS_CHECK_CMD}} or explicitly set FACTORY_FRESHNESS_NOT_APPLICABLE=1"
  exit 3
fi
exec sh -c "${command_template}"
