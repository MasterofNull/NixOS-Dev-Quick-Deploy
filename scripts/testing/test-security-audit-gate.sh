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
printf '{"status":"ok"}' > "$2"
N
cat > "$T/ok-secrets.sh" <<'N'
#!/usr/bin/env bash
printf '{"rotation_ready":true}' > "$2"
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
echo '{"metadata":{"vulnerabilities":{"high":0,"critical":0}}}'
N
rc=0; out="$(PATH="$T/bin:$PATH" env -u CI SECURITY_AUDIT_FAIL_ON_DEGRADED=1 DASHBOARD_SCAN_SCRIPT=/nonexistent SECRETS_ROTATION_PLAN_SCRIPT="$T/ok-secrets.sh" bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/nonpm" --output-dir "$T/o23" 2>&1)" || rc=$?
[[ $rc -eq 3 ]] && [[ "$(jq -r .status "$T/o23/latest-security-audit.json")" == "degraded" ]] && jq -e '.degraded_reasons | map(test("dashboard scanner unavailable")) | any' "$T/o23/latest-security-audit.json" >/dev/null \
  || { echo "FAIL: unavailable dashboard scanner not degraded/exit 3 rc=$rc"; echo "$out"; exit 1; }
unset DASHBOARD_SCAN_SCRIPT SECRETS_ROTATION_PLAN_SCRIPT
# A clean scan with real coverage stays ok.
cat > "$T/bin/pip-audit" <<'N'
#!/usr/bin/env bash
echo '{"dependencies":[{"name":"x","version":"1","vulns":[]}]}'
N
rc=0; out="$(PATH="$T/bin:$PATH" env -u CI bash "$ROOT/scripts/security/security-audit.sh" --repo-root "$T/cov" --output-dir "$T/o17" 2>&1)" || rc=$?
[[ "$(jq -r .status "$T/o17/latest-security-audit.json")" == "ok" ]] || { echo "FAIL: covered clean scan not ok"; echo "$out"; exit 1; }
echo "PASS: security-audit gate blocks on seeded finding, passes clean, flags no-coverage as degraded"
