# A2A task for antigravity — round 'c6a-impl-binding-review-20260925'

Dropped: 2026-09-26T01:37:48Z

Respond by writing `.agents/plans/c6a-impl-binding-review-20260925/antigravity.md`.

## SCOPE & STOP (HARD — read before writing)
- Edit ONLY the files this task names as surfaces. A related-looking file is still out of scope.
- NEVER implement a data/config change as a filesystem shortcut: no symlink, bind mount, mount,
  chmod/chown/rm on tracked or runtime paths. 'Single source of truth' = a resolver in code,
  never one directory replacing/redirecting another.
- NO DELETE — archive to a timestamped path; never rm/rmdir.
- If this task references an authorization/round: confirm it still reads AUTHORIZED and (where a
  package root is named) that `aq-package-freeze verify` exits 0 BEFORE writing. If suspended,
  STOP — do not recreate or continue suspended files.
- Undeclared dependency discovered -> STOP and report; do not expand scope to 'make it work'.
- Budgets/acceptance criteria are hard facts: a measured violation FAILS; a sentence calling it
  'acceptable' does not change the number. Report the real value.
- Write ONLY your own named output file. Do NOT edit shared files. Do NOT commit.
- When unsure whether something is in scope: it is not. Report, do not act.

COLLABORATIVE ROUND 'c6a-impl-binding-review-20260925'.
=== REVIEW ARTIFACT (.agents/plans/c6a-impl-binding-review-20260925/REVIEW-PACKET.md) — INLINED; do NOT read the file ===
# C6a implementation binding-review packet

