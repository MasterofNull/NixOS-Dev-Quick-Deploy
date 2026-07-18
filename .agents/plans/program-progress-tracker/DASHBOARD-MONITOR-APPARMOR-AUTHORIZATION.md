# Authorization — Dashboard Monitor Shared-Lock AppArmor Repair

Authorization ID: `auth-dashboard-monitor-apparmor-r0-20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**

## Evidence and root cause

Staged Tier0 failed QA `0.12.8` because the live dashboard route returned
`available:false`, `status:blocked`, and `reason:[Errno 13] Permission denied`. Kernel audit records
repeatedly bind the denial to:

- profile `command-center-dashboard-api`;
- operation `file_lock`;
- path `.agents/delegation/registry.jsonl`;
- requested/denied mask `k`; and
- live dashboard PID/user.

The service runs as repository owner `hyperd`. POSIX path permissions allow read. The AppArmor profile
grants repository `r`, while `TaskRegistry._read_registry()` uses a correct shared `LOCK_SH`. The same
current route returns counts outside the profile. AppArmor `k` is therefore the missing capability.

## Exact one-file lease

The only editable file is `nix/modules/services/mcp-servers.nix`, predecessor SHA-256
`ba6a70c9063f81eca561da2139b39372f4ea9698a96059cd198ee860f3d5c303`.

One monitored implementer may add one exact read+lock (`rk`) rule for
`${mcp.repoPath}/.agents/delegation/registry.jsonl` inside only the
`command-center-dashboard-api` profile, with a comment binding the shared read-lock requirement.

No directory-wide `k`, write/append/create/link permission, process/proc expansion, profile-mode
change, service/user/group change, route/TaskRegistry/QA change, second file, staging, commit,
deployment, subdelegation, or self-review is authorized.

## Acceptance and activation

Candidate acceptance requires Nix syntax/evaluation, an exact one-file diff, proof the generated
profile contains the exact `rk` rule and no write grant, and independent review.

After integration, the owner has preauthorized the normal non-destructive NixOS deployment path.
Runtime acceptance then requires:

- profile loaded in enforce mode;
- dashboard service active under its declared user/profile;
- live `/api/aistack/local-agent/monitor` returns `available:true` and a counts object;
- a fresh kernel-audit window contains no registry `file_lock` denial;
- QA `0.12.8` passes; and
- Tier0 returns 23/23.

Before deployment, the orchestrator must capture the exact pre-deploy generation number and
`/run/current-system` store target in the acceptance record. Any deployment or runtime failure stops
activation and requires a separately explicit owner approval before rolling back to that captured
generation. This authorization does not itself authorize rollback, an arbitrary generation target,
or broader access; without rollback approval, retain the failed evidence and prepare a new bounded
repair authorization.

`RECORD: prepared exact shared-lock AppArmor repair; inactive pending independent review.`
