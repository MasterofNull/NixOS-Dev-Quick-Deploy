# Handoff: read-only event-log enforcement (2026-09-27)

## Outcome

`aq-event pulse` and `aq-event resume` now write to the writable
`.agent/collaboration/a2a-events.jsonl`. Reads also import the historical
`.agents/events/a2a-events.jsonl` projection, then merge, deduplicate event IDs,
verify signatures, and sort by timestamp. A guarded fallback spool remains for
unexpected write errors; its warning is emitted once per process.

## Root cause

`.agents` is a separate ext4 bind mount with `ro,nosuid,nodev` options in this
managed workspace. Its Unix mode bits look writable to the repository user, but
the mount policy rejects writes. The previous logger treated that projection as
the writable canonical path. The root fix moves new writes to `.agent` and keeps
`.agents` readable for migration/history.

## Validation

- `python3 scripts/testing/test-event-bus-a2a.py` — all checks pass, including a
  simulated `EROFS` primary-write failure.
- `python3 -m py_compile scripts/governance/aq-evidence-collector.py`
- `python3 -m py_compile scripts/ai/lib/event_log.py scripts/ai/lib/resume_projector.py`
- `scripts/ai/aq-event pulse ...` and `scripts/ai/aq-event resume ...` complete;
  projection reports 5 fields and 26 agents.

## Operational boundary

The read-only `.agents` mount remains intentional. The fallback spool is runtime
state and is ignored by Git. If a deployment expects `.agents` to be writable,
fix the mount policy instead of weakening the fallback guard.

## Agent-process incident

The initial implementation responded to the write failure with a fallback before
checking the mount and producer contract. That was a workaround-first failure:
it preserved operation but delayed the root correction. The incident is logged as
`agent-workaround-before-root-fix` in `.agent/memory/issues-backlog.md` and WR-10
in `.agent/WORKAROUND-REGISTER.md`. The regression test now pins the writable
`.agent/collaboration` path so this ordering mistake cannot silently recur.
