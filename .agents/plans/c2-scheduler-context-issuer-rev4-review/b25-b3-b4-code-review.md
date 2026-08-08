# C2 Scheduler-Context Issuer — B2.5 / B3 / B4 Confirmatory Code Review (rev4)

Reviewer: fresh Claude Opus 4.8 flagship (Codex-substitute, Rule 18). NOT the author.
Scope: committed code only — `0bd67174` (B2.5), `ad5d95dd` (B3), `2c36e7d3` (B4).
Method: `git show` each commit, read live source, run all suites live. No speculative findings.

## Live suite results (all green)
| Suite | Result |
|-------|--------|
| test-capability-lease-gate.py | **83/83** |
| test-scheduler-context-issuer.py | **53/53** |
| test-scheduler-context-ledger.py | **32/32** |
| test-c2-gate-dispatch-wiring.py | **42/42** |
| test-c2-sci-service-coverage.py | **PASS** |
| test-local-inference-l2b.py (golden re-anchor witness) | **16/16** |

---

## 1. [HIGH] B3 FLAG-OFF BYTE-PARITY on the LIVE gate — VERIFIED

`capability_lease_gate.py`:
- `_scheduler_context_issuer_enabled()` (L625-626): `os.environ.get("CAPABILITY_SCHEDULER_CONTEXT_ISSUER","0")=="1"` — default OFF, unset OFF.
- Both ADMIT sites (candidate L791-799, first-party L849-857): the `decision` dict is built IDENTICALLY, then `scheduler_context` is added ONLY inside `if _scheduler_context_issuer_enabled():`. When OFF the block is skipped and `decisions.append(decision)` runs on an unmodified dict — **byte-identical, no `scheduler_context` key**.
- `_request_scheduler_context()` (L629-652): first statement is the flag guard returning `None` (L636-637) — **the `import scheduler_context_transport` (L642) is never reached when OFF**; no hot-path import.
- `_scheduler_correlation` (L740-742) is a pure `ctx.get(...)` dict-lookup defaulting to `{}` — computed unconditionally but no side effect and never read when OFF. Does not affect decision bytes.
- The live 83-assertion suite is **unmodified and 83/83** — the gate's own behavior contract is intact.

**L2B golden re-anchor is legitimate additive drift, not masking:** the diff is a SINGLE line — the `scripts/ai/lib/dispatch.py` sha256 anchor `1b083b10…` → `77ba0c25…`. `sha256sum scripts/ai/lib/dispatch.py` = `77ba0c25…` (matches). The dispatch-direct source-shape predicate `payload = build_llama_payload(` is intact (exactly 1 occurrence) and `test-local-inference-l2b.py` is 16/16. The anchor moved because B3 added the inert ingress adapter to dispatch.py — a real byte change to a file an unrelated drift-tripwire pins, correctly re-anchored.

## 2. [HIGH] B3 fail-closed + NON-BLOCKING outbound + INERT ingress — VERIFIED

- `_request_scheduler_context` returns `None` on every failure path: flag off (L636), socket unset (L638-640), transport import failure (L643-644), transport raise (L647-648), non-dict/`ok!=True` reply (L649-650), non-dict context (L651-652). Its result is read ONLY as `if minted is not None: decision["scheduler_context"]=minted` — it **never touches `admitted` or the ADMIT/DENY verdict** (that is decided by `_admission_verify` above). Never raises.
- `verify_ingress_scheduler_context` (dispatch.py L1180-1229) is a **total function**: outer `try/except` (L1198/L1228) returns `DENY_INGRESS_UNVERIFIED` on any exception; non-mapping rejected BEFORE any coercion (L1199-1200, no `dict(candidate)` on untrusted input); full fail-closed chain schema-tag (L1201) → Ed25519 sig via `verify_scheduler_context` (L1210) → audience `aq-f2.5-slot-queue` (L1214) → expiry (L1218) → epoch-stale (L1220), with the temporal checks in their own nested `try` that also DENIES (L1222-1225). `ok:True` returns a `dict(candidate)` copy only after the whole chain.
- **INERT**: `verify_ingress_scheduler_context` appears in dispatch.py ONLY as a comment (L1142) and its definition (L1180) — **no call site anywhere**; not spliced into `dispatch_task` (L1234) or `main` (L1478). `_load_scheduler_signer_keys_json` (L1165-1177) is fail-closed → `{}` deny-all sentinel on any read/parse/non-dict fault.

