# Implementation Authorization Amendment 1 — C0.5A

**Authorization ID:** `auth-agent-connection-reliability-c0.5a-am1-20260716`
**Status:** `ACTIVE — AUTO-ACTIVATED UNDER OWNER PREAUTHORIZATION`
**Base authorization:** `auth-agent-connection-reliability-c0.5a-20260716`
**Idempotency key:** `acr-c05a-review-feedback-contract-am1-20260716-single-use`

## Reason

The preferred balanced Claude task `claude-20260716-142715-p4h6un` remained alive for more than the
bounded no-progress window while producing zero log bytes and zero candidate files. Codex interrupted
the call and registry reconciliation marked the task `stale`. No authorized file was created or
modified, so there is no overlapping writer or partial candidate to preserve.

## Amended implementer

Assign one Codex sub-agent as the sole bounded implementer. The sub-agent receives the same exact
seven-file creation scope and all constraints from the base authorization. It may not review or accept
its own work. Fable and Antigravity remain the required independent flagship acceptance lanes.

## Scope and stop conditions

The exact thirteen-file candidate and the six frozen input hashes remain unchanged. The implementer
may create only files 7–13 listed in the base authorization. Any existing target file at assignment,
any edit to files 1–6, any fourteenth implementation file, live authority, route/store mutation,
delegation, staging, commit, deployment, or destructive action is a hard stop.

`RECORD: ACTIVE. One Codex sub-agent implementation attempt is authorized under these bounds.`
