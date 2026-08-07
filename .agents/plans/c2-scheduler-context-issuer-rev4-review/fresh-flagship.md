# C2 Scheduler-Context Issuer rev4 — Independent Binding Review

- Reviewer: fresh Claude flagship (Opus 4.8), independent binding — Codex-substitute per Rule 18
- Date: 2026-08-07
- Design under review: `.agents/plans/aqos-foundation-c/C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md` (rev4)
- Method: every claim verified against actual repo code, not the design's self-description.
- **VERDICT: PASS**

## Baseline anchor verification (all EDIT/NO-EDIT hashes)

All four anchored SHA-256 values match the working tree exactly (`sha256sum`):

| Path | Design anchor | Measured | Match |
|---|---|---|---|
| `ai-stack/switchboard/capability_lease_gate.py` | `0686c6fa…85ed8cc8` | `0686c6fa…85ed8cc8` | ✓ |
| `scripts/ai/lib/dispatch.py` | `1b083b10…2e01dd92` | `1b083b10…2e01dd92` | ✓ |
| `nix/modules/services/default.nix` | `c3b6d18e…decdec7ce4`* | `c3b6d18e…dec7ce4` | ✓ |
| `nix/modules/services/switchboard.nix` (NO EDIT) | `9b090af1…c93dfba` | `9b090af1…c93dfba` | ✓ |

All NEW files confirmed absent by design: `scheduler_context_issuer.py`, `scheduler_context_transport.py`,
`c2-scheduler-context-issuer.nix`, `config/aqos/c6-scheduler-signer-keys.json`,
`config/schemas/scheduler-lease-gate-decision.schema.json`. The dropped bare
`config/scheduler-context-signing-public-key` is also absent (sole-source claim intact — nothing to leak a
status-less pubkey through). ALA anchors present and working: `capability_lease.verify_authoritative`,
`config/aqos/lease-signer-keys.json`.

## Assessment against the 7 points

### 1. TRUST MODEL — SOUND. Neutralizes caller-indistinguishability. (§4, §3, §1 rev2)
Verified `switchboard.nix:552` → `User = cfg.primaryUser;` — the switchboard genuinely runs as the human
owner uid, so `SO_PEERCRED`/group on the issuer socket cannot separate the legit caller from any other
owner-uid process. The design's fix — authority = an independently-verified Ed25519 signed lease, peer/group
= defense-in-depth only — is the correct resolution. `verify_authoritative` (capability_lease.py:361-439) is
genuinely fail-closed and un-forgeable by a shell caller: scheme-pinned to `ed25519` BEFORE any key lookup
(line 390), **no reachable HMAC/dev-key fallback**, deny-ALL on malformed/missing `keys_json` (394-397),
unknown key-id denies (408), and `status != "active"` denies re-checked every call (413). A shell caller
cannot mint the signature, so peer-uid indistinguishability no longer confers authority. Claim holds.

