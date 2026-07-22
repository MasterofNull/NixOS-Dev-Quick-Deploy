# Stream Authorization Re-Review — Independent Flagship Verdict

**Reviewer:** Claude (claude-opus-4-8), fresh independent session, no prior stake
**Date:** 2026-07-20
**Mandate:** Re-review three PREPARED_ONLY implementation authorizations whose companion
Antigravity review docs cited subject hashes that did not match live files. Each subject
SHA-256 recomputed locally with `sha256sum` and confirmed against the expected value.

---

## Recomputed Subject Hashes (all CONFIRMED)

| # | Subject | Recomputed SHA-256 | Expected | Match |
|---|---------|--------------------|----------|-------|
| 1 | `.agents/plans/aqos-foundation-b3/B3-C1-CANON-COMPILER-AUTHORIZATION.md` | `d6676252dc30061d58d9a2f8d5339cc2fc828b59eb3f41a6abc2552b746621ad` | `d6676252…621ad` | ✅ |
| 2 | `.agents/plans/verified-factory/VF-7-EVIDENCE-PATH-AUTHORIZATION.md` | `71c5df38e736c48d86371c9aff294299e1c1dd0896adb80e4186b762547a1741` | `71c5df38…a1741` | ✅ |
| 3 | `.agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION.md` | `b9055bb6a763189fd0b5fbc054ead4fc6a41d41ed117181039f0ce67d62f7cb8` | `b9055bb6…f7cb8` | ✅ |

All three live files match the expected hashes. My verdicts below are bound to these exact bytes.

---

## B3-C1 — Canon-Compiler Shadow — PASS

- **Ceiling:** Explicit 5-file ceiling; §2 CAUTION declares a MANDATORY FAIL-STOP on any 6th
  file or any grant of runtime authority. Fail-stop present and unambiguous. ✅
- **Bound targets real:** Only MODIFY is `scripts/governance/tier0-validation-gate.sh` (EXISTS,
  verified). The 4 NEW files land in real dirs (`scripts/governance/`, `config/schemas/`,
  `scripts/testing/`, `.agents/plans/aqos-foundation-b3/`). No phantom path. ✅
- **Invariants safe:** Non-authoritative read-only generator; pure byte-for-byte determinism;
  no network / no FS mutation / no DB / no exec; fail-closed non-zero exit on invalid schema.
  Concrete and safe. ✅
- **Verification runnable:** unit test → `py_compile` → `aq-qa 0 --machine` → tier0 pre-commit. ✅
- **Non-blocking note:** Invariant 3 permits writing generated output to "designated build
  target paths," and those output paths are not enumerated in the 5-file ceiling. This is
  acceptable — a generator's *runtime output* is not a repo source edit under the authorization,
  and the verification gate does not require generating into a bound path. No action required.

**Verdict: PASS.** Sound, implementable, fail-closed. Fit to hand a bounded implementer.

---

## VF-7 — Guaranteed Unwrapped Evidence Path — PASS

- **Ceiling:** Explicit 5-file ceiling; §2 CAUTION declares MANDATORY FAIL-STOP on any 6th file
  or modification of core inference/DB paths. Fail-stop present. ✅
- **Bound targets real:** Only MODIFY is `scripts/governance/tier0-validation-gate.sh` (EXISTS).
  The 4 NEW files land in real dirs. No phantom path. ✅
- **Invariants safe:** Unwrapped raw stdout/stderr (no compression filter); SHA-256 immutability
  digest over `(timestamp + payload_bytes + caller_agent_id)`; mandatory redaction of env vars /
  bearer tokens / SSH-OAuth keys before write; append-only ledger with `fcntl.flock`, truncation
  prohibited. Concrete and safe; no secret/network/DB-mutation exposure. ✅
- **Verification runnable:** verification suite → `py_compile` → `aq-qa 0 --machine` → tier0. ✅
- **Non-blocking note (interoperability):** The collector appends to the SHARED ledger
  `.agents/events/a2a-events.jsonl` (EXISTS) — the same file backing `aq-event pulse|resume`
  projections. Append-only + flock protects integrity, but mixing evidence records into a ledger
  consumed by existing pulse/resume parsers risks confusing those consumers. Recommend the
  implementer tag every evidence record with an explicit record-type discriminator (e.g.
  `"kind":"vf7_evidence"`) so existing consumers can filter. This is a design caution, not a
  contract breach — the append target is runtime data, not a bound source edit — so it does not
  block. No source edit outside the ceiling is required.

