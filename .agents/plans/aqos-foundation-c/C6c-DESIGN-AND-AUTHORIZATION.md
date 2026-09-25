---
title: "Foundation C — C6c: Callable offline owner-key submission path for a signed epoch-bump (deliver an owner-produced offline signature to the running authority over the C6-S control-socket owner-bump path; no host private key, no owner-UID 0700 access — completes the amended C4 prerequisite)"
slice: "C6c (fans out from C6-S in parallel with C6a; with C6d + C6-S it completes the amended C4 freeze prerequisite)"
status: "PREPARED_ONLY — authorizes NOTHING (no build, no freeze, no activation, no epoch bump, no provider traffic, no flag flip). Design + authorization note only."
revision: 2
kind: "design-only"
rev2_review: "CODEX-C6C-DESIGN-BINDING-REVIEW-20260924.md (rev1, factory/c6c-design@4d0005ef, FREEZE-ELIGIBLE, no HIGH). rev2 applies the review's binding fixes: (1) MEDIUM build-time-binding — §6 Dashboard API row 5 now REQUIRES authority reachability (not just allowlist+key+verb) for the `operational` state, adds a distinct `degraded(authority-unreachable)` state, and binds a §6 probe assertion for the active-key-but-authority-down fixture (Finding 1); (2) LOW — §1/§8 pair the `import os` fix with an explicit `bump`-verb deprecation note steering owners to `submit --socket` (Finding 3); (3) LOW — §6/§8 make the dual-harness check-id collision check a HARD freeze/land-time gate, not just a 0.10.54-specific verification (Finding 2). No mechanism/submission/idempotency/rotation change."
implementation_authorization: "NONE"
activation_authorization: "NONE"
base_head: "f1f409ef97f73fb6ae152a297ba0c0367e30bf22"
parent_decomposition: ".agents/plans/aqos-foundation-c/C6-DECOMPOSITION-20260924.md (factory/c6-decomposition-v2) §4 — C6c slice spec; §0.4 Service Coverage Contract; §7 [AMEND-C4]; §8 build order"
sibling_foundation: ".agents/plans/aqos-foundation-c/C6-S-DESIGN-AND-AUTHORIZATION.md (factory/c6s-design-v2, rev2) — freezes the two-socket topology; C6c lands the owner submission on the CONTROL-socket owner-bump path it froze, DISTINCT from the launch group. AND .agents/plans/aqos-foundation-c/C6d-DESIGN-AND-AUTHORIZATION.md (factory/c6d-design-v2, rev2) — the submitted bump flows through C6d's journal/two-index/recover so a resubmit is a deterministic receipt / DENY_REPLAY, never a double-bump."
closes_finding: "CODEX-C6-REV5-BINDING-REVIEW-20260924.md Finding 3 (HIGH) / rev4 Finding 4 — the selected offline owner-key ceremony had NO callable submission path (build/submit/bump reconciliation; submit --signed applies apply_bump in-process against 0700 authority StateDirs the owner UID cannot use; bump reads a host private-key file, contra the never-on-host model; the TEG public envelope accepts no authority object; no signed-bump courier inventoried)."
mechanism: "Add an offline socket-submit path to aq-epoch-bump (submit --signed --socket <path>) that delivers a PRE-SIGNED {\"bump\": <signed doc>} to the RUNNING authority over the C6-S control-socket owner-bump path via revocation_epoch_transport.send_request — no host private key read, no owner-UID write to the authority's 0700 StateDirectory (the authority applies the verified bump itself under epoch.lock). The authority's landed handler already accepts {\"bump\": {...}} — no new authority op is added."
authoring_role: "architect (design/planning only)"
owner_activation_needed: "NO for the DESIGN/BUILD (builds dormant). YES at a SEPARATE later act — P-F4: owner OFFLINE keygen + public-only monotonic allowlist advance rev-4 -> rev-5 adding an active owner public key. This slice neither performs nor depends on P-F4; until it, the lever is observably none(revoked-only)."
build_order: "C6d -> C6-S -> {C6a || C6c} -> [AMEND-C4] -> C4 -> C6b -> C6e (decomposition §8). C6c fans out from C6-S in PARALLEL with C6a; it does NOT require C6a. Completing C6c (with C6d + C6-S) is the event that makes C4 freeze-eligible under the amended prerequisite (§7 of the decomposition)."
---

# Foundation C — C6c: Callable offline owner-key submission path

## 0. What this slice is, and why it exists

C6c is the **owner kill-lever completion slice** of the freeze-eligible C6 decomposition
(`C6-DECOMPOSITION-20260924.md` §4, §8). With **C6d** (durable, recoverable epoch authority) and
**C6-S** (the frozen two-socket topology + control-socket owner-bump path), C6c makes the operator
kill-lever *actually usable*: it defines the **callable authorized path** by which an owner who
produced an Ed25519 signature **offline** delivers that signature TO the running authority and
advances the epoch — the exact piece rev5 Finding 3 proved was missing.

C6c closes **rev5 Finding 3 (HIGH)** — the binding re-review proved that at the anchored baseline
the offline-signing ceremony had **no callable submission path** after the proposed principal
separation:

- the landed CLI verb is **`build`** (not `prepare`) — it constructs an unsigned request and prints
  the canonical bytes to sign offline;
- **`submit --signed`** calls `revocation_epoch.apply_bump` **in-process** against `--epoch-path` /
  `--ledger-dir`, which are the authority's **`0700`, authority-owned** StateDirectory paths the
  owner UID **cannot write** in the running system;
- **`bump`** reaches the authority over the UDS, but it **reads and signs with a private-key file on
  the host** — contradicting the design's "the owner private key never touches the harness host"
  model;
- the TEG public envelope accepts no authority object, and **no signed-bump courier is inventoried**.

So an owner could create a valid offline signature but had **no authorized route** to deliver it to
the running authority. C6c inventories that route.

**The route already half-exists in the landed code, and that is the whole point of a minimal
close.** The authority's request handler **already accepts `{"bump": <signed doc>}` on the control
socket** and applies it through `apply_bump` (`revocation_epoch_transport.py:290,296`). What is
missing is purely a **client verb** that (a) reads a **pre-signed** document from a file (as
`submit` does) and (b) delivers it over the socket (as `bump` does) — **without** `submit`'s
in-process 0700 write and **without** `bump`'s host private-key read. C6c adds exactly that verb.
No new authority operation, no new socket, no new group.

