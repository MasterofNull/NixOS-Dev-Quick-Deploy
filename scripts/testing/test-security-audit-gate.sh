#!/usr/bin/env bash
# security-audit.sh must exit non-zero on a blocking finding and 0 on a clean tree.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/clean" "$T/bad/ai-stack/mcp-servers/svc" "$T/bin"
# Fake npm reporting one critical vuln; only used for the seeded run.
cat > "$T/bin/npm" <<'N'
#!/usr/bin/env bash
echo '{"metadata":{"vulnerabilities":{"info":0,"low":0,"moderate":0,"high":0,"critical":1,"total":1}}}'
exit 1
N
chmod +x "$T/bin/npm"
echo '{"name":"x","lockfileVersion":3}' | tee "$T/bad/package.json" "$T/bad/package-lock.json" >/dev/null

rc=0; out="$(PATH="$T/bin:$PATH" bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/bad" --output-dir "$T/o1" 2>&1)" || rc=$?
[[ $rc -ne 0 ]] && grep -q "BLOCKING: npm" <<<"$out" || { echo "FAIL: seeded finding did not block (rc=$rc)"; echo "$out"; exit 1; }

rc=0; out="$(env -u CI bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/clean" --output-dir "$T/o2" 2>&1)" || rc=$?
[[ $rc -eq 0 ]] && grep -q "blocking=0" <<<"$out" || { echo "FAIL: clean fixture rc=$rc"; echo "$out"; exit 1; }
# Fake pip-audit (clean) so coverage is deterministic and offline.
cat > "$T/bin/pip-audit" <<'N'
#!/usr/bin/env bash
echo '{"dependencies":[{"name":"x","version":"1","vulns":[]}]}'
N
chmod +x "$T/bin/pip-audit"
mkdir -p "$T/cov/ai-stack/mcp-servers/svc" "$T/err"
echo "x==1" > "$T/cov/ai-stack/mcp-servers/svc/requirements.txt"

# Zero pip coverage: CI=true blocks, local only warns.
rc=0; out="$(CI=true bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/clean" --output-dir "$T/o3" 2>&1)" || rc=$?
[[ $rc -ne 0 ]] && grep -q "BLOCKING: zero pip-audit coverage" <<<"$out" || { echo "FAIL: zero coverage not blocking in CI (rc=$rc)"; echo "$out"; exit 1; }
rc=0; out="$(env -u CI bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/clean" --output-dir "$T/o4" 2>&1)" || rc=$?
[[ $rc -eq 0 ]] && grep -q "WARNING: zero pip-audit coverage" <<<"$out" || { echo "FAIL: zero coverage local rc=$rc"; echo "$out"; exit 1; }

# Covered + clean in CI passes.
rc=0; out="$(PATH="$T/bin:$PATH" CI=true bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/cov" --output-dir "$T/o5" 2>&1)" || rc=$?
[[ $rc -eq 0 ]] && grep -q "pip coverage: 1 files" <<<"$out" || { echo "FAIL: covered CI run rc=$rc"; echo "$out"; exit 1; }

