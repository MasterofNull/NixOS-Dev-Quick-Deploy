#!/usr/bin/env bash
# Post-switch validation of the live llama.cpp main-model server after a binary bump.
# The new main model cannot co-run with the live one (RAM), so this runs AFTER
# `nixos-rebuild switch`, against the running service. Checks: /health, one chat
# completion with enable_thinking:false, one JSON-schema constrained completion,
# MTP/draft acceptance (response timings, then /metrics), and tok/s vs baseline.
# Exit 0 = all hard checks passed; non-zero = failure, with the rollback command printed.
#
# Env: LLAMA_URL | LLAMA_CPP_BASE_URL | LLAMA_PORT (default 8080), LLAMA_API_KEY (optional),
#      AQ_VALIDATE_BASE_GEN_TOKPS (4.2) AQ_VALIDATE_BASE_PROMPT_TOKPS (5.15)
#      AQ_VALIDATE_MIN_RATIO (0.8; fail below ratio*baseline), AQ_VALIDATE_REQUIRE_MTP (0; 1 = fail if
#      no acceptance data), AQ_VALIDATE_TIMEOUT_S (600; main model runs ~4 tok/s, be patient).
# Baselines: docs/harness-first/evidence/2026-11-18-llama-cpp-bump.md section 6.
set -uo pipefail

BASE="${LLAMA_URL:-${LLAMA_CPP_BASE_URL:-http://127.0.0.1:${LLAMA_PORT:-8080}}}"
BASE_GEN="${AQ_VALIDATE_BASE_GEN_TOKPS:-4.2}"
BASE_PROMPT="${AQ_VALIDATE_BASE_PROMPT_TOKPS:-5.15}"
MIN_RATIO="${AQ_VALIDATE_MIN_RATIO:-0.8}"
REQUIRE_MTP="${AQ_VALIDATE_REQUIRE_MTP:-0}"
TIMEOUT="${AQ_VALIDATE_TIMEOUT_S:-600}"
ROLLBACK='sudo nixos-rebuild switch --rollback   # or: set mySystem.aiStack.llamaCpp.useFallback = true and rebuild'

fails=0
fail() { echo "FAIL: $*" >&2; fails=$((fails + 1)); }
pass() { echo "PASS: $*"; }
warn() { echo "WARN: $*"; }

auth=()
[ -n "${LLAMA_API_KEY:-}" ] && auth=(-H "Authorization: Bearer ${LLAMA_API_KEY}")

post() { # $1=json body -> stdout response; nonzero on transport/HTTP failure
  curl -sS -f -m "$TIMEOUT" "${auth[@]}" -H 'Content-Type: application/json' \
    -d "$1" "$BASE/v1/chat/completions"
}

finish() {
  if [ "$fails" -gt 0 ]; then
    echo "RESULT: FAIL ($fails failed checks) against $BASE" >&2
    echo "ROLLBACK: $ROLLBACK" >&2
    exit 1
  fi
  echo "RESULT: PASS against $BASE"
  exit 0
}

# 1. health
if curl -sS -f -m 10 "$BASE/health" | python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("status")=="ok" else 1)'; then
  pass "/health ok"
else
  fail "/health not ok at $BASE"
  finish # nothing else can work
fi

# 2. chat completion, thinking off (also the speed + MTP sample)
chat_body='{"messages":[{"role":"user","content":"Count from one to twenty in English words, separated by commas."}],"max_tokens":128,"temperature":0,"chat_template_kwargs":{"enable_thinking":false}}'
chat_out="$(post "$chat_body")" || { fail "chat completion request failed"; chat_out=""; }
verdict="$(printf '%s' "$chat_out" | BASE_GEN="$BASE_GEN" BASE_PROMPT="$BASE_PROMPT" MIN_RATIO="$MIN_RATIO" python3 -c '
import json, os, sys
try:
    r = json.loads(sys.stdin.read())
except ValueError:
    print("ERR chat response is not JSON"); sys.exit(0)
msg = (r.get("choices") or [{}])[0].get("message", {})
if not (msg.get("content") or "").strip():
    print("ERR empty content"); sys.exit(0)
if (msg.get("reasoning_content") or "").strip():
    print("ERR reasoning_content present although enable_thinking=false"); sys.exit(0)
