# Foundation B1 L2B-B Implementation Authorization Amendment 4

**Authorization ID:** `auth-local-inference-l2b-b-am4-20260722`

**Idempotency key:** `local-inference:l2b-b:am4:20260722:single-use`

**Status:** `PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS AND OWNER ACTIVATION`

**Required activation HEAD:** `99364942d42a31b33248abc8db7f840ee590c9b5`

**Required implementer:** `codex-subagent-l2b-b-am4-implementer`

**Governing amendment:** `L2B-B-CANDIDATE-REVISION-AM4.md`, SHA-256
`539ebd85c0e94da0097cdb779fd2df3f4400d8785082540faf55d781c82cf735`

**Governing acceptance:** `L2B-B-NARROW-REVISION-CODEX-ACCEPTANCE.md`, SHA-256
`97e68a7c7ee96750deb669f2168e7e67bd514881a3f78e56544b3e567b8bfb6a`

## 1. Activation prerequisites and supersession

This record grants no authority while `PREPARED_ONLY`. Fresh independent review by an agent/session
distinct from the author and implementer must bind a PASS to this authorization's exact raw SHA-256.
The owner must then name that reviewed hash, this idempotency key, exact HEAD, exact implementer, a
non-retroactive start, and a positive expiry no more than 24 hours later.

The activation statement must explicitly supersede and void for all future use consumed AM2
`d5e78b793df0767399a8559d77360c84cecc8225f67880518adf5d22a961d593`, completed conflicting
grant `1b043066ffe785f1be6e1934fcd6d7d7b50d9e24b17e416d7946ea74f16a8391`, and invalidated AM3
`951c9f9dfde931f7349ae7c817874ee6889b76b26ac396f87e5752a3b72ced6f`.

No external L2B process, task, intent, grant, or implementer may be live, queued, running, ambiguous,
or overlapping at activation, dispatch, first write, or after any pause.

## 2. Exact subject and four-file ceiling

| State | Operation | Path | Required SHA-256 |
|---|---|---|---|
| WRITABLE | MODIFY | `scripts/ai/lib/local_inference_transport.py` | `39ee836f2eb595e877dd29bba15f7ac955ab2a6aa24639c87aca6ae1a27b2866` |
| WRITABLE | MODIFY | `scripts/testing/test-local-inference-l2b.py` | `33ab4d84e642873ddc4a5fa2b8488c157f221550340366a8bdc04cfa0250319d` |
| FROZEN | NO EDIT | `assets/dashboard.js` | `1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49` |
| FROZEN | NO EDIT | `config/schemas/local-inference-payload-v1.json` | `7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65` |
| WRITABLE | MODIFY | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | `fcee0b2d8faecc9854217f7491e9664eea8231d423adfc55a948b6bff3f65662` |
| WRITABLE | MODIFY | `dashboard/backend/api/routes/aistack.py` | `8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46` |

All six L2B candidate paths must remain absent from the index. Staged L2B governance records and
disjoint VF-7 paths may remain only when an exact staged-name inventory proves no overlap with these
six paths. Foreign staged bytes must be preserved and cannot be modified, unstaged, reverted,
included, or attributed to AM4. Any fifth write, substitution, mode change, move, deletion, symlink,
frozen drift, candidate staging, or overlap hard-stops.

## 3. Exact grant

Only after valid activation, the named implementer may patch the four writable paths to preserve
the accepted NFC key normalization and opaque non-string-key rejection while:

- rejecting NFC-equivalent key collisions before overwrite at every depth with bounded reason code
  `nfc_key_collision`;
- applying trusted canonical known-model VRAM floors via
  `max(valid_caller_value, _KNOWN_MODEL_VRAM_GB[canonical_name])`;
- converting the fixture to strict RFC 8259 JSON and constructing non-finite floats only inside the
  Python oracle; and
- forwarding closed `payload_normalization_status` values through the existing backend projection
  and cache for the frozen dashboard consumer.

No live inference, provider, model load, hardware probe, network, DNS, socket, credential, secret,
database, service, browser, Nix, deployment, restart, traffic, new route/endpoint/poller, store,
writer, queue, environment variable, port, URL, dependency, production subprocess, staging, commit,
deletion, delegation, or self-acceptance is authorized.

## 4. Exact pre-write checks

