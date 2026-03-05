#!/usr/bin/env bash
# Compatibility shim: use scripts/automation/cron-templates.sh.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/automation/cron-templates.sh" "$@"
