---
title: "Foundation C C3b: Dedicated Execution Cell Runner — Rev3 Design Packet"
slice: "C3b"
status: "R0_REVIEWED_PASS"
review: "C3B-R0-REVIEW-OPUS.md (Opus, independent of codex author) — PASS; SF-1/SF-2/SF-3 non-blocking → R1"
revision: 3
kind: "design-only"
implementation_authorization: "NONE"
activation_authorization: "NONE"
predecessors:
  - "C0 lease+signer"
  - "C1 shadow issuance"
  - "C2 tool-lease gate, flag OFF (97131faa)"
successors:
  - "C4 network profiles"
  - "deferred C3a effect brokers"
---

# Foundation C — C3b Rev3: Dedicated Execution Cell Runner

## 1. Decision and scope

C3b supplies the confinement substrate for C2-admitted write-capable or subprocess
effects. The switchboard remains a hardened policy, routing, admission, and audit
process. It **does not** create user or mount namespaces, invoke `bwrap`, receive
relaxed hardening, or become a general execution host.

Instead, a small, socket-activated, persistent `aq-execution-cell-runner` service is
the only component permitted to construct an execution cell. The switchboard sends it
a serialized request over a local Unix-domain socket (UDS); the runner validates an
immutable execution grant and either creates a confined cell or returns a typed denial.
UDS is transport only. It grants no authority, and possession of a socket connection
does not substitute for a verified grant.

This is a design packet only. It authorizes neither implementation, Nix changes,
service deployment, runtime traffic, flag activation, database writes, nor commits.

## 2. Why a separate runner is required

The hardened switchboard is configured with `RestrictNamespaces=true`,
`NoNewPrivileges=true`, and no capabilities. Those constraints correctly prevent
`bwrap` from creating the user and mount namespaces it needs. Relaxing them would
expand the blast radius of the process that also owns routing, tool dispatch, and
remote-provider credentials.

Furthermore, current tool handlers execute as in-process Python. A wrapper cannot
retroactively confine an already-running handler; a separate worker process is needed
regardless. The runner therefore makes the privilege boundary explicit and keeps
switchboard hardening monotonic. C3b is not a justification to weaken the switchboard.

Persistent socket activation is the Rev2 baseline: it gives one observable service
identity, bounded startup behavior, and a narrow capability surface. A per-call
`systemd-run` transient-unit design is deliberately deferred for a separate comparison
and review; it is not an implicit fallback.

## 3. Authority model and immutable execution grant

### 3.1 Admission-to-runner handoff

After C2 admits a cell-required operation, its gate produces a **signed immutable
execution grant**. The runner accepts no caller-built bwrap arguments, filesystem
paths, environment values, effect labels, base revisions, or revocation epochs.
It verifies the grant signature and all bounds using its own trusted verifier before
it allocates a cell.

The grant is the runner's sole authority input and contains, at minimum:

| Field | Required invariant |
|---|---|
| `grant_id`, `lease_id`, `task_id`, `request_id` | bound identities, unique and replay-protected |
| signer key id, signature, schema version | independently verified; unknown versions deny |
| issue/expiry time and `revocation_epoch` | finite lifetime; stale or future-invalid epoch denies |
| immutable base revision | full verified Git object ID, not a symbolic ref |
| `effect_set` | signed closed set of declared effects and scopes |
| `exec_class` | `sandbox-required` only in C3b |
| trusted repository and requested logical paths | canonicalized and resolved by trusted policy code |
| resource limits | timeout, output bounds, requested cell class, and grant digest |

The signer must issue the grant at C2 admission time, not reconstruct it from mutable
lease state later. The runner persists only a grant digest and minimum lifecycle
receipt data needed for replay resistance and audit; it never treats the UDS peer,
socket path, or a mutable task document as authority.

### 3.2 Conservative multi-effect classification

`effect_class` is insufficient because one tool can combine subprocess, write,
network, and delegation effects. C3b consumes a closed, signed `effect_set`, with
per-effect scopes. Classification is conservative: an unknown, omitted, contradictory,
or unrepresentable effect means `classification-ambiguous` and denial. C3b supports
only the initial subset necessary for an offline execution cell:

