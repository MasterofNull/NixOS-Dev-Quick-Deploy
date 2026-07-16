# M2A Read-Only `show` Hotfix — Design Packet

## Evidence and defect

`aq-delegation-registry show <task>` is observational, but `show_m2a()` calls `_m2a_transact()`, which
unconditionally creates/opens the stable writer-lock inode with `O_CREAT|O_RDWR` and takes `LOCK_EX`.
The command therefore fails in a read-only monitoring context and violates monitoring-first operation.

## Exact five-file candidate

1. This design packet.
2. `IMPLEMENTATION-AUTHORIZATION-M2A-READ-ONLY-SHOW-HOTFIX.md`.
3. `scripts/ai/lib/task_registry.py`.
4. `scripts/testing/test-agent-ops-projection.py`.
5. `scripts/testing/fixtures/local-delegation-reliability-golden.json` — only required source/digest scalars.

## Design

- Keep `_m2a_acquire_lock()` and `_m2a_transact()` unchanged for mutations.
- Make the M2A record reader a descriptor-bound, bounded, fail-closed snapshot reader using
  `O_RDONLY|O_CLOEXEC|O_NOFOLLOW` where supported, descriptor `fstat`, regular-file enforcement, and
  bounded bytes/records. Missing registry maps to an empty snapshot; symlinks and malformed input fail.
- `show_m2a()` reads the immutable snapshot directly and never creates directories or lock files.
- Atomic writer replacement permits a complete old-or-new snapshot. Any later mutation still requires
  CAS, so a read lock would not guarantee future freshness.
- Preserve the machine envelope, typed reasons, exit codes, and writer behavior exactly.

## Acceptance

Tests prove absent-lock/missing-registry immutability, no writer transaction call, no write-capable open,
symlink/non-regular rejection, old-or-new descriptor race behavior, bounds/malformed failures, CLI
tree/inode/content/mtime immutability, concurrent atomic writer/show behavior, and unchanged mutation/CAS
tests. Focused projection, local reliability, Python compilation, and Tier0 must pass. Independent
flagship acceptance is required before commit.
