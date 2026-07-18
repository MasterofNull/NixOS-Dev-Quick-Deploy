# C0 Design Packet — lean-ctx Workspace Identity Guard

Design date: 2026-07-17
Status: **DESIGN ONLY — NOT IMPLEMENTATION AUTHORITY**
Scope: contract-first prevention of cross-workspace `ctx_session load` in the system-packaged lean-ctx
stdio surface

## 1. Evidence and problem statement

The installed lean-ctx v3.3.7 stores sessions under one data directory and maintains one mutable
`sessions/latest.json` pointer. Local read-only inspection and isolated tests established:

1. A fresh stdio process is cwd-aware. With a shared temporary data directory, startup in repository
   A created/selected A, startup in B created/selected B, and returning to A reused A.
2. The global pointer flipped A -> B -> A. It is process-global recency state, not workspace identity.
3. A live process launched in A accepted `ctx_session load(session_id=<B>)` and changed its active root
   to B. The load operation does not bind the target session to the process launch workspace.
4. `ctx_session load` supports an explicit session ID, while the stdio CLI has no documented
   `--project-root` option. HTTP `serve` has `--project-root`, but changing transport is outside C0.
5. `LEAN_CTX_DATA_DIR` can isolate an entire store, but doing so fragments caches, knowledge, agent
   state, and statistics. C0 must keep the shared store.

The defect is therefore not ordinary cwd detection. It is the absence of an immutable, client-bound
workspace identity check around later session loads. A stale or concurrently changing global pointer
must neither authorize nor deny a load.

## 2. Objective

C0 shall place a fail-closed stdio guard in front of the pinned lean-ctx binary. The guard shall:

- bind each server process to a canonical launch workspace identity;
- verify the server's initial active root before allowing ordinary tool traffic;
- allow `ctx_session load` only when the target session's canonical `project_root` is the same launch
  workspace root;
- reject missing, malformed, ambiguous, traversing, symlinked, or cross-root session subjects;
- leave `sessions/latest.json` untouched and treat it as non-authoritative telemetry only;
- preserve one shared lean-ctx data store;
- expose machine-readable state and rejection counters; and
- preserve lean-ctx CLI behavior when the executable is invoked with ordinary CLI arguments.

C0 does not repair, migrate, delete, merge, or select historical sessions.

## 3. Identity contract

### 3.1 Launch identity

At process start, before launching the real MCP server, the guard computes:

```text
canonical_cwd       = realpath(getcwd())
workspace_root      = realpath(git rev-parse --show-toplevel) when successful
                      otherwise canonical_cwd
workspace_kind      = "git-worktree" or "directory"
git_common_dir      = realpath(git rev-parse --git-common-dir) when applicable
workspace_id        = sha256(
                        "lean-ctx-workspace-v1\0" +
                        workspace_kind + "\0" +
                        workspace_root + "\0" +
                        (git_common_dir or "")
                      )
```

Authorization equality is exact canonical `workspace_root` equality. `git_common_dir` is recorded to
diagnose related worktrees but never collapses distinct worktree roots. Nested repositories bind to
their own top-level. Symlink aliases normalize to one root.

Failure to determine or canonicalize cwd is a startup failure. Non-Git directories are supported as
distinct canonical directory workspaces; `/` is not silently substituted for an unavailable cwd.

### 3.2 Session subject

For a requested session ID, the guard opens exactly:

```text
${LEAN_CTX_DATA_DIR:-$HOME/.lean-ctx}/sessions/<session-id>.json
```

The pinned v3.3.7 adapter accepts only ASCII IDs matching
`^[0-9]{8}-[0-9]{6}-[0-9]{6}s[0-9]{1,6}$` (24-29 bytes) and containing no separator. This grammar is
an explicit adapter constant, not inferred from filenames; a future upstream format requires a
reviewed adapter revision. Golden vectors must accept `20260717-170127-645596s0` and suffix values
through six digits, and reject empty/default-latest, separators, Unicode digits, missing `s`, a
seven-digit suffix, and any ID over 29 bytes. The guard must
use directory-relative, no-follow opening; require a regular file owned by the current user; enforce a
bounded size; parse one JSON object; require its internal `id` to equal the requested ID; and require a
non-empty absolute `project_root` whose canonical value equals `workspace_root`.

Missing data, invalid JSON, schema mismatch, ownership/type failure, canonicalization failure, or root
mismatch is a denial. There is no fallback to `latest.json`, filename ordering, timestamps, task text,
`shell_cwd`, repository basename, or Git common-directory equality.