| Effect | C3b treatment |
|---|---|
| read / deterministic validation | allowed only through the clone and declared read paths |
| write | allowed only inside the cell worktree and declared rebased paths |
| subprocess | allowed only as the grant's bounded command descriptor |
| network / remote delegation | denied; C4 is required before any grant can permit it |
| privilege, host process, mount, device, secret, or arbitrary environment access | denied |

`unsandboxed-authorized` is not honored in C3b. A cell-required execution either has
`sandbox-required` plus a valid grant or does not run.

## 4. Runner boundary and service posture

The runner is a dedicated, socket-activated service with a single request protocol,
one writer for its receipts, strict peer admission, bounded queueing, and low-cardinality
telemetry. It receives a serialized grant plus a command descriptor selected from the
grant, not an arbitrary shell fragment.

The runner's Nix declaration must be introduced before any live use and must explicitly
state all prerequisites: `pkgs.bubblewrap` availability; the required unprivileged
user-namespace setting; a dedicated unprivileged service account; UDS ownership/mode;
working roots; resource limits; and the smallest possible relaxation needed for the
runner alone to create namespaces. The switchboard keeps its present namespace,
capability, and `NoNewPrivileges` hardening unchanged.

The frozen Nix boundary for R3/R5 is:

- NEW `nix/modules/services/execution-cell-runner.nix`, imported by
  `nix/modules/services/default.nix`;
- NEW options under `mySystem.ai.executionCellRunner`: `enable` (default `false`),
  `socketPath` (default `/run/aq-execution-cell-runner/control.sock`),
  `stateDirectory` (default `aq-execution-cell-runner`),
  `maxConcurrentCells` (default `1`, maximum `2`), and `requestTimeoutSeconds`;
- NEW system user/group `aq-execution-cell-runner` and client group
  `aq-execution-cell-clients`; only `cfg.primaryUser` (the switchboard identity) joins
  the client group;
- `systemd.sockets.aq-execution-cell-runner` uses `SocketUser=aq-execution-cell-runner`,
  `SocketGroup=aq-execution-cell-clients`, and `SocketMode=0660`;
- `systemd.services.aq-execution-cell-runner` uses
  `RuntimeDirectory=aq-execution-cell-runner`,
  `StateDirectory=aq-execution-cell-runner`, cell root
  `/var/lib/aq-execution-cell-runner/cells`, quarantine root
  `/var/lib/aq-execution-cell-runner/quarantine`, and an executable path containing
  exactly the packaged runner dependencies plus `${pkgs.bubblewrap}/bin/bwrap`;
- runner hardening keeps `NoNewPrivileges=true`, empty `CapabilityBoundingSet`,
  `ProtectSystem=strict`, `ProtectHome=true`, private devices/tmp, and writable paths
  limited to the state/runtime directories. `RestrictNamespaces` permits only the
  namespace types required by the frozen bwrap argv on this runner unit.

R0 records the global threat decision explicitly: C3b requires
`security.unprivilegedUsernsClone = true`, which expands kernel attack surface for all
unprivileged users and therefore must be owner-ratified before R3 implementation. If
that global exposure is rejected, R3 stops for a separately reviewed privileged
namespace-broker design; it may not weaken switchboard hardening or silently choose a
setuid/unsandboxed fallback. `nix/modules/services/switchboard.nix` must retain
`NoNewPrivileges=true`, `CapabilityBoundingSet=""`, and `RestrictNamespaces=true`
byte-for-byte across R3/R5.

If bwrap, the userns prerequisite, the runner socket, the verifier, a trusted base
object, or cell creation is unavailable, the response is a typed
`confinement-unavailable` (or more specific typed) denial. There is no unsandboxed,
in-process, or direct-exec fallback.

## 5. R0–R6 delivery sequence

Each row is independently frozen, implemented, reviewed, and accepted. A later row
cannot silently expand an earlier row's authority.

