# Foundation C Revision 3 — Binding Design Re-review

Status: `PASS_DESIGN — PREPARED_ONLY; PREREQUISITES RETAINED`  
Reviewer: `Codex orchestrator, independent of revision implementers`  
Reviewed: 2026-08-01 UTC

## Exact subjects and verdicts

| Subject | SHA-256 | Verdict | Freeze eligible now |
|---|---|---|---|
| runner design | `48cae30d1c93ff9e76fdff0e3866f885b54e544de95c978c8286a1c8065f0c63` | `PASS_DESIGN` | `yes, through exact candidate below` |
| runner freeze candidate | `430093d2c4af905793c9cdf4539b9b5a50c93b16976ede2d08795f34921a25df` | `PASS_FREEZE_CANDIDATE` | `yes; owner activation still required` |
| C6 design | `e39331414370683431aa42100c79aa3d7d5836d02d22ecdd64df88d6fae692a0` | `PASS_DESIGN` | `no` |
| C4 design | `9c8e27a0907760fc05909f6c5e62d1dc9ee080a8a4e046f064add79d6e36e5af` | `PASS_DESIGN` | `no` |
| C3a-2 design | `d633b2cb8c6c7cf8837a3c1bfd2d6228d480db0d1e7b597cb8630029127cadc1` | `PASS_DESIGN` | `no` |

All files remain PREPARED_ONLY. This review grants no implementation, owner
activation, deployment, traffic, provider/network action, staging, or commit.

## Correction closure

- Runner freeze now binds the exact passing design, prior acceptance, current
  HEAD, four editable predecessors, switchboard no-edit anchor, roles, commands,
  default-OFF build boundary, and separate live exercise. It is a valid exact
  freeze candidate, not a self-activation.
- C6 adds a durable request-bound WAL with
  `prepared -> epoch_committed -> receipt_committed -> audit_projected`, recovery
  for every crash boundary, stable replay receipt, and quarantine on divergent
  WAL/epoch/receipt state. It cannot double-bump or report success before the
  receipt is durable.
- C4 freezes three exact receiver actions, schemas, identities, byte/deadline/
  concurrency limits and UDS endpoints; completes schema/fixture/Nix inventory;
  denies before receiver invocation on audit saturation; and supplies measurable
  100/500/2000/5000 ms teardown gates with fail-stop recovery.
- C3a-2 makes execution-grant and lane-registry immutable inputs, separates the
  pre-receive session key from post-receive blob CAS, and adds an import-prepared/
  effect-receipt/receipt-committed state machine whose ambiguous crash state is
  quarantined and never retried or reported successful. Its schema, fixture,
  focused/integration test, R5 adapter, and Nix inventory is explicit.

## Retained gates

C6 still needs a separately reviewed C2 scheduler-context issuer/transport and
the exact owner public-key/service-hardening source. C4 still needs the accepted
runner live-cell exercise, an active C6 intervention lever, and then-current
gateway/health ownership hash preflight. C3a-2 still needs accepted runner/C4/C6,
R5 attach, and a real hash-pinned signing-capable remote principal. These are
prerequisites, not design defects, and must not be inferred or bypassed.

`VERDICT: PASS_DESIGN — runner freeze candidate may seek exact owner activation; C6, C4, and C3a-2 remain non-freeze-eligible until named prerequisites exist.`
