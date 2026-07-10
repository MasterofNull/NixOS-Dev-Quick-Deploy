# Fresh APPROVE Review — AQ-OS Cycle 0 Final Package Root (Anthropic lane)

**Reviewer lineage:** Claude Fable 5 (Anthropic family).
**Execution principal:** Claude Code CLI session (distinct from the codex CLI and the Antigravity IDE).
**Attribution assurance:** `ORCHESTRATOR_ATTESTED`.
**Review date:** 2026-07-10.
**Review type:** fresh `APPROVE`-eligibility review of the amended subject, as required after my prior
`APPROVE_WITH_CHANGES` (REVIEW-FABLE5.md) — per STATE-CONTRACT, only fresh APPROVE reviews of the
exact amended root can ratify.

## Subject binding (tool-verified)

- **Package root:** `0a2b0cce9876edf9b58d627c8c2d59608996f9e8c98d5b7e8fba8f7d065bdb3f`
- **Verification:** `scripts/governance/aq-package-freeze verify PACKAGE-ROOT.json` → **exit 0**
  (sidecar matches descriptor bytes; all 10 declared subjects match raw-byte sha256).
- The OWNER-POLICY-RATIFICATION condition — no reviews against hand-stamped roots once the tool
  exists — is satisfied: the tool exists (commit history) with a 14/14 passing focused suite, and this
  root is tool-verified. Note: this root's hashes were originally computed by hand and happen to be
  byte-accurate; all FUTURE roots must be produced by `freeze`, not merely confirmed by `verify`.

## Provenance caveat (declared, not hidden)

The freeze tool itself was implemented by this reviewer as a logged orchestrator-salvage exception
(all implementer lanes unavailable; owner directed the chain forward twice). Tool-authorship and
package-review are different subjects, so this does not constitute self-review of the package — but
the tool's correctness should not rest on its author's word: the Gemini fresh review is explicitly
instructed to re-run `verify` itself as an independent execution principal, and the focused test
suite is committed for any lane to re-execute.

## Disposition verification (each prior finding, against the frozen bytes)

| Finding | Disposition in frozen package | Verdict |
|---|---|---|
| F1 freeze discipline | Freeze specified as one bounded operation; manual root maintenance prohibited once tool exists; the hand-built root retained as REQUEST_REVISION evidence. Tool now exists and verifies. | RESOLVED |
| F2 quorum deadlock | Bounded degraded mode drafted (SLA-gated, one family + authenticated owner co-review, 7-day non-renewable, zero weight for the missing lane; security/identity/promotion/destructive work strict-quorum) — matches the owner-ratified policy. Local-lane repair is a Cycle-1 governance prerequisite per OWNER-POLICY-RATIFICATION. | RESOLVED |
| F3 numeric representation | Hybrid adopted exactly as two families concurred: integer `{numerator, denominator}` (nonzero positive denominator) for ratios/scores; decimal strings + integer scale + unit for physical measures; JSON floats remain forbidden. | RESOLVED |
| F4 dual telemetry root | Single canonical resolver; `TELEMETRY_ROOT_DIVERGENCE` fails closed before writing; isolated dual-env fixture required. Elevated to Intent-Lock precondition. | RESOLVED |
| F5 local review budget | Raised to ≤6,000 in / ≤1,500 out / ≤900 s wall, one retry only after a readiness check — matches the measured lane envelope. | RESOLVED |
| F6 stale anchor | Point-in-time totals moved to dated evidence records; durable PRD no longer carries live QA numbers as facts. | RESOLVED |
| F7 scan bound | Bound raised to 8,000 with measured baseline 4,793 stated; truncation is DEGRADED for discovery but blocks C0.3 ratification without a complete rerun or owner-approved bound change. | RESOLVED |
| N1 (Gemini) A2A telemetry | Fixed-cardinality collaboration telemetry (round duration, lane queue/response time, response bytes, eligible counts, stable failure reasons) through the existing collaboration endpoint/card; IDs/prompts never metric labels. | RESOLVED |
| N2 (Gemini) lane-output verification | Dispositioned via the standing deferred decision: Cycle 0 uses truthful `ORCHESTRATOR_ATTESTED`, rejects `UNVERIFIED` quorum; per-workload cryptographic identity is Cycle 2 scope. Substance adequate; an explicit N2 row in DECISION-LOG would have been cleaner (style, not blocking). | RESOLVED (minor style note) |
| N3 (Gemini) rollback fixture | Compatibility-rollback fixture added (v2 writer disabled, v1+v2 preserved as `legacy_untrusted`, legacy assignment paths stay blocked, re-enable reconstructs the same decision hash); honest about no-DB-migration scope. | RESOLVED |

Local lane's F2 dissent (repair-first) is preserved in the round record and substantially honored by
the repair-SLA prerequisite; its F3 preference (decimal strings) is half-adopted via the hybrid.

## Residual notes (none blocking)

1. All future package roots must be minted by `freeze` (see subject binding note).
2. N2's explicit DECISION-LOG row — recommend adding in any future amendment, no new revision needed.
3. The C0.1 ownership preflight at authorization time remains mandatory (verified clean at HEAD
   4a291dbf as of this review).

## Verdict

`VERDICT: APPROVE — the amended package at tool-verified root 0a2b0cce9876edf9b58d627c8c2d59608996f9e8c98d5b7e8fba8f7d065bdb3f
dispositions every finding from both independent family reviews and the local lane's dissents are
honestly recorded. This supplies the Anthropic-family fresh APPROVE toward the two-family quorum.
Ratification still requires the Gemini-family fresh APPROVE of this exact root; implementation
authorization remains a separate owner action.`
