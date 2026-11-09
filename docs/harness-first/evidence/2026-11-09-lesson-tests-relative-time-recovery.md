# Lesson-test relative-time recovery evidence

Date: 2026-11-09

The prior fixed 2026-03-13 fixture fell outside the rolling seven-day window on
2026-11-09, causing both lesson tests to find no candidates. Each test now uses
one aware UTC clock, three fresh events, and three expired events for the same
`(agent, hint_id)` key. Exact `total_events`, `event_count`, and `evidence_count`
assertions prove expiry exclusion occurs before grouping. `TemporaryDirectory`
keeps feedback and registry state outside the repository and `finally` restores
both patched globals.

Validation:

- `python3 -m py_compile scripts/testing/test-agent-lesson-registry.py scripts/testing/test-agent-lesson-schema.py` — pass.
- `python3 scripts/testing/test-agent-lesson-registry.py` — pass.
- `python3 scripts/testing/test-agent-lesson-schema.py` — pass.
- `python3 scripts/testing/test-ci-checks-manifest.py` — pass (eight checks).
- Manifest assertion verified both scripts are in `tests-misc-a-c` `paths` and
  `tests`, with no `test_exempt` entries.
- Root independently re-ran both direct scripts at 17:51 UTC — pass.
- First serialized tier0 attempt (2026-11-09) blocked on `ai-stack/agent-memory/MEMORY.md` at 203 lines against its 200-line cap; the index entry was condensed without removing its topic or evidence links. Parent will retry the gate.

Activation deferral (2026-11-09): this is repository-only test maintenance; it
introduces no service, runtime configuration, or deployment to activate. Parent
owns serialized tier0, exact-head independent review, commit, CI, and landing.
