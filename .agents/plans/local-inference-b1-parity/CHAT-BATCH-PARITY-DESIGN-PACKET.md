# Foundation B1 — Chat/Batch Parity (Shadow) Design Packet

**Slice:** B1-PARITY (local-inference chat/batch shadow parity oracle)
**Track:** AQ-OS Unified Program — Foundation B1 (L-series), the "then chat/batch
parity in shadow" step after L2B-B.
**Author:** fable-5 (orchestrator/architect). **Status:** DESIGN PACKET — pre-authorization
(design → independent review → PREPARED_ONLY authorization → owner activation → implement).
**Parent architecture:** `.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md`;
**PRD:** `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md`.

## 0. Scope resolution (why this is NOT already done by L2B-B)
L2B-B (activated 2026-07-21, committed) enforced *pure payload normalization* across
`/v1/chat/completions` and `/v1/completions` (batch) and routed llama-bound requests
through `build_llama_payload()`. It normalized each path; it did **not** prove the two
CALLER ADAPTERS are equivalent. The PRD keeps the equivalence proof separate:
- L2A acceptance (line 417): "flagship, standard, budget and deterministic callers
  create **equivalent valid requests**."
- L2B-B (line 433): "Preserve streaming content/usage **equivalence**."
- L4 (line 448): duplicated routing/prompt/budget/retry/authority logic is removed
  "**after parity evidence passes**."

So the missing artifact is the **parity evidence oracle** itself: an offline,
report-only proof that the batch adapter (`delegate-to-local` → `dispatch.py`
build_llama_payload) and the interactive chat adapter (`aq-chat`) emit
**byte-equivalent canonical requests** through the L2B kernel, across caller tiers
and task shapes. This slice produces that evidence in SHADOW (no routing change),
unblocking L3/L4 live adoption. It is distinct, additive, and low-risk.

## 1. Objective
A pure, offline **chat/batch parity oracle** that, for a fixed matrix of caller
inputs, builds the canonical request via BOTH adapters and asserts byte-equivalence
of the canonical fields the PRD names (line 480): mode, profile, model, task_type,
role, tools, budgets, fallback, version — plus streaming content/usage decoder
equivalence (L2B-A observation contract). Divergence FAILS CLOSED with a typed,
field-level diff. Report-only: no live routing, caller, or tool-execution change.

## 2. Parity matrix (fixtures)
Caller tier × task shape, each producing one canonical request per adapter:
- **Tiers:** flagship, standard, budget, deterministic (the PRD's four).
- **Shapes:** chat (messages[]) and batch (prompt / completion). Where a shape is
  legitimately adapter-specific (chat messages vs batch prompt), the oracle
  compares the NORMALIZED canonical projection, not the raw input — the equivalence
  is over the canonical request the kernel emits, not the surface input.
- Golden fixtures freeze the expected canonical request per (tier, shape) so the
  oracle is deterministic and offline (no live llama/switchboard).

## 3. Design
- **New** `scripts/testing/test-local-inference-chat-batch-parity.py` — the oracle:
  loads the parity fixtures, invokes the two adapters' canonical-request builders
  (import `build_llama_payload` and the aq-chat canonical path; NEVER call live
  services), computes the field-level canonical projection, asserts byte-equivalence
  per §1, and emits a typed parity report (pass/fail + per-field diff). Pure/offline.
- **New** `scripts/testing/fixtures/local-inference-chat-batch-parity-golden.json` —
  the frozen caller matrix + expected canonical projections + a manifest digest
  (self-consistency, like the L2B golden fixture).
- **No modification** to any live adapter, router, or the frozen L2B files — the
  oracle READS the existing canonical builders. This keeps the slice report-only and
  off every frozen-manifest ceiling (no re-pin needed).

## 4. Acceptance criteria
- For every (tier, shape) in the matrix, the two adapters' canonical requests are
  byte-equivalent on the PRD line-480 fields; streaming content/usage decoder
  observations are equivalent (or explicitly, typed-differently where the contract
  permits — documented, not silent).
- Divergence FAILS CLOSED with a field-level diff (no "acceptable" narration of a
  real mismatch).
- Oracle is pure + offline (no live service dependency; runs in CI/tier0-eligible).
- Zero change to live routing/callers/tools; touches no frozen-manifest file.
- Independent review (any eligible flagship/codex, not the author) + never-skip-local.

## 5. Bound file ceiling (for the authorization to freeze)
Exactly 2 NEW files: the oracle test + the golden fixture. No modifies. This makes
the eventual PREPARED_ONLY authorization small, fail-closed, and collision-free.

## 6. Open questions for design review (partially resolved by code inspection)
1. **RESOLVED (materially) — the two adapters do NOT yet share one canonical
   builder.** Batch: `scripts/ai/lib/dispatch.py:build_llama_payload` is an
   importable, pure function (L2B-B routed llama-bound requests through it). Chat:
   `scripts/ai/aq-chat`'s `_build_coordinator_delegate_payload` /
   `_build_fast_path_payload` are **class methods coupled to client state**
   (`self.switchboard_url`, fast-path vs coordinator branching) targeting the
   **coordinator/switchboard** `/v1/chat/completions`, NOT the direct-llama
   `build_llama_payload`. Consequences:
   - The oracle cannot simply import two pure builders. Options: (a) drive a minimal
     aq-chat harness to invoke its builder methods with stubbed I/O, or (b) a thin
     PURE-EXTRACTION of aq-chat's canonical builder as a PREREQUISITE micro-slice
     (recommended if the coupling is heavy — keep it a SEPARATE slice, do not fold).
   - More important: the oracle's real value is exposing **whether chat and batch
     currently converge on the canonical form at all** — they use different builders
     and transport targets today, so the honest expectation is the oracle will
     surface residual divergence that L3/L4 adoption must close. That is the point:
     the parity oracle is the *evidence instrument*, and a first run showing
     divergence is a valid, useful result (it scopes L3/L4), not a failure of the
     slice.
   - Ceiling caveat: if option (a) (harness-drive) works, the 2-new-file ceiling
     holds. If option (b) (extraction) is required, that extraction is its own
     prerequisite slice with its own authorization — this packet stays report-only
     and does not modify aq-chat.
2. Which streaming/usage equivalence differences are contract-legitimate (chat SSE
   vs batch buffered) vs true divergences the oracle must fail on? (Design review to
   enumerate; L2B-A decoder observations are the reference.)
3. Does this offline oracle satisfy the UNIFIED-PROGRAM-PLAN "chat/batch parity in
   shadow" B1 exit item on its own, or is a live-shadow (dual-run against a running
   service) parity pass also required before declaring B1 complete? **Recommend:**
   offline oracle first = this slice; live-shadow parity = a follow-on L3-adjacent
   slice (needs a running service + fresh authorization).

## 7. Next step
Independent design review of this packet (resolve §6), then draft
`B1-PARITY-IMPLEMENTATION-AUTHORIZATION.md` (PREPARED_ONLY, 2-file ceiling, frozen
predecessor hashes, single-use owner activation) matching the L2B-B / B2-C1 format.
