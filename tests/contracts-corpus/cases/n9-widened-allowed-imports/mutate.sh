#!/usr/bin/env bash
# N9: a candidate widens its own context allowed_imports in the same PR
set -euo pipefail
sed -i '/^  - {id: K2,/s/allowed_imports: \[/allowed_imports: [task_registry, /' config/system-state-authorities.yaml
