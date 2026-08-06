# Binding Independent Review — C6-P0 rev3 + C2 Scheduler-Context Issuer

Reviewer: fresh Claude Opus flagship, independent of author (separate session, no shared reasoning
state; all factual claims re-derived from files). Rule 18 binding.
Date: 2026-08-06. Advisory lanes (local Qwen, Antigravity, codex) folded/queued separately.

## Verdicts

- **C6-P0 Trust Anchors rev3 → PASS** (authorizes freeze only, NOT build/activation), contingent on
  the parent-C6 schema-ownership amendment (applied 2026-08-06). The narrowing to declarative-only
  is honest — it withdraws the unspecified issuer/transport claims rather than hiding them.
- **C2 Scheduler-Context Issuer rev1 → REQUEST_REVISION** (2 HIGH + 1 LOW-MED). Superseded by rev2.

## The HIGH defect (confirmed by the reviewer AND re-verified by the orchestrator)

The switchboard hosting the C2 gate runs as `cfg.primaryUser` (`switchboard.nix:542`; gate imported
at `switchboard.py:1253`) — the **human owner uid**. Therefore `SO_PEERCRED` + group membership on
the issuer socket cannot distinguish the legitimate switchboard client from any other owner-uid
process (shell, `delegate-to-local`, compromised tool). Combined with rev1's issuer trusting a
caller-asserted ALLOW, an owner-uid process could present a fabricated `{ALLOW, principal, task}`
and receive a validly-signed context. Peer-uid was not authority.

## Closure in rev2 (`C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md`, revision 2)

- **Findings 1+2 (HIGH):** authority moved from peer-uid to the **already-Ed25519-signed C2 lease**.
  The issuer verifies the presented lease signature (lease-issuer public key), re-checks
  freshness/epoch, and re-derives the tuple from the lease's own signed fields — never a
  caller-asserted ALLOW. A shell caller cannot forge a signed lease; `SO_PEERCRED` is
  defense-in-depth only. The switchboard-as-human-uid fact no longer matters.
- **Finding 3 (LOW-MED):** `config/aqos/c6-scheduler-signer-keys.json` (status-bearing) is the SOLE
  signer-verifier source; the status-less bare public-key file is dropped.
- **Doc-1 Finding 2 (MED, parent-C6):** amendment added to `C6-DESIGN-AND-AUTHORIZATION.md` marking
  the two schemas as C6-P0-provided verify-only anchors at C6-main freeze.

## What the review confirmed was already correct (do not re-litigate)

Signer authority (SOPS `/run/secrets` `0400`, dedicated principal, rotation/revocation, fail-closed
`signer-unavailable`); the SOPS re-encrypt hazard flagged HARD; key isolation from switchboard
(separate uid); issuer hosted as its own default-OFF service independent of the disabled epoch
authority; two-flag independence.

## Combined recommendation (reviewer)

The C6→C4 chain cannot freeze on the rev1 bytes. C6-P0 rev3 is freeze-ready once the parent-C6
amendment lands (done). The C2 issuer slice required the trust-model revision (done in rev2). rev2
now needs a fresh independent PASS before freeze.

## Advisory lanes (folded 2026-08-06)

- **Local Qwen (never-skip, advisory):** independently CORROBORATED the flagship's HIGH finding —
  flagged "SO_PEERCRED (UID/GID) to authenticate the switchboard is fragile" as a trust-boundary
  violation. Also raised replay-via-missing-nonce. Verification: replay/single-use is ALREADY
  covered — parent C6 §3.1 makes the context single-use (`slot_queue` durably records the context
  digest before a reservation and refuses replay/digest conflict) + `context_id` + bounded expiry.
  No new unaddressed defect; the concern is a re-review verification item (already queued for codex).
- **Antigravity:** dispatched via the sanctioned `--loop` lane; ran async into its agent loop
  (no inline verdict returned this cycle). Untrusted-advisory regardless; not gate-clearing.
- **Codex:** confirmatory queued (rev2 subject) — verify the lease-verification seam + single-use.

Consensus: the binding (flagship) verdict stands; local corroborates; rev2's signed-lease trust
model + parent-C6 single-use enforcement address both HIGH findings. rev2 needs a fresh binding PASS.
