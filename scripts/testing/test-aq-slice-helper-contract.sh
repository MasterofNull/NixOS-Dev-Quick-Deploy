#!/usr/bin/env bash
# test-aq-slice-helper-contract.sh — static/smoke contract for aq-slice-helper.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

python3 -m json.tool config/lessons/agentic-slice-lessons.json >/dev/null
python3 -m py_compile scripts/ai/aq-slice-helper
scripts/ai/aq-slice-helper --help >/dev/null
scripts/ai/aq-slice-helper assess --task "dashboard visibility" --json >/tmp/aq-slice-helper-smoke.json
python3 - <<'PY'
import json
payload=json.load(open('/tmp/aq-slice-helper-smoke.json'))
for key in ('classification','matched_lessons','recommended_surfaces','checks'):
    assert key in payload, key
assert any(l.get('id') == 'managed-dashboard-service-required' for l in payload['matched_lessons'])
assert any('check-dashboard-managed-service.sh' in ' '.join(c['command']) for c in payload['checks'])
print('PASS: aq-slice-helper contract')
PY
