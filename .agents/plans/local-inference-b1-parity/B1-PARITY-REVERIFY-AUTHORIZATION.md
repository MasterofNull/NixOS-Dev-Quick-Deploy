# Foundation B1 — Chat/Batch Parity RE-VERIFICATION (source-drift re-pin) Authorization

**Authorization ID:** `auth-aqos-foundation-b1-parity-reverify-20260914`
**Idempotency key:** `aqos-foundation-b1:b1-parity:reverify-repin:v1:20260914:single-use`
**Status:** **PREPARED_ONLY — RE-VERIFICATION NOT AUTHORIZED**
**Track:** AQ-OS Unified Program — Foundation B1 (L-series), "chat/batch parity in shadow" — closes the B1 tail.
**Author:** claude-opus-4.8 (orchestrator/architect). Requires independent non-author review, then owner activation.

## 0. Why this exists (the drift, diagnosed)
The chat/batch parity shadow oracle landed at `e5460c07` and was accepted `VERDICT: PASS` (2026-07-23,
`B1-PARITY-ACCEPTANCE.md`). It hash-pins the live sources it measures parity against in the golden fixture's
`live_source_manifest`. It now FAIL-CLOSES with `live source drift: ai-stack/mcp-servers/shared/llm_config.py
(predecessor hash mismatch — re-authorize)`. This is the oracle working as designed (anti-tautology: the
parity claim must be re-established whenever a measured source changes), NOT a bug, and it is NOT wired into
tier0 (tier0 --pre-commit passes; commits are not blocked).

**Diagnosis (read-only, this session):**
- `scripts/ai/aq-chat`: current hash == pinned `4302af37…` — UNCHANGED (chat side did not drift).
- `ai-stack/mcp-servers/shared/llm_config.py`: pinned `be5a0986…` → current `68f5519994…` — drifted by
  EXACTLY ONE commit, `cc63ac57` ("fix tool-call reliability"). Its ONLY change to llm_config.py is the
  module constant `AGENT_TOOL_CALL_MAX_TOKENS` 256 → 512. `build_llama_payload` and every parity-checked
  payload param (enable_thinking, temperature, frequency_penalty, repeat_penalty/repeat_last_n, role/profile/
  authority, sampling, model-id) are UNTOUCHED.
- `AGENT_TOOL_CALL_MAX_TOKENS` is a max_tokens budget constant. Budget/max_tokens is ALREADY one of the
  oracle's accepted TYPED-DIVERGENCE classes (not a must-fail). So the drift is expected-benign: parity on
  the security-critical surface should still hold; at most the recorded budget-divergence evidence shifts.

This authorization therefore covers a CONFIRM-AND-RE-PIN, with a hard anti-gaming guard: the re-pin is valid
ONLY if a genuine oracle re-run confirms zero NEW must-fail divergence. It is NOT a licence to bump the hash
to green.

## 1. Bound authority & design chain (immutable inputs — any mismatch is a HARD STOP)
Reverify each before the first edit; a change means re-authorize (do not proceed).
| Subject | SHA-256 (as of this draft, HEAD `b7e33f3c`) |
|---|---|
| `scripts/testing/test-local-inference-chat-batch-parity.py` (the oracle — RUN it, do NOT modify it) | `daea1f6eb679018f07a762f66794eb1c5b5d8c46308e2750ac302eccacb8a83f` |
| `scripts/testing/fixtures/local-inference-chat-batch-parity-golden.json` (the ONLY file to modify) | `b548f146bcfbd0dba82750b8e4fe856b6786d3f57ae1dd244cb5f10939c48108` |
| `.agents/plans/local-inference-b1-parity/CHAT-BATCH-PARITY-DESIGN-PACKET.md` | `b2ae8cf33fdb3f0f60a684f23bc645f72691762fb6c6b72408f3ccc73aef2c10` |
| `.agents/plans/local-inference-b1-parity/B1-PARITY-ACCEPTANCE.md` (prior PASS record) | reverify at activation |

**Read-only builder references** (the oracle imports/reads these; must NOT be modified by this slice):
| Reference | SHA-256 |
|---|---|
| `ai-stack/mcp-servers/shared/llm_config.py` (`build_llama_payload`; the NEW pin target) | `68f5519994…` (reverify current at activation) |
| `scripts/ai/aq-chat` (chat builders) | `4302af375b25aa98dfb6d923e671e9d7597c814759b45b5c12fe3c84cb6d8392` (unchanged) |

