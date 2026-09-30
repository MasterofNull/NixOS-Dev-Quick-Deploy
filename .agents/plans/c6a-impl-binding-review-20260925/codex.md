# Codex independent binding review

Subject: `1160f18f1da74a0ab474b4cb0dc7cf1844cf574e` (factory/c6a-impl). Parent: `99fd115f7194729640e9970bed8da37060fcff74`.

Reviewed the full 12-file diff and relevant surrounding implementations against the inlined packet. Tests ran against a `git archive` snapshot in `/tmp/c6a-codex-review-ltv257c6`, not the parent checked out in this worktree. No implementation edits, staging, commit, activation, service restart, deployment, or owner act. This contribution is the only repository write; shared workflow logs were excluded by the task's explicit own-file-only rule.

## Findings

1. **HIGH — malformed persisted tokens can authorize consumption.** `scripts/ai/lib/revocation_epoch.py:1463`, `:1471`, `:1485`: stored records are only checked as mappings; stored nonce is never compared, Python equality accepts boolean revisions as integers, and the deadline check omits the 250 ms maximum. In isolated fixtures, changing an issued record to `deadline_ms=10000` allowed consumption at issuance +1000 ms; replacing its internal nonce also succeeded; changing revision 1 to `true` succeeded and returned a boolean revision in the receipt. This violates the explicit malformed-state fail-closed obligation, irrespective of the ledger's restricted write access. Validate the complete persisted schema, exact types, nonce/path identity, and deadline bound before using it; add these negative tests.

2. **HIGH — elapsed lifetime is not bounded across backward clock steps.** `scripts/ai/lib/revocation_epoch.py:1487`: freshness uses only wall-clock upper-bound comparison. With an otherwise untouched issued token, consuming at `issued_at - 1000 ms` returned success. This deterministic `now=` probe models wall-clock regression, not an unprivileged ability to supply time over the socket. A clock step can extend the actual lifetime beyond 250 ms. Enforce elapsed freshness using a suitable monotonic lifetime bound and fail closed on temporal inconsistency; restart sweeping already permits process-local lifetime state to be invalidated at restart.

3. **MEDIUM — dashboard reports source presence as operational enforcement.** `dashboard/backend/api/routes/aistack.py:2187`, `:2193`, `:2199`, `:2216`; `assets/dashboard.js:3626`: finding two strings in repository source sets `teg_peer_check_enforced=true`; directory existence/modes are labeled durability; a hardcoded state path ignores configurable `statePath`; absent/inaccessible state becomes null and renders `--`, while status remains `ok` even when `ledger_durable=false`. These indicators cannot establish the running instance's integration state or distinguish inaccessible, disabled, and unhealthy state. Expose explicit observed/unknown/disabled states and configured-path evidence, and avoid calling source presence enforcement or directory modes durability. Existing static substring tests do not catch this.

## Seven frozen obligations

1. **PASS:** only the launch handler dispatches the new ops. Control handler and both server functions retain exact source parity. Dual-UDS tests deny launch authorization on the control socket.
2. **PASS for frozen C6a defaults:** kernel SO_PEERCRED acquisition (`revocation_epoch_transport.py:78`) feeds the UID-only pre-dispatch check (`:260`). Empty, invalid, negative, mismatching UID and absent peer credentials deny. Empty UID excludes the authority user as well. There is no independent authority-UID exclusion when configured equal: distinct provisioning remains the explicitly deferred C6b condition, not a guarantee this implementation enforces.
3. **PARTIAL / FAIL freshness:** issuance uses `secrets.token_hex(32)`, binds all named fields/current epoch, millisecond timestamp, and fixed 250 ms deadline (`revocation_epoch.py:1390`). Stored-state validation and clock behavior fail findings 1–2.
4. **PASS:** issue, consume, bump, and recovery use the same existing lock helper/inode (`revocation_epoch.py:613`, `:1380`, `:1450`, `:1549`). Existing apply_bump/recover bodies are unchanged. Supplied ordering tests use sequential real signed bumps; they are not concurrent bump races. Additional 16-thread consume probe produced exactly one success and 15 duplicate denials.
5. **PARTIAL / FAIL malformed-state denial:** issuance/consumption reuse O_CREAT|O_EXCL|O_NOFOLLOW plus file/directory fsync (`revocation_epoch.py:742`, `:1406`, `:1511`). Normal duplicate, expiry, binding and supersession denials pass. Public issue/consume catch exceptions into typed denials. Finding 1 prevents full acceptance. No power-loss fault-injection claim is made.
6. **PASS by inspection and library test:** unconditional issued-without-consumed sweep (`revocation_epoch.py:1555`) precedes listening (`revocation_epoch_transport.py:565`, `:581`). It reads the clock for an audit timestamp, but never conditions sweeping on time. Separate same-inode lock acquisitions around C6d and C6a recovery do not expose a listening gap. Recovery I/O exceptions can propagate despite its docstring; startup then aborts before listen, preserving fail-closed behavior.
7. **PARTIAL:** Nix retains default OFF/mkIf, empty launchTegUid, and authority-owned 0700 root/issued/consumed/expired declarations (`nix/modules/services/revocation-epoch-authority.nix:101`, `:179`). Registry and both QA engines wire 0.10.53. Real temporary UDS integration passes; dashboard operational observability fails finding 3. No activation occurred.

## Independent validation

All commands below ran in the subject snapshot unless stated otherwise:

- `python3 scripts/testing/test-revocation-epoch.py` — exit 0, 173/173 assertions.
- `python3 scripts/testing/test-c6a-authorize-launch-service-coverage.py` — exit 0, temporary dual-UDS integration PASS. Non-TEG mismatch is a direct handler fixture, not a distinct OS-user socket connection; the socket supersession test simulates the bump by writing the fixture epoch.
- `python3 scripts/testing/test-revocation-launch-socket-topology.py` — exit 0, PASS.
- `python3 -m py_compile scripts/ai/lib/revocation_epoch.py scripts/ai/lib/revocation_epoch_transport.py dashboard/backend/api/routes/aistack.py scripts/testing/harness_qa/phases/phase0.py scripts/testing/test-c6a-authorize-launch-service-coverage.py scripts/testing/test-revocation-epoch.py scripts/testing/test-revocation-launch-socket-topology.py` — exit 0.
- `bash -n scripts/ai/_aq-qa-bash` — exit 0.
- `nix-instantiate --parse nix/modules/services/revocation-epoch-authority.nix` — exit 0; parse only, not evaluation/deployment.
- Inline `python3` JSON-load, AST source-segment comparisons against `git show 99fd115:<path>` — PASS: registry parses; exact parity for apply_bump, recover, lock/create helpers, serve, serve_multi, build_env_handler.
- Inline `python3` isolated probes described above — reproduced all three malformed-record accepts and backward-time accept; race and UID denial assertions passed. Fixtures use temporary directories and public library calls with explicit deterministic `now=` values.

No live production dashboard, actual service account/DAC deployment, power-loss recovery, full tier0 gate, or focused pre-commit CI rerun. The read-only review does not inherit the implementer's claims for those checks. Missing local LEAN-CTX.md and the absent review directory were encountered; installed lean-ctx instructions were available, and only the requested report directory/file was created.

REJECTED