| Stage | Bounded outcome | Must remain out of scope |
|---|---|---|
| **R0 — design** | grant schema/protocol, threat model, resource budgets, Nix hardening plan, test vectors | code, services, flags, live traffic |
| **R1 — pure grant and classification** | closed schemas; signature, expiry, replay, multi-effect and trusted-path classification as pure functions with golden vectors | sockets, clones, bwrap, Nix/runtime changes |
| **R2 — self-contained clone primitive** | transactional clone/worktree primitive at verified base OID, trusted path rebase, typed failure/quarantine/reconcile API | switchboard adapter, bwrap, live `.git` binds |
| **R3 — default-OFF runner** | socket-activated persistent runner, verified request protocol, bwrap cell, offline runner tests, default OFF | switchboard routing/adoption, live traffic, network |
| **R4 — revocation and performance** | mid-run epoch watcher, process-tree/cgroup termination, final epoch fence, measured APU budget gate | activation or auto-merge |
| **R5 — default-OFF switchboard adapter** | guarded adapter, receipt projection, AQ-QA integration and dashboard Service Coverage | turning the feature on or deployment cutover |
| **R6 — separate activation** | owner-authorized live canary, operator revoke/intervene proof, rollback plan | automatic broad rollout or auto-merge |

R0 is the only stage represented by this document. Each R1–R6 step requires its own
hash-bound design and authorization. The default-OFF state never conveys permission to
route production effects through the runner.

## 6. Cell construction: trusted clone, rebase, and confinement

### 6.1 Self-contained clone primitive

R2 replaces the draft's live `git worktree` bind model. Git worktrees contain a
`.git` pointer into common metadata, so binding a worktree plus its common `.git`
directory would give a cell unexpected access to live repository state. C3b must never
bind the live repository's `.git` metadata into a cell.

The primitive creates a fresh, self-contained clone from a trusted local source at the
grant's verified full base OID. It verifies that OID before use, makes clone setup
transactional, and confines all clone metadata inside the cell root. The source-side
repository is read only; the live worktree and common `.git` are not mounted. A failed
creation may not report success.

### 6.2 Trusted path rebasing

Grant logical paths are not host paths. The runner resolves them against a fixed cell
root after canonicalization and rejects absolute host paths, `..` traversal, symlink
escape, ambiguous Unicode/normalization forms where applicable, and paths outside the
signed allowlist. Any caller-facing `$HOME/Documents/...` convention is translated by
trusted runner code to a cell-relative destination; no caller may select a bind target.

### 6.3 bwrap mapping

Only the runner derives bwrap argv from verified grant fields. The baseline is deny
closed: read-only Nix store and required immutable runtime inputs; private `/proc`,
minimal `/dev`, and tmpfs `/tmp`; a single writable self-contained cell root; no host
home; no live repository or `.git` bind; `--unshare-net`; `--unshare-all`;
`--die-with-parent`; `--new-session`; no ambient capabilities; and a fixed
environment allowlist. C4, not C3b, is the only future authority that can propose a
network profile.

### 6.4 Trusted post-run validator

The cell's Git metadata and all files it controls are untrusted evidence, not the
verdict authority. GREEN publication requires a separate validator process outside
the cell. It receives only the signed grant digest, trusted base OID, cell root, and
declared output paths from the runner receipt.

The validator obtains the base tree from the trusted object source (or creates a fresh
validation clone whose config is constructed by the validator) and compares filesystem
bytes, modes, symlink targets, additions, and deletions directly against that base.
It does not run `git diff`, hooks, filters, clean/smudge drivers, textconv, external
diff commands, attributes, config, executables, or object helpers supplied by the
cell. It clears repository-local/system/global Git configuration and uses no
cell-controlled `.git`, `.gitattributes`, `.gitconfig`, hook, or executable.

Every changed path must equal one declared, signed, canonically rebased output path.
An undeclared change, special file, path escape, unreadable entry, base mismatch,
validator timeout, or validator error is a typed RED result. Only the trusted
validator's signed result digest can satisfy the final GREEN fence.

## 7. Lifecycle, quarantine, and revocation

1. **Admit.** Switchboard obtains C2's signed immutable grant and submits it to the UDS.
2. **Verify and reserve.** Runner verifies signature, freshness, replay state, grant
   digest, base OID, effect set, and resource limits before allocating any cell.