**Verdict: PASS.** Sound, implementable, fail-closed. Fit to hand a bounded implementer.

---

## L2B-B — Live Payload Normalization — REQUEST_REVISION

Material defect: the primary MODIFY target is a **phantom path**, and the real edit target is
**out of ceiling** — the contract is internally contradictory and unimplementable as written.

- **Bound target does not exist.** §2 binds `MODIFY ai-stack/local-agents/lib/local_inference_transport.py`.
  That file — and even the directory `ai-stack/local-agents/lib/` — does not exist in the repo.
- **The real module is unbound.** The transport module L2B-A established actually lives at
  `scripts/ai/lib/local_inference_transport.py` (confirmed: it is the only such file in the repo).
  The bound test `scripts/testing/test-local-inference-l2b.py` loads it explicitly at line 36 and
  line 218: `load(ROOT / "scripts/ai/lib/local_inference_transport.py", …)`.
- **The contract forces an out-of-ceiling edit.** To make the 14/14 golden gate pass, the
  implementer MUST inject the normalization logic into `scripts/ai/lib/local_inference_transport.py`.
  But that file is NOT in the bound inventory, and §2 CAUTION declares that "modification of un-bound
  files … constitutes a MANDATORY FAIL-STOP and immediately voids this authorization." So a
  compliant bounded implementer is trapped: the only path to a passing gate is a FAIL-STOP action;
  editing the named phantom path instead either errors (file-not-found) or creates a dead duplicate
  module at a wrong path that the test never imports.
- Everything else in L2B-B is otherwise sound: the 6-file ceiling and fail-stop are explicit;
  invariants are concrete and safe (27 GB single-model VRAM concurrency lock; deterministic
  NFC UTF-8 + key-sort + non-finite-float removal; no API-key inject/read/forward; opaque error
  mapping; fail-closed `REJECTED_SCHEMA_INVALID` with audit trace); verification is runnable; the
  other 5 targets (`test-local-inference-l2b.py`, `assets/dashboard.js`, and 3 NEW files) all exist
  or land in real dirs. Minor terminology mix ("RFC 8259 canonical forms" in §1 vs "NFC" in §3) is
  cosmetic; the operative NFC invariant is clear.

**Required revision (single-line fix):** change the bound MODIFY path from
`ai-stack/local-agents/lib/local_inference_transport.py` to `scripts/ai/lib/local_inference_transport.py`.
With that one correction the packet becomes sound and implementable; the fix is mechanical, but as
written the authorization must NOT be handed to a bounded implementer.

**Verdict: REQUEST_REVISION.**

---

## File-Overlap Sanity Check

Full bound inventories cross-checked. Only ONE overlap exists across all three:

- **B3-C1 ∩ VF-7 → `scripts/governance/tier0-validation-gate.sh`** — the known, expected overlap.
  Both are additive: B3-C1 appends a canon-compiler determinism check, VF-7 appends an
  evidence-collector verification step. Distinct, non-conflicting registrations → **safe to
  sequence** (land one, rebase, land the other). No structural collision.
- **L2B-B is disjoint** from both B3-C1 and VF-7 — no shared file (its intended real target,
  `scripts/ai/lib/local_inference_transport.py`, is touched by neither).
- All `config/schemas/*.json`, `scripts/testing/test-*.py`, and per-slice review docs are
  uniquely named. No other collisions.

Conclusion: implementable without collision, modulo (a) sequencing the known B3-C1/VF-7 tier0
double-touch, and (b) fixing the L2B-B path defect before that slice is authorized.

---

B3-C1 VERDICT: PASS (hash d6676252dc30061d58d9a2f8d5339cc2fc828b59eb3f41a6abc2552b746621ad)
VF-7 VERDICT: PASS (hash 71c5df38e736c48d86371c9aff294299e1c1dd0896adb80e4186b762547a1741)
L2B-B VERDICT: REQUEST_REVISION (hash b9055bb6a763189fd0b5fbc054ead4fc6a41d41ed117181039f0ce67d62f7cb8)
