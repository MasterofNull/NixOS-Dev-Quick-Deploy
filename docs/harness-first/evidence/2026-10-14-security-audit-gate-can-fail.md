# Evidence: Security Audit Gate Can Fail (W6-S4)

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

## Review Record
| Author-lane | Reviewer | Disposition |
|---|---|---|
| claude | claude-sonnet (independent reviewer, 4 rounds) | PASS |

## Follow-ups
- Remove the diskcache exception once the nixos-docs diskcache replacement slice merges.
- Low: "applied" printed before package-match check; missing package field garbles warning (fail-closed).

## Rule 15 Activation Attestation
- Integrated: YES - security.yml CI workflow and security-audit.sh are the live path.
- Turned ON: DEFERRED (dated 2026-10-14): runtime activation is owner-operated (nixos-rebuild / service restart).
- Functionally validated: tests above; full real-world end-to-end run DEFERRED (2026-10-14) pending activation unless stated in Validation Evidence.
- Observable: DEFERRED (dated 2026-10-14): no new dashboard/alert in this slice; existing logs/health unchanged.
- Intervenable: DEFERRED (dated 2026-10-14): no new operator control in this slice; existing controls unchanged.
- PM-tracked: commit subject carries `W6-S4` for the sota-rounding tracker; status projected.
