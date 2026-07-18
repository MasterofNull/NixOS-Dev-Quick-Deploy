# Independent Review — Dashboard Monitor Shared-Lock AppArmor Authorization

Reviewed subject: `.agents/plans/program-progress-tracker/DASHBOARD-MONITOR-APPARMOR-AUTHORIZATION.md`  
Reviewed SHA-256: `77ec291726307d86350eb48edb9cdabc403b195f7b2ad793739aadb53047eefa`  
Reviewer role: independent security / NixOS / AppArmor acceptance gate  
Review date: 2026-07-18

## Evidence checked

- The reviewed file matches the assigned SHA-256 exactly.
- The live kernel audit log repeatedly records `operation="file_lock"`, profile
  `command-center-dashboard-api`, the exact live-repository path
  `.agents/delegation/registry.jsonl`, and `requested_mask="k" denied_mask="k"` for dashboard PID
  2184.
- `TaskRegistry._read_registry()` opens the registry without a write mode and acquires
  `fcntl.LOCK_SH`; the requested `k` capability is therefore necessary for a non-mutating read.
- The current profile grants `${repoSource}/** r` but has no lock grant for the mutable live-repo
  registry. The proposed exact `${mcp.repoPath}/.agents/delegation/registry.jsonl rk,` rule targets
  the denied path and does not add `w`, `a`, `l`, directory-wide `k`, or execution permission.
- The live systemd unit is active as `User=hyperd`, `Group=users`, with
  `AppArmorProfile=command-center-dashboard-api`; the registry is mode `0600`, owned by
  `hyperd:users`. DAC read access is present, so the observed failure is correctly isolated to the
  AppArmor lock capability.
- The authorization binds the only editable runtime file to the current predecessor SHA-256
  `ba6a70c9063f81eca561da2139b39372f4ea9698a96059cd198ee860f3d5c303`, confines the edit to one
  profile and one exact file rule, and excludes route, registry, service identity, profile mode,
  deployment, staging, commit, and broader permission changes from the implementation lease.
- The declared candidate and runtime checks cover Nix parsing/evaluation, exact diff scope,
  generated-profile inspection, enforce-mode attachment, live route behavior, a fresh audit
  window, QA `0.12.8`, and Tier0.

## Amendment verification

The amended failure path now requires capturing both the exact pre-deploy generation number and
`/run/current-system` store target in the acceptance record. A deployment or runtime failure stops
activation; rollback requires separate explicit owner approval and is bound to that captured
generation. The authorization explicitly does not grant rollback, an arbitrary generation target,
or broader access. This resolves the prior conflict with
`docs/operations/AUTONOMOUS-OPERATIONS-POLICY.md` and prevents an ambiguous rollback from reverting
unrelated state.

No broader AppArmor permission is justified by the separately observed `/proc/*/mountinfo` denials;
those are outside this exact subject and must remain outside this authorization.

VERDICT: PASS — exact one-file read-and-lock authorization is least-privilege, evidence-bound, independently gated, and rollback-safe
