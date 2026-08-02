---
title: "Foundation C — Runner Deployment-Hardening Codex Depth Review"
reviewer_identity: "codex"
reviewer_role: "independent architecture, security, and SRE reviewer"
reviewed_at_utc: "2026-08-01"
review_status: "REQUEST_REVISION"
review_scope: "deployment-hardening design and freeze only; read-only review"
subject_path: ".agents/plans/aqos-foundation-c/RUNNER-DEPLOYMENT-HARDENING.md"
subject_sha256: "68e3b120db2e215fae12fecbf916de18571c9cc8f10ba0828f53709cd579e5b2"
freeze_path: ".agents/plans/aqos-foundation-c/RUNNER-DEPLOYMENT-HARDENING-FREEZE.md"
freeze_sha256: "aacce522925514a5b409c7b34f4306e741a3d47217fe1a69e0bcd48e0436cf82"
baseline_head: "e7bf91deb4693a6667cd3c3ed10b0988b4143ef6"
implementation_authority: "NONE"
activation_authority: "NONE"
---

# VERDICT: REQUEST_REVISION

The exact design subject and freeze record above were reviewed against the exact
baseline HEAD above. This is a binding depth review for the frozen runner
deployment-hardening slice. It does not authorize a build, activation, deploy,
runtime traffic, staging, commit, or any change outside a later corrected and
re-frozen subject.

## Reviewed baseline and scope anchors

| Path | SHA-256 | Role |
|---|---|---|
| `ai-stack/switchboard/execution_cell_runner.py` | `34837d4dc6718afccc2f663e590024f7d18723712a0a42c7cefd1969273e60fb` | Proposed socket-acquisition edit target; matches freeze baseline. |
| `scripts/testing/test-execution-cell-runner.py` | `4f8094bcc11cb29d8ce9ec8348bb4356d51df862bab4ee1124fcd87b13ea93ef` | Required activated-fd and self-bind test target. |
| `nix/modules/services/execution-cell-runner.nix` | `d2f12a1cdcf4c33aae17239fbdbf92877a5b8940cd52e1946f60eab2cb6e1d12` | No-edit socket-unit and runner-hardening anchor. |
| `nix/modules/services/switchboard.nix` | `10e3bbfd3bcaef1beef0782f106614968f7ba0cd193c68a8bf6a17ca68d1343a` | No-edit switchboard hardening/parity anchor. |

At review time both `aq-execution-cell-runner.socket` and
`aq-execution-cell-runner.service` were inactive. No live deploy exercise was
run: it requires the later owner activation and re-activation explicitly outside
this review's authority.

## BLOCKING findings

### B1 — fallback can again delete a systemd-owned socket

The proposed `_acquire_listen_socket` retains the existing self-bind fallback's
unconditional `unlink(config.socket_path)`. A manual/explicit service start or
restart, or an absent/malformed activation environment while the `.socket` unit
already owns the pathname, reaches that fallback and deletes the systemd-owned
socket. That recreates the deployment defect the slice is meant to fix.

The design must change the acquisition contract so fallback never removes an
existing production socket. Safely parse activation state; if systemd owns or may
own the configured path but no valid activated FD is available, preserve the path
and fail closed rather than self-binding. Standalone tests can use a fresh absent
temporary pathname.

Required tests: explicit/manual service-start and restart semantics; an existing
systemd-style socket pathname with absent activation variables; and proof that all
such failure paths leave pathname, group, and mode unchanged.

### B2 — activated-FD validation and descriptor hygiene are incomplete

The sketch accepts `LISTEN_FDS >= 1`, adopts fd 3, neither proves that it is the
single expected AF_UNIX stream listener for `config.socket_path` nor handles FDs
4 through `3 + LISTEN_FDS - 1`. The unit declares exactly one `ListenStream`, so
the runner must enforce that invariant or deliberately close every unexpected
activation FD. Otherwise unexpected inherited descriptors remain open in the
runner process.

Also, `int(os.environ.get("LISTEN_FDS", "0"))` can raise on malformed input,
causing a crash loop rather than a controlled fallback/fail-closed posture.

Require a total parser; `LISTEN_PID == getpid()`; exactly one received FD;
validation of fd 3 as the expected AF_UNIX stream listener at the configured path;
closure of all unadopted received FDs; and clearing of activation environment after
acquisition. Invalid PID, zero, malformed, multiple, wrong-family/type/path, and
adopted-exit/restart cases must be golden tests. The activated path must never
unlink, chmod, bind, or listen on the systemd-owned socket.

### B3 — claimed exact two-file ceiling is not fully hash-bound

The freeze record names the runner and its test as the only editable files but
pins only the runner's pre-fix hash. It does not pin the test baseline. Therefore
the stated two-file ceiling cannot be audited exactly at owner-activation or
independent-review time.

Before any activation, amend and re-freeze the record to pin the test hash above,
and retain the runner-Nix and switchboard-Nix no-edit anchors above. The corrected
design and freeze bytes require fresh review and fresh owner authorization.

## Non-regression assessment

- The proposed one-seam change can preserve SO_PEERCRED because
  `_handle_connection` remains outside the permitted edit. The UDS remains
  transport only, and non-client peers remain dropped before request parsing.
- Per-request Ed25519 grant verification, typed deny behavior, cell construction,
  out-of-cell validation, and cgroup reaping are likewise outside the ceiling and
  must remain byte-identical.
- The systemd socket unit supplies `SocketGroup=aq-execution-cell-clients`,
  `SocketMode=0660`, `Accept=false`, and `RemoveOnStop=true`; correct FD adoption
  is the appropriate way to preserve that ownership/mode boundary. Adding the
  switchboard to the runner group or chowning from the runner would be an
  authorization-boundary regression.
- Current switchboard hardening remains a no-edit anchor, including
  `NoNewPrivileges=true`, empty `CapabilityBoundingSet`, and
  `RestrictNamespaces=true`. No switchboard parity change is authorized.
- The documented deploy gate is directionally correct only when it proves, after
  the runner starts, socket group/mode persistence, repeated clients rather than
  merely the activation-triggering connection, and a full
  mint-to-typed-GREEN round trip. It must additionally cover B1/B2 restart and
  invalid-activation cases.
- The self-bind fallback remains acceptable only for an explicitly standalone,
  fresh-absent test pathname. It must not be allowed to overwrite a potentially
  systemd-owned configured production socket.

## Required disposition

Revise the design and freeze to close B1–B3, perform a fresh independent depth
review of the changed bytes, then obtain a new single-use owner activation before
any build. No live deploy exercise, shadow re-activation, or commit is authorized
by this review.
