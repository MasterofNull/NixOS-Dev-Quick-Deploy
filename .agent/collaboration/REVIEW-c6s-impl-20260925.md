# Binding Review — C6-S implementation (`factory/c6s-impl` @ `6b289376`)

- **Subject:** branch `factory/c6s-impl` at `6b289376`, implementing the frozen C6-S design
  (`.agents/plans/aqos-foundation-c/C6-S-DESIGN-AND-AUTHORIZATION.md`, rev 2) — mechanism B:
  a dedicated TEG-only launch socket + `aq-revocation-launch-clients` group; freezes the
  two-socket transport/principal topology before C6a/C6c.
- **Baseline:** `origin/main` (includes merged C6d, `64956bd3`).
- **Role:** INDEPENDENT adversarial binding reviewer of a CODE implementation (socket-isolation
  security). Read-only on git; ran the test suite in a scratch mirror only.

## Disposition: **APPROVE**

## Reproduced digest

```
command git diff origin/main..factory/c6s-impl | sha256sum
762f225bd22122f931164ab364624d9c0d333bd83f974966ed6368d94cc3e44c
```
**MATCHES** the requested digest exactly — no subject drift. Diff is the stated 9 files
(transport, the Nix module, aistack.py, dashboard.js, env-contract, registry, phase0,
_aq-qa-bash, new topology test), +542/-26. `lease-signing-authority.nix`,
`c2-scheduler-context-issuer.nix`, and `services/default.nix` are **not** in the diff (their
`aq-revocation-epoch-clients` memberships and the landed import are untouched, as required).

## Assessment

The implementation faithfully realizes the frozen mechanism-B design. `serve()` is byte-for-byte
unchanged; `serve_multi()` is a genuine sibling (duplicated bind/loop bodies, not a refactor). The
launch socket is an idle second listener with a constant deny-all stub — no reachable op, no path
to mutate epoch/journal/state. Kernel `0660`-group DAC on a separate inode is the enforcing
boundary; ALA/C2-SCI/owner hold only the epoch group and are structurally excluded from the launch
group; the owner kill-lever stays on the control socket. Recover-before-listen composes correctly
with C6d and, if anything, tightens the readiness contract (READY now fires after BOTH sockets
listen, via `ready_callback`, vs. C6d's landed pre-bind `_sd_notify_ready()`). The new topology
test is a real live `serve_multi()` exercise, not fixture theater, and both it and the C6d suite
pass with no regression.

## Findings

**No HIGH or MEDIUM findings.** Two LOW / informational notes:

1. **LOW / forward-consideration (not a C6-S defect)** — `dashboard/backend/api/routes/aistack.py:2160-2170`.
   `launch_group_teg_only` is computed as *"launch group has zero non-authority members"*
   (`len(non_authority_members) == 0`), not literally *"members ⊆ {TEG}"* as the design §6 wording
   phrases it. For C6-S the two are equivalent (the group is declared empty of non-authority
   principals, TEG joins in C6b) and the check correctly reports `True`/`ok`. **But once C6b adds
   the TEG to the group, this predicate flips to `False` → `status: "degraded"` unless C6b updates
   it.** No bypass, no security impact for C6-S; flag for the C6b implementer. This is a latent
   maintenance item, not a topology-freeze violation.

2. **LOW / informational (pre-existing posture, byte-parity, not introduced here)** —
   `revocation_epoch_transport.py` `serve_multi()` accept loop: `conn, _ = key.fileobj.accept()`
   is outside the per-connection `try/except`, so a raise from `accept()` itself (e.g. EMFILE)
   would propagate. This exactly mirrors `serve()`'s existing structure (`srv.accept()` outside its
   try), so it is **byte-parity with the reviewed-and-landed single-socket posture, not a
   regression**. Garbage bytes and handler faults on the launch socket are fully contained (verified
   live — control socket keeps serving after a garbage launch connection), satisfying the design's
   robustness requirement (§7 item 6).

## Explicit verdicts