**This is design-only and PREPARED_ONLY.** It authorizes no implementation, no freeze, no build, no
activation, no epoch bump, no flag flip, no key provisioning. The baseline at `f1f409ef` is dormant
(sole owner key `revoked`, allowlist revision 4, authority `enable = false`, gate env absent); C6c
does not change that. The DESIGN/BUILD needs **no owner activation**; the later **P-F4** activation
(offline keygen + public-key allowlist advance rev-4 → rev-5) is a **separate owner act** this slice
neither performs nor depends on (§8).

---

## 1. Current anchored baseline (verified against `f1f409ef`)

Every SHA-256 below was computed at `f1f409ef97f73fb6ae152a297ba0c0367e30bf22`. Every file:line
citation was verified against HEAD in this worktree (`command git diff --stat f1f409ef..HEAD` shows
**no source-file drift** — only the sibling design docs differ, so the working tree equals the
anchor for every path cited here).

| Existing path | SHA-256 | C6c role |
|---|---|---|
| `scripts/ai/aq-epoch-bump` | `f9cd487ce5ad447bad3cadb6453a87aa095a538670c3ddb369347b6ce1fb4b8f` | **EDIT (the crux).** Add an offline socket-submit path: `submit --signed --socket <path>` (a new `--socket` on the landed `submit` verb, `:238-250`) that reads the **pre-signed** doc from `--signed` (as `cmd_submit` already does, `:105-121`), then delivers `{"bump": <signed doc>}` over the socket via `revocation_epoch_transport.send_request` (the same client call `cmd_bump` already makes at `:204`) — **without** constructing a `DurableReplayLedger` or calling `apply_bump` in-process (no 0700 write), and **without** `_load_owner_key` (`:138-166`, no host private-key read). When `--socket` is absent, `submit` keeps its landed in-process behavior byte-for-byte (`:132-135`). Also fold in the bounded fix of the landed missing `import os` (see "Landed reality", below), **paired with an explicit deprecation note on `bump`** (rev2 fix): reviving `bump` by fixing its `NameError` must not silently re-bless the host-key path C6c deprecates — add a one-line docstring/help note on `cmd_bump` stating `bump` is retained only for the offline/no-socket-available fixture case and that `submit --signed --socket` is the sanctioned owner-delivery path (§8 freeze criterion 3). |
| `scripts/ai/lib/revocation_epoch_transport.py` | `066b30c326898d6ef8e4ab085cf82ce131bb9812b08a61993de86b0812a6be28` | **NO EDIT.** Cited as ground truth: `send_request(socket_path, request)` (`:193-219`) is the fail-closed client helper C6c reuses; `build_env_handler().handler` already accepts `{"bump": <signed doc>}` and calls `re_lib.apply_bump(bump_doc, epoch_path, ledger, owner_keys_json)` (`:290-296`) — the authority is the only writer of epoch/ledger, under its own StateDirectory. `SO_PEERCRED` is **log-only** (`:69-77`, `:163-171`). No new op, no `__main__` change (that is C6d/C6-S). **rev2: also cited as ground truth for the dashboard reachability probe (§6, Finding 1)** — the handler already answers a cheap read-only `{"op": "read-epoch"}` request (`:283-289`, distinct from the `bump` branch at `:290-296`); C6c's `owner_epoch_bump_lever` reuses this landed op via `send_request` to distinguish `operational` from `degraded(authority-unreachable)`. No new authority op is added for this either. |
| `scripts/ai/lib/revocation_epoch.py` | `d6c3a3b60a04fde15b5fe9a619f6fc290110776bbdefc35c6de21dcd594a75e6` | **NO EDIT.** Cited as ground truth: `apply_bump(bump_doc, epoch_path, ledger, owner_keys_json_dict, now=None)` (`:609-615`) verifies then advances the epoch by +1 under one exclusive `epoch.lock`; `verify_bump` (`:432`) → `_verify_signature` (`:389`) matches `actor_key_id` against the allowlist and **re-checks `status == "active"` on EVERY call** (`:407`, no caching). Replay is denied by the ledger on `(request_id, idempotency_key)` (`:658-664`, `DENY_REPLAY`). C6d replaces that single-marker ledger with the journal+two-index; C6c inherits whatever apply_bump's dedup is. |
| `config/aqos/c6-owner-public-keys.json` | `562c81ca86b6853aed40cf7430a6512cd3cd22aa8269c479a46c65575314ae4e` | **NO EDIT by the build.** The public allowlist: `revision: 4`, exactly one key `owner-mechtest-2026-08` with `status: "revoked"` — **zero active signers** (the dormant baseline). Advancing it rev-4 → rev-5 with an active owner public key is **P-F4**, a separate owner activation act (§8), not part of this build. |
| `nix/modules/services/revocation-epoch-authority.nix` | `b539e5de6dd89eb4fd93ed2119055ad9440897b1c408a98f6c23d9ded0db0172` | **NO EDIT.** Cited as ground truth: the owner-bump principal path is `users.users.${primaryUser}.extraGroups = mkAfter ["aq-revocation-epoch-clients"]` (`:111`), which lets the owner UID *connect* to the control socket (`socketPath` default `/run/aq-revocation-epoch-authority/control.sock`, `:79`). **C6-S froze this control-socket owner-bump path**; C6c lands ON it and needs no attribute beyond what C6-S froze. StateDirs are `0700` authority-owned (`:84-85`, `:124-125`, `StateDirectoryMode="0700"` `:145`); env `AQ_REVOCATION_EPOCH_SOCKET_PATH` (`:147`), owner-keys path (`:149`), epoch/ledger paths (`:150-151`). Keeps `enable = false;` (`:65`). |
| `config/env-contract.yaml` | `21a64d786c1e6ea167e3baeb2b03e5a657137e343a76359ec87018589066a8b2` | **NO EDIT (binds landed).** `AQ_REVOCATION_EPOCH_SOCKET_PATH` is already the canonical control-socket reference (`:1339`). The offline socket-submit reuses that landed path reference; C6c introduces **no new env var and no capability flag**, so the "new flags default `\"0\"`" rule has nothing to gate. |
| `dashboard/backend/api/routes/aistack.py` | `46afe8d86848bd3d2cebc0831a7c2878d1d664ec52e87c13ac371cbb73579b58` | **EDIT (minimal).** Add a compact live-backed `result["owner_epoch_bump_lever"]` section modelled on the ALA section (`:2090-2110`) / C2-SCI section (`:2112-2132`), reporting the four states **`operational` \| `degraded(authority-unreachable)` \| `none(revoked-only)` \| `unavailable`** (§6, rev2 — `operational` now REQUIRES authority reachability, not just allowlist+key+verb; see Finding 1 of the binding review). |
| `assets/dashboard.js` | `6a1610475db60a0bacd830a523013d2d825101a9721b38eaa3d70c269074001a` | **EDIT (minimal).** Read `owner_epoch_bump_lever` and render its rows inside the existing Foundation-C authority health block (no new card). |
| `config/validation-check-registry.json` | `f679818f7c89bc0c6d888455f766e528a6d34d37054630092dd6ca73a06885a4` | **EDIT.** Register the new `c6c-owner-submission-coverage` behavioral check (§6), modelled on `c2-sci-service-coverage` (`:1398-1419`) / `ala-service-coverage` (`:1376`). |
| `scripts/testing/harness_qa/phases/phase0.py` | `12701183de2e55040a9cf6e3015a7bf29320046dfa5195b516b3c7af3257f527` | **EDIT.** Add the owner-submission integration probe via `results.extend(...)`, modelled on `_check_intent_classifier_coverage` (`:1325`, wired at `:1985`). Allocate the **next-free id `0.10.54`** (see §6 — coordination with C6a). |
| `scripts/ai/_aq-qa-bash` | `3d4364ec55b3f2e0f6c4b898fe5296d24ea5767c3321e927501edc357b997b45` | **EDIT.** Mirror the same `0.10.54` check id in the bash harness, modelled on the `0.10.10` `_check` line (`:1635`), per the dual-harness check-id contract. |
| `scripts/testing/test-c2-sci-service-coverage.py` | `ad7a9785e75a6d80ff8e0b8528fd6bbc710437a9f2e49e15e37d205155e66c70` | **NO EDIT.** Cited as the template the new `test-c6c-owner-submission-service-coverage.py` mirrors. |
| `nix/modules/services/default.nix` | `7873bff56d33f7d798bafa4cc1ecceebdb10975d1ae62c83e48fdcafe94e0ecc` | **NO EDIT.** Already imports `./revocation-epoch-authority.nix` at **line 26** — the authority (and its control socket) is already wired into the system. C6c adds **no new module** and binds this landed import (Service-Coverage row 2). |

