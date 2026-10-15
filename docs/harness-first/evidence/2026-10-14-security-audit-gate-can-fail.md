# Evidence: Security Audit Gate Can Fail (W6-S4)

## Objective
Make the security-audit CI gate able to fail: it must block on real npm/pip findings instead of grepping tokens the script never printed under continue-on-error, and pip scanning must target real requirements files instead of nonexistent `*.lock` files.

## Workflow/Session IDs
- Orchestrator sessions: eb012479-4564-462f-8e6f-4824d5a77754, 03acd9b7-086d-410f-b409-b1dd7d113856
- Plan slice: 15 W6-S4 (sota-rounding tracker)
- Branch: `fix/security-audit-gate-can-fail`

## Delegation Decision
- Implementer: claude-sonnet (cheapest eligible Claude lane, Rule 17), bounded to the files listed under Context.
- Reviewer: claude-sonnet, independent of the implementing session, 4 review rounds, final disposition PASS.

## Commands Executed
- `git diff origin/main...HEAD --stat` to scope the change.
- `bash scripts/testing/test-security-audit-gate.sh` (seeded-finding fixture: gate blocks; clean fixture: gate passes).
- `FORCE_HARNESS_FIRST_EVIDENCE_GATE=true bash scripts/testing/check-harness-first-pr-evidence-gate.sh`.
- `scripts/governance/tier0-validation-gate.sh --pre-commit` at commit time.

## Context
Date: 2026-10-14
Slice: `fix/security-audit-gate-can-fail`
Component: `.github/workflows/security.yml`, `scripts/security/security-audit.sh`, `config/security-exceptions.json`, `scripts/testing/test-security-audit-gate.sh`, `ai-stack/mcp-servers/{aidb,hybrid-coordinator,nixos-docs}/requirements.txt`, `.agent/WORKAROUND-REGISTER.md`
Author lane: claude; independent reviewer: claude-sonnet (independent reviewer, 4 rounds)

## Problem
Root cause: security.yml grepped tokens the script never printed and used continue-on-error, so the gate could never fail; pip scanning targeted nonexistent *.lock files.

## Solution
Real pip coverage and CI pip-audit; npm/pip errors block in CI; time-boxed exceptions in config/security-exceptions.json. Real findings surfaced: pytest PYSEC-2026-1845 fixed by floor >=9.0.3 (+pytest-asyncio >=1.3.0); nltk PYSEC-2026-3740 and diskcache PYSEC-2026-2447 carried as exceptions time-boxed to 2026-11-13 (owner-approved 2026-10-14).

## Validation Evidence
- `bash scripts/testing/test-security-audit-gate.sh`: `PASS: security-audit gate blocks on seeded finding, passes clean`.
- tier0 `--pre-commit`: see commit/PR.

## Rollback Plan
Revert the PR (`git revert` of the merge commit). This restores the previous `security.yml` and `security-audit.sh` behavior (non-blocking gate) and the prior requirements floors; no runtime state or data migration is involved.

## Residual Risk
- nltk PYSEC-2026-3740 and diskcache PYSEC-2026-2447 are carried as time-boxed exceptions (to 2026-11-13) in `config/security-exceptions.json`.
- The diskcache exception is now moot: PR #516 replaced diskcache with stdlib sqlite3 and has merged. A follow-up change removes that exception entry; it is intentionally not removed in this change.
- Low: "applied" is printed before the package-match check, and a missing package field garbles the warning (fail-closed).

## Hint Feedback
No harness hints were consulted or rated for this slice; none to report.

## Review Record
| Author-lane | Reviewer | Disposition |
|---|---|---|
| claude | claude-sonnet (independent reviewer, 4 rounds) | PASS |

## Follow-ups
- Remove the diskcache exception (replacement merged in PR #516; follow-up change).
- Low: "applied" printed before package-match check; missing package field garbles warning (fail-closed).

## Rule 15 Activation Attestation
- Integrated: YES - security.yml CI workflow and security-audit.sh are the live path.
- Turned ON: DEFERRED (dated 2026-10-14): runtime activation is owner-operated (nixos-rebuild / service restart).
- Functionally validated: tests above; full real-world end-to-end run DEFERRED (2026-10-14) pending activation unless stated in Validation Evidence.
- Observable: DEFERRED (dated 2026-10-14): no new dashboard/alert in this slice; existing logs/health unchanged.
- Intervenable: DEFERRED (dated 2026-10-14): no new operator control in this slice; existing controls unchanged.
- PM-tracked: commit subject carries `W6-S4` for the sota-rounding tracker; status projected.
