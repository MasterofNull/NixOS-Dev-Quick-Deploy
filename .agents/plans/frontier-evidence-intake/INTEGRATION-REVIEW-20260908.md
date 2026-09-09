# Integration Review — Frontier Evidence Intake + C-1 Slice Claim Registry

Date: 2026-09-08
Reviewer: independent/adversarial (non-author), Claude Sonnet 5
Branch under review: `integrate/frontier-to-main` @ `7d0b39b8`
Worktree: `/tmp/frontier-integrate`
Merge-base check: `main` tip (`d317b026`) == merge-base with the integration branch — branch is current, no drift, cleanly mergeable.

Scope note: this is an INTEGRATION review (safe-to-merge + security), not a full line audit of all 2494 changed lines — the system was already developed and reviewed on its source branch.

## 1. TESTS GREEN — PASS

All six suites run clean in the worktree with `PATH=/run/current-system/sw/bin:$PATH`:

```
test-frontier-backlog:   ok 6/6
test-frontier-sources:   ok 5/5
test-frontier-relevance: ok 6/6
test-frontier-context:   ok 5/5   (1 harmless DeprecationWarning: datetime.utcfromtimestamp,
                                    scripts/testing/test-frontier-context.py:36 — cosmetic, not a failure)
test-frontier-fold:      ok 4/4
test-slice-claim:        ok 5/5
```
Total: 31/31 assertions pass, 0 failures.

## 2. SEAMS SAFE — PASS

Diff confirms all three seams are pure insertions (no lines removed from existing files):
```
.claude/commands/create-prd.md   | 10 ++++++++++
.claude/commands/plan-feature.md |  7 +++++++
scripts/ai/aq-session-start      | 10 ++++++++++
```
- `scripts/ai/aq-session-start:57-65` — the frontier block is gated on `machine -eq 0`, calls
  `"${SCRIPT_DIR}/aq-frontier" context "$task" 2>/dev/null || true`, and only prints
  (`[[ -n "$_frontier_ctx" ]] && printf ...`) when non-empty. Verified live: with
  `scripts/ai/aq-frontier` temporarily moved aside (simulating "absent"), the substitution still
  returns exit 0, empty string, and the surrounding script continues normally — no crash, no
  hydration block.
- `scripts/ai/aq-frontier context <topic>` was also exercised directly with a topic outside the
  taxonomy (`nonexistent-topic-xyz-test`) — exits 0 with a graceful "no matched concepts" line,
  never a traceback.
- `.claude/commands/create-prd.md:15-21` and `.claude/commands/plan-feature.md:15-19` are
  prompt-instruction additions (not executable gates) telling the agent to pull frontier context
  first — additive text, doesn't alter any other existing instruction in either file.

## 3. NO SECRETS/PII — PASS

- `grep -nEi "api[_-]?key|secret|token|password|credential"` across
  `scripts/ai/aq-frontier`, `scripts/ai/lib/frontier_*.py`, `.agents/plans/frontier-evidence-intake/*`
  turns up only the coordinator-key *plumbing* code, no literal values:
  - `scripts/ai/lib/frontier_relevance.py:124-131` (`_hybrid_key()`) reads the key from
    `HYBRID_API_KEY_FILE` (a path, read from disk) or `HYBRID_API_KEY` env var — never hardcoded.
  - `scripts/ai/lib/frontier_relevance.py:146` sets `X-API-Key` header only if a key was found.
