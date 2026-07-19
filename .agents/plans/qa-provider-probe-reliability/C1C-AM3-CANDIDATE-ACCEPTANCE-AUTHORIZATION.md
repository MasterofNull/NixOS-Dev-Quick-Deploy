# QPPR C1C-AM3 candidate-acceptance authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-c1c-am3-acceptance-20260719`
**Status:** PREPARED_ONLY until owner activation (standing authorization applies)
**Prepared:** 2026-07-19 UTC, Fable 5 orchestrator session (drafting only)
**Required reviewer:** `claude-subagent-qppr-c1c-am3-acceptance-reviewer` — flagship tier, fresh
session; must not be the implementer (Sonnet candidate author), the Opus design reviewer (R1/R2),
the orchestrator session, or any author in this slice's lineage
**Single use:** one acceptance review of the exact two-hash candidate below; ≤24h window on activation

## Exact frozen candidate subject

| Path | Required SHA-256 |
|---|---|
| `scripts/testing/harness_qa/core/process_lifecycle.py` | `c7407ea4d172abd2250c459dbe6fdd1bfd4fec959d834abaf553f5e903c32ae2` |
| `scripts/testing/test-qa-provider-probe-lifecycle.py` | `d95479d0aa0961d4d5561e0239aa0c1547577190ca07208b460a04aeb579148b` |
| frozen observer test (must be unchanged) | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` |

Predecessors: `ceef8fbe…0b38e` / `4dc49ef8…3efac7`. Lineage: amendment rev2 `71911585…2f0f6`;
implementation authorization `95d8d947…04474` (consumed); R1 review REQUEST_REVISION + R2 review
PASS (`2079ca6a…61df0`); AM2 rejection record `544b84dd…a1a9b6`; owner activation + standing
authorization PULSE entries of 2026-07-19.

## Acceptance criteria (all mandatory; REQUEST_REVISION names the failed item)

1. All three hashes above match exactly; predecessor deltas confined to the two MODIFY paths.
2. Amendment R1–R7 verified in the actual code, with special scrutiny on R5's mechanism: the
   candidate neutralizes `lock_held`/`controller` before raising its dedicated exception and relies
   on the predecessor's `except Exception:` re-raise gate (`controller is None and identity is None
   and not lock_held`). The reviewer must verify `identity` is provably `None` at the publication
   invocation point on every path reaching it — otherwise the handler's recovery branch (release
   1118, restore 1142) executes and the candidate FAILS. Verify lines 1118/1142/1179/1184 are
   unreachable with live state on both violation paths; verify the finally-block guards
   (`if lock_held:`, `if controller is not None:`) are the only thing standing between the violation
   path and restoration, and that the neutralization precedes the raise.
3. R2/R6 structure: synchronous invocation on the barrier path with zero new threads (verify the
   `threading.Thread` scan yields only the legacy line and pre-existing `_drain` readers); legacy
   no-`publication_fd` path byte-identical in behavior; never-return blocks before any restoration.
4. The six deterministic proofs exist as tests and prove what they claim: subprocess isolation with
   event barriers for never-return/late-return (no sleep-only assertions), injected classifier time,
   post-violation non-downgrade, zero restoration/redelivery/release evidence, exact fixture reap.
5. All validation commands from the implementation authorization re-run fresh by the reviewer and
   pass: both suites (39 lifecycle / 8 observer expected), py_compile, observer hash, diff --check,
   secret-scan (3 pre-existing matches acceptable ONLY if reviewer confirms none are in the diff),
   threading scan.
6. Governance trail: resume/intent/write/validate/done entries present via canonical writers.
   Disclosed deviation to adjudicate: the implementer ran the pre-edit governance commands AFTER
   editing (belated resume/intent), self-disclosed in its report and PULSE. The reviewer weighs
   whether the deviation affects candidate integrity (the bytes are hash-frozen) and states its
   adjudication explicitly; concealment would have been disqualifying, disclosure is mitigation.
7. No prohibited action occurred: nothing staged (`git diff --cached` clean for these paths), no
   commit, no third file, no live/provider/network action, no self-acceptance.

## Reviewer allowance

Bounded reads of the subject, lineage documents, and rejected-candidate evidence; `sha256sum`;
the exact validation commands in criterion 5; path-limited `git status/diff`; `rg -n` within subject
paths. Writes: exactly one verdict artifact
`.agents/plans/qa-provider-probe-reliability/C1C-AM3-CANDIDATE-ACCEPTANCE.md` (identity/model,
recomputed hashes, per-criterion evidence, deviation adjudication, terminal `VERDICT: PASS` or
`VERDICT: REQUEST_REVISION — <reason>`) and one closing pulse as
`claude-subagent-qppr-c1c-am3-acceptance-reviewer`. No edits to any subject, no staging, commit,
Tier-0, delegation, or authority expansion. PASS authorizes only the orchestrator to run Tier-0,
stage, and commit the exact accepted candidate; A1-AM3 rebind remains downstream of that commit.

`RECORD: single use. Activation under the owner's recorded standing authorization must name this
document's exact SHA-256, the reviewer identity, and a ≤24h window.`