HEAD advances legitimately between this draft and activation (F1/ledger commits land on top). The implementer
therefore binds to the SUBJECT HASHES above (reverified at activation), not to a fixed HEAD; the owner names
this authorization's exact SHA-256 at activation.

## 2. Exact one-file ceiling (MODIFY only; no new file, no second file)
| # | Operation | Path | Change |
|---:|---|---|---|
| 1 | **MODIFY** | `scripts/testing/fixtures/local-inference-chat-batch-parity-golden.json` | Re-pin `live_source_manifest["ai-stack/mcp-servers/shared/llm_config.py"]` to the reverified current hash; regenerate `manifest_digest`; update ONLY the budget/max_tokens typed-divergence evidence values that legitimately shifted (256→512), leaving all security-critical expectations byte-identical. |

Zero modification to the oracle, `llm_config.py`, `aq-chat`, `dispatch.py`. If the re-run surfaces a NEW
must-fail divergence (any security-critical field), that is a HARD STOP → do NOT re-pin → report it as a real
L3/L4 finding needing a separate slice (the drift would then be non-benign, contradicting §0).

## 3. Re-verification contract
1. Reverify all §1 subject hashes. Confirm `aq-chat` still `4302af37…` (unchanged) and capture the current
   `llm_config.py` hash as the re-pin target.
2. Run the oracle against current sources with the hash-gate satisfied by the NEW pin (i.e. update the pin
   FIRST in a working copy, then run — the run is the evidence the pin is honest). The oracle must reach its
   parity comparison (past the drift gate) and emit its typed report.
3. Confirm ZERO must-fail divergence on the security-critical surface (enable_thinking, temperature,
   frequency_penalty, repeat_penalty/repeat_last_n, role/profile/authority, sampling params, model-id) —
   byte-equivalent-on-projection, exactly as the original PASS. The accepted typed divergences (budgets/
   max_tokens; repeat_penalty set-vs-unset) may shift to reflect 256→512 but remain EVIDENCE, not failures.
4. Regenerate the fixture's `manifest_digest` for self-consistency (no `golden_digest_mismatch`).
5. Oracle exits `PASS: local-inference-chat-batch-parity`, offline, `py_compile`/`--staged-isolated` clean.

## 4. Acceptance criteria (independent, non-author lane)
- The re-pin equals the reverified current `llm_config.py` hash — NOT an arbitrary value (reviewer recomputes
  `sha256sum ai-stack/mcp-servers/shared/llm_config.py` and confirms it matches the new pin).
- The oracle genuinely re-ran and PASSED with **0 must-fail divergence** on the security-critical surface
  (reviewer runs it, does not take the candidate's word). Anti-gaming: a pin update without a passing re-run
  is REJECTED.
- Only budget/max_tokens typed-divergence evidence changed; every security-critical expectation byte-identical.
- Exactly the one fixture file modified; oracle + builders + frozen files unchanged; predecessor hashes reverified.
- `manifest_digest` self-consistent; offline; tier0 --staged-isolated green.

## 5. Stop conditions (fail-stop, zero-write)
- Any §1 subject-hash mismatch (other than the expected `llm_config.py` drift) → STOP, re-authorize.
- A NEW must-fail divergence on any security-critical field → STOP, do NOT re-pin, file a real divergence
  finding (the "benign drift" premise is false; needs a distinct L3/L4 slice).
- Any attempt to bump the pin without a passing oracle re-run → forbidden (anti-gaming, Rule 19).
- HEAD drift under the implementer → resume same-implementer with full reverify.

## 6. Owner Activation Record
**Current activation state: NOT ACTIVATED.** To activate: after an independent non-author `PASS` review of
THIS record, the owner records a `pulse.append` (or equivalent) naming this authorization's exact SHA-256 hash
and an expiry ≤24h. The orchestrator then routes a single bounded implementer (cheapest-eligible, non-author)
for the one-file re-pin candidate, independent acceptance, and (on PASS) staging + commit closing the B1 tail.
Silence, standing preauthorization, or a review PASS alone do NOT activate it.
