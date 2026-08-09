---
doc_type: skill
id: finding-freshness
title: Finding Freshness — verify before logging or acting
status: active
tags: [freshness, multi-agent, concurrent, audit, backlog, stale-finding, verify-before-act]
---

# Finding Freshness

## Tags
freshness, multi-agent, concurrent, audit, backlog, stale-finding, verify-before-act, confused-deputy

## When to Use
Before you LOG an audit/review finding as OPEN, or ACT on one (author a fix, request an owner grant,
dispatch an implementer), in any multi-lane session. Findings go stale fast when several lanes commit in
parallel — a defect found an hour ago may already be fixed and released by another lane.

## Why this exists
Lived failure (2026-08-08): a Codex catch-up audit found a real HIGH (ALA→C2 lease-schema mismatch). It was
accurate WHEN WRITTEN, but by the time it was logged OPEN and nearly turned into a redundant fix + a
redundant owner grant, a concurrent lane had already fixed AND released it (commit `3d45e03c`). Only a
verify-first step caught it. Acting on a stale finding wastes a build, and — worse — emitting an owner grant
for already-done work is confused-deputy-adjacent. See issues-backlog `stale-finding-acted-before-freshness-check`.

## The check (run before log/act on any finding)
1. **Identify the producer files** the finding names (the exact `path:line` it blames).
2. **Ask "has HEAD moved on these since the finding was written?"**
   ```bash
   git log --oneline -5 -- <producer-file-1> <producer-file-2>
   git log --oneline --since="<finding-timestamp>" -- <producer-files>
   ```
   A commit touching those files after the finding's timestamp is a stale-risk signal — especially one whose
   message mentions fix/repair/resolve/close.
3. **Re-run the finding's own reproduction** against HEAD, not against the finding's prose. If the audit
   minted a real object and fed it to a real consumer, do THAT again now:
   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 <the-exact-repro-or-test-the-finding-cited>
   ```
   Green now = the finding is stale (fixed). Red = still live.
4. **Resolve or log accordingly:**
   - Stale → mark the backlog entry `[RESOLVED <date> by <commit>]` with the verification evidence; do NOT
     act, do NOT request a grant. (This is also anti-gaming honest record-keeping.)
   - Live → log OPEN / act, and record the HEAD hash you verified against so the next reader knows the
     freshness baseline.

## Hard rule
NEVER request an owner activation/build grant, or dispatch an implementer, for a finding you have not
re-verified against current HEAD in the same working session. A grant pins a design SHA; a concurrent lane
may have already superseded it. Verify first — every time. Links [[feedback-agent-agnostic-roles-and-catchup]]
and the confused-deputy guard the whole capability-lease spine exists to prevent.
