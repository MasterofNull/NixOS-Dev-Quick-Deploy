# Foundation B1 — Chat/Batch Parity (Shadow) Implementation Authorization

**Authorization ID:** `auth-aqos-foundation-b1-parity-20260723`
**Idempotency key:** `aqos-foundation-b1:b1-parity:chat-batch-shadow-oracle:v1:20260723`
**Status:** **PREPARED_ONLY — IMPLEMENTATION NOT AUTHORIZED**
**Track:** AQ-OS Unified Program — Foundation B1 (L-series), "chat/batch parity in shadow".
**Owner basis:** Q1/Q2 ratification (commit `cf3e81d7a09205ad808c1b5db8a113ba297eff0d`)
authorizes preparation + independent review of this record only.
**Author:** fable-5 (orchestrator/architect).
**Design review:** independent Opus — VERDICT REVISE (additive, within ceiling);
scope/offline-first/ceiling approved; corrections folded into the design packet §8.

**Activation rule:** this record remains `PREPARED_ONLY` after an independent
authorization `PASS`. Implementation requires a **later, explicit owner activation
naming this authorization's exact SHA-256 hash** and an expiry no longer than 24
hours. Silence, broad/standing preauthorization, design acceptance, or a review
`PASS` do **not** activate it.
**Single use:** a later activation is consumed by the first complete exact
two-file candidate report. An interrupted attempt without a complete candidate does
not consume it; resumption must use the same implementer and reverify every
predecessor hash.

## 1. Bound authority & design chain (immutable inputs — any mismatch is a HARD STOP)
| Subject | SHA-256 (HEAD-committed) |
|---|---|
| `.agents/plans/local-inference-b1-parity/CHAT-BATCH-PARITY-DESIGN-PACKET.md` | `b2ae8cf33fdb3f0f60a684f23bc645f72691762fb6c6b72408f3ccc73aef2c10` |
| `.agents/plans/local-inference-b1-parity/CHAT-BATCH-PARITY-DESIGN-REVIEW.md` | `3d8a4d8bc686d21543a5bc7ba025dc1341afba6ad62dde0620007f41b2a368f3` |
| `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md` | `4a90d130323d5067dbee12e588744766654590811806a271fce76b12560e4b4e` |
| `.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md` | `67796d15a03f3712eef21f4f77407bce6067c7faba672892a7a91ceeb4f6ea12` |
| `.agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION.md` | `fea8bde12d5639306aeb50d14cdd307ff0e7459ea6e75b80f5b996de1cd5cc07` |
| `.agents/plans/UNIFIED-PROGRAM-PLAN.md` | `285bda20b4bb3b43cafbc3a46b90c905b203996448f2f5cfda62a0d950bea62e` |

**Read-only builder references** (the oracle IMPORTS/reads these; it must NOT modify
them; reverify before first edit — a change means re-authorize):
| Reference | SHA-256 (HEAD-committed) |
|---|---|
| `ai-stack/mcp-servers/shared/llm_config.py` (`build_llama_payload` — the REAL builder) | `be5a098687c92c4345c80307175144887c262174afbf6da9fc2ca8012d961905` |
| `scripts/ai/aq-chat` (chat builders, harness-driven) | `4302af375b25aa98dfb6d923e671e9d7597c814759b45b5c12fe3c84cb6d8392` |
| `scripts/ai/lib/dispatch.py` (L2B frozen; NOT imported for the builder — use llm_config) | `1b083b1025877385cb4e295234edd23a61a85aae554393fb87792c732e01dd92` |

This grant implements ONLY the offline, report-only chat/batch parity oracle. It
does NOT move authority, change routing/callers/tools, adopt L3/L4, or modify any
live adapter or frozen-manifest file.

