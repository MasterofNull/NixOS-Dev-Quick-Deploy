# C6c Design — Independent Binding Review

- **Subject:** `factory/c6c-design` @ `4d0005efa8168f82a9db7c99f72c912a689e6756`
  File: `.agents/plans/aqos-foundation-c/C6c-DESIGN-AND-AUTHORIZATION.md` (rev 1, PREPARED_ONLY, design-only)
- **Baseline:** main `f1f409ef97f73fb6ae152a297ba0c0367e30bf22`
- **Role:** INDEPENDENT adversarial binding reviewer — did NOT author this design. Read-only (`git show`/`git diff`); edited only this output file.
- **Reviewed by:** Claude Opus 4.8 (non-author)
- **Disposition: FREEZE-ELIGIBLE** — with one MEDIUM build-time-binding refinement (Finding 1) and two LOW advisories (Findings 2–3). No HIGH findings.

## Reproduced diff digest

```
$ command git diff f1f409ef..factory/c6c-design | sha256sum
a02dbfff2924d6ec849173f7de1631b14e7bfa42c3751ff5b02bef750583442b
```
MATCHES the requested digest exactly → **no subject drift**. `git diff --stat` confirms the change is a
single new file (`+457`, design-only, zero code bytes touched).

## Assessment

Every SHA-256 anchor and every `file:line` citation in §1 was independently verified against
`f1f409ef`. The design is accurate; I found no misquoted anchor and no drifted line reference.

**The ground-truth correction HOLDS — verified point by point.**

1. The authority ALREADY exposes the callable bump op. `build_env_handler().handler` accepts
   `{"bump": <dict>}`, loads the public allowlist fresh per request via `_load_json_file`, and calls
   `re_lib.apply_bump(bump_doc, epoch_path, ledger, owner_keys_json)` —
   `revocation_epoch_transport.py:290-296` (verified: `bump_doc = request.get("bump")` at :290,
   `apply_bump(...)` at :296). The ledger/epoch are the authority's own StateDirectory
   (`StateDirectoryMode="0700"`, dedicated user) — **the authority is the sole writer**.
2. The three landed CLI verbs are exactly as the design reconciles them (rev5 had named a
   nonexistent `prepare`):
   - `cmd_build` (`aq-epoch-bump:53-102`) — unsigned request + `bytes_to_sign_hex` (:83-86); holds no key.
   - `cmd_submit --signed` (`:105-135`) — reads pre-signed doc (:107-121), builds
     `DurableReplayLedger(args.ledger_dir)` (:132) and calls `apply_bump(...)` **in-process** (:133);
     `--ledger-dir` required-no-default (:241-248), `--epoch-path` defaults to the repo path (:240).
     Against the live authority these are `0700` authority-owned StateDirs the owner UID cannot write →
     unusable, exactly as the design states.
   - `cmd_bump` (`:169-212`) — one-shot build→sign→submit; reads a **host** private key via
     `_load_owner_key` (:190, :138-166) and sends `{"bump": request}` over the UDS via
     `send_request` (:204).
3. The proposed fix — a client verb that reads a **pre-signed** file (as `submit` does) and delivers
   `{"bump": <doc>}` over the socket (as `cmd_bump` does at :204), **without** `_load_owner_key`
   and **without** in-process `apply_bump`/ledger construction — **genuinely avoids BOTH defects**:
   - **0700-write problem — AVOIDED.** The verb only connects to the `0660` control socket and sends
     bytes; the authority process (its own user) performs the epoch/ledger mutation inside its `0700`
     StateDirectory. "Delivering bytes ≠ writing state" is correct on this codebase.
   - **Host-private-key problem — AVOIDED.** The signed doc arrives already signed; no signing routine
     or `_load_owner_key` is invoked. `sign_bump` is offline-tooling/test-only and nothing in the
     authority calls it.
   This is a **strictly simpler and correct** close than rev5's "courier from scratch": no new
   authority op, no new socket, no new group. The trust gate is unchanged — the Ed25519 signature
   verified in `apply_bump` against the public allowlist. Socket-group membership + `SO_PEERCRED` are
   log-only defense-in-depth (`revocation-epoch-authority.nix:80`; transport :163-171), so it is safe
   for `primaryUser` to hold `aq-revocation-epoch-clients` on the control socket: a connected peer
   advances nothing without an active-key-signed bump. Verified.

