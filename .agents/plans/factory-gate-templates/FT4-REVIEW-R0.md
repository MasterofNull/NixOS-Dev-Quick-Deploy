# FT-4 independent review R0

Reviewer: Codex /root/ft1_independent_acceptance (non-author).
REQUEST_REVISION on unchanged full subject
9342665a028daa61f302a02176a2401364d7f89b9a2f4c3e5e3df9445b8ecc28.
All probes used disposable fixtures; no activation/user-project mutation.

Four blocking invariants, one bounded FT4-R1 correction:

1. Backup path/ancestors were not validated. Symlinked .factory/gate-backups
   caused safe preview/install to copy Git config outside target. Validate exact
   backup destination and all ancestors before any write; prove outside unchanged.
2. Unframed concatenated file contents permit equal hashes for changed files.
   Tool availability can change rendered scanner commands without changing hash.
   Use canonical framed per-file path/type/mode/content-digest records and bind
   meaningful planned rendering/check configuration; prove both stale refusals.
3. Router assumes git rev-parse --show-toplevel. Post-update from .git exits128
   instead of invoking original with cwd/argument/exit7. Resolve installed routing
   independent of working-tree context; preserve original hook invocation behavior.
4. Existing scripts/governance/gate-runner was preserved instead of refused;
   its no-op bypasses new pre-commit/configuration block. Refuse enforcement-
   component collisions; preserve project instructions/CI separately.

Focused four-marker, FT3 regression, syntax/whitespace and root QA/UI probes
passed but were insufficient to detect these. Tier0 is a separate gate.
One corrective replay per invariant; recurrence escalates, no widening loop.
Nonblocking support breadth/custom hook routing remains explicitly deferred.
