#!/usr/bin/env bash
set -euo pipefail
command_template='{{BUILD_CMD}}'
if [[ "${command_template}" == *'{{'* ]]; then
  if [[ "${FACTORY_BUILD_NOT_APPLICABLE:-0}" == "1" ]]; then
    echo "NOT_APPLICABLE: BUILD explicitly disabled by FACTORY_BUILD_NOT_APPLICABLE=1"
    exit 0
  fi
  echo "UNCONFIGURED: render {{BUILD_CMD}} or explicitly set FACTORY_BUILD_NOT_APPLICABLE=1"
  exit 3
fi
exec sh -c "${command_template}"
