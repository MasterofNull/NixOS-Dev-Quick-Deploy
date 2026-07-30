> **DEFERRED 2026-07-29 (owner-ratified resequence).** Effect-brokering now follows C3b
> (execution cells) + C4 (network profiles) — in-process brokering cannot safely precede
> confinement (codex 3-round review). This design is retained with all findings; it resumes
> after C3b+C4 land and an accurate signed per-handler effect inventory replaces the
> `first-party-tools.json` guesses. NEXT ACTIVE SLICE: C3b. See DESIGN-PACKET.md §8 RESEQUENCE.

# Foundation C — C3a-2 Forward Scope: Delegation + Signed-A2A (deferred)

**Status:** FORWARD-SCOPE stub (not yet a full design). Split out of C3a per codex rev2
re-review (`codex-20260729-172222`, slice-size judgment: split mandatory). **Bound to the
accepted C3a-1 hash** — C3a-2 gets its own full design→review→freeze→activation cycle only
after C3a-1 is accepted and frozen. This stub records the deferred findings so they are not lost.

## Scope
The delegation half of the effect brokers: `delegate_to_remote` + inbound A2A acceptance.
Everything write/secret/read/exec-deny/network-deny is C3a-1; everything below is C3a-2.

## Deferred findings to fold in the C3a-2 design (from the codex rev2 re-review)
- **BLOCKING-4 — A2A signer chronology.** The remote lane has no local HMAC key, yet the
  signature must cover `output_digest` + heartbeat values that exist only *after* remote
  execution. Resolve by naming the signer and the signing instant: the **local broker** signs
  after reading the quarantine blob and attests the broker's **locally recomputed** digest (not
  remote identity). If remote authenticity is ever required, define a separate remote-verification
  mechanism — never hand the local HMAC key to a remote principal.
- **BLOCKING-5 — verify-before-write + replay uniqueness.** Remote writes ONLY an untrusted
  quarantine blob; the broker reads → verifies (sig/digest/deadline/child-lease/path/schema) →
  **atomically reserves** the idempotency token → commits via the C3a-1 write broker. Uniqueness
  domain must be a **signed canonical task/request identity**, `(child_lease_id, idempotency_token)`
  (existing inbox locks are task-ID-scoped only). Lock/reserve on a collision-resistant digest of
  the complete key; define `reserved → committed | failed` crash recovery so a reserved token
  cannot leave ambiguous acceptance state.
- **BLOCKING-6 — heartbeat / exec-delegation coupling.** Deterministic heartbeat: signed
  monotonic `heartbeat_seq` + trusted receipt time; state machine `live → pending-late → dead`
  with irreversible append-only transitions; replayed/duplicate seq rejected; `dead` → acceptance
  denied.
- **SHOULD-2 — `allowed_gap` must be signed** (bound into the child authority), not a free config
  value; resolve alongside the signer question.

## Ceiling (indicative — pinned at C3a-2 freeze)
NEW A2A envelope schema; EDIT `scripts/ai/aq-antigravity-inbox` (+ receipt schema) for atomic
idempotency reservation + signed heartbeat records; EDIT the delegate broker in
`ai-stack/switchboard/effect_brokers.py` (from C3a-1's deny-stub to the real quarantine→verify→
commit path); tests. Uses the C3a-1 write broker for the final commit; consumes the C3a-1
per-tool `VerifiedToolLeaseContext`.

## Dependency
C3a-2 cannot be frozen until C3a-1 is accepted (it reuses the write broker + per-tool context +
signed classification). It does not depend on C3b, but a delegated write that lands as an
arbitrary process still routes through C3b confinement once that exists.
