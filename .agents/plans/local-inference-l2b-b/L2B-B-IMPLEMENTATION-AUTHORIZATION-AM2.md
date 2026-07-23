# Foundation B1 L2B-B Implementation Authorization Amendment 2

**Authorization ID:** `auth-local-inference-l2b-b-am2-20260722`

**Idempotency key:** `local-inference:l2b-b:am2:20260722:single-use`

**Status:** `PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS AND OWNER ACTIVATION`

**Acceptance lineage HEAD:** `90a55e06d653b4c7a7366f5880b3c30bd9ba0898`

**Required activation HEAD:** `60e47d9515a234e3179cf72e95f576e88dc4e047`

**Governing amendment:** `L2B-B-CANDIDATE-REVISION-AM2.md`, SHA-256
`97242dcd460d9cdd0275ab0aa6c4f246ca9283af0d0c15deeae8400ab0749328`

**Governing REQUEST_REVISION:** `L2B-B-CODEX-CANDIDATE-ACCEPTANCE.md`, SHA-256
`0b56d7d59ab50ce3496ee2cb0a7c2bc8e4762db7604fe8e4fc929feeffe87b5d`

## 1. Activation prerequisites

This record grants no authority while `PREPARED_ONLY`. Activation requires:

1. a fresh independent reviewer, distinct from the AM2 author and proposed implementer, to verify
   both governing hashes, current HEAD, every predecessor hash, the four-file ceiling, all stops and
   commands, and issue `VERDICT: PASS` bound to this authorization's exact raw SHA-256;
2. an owner activation record naming that reviewed SHA-256, the idempotency key,
   `codex-subagent-l2b-b-am2-implementer`, a non-retroactive start, and an expiry no more than 24
   hours later; and
3. successful repetition of the exact pre-write checks immediately before dispatch, before the first
   write, and after every pause.

The owner must explicitly accept the disclosed, candidate-disjoint HEAD advance from `90a55e06` to
`60e47d95`. Any later HEAD drift requires AM3; it cannot be waived inside this record.

## 2. Frozen subject and exact four-file correction lease

| State | Operation | Path | Required SHA-256 |
|---|---|---|---|
| WRITABLE | MODIFY | `scripts/ai/lib/local_inference_transport.py` | `6c28a4110966b326bfba30abf9c399a073a9f6079cd7f2843bf8345ecbce60be` |
| WRITABLE | MODIFY | `scripts/testing/test-local-inference-l2b.py` | `2af6ae699c322bc5701ba147b5ea8c2b744185a82ab6ee686508f8746099c495` |
| FROZEN | NO EDIT | `assets/dashboard.js` | `1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49` |
| FROZEN | NO EDIT | `config/schemas/local-inference-payload-v1.json` | `7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65` |
| WRITABLE | MODIFY | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | `fcee0b2d8faecc9854217f7491e9664eea8231d423adfc55a948b6bff3f65662` |
| WRITABLE | MODIFY | `dashboard/backend/api/routes/aistack.py` | `8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46` |

The exact AM2 write ceiling is four paths. The two frozen candidate paths remain part of the final
six-file acceptance subject but may not change. Any fifth AM2 write, path substitution, mode change,
move, deletion, symlink, foreign overlap, or frozen-byte change hard-stops immediately.

## 3. Exact grant

After valid activation, the named implementer may patch only the four writable paths to implement
the governing amendment exactly:

- recursively NFC-normalize string keys and values, reject non-string keys, and fail closed with
  `nfc_key_collision` before any normalized-key overwrite;
- scan normalized keys for forbidden credential fields and retain the bounded
  `REJECTED_SCHEMA_INVALID` envelope without sensitive detail;
- account known models using `max(caller_value, _KNOWN_MODEL_VRAM_GB[canonical_name])`, making
  concurrent `qwen3-35b` plus either known 8B model exceed 27 GB despite underreporting;
- make the golden fixture strict RFC 8259 JSON while constructing NaN and both infinities only in
  programmatic tests;
- forward only closed `payload_normalization_status` states (`pass`, `fail`, `unavailable`) through
  the existing backend default, validator, sanitizer and cache so the frozen dashboard row receives
  live fixture-health state; and
- preserve exactly 14 deterministic top-level L2B checks while adding assertions for nested NFC key
  normalization, collision refusal, underreported 35B+8B rejection, strict JSON, and sanitized
  backend/dashboard projection.

No live inference, model load, hardware probe, provider, network, DNS, socket, credential, secret,
database, service, browser, Nix, deployment, restart, traffic, route, poller, endpoint, store, writer,
queue, environment variable, port, URL, dependency, production subprocess, staging, commit,
delegation, deletion, or self-acceptance is authorized. Only the exact offline commands below may run.

## 4. Exact pre-write checks