# npm audit error: CI blocks, local warns.
cat > "$T/bin/npm" <<'N'
#!/usr/bin/env bash
echo "network down" >&2; exit 2
N
echo '{"name":"x","lockfileVersion":3}' | tee "$T/err/package.json" "$T/err/package-lock.json" >/dev/null
rc=0; out="$(PATH="$T/bin:$PATH" CI=true bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/err" --output-dir "$T/o6" 2>&1)" || rc=$?
[[ $rc -ne 0 ]] && grep -q "BLOCKING: npm audit errored" <<<"$out" || { echo "FAIL: npm error not blocking in CI (rc=$rc)"; echo "$out"; exit 1; }
rc=0; out="$(PATH="$T/bin:$PATH" env -u CI bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/err" --output-dir "$T/o7" 2>&1)" || rc=$?
[[ $rc -eq 0 ]] && grep -q "WARNING: npm audit errored" <<<"$out" || { echo "FAIL: npm error local rc=$rc"; echo "$out"; exit 1; }
# Exceptions: unexpired => --ignore-vuln passed and reported; expired => not passed (blocking again).
cat > "$T/bin/pip-audit" <<'N'
#!/usr/bin/env bash
echo '{"dependencies":[{"name":"x","version":"1","vulns":[{"id":"VULN-1"}]}]}'; exit 1
N
fut() { date -u -d "+$1 days" +%F; }
mkex() { printf '{"exceptions":[{"id":"VULN-1","package":"%s","expires":"%s"}]}' "$2" "$3" > "$1"; }
mkex "$T/ex-ok.json" x "$(fut 30)"
mkex "$T/ex-bad.json" x "2026-13-45"
mkex "$T/ex-far.json" x "$(fut 120)"
mkex "$T/ex-pkg.json" other "$(fut 30)"
printf '{"exceptions":[{"id":"VULN-1","package":"x","expires":"2000-01-01"}]}' > "$T/ex-old.json"
rc=0; out="$(PATH="$T/bin:$PATH" SECURITY_EXCEPTIONS_FILE="$T/ex-ok.json" bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/cov" --output-dir "$T/o8" 2>&1)" || rc=$?
[[ $rc -eq 0 ]] && grep -q "EXCEPTION applied: VULN-1" <<<"$out" || { echo "FAIL: unexpired exception rc=$rc"; echo "$out"; exit 1; }
rc=0; out="$(PATH="$T/bin:$PATH" SECURITY_EXCEPTIONS_FILE="$T/ex-old.json" bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/cov" --output-dir "$T/o9" 2>&1)" || rc=$?
[[ $rc -ne 0 ]] && grep -q "EXPIRED, not applied: VULN-1" <<<"$out" && grep -q "BLOCKING: pip-audit" <<<"$out" || { echo "FAIL: expired exception did not block rc=$rc"; echo "$out"; exit 1; }
for pair in "ex-bad.json:EXPIRED" "ex-far.json:EXPIRED" "ex-pkg.json:package mismatch"; do
  f="${pair%%:*}"; msg="${pair#*:}"
  rc=0; out="$(PATH="$T/bin:$PATH" SECURITY_EXCEPTIONS_FILE="$T/$f" bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/cov" --output-dir "$T/o10" 2>&1)" || rc=$?
  [[ $rc -ne 0 ]] && grep -q "$msg" <<<"$out" && grep -q "BLOCKING: pip-audit" <<<"$out" || { echo "FAIL: $f rc=$rc"; echo "$out"; exit 1; }
done

# Partial pip failure: CI blocks, local warns.
cat > "$T/bin/pip-audit" <<'N'
#!/usr/bin/env bash
echo boom >&2; exit 3
N
mkdir -p "$T/cov2/ai-stack/mcp-servers/a" "$T/cov2/ai-stack/mcp-servers/b"
echo "x" > "$T/cov2/ai-stack/mcp-servers/a/requirements.txt"; echo "y" > "$T/cov2/ai-stack/mcp-servers/b/requirements.txt"
rc=0; out="$(PATH="$T/bin:$PATH" CI=true bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/cov2" --output-dir "$T/o11" 2>&1)" || rc=$?
[[ $rc -ne 0 ]] && grep -q "BLOCKING: pip-audit failed" <<<"$out" || { echo "FAIL: pip failure not blocking in CI rc=$rc"; echo "$out"; exit 1; }
rc=0; out="$(PATH="$T/bin:$PATH" env -u CI bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/cov2" --output-dir "$T/o12" 2>&1)" || rc=$?
[[ $rc -eq 0 ]] && grep -q "WARNING: pip-audit failed" <<<"$out" || { echo "FAIL: pip failure local rc=$rc"; echo "$out"; exit 1; }
# Zero coverage / tool failure must not report status=ok (false-green regression).
# $T/bin/pip-audit currently fails (exit 2) from the block above.
rc=0; out="$(PATH="$T/bin:$PATH" env -u CI bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/cov2" --output-dir "$T/o13" 2>&1)" || rc=$?
[[ "$(jq -r .status "$T/o13/latest-security-audit.json")" == "degraded" ]] && grep -q "status=degraded" <<<"$out" \
  && jq -e '.degraded_reasons | map(test("pip-audit failed")) | any' "$T/o13/latest-security-audit.json" >/dev/null \
  || { echo "FAIL: pip-audit tool failure not degraded"; echo "$out"; exit 1; }
