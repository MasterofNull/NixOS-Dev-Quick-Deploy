# Foundation B1 L2B-B AM5 Drift-Recovery Acceptance Authorization

**Prepared:** 2026-07-22T17:21:16Z

**Authorization ID:** `auth-local-inference-l2b-b-am5-drift-recovery-acceptance-20260722`

**Idempotency key:** `local-inference:l2b-b:am5:drift-recovery-acceptance:20260722:single-use`

**Status:** `PREPARED_ONLY/SUSPENDED — NON-DISPATCHABLE AND NON-ACTIVATABLE WHILE OWNER RECONCILIATION DIRECTIVE STANDS`

**Required activation HEAD:** `e5578e5c17fed4743ec8d49d62b4b0bc9fe2b2d4`

**Required reviewer:** `codex-subagent-l2b-b-am5-acceptance-reviewer`

**Recovery predecessor:** AM4 authorization SHA-256
`f68da0b24e149bd215400589cc5d08454a0dc31b1b583d9a188ca206e7f7a487`, independently reviewed
PASS at SHA-256 `e29b60e3321d17f1f2e0b1e3764a64be74ad416bf22ff2b0fda96f2648c905e4`.

## 1. Recovery finding and AM4 disposition

The AM4 implementer completed the exact four-path correction and all authorized offline validation.
The focused oracle passed 16/16. After validation and before acceptance, repository `HEAD` advanced
from AM4's authorized `99364942d42a31b33248abc8db7f840ee590c9b5` to
`e5578e5c17fed4743ec8d49d62b4b0bc9fe2b2d4`. AM4 correctly fail-stopped without staging or commit.

AM4 is consumed and non-replayable because its canonical dispatch and first writes occurred. Its
successful validation is evidence, not acceptance authority. AM4 may not be resumed, reactivated,
replayed, or used to accept, stage, or commit the candidate. This AM5 record authorizes no correction
and does not retroactively waive the AM4 stop.

At `2026-07-22T10:21:36-0700`, after this recovery need arose, the canonical PULSE ledger recorded an
owner `l2b-reconciliation-directive` that pauses the Codex L2B-B AM2-AM5 track and assigns the
stranded AM4 bytes to a Fable follow-up reconciliation slice. That later routing directive controls.
This AM5 draft is therefore suspended: it may not be reviewed, dispatched, claimed, activated, or
used for acceptance while that directive stands. A future owner decision must explicitly retire or
supersede the reconciliation directive before this exact draft could even be reconsidered; byte or
HEAD drift would instead require a newly numbered record.

The intervening range contains exactly two commits:

- `0ca93b2b77d45640f1996aa62c5b00a7ce597f63`, modifying only `.githooks/pre-commit`; and
- `e5578e5c17fed4743ec8d49d62b4b0bc9fe2b2d4`, modifying only the three VF-7 governance records,
  `config/schemas/aq-evidence-record-v1.json`, `scripts/governance/aq-evidence-collector.py`,
  `scripts/governance/tier0-validation-gate.sh`, and
  `scripts/testing/test-aq-evidence-collector.py`.

None is one of the six L2B-B subject paths. The HEAD drift is therefore disjoint, but disjointness
does not restore AM4. It only permits this fresh, exact-byte, acceptance-only recovery gate.

## 2. Frozen exact-byte subject

| State | Path | Required SHA-256 |
|---|---|---|
| CANDIDATE — READ ONLY | `scripts/ai/lib/local_inference_transport.py` | `e42fb5480385f791a8cd43bb94802499eddb5ef335ef0228d749a828d7130405` |
| CANDIDATE — READ ONLY | `scripts/testing/test-local-inference-l2b.py` | `79425baf3c58cf764c75a32fc597755618ac69377032d52d99d41295c69b4e82` |
| FROZEN — READ ONLY | `assets/dashboard.js` | `1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49` |
| FROZEN — READ ONLY | `config/schemas/local-inference-payload-v1.json` | `7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65` |
| CANDIDATE — READ ONLY | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | `a72c796368229865e7689a0069791d6f9789311992de7fbcdd85655a68307cd6` |
| CANDIDATE — READ ONLY | `dashboard/backend/api/routes/aistack.py` | `a5831eecf7b36cc178f72565a998836133e512e66c17d291e92fbc80cb28d8b6` |

All six paths must remain absent from the index and byte-exact at activation, claim, before each
validation command, and before verdict publication. No candidate or frozen-path write, staging,
mode change, move, deletion, symlink, substitution, or seventh subject path is permitted.

The only permitted write after valid activation is one new governance verdict at
`.agents/plans/local-inference-l2b-b/L2B-B-AM5-CODEX-ACCEPTANCE.md`. It must contain the exact HEAD,
all six hashes, reviewer identity, validation results, Service Coverage adjudication, and terminal
verdict. It is not a candidate path and must remain unstaged.

## 3. Activation contract

This record grants no authority while `PREPARED_ONLY/SUSPENDED`. It is not eligible for review or
activation while the owner reconciliation directive in Section 1 stands. Only after the owner
explicitly supersedes that routing directive could a fresh independent authorization reviewer,
distinct from this author, the AM4 implementer, and the required acceptance reviewer, bind a
PASS to this record's exact raw SHA-256. The owner must then activate that reviewed hash, exact HEAD,
idempotency key, only the required reviewer, a non-retroactive start, and a positive expiry no more
than 24 hours later.

