---
doc_type: design-packet
id: acp-p0-design-20260816
title: ACP-P0 — approval-request record schema + audited action contract
status: draft
parent_prd: approval-control-plane
slice: acp-p0
implementation_authority: cheapest-eligible-implementer-lane
runtime_authority: audited-aq-action-path
reviewer: pending
date: 2026-08-16
---

# ACP-P0 — approval-request record + audited action contract

Foundation slice of the Approval Control Plane. No UI, no WebAuthn, no keys yet. It defines the
**record everything else binds to** and the audited path that executes an approved request. Ratified PRD:
`.agent/PROJECT-APPROVAL-CONTROL-PLANE-PRD.md` (R2, owner-ratified 2026-08-16).

## Why this is P0 (and why it's crypto-free for the human)
Later slices (P1 WebAuthn signing service) close the "what-you-see-is-not-what-you-sign" hole by having the
signer **fetch the canonical request itself by id** and derive the challenge from it. That only works if the
record is (a) closed/bounded, (b) canonically serializable to a stable hash, (c) split into a plain-language
layer the human reads and a technical layer they never need to. P0 builds exactly that substrate. It requires
zero human crypto — it is a schema + a state machine + an executor contract.

## The record: `aq.approval-request.v1`
A closed schema (unknown keys rejected). Three layers with a hard privacy boundary between them.

```jsonc
{
  "schema": "aq.approval-request.v1",
  "request_id": "<ULID>",              // stable id; P1 signer fetches BY THIS, never trusts caller bytes
  "created_at": "<ISO8601-UTC>",
  "created_by": "<lane/agent id that is ASKING>",
  "status": "pending",                 // state machine below

  // LAYER 1 — plain-language. The ONLY thing the surface shows by default.
  "summary": {
    "title":   "Activate the scheduler-context issuer",   // <= 80 chars, imperative
    "what":    "Lets the system issue signed scheduling permits.",
    "why":     "Turns on C2-SCI so the scheduler can sign contexts.",
    "impact":  "medium",               // low | medium | high  (drives surface prominence)
    "reversible": true
  },

  // LAYER 2 — the bounded, machine-executable action. NOT free text.
  "required_authority": "owner-webauthn",   // enum; P0 only defines it, P1 enforces
  "action_manifest": {
    "runbook": "activate-signer-service",   // MUST name a registered runbook (closed set)
    "params":  { "service": "c2-scheduler-context-issuer" },  // schema-validated per runbook
    "declared_effects": ["provision-key","wire-allowlist","emit-grant","rebuild"]
  },

  // LAYER 3 — technical trail. Hashes/paths/keys live ONLY here. Never surfaced by default.
  "technical_trail": {
    "design_sha256": "<hex>",
    "target_files":  ["config/aqos/..."],
    "grant_subject": "c2-ACTIVATE"
  },

  // integrity — binds the whole record; P1 recomputes this and derives the WebAuthn challenge from it.
  "binding": {
    "canonical_hash": "<sha256 of canonical bytes of the record MINUS the binding block>",
    "requester_sig":  "<optional lane signature over canonical_hash>"
  }
}
```

### Design invariants (each becomes a test)
1. **Closed schema** — unknown top-level or per-layer keys are rejected (no smuggling fields past the surface).
2. **Privacy boundary (the load-bearing one)** — `summary` MUST contain no hex-64, no `/run/secrets`, no
   file path, no key_id, no socket path, no "sha256". Enforced by a validator + a golden privacy test. This
   is what makes the surface beginner-safe: the human physically cannot be shown crypto.
3. **Bounded action** — `action_manifest.runbook` MUST be a member of the registered runbook set;
   `params` MUST validate against that runbook's own param schema. Approving cannot execute an arbitrary
   command — only a named, pre-reviewed runbook with typed params. (Directly closes PRD-R2 hole "downgrade/
   arbitrary-action": there is no free-form action to smuggle.)
4. **Canonical + stable hash** — deterministic serialization (sorted keys, UTF-8, no whitespace drift) over
   the record minus `binding`, hashed sha256. Same record → same hash on any machine. Golden vectors pin it.
   This hash is the anchor P1 signs; if it isn't reproducible, WYSIWYS breaks.
5. **State machine** — `pending → approved → executed` (happy path);
   `pending → denied` (terminal); `approved → failed` (executor error, terminal); `pending → expired`
   (TTL, terminal). No other transitions. Each transition is an audited event.
6. **Agent-inaccessible at rest** — the record store is root-owned / confined-service-owned, mode such that
   the requesting agent can WRITE a request (append) but cannot MUTATE an existing one or read the
   authority's view. (P0 defines the contract; the confined store lands with P1's service. P0's store is a
   spec + a reference file layout under a root-owned StateDirectory.)