rc=0; out="$(PATH="$T/bin:$PATH" env -u CI SECURITY_AUDIT_FAIL_ON_DEGRADED=1 bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/cov2" --output-dir "$T/o14" 2>&1)" || rc=$?
[[ $rc -eq 3 ]] && grep -q "DEGRADED:" <<<"$out" || { echo "FAIL: degraded did not fail unit-mode run rc=$rc"; echo "$out"; exit 1; }
# Zero coverage (no requirements at all) => degraded, not ok.
rc=0; out="$(env -u CI bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/clean" --output-dir "$T/o15" 2>&1)" || rc=$?
[[ "$(jq -r .status "$T/o15/latest-security-audit.json")" == "degraded" ]] || { echo "FAIL: zero coverage reported ok"; echo "$out"; exit 1; }
# Tool missing (no pip-audit, no nix on PATH) => degraded.
mkdir -p "$T/nobin"; for c in bash jq python3 date find mktemp mkdir cat tr sort dirname rm cp mv git env wc sed head cut; do p="$(command -v "$c" 2>/dev/null || true)"; [[ -n "$p" ]] && ln -sf "$p" "$T/nobin/$c"; done
rc=0; out="$(PATH="$T/nobin" env -u CI "$(command -v bash)" "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/cov" --output-dir "$T/o16" 2>&1)" || rc=$?
[[ "$(jq -r .status "$T/o16/latest-security-audit.json")" != "ok" ]] && jq -e '.degraded_reasons | map(test("scanner missing")) | any' "$T/o16/latest-security-audit.json" >/dev/null \
  || { echo "FAIL: missing pip-audit not degraded rc=$rc"; echo "$out"; exit 1; }
cat > "$T/bin/pip-audit" <<'N'
#!/usr/bin/env bash
echo '{"dependencies":[{"name":"x","version":"1","vulns":[]}]}'
N
# npm project needing a scan + clean pip coverage + no npm on PATH => degraded (and exit 3 in unit mode).
mkdir -p "$T/nonpm/ai-stack/mcp-servers/svc" "$T/nonpmbin"
echo "x==1" > "$T/nonpm/ai-stack/mcp-servers/svc/requirements.txt"
echo '{"name":"x","lockfileVersion":3}' | tee "$T/nonpm/package.json" "$T/nonpm/package-lock.json" >/dev/null
for c in bash jq python3 date find mktemp mkdir cat tr sort dirname rm cp mv git env wc sed head cut pip-audit; do p="$(command -v "$c" 2>/dev/null || true)"; [[ -n "$p" ]] && ln -sf "$p" "$T/nonpmbin/$c"; done
ln -sf "$T/bin/pip-audit" "$T/nonpmbin/pip-audit"
export DASHBOARD_SCAN_SCRIPT=/nonexistent SECRETS_ROTATION_PLAN_SCRIPT=/nonexistent
rc=0; out="$(PATH="$T/nonpmbin" env -u CI "$(command -v bash)" "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/nonpm" --output-dir "$T/o18" 2>&1)" || rc=$?
[[ "$(jq -r .status "$T/o18/latest-security-audit.json")" == "degraded" ]] && jq -e '.degraded_reasons | map(test("npm scanner missing")) | any' "$T/o18/latest-security-audit.json" >/dev/null \
  || { echo "FAIL: missing npm with npm project not degraded rc=$rc"; echo "$out"; exit 1; }
