#!/usr/bin/env bash
# test-delegate-codex-quota-precheck.sh — deterministic, offline tests for the
# delegate-to-codex quota-aware pre-check (delegate-codex-quota-precheck slice).
#
# NEVER invokes real codex and NEVER depends on a live coordinator/network.
# $CODEX_BIN is stubbed with a fake script whose behavior (quota-exhausted
# error / unparseable quota error / healthy success) is controlled by a mode
# file this test writes, and which records every invocation to a marker file
# so the test can prove whether it was (or was not) invoked.
#
# Cases covered (see SLICE-DESIGN-AND-AUTHORIZATION.md Validation section):
#   (a) cooldown written with the parsed reset time on quota error
#   (b) second dispatch fast-fails without invoking the stub while cooldown active
#   (c) bypass env var / --force-quota-retry forces an attempt; a forced
#       attempt that still hits the limit re-arms the cooldown
#   (d) expired cooldown is cleared and dispatch proceeds
#   (e) healthy success writes no cooldown
#   (f) unparseable reset line falls back to a bounded cooldown
# Plus background (nohup) run-mode coverage for (a) and (e), since the design
# requires error capture after BOTH run modes.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DELEGATE="$REPO_ROOT/scripts/ai/delegate-to-codex"
DELEGATION_DIR="$REPO_ROOT/.agents/delegation"
COOLDOWN_FILE="$DELEGATION_DIR/.codex-quota-cooldown"
REGISTRY="$DELEGATION_DIR/registry.jsonl"
OUTPUTS_DIR="$DELEGATION_DIR/outputs"

[[ -x "$DELEGATE" ]] || { echo "FAIL: delegate-to-codex not found/executable at $DELEGATE"; exit 1; }

WORKDIR="$(mktemp -d)"
STUB_BIN="$WORKDIR/codex"
MARKER="$WORKDIR/stub-invoked.marker"
STUB_MODE_FILE="$WORKDIR/stub-mode"

PASS=0
FAIL=0
CREATED_TASK_IDS=()

# ── isolate real runtime state so this test never disturbs live delegation ──
SAVED_COOLDOWN=""
SAVED_REGISTRY=""
if [[ -f "$COOLDOWN_FILE" ]]; then
    SAVED_COOLDOWN="$WORKDIR/saved-cooldown"
    cp "$COOLDOWN_FILE" "$SAVED_COOLDOWN"
fi
if [[ -f "$REGISTRY" ]]; then
    SAVED_REGISTRY="$WORKDIR/saved-registry.jsonl"
    cp "$REGISTRY" "$SAVED_REGISTRY"
fi

cleanup() {
    rm -f "$COOLDOWN_FILE"
    if [[ -n "$SAVED_COOLDOWN" ]]; then
        cp "$SAVED_COOLDOWN" "$COOLDOWN_FILE"
    fi
    if [[ -n "$SAVED_REGISTRY" ]]; then
        cp "$SAVED_REGISTRY" "$REGISTRY"
    fi
    for tid in "${CREATED_TASK_IDS[@]:-}"; do
        [[ -n "$tid" ]] && rm -f "$OUTPUTS_DIR/${tid}.log"
    done
    rm -rf "$WORKDIR"
}
trap cleanup EXIT

pass() { PASS=$((PASS+1)); echo "PASS: $1"; }
fail() { FAIL=$((FAIL+1)); echo "FAIL: $1"; }

reset_state() {
    rm -f "$COOLDOWN_FILE"
    rm -f "$MARKER"
    printf '%s' "ok" > "$STUB_MODE_FILE"
}

# ── fake codex binary ────────────────────────────────────────────────────────
# Mode read from $TEST_STUB_MODE_FILE: "quota" | "quota-unparseable" | "ok".
# Ignores all args (delegate-to-codex passes `exec <full_prompt>`); a real
# codex binary is never invoked anywhere in this test.
cat > "$STUB_BIN" <<'STUBEOF'
#!/usr/bin/env bash
echo "invoked $(date -u +%s%N)" >> "$TEST_MARKER"
mode="$(cat "$TEST_STUB_MODE_FILE" 2>/dev/null || echo ok)"
case "$mode" in
    quota)
        echo "ERROR: You've hit your usage limit for the day, try again at Jul 25th."
        exit 1
        ;;
    quota-unparseable)
        echo "ERROR: You've hit your usage limit for the day, try again at whenever-the-wind-blows."
        exit 1
        ;;
    *)
        echo "codex stub: task complete"
        exit 0
        ;;