Subject: `1160f18f1da74a0ab474b4cb0dc7cf1844cf574e` (`factory/c6a-impl`)
Parent: `99fd115f7194729640e9970bed8da37060fcff74` (merged C6-S / PR #345)
Author lane: Claude Sonnet 5 implementer
Review posture: read-only; default OFF; no activation, restart, deploy, or owner act.

This packet is the bounded common evidence slice for every model lane. It is not a substitute for
full-diff inspection by lanes with enough context. Judge the same expert-team baseline: security
architecture, systems correctness, adversarial concurrency/crash safety, service coverage, and
operator observability.

## Frozen obligations

1. Only the dedicated C6-S launch socket gains `authorize_launch` and `consume_launch`; the control
   socket and C6d recovery/bump contracts retain byte/API parity.
2. Both launch operations deny before dispatch unless `SO_PEERCRED.uid` equals the resolved TEG uid.
   Empty/unparseable uid denies every peer, including the authority service uid. C6b must later
   provision a TEG uid distinct from the authority uid.
3. Authorization binds a 256-bit nonce to context digest, task id/revision, current epoch, gateway
   instance, millisecond issuance time, and a deadline no greater than 250 ms.
4. Authorization, consumption, bump, and recovery serialize through the same `epoch.lock` inode.
5. Consumption is exactly-once via durable `O_CREAT|O_EXCL|O_NOFOLLOW`, file fsync, and directory
   fsync. Binding mismatch, expiry, epoch supersession, malformed state, and duplicate consumption
   are typed fail-closed denials.
6. Restart recovery unconditionally moves every surviving issued-without-consumed record to expired
   before either socket listens; it must not depend on elapsed wall time.
7. Nix declares authority-owned `0700` launch-ledger directories; `launchTegUid` defaults empty;
   service remains disabled. QA and dashboard surfaces expose integration state.

## Key implementation evidence

`revocation_epoch.py`:

```python
lock_fd = _acquire_epoch_lock(epoch_path_p)
current_epoch = read_epoch(epoch_path_p)
record = {
    "nonce": secrets.token_hex(32),
    "context_digest": data["context_digest"],
    "task_id": data["task_id"],
    "task_revision": data["task_revision"],
    "epoch": current_epoch,
    "gateway_instance": data["gateway_instance"],
    "issued_at": _iso_ms(moment),
    "deadline_ms": LAUNCH_TOKEN_DEADLINE_MS,
}
created = _create_exclusive_json(issued_dir / nonce, record, 0o640)
```

Consumption takes the same lock, loads `issued/<nonce>`, compares the full binding, rejects when
`moment > issued_at + timedelta(milliseconds=deadline_ms)`, rereads the epoch under lock, and then:

```python
created = _create_exclusive_json(consumed_dir / nonce, receipt, 0o640)
if not created:
    return _consume_launch_deny(DENY_LAUNCH_ALREADY_CONSUMED)
```

`recover_launch_ledger()` takes the same lock and, without reading the clock or token deadline,
creates `expired/<nonce>` exclusively, fsyncs it, unlinks `issued/<nonce>`, and fsyncs the issued
directory. It runs after C6d `recover()` and before `serve_multi()` binds/listens.

`revocation_epoch_transport.py`:

```python
teg_uid = _resolve_teg_uid(os.environ.get("AQ_REVOCATION_LAUNCH_TEG_UID", ""))
if teg_uid is None or peer_creds is None or peer_creds[1] != teg_uid:
    if op == "authorize_launch":
        return {"ok": False, "reason": re_lib.DENY_NOT_TEG_PEER,
                "detail": "", "token": None}
    return _deny(re_lib.DENY_NOT_TEG_PEER)
if op == "authorize_launch":
    return re_lib.authorize_launch(fields, epoch_path)
if op == "consume_launch":
    return re_lib.consume_launch(fields, epoch_path)
return _deny(DENY_LAUNCH_OP_UNKNOWN)
```

Nix adds `launchTegUid` as `types.str` with `default = ""`, passes it only as
`AQ_REVOCATION_LAUNCH_TEG_UID`, and declares launch-ledger root/issued/consumed/expired at `0700`.
The enclosing module remains `mkIf cfg.enable`, whose existing default is OFF.

## Claimed deterministic evidence to independently verify

- Commit diff: 12 files, 1099 insertions, 32 deletions.
- `python3 scripts/testing/test-revocation-epoch.py`: 173/173.
- Live dual-UDS service coverage: empty TEG uid denies; matching fixture uid issues once, consumes
  once, duplicate denies; expiry and epoch-supersession deny.
- New registered check: `0.10.53 c6a-authorize-launch-coverage` on both QA engines.
- Python AST parsing, registry JSON load, Nix parse, and focused pre-commit CI passed in implementer
  evidence; reviewers must report which checks they reran rather than inheriting the claim.

## Required review output

State the exact subject hash reviewed; list commands/results; report findings by severity with
path:line evidence; explicitly address all seven obligations. End with exactly one terminal
disposition: `ACCEPTED`, `IMPLEMENTED_FOLLOWUP_REQUIRED`, `ACTIVATION_BLOCKED`, or `REJECTED`.

=== END ARTIFACT ===

TASK:
READ-ONLY independent binding review of C6a implementation commit 1160f18f1da74a0ab474b4cb0dc7cf1844cf574e on branch factory/c6a-impl. Apply the same expert-team baseline: security architect, systems implementer, adversarial reviewer, and service-coverage operator. Treat the inlined packet as the common bounded evidence slice. Lanes with repository tooling must additionally inspect the full commit diff and run relevant tests in isolation; the local leaf lane must judge only the inlined packet and clearly bound its confidence. Verify frozen scope, TEG uid SO_PEERCRED fail-closed behavior, authority-user exclusion, durable single-use issuance and consume, shared-lock ordering versus apply_bump, unconditional recovery before listen, typed total denials, control-socket and C6d parity, Nix default-off safety, QA coverage, dashboard observability, and no activation. Output exact subject hash, validations, findings with severity and path-line evidence, and exactly one terminal disposition: ACCEPTED, IMPLEMENTED_FOLLOWUP_REQUIRED, ACTIVATION_BLOCKED, or REJECTED. Do not edit implementation files, stage, commit, activate, restart, deploy, or change runtime state.

Write your contribution to YOUR OWN file ONLY: .agents/plans/c6a-impl-binding-review-20260925/<AGENT>.md (<AGENT> = codex | local | antigravity). Do NOT edit any shared file. Do NOT read the artifact file (it is inlined above). Be decisive and concise.