### 3.3 Global pointer

`sessions/latest.json` is defined as a global convenience pointer controlled by lean-ctx. It may
legitimately oscillate between concurrently active repositories. C0 shall not edit, lock, repair,
replace, or use it as authorization evidence. Dashboard display, if any, must label it `global latest`
and show it separately from the client-bound workspace ID and active session root.

## 4. Guard behavior

### 4.1 Packaging and invocation

The Nix package retains the upstream binary as a private sibling and installs the guard at the public
`lean-ctx` path. Existing MCP configurations continue invoking the same public path, so no global
Claude, Codex, Gemini, Antigravity, or other client configuration edit is required.

Both executables are closure-bound: the public guard uses an interpreter path substituted from the
Nix store at build time, and the private upstream path is an immutable Nix-store path supplied by the
package. `/usr/bin/env`, shell lookup, and ambient `PATH` resolution are forbidden for either edge.

- No arguments: run the guarded stdio proxy.
- Ordinary lean-ctx CLI arguments: exec the private upstream binary unchanged.
- `serve`: exec unchanged in C0; HTTP guarding is explicitly deferred.
- An internal, package-bound environment value may identify the private binary, but C0 introduces no
  new user configuration variable.

The wrapper must not run setup, `doctor --fix`, hook repair, session cleanup, or global configuration
mutation.

### 4.2 Startup preflight

The guard launches the real stdio server with the original cwd and shared data directory, relays MCP
initialization, then obtains `ctx_session status` through an internal request before releasing general
tool calls. For the pinned v3.3.7 protocol adapter, it parses the returned active root and requires
exact canonical equality with `workspace_root`.

If the status call fails, its response is ambiguous, the installed protocol shape differs, or the root
does not match, the guard emits a structured startup-denial event, terminates the child cleanly, and
returns an MCP error. It must not try another session, load `latest`, reset state, or create a session.

Internal request IDs use a collision-proof namespace and are never exposed to the client. The proxy
tracks every outstanding client ID and allocates an internal ID only after proving it is not in that
set; a merely improbable prefix is insufficient. Requests
received before preflight completion are bounded and queued; queue overflow fails closed.

### 4.3 Load interception

For every `tools/call` whose name is `ctx_session` and whose action is `load`:

1. Require an explicit `session_id`; default-latest load is denied.
2. Resolve and validate the exact session subject under Section 3.2.
3. If the target root differs, return an MCP tool error with stable reason
   `workspace_root_mismatch`; do not forward the request.
4. If validation succeeds, forward the original request without rewriting its ID or arguments.
5. Inspect the response and run a post-load internal status check. If the active root is no longer the
   launch root, stop the child and fail closed.

Concurrent replacement of a same-user session file is outside the malicious-local-user threat model,
but the guard records pre/post metadata and denies detected drift. C0 must not claim protection from a
hostile process with the same UID; an upstream atomic load-by-digest API would be required for that.

`ctx_session reset`, cleanup, and all other mutating session operations retain upstream behavior only
when startup identity remains valid. C0 adds no new authority to invoke them.

### 4.4 Protocol safety

The proxy supports only the stdio framing emitted by the pinned packaged lean-ctx version. It shall
preserve message bytes except for denied requests and its internal status calls, tolerate out-of-order
responses, bound line/message size and queued requests, propagate child exit, and never compress or
rewrite evidence output. Unsupported framing or malformed JSON fails closed with a stable diagnostic.

## 5. Telemetry and monitoring contract

The guard atomically maintains bounded multi-process state at:

```text
${LEAN_CTX_DATA_DIR:-$HOME/.lean-ctx}/workspace-identity-status.json
```

This is guard telemetry, not session state or configuration. It contains no prompt or file content.
Schema v1 contains an `instances` map capped at 64 records plus one deterministic `aggregate`.
Instance identity is `workspace_id + child_pid + child_start_time` so PID reuse cannot overwrite an
older process. Each record contains:

- `schema_version`, `generated_at`, `guard_version`;
- `workspace_id`, `workspace_kind`, redacted root label, and Git-worktree indicator;
- `active_session_id`, active-root match boolean, and child PID/start time;
- cumulative `startup_checks`, `allowed_loads`, `rejected_loads`, and `protocol_failures`;
- `last_outcome` and closed `last_reason` vocabulary;
- `global_latest_session_id` as optional observation explicitly labeled non-authoritative; and
- `data_dir_shared: true`, `lifecycle` (`active` or `terminal`), `heartbeat_at`, and `terminal_at`.

