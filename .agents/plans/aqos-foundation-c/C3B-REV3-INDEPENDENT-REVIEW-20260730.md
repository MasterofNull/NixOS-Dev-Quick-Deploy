---
title: "Foundation C C3b Rev3 — Independent R0 Design Review"
review_status: "PASS"
review_scope: "R0_DESIGN_ONLY"
reviewer_identity: "codex-subagent-c3b-independent-reviewer"
reviewer_role: "independent architecture, security, SRE, and systems reviewer"
reviewed_at_utc: "2026-07-30"
subject_path: ".agents/plans/aqos-foundation-c/C3B-DESIGN-AND-AUTHORIZATION.md"
subject_sha256: "709346ac6dd353c89d0a871e7cffd692ead9d113aa23d9a3709dba7f1b218c3e"
implementation_authority: "NONE"
activation_authority: "NONE"
---

# Foundation C C3b Rev3 — Independent R0 Design Review

## Verdict

**PASS** — the exact reviewed subject at SHA-256
`709346ac6dd353c89d0a871e7cffd692ead9d113aa23d9a3709dba7f1b218c3e`
resolves the requested R0 design revisions and addresses the nine historical C3b
blocking findings at the appropriate design depth.

This verdict accepts only the R0 design. It does not authorize implementation,
activation, deployment, runtime traffic, flag changes, Nix changes, staging, commit,
or progression through R1–R6 without their own hash-bound designs, reviews, and owner
authorizations.

## Reviewed subject

- Path:
  `.agents/plans/aqos-foundation-c/C3B-DESIGN-AND-AUTHORIZATION.md`
- SHA-256:
  `709346ac6dd353c89d0a871e7cffd692ead9d113aa23d9a3709dba7f1b218c3e`
- Scope: dedicated persistent socket-activated execution-cell runner, R0 design only

## Verified revision areas

### 1. Trusted validator isolation

The cell-controlled clone, including its Git metadata and filesystem contents, is
treated as untrusted evidence. GREEN requires a separate validator using the signed
grant digest, trusted base OID, runner receipt, and declared outputs. The validator
does not consume or execute cell-controlled Git configuration, hooks, attributes,
filters, clean/smudge drivers, textconv, external-diff commands, object helpers, or
executables. It compares filesystem bytes, modes, symlink targets, additions, and
deletions against an independently trusted base and denies undeclared or unsafe
changes.

### 2. Epoch authority, heartbeat binding, and terminal ordering

The design names
`ai-stack/switchboard/capability_lease_gate.py::resolve_current_epoch`, reading
`config/capability-lease-epoch`, as the authoritative epoch source subject to R1 hash
freeze or an explicitly reviewed replacement. It combines `SO_PEERCRED`, verified
grant signature/freshness, and a runner-generated heartbeat bound to grant digest,
runner receipt, PID, process start time, and cgroup.

The terminal sequence is explicit and fail closed: close admission; mark
`TERMINATING`; terminate the cgroup; wait; escalate through `cgroup.kill`/`SIGKILL`;
prove whole-tree absence; run the trusted validator; then perform the final epoch,
freshness, heartbeat/receipt, process-absence, validator-signature, and
declared-output fence before GREEN. Unproven termination is quarantined and cannot
produce a false finite-redelivery or GREEN claim.

### 3. Reproducible numeric APU performance protocol

The design freezes numeric latency, memory, revocation, concurrency, and
unaccounted-process limits. It requires cold-cache and warm-cache cohorts for three
command classes with at least `N=40` successful samples per cohort and command class
after five discarded setup iterations. Cache residency, host memory/swap conditions,
monotonic timing boundaries, nearest-rank p95 computation, cgroup-v2 memory
measurement, and immutable content-digested JSONL evidence are specified. Failed and
denied samples remain evidence and cannot be discarded to improve the result.

### 4. Exact Nix boundary and user-namespace threat decision

The design identifies the new runner module/import, option namespace, service and
client identities, UDS ownership/mode, runtime/state/quarantine roots, bounded
concurrency, packaged bwrap path, and runner hardening. The runner retains
`NoNewPrivileges=true`, an empty capability bounding set, strict filesystem
protection, private devices/tmp, and only the namespace allowance required by its
frozen bwrap invocation.

It explicitly records that `security.unprivilegedUsernsClone = true` expands the
kernel attack surface globally and therefore requires owner ratification before R3.
If rejected, R3 must stop for a separately reviewed namespace-broker design.
`nix/modules/services/switchboard.nix` retains `NoNewPrivileges=true`,
`CapabilityBoundingSet=""`, and `RestrictNamespaces=true`; C3b provides no authority
to weaken those controls.

### 5. Service Coverage and commit cadence

R5 requires an AQ-QA integration check that exercises the full default-OFF adapter
path through grant verification, UDS admission, runner receipt projection, and typed
success/denial fixtures; a health-only probe is insufficient. The dashboard must
surface low-cardinality runner, receipt, denial, and revocation state without exposing
grants, paths, prompts, or high-cardinality identifiers.

Runner adapter code, the AQ-QA integration check, and the dashboard projection must be
committed together or in immediately consecutive commits on the same branch. No
release or activation may occur while any Service Coverage leg is absent.

## Architectural conclusion

The persistent socket-activated runner is the accepted R0 baseline. The switchboard
remains the hardened admission, routing, and audit client and never invokes bwrap or
executes effectful handlers in process. The UDS is transport rather than authority;
the runner independently verifies the immutable signed execution grant. Per-call
`systemd-run`, network enablement, pooling/reuse, live Git metadata binds,
unsandboxed fallback, and automatic merge remain outside this design.

## Editorial note

The subject's review-obligation shorthand that Nix grants user-namespace privilege
"only to the runner" is interpreted as: only the runner managed service relaxes its
systemd namespace restriction. The subject correctly states separately that
`security.unprivilegedUsernsClone = true` is a global kernel exposure requiring owner
ratification. Its reserved Nix question is therefore an owner-ratification and
containment question, not an unresolved silent fallback.

## Explicit exclusions

- no implementation or source-code changes;
- no R1–R6 authorization or activation;
- no Nix evaluation, module mutation, rebuild, or deployment;
- no runner socket, process, namespace, bwrap, or live traffic;
- no C2/C4/effect-broker expansion;
- no automatic merge, promotion, or repository mutation;
- no staging, commit, or push authority.

## Final verdict

**VERDICT: PASS — the exact R0 design subject at SHA-256
`709346ac6dd353c89d0a871e7cffd692ead9d113aa23d9a3709dba7f1b218c3e`
is accepted for design freeze preparation only; no implementation or activation
authority is granted.**
