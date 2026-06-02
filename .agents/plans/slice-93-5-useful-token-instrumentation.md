# Slice 93.5: Useful-Token Instrumentation

Status: Complete
Owner: Gemini Code Assist (Orchestrator)
Last Updated: 2026-06-01
Supersedes: none
Superseded-By: none

## 1. Objective
Implement telemetry for `useful-token ratio` and waste buckets in `aq-report`, fulfilling Slice 93.5 from the Effectiveness-Centered System Improvement PRD. We must distinguish between tokens spent on accepted artifacts versus tokens wasted on rework loops, failed tool calls, or abandoned context.

## 2. Scope Lock
- **In scope**: Modifying `scripts/ai/aq-report` to aggregate and display the `useful_token_ratio` and waste buckets in `--machine` mode.
- **Out of scope**: Modifying the dashboard UI (Slice 93.13) or rewriting the core event stream (Slice 93.1).
- **Constraints**: Must safely return `no_data` if attribution is missing. Must not break existing human-readable `aq-report` text output.

## 3. Active Authority Links
- `.agents/plans/EFFECTIVENESS-CENTERED-SYSTEM-IMPROVEMENT-PRD.md` (Phase 93 PRD)
- `docs/AGENTS.md` (Dashboard & Telemetry Principles)

## 4. Steps
1. **Read-Before-Edit**: Inspect `scripts/ai/aq-report` and existing telemetry formats.
2. **Implement Aggregation**: Add logic in `aq-report` to parse token counts and categorizations (e.g., accepted vs. loop/rework/failed).
3. **Expose JSON Schema**: Update `aq-report --machine` output to nest these under `effectiveness_scorecard.efficiency_inputs`.
4. **Validate**: Run `aq-report --machine` to verify JSON structure and fallback behavior (`no_data`).

## 5. Validation Commands
```bash
scripts/ai/aq-report --machine | grep -A 10 "useful_token_ratio"
scripts/testing/run-focused-ci-checks.sh --target aq-report
```

## 6. Rollback Notes
Revert `scripts/ai/aq-report` to previous commit via `git checkout HEAD -- scripts/ai/aq-report`.