esac
STUBEOF
chmod +x "$STUB_BIN"

export CODEX_BIN="$STUB_BIN"
export TEST_MARKER="$MARKER"
export TEST_STUB_MODE_FILE="$STUB_MODE_FILE"
# Full offline isolation: no live coordinator dependency, no dispatch-budget
# interference from real usage history, no secret-scan surprises.
export A2A_GUARD_BLOCK=0
export A2A_BUDGET_BYPASS=1
export HYBRID_COORDINATOR_URL="http://127.0.0.1:1"
unset DELEGATE_CODEX_IGNORE_COOLDOWN

# run_bg <stub-mode> — dispatch in background mode, wait for completion, track
# the created output file for cleanup. Never invokes real codex.
run_bg() {
    local stub_mode="$1"
    printf '%s' "$stub_mode" > "$STUB_MODE_FILE"
    local out tid
    out="$("$DELEGATE" --prompt "quota-precheck-test-bg-$(date +%s%N)" 2>&1)"
    tid="$(printf '%s\n' "$out" | tail -1)"
    if [[ "$tid" == codex-* ]]; then
        CREATED_TASK_IDS+=("$tid")
        local waited=0
        while [[ $waited -lt 100 ]]; do
            local status
            status="$("$DELEGATE" --status "$tid" 2>/dev/null \
                | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' 2>/dev/null)"
            [[ "$status" == "done" || "$status" == "failed" ]] && break
            sleep 0.1
            waited=$((waited+1))
        done
    fi
}

echo "=== delegate-to-codex quota pre-check tests ==="

# (a) cooldown written with the parsed reset time on quota error (wait-mode).
reset_state
printf '%s' "quota" > "$STUB_MODE_FILE"
"$DELEGATE" --wait --prompt "quota-precheck-test-a" >/dev/null 2>&1
if [[ -f "$COOLDOWN_FILE" ]] && grep -q "^2026-07-25T" "$COOLDOWN_FILE"; then
    pass "(a) wait-mode quota error writes parsed cooldown (2026-07-25)"
else
    fail "(a) wait-mode quota error writes parsed cooldown — got: $(cat "$COOLDOWN_FILE" 2>/dev/null || echo MISSING)"
fi
if [[ -f "$MARKER" ]] && [[ "$(wc -l < "$MARKER")" -eq 1 ]]; then
    pass "(a) stub invoked exactly once"
else
    fail "(a) stub invocation count — got: $(cat "$MARKER" 2>/dev/null || echo MISSING)"
fi

# (b) second dispatch fast-fails without invoking the stub while cooldown active.
rm -f "$MARKER"
out="$("$DELEGATE" --wait --prompt "quota-precheck-test-b" 2>&1)"; rc=$?
if [[ $rc -ne 0 ]] && echo "$out" | grep -qi "cooldown"; then
    pass "(b) fast-fail while cooldown active (rc=$rc)"
else
    fail "(b) expected fast-fail with cooldown message, got rc=$rc: $out"
fi
if [[ ! -f "$MARKER" ]]; then
    pass "(b) stub NOT invoked during active cooldown"
else
    fail "(b) stub was invoked during active cooldown: $(cat "$MARKER")"
fi

# (c) bypass env var forces an attempt despite active cooldown.
rm -f "$MARKER"
printf '%s' "ok" > "$STUB_MODE_FILE"
DELEGATE_CODEX_IGNORE_COOLDOWN=1 "$DELEGATE" --wait --prompt "quota-precheck-test-c-env" >/dev/null 2>&1
if [[ -f "$MARKER" ]]; then
    pass "(c) DELEGATE_CODEX_IGNORE_COOLDOWN=1 forces stub invocation despite active cooldown"