**Landed reality that C6c changes (verified).**

- The authority **already** exposes a callable bump op on the control socket: `build_env_handler`'s
  `handler` accepts `{"bump": <dict>}` (`revocation_epoch_transport.py:290-292`), loads the public
  owner-keys allowlist fresh per request (`_load_json_file`, `:293`; never cached — a revocation
  takes effect with no restart, `:234-236`), and calls
  `re_lib.apply_bump(bump_doc, epoch_path, ledger, owner_keys_json)` (`:296`). The authority — not the
  caller — owns `epoch_path` and `ledger` under its `0700` StateDirectory. **So the missing piece is
  a client that delivers a pre-signed doc over the socket; the authorized authority op is already
  there.**
- The three landed `aq-epoch-bump` verbs, verified:
  - **`build`** (`cmd_build`, `:53-102`) — constructs an unsigned `aq.revocation-epoch-bump/1`
    request and prints `bytes_to_sign_hex` (`:83-86`); reads/holds **no** private key. rev5 called
    this `prepare`; the real verb is `build`.
  - **`submit --signed <file>`** (`cmd_submit`, `:105-135`) — reads the pre-signed doc (`:107`),
    constructs `DurableReplayLedger(args.ledger_dir)` (`:132`) and calls `apply_bump(bump_doc,
    args.epoch_path, ledger, owner_keys)` **in-process** (`:133`). `--ledger-dir` is **required, no
    default** (`:241-248`); `--epoch-path` defaults to the repo `config/capability-lease-epoch`
    (`:240`, `DEFAULT_EPOCH_PATH` `:45`). In the running system the authority's `--epoch-path` /
    `--ledger-dir` are `0700` authority-owned StateDirs — **the owner UID cannot write them**, so
    this path is unusable against the live authority. (It remains valid for the offline/no-service
    fixture case its docstring describes, `:21-27`.)
  - **`bump`** (`cmd_bump`, `:169-212`) — one-shot build → sign → submit over the UDS. It reads a
    **host private-key file** via `_load_owner_key` (`:190`, `:138-166`) and submits
    `{"bump": request}` over the control socket via `send_request` (`:204`, socket default
    `/run/aq-revocation-epoch-authority/control.sock` `:260`). The host private-key read is exactly
    what contradicts the "owner private key never on the harness host" model.