- Port check: `scripts/ai/lib/frontier_relevance.py:142` —
  `base = coordinator_url or os.environ.get("HYBRID_COORDINATOR_URL", "http://127.0.0.1:8003")`.
  Env var is read first; `8003` appears only as a same-machine localhost fallback default. This
  exact `os.environ.get("HYBRID_COORDINATOR_URL", "http://127.0.0.1:8003")` pattern is the
  established repo-wide convention (~140 existing files use it, including
  `ai-stack/local-orchestrator/mcp_client.py`, whose exact `/query` + `X-API-Key` contract this
  file's docstring explicitly cites as its match) — not a new violation introduced by this branch.
  No other numeric port literals found in the new files.
- No API keys, passwords, private key material, or PII strings found anywhere in the new files.

## 4. DEBATE GATE REAL — PASS

`scripts/ai/lib/frontier_backlog.py`:
- `STATUSES` (line 32) includes `"new"`; `consensus()` (lines 59-71) computes
  `eligible = len(supports) >= min_supports and not rejects` — requires >=2 distinct supporting
  lanes (default `min_supports=2`) **and** zero open rejects.
- `add()` (lines 128-141): `rec["status"] = record.get("status") if record.get("status") in STATUSES else "new"`.
  The `add` CLI subparser (`scripts/ai/aq-frontier:84-87`) exposes no `--status` flag at all, so
  every `aq-frontier add` lands as `"new"`, never `"accepted"`.
- `scripts/ai/aq-frontier:161-171` (`accept` command): calls `fb.consensus(...)`; if not
  `accept_eligible` it prints `BLOCKED — ...` and returns exit code 3 **unless** `--force` is
  passed. `--force` is an explicit, visible CLI flag (not a silent bypass) — flagged here as a
  minor observation: the stored record doesn't persist a distinct marker for forced vs.
  consensus-based acceptance (no audit trail beyond CLI/shell history). Not a blocking defect —
  it's a documented manual owner-override escape hatch, and the default/automatic path is real
  and adversarial (a single unaddressed reject blocks acceptance, per
  `frontier_backlog.py:61-62` docstring).

## 5. C-1 SOUND — PASS (spot-check)

`scripts/ai/lib/slice_claim.py`:
- Real cross-process locking: `_transaction_lock()` (lines 110-121) opens `<store>.lock` and takes
  `fcntl.flock(..., LOCK_EX)` around the entire read-check-write critical section in `take_claim`,
  `release_claim`, and `check_paths` — all three route through the same lock, so no TOCTOU window
  between the conflict check and the write.
- Atomic writes: `_write()` (lines 124-138) writes to a `tempfile.mkstemp` in the same directory,
  `fsync`s, then `os.replace()` (atomic rename) — no partial-write/corruption window; stale temp
  file is cleaned up in a `finally`.
- Path-escape guarded: `_norm()` (lines 43-53) rejects absolute paths, `.`/`..` components,
  backslashes, non-stripped/non-canonical strings — claims can't be registered against paths
  outside the repo tree or use traversal tricks.
- Owner tokens: `secrets.token_urlsafe(32)` (line 170), cryptographically random; `_parse_claim`
  (line 83) rejects any stored token shorter than 32 chars on read-back. Token comparison
  (`owner_token != existing.owner_token`, lines 161/189) is a plain `!=`, not constant-time — a
  theoretical timing side-channel, but irrelevant here since the module's own docstring (lines
  2-6) states this registry is advisory-only, "not an access control boundary," so this is not a
  real regression.
- No obvious TOCTOU or path-escape found in the spot-check.

## 6. NO REGRESSION — PASS

`git diff main...HEAD --numstat` (28 files changed): every single file shows `+N  0` — 100%
insertions, zero deletions, across the whole branch. The one file that already existed on `main`,
`.agent/collaboration/AGENT-CATCHUP-QUEUE.md`, goes from 601 lines (as of `main`) to +75
appended / 0 removed — a clean union-style log append, not a rewrite. No existing file had any
line removed or altered by this merge.

## Overall

All six checks pass. Tests green, seams fail-safe and verified live (including with `aq-frontier`
physically absent), no secrets/hardcoded credentials, the coordinator-URL fallback is a
pre-existing repo-wide convention not a new violation, the debate/consensus gate is real and
cannot be silently bypassed via `add`, the C-1 claim registry uses sound file-locking +
atomic-write + path-validation primitives, and the entire branch is additive with zero deletions
to existing files. One non-blocking observation recorded: `aq-frontier accept --force` has no
persisted audit marker distinguishing a forced accept from a consensus accept — worth a follow-up
slice, not a merge blocker.

OVERALL: PASS
