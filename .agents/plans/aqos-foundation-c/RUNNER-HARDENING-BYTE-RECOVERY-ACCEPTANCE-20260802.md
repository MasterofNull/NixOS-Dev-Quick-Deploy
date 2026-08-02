# Runner Hardening Byte-Recovery — Independent Acceptance

Status: `PASS — BYTE RECOVERY ACCEPTED; NO DEPLOYMENT AUTHORITY`  
Reviewer: `codex-subagent-runner-hardening-byte-recovery-reviewer`  
HEAD: `99621ace21f1c60d7908ce82d8928f5001081592`

## Bound recovery chain

- Design SHA-256: `55a5ad894d811c6f70ed815f86fdbd7872a81a8cd157f8a1b7272cde539070b3`
- Authorization SHA-256: `53c3b8fc52bcff36be1c4391aeb316fce88e809e3134c8d3a431328adbed3d40`
- Lease first write: `2026-08-02T06:06:43Z`; final recovery byte: `2026-08-02T06:08:07Z`
- Deterministic recovered manifest: `0d1f9acfbd349a88fcc21084c04be1ba0d6ed7d86ba297bfb2ed3499577544e3`

The recovery source is the previously independent-accepted four-file candidate,
not a new semantic implementation. Exact restored hashes are:

| Path | SHA-256 |
|---|---|
| `ai-stack/switchboard/execution_cell_runner.py` | `0370037e8822394fd7d8d8ace64c52d2fcf22f3797f0314c725790a43e1bfac6` |
| `scripts/testing/test-execution-cell-runner.py` | `0c290c36d4c4c6e07a7233a03650d617a7fb77929d8d827b38db6637179b7504` |
| `nix/modules/services/execution-cell-runner.nix` | `3ad51487deefa9a604471ad407c496033d32efcc406ec6400fc9f89b7c2e3f72` |
| `config/env-contract.yaml` | `7bf49e7d3b64fb8eeb8b7902893a96230a414325da137233586ccda2d0c8f96e` |

Frozen no-edit switchboard anchor:
`10e3bbfd3bcaef1beef0782f106614968f7ba0cd193c68a8bf6a17ca68d1343a`.

## Validation and decision

Independent static review confirmed only the four recovered paths differ, the
index is empty, `py_compile` passes, and `git diff --check` passes. The
orchestrator independently ran the exact suite outside the managed sandbox:
exit `0`, `56/56` passed, with only two R6 systemd deployment canaries deferred.
The outside-sandbox context is required for AF_UNIX/bwrap capabilities; it is
offline test evidence, not live deployment evidence.

**VERDICT: PASS.** This acceptance confirms exact recovery of already accepted
bytes and no semantic widening. It authorizes neither staging, commit, deploy,
restart, service activation, traffic, runtime/provider/network action, nor live
canary execution. The deferred R6 canaries remain future deployment gates.