else
    fail "(c) bypass env var did not force invocation"
fi

# (c) --force-quota-retry flag forces an attempt despite active cooldown.
rm -f "$COOLDOWN_FILE" "$MARKER"
printf '%s' "quota" > "$STUB_MODE_FILE"
"$DELEGATE" --wait --prompt "quota-precheck-test-c-arm" >/dev/null 2>&1   # arm a cooldown
rm -f "$MARKER"
printf '%s' "ok" > "$STUB_MODE_FILE"
"$DELEGATE" --wait --force-quota-retry --prompt "quota-precheck-test-c-flag" >/dev/null 2>&1
if [[ -f "$MARKER" ]]; then
    pass "(c) --force-quota-retry forces stub invocation despite active cooldown"
else
    fail "(c) --force-quota-retry did not force invocation"
fi

# (c) a forced attempt that still hits the limit re-arms the cooldown.
rm -f "$COOLDOWN_FILE" "$MARKER"
printf '%s' "quota" > "$STUB_MODE_FILE"
"$DELEGATE" --wait --prompt "quota-precheck-test-c-rearm1" >/dev/null 2>&1
first_cooldown="$(cat "$COOLDOWN_FILE" 2>/dev/null || echo "")"
rm -f "$MARKER"
DELEGATE_CODEX_IGNORE_COOLDOWN=1 "$DELEGATE" --wait --prompt "quota-precheck-test-c-rearm2" >/dev/null 2>&1
if [[ -f "$MARKER" ]] && [[ -f "$COOLDOWN_FILE" ]] && [[ -n "$first_cooldown" ]]; then
    pass "(c) forced attempt that still hits the limit re-arms the cooldown"
else
    fail "(c) re-arm after forced failure did not happen"
fi

# (d) expired cooldown is cleared and dispatch proceeds.
reset_state
printf '2000-01-01T00:00:00Z\n' > "$COOLDOWN_FILE"
printf '%s' "ok" > "$STUB_MODE_FILE"
"$DELEGATE" --wait --prompt "quota-precheck-test-d" >/dev/null 2>&1
if [[ -f "$MARKER" ]] && [[ ! -f "$COOLDOWN_FILE" ]]; then
    pass "(d) expired cooldown cleared, dispatch proceeded, stub invoked"
else
    fail "(d) expired cooldown handling — marker=$([[ -f "$MARKER" ]] && echo yes || echo no) cooldown_file=$([[ -f "$COOLDOWN_FILE" ]] && echo yes || echo no)"
fi

# (e) healthy success writes no cooldown.
reset_state
printf '%s' "ok" > "$STUB_MODE_FILE"
"$DELEGATE" --wait --prompt "quota-precheck-test-e" >/dev/null 2>&1
if [[ ! -f "$COOLDOWN_FILE" ]]; then
    pass "(e) healthy success writes no cooldown"
else
    fail "(e) healthy success unexpectedly wrote a cooldown: $(cat "$COOLDOWN_FILE")"
fi

# (f) unparseable reset line falls back to a bounded ~1h cooldown.
reset_state
printf '%s' "quota-unparseable" > "$STUB_MODE_FILE"
"$DELEGATE" --wait --prompt "quota-precheck-test-f" >/dev/null 2>&1
if [[ -f "$COOLDOWN_FILE" ]]; then
    cooldown_epoch="$(date -u -d "$(cat "$COOLDOWN_FILE")" +%s 2>/dev/null || echo 0)"
    now_epoch="$(date -u +%s)"
    lower=$((now_epoch + 3500))
    upper=$((now_epoch + 3900))
    if [[ "$cooldown_epoch" -gt "$lower" && "$cooldown_epoch" -lt "$upper" ]]; then
        pass "(f) unparseable reset line falls back to bounded ~1h cooldown"
    else
        fail "(f) fallback cooldown out of expected bound: $(cat "$COOLDOWN_FILE") (epoch=$cooldown_epoch now=$now_epoch)"
    fi