rc=0; out="$(PATH="$T/nonpmbin" env -u CI SECURITY_AUDIT_FAIL_ON_DEGRADED=1 "$(command -v bash)" "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/nonpm" --output-dir "$T/o19" 2>&1)" || rc=$?
[[ $rc -eq 3 ]] && grep -q "DEGRADED:.*npm scanner missing" <<<"$out" || { echo "FAIL: missing npm did not exit 3 rc=$rc"; echo "$out"; exit 1; }
# pip error + dashboard error, no vulns: status=findings (presentation) but unit mode must still exit 3.
cat > "$T/bin/pip-audit" <<'N'
#!/usr/bin/env bash
echo boom >&2; exit 3
N
printf '#!/usr/bin/env bash\nexit 1\n' > "$T/bad-dashboard.sh"; chmod +x "$T/bad-dashboard.sh"
rc=0; out="$(PATH="$T/bin:$PATH" env -u CI SECURITY_AUDIT_FAIL_ON_DEGRADED=1 DASHBOARD_SCAN_SCRIPT="$T/bad-dashboard.sh" bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/cov2" --output-dir "$T/o20" 2>&1)" || rc=$?
[[ $rc -eq 3 ]] && [[ "$(jq -r .status "$T/o20/latest-security-audit.json")" == "findings" ]] && grep -q "blocking=0" <<<"$out" \
  || { echo "FAIL: pip+dashboard error did not exit 3 rc=$rc"; echo "$out"; exit 1; }
rc=0; out="$(PATH="$T/bin:$PATH" env -u CI bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/cov2" --output-dir "$T/o21" 2>&1)" || rc=$?
[[ $rc -eq 0 ]] || { echo "FAIL: incomplete scan without the unit flag must stay exit 0 rc=$rc"; echo "$out"; exit 1; }
# npm exits 0 with EMPTY output: scanner error, not clean (dashboard/secrets fakes healthy so only npm is at fault).
cat > "$T/ok-dashboard.sh" <<'N'
#!/usr/bin/env bash
printf '{"generated_at":"t","status":"ok","checks":{"root":{"status":"ok"},"compliance":{"status":"ok"},"integrity":{"status":"ok"}}}' > "$2"
N
cat > "$T/ok-secrets.sh" <<'N'
#!/usr/bin/env bash
printf '{"generated_at":"t","rotation_ready":true,"core_ready":true,"summary":{"total_managed_secrets":3}}' > "$2"
N
chmod +x "$T/ok-dashboard.sh" "$T/ok-secrets.sh"
cat > "$T/bin/npm" <<'N'
#!/usr/bin/env bash
exit 0
N
rc=0; out="$(PATH="$T/bin:$PATH" env -u CI SECURITY_AUDIT_FAIL_ON_DEGRADED=1 DASHBOARD_SCAN_SCRIPT="$T/ok-dashboard.sh" SECRETS_ROTATION_PLAN_SCRIPT="$T/ok-secrets.sh" bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/nonpm" --output-dir "$T/o22" 2>&1)" || rc=$?
[[ $rc -eq 3 ]] && [[ "$(jq -r .status "$T/o22/latest-security-audit.json")" == "degraded" ]] && jq -e '.degraded_reasons | map(test("npm audit errored")) | any' "$T/o22/latest-security-audit.json" >/dev/null \
  || { echo "FAIL: empty npm output not degraded/exit 3 rc=$rc"; echo "$out"; exit 1; }
# Missing dashboard scanner with clean pip + clean npm: unavailable counts as incomplete.
cat > "$T/bin/npm" <<'N'
#!/usr/bin/env bash
echo '{"metadata":{"vulnerabilities":{"info":0,"low":0,"moderate":0,"high":0,"critical":0,"total":0}}}'
N
rc=0; out="$(PATH="$T/bin:$PATH" env -u CI SECURITY_AUDIT_FAIL_ON_DEGRADED=1 DASHBOARD_SCAN_SCRIPT=/nonexistent SECRETS_ROTATION_PLAN_SCRIPT="$T/ok-secrets.sh" bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/nonpm" --output-dir "$T/o23" 2>&1)" || rc=$?
[[ $rc -eq 3 ]] && [[ "$(jq -r .status "$T/o23/latest-security-audit.json")" == "degraded" ]] && jq -e '.degraded_reasons | map(test("dashboard scanner unavailable")) | any' "$T/o23/latest-security-audit.json" >/dev/null \
  || { echo "FAIL: unavailable dashboard scanner not degraded/exit 3 rc=$rc"; echo "$out"; exit 1; }