## 3. [HIGH] B2.5 durable ledger atomicity — VERIFIED

`scheduler_context_issuer.py::DurableSingleUseLedger.check_and_record` (L221-247):
- Atomic test-and-set is `os.open(path, O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0o600)` (L223-225) — a single kernel syscall; exactly one caller wins the create, all others get `FileExistsError` → `False` (L226-228). Holds across threads / processes / restart (decided by the filesystem, not process memory). Per-key path is `sha256("{lease_id}\x00{grant_digest}")` (L216-219).
- **No double-mint/fail-open window**: `True` is returned (L247) only AFTER the marker bytes fsync (L238) AND the containing-directory fsync (L241-245), so durability is committed before the caller proceeds to mint. A crash before those fsyncs means `True` was never returned → no context was minted → legitimate retry on restart. A crash after marker create but before fsync leaves the marker present → subsequent callers get EEXIST → over-denial, never a second mint.
- **Fail-closed**: `EEXIST` is the ONLY `False`. Every other `OSError` (EACCES, ENOSPC, dir gone) is deliberately NOT caught (L229-231) → propagates → caught by `mint_scheduler_context`'s `except: DENY_LEDGER_UNAVAILABLE` (issuer L398-401). Verified live: `keys_file_*` and `post-restart replay -> DENY_REPLAY` / `-> no context minted` assertions pass in the 32/32 ledger suite.

## 4. [MED] B4 coverage / dashboard / env-contract — VERIFIED

- `config/env-contract.yaml` L1317-1319: `CAPABILITY_SCHEDULER_CONTEXT_ISSUER` default `"0"`, layer all.
- Coverage test is **structural, not naive-substring**: parses YAML/JSON and asserts on parsed objects — default `=="0"` (L40), ≥1 `status=="active"` key (L54), public-only entries no private field (L55-56), and key-family disjointness `lease_ids.isdisjoint(c2_ids)` (L58-61), registry id membership (L92-93).
- Dashboard (`aistack.py` c2 section) is **low-cardinality**: emits only `signer_allowlist_active_keys` (a `sum(...)` COUNT), `signer_allowlist_revision`, `ledger_durable` (bool), `sci_on` (flag), `status` (`ok` iff not-on OR active-key AND durable-ledger). **No lease id / grant / prompt / path / signature / key material** in the payload.
- Committed `config/aqos/c6-scheduler-signer-keys.json`: 1 key, active, fields `{key_id, ed25519_public_key, status}` — **public-only, no private/secret/`d` field**, distinct family from lease-signer.

## 5. Fail-open / byte-parity / downgrade / oracle / activation footguns

- No fail-open found. Every failure across the three subslices denies (issuer: typed `_deny`; gate outbound: `None`→no context; ingress: `DENY_INGRESS_*`; ledger: propagate→`DENY_LEDGER_UNAVAILABLE`).
- No byte-parity break on the live gate (§1). No signature/verify downgrade — ingress requires the full Ed25519 chain before `ok`; the gate holds no signing key (relay only); signer files are public-only.
- No oracle: deny reasons are coarse typed constants; dashboard is low-cardinality counts.

### Advisory (LOW, non-blocking) — ledger burns slot before signer-availability check
`mint_scheduler_context` (issuer L395-408) calls `ledger.check_and_record` (step 4, L399) BEFORE the `private_key_bytes` signer-availability guard (step 5, L407-408). A transient signer outage therefore permanently burns a legitimate lease's single-use slot and then denies `DENY_SIGNER_UNAVAILABLE`; that lease can never mint even after the signer recovers, absent the documented operator marker-file reset. This is strictly **fail-CLOSED (over-denial), never fail-open** — no security gap — but reordering the signer-availability check ahead of the ledger burn would avoid burning slots on a recoverable outage. Advisory only; the service is default-OFF and inert. Suggest a bounded follow-up, not a revision blocker.

---

VERDICT: PASS