3. **Snapshot.** Runner creates the self-contained clone and emits a typed
   `workspace.snapshot` receipt bound to the grant digest and base OID.
4. **Execute.** Runner starts the bounded bwrap process tree and records its managed
   cgroup/process identity; no untracked subprocess is a successful execution.
5. **Supervise.** The sole authoritative epoch source is
   `ai-stack/switchboard/capability_lease_gate.py::resolve_current_epoch` reading
   `config/capability-lease-epoch`; R1 must freeze that API/hash or replace it through
   an explicit reviewed epoch-source contract. The runner authenticates the socket
   peer with `SO_PEERCRED`, verifies the grant signature/freshness, and binds a
   runner-generated heartbeat to `{grant_digest, runner_receipt_id, pid,
   proc_starttime, cgroup_path}`. Caller heartbeats are never trusted. Epoch and
   process liveness are polled every 250 ms; the local supervisor heartbeat deadline
   is 1 second. Unreadable/unparseable epoch state, peer mismatch, stale grant,
   heartbeat miss, receipt mismatch, or deadline expiry fails closed.
6. **Kill and wait.** On any terminal trigger, the runner closes admission, marks the
   receipt TERMINATING, sends cgroup-scoped termination, waits at most 500 ms, then
   uses `cgroup.kill`/SIGKILL and waits at most another 4.5 seconds for the entire
   tracked tree to disappear. Failure to prove disappearance is QUARANTINED, never
   GREEN and never a false finite-redelivery claim.
7. **Validate and final fence.** Only after the process tree is proven absent does the
   trusted post-run validator run. Immediately before publishing GREEN, the runner
   rereads the authoritative epoch, verifies grant freshness, heartbeat/receipt
   binding, terminal process absence, validator signature/digest, and declared-output
   equality in that order. Any failure changes the result to RED/QUARANTINED.
8. **Teardown.** GREEN retains the isolated clone diff for orchestrator review only;
   it is never auto-merged. RED, timeout, revoke, or teardown failure produces a typed
   rollback/quarantine receipt. Cleanup failure is quarantined and reconciled by a
   typed, idempotent reconciler; it is never deleted-and-reported-success.

The live worktree is never modified by a cell. Merge/import of a retained diff is a
separate orchestrator-and-review decision outside C3b.

## 8. Numeric APU budgets and telemetry gate

The host budget is a Renoir APU with 27 GB RAM. R4 must collect a reproducible baseline
before any activation. The following initial hard limits are intentionally conservative
and must be met at the configured concurrency cap; failure blocks R5/R6 rather than
being explained away in a summary:

| Metric | Acceptance limit |
|---|---:|
| p95 self-contained clone/snapshot latency | <= 3.0 s |
| p95 runner-to-bwrap spawn latency (after clone) | <= 250 ms |
| peak incremental RSS per idle/running cell | <= 768 MiB |
| default concurrent cells | 1 |
| maximum configurable concurrent cells before new review | 2 |
| teardown/revocation p95 from observed epoch bump | <= 5.0 s |
| unaccounted process or untyped terminal receipt | 0 allowed |

The R4 performance protocol is frozen as follows:

- command classes: `noop`, `read-validate`, and `single-file-write-validate`;
- cohorts: cold-cache and warm-cache, with at least **N=40 successful samples per
  cohort per command class** after five discarded setup iterations;
- cold-cache validity: the dedicated trusted test-object source is evicted with
  `posix_fadvise(POSIX_FADV_DONTNEED)` and `mincore` confirms at most 5% resident
  pages before each sample; warm-cache validity requires at least 95% resident pages
  after an untimed priming run. A cohort that cannot prove its cache bound is invalid;
- host bounds: no other cell runs, CPU governor and kernel/build revision are recorded,
  swap activity is zero during the sample, and `MemAvailable` remains at least 8 GiB.
  A separate pressure cohort may be reported at 6–8 GiB but cannot replace the
  acceptance cohorts;
- timing uses monotonic nanoseconds (`CLOCK_MONOTONIC_RAW` where available) at runner
  receipt boundaries. p95 is nearest-rank `sorted_samples[ceil(0.95*N)-1]`; no
  averaging of cohort percentiles;
