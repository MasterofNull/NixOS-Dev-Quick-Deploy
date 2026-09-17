# CS3-F1 — exact owned deletions and rename hash parity

Disposition: PLAN_READY. Parent candidate: 1a9a0567, ACTIVATION_BLOCKED.
Binding prior review: c5506ed015c5917b33f16b5f654a90e7d484d20fa4480b21c38c44026a8f9cf1;
cold cs3_final_review returned REQUEST_REVISION, never PASS.

## Bounded next slice

Only integration_guard.py and test-integration-guard.py implementation changes.
Preserve the CS-3 interface, safety boundary, lock ownership, ordinary hooks,
literal-path restrictions, and all existing passing tests. No rearchitecture.

- Missing index entry for a pre-staged deletion must be accepted ONLY when the
  declared literal path is an exact tracked file in the frozen HEAD. Reject
  trees/directory prefixes and unrelated absent paths before any staging.
- Published subject SHA256 must use precisely equivalent Git diff semantics to
  the staged binary/full-index subject, including renames, modes and deletions.
- Positive explicit owned deletion and two-path owned rename create exactly the
  intended commit, return COMMIT_SUCCESS-equivalent success, match frozen parent,
  paths and reviewed bytes; no rollback even on a post-commit assertion failure.
- Existing foreign-source rename refusal and absent-directory-prefix rejection
  remain passing; add actual HEAD-object drift coverage, not only branch drift.

One bounded corrective and one independent review per reported invariant.
Further recurrence escalates and remains preserved rather than spawning loops.
CS4 deployed dashboard exposure remains a separate activation gate.