```bash
test "$(git rev-parse HEAD)" = "99364942d42a31b33248abc8db7f840ee590c9b5"
printf '%s  %s\n' \
  '39ee836f2eb595e877dd29bba15f7ac955ab2a6aa24639c87aca6ae1a27b2866' 'scripts/ai/lib/local_inference_transport.py' \
  '33ab4d84e642873ddc4a5fa2b8488c157f221550340366a8bdc04cfa0250319d' 'scripts/testing/test-local-inference-l2b.py' \
  '1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49' 'assets/dashboard.js' \
  '7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65' 'config/schemas/local-inference-payload-v1.json' \
  'fcee0b2d8faecc9854217f7491e9664eea8231d423adfc55a948b6bff3f65662' 'scripts/testing/fixtures/l2b_b_golden_payloads.json' \
  '8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46' 'dashboard/backend/api/routes/aistack.py' \
  '539ebd85c0e94da0097cdb779fd2df3f4400d8785082540faf55d781c82cf735' '.agents/plans/local-inference-l2b-b/L2B-B-CANDIDATE-REVISION-AM4.md' \
  '97e68a7c7ee96750deb669f2168e7e67bd514881a3f78e56544b3e567b8bfb6a' '.agents/plans/local-inference-l2b-b/L2B-B-NARROW-REVISION-CODEX-ACCEPTANCE.md' \
  'd5e78b793df0767399a8559d77360c84cecc8225f67880518adf5d22a961d593' '.agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION-AM2.md' \
  '1b043066ffe785f1be6e1934fcd6d7d7b50d9e24b17e416d7946ea74f16a8391' '.agents/plans/local-inference-l2b-b/L2B-B-REVISION-AUTHORIZATION.md' \
  '951c9f9dfde931f7349ae7c817874ee6889b76b26ac396f87e5752a3b72ced6f' '.agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION-AM3.md' \
  | sha256sum -c -
git diff --cached --quiet -- scripts/ai/lib/local_inference_transport.py scripts/testing/test-local-inference-l2b.py assets/dashboard.js config/schemas/local-inference-payload-v1.json scripts/testing/fixtures/l2b_b_golden_payloads.json dashboard/backend/api/routes/aistack.py
```

The orchestrator must also inventory staged names and prove every remaining staged path is a
governance record or disjoint VF-7 path. Repeat all checks before dispatch, before first write, and
after every pause.

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

The focused oracle must retain the 16 accepted checks and cover collision refusal, underreported
VRAM, strict non-finite handling, and backend/dashboard projection. No `aq-qa`, curl, browser,
service, provider, live endpoint, Tier-0, deploy, restart, staging, or commit command is permitted.

## 6. Single-use, drift, overlap, and acceptance

- First canonical dispatch or claim consumes the key. Failure, timeout, interruption, cancellation,
  or zero-write exit is non-replayable and requires AM5. First write also consumes the grant.
- No parallel, substitute, retroactive, resumed, or overlapping implementer is allowed.
- Expiry, identity mismatch, HEAD/hash/index drift, candidate staging, new process/task/intent/grant,
  fifth path, frozen drift, or overlap suspends the grant without workaround.
- Completion freezes all six final hashes. The implementer stops without staging or committing and
  reports before/after hashes, four-path diff inventory, full validation output, untouched frozen
  and foreign bytes, and absence of prohibited action.
- A fresh different agent/session must independently bind all final hashes, rerun Section 5,
  confirm both accepted partial fixes remain intact and all four remaining defects are closed, and
  end with `VERDICT: PASS — exact six-file L2B-B AM4 candidate satisfies all correction criteria`.
  Any other verdict requires AM5. Tier-0, staging, and commit remain separately authorized.

`RECORD: PREPARED_ONLY single-use four-file L2B-B AM4 correction lease; exact-subject review and
owner activation remain mandatory; no live, network, staging, commit, or acceptance authority.`


## Owner Activation Record (reconciled 2026-07-23)
**Activation state: ACTIVATED** (record reconciled from the authoritative event ledger).
Owner activation recorded as a `pulse.append` in `.agents/events/*.jsonl` — subject `L2B-B-AM4`, event_id `018d47a6a02f43d68d69eccdb7e7f133`, ts `2026-07-22T17:12:49Z`. Any `PREPARED_ONLY / NOT ACTIVATED` status earlier in this record is a **stale header** predating the activation; the owner activation and any independently-accepted, committed candidate stand. Reconciled by fable-5 (no scope, ceiling, or hash change — header hygiene only).