- memory is the maximum of cgroup-v2 `memory.current` during the cell lifetime minus
  the measured idle-runner baseline; `memory.peak` is recorded when available;
- raw evidence is immutable JSONL with schema
  `{schema_version, run_id, host_fingerprint, kernel, build_revision, command_class,
  cache_cohort, cache_residency_pct, sample_index, monotonic_start_ns,
  clone_done_ns, bwrap_started_ns, process_terminal_ns, tree_absent_ns,
  validation_done_ns, receipt_published_ns, cgroup_peak_bytes, idle_baseline_bytes,
  mem_available_bytes, swap_delta_bytes, outcome, denial_code}` plus a content digest.

No failed/denied sample is discarded; it is recorded and fails the zero-untyped-outcome
gate. No hidden pool/reuse or `git stash` fallback is allowed to meet the limits. If
later performance requires pooling or reuse, it is a new design/review because
isolation changes.

R5 must satisfy the Service Coverage Contract: an AQ-QA integration check exercises
the full default-OFF adapter path through grant verification, UDS admission, runner
receipt projection, and a typed denial/success fixture (a `/health` probe alone does
not count); the dashboard exposes runner/receipt state and denial/revocation counts
without grants, paths, prompts, or high-cardinality IDs. Runner adapter code, AQ-QA
integration check, and dashboard projection must be committed together or in
immediately consecutive commits on the same branch; the sequence may not be released
or activated with any one of the three absent.

## 9. Explicit non-goals and safety constraints

- No switchboard hardening regression or namespace exception.
- No live `.git`, host home, arbitrary host path, secret, device, or network bind.
- No caller-provided bwrap argv, shell text, environment, base ref, or effect set.
- No raw UDS peer trust, mutable-lease rehydration, untracked child, or false terminal receipt.
- No `AI_AIDER_SANDBOX_FALLBACK_UNSAFE`-style fallback.
- No automatic merge, promotion, activation, traffic cutover, or deployment.
- No reuse/pooling, transient `systemd-run`, C4 network access, or effect-broker expansion
  without a separately reviewed slice.

## 10. Review obligations and freeze criteria

Independent reviewers must explicitly test the following nine historical blocking
findings rather than merely approve the architecture:

1. in-process handlers cannot be bwrap-confined;
2. the execution boundary receives an independently verifiable grant;
3. `exec_class` and conservative multi-effect classification are signed/closed;
4. caller-facing paths are securely rebased into the cell;
5. the clone contains no live `.git` bind or common-metadata escape;
6. clone creation, cleanup, quarantine, and reconciliation have typed truthful outcomes;
7. epoch revocation kills the tracked tree and a final epoch fence prevents false GREEN;
8. the numeric APU performance gate is measured, bounded, and observable; and
9. Nix grants userns privilege only to the runner while switchboard hardening remains monotonic.

The freeze packet must pin: this document; C2 predecessor hashes; trusted clone source
and verifier interfaces; runner protocol/schema; all authorized file inventory hashes;
the exact Nix service hardening declarations; golden vectors; and perf harness method.
It must also state the independent reviewer, explicit exclusions, and no-auto-merge
invariant. Any changed reviewed byte requires re-review. A successful R0 review is not
implementation authorization.

## 11. Questions reserved for independent review

1. Does a persistent socket-activated runner have a sufficiently narrow Nix hardening
   profile, or should a later transient-unit design be independently compared?
2. Are the stated latency/RSS/revocation budgets appropriate after a clean baseline,
   or should only stricter limits be frozen?
3. Is the trusted local clone source sufficiently immutable and access-controlled, or
   does R2 require a dedicated bare mirror boundary?
4. Which exact Nix userns option and service-level policy are correct for this host,
   while preserving switchboard restrictions exactly?
5. Does C2 already expose every grant field needed for R1, or must R1 add only pure
   schema/projection work before the runner exists?

**Requested reviewer result:** `PASS`, `FAIL`, or `REQUEST_REVISION` against this
document's R0 scope and the nine obligations above. No review outcome authorizes build
or activation unless a later owner authorization says so explicitly.
