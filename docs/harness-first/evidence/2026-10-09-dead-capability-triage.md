# Harness-First Task Evidence

Date: 2026-10-09
Task ID: HF-20261009-070

## Objective
- Plan item ci-6: triage the 69 DEAD-CANDIDATE capabilities with evidence.
  - KEEP-DECLARED: 33, recorded in config/capability-triage.json. Host- or profile-specific units, operator-run scripts and skills; the audit classifies them instead of calling them dead.
  - REVIVE-WIRE: 3 (aq-verify-committed, aq-claim and aq-transcribe got hint rules).
  - ARCHIVE: 17 superseded scripts moved under Rule 12 to archive/deprecated/20261009-capability-triage/. None is referenced by Nix, .githooks, tier0 or CI.
  - OWNER-DECISION: 16, listed with recommendations in .agents/reports/capability-triage-20261009.md.
- Merged with ci-3 (#446): a union of the new classes (ACKNOWLEDGED/STALE-ARTIFACT plus KEEP-DECLARED, index letter D), and AUDIT_VERSION bumped to 3.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer (judgement per item). The orchestrator resolved the stack conflict with #446 and the colliding test fixture name.

## Commands Executed
```bash
python3 scripts/testing/test-capability-audit.py (15 OK); test-capability-index (PASS, 424 entries); test-rsi-sweep (OK); test-aq-usage-logging (PASS)
aq-capability-audit (live): ACTIVE 154, UNUSED-AVAILABLE 240, UNDISCOVERABLE 5, STALE-CLAIM 0, ACKNOWLEDGED 2, STALE-ARTIFACT 1, DEAD-CANDIDATE 17, KEEP-DECLARED 31, BROKEN 0
repo-structure-lint --all PASS
```

## Validation Evidence
- DEAD-CANDIDATE went from 69 to 17. The remaining items are the 16 owner decisions plus 1.

## Rollback Plan
- Revert. The archived files are recoverable with git mv back.

## Residual Risk
- Two archived scripts remain listed in config/repo-structure-allowlist.txt (harmless). The owner-decision group needs the owner's call.

## Hint Feedback
- None.