unset DASHBOARD_SCAN_SCRIPT SECRETS_ROTATION_PLAN_SCRIPT

# Table-driven: every scanner x failure mode must be non-ok, carry a degraded reason, and exit 3 under the flag.
PIP_OK='{"dependencies":[{"name":"x","version":"1","vulns":[]}]}'
NPM_OK='{"metadata":{"vulnerabilities":{"info":0,"low":0,"moderate":0,"high":0,"critical":0,"total":0}}}'
DASH_OK='{"generated_at":"t","status":"ok","checks":{"root":{"status":"ok"},"compliance":{"status":"ok"},"integrity":{"status":"ok"}}}'
SEC_OK='{"generated_at":"t","rotation_ready":true,"core_ready":true,"summary":{"total_managed_secrets":3}}'
run_case() { # <scanner> <mode> ; echoes nothing, sets CASE_RC CASE_OUT CASE_DIR
  local sc="$1" mode="$2" d="$T/tc-$1-$2" c p
  mkdir -p "$d/bin"
  for c in bash jq python3 date find mktemp mkdir cat tr sort dirname rm cp mv git env wc sed head cut; do
    p="$(command -v "$c" 2>/dev/null || true)"; [[ -n "$p" ]] && ln -sf "$p" "$d/bin/$c"
  done
  printf '#!/usr/bin/env bash\nprintf "%%s" "$PIP_BODY"; exit "${PIP_RC:-0}"\n' > "$d/bin/pip-audit"
  printf '#!/usr/bin/env bash\nprintf "%%s" "$NPM_BODY"; exit "${NPM_RC:-0}"\n' > "$d/bin/npm"
  printf '#!/usr/bin/env bash\nprintf "%%s" "$DASH_BODY" > "$2"; exit "${DASH_RC:-0}"\n' > "$d/dash.sh"
  printf '#!/usr/bin/env bash\nprintf "%%s" "$SEC_BODY" > "$2"; exit "${SEC_RC:-0}"\n' > "$d/sec.sh"
  chmod +x "$d/bin/pip-audit" "$d/bin/npm" "$d/dash.sh" "$d/sec.sh"
  local pb="$PIP_OK" nb="$NPM_OK" db="$DASH_OK" sb="$SEC_OK" body="" rc=0 unknown=""
  case "$sc" in
    pip) unknown='{"dependencies":"nope"}' ;;
    npm) unknown='{"metadata":{"vulnerabilities":"x"}}' ;;
    dashboard) unknown='{"generated_at":"t","status":"weird"}' ;;
    secrets) unknown='{"generated_at":"t","rotation_ready":"maybe"}' ;;
  esac
  local nocov nocov2 nocov3
  case "$sc" in
    pip) nocov='{"dependencies":[]}'; nocov2='{"dependencies":[{"name":"x","version":"1","skip_reason":"not on index"}]}'; nocov3='{"dependencies":[{"name":"x","version":"1"}]}' ;;
    npm) nocov='{"metadata":{"vulnerabilities":{}}}'; nocov2='{"metadata":{"vulnerabilities":{"info":0,"low":0,"moderate":0,"high":"0","critical":0}}}'; nocov3='{"metadata":{"vulnerabilities":{"high":0,"critical":0,"total":0}}}' ;;
    dashboard) nocov='{"generated_at":"t","status":"ok"}'; nocov2='{"generated_at":"t","status":"ok","checks":{"root":{"status":"ok"},"compliance":{"status":"unavailable"},"integrity":{"status":"ok"}}}'; nocov3='{"generated_at":"t","status":"degraded","checks":{"root":{"status":"ok"},"compliance":{"status":"unavailable"},"integrity":{"status":"ok"}}}' ;;
    secrets) nocov='{"generated_at":"t","rotation_ready":true}'; nocov2='{"generated_at":"t","rotation_ready":true,"core_ready":true,"summary":{"total_managed_secrets":0}}'; nocov3='{"generated_at":"t","rotation_ready":true,"core_ready":true,"summary":{}}' ;;
  esac
  case "$mode" in
    nocov) body="$nocov" ;;
    nocov2) body="$nocov2" ;;
    nocov3) body="$nocov3" ;;
    nonzero) rc=2; body="" ;;
    empty) body="" ;;
    malformed) body='{not json' ;;
    emptyobj) body='{}' ;;
    unknown) body="$unknown" ;;
  esac
  local prc="" nrc="" drc="" src="" dscript="$d/dash.sh" sscript="$d/sec.sh"
  case "$sc:$mode" in
    pip:missing) rm -f "$d/bin/pip-audit" ;;
    npm:missing) rm -f "$d/bin/npm" ;;
    dashboard:missing) dscript=/nonexistent ;;
    secrets:missing) sscript=/nonexistent ;;
    pip:*) pb="$body"; prc="$rc" ;;
    npm:*) nb="$body"; nrc="$rc" ;;
    dashboard:*) db="$body"; drc="$rc" ;;
    secrets:*) sb="$body"; src="$rc" ;;
  esac
  CASE_RC=0
  CASE_OUT="$(PATH="$d/bin" env -u CI SECURITY_AUDIT_FAIL_ON_DEGRADED=1 PIP_BODY="$pb" PIP_RC="$prc" NPM_BODY="$nb" NPM_RC="$nrc" \
    DASH_BODY="$db" DASH_RC="$drc" SEC_BODY="$sb" SEC_RC="$src" DASHBOARD_SCAN_SCRIPT="$dscript" SECRETS_ROTATION_PLAN_SCRIPT="$sscript" \
    "$(command -v bash)" "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/nonpm" --output-dir "$d/out" 2>&1)" || CASE_RC=$?
  CASE_DIR="$d/out"
}
run_case none healthy
[[ $CASE_RC -eq 0 && "$(jq -r .status "$CASE_DIR/latest-security-audit.json")" == "ok" ]] || { echo "FAIL: healthy baseline not ok rc=$CASE_RC"; echo "$CASE_OUT"; exit 1; }
for sc in pip npm dashboard secrets; do
  for mode in missing nonzero empty malformed emptyobj unknown nocov nocov2 nocov3; do
    run_case "$sc" "$mode"
    st="$(jq -r .status "$CASE_DIR/latest-security-audit.json")"
    if [[ $CASE_RC -ne 3 || "$st" == "ok" ]] || ! jq -e '.degraded_reasons | length > 0' "$CASE_DIR/latest-security-audit.json" >/dev/null; then
      echo "FAIL: $sc/$mode rc=$CASE_RC status=$st"; echo "$CASE_OUT"; exit 1
    fi
    echo "case $sc/$mode: status=$st exit=$CASE_RC"
  done
