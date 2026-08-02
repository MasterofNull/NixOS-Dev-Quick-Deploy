# Runner Deployment-Hardening — Independent Implementation Acceptance

Status: `PASS — IMPLEMENTATION CANDIDATE ACCEPTED; NO DEPLOYMENT AUTHORITY`  
Reviewer: `Codex independent reviewer`  
Owner activation authorization SHA-256:
`e94e36bf7a2f50dbab286bc35a07a80b5f1a6591f5cb93b94dd3837d1fd06059`

## Exact manifest

| Authorized candidate path | SHA-256 |
|---|---|
| `ai-stack/switchboard/execution_cell_runner.py` | `0370037e8822394fd7d8d8ace64c52d2fcf22f3797f0314c725790a43e1bfac6` |
| `scripts/testing/test-execution-cell-runner.py` | `0c290c36d4c4c6e07a7233a03650d617a7fb77929d8d827b38db6637179b7504` |
| `nix/modules/services/execution-cell-runner.nix` | `3ad51487deefa9a604471ad407c496033d32efcc406ec6400fc9f89b7c2e3f72` |
| `config/env-contract.yaml` | `7bf49e7d3b64fb8eeb8b7902893a96230a414325da137233586ccda2d0c8f96e` |

Frozen no-edit switchboard anchor:
`nix/modules/services/switchboard.nix` =
`10e3bbfd3bcaef1beef0782f106614968f7ba0cd193c68a8bf6a17ca68d1343a`.
No fifth candidate path is accepted by this record.

## Independent findings

The activation parser is total and fail-closed: any `LISTEN_*` claim prevents
fallback, malformed claims clear activation variables, and invalid/extra
descriptors are closed. FD 3 is accepted only as an AF_UNIX SOCK_STREAM
listening socket at the configured path. The adopted path does not bind, unlink,
chmod, or replace the systemd socket.

Production self-bind remains disabled. Explicit dev/test self-bind requires an
absent path and cleanup unlinks only the inode it created. Client identity is
resolved from the configured client user when needed; direct UID wins; peer
authorization is UID-only, so supplementary GID membership cannot become an
identity proof. The Nix/env changes keep the default-off self-bind setting and
declare the client-user configuration.

## Validation evidence

My direct hermetic execution was:

```text
python3 scripts/testing/test-execution-cell-runner.py
```

Result: `56/56 passed`, with two R6 deployment canaries explicitly deferred
(systemd socket activation and systemd cgroup delegation).

Orchestrator reproduction of the same command initially reported `27/37` inside
the managed sandbox because AF_UNIX/bwrap setup returned `EPERM`. That is a
sandbox capability restriction, not a candidate defect. The approved
outside-sandbox offline rerun exited `0`, reported `56/56 passed`, and retained
the same two R6 deployment-canary deferrals. No live service, socket unit,
provider, network, or deployment operation was performed in either acceptance
path. `py_compile` and `git diff --check` also passed during review.

## Decision and exclusions

**VERDICT: PASS.** This is an independent implementation acceptance of the
four-file candidate under the named owner activation. It does not stage, commit,
deploy, restart, enable traffic, call a provider, use network access, or grant
any further authority. The two deferred R6 canaries remain later deployment
evidence, not a claim that live acceptance occurred.