t = r.get("timings") or {}
gen, pr = t.get("predicted_per_second"), t.get("prompt_per_second")
dn, da = t.get("draft_n"), t.get("draft_n_accepted")
print("OK gen=%s prompt=%s draft_n=%s draft_acc=%s" % (gen, pr, dn, da))
')"
case "$verdict" in
  OK*) pass "chat completion (enable_thinking:false) returned content"; echo "     $verdict" ;;
  ERR*) fail "chat completion: ${verdict#ERR }" ;;
  *) [ -n "$chat_out" ] && fail "chat completion: unparseable verdict" ;;
esac

# 3. JSON-schema constrained completion
schema_body='{"messages":[{"role":"user","content":"Give a fruit and its colour."}],"max_tokens":96,"temperature":0,"chat_template_kwargs":{"enable_thinking":false},"response_format":{"type":"json_schema","json_schema":{"name":"fruit","strict":true,"schema":{"type":"object","properties":{"fruit":{"type":"string"},"colour":{"type":"string"}},"required":["fruit","colour"],"additionalProperties":false}}}}'
schema_out="$(post "$schema_body")" || { fail "json_schema completion request failed"; schema_out=""; }
if [ -n "$schema_out" ]; then
  if printf '%s' "$schema_out" | python3 -c '
import json, sys
c = json.loads(sys.stdin.read())["choices"][0]["message"]["content"]
o = json.loads(c)
sys.exit(0 if isinstance(o.get("fruit"), str) and isinstance(o.get("colour"), str) and set(o) == {"fruit", "colour"} else 1)
' 2>/dev/null; then
    pass "json_schema completion is valid schema-conforming JSON"
  else
    fail "json_schema completion not valid JSON matching the schema"
  fi
fi

# 4. MTP / draft acceptance: response timings first, then /metrics, then slots
mtp="$(printf '%s' "$verdict" | sed -n 's/.*draft_n=\([^ ]*\) draft_acc=\([^ ]*\).*/\1 \2/p')"
dn="${mtp%% *}"; da="${mtp##* }"
if [ -n "$mtp" ] && [ "$dn" != "None" ] && [ "$dn" -gt 0 ] 2>/dev/null; then
  if [ "${da:-0}" -gt 0 ] 2>/dev/null; then
    pass "MTP draft acceptance: $da of $dn drafted tokens accepted"
  else
    fail "MTP draft path produced zero accepted tokens ($da/$dn): draft-mtp likely broken"
  fi
else
  m="$(curl -sS -m 10 "$BASE/metrics" 2>/dev/null | grep -iE '^llamacpp:.*(draft|accept)' || true)"
  if [ -n "$m" ]; then
    echo "     metrics: $(echo "$m" | tr '\n' ' ')"
    pass "draft/accept counters present in /metrics (inspect values above)"
  elif [ "$REQUIRE_MTP" = "1" ]; then
    fail "no draft acceptance data in response timings or /metrics (AQ_VALIDATE_REQUIRE_MTP=1)"
  else
    warn "no draft acceptance data in response timings or /metrics; check the journal at --log-verbosity 2 and record the rate"
  fi
fi

# 5. tok/s vs baseline
speed="$(printf '%s' "$verdict" | sed -n 's/.*gen=\([^ ]*\) prompt=\([^ ]*\) .*/\1 \2/p')"
gen="${speed%% *}"; prm="${speed##* }"
if [ -n "$speed" ] && [ "$gen" != "None" ]; then
  python3 - "$gen" "$prm" "$BASE_GEN" "$BASE_PROMPT" "$MIN_RATIO" <<'PY' && pass "tok/s within threshold (gen $gen vs $BASE_GEN, prompt $prm vs $BASE_PROMPT, min ratio $MIN_RATIO)" || fail "tok/s below ${MIN_RATIO}x baseline (gen $gen vs $BASE_GEN, prompt $prm vs $BASE_PROMPT); check AC power, performance profile and free memory before blaming the build"
import sys
gen, prm, bg, bp, ratio = (float(x) if x != "None" else 0.0 for x in sys.argv[1:6])
sys.exit(0 if gen >= ratio * bg and (prm >= ratio * bp or prm == 0.0) else 1)
PY
else
  warn "no timings in chat response; speed not checked"
fi

finish
