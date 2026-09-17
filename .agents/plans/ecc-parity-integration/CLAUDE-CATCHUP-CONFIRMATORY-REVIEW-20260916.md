# ECC parity/integration — returning-Claude confirmatory review + convergence note (2026-09-16)

Reviewer: Claude Opus 4.8 (returning main session; independent of the Codex-authored ECC analysis).
Kind: Rule-18 catch-up confirmatory audit — advisory unless a material defect is found (none was).
Owner ask: assist Codex's parity/gap analysis + help integrate ECC's missing capabilities into AQ-OS.

## Disposition: CONFIRM (the analysis is sound + security-disciplined)
I independently read `PARITY-GAP-LEDGER.md`, `PROJECT-ECC-PARITY-INTEGRATION-PRD.md`, and `P0A-SLICE-BRIEF.md`
and spot-verified their claims. The decision surface is rigorous and conservative in exactly the right ways:
- **Untrusted / reference-only intake, runtime disabled** — correct posture for external code; aligns with our
  `capability-intake` (deny-by-default) + the risk-tiering we just designed (external code = top tier).
- **Resists inventory-marketing** — "3,716 artifacts ≠ 799 features"; per-feature source-verified verdicts
  (equivalent / stronger-local / partial / missing / unsuitable / approval-blocked). Correct.
- **Non-candidates are right** — no bulk-copy of agents/skills/commands, no running ECC installers/hooks/npx/
  scanners/auto-update, no second memory/orchestration/review/policy SSOT, no home-dir mutation, no
  browser→spawn authority, no autonomous promotion lifecycle. These would all violate our authority model.
- **Adversarial corrections to the Antigravity report** are well-founded (the "16 harnesses"/"~10 commands"/
  "5 roles"/skill-category claims were not source-derived; our side has 159 `aq-*` CLIs, capability leases
  mediate pre-execution, we already have worktree/learning/redaction/projection/evals/discovery).

## Spot-verifications (genuine, not rubber-stamp)
- ECC pin consistent: `8321021c54d670126ce3b2969d5deb880b4b0c2a` in both the PRD and SOURCE-READ-LEDGER;
  security-pass subtree pin `a7489fb4…` recorded separately. Consistent.
- **Candidate #4 (CI/CD) gap CONFIRMED against our repo:** our `.github/workflows/*.yml` use MUTABLE action
  refs pervasively (`test.yml` 27 `uses:@v*/@main/@master`, `security.yml` 18, others 2–6) — no SHA-pinning,
  matching the ledger's "mutable action refs, no proven GitHub protection" finding. This is a real
  supply-chain gap on OUR side, not an ECC-marketing artifact.

## The one connection worth making explicit (my value-add)
**P0-E (portable GitHub CI pack) + ledger candidate #4 ARE the CI/CD-enforcement leg of the
factory-gate-templates track (FT-*).** They should be ONE unified effort, not two parallel ones:
- The factory-gate-templates PRD already commits to a reproducible gate bundle installed by greenfield/
  brownfield; a portable, SHA-pinned, least-privilege, fork-safe-secret, provenance/OIDC, required-checks,
  environment-approval, rollback-capable CI/CD pack is precisely its CI/CD component.
- The ECC analysis is the best available reference for WHAT that pack should contain (ECC pins Actions by
  SHA, disables install lifecycle scripts, validates workflow security, tests packed artifacts, publishes
  with provenance/OIDC). Reuse the PATTERNS (reference-only), not ECC's source.
- Apply it to THIS repo first (fix the verified mutable-ref gap → dogfood), then template it into the bundle
  so every greenfield/brownfield project the factory starts inherits pinned, least-privilege CI/CD.
- Risk-tier (cross-cutting B): CI/CD enforcement is a core/security gate → top-tier review + locking.

Recommendation: fold P0-E into the factory-gate-templates bundle as its CI/CD-enforcement component (a shared
slice), rather than building a standalone ECC CI pack. The other four candidates (capability resolver P0-A,
projection compiler P0-B, lifecycle adapter P0-C, hermetic eval P0-D) stay as native AQ-OS slices per the
ledger — all correctly scoped to wrap existing authorities, never replace them.

## No blocking findings
Nothing here blocks the frozen queue. This is advisory catch-up confirming the decision surface + surfacing
the P0-E ↔ FT-* convergence so the CI/CD work lands once, in the right place, applied to us first.
