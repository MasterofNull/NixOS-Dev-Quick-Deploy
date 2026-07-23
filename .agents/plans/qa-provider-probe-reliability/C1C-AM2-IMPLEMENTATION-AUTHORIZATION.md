# QPPR-C1C Amendment 2 implementation authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-c1c-am2-20260719`  
**Idempotency key:** `qa-provider-probe-reliability:c1c:am2:observable-fail-stop:20260719`  
**Required implementer:** `codex-subagent-qppr-c1c-am1-implementer`  
**Required implementer identity SHA-256:** `40ae41866aa866e85656b6f682ef01367a51a867d234007887aa49eba82f5873`  
**Status:** **PREPARED_ONLY / OWNER SRE RATIFICATION REQUIRED — NOT ACTIVATED**  
**Single use:** consumed by the first complete exact two-file candidate report after valid activation

## Exact binding and ceiling

| Subject | SHA-256 |
|---|---|
| C1C-AM2 amendment | `02f4c5317faa80aac7d2872d04eafa8cf5337c9297f1a335fe737160d06e8dfc` |
| C1C-AM2 blocking review | `520fdcaccf7b19ded8ab061a4f0f6bfdf6ac3d2772c425ccfcc2487e5aa3c19d` |
| process-owner predecessor | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` |
| lifecycle-test predecessor | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` |
| frozen observer test | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` |

The ceiling is exactly those two MODIFY paths. Any third path, substitution, byte drift, identity
drift, expired window, or replay after consumption hard-stops without workaround.

## Exact grant and validation

After independent design/auth `PASS`, explicit owner SRE ratification, and valid owner activation,
only the required implementer may add the observable publication-status pipe, pure authoritative
classifier, fail-stop late-return handling, and deterministic tests exactly as frozen.

Exact required commands:

```bash
python3 scripts/testing/test-qa-provider-probe-lifecycle.py
python3 scripts/testing/test-qa-provider-probe-observer.py
python3 -m py_compile scripts/testing/harness_qa/core/process_lifecycle.py scripts/testing/test-qa-provider-probe-lifecycle.py
sha256sum scripts/testing/test-qa-provider-probe-observer.py
git diff --check -- scripts/testing/harness_qa/core/process_lifecycle.py scripts/testing/test-qa-provider-probe-lifecycle.py
rg -n 'shell=True|os\.system|https?://|BEGIN (RSA|OPENSSH) PRIVATE KEY|Bearer [A-Za-z0-9]' scripts/testing/harness_qa/core/process_lifecycle.py scripts/testing/test-qa-provider-probe-lifecycle.py
```

The observer hash must match above; `rg` must return no matches. Only after exact independent
candidate `PASS` may the orchestrator run
`scripts/governance/tier0-validation-gate.sh --pre-commit`, stage, and commit.

## Activation, replay, and exclusions

Owner activation must state this authorization's exact SHA-256, repeat required implementer and its
identity hash, explicitly ratify the no-finite-redelivery SRE exception for non/late-return callback
violations, and provide activation and expiry timestamps no more than 24 hours apart. Activation
before independent review, after expiry, for another identity/hash, or without exact ratification is
invalid. The first complete exact two-file report atomically consumes the idempotency key; later
reports or activation replay cannot authorize edits and require fresh reviewed bytes.

The implementer cannot delegate, stage, commit, deploy, delete, or self-accept. Control-plane
session/intent/resume/pulse/handoff/registry evidence contains no product code and is not staged.
No provider/live/network/heartbeat/evidence/Phase-0/A1/A2/API/browser/Nix/service/deploy/traffic/
rollback action is authorized.

A1-AM3 four-file recovery remains NON-ACTIVATABLE pending C1C-AM2 acceptance/commit and final exact
rebind. A2 remains blocked.

`RECORD: PREPARED_ONLY / SINGLE USE. Implementation and all live actions remain unauthorized.`


## Owner Activation Record (reconciled 2026-07-23)
**Activation state: ACTIVATED** (record reconciled from the authoritative event ledger).
Owner activation recorded as a `pulse.append` in `.agents/events/*.jsonl` — subject `auth-qa-provider-probe-reliability-c1c-am2-20260719`, event_id `a0ffc92911844ec7963762a60d5848e2`, ts `2026-07-19T03:39:01Z`. Any `PREPARED_ONLY / NOT ACTIVATED` status earlier in this record is a **stale header** predating the activation; the owner activation and any independently-accepted, committed candidate stand. Reconciled by fable-5 (no scope, ceiling, or hash change — header hygiene only).