done
# pip skip handling and -r includes (healthy dashboard/secrets/npm from the table fixtures).
pip_case() { # <name> <requirements-setup-fn> <pip-body> [allowlist-json]
  local body="$3" al="${4:-}" d="$T/tc-pip-$1" rd="$T/tc-pip-$1/repo"
  mkdir -p "$rd/ai-stack/mcp-servers/svc"; : > "$d/.keep"
  "$2" "$rd/ai-stack/mcp-servers/svc"
  [[ -n "$al" ]] && printf '%s' "$al" > "$d/allow.json"
  PIPC_RC=0
  PIPC_OUT="$(PATH="$T/tc-none-healthy/bin" env -u CI SECURITY_AUDIT_FAIL_ON_DEGRADED=1 PIP_BODY="$body" NPM_BODY="$NPM_OK" DASH_BODY="$DASH_OK" SEC_BODY="$SEC_OK" \
    DASHBOARD_SCAN_SCRIPT="$T/tc-none-healthy/dash.sh" SECRETS_ROTATION_PLAN_SCRIPT="$T/tc-none-healthy/sec.sh" ${al:+SECURITY_AUDIT_PIP_SKIP_ALLOWLIST="$d/allow.json"} \
    "$(command -v bash)" "$ROOT/scripts/security/security-audit.sh" --repo-root "$rd" --output-dir "$d/out" 2>&1)" || PIPC_RC=$?
  PIPC_STATUS="$(jq -r .status "$d/out/latest-security-audit.json")"
}
req_plain() { echo "x==1" > "$1/requirements.txt"; }
req_only_r() { echo "x==1" > "$1/base.txt"; printf -- '-r base.txt\n-c constraints.txt\n' > "$1/requirements.txt"; }
req_cycle() { printf -- '-r b.txt\ny==1\n' > "$1/requirements.txt"; printf -- '-r requirements.txt\n' > "$1/b.txt"; }
req_constraint_only() { printf -- '-c constraints.txt\n# nothing\n' > "$1/requirements.txt"; }
PIP_MIXED='{"dependencies":[{"name":"x","version":"1","vulns":[]},{"name":"Weird_Pkg","version":"2","skip_reason":"not on PyPI"}]}'
PIP_EMPTY='{"dependencies":[]}'
pip_case skip-unlisted req_plain "$PIP_MIXED"
[[ $PIPC_RC -eq 3 && "$PIPC_STATUS" != "ok" ]] && grep -q "Weird_Pkg" <<<"$PIPC_OUT" || { echo "FAIL: unallowlisted partial skip rc=$PIPC_RC"; echo "$PIPC_OUT"; exit 1; }
echo "case pip/partial-skip-not-allowlisted: status=$PIPC_STATUS exit=$PIPC_RC"
pip_case skip-listed req_plain "$PIP_MIXED" '{"allowed_skips":[{"package":"weird-pkg","reason":"internal wheel, not on PyPI"}]}'
[[ $PIPC_RC -eq 0 && "$PIPC_STATUS" == "ok" ]] || { echo "FAIL: allowlisted partial skip rc=$PIPC_RC status=$PIPC_STATUS"; echo "$PIPC_OUT"; exit 1; }
echo "case pip/partial-skip-allowlisted: status=$PIPC_STATUS exit=$PIPC_RC"
pip_case skip-noreason req_plain "$PIP_MIXED" '{"allowed_skips":[{"package":"weird-pkg"}]}'
[[ $PIPC_RC -eq 3 ]] || { echo "FAIL: allowlist entry without reason must not allow rc=$PIPC_RC"; echo "$PIPC_OUT"; exit 1; }
echo "case pip/allowlist-entry-without-reason: exit=$PIPC_RC"
pip_case r-empty req_only_r "$PIP_EMPTY"
[[ $PIPC_RC -eq 3 && "$PIPC_STATUS" != "ok" ]] || { echo "FAIL: -r-only file with empty report rc=$PIPC_RC"; echo "$PIPC_OUT"; exit 1; }
echo "case pip/-r-only-empty-report: status=$PIPC_STATUS exit=$PIPC_RC"
pip_case r-audited req_only_r "$PIP_OK"
[[ $PIPC_RC -eq 0 && "$PIPC_STATUS" == "ok" ]] || { echo "FAIL: -r with audited deps rc=$PIPC_RC status=$PIPC_STATUS"; echo "$PIPC_OUT"; exit 1; }
echo "case pip/-r-with-audited-deps: status=$PIPC_STATUS exit=$PIPC_RC"
pip_case cycle req_cycle "$PIP_EMPTY"
[[ $PIPC_RC -eq 3 ]] || { echo "FAIL: cyclic includes with empty report rc=$PIPC_RC"; echo "$PIPC_OUT"; exit 1; }
echo "case pip/cyclic-include-empty-report: exit=$PIPC_RC"
pip_case constraint-only req_constraint_only "$PIP_EMPTY"
[[ $PIPC_RC -eq 0 && "$PIPC_STATUS" == "ok" ]] || { echo "FAIL: constraint-only file needs no audited dep rc=$PIPC_RC"; echo "$PIPC_OUT"; exit 1; }
echo "case pip/constraint-only-no-requirements: status=$PIPC_STATUS exit=$PIPC_RC"
# Stale report: scanners exit 0 writing nothing while a valid report from a previous run sits in the output dir.
d="$T/tc-stale"; mkdir -p "$d/out"
cp "$T/tc-none-healthy/out/latest-dashboard-security-scan.json" "$T/tc-none-healthy/out/latest-secrets-rotation-plan.json" "$d/out/"
printf '#!/usr/bin/env bash\nexit 0\n' > "$d/noop.sh"; chmod +x "$d/noop.sh"
rc=0; out="$(PATH="$T/tc-none-healthy/bin" env -u CI SECURITY_AUDIT_FAIL_ON_DEGRADED=1 PIP_BODY="$PIP_OK" NPM_BODY="$NPM_OK" DASHBOARD_SCAN_SCRIPT="$d/noop.sh" SECRETS_ROTATION_PLAN_SCRIPT="$d/noop.sh" "$(command -v bash)" "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/nonpm" --output-dir "$d/out" 2>&1)" || rc=$?
[[ $rc -eq 3 ]] && [[ "$(jq -r .status "$d/out/latest-security-audit.json")" != "ok" ]] || { echo "FAIL: stale prior report satisfied a no-op scanner rc=$rc"; echo "$out"; exit 1; }
echo "case dashboard+secrets/stale-prior-report: exit=$rc"
# secrets "planning_required" with full evidence is a state finding, not a coverage gap: ok, exit 0.
PLAN_BODY='{"generated_at":"t","rotation_ready":false,"core_ready":false,"summary":{"total_managed_secrets":3}}'
d="$T/tc-plan"; mkdir -p "$d"
printf '#!/usr/bin/env bash\nprintf "%%s" "$PLAN_BODY" > "$2"\n' > "$d/sec.sh"; chmod +x "$d/sec.sh"
rc=0; out="$(PLAN_BODY="$PLAN_BODY" PATH="$T/tc-none-healthy/bin" env -u CI SECURITY_AUDIT_FAIL_ON_DEGRADED=1 PIP_BODY="$PIP_OK" NPM_BODY="$NPM_OK" DASHBOARD_SCAN_SCRIPT="$T/tc-none-healthy/dash.sh" DASH_BODY="$DASH_OK" SECRETS_ROTATION_PLAN_SCRIPT="$d/sec.sh" "$(command -v bash)" "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/nonpm" --output-dir "$d/out" 2>&1)" || rc=$?
[[ $rc -eq 0 && "$(jq -r .summary.secrets_rotation.status "$d/out/latest-security-audit.json")" == "planning_required" && "$(jq -r .status "$d/out/latest-security-audit.json")" == "ok" ]] || { echo "FAIL: planning_required should stay informational rc=$rc"; echo "$out"; exit 1; }
echo "case secrets/planning_required (valid, informational): status=ok exit=$rc"
# A clean scan with real coverage stays ok.
cat > "$T/bin/pip-audit" <<'N'
#!/usr/bin/env bash
echo '{"dependencies":[{"name":"x","version":"1","vulns":[]}]}'
N
rc=0; out="$(PATH="$T/bin:$PATH" env -u CI bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/cov" --output-dir "$T/o17" 2>&1)" || rc=$?
[[ "$(jq -r .status "$T/o17/latest-security-audit.json")" == "ok" ]] || { echo "FAIL: covered clean scan not ok"; echo "$out"; exit 1; }
echo "PASS: security-audit gate blocks on seeded finding, passes clean, flags no-coverage as degraded"
