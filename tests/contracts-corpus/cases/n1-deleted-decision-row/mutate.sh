#!/usr/bin/env bash
# N1: a candidate deletes a decision row to dissolve a violation
set -euo pipefail
grep -v '^  - {id: D06,' config/system-state-authorities.yaml > x && mv x config/system-state-authorities.yaml