## 2. Exact two-file ceiling (NEW files only; both must be ABSENT before first edit)
| # | Operation | Path | Purpose |
|---:|---|---|---|
| 1 | **CREATE** | `scripts/testing/test-local-inference-chat-batch-parity.py` | The parity oracle (harness-drive + canonical-projection + comparison + typed divergence report). |
| 2 | **CREATE** | `scripts/testing/fixtures/local-inference-chat-batch-parity-golden.json` | Frozen caller matrix (tier × shape) + expected canonical projections + self-consistency manifest digest. |

Zero MODIFY. No third file. If the implementer finds a third file is required
(e.g. an `aq-chat` builder extraction), that is a HARD STOP → separate slice +
separate authorization (do NOT fold; do NOT touch `aq-chat`).

## 3. Implementation contract (per design packet + review §8)
1. **Harness-drive, no aq-chat modification.** `importlib`-load the `aq-chat`
   module; invoke `_build_coordinator_delegate_payload` / `_build_fast_path_payload`
   bound to a `SimpleNamespace` stub self (set only `temperature`,
   `local_tools_enabled`) — never run `AQChat.__init__`, never touch
   `switchboard_url` or any live I/O.
2. **Batch builder = the REAL one.** Import `llm_config.build_llama_payload`
   (`ai-stack/mcp-servers/shared/llm_config.py`), NOT `dispatch.py`'s ImportError
   fallback clone.
3. **Pure canonical-projection layer (inside the oracle file).** The 3 builders emit
   disjoint wire payloads and `mode`/`fallback`/`version` have no producer, so map
   each adapter's wire output → the PRD line-480 canonical schema
   (mode/profile/model/task_type/role/tools/budgets/fallback/version) via a pure
   `canonical_projection(adapter, wire)`; compare on the PROJECTION. Fields with no
   producer are asserted **absent-in-all** (parity by absence) — never fabricated.
4. **Difference policy (review §6.2).** Allowlist (legitimate, ignored): transport
   framing, stream flags, usage-option presence — compare DECODED content+usage,
   never framing. MUST-FAIL on divergence in: `enable_thinking`, `frequency_penalty`,
   `temperature`, budgets, role/profile/authority, sampling params, model-id.
   Known first-run divergences (`max_tokens` 1024-vs-budget;
   `repeat_penalty`/`repeat_last_n` set-vs-unset) are recorded as **typed divergence
   evidence** (they scope L3/L4), NOT a slice failure — the oracle emits them in the
   report and still passes the slice.
5. **Report-only, offline, fail-closed.** No live service call; runs under tier0.
   A must-fail divergence FAILS CLOSED with a field-level diff (no "acceptable"
   narration of a real mismatch).

## 4. Acceptance criteria (for the independent candidate acceptance)
- Oracle covers the full tier × shape matrix (flagship/standard/budget/deterministic
  × chat/batch); projection comparison on line-480 fields with the §3.4 policy.
- Legitimate differences ignored; must-fail differences fail closed with a diff;
  known first-run divergences emitted as typed evidence, slice still passes.
- Pure + offline (no live llama/switchboard/coordinator); `py_compile` clean; runs
  green under `tier0 --staged-isolated`.
- Golden fixture carries a self-consistency manifest digest (regenerated with the
  projections — no `golden_digest_mismatch`).
- Zero modification to `aq-chat`, `llm_config.py`, `dispatch.py`, or any frozen file;
  exactly the 2 new files; predecessor hashes reverified.
- Independent acceptance by an eligible lane that is NOT the implementer; never-skip-local.

## 5. Stop conditions (fail-stop, zero-write)
- Any design-chain or read-only-reference hash mismatch → STOP, re-authorize.
- Need to modify any existing file / a third file → STOP (separate slice).
- HEAD drift under the implementer → STOP, resume same-implementer with reverify.
- A real must-fail divergence that cannot be classified → report it; do NOT relabel
  it "acceptable" (anti-gaming).

## 6. Owner Activation Record
**Current activation state: NOT ACTIVATED.** To activate, the owner records a
`pulse.append` naming this authorization's exact SHA-256 hash and an expiry ≤24h,
then the orchestrator routes a single bounded implementer for the 2-file candidate,
independent acceptance, and (on PASS) staging + commit.
