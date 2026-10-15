#!/usr/bin/env bash
# tier0.d/check-grype-ignore-expiry.sh - time-box enforcement for .grype.yaml ignores.
# An ignore whose reason carries `expires=YYYY-MM-DD` is dead after that date. Rule 19 gate
# corollary: an expiry is maintenance, so it WARNs in --pre-commit and FAILs in any other
# mode (--pre-deploy, --maintenance, no argument, CI). Entries without a token WARN (legacy),
# except entries that cite a WR-SEC-* register id, which must carry one (FAIL).
# Env: GRYPE_IGNORE_FILE overrides the file; GRYPE_IGNORE_TODAY (YYYY-MM-DD) overrides today (tests).
set -euo pipefail
MODE="${1:---maintenance}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export MODE FILE="${GRYPE_IGNORE_FILE:-$ROOT/.grype.yaml}"
exec python3 - <<'PY'
import datetime, os, re, sys
tag = "[tier0.d/check-grype-ignore-expiry]"
mode, path = os.environ["MODE"], os.environ["FILE"]
today = datetime.date.fromisoformat(os.environ.get("GRYPE_IGNORE_TODAY") or datetime.date.today().isoformat())
entries, cur = [], None
for line in open(path, encoding="utf-8"):
    m = re.match(r"\s*-\s+vulnerability:\s*(\S+)", line)
    if m:
        cur = {"id": m.group(1), "reason": ""}; entries.append(cur); continue
    m = re.match(r"\s+reason:\s*(.*)$", line)
    if m and cur is not None: cur["reason"] = m.group(1)
expired, missing_hard, missing_soft = [], [], []
for e in entries:
    t = re.search(r"expires=(\d{4}-\d{2}-\d{2})", e["reason"])
    if t:
        if datetime.date.fromisoformat(t.group(1)) < today: expired.append(f'{e["id"]} (expired {t.group(1)})')
    elif "WR-SEC-" in e["reason"]: missing_hard.append(e["id"])
    else: missing_soft.append(e["id"])
blocking = mode != "--pre-commit"
if missing_soft:
    print(f"{tag} WARN: {len(missing_soft)} legacy ignore(s) without expires= token (first 5: {', '.join(missing_soft[:5])})", file=sys.stderr)
bad = [f"expired: {x}" for x in expired] + [f"WR-SEC entry without expires=: {x}" for x in missing_hard]
for b in bad: print(f"{tag} {'FAIL' if blocking else 'WARN'}: {b}", file=sys.stderr)
if bad and blocking: sys.exit(1)
print(f"{tag} PASS ({mode}, {len(entries)} ignores, {len(bad)} {'blocking' if blocking else 'warned'})")
PY