## The audited action contract (executor)
On an approved request (P0: approval is a trusted test stub; P1 replaces the stub with a real WebAuthn
assertion — the executor contract does NOT change):

1. Load the record by `request_id`. Re-validate schema + recompute `canonical_hash`; ABORT if it differs
   from the stored `binding.canonical_hash` (tamper / drift → fail closed, audited).
2. Resolve `action_manifest.runbook` in the runbook registry; ABORT if unknown or params invalid.
3. Execute the runbook through the **existing audited AQ action path** (integration contract #4:
   human-controls → audited AQ actions). Every step emits an `aq-event`; nothing runs outside the audit log.
4. Transition `approved → executed` (or `→ failed` with the error) as a final audited event.

The executor NEVER interprets `summary` or free text — it acts ONLY on the typed `action_manifest`. What the
human read (Layer 1) and what the machine did (Layer 2) are bound by `canonical_hash`, so they cannot diverge.

## Validation goals (ground-truth signals for the tracker)
- **golden-canonical** — fixed record → pinned `canonical_hash` (cross-machine determinism).
- **privacy-leak** — property test: no generated `summary` leaks hex-64 / path / key_id / socket / "sha256".
- **closed-schema** — unknown-key and wrong-type records are rejected.
- **bounded-action** — an `action_manifest` naming an unregistered runbook, or bad params, is rejected.
- **state-machine** — every illegal transition is refused; every legal one emits an audited event.
- **executor-tamper** — a record whose stored hash ≠ recomputed hash aborts before any effect runs.
- **audit-completeness** — executing a request produces the full event chain (load→resolve→effect*→terminal).

## Scope fence (what P0 is NOT)
No WebAuthn, no signing service, no owner keys, no web surface, no NixOS confined-service module — those are
P1/P2. P0 is pure Python + schema + tests, committable and unit-validatable with zero rebuild and zero human
crypto. It is a bounded implementer slice.

## Dispatch (Rule 17 — cheapest-eligible implementer)
Architect/design: this packet (flagship, analysis tier). Build: route to the cheapest healthy implementer
lane once available. Current lane state (2026-08-16): Codex DOWN until Aug 21; local lane returned an empty
response twice this session (flaky); tier0 commits are environment-blocked on a missing `pydantic` (backlog:
tier0-gates-blocked-missing-pydantic) pending the owner's next rebuild. So the build is **queued behind the
rebuild + a healthy lane**, NOT self-implemented by the orchestrator. Independent review of THIS design packet
(local + Codex-on-return) precedes build per the PRD's per-slice design→review→freeze→build.

## Review fold — local Qwen (2026-08-16, verdict: right shape; 3 findings folded)
7. **Layer-1↔Layer-2 semantic binding (NEW — local #1, the important one).** A hand-written plain-language
   `summary` could drift from what `action_manifest` actually does — the human approves a benign-sounding
   card for a risky action. Mitigation: `summary` is NOT free prose. Each registered runbook ships a
   **summary template** (title/what/why/impact) rendered from its typed `params` + a declared risk class;
   the requester fills params, the system renders the human text. `impact` is DERIVED from the runbook's risk
   class, not asserted by the caller. So the words the human reads are a deterministic projection of the same
   typed manifest the executor runs — they cannot diverge. Free-text override is forbidden at P0.
8. **Hash scope = all immutable content (local #2).** `canonical_hash` covers every content field
   (summary + required_authority + action_manifest + technical_trail) EXCEPT `binding`; and those fields are
   write-once (immutable after creation — enforced by the append-only store, invariant 6). `status`,
   `created_at`, `request_id` are set at creation and frozen; any post-creation content mutation is rejected,
   not re-hashed. Test: mutate any content field after creation → store refuses.
9. **No runtime param injection (local #3).** The executor runs ONLY the `params` present in the hashed
   record (executor step 1 already recomputes + compares the hash before any effect). No caller may inject or
   override params at execute time; a mismatch aborts. Stated here as an explicit invariant + a test.
Local also confirmed the illegal transition: `pending → approved` without a passing `canonical_hash`
verification is refused (matches invariant 5 + executor step 1).

Consensus so far: local Qwen (verdict yes, above) + Antigravity's PRD-level WYSIWYS/replay/downgrade findings
(folded in PRD R2). Codex binding design review pending its return (Aug 21) before build.

## Review request (independent, per slice)
Reviewers, assess: (1) is `aq.approval-request.v1` the right closed shape; (2) does the Layer-1/Layer-3
privacy boundary + the `canonical_hash`-minus-binding anchor actually deliver WYSIWYS for P1; (3) is the
bounded `action_manifest` (registered-runbook + typed-params) sufficient to prevent arbitrary-action smuggling;
(4) any missing validation goal or illegal state transition.