**Idempotency under C6d — sound.** The design correctly adds NO client-side idempotency and defers
determinism to the op. `apply_bump` denies a replayed `(request_id, idempotency_key)` via
`ledger.check_and_record` → `DENY_REPLAY` before any mutation, all under `epoch.lock`
(`revocation_epoch.py` apply_bump body verified). C6c does not change `apply_bump`'s signature,
`recover()`, the journal, the two indexes, `Type=notify`, or the recover-before-listen barrier — so
C6d's `__main__`-only edit-surface claim is preserved and a resubmit is a deterministic
receipt/`DENY_REPLAY`/`DENY_IDENTITY_CONFLICT`, never a double-bump, by inheritance. Correct.

**Rotation / revoke-on-rotation — sound.** `_verify_signature` matches `actor_key_id`
(`DENY_UNKNOWN_KEY` on miss) and re-checks `matched.get("status") != "active"` → `DENY_KEY_NOT_ACTIVE`
**on every call, no caching**; the allowlist is loaded fresh per request. Revoke-on-rotation is
immediate and restart-free. Verified at HEAD.

**DESIGN/BUILD vs P-F4 split — clean.** Allowlist at anchor: `revision: 4`, one key
`owner-mechtest-2026-08` `status: "revoked"` → **zero active signers**. Authority `enable = false;`.
The build is dormant; the lever reads `none(revoked-only)` until the SEPARATE P-F4 owner act
(offline keygen + public-only rev-4→rev-5 advance adding an active key). The design neither performs
nor depends on P-F4. Clean.

**Check-id allocation — free and correctly coordinated.** Max `0.10.x` at HEAD is **`0.10.50` in BOTH**
`phase0.py` and `_aq-qa-bash` (verified). `0.10.51` (C6d) / `0.10.52` (C6-S) / `0.10.53` (C6a) are
sibling reservations not yet at HEAD; **`0.10.54` is free**. The design commits to a build-time
verification that `0.10.54` is unused in both harnesses. See Finding 2.

**Launch-surface separation — preserved.** C6c touches only the control-socket owner-bump path; adds
nothing to the launch socket / `aq-revocation-launch-clients` / `authorize_launch`. `primaryUser` is
in `aq-revocation-epoch-clients` only (nix:111 verified), never the launch group. C6-S's severance
is preserved byte-for-byte.

## Findings

### Finding 1 — MEDIUM (build-time binding): `operational` dashboard state over-claims "end to end"
`§6` (Dashboard API, row 5) defines `operational` as *allowlist readable AND ≥1 active owner key AND
the `submit --socket` verb exists → "the owner can deliver a signed bump end to end."* That definition
omits **authority reachability** (unit `enable`d + socket present/connectable). On a fleet KILL-LEVER,
a state literally labelled "the owner can deliver end to end" that does not confirm the delivery
endpoint is live can over-report: post-P-F4, with an active key present but the authority unit
disabled or the socket absent, the lever would read `operational` while a real `submit --socket` fails
with `DENY_CONNECT_FAILED`. 
- **Failure scenario:** operator glances at the lever during an incident, sees `operational`, believes
  the kill-lever is usable, but the authority is `enable=false`/down → the bump never reaches it.
- **Mitigant (why MEDIUM not HIGH):** at baseline the lever correctly reads `none(revoked-only)`
  (zero active keys), so the over-report is only reachable in the post-P-F4/authority-disabled corner;
  and row 6 folds the rows INTO the existing Foundation-C authority-health block, so the
  authority-reachability signal is adjacent. It is a bounded, dormant-until-P-F4 refinement, not a
  defect in the core submission mechanism.
- **Required at build (binds the freeze):** condition `operational` on the authority being reachable
  (unit enabled + control socket present/connectable), OR add a distinct
  `active-but-unreachable`/`degraded` state, so no state asserts "deliverable end to end" without a
  live endpoint. The §6 coverage probe should assert this (it currently only asserts the dormant
  allowlist maps to `none(revoked-only)`).

