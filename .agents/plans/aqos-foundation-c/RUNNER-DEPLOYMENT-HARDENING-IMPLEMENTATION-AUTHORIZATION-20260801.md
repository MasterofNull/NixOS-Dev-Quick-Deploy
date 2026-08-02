# Runner Deployment-Hardening — Prepared Implementation Authorization

Status: `PREPARED_ONLY — NOT ACTIVATED`  
Authorization ID: `auth-foundation-c-runner-hardening-20260801`  
Idempotency key: `foundation-c:runner-hardening:17f899bf:20260801`  
Base HEAD: `17f899bf838973c755ab7a3e6095ec04a2e74220`

## Exact reviewed chain

- Design: `48cae30d1c93ff9e76fdff0e3866f885b54e544de95c978c8286a1c8065f0c63`
- Freeze candidate: `430093d2c4af905793c9cdf4539b9b5a50c93b16976ede2d08795f34921a25df`
- Revision-3 binding review: `FOUNDATION-C-REV3-CODEX-ACCEPTANCE-20260801.md`, SHA-256 `c802f5f50c140129925ae5067b444d2fb5a6b1db24b8373e3832dab5226b89ca`

After a fresh independent exact review and explicit owner activation naming this
authorization SHA, implementer, and bounded UTC window, one implementer may edit
only:

1. `ai-stack/switchboard/execution_cell_runner.py`
2. `scripts/testing/test-execution-cell-runner.py`
3. `nix/modules/services/execution-cell-runner.nix`
4. `config/env-contract.yaml`

All predecessor and no-edit hashes, socket/client-identity semantics, negative
tests, default-OFF boundary, validation commands, and later live-exercise gates
are incorporated from the exact freeze. `nix/modules/services/switchboard.nix`
is a no-edit anchor. No fifth path, new file, substitution, mode change, staging,
commit, deployment, restart, provider/network action, or live traffic exists.

Proposed implementer: `codex-subagent-runner-hardening-implementer`. Candidate
acceptance requires a distinct flagship reviewer. This grant is single-use if
activated and is consumed on the first successful ceiling write or completed
exact candidate report. Any drift, overlap, test failure, runtime need, or
REQUEST_REVISION requires a newly numbered authorization.

`RECORD: PREPARED_ONLY runner-hardening implementation grant; exact review and owner activation required.`
