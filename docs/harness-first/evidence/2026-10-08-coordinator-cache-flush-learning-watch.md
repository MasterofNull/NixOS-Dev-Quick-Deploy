# Harness-First Task Evidence

Date: 2026-10-08
Task ID: HF-20261008-130

## Objective
- The owner reported degraded cache, context, and memory after the 18:13 rebuild. There were three root causes:
  1. Every coordinator restart flushed the whole embedding cache. The legacy check spared only keys starting with 'm', but current keys are 'e<epoch>:m<slug>:...'. The journal shows legacy_keys_flushed count=274/68/28 at each restart today.
  2. The continuous-learning loop failed every cycle with EACCES. watchfiles awatch was recursive, and telemetry/retired is a 0700 directory owned by hyperd (written by qa_evidence_store). There have been 426 learning_loop_error since 2026-10-06.
  3. Every Codex run logged a skill-load error because .agent/skills/finding-freshness/SKILL.md lacked the name/description fields.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- The orchestrator made the edits directly. These are a few lines each, diagnosed from live journals, and delegation overhead would exceed the edit. The worktree git guard also blocks subagent commits.

## Commands Executed
```bash
journalctl -u ai-hybrid-coordinator --since -3d | rg 'legacy_keys_flushed|learning_loop_error'
<coordinator python> scripts/testing/test-embedding-cache-legacy-flush.py   # PASS with fix; FAIL "live key was flushed" on origin/main
```

## Validation Evidence
- The regression test passes with the fix and reproduces the bug without it.
- The coordinator's watchfiles is 1.1.1 and supports recursive=False.

## Rollback Plan
- Revert the commit and rebuild/restart ai-hybrid-coordinator.

## Residual Risk
- The bare-legacy flush now deletes only colon-free keys. Keys from an older epoch remain until their TTL expires, and they are never read because the epoch is part of the key.

## Hint Feedback
- None.
