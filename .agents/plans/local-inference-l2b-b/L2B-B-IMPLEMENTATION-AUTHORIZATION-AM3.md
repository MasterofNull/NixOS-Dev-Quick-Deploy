# Foundation B1 L2B-B Implementation Authorization Amendment 3

**Authorization ID:** `auth-local-inference-l2b-b-am3-20260722`

**Idempotency key:** `local-inference:l2b-b:am3:20260722:single-use`

**Status:** `PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS AND OWNER ACTIVATION`

**Required activation HEAD:** `60e47d9515a234e3179cf72e95f576e88dc4e047`

**Required implementer:** `codex-subagent-l2b-b-am3-implementer`

**Governing amendment:** `L2B-B-CANDIDATE-REVISION-AM3.md`, SHA-256
`c5b317bbacde93e20b07bcbc8b2f3fb3f4a0e560e483abd8a3f44a7381211f8e`

**Governing REQUEST_REVISION:** `L2B-B-CODEX-CANDIDATE-ACCEPTANCE.md`, SHA-256
`0b56d7d59ab50ce3496ee2cb0a7c2bc8e4762db7604fe8e4fc929feeffe87b5d`

## 1. Mandatory supersession and activation prerequisites

This record grants no authority while `PREPARED_ONLY`. A valid owner activation must name this
authorization's independently reviewed raw SHA-256, its idempotency key, exact HEAD, exact required
implementer, a non-retroactive start, and an expiry no more than 24 hours later.

The same owner statement must explicitly supersede and void for all future claim, dispatch, write,
resume, staging, and acceptance both:

1. consumed AM2 SHA-256
   `d5e78b793df0767399a8559d77360c84cecc8225f67880518adf5d22a961d593`; and
2. conflicting narrow grant SHA-256
   `1b043066ffe785f1be6e1934fcd6d7d7b50d9e24b17e416d7946ea74f16a8391`.

Before activation, a fresh independent reviewer, distinct from the AM3 author and proposed
implementer, must verify the amendment and authorization raw hashes, every bound hash and event,
the exact four-file ceiling, the frozen paths, all stop conditions, and every command, then issue an
explicit PASS bound to this authorization's raw SHA-256.

Before activation and dispatch, the owner/orchestrator must confirm no external L2B process or live
delegation-registry task exists and must make projected intent `l2b-b-rev-20260722` terminal. Any
live, queued, running, ambiguous, or newly appearing overlapping L2B process, task, intent, or grant
hard-stops. Repeat all checks immediately before dispatch, before first write, and after every pause.

## 2. Exact frozen subject and four-file correction lease

| State | Operation | Path | Required SHA-256 |
|---|---|---|---|
| WRITABLE | MODIFY | `scripts/ai/lib/local_inference_transport.py` | `6c28a4110966b326bfba30abf9c399a073a9f6079cd7f2843bf8345ecbce60be` |
| WRITABLE | MODIFY | `scripts/testing/test-local-inference-l2b.py` | `2af6ae699c322bc5701ba147b5ea8c2b744185a82ab6ee686508f8746099c495` |
| FROZEN | NO EDIT | `assets/dashboard.js` | `1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49` |
| FROZEN | NO EDIT | `config/schemas/local-inference-payload-v1.json` | `7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65` |
| WRITABLE | MODIFY | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | `fcee0b2d8faecc9854217f7491e9664eea8231d423adfc55a948b6bff3f65662` |
| WRITABLE | MODIFY | `dashboard/backend/api/routes/aistack.py` | `8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46` |

The exact write ceiling is four paths. The dashboard consumer and payload schema are part of the
six-file final acceptance subject but remain frozen. Any fifth write, path substitution, mode
change, move, deletion, symlink, frozen-byte change, staged candidate path, or foreign overlap
hard-stops immediately.

## 3. Exact grant and exclusions

After valid activation, only the named implementer may patch only the four writable paths to:

- recursively NFC-normalize string keys and values, reject non-string keys, detect normalized-key
  collisions before overwrite, scan normalized keys for forbidden credentials, and retain the
  bounded `REJECTED_SCHEMA_INVALID` envelope;
- enforce trusted known-model VRAM floors using
  `max(valid_caller_value, _KNOWN_MODEL_VRAM_GB[canonical_name])`, making `qwen3-35b` plus either
  known 8B model exceed 27 GB under caller underreporting;
- make the golden fixture strict RFC 8259 JSON while keeping NaN and both infinities covered only
  through Python-created values;
- sanitize and forward only closed `payload_normalization_status` values through the existing
  backend default, validator, result, and cache; and
