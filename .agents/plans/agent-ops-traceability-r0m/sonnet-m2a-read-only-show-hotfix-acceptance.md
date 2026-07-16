# Sonnet Acceptance — M2A Read-Only `show` Hotfix

**Reviewer task:** `claude-20260716-145818-fy8wa0`
**Model:** `claude-sonnet-4-6`
**Role:** independent read-only reviewer
**Candidate:** exact five-file subject in `M2A-READ-ONLY-SHOW-HOTFIX-DESIGN.md`

## Integrity and behavior

- All five authorized SHA-256 hashes matched exactly.
- `show_m2a()` calls the descriptor-bound snapshot reader directly and never calls the writer lock or
  transaction path.
- The reader opens with `O_RDONLY|O_CLOEXEC|O_NOFOLLOW` where supported, validates the opened inode with
  `fstat`, applies full-file and per-record bounds, and creates no directory or lock.
- Missing input remains an empty snapshot; symlink, non-regular, malformed, and oversized inputs fail
  closed with the existing typed reasons.
- Atomic replacement produces a complete old-or-new snapshot. Writer locking, mutations, CAS, machine
  envelopes, reasons, and exit codes remain unchanged.
- The reliability fixture changes exactly two scalar digests: TaskRegistry source and source manifest.

## Verification

- `test-agent-ops-projection.py`: 62/62 PASS.
- `test-local-delegation-reliability.py`: 16/16 PASS.
- Python compilation: PASS.
- Candidate diff/inventory inspection: PASS.

The reviewer made no candidate edits.

VERDICT: PASS — show_m2a is descriptor-bound and genuinely read-only while all writer and CAS semantics remain unchanged.