```bash
test "$(git rev-parse HEAD)" = "60e47d9515a234e3179cf72e95f576e88dc4e047"
printf '%s  %s\n' \
  '6c28a4110966b326bfba30abf9c399a073a9f6079cd7f2843bf8345ecbce60be' 'scripts/ai/lib/local_inference_transport.py' \
  '2af6ae699c322bc5701ba147b5ea8c2b744185a82ab6ee686508f8746099c495' 'scripts/testing/test-local-inference-l2b.py' \
  '1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49' 'assets/dashboard.js' \
  '7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65' 'config/schemas/local-inference-payload-v1.json' \
  'fcee0b2d8faecc9854217f7491e9664eea8231d423adfc55a948b6bff3f65662' 'scripts/testing/fixtures/l2b_b_golden_payloads.json' \
  '8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46' 'dashboard/backend/api/routes/aistack.py' \
  '97242dcd460d9cdd0275ab0aa6c4f246ca9283af0d0c15deeae8400ab0749328' '.agents/plans/local-inference-l2b-b/L2B-B-CANDIDATE-REVISION-AM2.md' \
  '0b56d7d59ab50ce3496ee2cb0a7c2bc8e4762db7604fe8e4fc929feeffe87b5d' '.agents/plans/local-inference-l2b-b/L2B-B-CODEX-CANDIDATE-ACCEPTANCE.md' \
  | sha256sum -c -
test -z "$(git diff --cached --name-only -- scripts/ai/lib/local_inference_transport.py scripts/testing/test-local-inference-l2b.py assets/dashboard.js config/schemas/local-inference-payload-v1.json scripts/testing/fixtures/l2b_b_golden_payloads.json dashboard/backend/api/routes/aistack.py)"
```

## 5. Exact offline validation

```bash
python3 scripts/testing/test-local-inference-l2b.py
python3 -m py_compile scripts/ai/lib/local_inference_transport.py scripts/testing/test-local-inference-l2b.py dashboard/backend/api/routes/aistack.py
python3 - <<'PY'
import json
from pathlib import Path

for name in (
    "config/schemas/local-inference-payload-v1.json",
    "scripts/testing/fixtures/l2b_b_golden_payloads.json",
):
    text = Path(name).read_text(encoding="utf-8")
    json.loads(
        text,
        parse_constant=lambda token: (_ for _ in ()).throw(
            ValueError(f"non-RFC-8259 constant: {token}")
        ),
    )
PY
node --check assets/dashboard.js
git diff --check -- scripts/ai/lib/local_inference_transport.py scripts/testing/test-local-inference-l2b.py scripts/testing/fixtures/l2b_b_golden_payloads.json dashboard/backend/api/routes/aistack.py
if git diff --unified=0 -- scripts/ai/lib/local_inference_transport.py dashboard/backend/api/routes/aistack.py \
  | rg -n '^\+.*(socket|requests|urllib|httpx|aiohttp|subprocess|os\.system|Popen|https?://)'; then
  echo 'prohibited connectivity or production-process surface added' >&2
  exit 1
fi
```

The focused oracle must truthfully emit `PASS: 14 local-inference L2B checks`. No `aq-qa`, curl,
browser, service, provider, live endpoint, Tier-0, deploy, or restart command is permitted to the
implementer. Per ai-stack-qa, broader Phase/Tier-0 checks belong to the orchestrator only after
independent candidate PASS, because this lease is explicitly static/offline.

## 6. Single-use, replay, expiry and drift

- The first canonical dispatch/claim by the exact named identity consumes this idempotency key.
  Failure, cancellation, timeout, interruption or zero-write exit does not permit replay; further
  work requires AM3.
- First write consumes the grant regardless of completion or later verdict.
- No parallel, substitute, retroactive or resumed implementer is allowed. Identity substitution
  requires a new authorization and review.
- The active window must be positive and at most 24 hours. Expiry before any action, any pause, or
  completion hard-stops.
- Recheck identity, window, HEAD and all eight hashes before first write and after every pause. Any
  mismatch, staged candidate path, new foreign overlap, fifth path, or frozen-path drift suspends the
  grant without workaround.
- Completion freezes the exact six-file final candidate hashes. Review corrections require AM3;
  AM2 cannot reopen.

## 7. Candidate report and independent acceptance

The implementer stops without staging or committing and reports exact before/after hashes, four-path
diff inventory, all validation output, the 14/14 count, and explicit confirmation of untouched frozen
and foreign bytes plus no prohibited action.

A fresh reviewer from a different agent/session must independently bind all six final candidate
hashes, inspect the correction diff and frozen paths, rerun every offline validation, confirm the
four acceptance defects are closed, verify no scope/security/connectivity expansion, and end with:

`VERDICT: PASS — exact six-file L2B-B AM2 candidate satisfies all correction criteria`

Any `FAIL` or `REQUEST_REVISION` requires AM3. Only an independent PASS permits separately authorized
orchestrator Tier-0, staging and commit.

`RECORD: PREPARED_ONLY single-use four-file L2B-B AM2 correction lease; exact-subject review and
owner activation remain mandatory; no live, network, staging, commit or acceptance authority.`


## Owner Activation Record (reconciled 2026-07-23)
**Activation state: ACTIVATED** (record reconciled from the authoritative event ledger).
Owner activation recorded as a `pulse.append` in `.agents/events/*.jsonl` — subject `L2B-B-AM2`, event_id `067887d75ec140c0849f19d3c066d865`, ts `2026-07-22T16:41:56Z`. Any `PREPARED_ONLY / NOT ACTIVATED` status earlier in this record is a **stale header** predating the activation; the owner activation and any independently-accepted, committed candidate stand. Reconciled by fable-5 (no scope, ceiling, or hash change — header hygiene only).
