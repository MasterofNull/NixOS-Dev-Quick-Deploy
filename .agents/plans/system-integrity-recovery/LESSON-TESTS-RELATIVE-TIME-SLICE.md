# Lesson-test relative-time recovery slice

Date: 2026-11-09

This bounded implementation executes the frozen recovery design's P0.5, P0.6,
and P4 requirements for the two aq-report lesson tests only.

## Cause and scope

Both tests created feedback dated 2026-03-13 while querying a rolling
`now - timedelta(days=7)` window, so their candidates were correctly excluded
on 2026-11-09. They also used repository-root temporary paths. The slice is
limited to the two test producers, their `tests-misc-a-c` manifest entries,
and recovery evidence/checkpoints.

## Minimal-code decision

The minimal-code ladder selects existing test fixtures plus standard-library
`datetime` and `tempfile`: no new helper module, dependency, or production
change. Capture one UTC `now`, create recent and stale records for the same
candidate key, and redirect both aq-report state outputs to one
`TemporaryDirectory`.

## Acceptance

- Each direct test passes with recent records and proves stale records are
  excluded before candidate grouping.
- Both tests restore `HINT_FEEDBACK_PATH` and `AGENT_LESSON_REGISTRY_PATH`.
- Both are registered in the `paths` and `tests` arrays for `tests-misc-a-c`,
  with their known-failing exemptions removed.
- Focused test, syntax, and manifest validation leave no root temporary files.

## Boundary

This is repository-only test maintenance. Runtime activation is deferred to
2026-11-09: no service, deployment, or runtime configuration is changed by
this slice. Final-head review, tier0, commit, CI, and landing remain with the
orchestrator.