1. **serve() unchanged + edit-surface — PASS.** `serve()`'s def body is byte-for-byte identical to
   `origin/main` (no diff hunk touches it; confirmed by extracting both versions). The only change
   to the `serve` name is the `__main__` call site switching to `serve_multi`. `serve_multi()`,
   `build_launch_deny_all_handler()`, and the new `DENY_LAUNCH_NOT_IMPLEMENTED` constant are added
   as siblings after `serve()`. `apply_bump` call site (`:296` region), `build_env_handler()`
   dispatch, and `read_frame()` framing are untouched.

2. **Launch-socket isolation + owner-off-group — PASS.**
   `revocation-epoch-authority.nix`: `launch.sock` at `0660`, chgrped to a NEW
   `aq-revocation-launch-clients` group declared **empty** (`users.groups.aq-revocation-launch-clients = {};`);
   the authority-user is added to the launch group **only for the chgrp role** (server, never a
   launch client); `primaryUser`/owner line is UNCHANGED (`aq-revocation-epoch-clients` only — NOT
   in the launch group); ALA/C2-SCI files not touched. Env vars
   `AQ_REVOCATION_LAUNCH_SOCKET_PATH`/`AQ_REVOCATION_LAUNCH_CLIENT_GROUP` wired. Same
   RuntimeDirectory, no new tmpfiles rule needed. Verified line-by-line against the Nix diff.

3. **Deny-all stub (no reachable launch op) — PASS.** `build_launch_deny_all_handler()` returns a
   constant `_deny(DENY_LAUNCH_NOT_IMPLEMENTED, ...)` for **every** request, ignoring content (no
   distinguishing response, no info leak). `authorize_launch` is absent from the codebase. No path
   on `launch.sock` can mutate epoch/journal/state — the control handler (`build_env_handler`) is
   only bound to the control listener, and the launch listener's handler never touches epoch state.

4. **Recover-before-listen composition — PASS.** In `__main__`: env checks → single
   `_re_lib.recover(_epoch_path)` (unchanged from C6d, same error handling) → `serve_multi(...)`.
   Inside `serve_multi`, both sockets `_bind` (bind→chmod 0660→chgrp→listen) BEFORE `ready_callback`
   fires, and the accept loop starts only after. `sd_notify(READY=1)` (`_sd_notify_ready`, passed as
   `ready_callback`) therefore fires only after recover() returns AND both sockets are listening —
   correct per §3 item 3, and stricter than C6d's landed pre-bind READY. C6d's journal/recover/
   exactly-once logic is untouched.

5. **Control-socket byte-parity — PASS.** `serve_multi()`'s per-connection body is a duplicate of
   `serve()`'s (`read_frame` → handler → `json.dumps(..., sort_keys=True)+"\n"` →
   `sendall(payload[:MAX_RESPONSE_BYTES])`). The live test asserts real byte-parity: `read-epoch`
   returns `epoch == 7`, a malformed request returns `DENY_MALFORMED_BUMP` — identical to what
   `serve()` yields. (The only textual difference is a stderr WARN string in `_bind`, not wire
   bytes.) Assertions are real, not static-only.

6. **enable=false / no activation — PASS.** `enable` still `default = false;`, `config = mkIf
   cfg.enable`, `Type=notify`, `RestrictAddressFamilies=["AF_UNIX"]`, `NoNewPrivileges`/
   `ProtectSystem=strict` unchanged (not in diff). No epoch bump, no flag, no key, no network, no
   capability flag. Check id `0.10.52` registered (registry + phase0 `results.extend` +
   `_aq-qa-bash` mirror); `0.10.51` was C6d, `0.10.52` has no collision on main. Dashboard section is
   live-backed (`Path.exists`, `grp.getgrnam`), folded into the existing capability-enforcement
   block — no new card, no hardcoded state, no `--` placeholder in the API.

7. **Tests real — PASS.** `test-revocation-launch-socket-topology.py` runs a live `serve_multi()` on
   temp-dir sockets on a background thread: asserts both sockets bind at `0o660`, control-socket
   `read-epoch`/malformed byte-parity, launch deny-all on two differently-shaped requests (same typed
   reason), and that garbage bytes on the launch socket do not crash the shared loop (control keeps
   serving). Ran in a scratch mirror of the branch:
   - `test-revocation-launch-socket-topology.py` → **PASS** (exit 0).
   - `test-revocation-epoch.py` → **136 passed, 0 failed** (no regression; matches expected 136).

VERDICT: APPROVE
