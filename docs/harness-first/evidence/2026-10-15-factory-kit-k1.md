# Evidence — factory kit K1 (blockers B1/B2/B5/B17/B18) — 2026-10-15

Plan: `.agents/plans/software-dev-factory-rollout/DESIGN.md` (v2.2, v0.1 K1-K4 PLAN_READY after adversarial review + confirmatory re-review; `DESIGN-REVIEW.md`).

## Changes
- B1: test-enforced scan — kit bundle contains no host-absolute paths (`/home/`, `/run/current-system`) and no maintainer identity strings.
- B2: `{{OWNER_HANDLE}}` (new `CODEOWNERS.tmpl`) comes from the LOCAL user (`FACTORY_OWNER_HANDLE`, else `gh api user`), validated by regex, memoized, timeout-safe; unset/invalid -> `@OWNER-HANDLE-UNSET` + install hint. Never a maintainer default (owner rule 2026-10-15: each user's identity/auth is their own, stored locally).
- B5: gate-runner prints a notice when `aq-risk-tier` is absent (skip, not fail).
- B17: receipt/detector store `.` instead of the absolute target; hook router resolves root at runtime (`git rev-parse --show-toplevel`, original hooks via `--git-common-dir`).
- B18: `checks.install_hints` for every blocked required check (gitleaks named for secret_scan).
- Mode hardening (from gemini lane): receipts 0644; 0755 only for hook files or exec bundle sources.
- commit-msg behavior matrix test (main/master/trunk/feature x trailer dispositions).
- tracker.json: editorial K1-K4, K6-K12; no hand-typed status.

## Validation
- `for t in scripts/testing/test-factory-*.py; do python3 $t; done` — 8/8 rc=0; fixture JSON lines contain no `false`.
- `python3 scripts/testing/test-factory-kit-k1.py` — PASS (incl. real `git worktree add`, path with space, invalid handles `evil\nuser`/`bad user`/`x;rm`).
- `bash templates/factory-gate-bundle/self-test.sh` — SELF-TEST PASS.
- `scripts/ai/aq-pm-tracker .agents/plans/software-dev-factory-rollout --check` — PASS.

## Review
Independent reviewer (claude-sonnet, separate instance from implementer): PASS_WITH_FOLLOWUPS -> all 6 followups RESOLVED -> PASS. Reviewed subject (staged code diff) sha256 8b7ca4c0e134874393e0849601ba1cdeb815caafc4565f4be42f773a108588b0. This evidence doc + activation-audit entry added after review (docs only). Cross-lane confirmatory review queued.

## Activation (Rule 15)
- Integrated: installer live path (`aqd workflows retrofit` / install via `factory_gate_install.py`).
- Turned ON: active for every new install/retrofit; no flag.
- Validated: fixture suites above (real git repos, worktrees). Real-world consumer retrofit = K7 (T17, Mendocino) — deferred, dated 2026-10-15.
- Observable: `install_hints` in preview/status/receipt; `doctor` surface deferred to K3 (dated 2026-10-15).
- Intervenable: `FACTORY_OWNER_HANDLE` override; preview before install.
- PM-tracked: `.agents/plans/software-dev-factory-rollout/tracker.json` item factory-kit-k1.
