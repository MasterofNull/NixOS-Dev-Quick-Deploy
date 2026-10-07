# Harness-First Task Evidence

Date: 2026-10-07
Task ID: HF-20261007-007

## Objective
- Make the memory crystallizer work live: client-side transcript extraction + secret redaction; coordinator never reads user transcripts. Includes Antigravity review follow-ups (metadata/subagent files excluded from scan, provenance field, single-pass discovery, RSI test AQ_DELEGATION_DIR isolation).

## Workflow/Session IDs
- Workflow ID: wf-crystallizer-client-side-20261007
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Implementers: Claude Haiku 4.5 (two slices). Reviewers: Antigravity (independent review → follow-ups), local Qwen (Continue filter + redaction gap), Claude Opus 5.5 (caught handler routing defect: session_path checked before history → same PermissionError). Local redaction attempt failed (APU first-token stall) and was folded in.

## Commands Executed
```bash
pytest -q ai-stack/mcp-servers/hybrid-coordinator/tests/test_memory_crystallizer_sessions.py ai-stack/mcp-servers/hybrid-coordinator/tests/test_memory_crystallizer.py ai-stack/mcp-servers/hybrid-coordinator/tests/test_cognitive_intelligence_l5_l6.py
bash -n scripts/ai/aq-crystallize
scripts/ai/aq-crystallize --session-dir ~/.claude/projects --since-hours 24 --max-sessions 2 --dry-run
```

## Validation Evidence
- Live failure evidence: after rebuild, coordinator (User=ai-hybrid) raised PermissionError(13) on ~/.claude/projects (0700); status sessions_processed=0.
- 35/35 tests PASS incl. 6 redaction patterns, dict payload, unreadable path → error (not raise), handler routes history over unreadable session_path.
- Dry-run extraction on real transcripts succeeds as invoking user.

## Rollback Plan
- Revert; nixos-rebuild switch; restart ai-hybrid-coordinator.

## Residual Risk
- Needs nixos-rebuild (coordinator runs store copy) + restart; live e2e confirmation pending. Fact quality bounded by local Qwen. /memory/crystalline/run remains auth-exempt (security deferred post-SOTA).

## Hint Feedback
- No aq-hints consulted.