- preserve exactly 14 deterministic top-level focused checks while adding assertions for nested
  NFC keys, collision refusal, underreported 35B+8B rejection, strict JSON, and backend/dashboard
  projection.

No live inference, model load, hardware probe, provider, network, DNS, socket, credential, secret,
database, service, browser, Nix, deployment, restart, traffic, route, poller, endpoint, store,
writer, queue, environment variable, port, URL, dependency, production subprocess, staging, commit,
delegation, deletion, or self-acceptance is authorized. Only the exact offline commands in Section 5
may run after an authorized write.

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
  'c5b317bbacde93e20b07bcbc8b2f3fb3f4a0e560e483abd8a3f44a7381211f8e' '.agents/plans/local-inference-l2b-b/L2B-B-CANDIDATE-REVISION-AM3.md' \
  '97242dcd460d9cdd0275ab0aa6c4f246ca9283af0d0c15deeae8400ab0749328' '.agents/plans/local-inference-l2b-b/L2B-B-CANDIDATE-REVISION-AM2.md' \
  'd5e78b793df0767399a8559d77360c84cecc8225f67880518adf5d22a961d593' '.agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION-AM2.md' \
  '8863ec8748cee97fb077fe790aaf64c6be649a64634c1cb76c2058e868e357fd' '.agents/plans/local-inference-l2b-b/L2B-B-AM2-AUTHORIZATION-REVIEW.md' \
  '1b043066ffe785f1be6e1934fcd6d7d7b50d9e24b17e416d7946ea74f16a8391' '.agents/plans/local-inference-l2b-b/L2B-B-REVISION-AUTHORIZATION.md' \
  '0b56d7d59ab50ce3496ee2cb0a7c2bc8e4762db7604fe8e4fc929feeffe87b5d' '.agents/plans/local-inference-l2b-b/L2B-B-CODEX-CANDIDATE-ACCEPTANCE.md' \
  | sha256sum -c -
test -z "$(git diff --cached --name-only -- scripts/ai/lib/local_inference_transport.py scripts/testing/test-local-inference-l2b.py assets/dashboard.js config/schemas/local-inference-payload-v1.json scripts/testing/fixtures/l2b_b_golden_payloads.json dashboard/backend/api/routes/aistack.py)"
```

The owner/orchestrator must separately verify that events `067887d75ec140c0849f19d3c066d865`,
`6b738ae183f341dc8d6ae386ff6981cb`, and `8f3d4e81ead0446993941a857852e094`
remain present with their original activation, conflicting activation, and zero-write stop payloads.
Any mismatch or ambiguity hard-stops.

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
browser, service, provider, live endpoint, Tier-0, deploy, restart, staging, or commit command is
permitted to the implementer.

## 6. Single-use, expiry, drift, and overlap controls

- The first canonical dispatch or claim by the exact named identity consumes the idempotency key.
  Failure, cancellation, timeout, interruption, or zero-write exit does not permit replay; further
  work requires AM4.
- First write consumes the grant regardless of completion or later verdict.
- No parallel, substitute, retroactive, resumed, or overlapping implementer is allowed. Identity
  substitution requires a new authorization and review.
- The active window must be positive and no longer than 24 hours. Expiry before action, after any
  pause, or before completion hard-stops.
- Recheck identity, window, HEAD, all bound hashes, staged state, process/task state, and overlap
  immediately before dispatch, before first write, and after every pause. Any mismatch, stale
  running intent, new grant, new task/process, foreign overlap, fifth path, or frozen drift suspends
  the grant without workaround.
- Completion freezes the exact six-file candidate hashes. Review corrections require AM4; AM3
  cannot reopen.

## 7. Candidate report and independent acceptance

The implementer stops without staging or committing and reports exact before/after hashes, the
four-path diff inventory, complete validation output, the 14/14 count, and explicit confirmation of
untouched frozen and foreign bytes plus no prohibited action.

A fresh reviewer from a different agent/session must independently bind all six final hashes,
inspect the correction diff and frozen paths, rerun every Section 5 command, confirm all four
REQUEST_REVISION defects are closed, verify no scope/security/connectivity expansion, and end with:

`VERDICT: PASS — exact six-file L2B-B AM3 candidate satisfies all correction criteria`

Any `FAIL` or `REQUEST_REVISION` requires AM4. Only an independent PASS permits separately
authorized orchestrator Tier-0, staging, and commit.

`RECORD: PREPARED_ONLY single-use four-file L2B-B AM3 correction lease; exact-subject review and
owner activation remain mandatory; no live, network, staging, commit, or acceptance authority.`