else
    fail "(f) unparseable reset line wrote no cooldown at all"
fi

# (g) wait-mode non-zero codex exit is reported as failed, not success.
# Regression coverage for the acceptance-verdict criterion-4 defect: a bare
# `| tee "$output_file" || true` runs `true` as its own one-element pipeline,
# which resets PIPESTATUS[0] to 0 on every failed run — pinning exit_code=0 and
# firing the success branch even though codex exited non-zero. This asserts the
# registry status is "failed" (not "done") and the audit outcome posted to the
# coordinator is "error" (not "success") for a non-zero wait-mode codex exit.
reset_state
CURL_LOG="$WORKDIR/curl-calls.log"
rm -f "$CURL_LOG"
STUB_CURL="$WORKDIR/curl"
# Fake curl: capture the JSON -d payload of every audit POST instead of
# reaching a real network endpoint, so the wait-mode audit outcome (which the
# real audit-write.sh silently swallows on curl failure) can be asserted
# offline. Always exits 0 so the caller's audit path behaves as if the post
# succeeded — no real network I/O anywhere in this test.
cat > "$STUB_CURL" <<'CURLEOF'
#!/usr/bin/env bash
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
    if [[ "${args[i]}" == "-d" ]]; then
        printf '%s\n' "${args[i+1]}" >> "$TEST_CURL_LOG"
    fi
done
exit 0
CURLEOF
chmod +x "$STUB_CURL"
export TEST_CURL_LOG="$CURL_LOG"
printf '%s' "quota" > "$STUB_MODE_FILE"
out="$(PATH="$WORKDIR:$PATH" "$DELEGATE" --wait --prompt "quota-precheck-test-g-exitcode" 2>&1)"
tid="$(printf '%s\n' "$out" | grep -oE 'codex-[0-9]{8}-[0-9]{6}-[a-z0-9]+' | tail -1)"
[[ -n "$tid" ]] && CREATED_TASK_IDS+=("$tid")
if printf '%s\n' "$out" | grep -q "Task .* failed\."; then
    pass "(g) wait-mode non-zero codex exit reported as failed (not completed)"
else
    fail "(g) wait-mode non-zero codex exit — expected 'Task ... failed.', got: $out"
fi
status=""
if [[ -n "$tid" ]]; then
    status="$("$DELEGATE" --status "$tid" 2>/dev/null \
        | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' 2>/dev/null)"
fi
if [[ "$status" == "failed" ]]; then
    pass "(g) wait-mode non-zero codex exit sets registry status=failed (not done)"
else
    fail "(g) wait-mode non-zero exit — expected registry status=failed, got: '$status' (tid=$tid)"
fi
last_outcome=""
if [[ -f "$CURL_LOG" ]]; then
    last_outcome="$(tail -1 "$CURL_LOG" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("outcome",""))' 2>/dev/null)"
fi
if [[ "$last_outcome" == "error" ]]; then
    pass "(g) wait-mode non-zero codex exit posts audit outcome=error (not success)"
else
    fail "(g) wait-mode non-zero exit audit outcome — expected error, got: '$last_outcome' (log: $(cat "$CURL_LOG" 2>/dev/null || echo MISSING))"
fi
unset TEST_CURL_LOG

# ── background (nohup) run-mode coverage ─────────────────────────────────────
# (a-bg) cooldown written with the parsed reset time on quota error.
reset_state
run_bg quota
if [[ -f "$COOLDOWN_FILE" ]] && grep -q "^2026-07-25T" "$COOLDOWN_FILE"; then
    pass "(a-bg) background quota error writes parsed cooldown"
else
    fail "(a-bg) background quota error cooldown — got: $(cat "$COOLDOWN_FILE" 2>/dev/null || echo MISSING)"
fi

# (e-bg) healthy background success writes no cooldown.
reset_state
run_bg ok
if [[ ! -f "$COOLDOWN_FILE" ]]; then
    pass "(e-bg) healthy background success writes no cooldown"
else
    fail "(e-bg) healthy background success unexpectedly wrote a cooldown"
fi

echo "=== $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]]
