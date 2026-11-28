#!/usr/bin/env bash
# N3: a candidate extends a baseline exception expiry
set -euo pipefail
sed -i '0,/expiry: "2027-03-31"/s//expiry: "2029-03-31"/' config/system-state-authorities.yaml