Active records become stale after 120 seconds without a heartbeat. Successful terminal records expire
after 15 minutes; red terminal outcomes remain visible for 60 minutes. Capacity eviction removes
expired successful records first, then the oldest non-red stale record. If 64 unexpired red records
already occupy the map, the writer increments the saturating cumulative diagnostic counter
`dropped_red_records_total` and sets `dropped_red_until` to
`max(existing_deadline, drop_time + 60 minutes)`. The aggregate remains red only while the injected
UTC clock is earlier than that deadline; expiry clears the aggregate condition but never decrements
the cumulative counter. A fresh green writer can therefore never erase an unexpired red failure from
another process, while one historical capacity event cannot hold the system red forever.

The aggregate is recomputed under the same lock from all retained records using fixed severity order
`red > amber > green > unavailable`: red when any retained record has mismatch/startup/protocol
failure or `now < dropped_red_until`; amber when no red exists but any record is stale or no guarded
process is active; green only when at least one active record is fresh and every fresh active record
matches its launch root; unavailable only when the telemetry object cannot be validated. Counters are
saturating unsigned 64-bit values, and aggregate reason selection is lexical within the worst severity
so output is deterministic.

Updates use a sibling lock plus atomic replace, preserve counters under concurrent writers, cap string
lengths, and tolerate absent/corrupt prior telemetry by publishing a degraded status rather than
authorizing a load. No session file or `latest.json` is modified.

The dashboard endpoint returns a closed machine object with freshness, active-root match, rejection
count, last reason, and guard activation. The dashboard shows at least one visible badge/card:

- green: guard active, telemetry fresh, active root matched;
- amber: no recent guarded stdio process or stale telemetry;
- red: mismatch denial, startup denial, or protocol failure; and
- `--` only when the endpoint explicitly reports unavailable, which remains a visible defect signal.

Phase 0 checks the integration path, not merely file presence: closure-bound packaged command
identity, guarded startup/status in an isolated store, one allowed same-root load, one rejected
cross-root load, pointer non-mutation, telemetry schema, dashboard API projection, and two concurrent
installed guarded processes proving that an unexpired red record remains the live API's worst state
while a fresh green process reports.

## 6. Exact bounded implementation inventory

C0 implementation authority, if separately granted after review, is limited to these nine files:

1. `scripts/ai/lean-ctx-workspace-guard`
   - New self-contained stdio guard, identity validator, telemetry writer, and CLI passthrough.
2. `scripts/testing/test-lean-ctx-workspace-identity.py`
   - New isolated protocol, identity, concurrency, telemetry, and passthrough regression suite.
3. `nix/pkgs/lean-ctx.nix`
   - Preserve the pinned real binary privately and expose the guard at the existing public executable.
4. `scripts/testing/harness_qa/phases/phase0.py`
   - Add one integration-path `CheckResult` for the installed guard and machine telemetry.
5. `dashboard/backend/api/routes/aistack.py`
   - Add the read-only workspace-identity telemetry projection to the existing Agent Ops API surface.
6. `assets/dashboard.js`
   - Render guard state, root-match health, rejection count, freshness, and last reason.
7. `.agent/skills/lean-ctx/SKILL.md`
   - Replace unsafe default-latest guidance with explicit guarded-load and root-preflight rules.
8. `docs/agent-guides/20-LOCAL-LLM-USAGE.md`
   - Document workspace identity, troubleshooting, machine status, and non-authoritative latest state.
9. `config/validation-check-registry.json`
   - Register the focused path-gated validation command for the guard slice.

Any tenth file is a hard stop requiring a reviewed amendment. In particular, `LEAN-CTX.md` is
lean-ctx-owned and must not be edited manually.

## 7. Lease-aware execution order

C0 is not authorized by this packet. A later implementation authorization must acquire or verify
exclusive leases before each group:

1. **Contract core:** files 1-2 and 7-9. Implement the guard contract and isolated tests first.
2. **Packaging activation:** file 3 only after any active Nix/package lease clears. Until then, tests
   run the guard explicitly against the pinned real binary and no activation claim is permitted.
3. **Operational integration:** file 4 only after the active Phase-0 lease clears. A passing unit suite
   without this integration check is not completion.
4. **Visibility:** files 5-6 only after dashboard leases clear. No delivery claim is permitted while
   the dashboard field is absent or `--` despite available telemetry.

