#!/usr/bin/env bash
# Purpose: Test capability promotion workflow from stub to active
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GAP_TOOL="${ROOT_DIR}/scripts/ai/aq-capability-gap"
PROMOTE_TOOL="${ROOT_DIR}/scripts/ai/aq-capability-promote"

tmp_observations="$(mktemp)"
tmp_gap_first="$(mktemp)"
tmp_gap_second="$(mktemp)"
tmp_promote="$(mktemp)"
trap 'rm -f "${tmp_observations}" "${tmp_gap_first}" "${tmp_gap_second}" "${tmp_promote}"' EXIT

AQ_CAPABILITY_GAP_OBSERVATIONS_FILE="${tmp_observations}" python3 "${GAP_TOOL}" --tool mm --context-language rust --format json > "${tmp_gap_first}"
AQ_CAPABILITY_GAP_OBSERVATIONS_FILE="${tmp_observations}" python3 "${GAP_TOOL}" --tool mm --context-language rust --format json > "${tmp_gap_second}"
AQ_CAPABILITY_GAP_OBSERVATIONS_FILE="${tmp_observations}" python3 "${PROMOTE_TOOL}" --gap-file "${tmp_gap_second}" --format json > "${tmp_promote}"

python3 - "${tmp_gap_first}" "${tmp_gap_second}" "${tmp_promote}" <<'PY'
import json
import sys
from pathlib import Path

first = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
second = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
promote = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))

if first.get("observation", {}).get("promotion_candidate") is not False:
    print("ERROR: first repeated-gap observation should not yet be a promotion candidate", file=sys.stderr)
    raise SystemExit(1)
if second.get("observation", {}).get("promotion_candidate") is not True:
    print("ERROR: second repeated-gap observation should become a promotion candidate", file=sys.stderr)
    raise SystemExit(1)
if promote.get("promotion_candidate") is not True:
    print("ERROR: capability promote did not surface promotion candidacy", file=sys.stderr)
    raise SystemExit(1)
if not any("aq-capability-stub" in cmd for cmd in promote.get("recommended_actions", [])):
    print("ERROR: capability promote did not recommend stub generation", file=sys.stderr)
    raise SystemExit(1)
if not any("aq-capability-catalog-append" in cmd for cmd in promote.get("recommended_actions", [])):
    print("ERROR: capability promote did not recommend catalog append preparation", file=sys.stderr)
    raise SystemExit(1)
if not any("aq-capability-patch-prep" in cmd for cmd in promote.get("recommended_actions", [])):
    print("ERROR: capability promote did not recommend patch preparation", file=sys.stderr)
    raise SystemExit(1)

print("PASS: capability promotion validated")
PY