- **Latent defect found and reported (Rule 11 / Rule 19).** `cmd_bump` references `os.environ`
  (`:147`, inside `_load_owner_key`'s age-passphrase branch) and `os.path` (`:201`), but the module
  **never imports `os`** (imports are `argparse, json, sys, uuid, datetime, pathlib, typing`,
  `:31-37`; `_load_owner_key` imports only `subprocess` and `pathlib`, `:143-144`). Both references
  would raise `NameError` at runtime, so the landed `bump` verb is **non-functional** on either
  branch. C6c's new socket-submit path does **not** depend on `bump`, but because C6c edits this same
  file, it **folds in the one-line fix (`import os`)** as a bounded root-cause fix carrying a one-line
  note in the commit body (Rule 19), rather than leaving a discovered defect in a security-critical
  CLI. This is logged to `memory/issues-backlog.md`.
- **rev2: the `import os` fix must not silently revive `bump` as an equal, undeprecated path
  (binding review Finding 3, LOW).** Fixing the `NameError` makes `bump` functional again, and `bump`
  is exactly the **host-private-key** path (`_load_owner_key`, `:190,:138-166`) this design deprecates
  in favor of `submit --signed --socket`. The build MUST pair the one-line `import os` fix with an
  **explicit deprecation note** on `cmd_bump` (docstring/`--help` text): `bump` is retained only for
  the offline/no-service fixture case its own docstring already describes (`:21-27`), `submit --signed
  --socket` is the sanctioned owner-delivery path against a running authority. This is a documentation
  pairing, not a behavior change — the existing `_load_owner_key` age-passphrase human-in-the-loop
  guard (`:143-166`) stays the control on `bump` if an owner still invokes it; the note only prevents
  the crash-fix from *implicitly* re-blessing host-key custody as an equally-sanctioned option.

The final freeze must reproduce every listed hash, bind the revised packet hash, reject all other
changed paths, and stop on HEAD drift.

---

## 2. The callable authorized submission path (the close of Finding 3)

C6c freezes exactly this owner-submission contract. It is a **client-side** addition on top of the
**already-callable** authority `{"bump": …}` op and the **C6-S-frozen** control-socket owner-bump
path.

### 2.1 The path, end to end

1. **Offline (owner's own machine, no harness involvement).** The owner runs `aq-epoch-bump build …`
   to obtain the canonical `bytes_to_sign_hex` (or reproduces those bytes with their own tooling),
   signs them **offline** with their Ed25519 **private** key (which never touches the harness host),
   and writes the resulting **signed document** — the `aq.revocation-epoch-bump/1` request with its
   `signature` field filled — to a file. `build` already prints these bytes and holds no key
   (`:83-95`); this step is unchanged.
2. **On the harness host, as the owner UID (`primaryUser`).** The owner runs the **new**
   `aq-epoch-bump submit --signed <file> --socket <control.sock>`. This verb:
   - reads the pre-signed document from `--signed` (reusing `cmd_submit`'s existing read+unwrap,
     `:107-121` — it accepts either the raw bump doc or the `{"request": …}` wrapper `build` emits);
   - reads **no** private key (no `_load_owner_key`), constructs **no** `DurableReplayLedger`, and
     calls **no** in-process `apply_bump` (so it never touches the `0700` StateDirectory);
   - delivers the envelope `{"bump": <signed doc>}` to the running authority over the control socket
     via `revocation_epoch_transport.send_request(args.socket, {"bump": signed_doc})` — the identical
     client call `cmd_bump` already makes (`:204`), minus the host-key step;
   - prints the authority's typed response and exits `0` iff `resp.get("ok")` (mirroring `cmd_bump`'s
     `:209-212`).
3. **Inside the running authority (unchanged landed code).** `build_env_handler`'s `handler` receives
   `{"bump": <signed doc>}` (`:290`), loads the **public** allowlist fresh
   (`config/aqos/c6-owner-public-keys.json`, `:293`), and calls `apply_bump(bump_doc, epoch_path,
   ledger, owner_keys_json)` (`:296`). `apply_bump` verifies the signature against the allowlist
   (`verify_bump` → `_verify_signature`, `status == "active"` re-checked, `revocation_epoch.py:407`),
   checks `expected_epoch` against the durable epoch, consults the replay ledger/journal, and — only
   on a valid, fresh, active-key bump — advances the epoch by exactly +1, all under `epoch.lock`
   (`:632-668`). The authority is the sole writer.

### 2.2 The message / envelope (frozen)

- **Wire frame:** one newline-terminated JSON object, `read_frame`/`send_request` framing
  (`transport:86-116`, `:193-219`), bounded by `MAX_REQUEST_BYTES = 65536` (`:40`).
- **Envelope:** `{"bump": <signed doc>}` — top-level key `bump` whose value is the complete
  `aq.revocation-epoch-bump/1` document (`schema_version`, `request_id`, `idempotency_key`,
  `issued_at`, `expires_at`, `actor_key_id`, `expected_epoch`, `reason_code`, `scope`, `signature`),
  exactly the shape `cmd_build` emits (`:71-82`) with `signature` filled offline. **No authority
  object, no host path, no key material** is in the envelope — it carries only the owner-signed
  document. This is the *same* envelope `cmd_bump` sends (`:204`); C6c changes only where the signed
  doc comes from (a file, not an in-process host-key signature).
- **Response:** the authority's typed dict — `{"ok": true, "reason": "ok", "receipt": {…}}` on a
  committed bump, or `{"ok": false, "reason": DENY_*, …}` on any deny (`revocation_epoch.py:617-619`;
  transport denies `transport:58-59`).

### 2.3 Why the owner UID no longer needs the 0700 paths, and why no private key touches the host

- **No 0700 access.** The owner UID never reads or writes `epoch_path` / `ledger_dir`. It only
  *connects* to the control socket and sends bytes; the **authority process** (running as its own
  dedicated user) performs the epoch/ledger mutation inside its `0700` StateDirectory. The socket is
  mode `0660`, group `aq-revocation-epoch-clients` (`serve():143,148`; group set by the unit at
  `.nix:148`), and the owner UID is a member of that group via `.nix:111` (frozen by C6-S) — so the
  owner can *connect* but the durable state stays authority-only. This is precisely why rev5's
  in-process `submit --signed` failed and the socket path succeeds: **delivering bytes ≠ writing
  state.**
- **No host private key.** The signed document arrives already signed; the new verb reads it from a
  file and never invokes `_load_owner_key` or any signing routine. `revocation_epoch.sign_bump` is
  explicitly "FOR OFFLINE OWNER-SIGNING TOOLING AND TEST FIXTURES ONLY" and nothing in the authority
  process calls it (`revocation_epoch.py:275-283`; `transport:15-18`). The owner private key exists
  only on the owner's offline machine.
- **Transport membership is not authority.** The socket group + `SO_PEERCRED` are defense-in-depth
  only (`transport:7-13`, `:69-77`, `:163-171`). The *actual* gate on advancing the epoch is the
  Ed25519 signature verified inside `apply_bump` against the public allowlist. A peer that connects
  advances nothing without a bump an **active** owner key signed — so it is safe for the owner UID to
  hold `aq-revocation-epoch-clients` membership on the control socket (this is the C6-S-preserved
  owner-bump path, kept **distinct** from the launch group so narrowing the launch surface never
  severs the kill-lever).

### 2.4 Relationship to the C6-S launch surface (kept distinct)

C6c touches **only** the **control** socket's owner-bump path. It adds **nothing** to the launch
socket, the `aq-revocation-launch-clients` group, or `authorize_launch` (all C6-S/C6a/C6b). The owner
kill-lever is structurally severed from the launch surface (C6-S §2.2 item 4): the `primaryUser` is
in `aq-revocation-epoch-clients` only, never the launch group. C6c preserves that separation
byte-for-byte.

---

## 3. Idempotency under the C6d journal (resubmit → deterministic receipt / DENY_REPLAY, never a double-bump)

C6c adds **no** client-side idempotency and **must not** — the authority is the single serialization
point under `epoch.lock`, and the CLI must stay a thin courier. Idempotency is a property of the op
C6c invokes:

- Every submitted `{"bump": <signed doc>}` carries a fixed `(request_id, idempotency_key)` pair
  (populated by `build`, `:73-74`, and frozen into the signed bytes — `canonical_bump_payload` covers
  every field except `signature`, `revocation_epoch.py:262-272`). **Re-submitting the same signed
  file re-sends the same pair.**
- On the **landed** baseline (`DurableReplayLedger`, keyed on `sha256(request_id ∥ "\x00" ∥
  idempotency_key)`), a resubmit of an already-consumed pair returns `DENY_REPLAY`
  (`revocation_epoch.py:658-664`) — never a second +1.
- Under **C6d** (which replaces that single marker with the write-ahead journal + two independent
  uniqueness indexes + `recover()`), the same resubmit is deterministic per C6d §3.2:
  - a bump that **committed** → the reconstructed **committed receipt** (exactly-once; vector h);
  - a bump that **never committed** (crash before the epoch CAS) → the identical retry
    **actually bumps** (C6d's `aborted → intent` reuse; never a wedged `DENY_REPLAY`, vector d);
  - the same `request_id` re-signed with a **different** `idempotency_key` (or the reverse) →
    typed `DENY_IDENTITY_CONFLICT` (C6d §3.2 identity gate, vector j) — never a double-bump.
- **C6c does not contradict C6d.** It does not change `apply_bump`'s signature (so C6d's
  `__main__`-only edit-surface claim holds), does not touch `recover()`, the journal, the two
  indexes, `Type=notify`, or the recover-before-listen barrier. The submitted bump flows through
  C6d's hardened `apply_bump` exactly as any bump does; a resubmitted signed bump is therefore a
  **deterministic receipt or a typed deny, never a double-bump** — by inheritance from C6d, not by
  any C6c mechanism. The integration probe (§6) asserts this end to end.

---

## 4. Forward-only public-key rotation / revoke-on-rotation semantics (carried forward from rev5)

These semantics are **sound per rev5** (rev5 §2.3; decomposition §0.3) and C6c keeps them; the
allowlist and verifier already enforce them at the anchor:

- **Public-only allowlist, per-request re-read.** `config/aqos/c6-owner-public-keys.json` holds only
  **public** keys + `status` + a monotone `revision` (verified: `revision: 4` at the anchor). The
  authority loads it **fresh on every request** (`_load_json_file`, `transport:234-236,293`) — never
  cached.
- **Revoke-on-rotation is immediate and restart-free.** `_verify_signature` re-checks
  `matched.get("status") != "active"` on **every** call (`revocation_epoch.py:405-408`), returning
  `DENY_KEY_NOT_ACTIVE`. Flipping a key's `status` to `"revoked"` (or removing it) takes effect on the
  next request with no service restart. An unknown `actor_key_id` yields `DENY_UNKNOWN_KEY` (`:402`).
- **Forward-only monotonic advance.** Rotation advances the allowlist `revision` monotonically
  (rev-4 → rev-5 at P-F4, and forward thereafter). The advance is a **public-only** edit of a tracked
  config file that mutates **no frozen code bytes** — consistent with the rev5 §2.3/§6 and C6-P0 §3
  reasoning the review CLOSED (rev4 Finding 3). A superseded key is revoked (status flip), never
  silently reused; the new active key is added at the advanced revision.
- **C6c changes none of this.** The submission path is agnostic to which key signed — it delivers the
  document and the authority's landed verifier applies the forward-only/revoke semantics. C6c only
  makes the delivery callable.

---

## 5. Exclusions

C6c touches **only** the files in §1. Explicitly excluded (each is a later slice, a separate act, or
out of scope):

- The `authorize_launch` op, the launch socket/group, single-use launch tokens — **C6a / C6-S /
  C6b** (C6c touches only the control-socket owner-bump path; it adds no launch surface).
- Any change to `apply_bump`'s signature, `verify_bump`, the journal/two-index/`recover()`, or
  `Type=notify` — **C6d** (C6c composes on top and contradicts none of it).
- The two-socket topology, the `aq-revocation-launch-clients` group, the authority-user launch-group
  membership — **C6-S** (frozen; C6c consumes the control-socket owner-bump path as a fixed input).
- The TEG principal / `dispatch_gateway` / in-principal provider execution / egress — **C6b / C6e /
  C4**.
- **The owner public-key allowlist advance (rev-4 → rev-5) and any epoch bump — P-F4**, the separate
  owner activation act (§8). C6c neither performs nor depends on it; the build is dormant.
- Offline key generation / key custody tooling — the owner's own offline environment; out of harness
  scope (the harness holds only public keys).
- `slot_queue` / `dispatch.py` scheduler-gate fence, `CAPABILITY_SCHEDULER_LEASE_GATE` — later C6.
- The auto-revert guard (decomposition §0.2 — no C6 slice modifies it).
- A general legacy-ledger import/migration path — out of scope (C6d §7; dormant baseline).
- Provider invocation, network, DDL, deployment, activation, flag flips.

Any need to touch an excluded path is a **stop condition** requiring a new reviewed design, not
expansion of C6c.

---

## 6. Service-Coverage inventory (decomposition §0.4)

C6c introduces a **new callable owner-facing surface** (the socket-submit verb), so per §0.4 it ships
its own coverage test PLUS the required registry + dual-harness + dashboard wiring:

- **env-contract** (row 1) — **binds landed; no new flag/var.** The offline socket-submit reuses the
  canonical `AQ_REVOCATION_EPOCH_SOCKET_PATH` (`env-contract.yaml:1339`); C6c introduces **no**
  capability flag, so the "new flags default `\"0\"`" rule has nothing to gate.
- **Nix service + import** (row 2) — **bound to the landed import.** `revocation-epoch-authority.nix`
  is already imported at `default.nix:26`; C6c adds **no new module** and does not edit the authority
  module (the control-socket owner-bump path was frozen by C6-S). The module stays `enable = false;`,
  AF_UNIX-only (`.nix:166`), `NoNewPrivileges`/`ProtectSystem="strict"` (`:159`/`:161`) unchanged.
- **Durable primitive** (row 3) — n/a for C6c itself: single-use/atomicity lives in `apply_bump`'s
  ledger/journal (C6d), which C6c reuses, not re-implements.
- **Flag-gated call path** (row 4) — n/a: C6c adds no gated call path. **Off-is-inert byte-parity
  holds:** the authority stays `enable=false`; the new `submit --socket` verb is owner-invoked only
  (nothing calls it automatically, `aq-epoch-bump:2-4`); with `--socket` absent, `submit` keeps its
  landed in-process behavior byte-for-byte.
- **Dashboard API** (row 5) — **NEW compact live-backed section.** Add
  `result["owner_epoch_bump_lever"]` in `aistack.py` (modelled on the ALA section `:2090-2110` /
  C2-SCI `:2112-2132`), probed live (no hard-coded healthy state, no `--` placeholder), with the
  **four** required states (rev2 — binding review Finding 1, MEDIUM build-time-binding: `operational`
  must not over-claim "deliverable end to end" without confirming the delivery endpoint is live):
  - **`operational`** — the allowlist is readable AND has ≥1 `status:"active"` owner key AND the
    callable socket-submit path is present (the `aq-epoch-bump submit --socket` verb exists) **AND
    the authority is reachable** (the control socket answers a cheap read-only `{"op": "read-epoch"}`
    probe via `revocation_epoch_transport.send_request`, reusing the landed handler branch at
    `transport:283-289` — no new authority op) → the owner can deliver a signed bump end to end,
    verified, not assumed.
  - **`degraded(authority-unreachable)`** — **NEW state, required.** The allowlist is readable AND has
    ≥1 active key AND the verb is present, but the authority `read-epoch` probe fails (unit
    disabled/down, socket absent, or connect/timeout) → the lever is wired and a key is active, but
    the delivery endpoint is NOT confirmed live. This is the state that closes Finding 1: an
    active-key-but-authority-down fixture MUST read this, never `operational`.
  - **`none(revoked-only)`** — the allowlist is readable but has **zero** active keys (all revoked;
    the dormant `f1f409ef` / pre-P-F4 state — revision 4, one revoked key). Authority reachability is
    irrelevant here (there is no active key to sign an admissible bump regardless).
  - **`unavailable`** — the allowlist is unreadable/malformed, or the submit verb / socket reference
    is absent (fail-closed; never reported healthy).
  Also surface `allowlist_revision`, `active_owner_keys`, and `authority_reachable` (bool, from the
  `read-epoch` probe) so the operator sees exactly why the lever is in its state — including why it is
  `degraded` rather than `operational` when a key is active but the authority did not answer.
  **Build-time binding (Finding 1):** the §6 coverage probe (row 8) MUST assert that an
  active-key-but-authority-unreachable fixture reads `degraded(authority-unreachable)`, never
  `operational` — a false-green on this fleet kill-lever is unacceptable (anti-gaming /
  observable≠functional).
- **Dashboard UI** (row 6) — **minimal, folded.** `assets/dashboard.js` reads `owner_epoch_bump_lever`
  and renders the state + revision/active-key/authority-reachable rows **inside the existing
  Foundation-C authority health block** — **no new card** (a separate card would duplicate the block
  without giving the operator a new action). Review Finding 3's observability bar is met: the lever's
  `operational` vs `degraded(authority-unreachable)` vs `none(revoked-only)` vs `unavailable` state is
  directly visible (rev2 adds the degraded state, §6 row 5).
- **Crypto/service tests exist** (row 7) — **NEW**
  `scripts/testing/test-c6c-owner-submission-service-coverage.py` (mirrors
  `test-c2-sci-service-coverage.py`), asserting: the callable `submit --socket` path exists; it reads
  **no** host private key and performs **no** in-process `apply_bump` / 0700 write; revoked / unknown /
  non-monotonic / bad-signature documents deny; the dormant allowlist state maps to
  `none(revoked-only)`; **(rev2)** an active-key-but-authority-unreachable fixture maps to
  `degraded(authority-unreachable)`, never `operational`.
- **Integration-check registration (NEW, required)** (row 8) — register
  **`c6c-owner-submission-coverage`** in `config/validation-check-registry.json` (modelled on
  `c2-sci-service-coverage` at `:1398-1419`: `id`, `description`, `trigger_paths` =
  [`scripts/ai/aq-epoch-bump`, `scripts/ai/lib/revocation_epoch_transport.py`,
  `scripts/ai/lib/revocation_epoch.py`, `config/aqos/c6-owner-public-keys.json`,
  `dashboard/backend/api/routes/aistack.py`, `assets/dashboard.js`,
  `scripts/testing/test-c6c-owner-submission-service-coverage.py`], `command`, `tier:"behavioral"`,
  `timeout_seconds`, `enabled:true`), **AND** wire the submission integration probe in **BOTH**
  harnesses per the dual-harness check-id contract:
  - `scripts/testing/harness_qa/phases/phase0.py` — a new `_check_c6c_owner_submission(ctx)` returning
    `CheckResult`, added via `results.extend(...)`, modelled on `_check_intent_classifier_coverage`
    (`:1325`, wired at `:1985`). Allocate the **next-free id `0.10.54`**.
  - `scripts/ai/_aq-qa-bash` — the mirror `_check 1 "0.10.54" "C6c owner epoch-bump submission" …`
    line, modelled on the `0.10.10` entry (`:1635`).
  - **Check-id coordination (verified).** The current max id is **`0.10.50` in BOTH `phase0.py` and
    `_aq-qa-bash`**. The sibling foundation slices reserve **C6d = `0.10.51`** and **C6-S = `0.10.52`**
    (per their designs). C6a and C6c **fan out in parallel** from C6-S (decomposition §8), so their
    ids must be distinct: **C6a takes `0.10.53`** (its design's next-free), and **C6c takes
    `0.10.54`**. C6c claims `0.10.54` explicitly to avoid a collision when the two parallel siblings
    land in either order.
  - **rev2 (binding review Finding 2, LOW — closed as a HARD gate):** `0.10.54`'s correctness depends
    on the sibling reservations (`0.10.51`/`0.10.52`/`0.10.53`) being at HEAD as claimed when C6c
    lands — those are unmerged sibling branches, not yet verified at C6c's freeze time. A **dual-harness
    check-id collision check** (no duplicate id across `phase0.py` AND `_aq-qa-bash`, checked against
    whatever siblings have actually landed, not just against the `0.10.54` assumption) is therefore a
    **HARD gate at freeze/land time** for C6c — not an informational "verify 0.10.54 is unused"
    note. If a sibling landed with a different id assignment than assumed here, the gate MUST block
    the land (never silently pick a colliding id) and the id is re-coordinated before proceeding. This
    is a HARD gate specifically so parallel-authored siblings (C6a alongside C6c) cannot land colliding
    ids.
  - **The probe asserts** (an integration exercise, not just unit tests, per review Finding 3): a
    **signed bump submitted over the socket is accepted** (against a **test fixture** allowlist
    holding an active key + a fixture authority StateDir — never the live revoked allowlist);
    **resubmitting the same signed document yields a deterministic result** (a committed receipt or a
    typed replay/identity deny — **never a second +1**); a **bad-signature** or **revoked/unknown-key**
    document is **rejected** (`DENY_BAD_SIGNATURE` / `DENY_KEY_NOT_ACTIVE` / `DENY_UNKNOWN_KEY`); the
    submit path performs **no host private-key read** and **no owner-UID 0700 write**; the dormant
    live allowlist maps the dashboard lever to `none(revoked-only)`; and **(rev2, Finding 1)** an
    active-key fixture whose authority `read-epoch` probe is made to fail (unit down / socket absent)
    maps the dashboard lever to `degraded(authority-unreachable)`, never `operational`.

---

## 7. How this closes rev5 Finding 3 (and satisfies the amended C4 prerequisite)

| Concern (rev5 Finding 3) | Landed / rev5 gap | C6c closure |
|---|---|---|
| **No callable submission path** | Owner can sign offline but cannot deliver the signature to the running authority through any authorized path. | §2: a new `submit --signed --socket` verb delivers `{"bump": <signed doc>}` over the C6-S control-socket owner-bump path via `send_request`; the landed handler already applies it (`transport:290-296`). |
| **`submit --signed` writes 0700 authority state** | `submit` calls `apply_bump` in-process against `--epoch-path`/`--ledger-dir`, the authority's `0700` StateDirs the owner UID cannot write. | §2.3: the new path does **no** in-process `apply_bump` and **no** ledger construction; the authority (its own user) is the sole writer of its `0700` StateDirectory. Owner only connects + sends bytes. |
| **`bump` reads a host private key** | `cmd_bump` reads/signs with `_load_owner_key` (`:190`) — a key on the harness host. | §2.3: the new path reads a **pre-signed** file and invokes **no** signing / key-load routine; the owner private key stays on the owner's offline machine. |
| **CLI verb is `build`, not `prepare`** | rev5 named a nonexistent `prepare` verb. | §1: reconciled — the real verbs are `build` / `submit` / `bump`; the offline flow is `build` (offline-sign) → `submit --signed --socket`. |
| **TEG envelope accepts no authority object; no courier inventoried** | No inventoried signed-bump courier. | §2.2: the courier is inventoried — the frozen `{"bump": <signed doc>}` envelope over `send_request`, carrying only the owner-signed document. |
| **Forward-only rotation sound but Finding 4 (idempotency) open** | rev5's rotation semantics were sound; determinism was C6d's job. | §4 carries the rotation/revoke semantics forward unchanged; §3 inherits determinism from the C6d journal (resubmit → deterministic receipt / deny, never a double-bump). |

**Amended-C4 prerequisite.** Per decomposition §7 ([AMEND-C4]) and §4, the C4 freeze prerequisite is
narrowed to **"an operational, owner-authorized, signed epoch-bump path" = C6d + C6c (+ the C6-S
socket/transport foundation)**. C6c is the slice whose completion (with C6d + C6-S) makes that
prerequisite satisfiable: a durable, recoverable epoch authority (C6d) with a **callable** authorized
owner-bump delivery path (C6c) on a **frozen** control-socket topology (C6-S). C6c does **not** depend
on C6a (`authorize_launch` is not part of the kill-lever, decomposition §0.3/§7.2). The [AMEND-C4]
contract amendment is a **separate** independently-reviewed step (decomposition §7); C6c neither
performs it nor assumes it — C6c only supplies the operational lever the amended prerequisite names.

---

## 8. Freeze, authorization, and activation

**Freeze criteria (all must hold):**
1. The callable owner submission path exists: `aq-epoch-bump submit --signed <file> --socket <path>`
   delivers `{"bump": <signed doc>}` to the running authority over the C6-S control-socket owner-bump
   path via `revocation_epoch_transport.send_request`, and the authority applies it through its
   landed `{"bump": …}` handler (`transport:290-296`) — **no new authority op**.
2. The path reads **no** host private key (no `_load_owner_key`) and performs **no** in-process
   `apply_bump` / no owner-UID write to the `0700` StateDirectory (the authority is the sole writer).
3. `submit` without `--socket` keeps its landed in-process behavior **byte-for-byte**; the landed
   `import os` defect in `cmd_bump` is fixed (one-line, with a root-cause note per Rule 19), **paired
   with an explicit deprecation note on `bump`** (rev2, Finding 3) steering owners to
   `submit --signed --socket` as the sanctioned path, so the crash fix does not silently re-bless
   `bump`'s host-key path as an equal option; the existing `_load_owner_key` age-passphrase guard
   remains the documented control if `bump` is still invoked.
4. **Composes with C6d (§3):** no change to `apply_bump`'s signature, `verify_bump`, the
   journal/two-index/`recover()`, or `Type=notify`; a resubmitted signed bump is a **deterministic
   receipt / typed deny, never a double-bump**, by inheritance from the C6d journal.
5. **Composes with C6-S (§2.4):** touches only the control-socket owner-bump path; adds **nothing** to
   the launch socket / `aq-revocation-launch-clients` group / `authorize_launch`; the owner-bump path
   stays distinct from the launch group.
6. **Forward-only rotation / revoke-on-rotation (§4)** preserved: public-only allowlist, per-request
   re-read, `status:"active"` re-checked every call, monotone `revision`.
7. **Off-is-inert byte-parity:** the authority ships `enable=false`; nothing invokes the new verb
   automatically; the dormant allowlist maps the dashboard lever to `none(revoked-only)`.
8. **(rev2, Finding 1 — MEDIUM, build-time binding, required at build.)** The dashboard
   `owner_epoch_bump_lever` `operational` state REQUIRES authority reachability (a live `read-epoch`
   probe over the control socket, `transport:283-289`) IN ADDITION to allowlist-readable + ≥1 active
   key + verb-present; an active-key-but-authority-unreachable case MUST read the distinct
   `degraded(authority-unreachable)` state, never `operational`. The §6 coverage probe (row 8) MUST
   assert this with an authority-down fixture. No state may assert "deliverable end to end" without a
   confirmed-live delivery endpoint.
9. The **`c6c-owner-submission-coverage` integration check is GREEN in both harnesses** (phase0
   `0.10.54` + bash mirror), distinct from C6d `0.10.51` / C6-S `0.10.52` / C6a `0.10.53`, per §6.
10. **(rev2, Finding 2 — LOW, HARD gate at freeze/land time.)** A dual-harness check-id collision
    check (no duplicate id across `phase0.py` AND `_aq-qa-bash`) runs at freeze/land time against the
    siblings actually landed at that moment — not merely a static "`0.10.54` is unused" assumption
    made at design time. A collision BLOCKS the land; it is never resolved by silently picking a
    different id without re-verifying both harnesses.
11. The freeze binds the exact candidate hashes, reproduces the §1 base hashes, rejects all other
    changed paths, and stops on HEAD drift.

**Authorization / activation note — the DESIGN/BUILD needs NO owner activation; P-F4 is a separate
owner act.** C6c is **default-safe**: it adds a **dormant** owner-invoked client verb to a CLI that
"nothing invokes automatically" (`aq-epoch-bump:2-4`), against an authority that ships
`enable = false;`, with an allowlist that has **zero active signers** at the anchor. Building it
performs **no epoch bump**, flips **no flag**, provisions **no key**, opens **no network** (AF_UNIX
only), and adds **no capability flag**.

- **What this slice builds (dormant):** the callable `submit --signed --socket` path, its coverage
  test, the dual-harness integration probe, and the `owner_epoch_bump_lever` dashboard section. Until
  activation the lever is observably **`none(revoked-only)`** — the path is wired but there is no
  active owner key to sign an admissible bump.
- **What the owner does at activation (P-F4 — a SEPARATE act this slice neither performs nor depends
  on):** (a) generate an Ed25519 keypair **offline** (private key never on the harness host); (b)
  advance the **public** allowlist `config/aqos/c6-owner-public-keys.json` **rev-4 → rev-5**, adding
  the new owner public key with `status:"active"` (e.g. `owner-2026-09`) — a **public-only monotonic
  advance** that mutates **no frozen code bytes** and is itself hash-bound + owner-authorized (rev5
  §2.3/§6; decomposition §4 "Owner activation needed? Yes — P-F4"). Only after P-F4 does the lever
  read **`operational`** and can a real signed bump advance the epoch.

There is **no owner activation act tied to the C6c build**. Enabling the authority unit and P-F4 are
separate, later owner acts. The baseline stays dormant.

**Dependencies / order.** Requires **C6d** (durable, recoverable epoch + reachable authority) and
**C6-S** (the frozen socket/group model + the control-socket owner-bump path this submission lands
on). **Does NOT require C6a.** **Fans out from C6-S in parallel with C6a** (decomposition §8).
Completing C6c (with C6d + C6-S) is the event that makes C4 freeze-eligible under the amended
prerequisite (§7).

---

**RECORD: PREPARED_ONLY revision 2. No implementation, freeze, activation, epoch bump, provider
traffic, deployment, restart, network authority, or flag flip is granted by this document. C6c is the
owner-submission slice of `C6-DECOMPOSITION-20260924.md` (§4, §8); it requires its own independent
binding review → hash-bound freeze → default-OFF build, per the decomposition's per-slice contract.
This document closes rev5 (`f68ccf91`) Finding 3 (HIGH) / rev4 Finding 4 at design level: it
inventories a CALLABLE authorized submission path (`aq-epoch-bump submit --signed --socket` delivering
`{"bump": <signed doc>}` to the running authority over the C6-S control-socket owner-bump path via
`revocation_epoch_transport.send_request`) that needs **no host private key** and **no owner-UID 0700
access** — the authority's landed `{"bump": …}` handler applies the verified bump itself. It composes
on top of C6d's journal (resubmit → deterministic receipt / DENY_REPLAY / DENY_IDENTITY_CONFLICT,
never a double-bump; §3) and C6-S's frozen control-socket owner-bump path (kept distinct from the
launch group; §2.4), contradicting neither. Forward-only public-key rotation / revoke-on-rotation is
carried forward unchanged (§4). The DESIGN/BUILD is dormant and needs no owner activation; **P-F4**
(offline keygen + public-only allowlist advance rev-4 → rev-5) is a SEPARATE owner act this slice
neither performs nor depends on (§8). A landed latent defect (`cmd_bump` uses `os` without importing
it, `aq-epoch-bump:147,201`) was found, reported, and folded as a bounded one-line fix (Rule 19).

**rev2 applies the three binding fixes from `CODEX-C6C-DESIGN-BINDING-REVIEW-20260924.md`** (rev1,
FREEZE-ELIGIBLE, no HIGH): (1) Finding 1 (MEDIUM, build-time binding) — the dashboard
`owner_epoch_bump_lever` `operational` state now REQUIRES authority reachability (a `read-epoch`
probe, `transport:283-289`) in addition to allowlist+active-key+verb, with a new distinct
`degraded(authority-unreachable)` state and a bound §6 probe assertion, so the kill-lever never
false-greens when a key is active but the authority is down (§1, §6, §8 criterion 8); (2) Finding 3
(LOW) — the folded `import os` fix on `cmd_bump` is paired with an explicit deprecation note steering
owners to `submit --signed --socket`, so reviving `bump` does not silently re-bless the host-key path
(§1, §8 criterion 3); (3) Finding 2 (LOW) — the dual-harness check-id collision check is elevated to a
HARD gate at freeze/land time, verified against siblings actually landed rather than a static
`0.10.54`-is-free assumption (§6, §8 criterion 10). No change to the submission mechanism,
idempotency-by-C6d, or rotation semantics.**
