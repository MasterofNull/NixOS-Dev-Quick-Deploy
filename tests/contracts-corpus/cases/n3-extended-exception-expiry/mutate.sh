#!/usr/bin/env bash
# N3: a candidate extends a baseline exception expiry
set -euo pipefail
sed -i '/local_agent_runtime.py", kind: http/s/2027-03-31/2029-03-31/' config/system-state-authorities.yaml