### 2. OBLIG-1 (expiry + epoch layered on top) — SOUND, and demonstrated by live sibling code. (§Rev3.2, §4)
`verify_authoritative` returns "signed by an active key" only — it does NOT call `is_expired`/`epoch_stale`
(confirmed: the function body ends at signature verify, line 437). The design's mandate that the issuer must
independently reject on past `expires_at` or non-matching `revocation_epoch`, re-deriving the tuple from the
lease's OWN signed fields, is exactly the pattern already live in the enforce path
(`capability_lease_gate.py:_admission_verify`, 602-624): `verify_authoritative` → then `cl.is_expired(lease)`
→ `cl.epoch_stale(lease, current_epoch)`, all off the signed lease, never caller input. The docstring there
explicitly names the fail-open this prevents ("absent this layering a stale/expired Ed25519 lease would
admit"). The C2 issuer replicating this is well-grounded in real code. Claim holds.

### 3. SINGLE-USE LEDGER keyed on {lease_id, grant_digest} — SOUND; correlation fields do not widen authority. (§Rev3.3, Q-R3-1)
The design correctly places the 1:1 lease→context enforcement at the issuer (a NEW file, absent by design),
keyed on `{lease_id, grant_digest}` = one context per lease, and treats `{task_id, principal, dispatch_mode}`
as caller-supplied DISPATCH-correlation that never enters the authority derivation (authority is re-derived
from the lease's signed fields per §4). Since those three fields never widen what the context authorizes,
caller-supplying them is safe. This is the right layer: a per-task key would re-open one-lease-many-contexts.
Q-R3-1 is answered correctly.

Note (LOW, factual precision — not a defect): §Rev3.3 asserts "slot_queue's single-use is on the CONTEXT
digest." `scripts/ai/lib/slot_queue.py` today implements only queue/acquire/release — it has NO
context/digest/single-use surface at all. That makes the design's conclusion (enforce 1:1 at the issuer)
*more* necessary, not less, so soundness is unaffected — but the eventual implementer should verify the actual
slot_queue single-use surface exists (or is added by C6) rather than assume it.

### 4. EPOCH SOURCE (Q-R3-2) — SOUND; mismatch denies. (§Rev3.2/.4)
Verified the pre-C6 authoritative epoch source: `capability_lease_gate.py:114` →
`DEFAULT_EPOCH_PATH = config/capability-lease-epoch`, resolved via `resolve_current_epoch` (203-238), current
on-disk value `0`. An unresolvable epoch degrades/denies rather than treating epoch as absent
(`enforce()` 672-674: `epoch-source-unresolvable` → `_degrade`). The design naming this file pre-C6 and the
C6 epoch authority once active, with a mismatch denying, matches live behavior. Q-R3-2 answered correctly.

### 5. SIGNER AUTHORITY — SOUND. (§2, §1)
Dedicated `aq-c2-scheduler-context-issuer` principal, SOPS `0400` private key at `/run/secrets/…`,
fail-closed `signer-unavailable` deny on key unreadable/malformed, no env/bootstrap/unsigned fallback. Sole
verifier source `config/aqos/c6-scheduler-signer-keys.json` (status-bearing; revoked never verifies) — a
distinct key family from the C6-P0 owner allowlist and from the lease-signer keys. All design-only (files
absent, no `secrets.nix` entry yet — confirmed). The status-bearing sole-source pattern mirrors the working
`lease-signer-keys.json` (verified: single `active` key, `status` field re-checked on every verify call). No
regression to the "revoked key still verifies via a bare status-less file" gap. Claim holds.

### 6. DEFAULT-OFF + two-flag independence + no switchboard.nix edit — SOUND. (§4, §1)
`CAPABILITY_SCHEDULER_LEASE_GATE` is the pre-existing C6 gate flag (C6-DESIGN §173/§206, env-contract default
`0`) — distinct and separately owner-gated. `CAPABILITY_SCHEDULER_CONTEXT_ISSUER` is the NEW issuer flag, not
present in code (design-only, correct). The two are structurally independent: the issuer flag controls
minting; the C6 gate flag controls scheduler enforcement — no conflation path exists. The NO-EDIT
switchboard.nix anchor holds byte-parity (hash match); the design correctly routes the switchboard's role as
an OUTBOUND UDS client call from `capability_lease_gate.py`, not a switchboard.nix edit. `CAPABILITY_ASYMMETRIC_LEASE=1`
is confirmed live at `switchboard.nix:467` (post-flip state the rev4 re-anchor accounts for). Claim holds.

### 7. Fail-open / oracle / fail-closed-breakage scan — NONE FOUND.
- No fail-open: the issuer mints only after `verify_authoritative` PASS + independent expiry + epoch checks +
  single-use ledger; every failure maps to a typed deny. An unverifiable/expired/replayed lease cannot mint.
  The one fail-open the design guards against (verify-authoritative-without-validity-layering) is the exact
  live pattern in `_admission_verify` — correctly carried into the C2 design.
- No oracle: dashboard/audit fields are explicitly low-cardinality (no lease id, grant, prompt, path,
  signature); typed deny reasons don't leak secret material.
- No fail-closed dispatch breakage: with the flag OFF (default) the switchboard makes no issuer call, the
  service is not enabled, and `dispatch.py` preserves byte-parity — verified `dispatch.py` today does NO
  scheduler-context deserialization (the ingress adapter is a future NEW edit; no caller-supplied context is
  accepted today), so there is no legacy path to break.

## Minor notes (LOW, non-blocking)
- §3 (rev2 quote) cites `switchboard.nix:542` for `primaryUser`; the actual line is `552` (post-flip drift).
  The FACT (`User = cfg.primaryUser`, human uid) is verified true; only the inline line number is stale. The
  rev4 re-anchor already updated the file hash. Cosmetic.
- §Rev3.3 slot_queue "single-use on context digest" is a forward claim; slot_queue.py has no such surface
  today (see point 3 note). Does not affect soundness.

## Conclusion
All rev4 anchor hashes match. The trust model correctly neutralizes the human-uid caller-indistinguishability
gap by rooting authority in the un-forgeable Ed25519 signed lease, with peer/group as defense-in-depth. OBLIG-1
expiry+epoch layering, single-use {lease_id, grant_digest} ledger, epoch source, fail-closed signer authority,
and two-flag independence all verify against live code, and the OBLIG-1 pattern is already proven in the live
enforce path. No fail-open, oracle, or fail-closed dispatch breakage found. The two LOW notes are
non-blocking. Design is safe to hash-bound freeze.

**VERDICT: PASS**