At activation and claim there must be no live, queued, running, ambiguous, resumed, or overlapping
L2B-B implementer/reviewer task or authorization. Any identity, time, HEAD, hash, index, overlap, or
subject drift hard-stops without workaround. First canonical claim consumes this grant. Failure,
timeout, interruption, cancellation, abstention, zero-verdict exit, or non-PASS verdict is
non-replayable and requires a newly numbered authorization.

## 4. Exact acceptance criteria

The independent reviewer must inspect the unchanged candidate against the AM4 amendment and confirm:

1. recursive NFC key normalization and opaque rejection of non-string mapping keys remain intact;
2. NFC-equivalent key collisions are rejected before overwrite at every nesting depth with bounded
   reason code `nfc_key_collision`;
3. canonical known-model VRAM accounting uses a trusted floor and an underreported `qwen3-35b` plus
   known 8B model fails with `vram_budget_exceeded`;
4. the golden fixture is strict RFC 8259 JSON, while NaN and both infinities are constructed only in
   the Python oracle and normalize fail-closed;
5. closed `payload_normalization_status` values (`pass`, `fail`, `unavailable`) flow through backend
   default, extraction, validation, sanitized result, and cache to the existing frozen dashboard
   consumer; and
6. no provider, network, process-launch, credential, new endpoint, poller, store, writer, queue,
   environment-variable, port, URL, dependency, or live-runtime surface was introduced.

Criterion 5 is a mandatory Service Coverage and dashboard-parity blocker. An honest `unavailable`
default alone is insufficient if real normalized status is dropped. The reviewer must explicitly
record PASS or failure for this passthrough; it may not be waived or deferred.

## 5. Permitted read-only/static validation

Only the following focused offline commands are authorized after every precondition passes:

```bash
test "$(git rev-parse HEAD)" = "e5578e5c17fed4743ec8d49d62b4b0bc9fe2b2d4"
printf '%s  %s\n' \
  'e42fb5480385f791a8cd43bb94802499eddb5ef335ef0228d749a828d7130405' 'scripts/ai/lib/local_inference_transport.py' \
  '79425baf3c58cf764c75a32fc597755618ac69377032d52d99d41295c69b4e82' 'scripts/testing/test-local-inference-l2b.py' \
  '1e0287cd7b4c153bc57d832fda7cac434fc19ec799eaadb7b98cd3ea7808ea49' 'assets/dashboard.js' \
  '7ada7a6c61da4f6bea1c26e9809e60893fe019c0dc52fff0a12d8da28013fb65' 'config/schemas/local-inference-payload-v1.json' \
  'a72c796368229865e7689a0069791d6f9789311992de7fbcdd85655a68307cd6' 'scripts/testing/fixtures/l2b_b_golden_payloads.json' \
  'a5831eecf7b36cc178f72565a998836133e512e66c17d291e92fbc80cb28d8b6' 'dashboard/backend/api/routes/aistack.py' \
  | sha256sum -c -
git diff --cached --quiet -- scripts/ai/lib/local_inference_transport.py scripts/testing/test-local-inference-l2b.py assets/dashboard.js config/schemas/local-inference-payload-v1.json scripts/testing/fixtures/l2b_b_golden_payloads.json dashboard/backend/api/routes/aistack.py
python3 scripts/testing/test-local-inference-l2b.py
python3 -m py_compile scripts/ai/lib/local_inference_transport.py scripts/testing/test-local-inference-l2b.py dashboard/backend/api/routes/aistack.py
python3 - <<'PY'
import json
from pathlib import Path

for name in (
    "config/schemas/local-inference-payload-v1.json",
    "scripts/testing/fixtures/l2b_b_golden_payloads.json",
):
    json.loads(
        Path(name).read_text(encoding="utf-8"),
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

The focused oracle must pass 16/16. Static source inspection and read-only diff/hash commands are
permitted only for these criteria. No candidate correction, `aq-qa`, Tier-0, curl, browser, live
endpoint, provider/model invocation, hardware probe, network, DNS, socket, secret access, database,
service, production subprocess, Nix, deployment, restart, traffic, staging, commit, deletion,
archive, or delegation is authorized.

## 6. Verdict and next gate

PASS requires all criteria and commands to pass against the unchanged exact subject. The verdict
record must end exactly:

`VERDICT: PASS — exact six-file L2B-B AM5 candidate satisfies all correction and mandatory Service Coverage criteria`

Any defect, ambiguity, drift, or unavailable proof requires `REQUEST_REVISION` and a fresh grant;
the reviewer may not repair it. Even PASS authorizes no Tier-0, staging, commit, deployment, or live
action. Those remain a separate orchestrator/owner gate.

`RECORD: PREPARED_ONLY/SUSPENDED single-use exact-byte drift-recovery acceptance draft; the later
owner reconciliation directive makes it non-dispatchable and non-activatable; AM4 is consumed; no
review, acceptance, implementation, live, network, staging, commit, or deployment authority is granted.`