### Finding 2 — LOW (advisory): 0.10.54 correctness depends on sibling reservations not yet at HEAD
`0.10.51`/`0.10.52`/`0.10.53` (C6d/C6-S/C6a) are asserted reservations on unmerged sibling branches; I
verified only that HEAD's max is `0.10.50` and `0.10.54` is currently free. If a sibling lands with a
different id assignment, `0.10.54` could still be safe but the reservation ledger drifts. The design
already commits to a freeze-time "verify `0.10.54` unused in both harnesses" gate, which closes the
practical risk. Advisory only: keep the freeze-time dual-harness collision check as a HARD gate.

### Finding 3 — LOW (advisory): folding `import os` revives the host-key `bump` path C6c deprecates
The `import os` defect is REAL and confirmed: the module imports `argparse, json, sys, uuid, datetime,
pathlib, typing` (`aq-epoch-bump:31-37`) but not `os`, while using `os.environ` (:147, in
`_load_owner_key`'s age branch) and `os.path` (:201, in `cmd_bump`) — both raise `NameError`, so the
landed `bump` verb is non-functional on both branches. Both references are reachable ONLY via the
`bump` verb; neither the existing `submit` nor C6c's new `submit --socket` path touches `os`. So the
one-line `import os` fix is **orthogonal to C6c's mechanism** and its only functional effect is to
revive the `bump` verb — the very host-private-key path the design elsewhere describes as
"contradicting the never-on-host model" (§1). 
- **Judgment:** folding it is nonetheless **in-scope-and-appropriate** under Rule 19 (fix the producer,
  don't leave a latent defect in a security-critical CLI whose file is already in C6c's edit surface),
  and it is correctly scoped as **design-time-noted / build-time-applied** — the design commit itself
  contains zero code (verified: diff is design-only), and it carries the Rule 11/19 backlog + commit
  note. Do NOT split it into a separate fix; that would leave the file half-fixed across two changes.
- **Advisory:** since the fix re-enables `bump`, the build should either (a) keep the existing
  `_load_owner_key` age-passphrase human-in-the-loop guard as the documented control on `bump`, or
  (b) add a one-line deprecation note steering owners to `submit --socket` as the sanctioned path — so
  reviving `bump` does not silently re-establish the host-key anti-pattern as an equal option.

## Closure of rev5 findings

- **rev5 Finding 3 (HIGH) — CLOSED.** The design inventories a CALLABLE authorized submission path
  (`aq-epoch-bump submit --signed --socket` → `{"bump": <signed doc>}` over `send_request` → the
  landed `{"bump": …}` handler at `transport:290-296`) that provably avoids the 0700-write
  (authority is sole writer) and the host-private-key read (pre-signed file, no `_load_owner_key`).
  The `build`/`submit`/`bump` verb reconciliation, the envelope, and the courier are all inventoried
  and verified against HEAD. The gap rev5 proved (owner can sign but cannot deliver) is closed.
- **rev5 Finding 4 / idempotency (was OPEN, C6d's job) — CLOSED-BY-INHERITANCE.** C6c adds no
  client-side idempotency and correctly routes determinism through the C6d journal; a resubmit is a
  deterministic receipt/typed deny, never a double-bump. C6c contradicts none of C6d's edit surface.

## Judgments requested

- **Ground-truth-correction framing:** TRUE and correct. "The authority already exposes the op; only a
  client verb is missing" is verified on this codebase, and the proposed client verb is a genuinely
  simpler + correct close than rev5's from-scratch courier, avoiding both the 0700-write and the
  host-key problems.
- **Folding the `import os` fix into C6c:** in-scope-and-appropriate (Rule 19; file already edited),
  correctly scoped as design-time-noted / build-time-applied (NOT implemented in this design commit).
  One LOW advisory: reviving `bump` re-enables the host-key path, so pair the fix with the existing
  age-passphrase guard or a deprecation note (Finding 3).

VERDICT: FREEZE-ELIGIBLE — freeze may proceed; the build MUST satisfy Finding 1 (condition the `operational` lever state on authority reachability, or add a distinct degraded state, and assert it in the §6 probe) as a binding build-time requirement, and SHOULD address the two LOW advisories (Findings 2–3).
