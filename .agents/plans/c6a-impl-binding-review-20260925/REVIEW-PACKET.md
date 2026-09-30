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
