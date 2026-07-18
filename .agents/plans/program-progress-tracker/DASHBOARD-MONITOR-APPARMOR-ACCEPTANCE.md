# Independent Candidate Acceptance — Dashboard Monitor Shared-Lock AppArmor Repair

Authorization: `auth-dashboard-monitor-apparmor-r0-20260718`  
Authorization SHA-256: `77ec291726307d86350eb48edb9cdabc403b195f7b2ad793739aadb53047eefa`  
Authorization review SHA-256: `623d91bd2d0ed0dcbd551a02fd491350d3efe7b4d597fbc1534aa6100ebb9a1d`  
Candidate file: `nix/modules/services/mcp-servers.nix`  
Candidate SHA-256: `473e4613159786d5ee485a87d14e26b7be11947063c2e4fee2941f91db8e7b50`  
Reviewed predecessor SHA-256: `ba6a70c9063f81eca561da2139b39372f4ea9698a96059cd198ee860f3d5c303`  
Reviewer role: independent security / NixOS / AppArmor acceptance gate  
Review date: 2026-07-18

## Exact-scope verification

- `git show HEAD:nix/modules/services/mcp-servers.nix` matches the authorized predecessor hash.
- The candidate matches the assigned candidate hash.
- The diff changes exactly one authorized file with two insertions and zero removals.
- The first insertion is a shared-reader rationale comment.
- The second insertion is exactly
  `${mcp.repoPath}/.agents/delegation/registry.jsonl rk,` inside only the
  `command-center-dashboard-api` profile.
- The additions contain no `w`, `a`, create, link, execute, wildcard-directory, or broad lock grant.
- No service identity, profile state, route, TaskRegistry, QA, or other Nix declaration changed.

## Nix and generated-profile verification

- `nix-instantiate --parse nix/modules/services/mcp-servers.nix` passed.
- `nix eval --raw path:.#nixosConfigurations.hyperd-ai-dev.config.security.apparmor.policies.command-center-dashboard-api.state`
  returned `enforce`.
- Evaluation of the generated profile succeeded and contained the resolved exact rule
  `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/registry.jsonl rk,` exactly once.
- The generated profile contained no `delegation/**` lock grant.
- `git diff --check -- nix/modules/services/mcp-servers.nix` passed.

This is candidate acceptance only. Commit, deployment, runtime verification, and any rollback remain
outside this review. Runtime completion still requires the authorization's captured pre-deploy
generation/store target and post-deploy enforce-mode, route, fresh-audit, QA `0.12.8`, and Tier0
evidence.

VERDICT: PASS — candidate exactly implements the authorized one-file read-and-shared-lock AppArmor repair with no broader permission