If an active lease cannot be obtained, stop at the last completed group, record the candidate as
partial, and do not stage, deploy, or claim guard activation. No group may silently bypass another
agent's changes.

## 8. Required tests

All tests use two temporary Git repositories and an isolated `LEAN_CTX_DATA_DIR`; they never touch or
clean the user's real session store.

1. **A -> B -> A baseline:** upstream fresh processes create/select distinct roots and reuse A.
2. **Same-root explicit load:** guarded A loads another A session and remains A.
3. **Cross-root load:** guarded A receives B's ID, returns `workspace_root_mismatch`, never forwards
   the request, and remains A.
4. **Default latest denied:** omitted `session_id` is rejected even when global latest happens to be A.
5. **Pointer immutability:** hash and metadata of test-store `latest.json` are unchanged by the guard's
   validation/denial path; ordinary upstream startup effects are measured separately.
6. **Concurrent A/B:** two guarded processes share the store; pointer oscillation cannot change either
   process's bound identity or authorization result.
7. **Symlink/nested/worktree:** symlink aliases normalize; nested repos and sibling worktrees remain
   distinct.
8. **Malformed subjects:** traversal ID, symlink, non-regular file, wrong owner where testable,
   oversized file, malformed JSON, internal-ID mismatch, relative/empty root, and missing file deny.
9. **Startup mismatch/status failure:** child is terminated and no ordinary tool call is released.
10. **Post-load drift:** unexpected active-root change terminates the child and records failure.
11. **Protocol behavior:** out-of-order replies, malformed/oversized frames, queue bounds, client EOF,
    child exit, and signal forwarding.
12. **CLI passthrough:** `--version`, `sessions list`, and non-stdio commands preserve exit/output and
    do not enter proxy mode.
13. **Telemetry:** atomic concurrent A/B records and worst-state aggregation, PID-reuse identity,
    deterministic severity, retention/expiry/capacity behavior, closed reasons, stale/degraded
    projection, no prompt content, and non-authoritative pointer labeling.
14. **Dashboard/Phase 0:** live endpoint and visible UI state consume real isolated guard telemetry;
    hardcoded healthy fixtures do not satisfy acceptance.

Focused tests must run with lean-ctx output rewriting disabled or through an evidence-safe raw path so
protocol bytes and pointer hashes cannot be corrupted by the compression hook.

## 9. Acceptance criteria

C0 may be accepted only when all are true:

- the exact nine-file candidate is hash-frozen and independently reviewed;
- same-root loads work and every tested cross-root/default-latest load fails closed;
- startup and post-load active roots equal the immutable launch root;
- the guard never writes, repairs, or authorizes from `latest.json`;
- the shared data directory remains shared and existing sessions remain intact;
- CLI passthrough remains compatible;
- focused tests, Phase 0, and Tier 0 pass;
- live dashboard telemetry shows the installed guard and real status; and
- a concurrent fresh green process cannot hide an unexpired red record, with the frozen
  120-second/15-minute/60-minute lifecycle thresholds enforced; and
- a distinct reviewer verifies exact-subject hashes, lease compliance, exclusions, and activation
  evidence after the Nix package is deployed.

## 10. Explicit exclusions

C0 does not authorize:

- edits to any global Claude, Codex, Gemini, Antigravity, shell, MCP, or lean-ctx configuration;
- direct or indirect writes to `sessions/latest.json`;
- session cleanup, deletion, migration, merge, deduplication, reset, or history repair;
- per-project `LEAN_CTX_DATA_DIR` values or fragmentation of knowledge/caches/statistics;
- manual edits to `LEAN-CTX.md`;
- HTTP `serve` proxying or transport migration;
- upstream publication, network submission, or lean-ctx cloud sync;
- deployment, service restart, traffic activation, staging, or commit;
- protection against a malicious same-UID process racing session files; or
- work outside the exact nine-file inventory.

## 11. Reviewer questions

An independent design reviewer must decide:

1. Is exact canonical root equality the correct authorization boundary for Git worktrees and non-Git
   directories?
2. Does the pinned v3.3.7 status/protocol adapter fail closed without creating a compatibility trap?
3. Does package-level wrapping activate all existing stdio clients without global configuration edits?
4. Are session-file validation and concurrency controls sufficient for the stated accidental-drift
   threat model?
5. Does telemetry meet dashboard parity without treating the global latest pointer as active truth?
6. Are the nine files and lease sequencing minimal, complete, and non-overlapping with active work?

`RECORD: design-only C0 contract; no implementation, activation, cleanup, or global configuration authority.`
