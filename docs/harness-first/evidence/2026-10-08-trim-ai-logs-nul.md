# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-trim-ai-logs-nul

## Objective
- trim-ai-logs.sh kept NUL-prefixed JSONL lines forever as unparseable. hybrid-events.jsonl carried April records past the 14-day TTL, and learning readers saw corrupt lines. Strip NULs before parsing; fsync the temp file and the directory around os.replace.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Haiku implementer; the orchestrator replaced its embedded-copy test with real-script extraction during review.

## Commands Executed
```bash
python3 scripts/testing/test-trim-ai-logs-nul.py; bash -n scripts/data/trim-ai-logs.sh
```

## Validation Evidence
- The test executes the heredoc extracted from the real script. It passes with the fix (removed 2/4) and exits 1 on the original (removed 1/4, NULs remain).

## Rollback Plan
- Revert the commit.

## Residual Risk
- The NUL origin is unproven (candidate: crash mid-trim before this fsync). The next data-retention run cleans the live file.

## Hint Feedback
- None.
