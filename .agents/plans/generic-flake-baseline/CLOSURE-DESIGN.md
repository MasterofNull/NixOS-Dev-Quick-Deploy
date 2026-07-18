# Generic Flake Baseline Closure Design

Status: design-ready; implementation not authorized by this packet  
Scope: minimum three-file closure slice  
Implementation files: `flake.nix`, `.github/workflows/test.yml`, `.agent/memory/issues-backlog.md`

## Outcome

Make the standard Git-backed command `nix flake check --offline --no-build` evaluate only source-visible, deployable hosts while retaining strict hardware and security assertions. The closure must stop incomplete local/generated host scaffolds from being auto-promoted into `nixosConfigurations`, keep all three concrete `hyperd-*` profiles under CI, and record that the original finding also affects the untracked `sbc-minimal` reference facts.

This slice is independent of Foundation A/R0.1. It changes flake host classification and CI evidence only; it does not adjudicate, move, or add writers for any state-authority row.

## Evidence and root cause

The current flake discovers a host whenever `nix/hosts/<name>/default.nix` exists. It does not require `facts.nix` to be present in the flake source. At the same time, `.gitignore` excludes `nix/hosts/*/facts.nix`. Consequently:

- `hyperd/facts.nix` remains visible because it was already force-tracked, and `hyperd-ai-dev`, `hyperd-gaming`, and `hyperd-minimal` evaluate successfully.
- `nixos/facts.nix` exists only as generated local state and is absent from a standard Git-backed flake source.
- `sbc-minimal/facts.nix` also exists locally but is ignored/untracked, so all three `sbc-minimal-*` outputs fail under the standard Git-backed source.
- The missing facts cause defaults to resolve to 8 GiB RAM, unknown firmware, and secrets disabled. The `ai-dev` profile correctly enables the AI role, MCP servers, and Secure Boot defaults, causing four fail-closed assertions: missing facts, MCP without secrets, RAM below 12 GiB, and Secure Boot on non-EFI/unknown firmware.

The assertions are functioning correctly. Host classification is the defect.

## Required implementation

### 1. `flake.nix`: source-visible host classification

Change the dynamically discovered `hostDirs` contract so a directory is exported through `nixosConfigurations` and `homeConfigurations` only when both are visible in the evaluated flake source:

1. `nix/hosts/<name>/default.nix`
2. `nix/hosts/<name>/facts.nix`

The classification must be derived with pure `builtins.pathExists` checks against the active flake source. Do not consult the ambient filesystem, environment variables, Git commands, or impure evaluation.

Required semantics:

- Standard Git-backed `.#...` evaluation exports only source-complete hosts.
- `path:<repo-root>` deployment continues to see generated local facts and may export the corresponding local host. This preserves the current `nixos-quick-deploy.sh` workflow, whose default flake reference is `path:${REPO_ROOT}`.
- `mkHost` retains its existing `hasHostFacts` assertion. Filtering is not permission to weaken the fail-closed assertion for any host that reaches `mkHost` through another path or later refactor.
- The existing hardware-configuration assertion remains unchanged.
- No aliases are introduced from `nixos-ai-dev` or `sbc-minimal-ai-dev` to `hyperd-ai-dev`.
- No incomplete host is silently assigned generic hardware, RAM, firmware, disk, user, secret, or Secure Boot values.

### 2. `.github/workflows/test.yml`: enumerate flake outputs, not directories

Replace filesystem-directory enumeration in the profile evaluation smoke test with enumeration of the actual `nixosConfigurations` attributes exported by the standard Git-backed flake.

CI requirements:

- Run `nix flake show --no-write-lock-file .` and `nix flake check --offline --no-build .` against the standard Git-backed source. Do not use `path:.` for the baseline closure gate because that changes source-visibility semantics.
- Obtain configuration names from `.#nixosConfigurations` and validate the declared `config.mySystem.profile` for each exported `*-ai-dev`, `*-gaming`, and `*-minimal` output.
- Explicitly require these concrete outputs to exist and evaluate:
  - `hyperd-ai-dev`
  - `hyperd-gaming`
  - `hyperd-minimal`
- Explicitly assert that a clean checkout does not export `nixos-ai-dev` or any `sbc-minimal-*` configuration until source-visible facts are intentionally supplied under a separately reviewed design.
- Fail on an empty configuration set. Dynamic enumeration must never turn zero coverage into a pass.

### 3. `.agent/memory/issues-backlog.md`: merge-safe issue closure

Update only the existing `generic-nixos-ai-dev-flake-check-baseline` entry after validation passes:

- Record that the same source-visibility defect affected the `sbc-minimal` reference outputs.
- Record the adopted source-visible host classification and CI enumeration contract.
- Record exact validation commands and results.
- Mark the entry done only if the standard Git-backed flake check and all required positive and negative tests pass.
- Keep the CrowdSec missing-acquisition warning as a separate operational prerequisite; do not represent it as fixed.

`issues-backlog.md` currently has concurrent uncommitted edits. Implementation must re-read the current file immediately before editing and apply a narrowly anchored patch to this one issue entry. It must preserve every unrelated concurrent change byte-for-byte and must not replace the file wholesale.

## Assertion preservation and negative tests

The implementation must not edit `nix/modules/roles/ai-stack.nix`, `nix/modules/services/mcp-servers.nix`, `nix/modules/core/base.nix`, or their option defaults. CI must demonstrate that the existing guards still fail closed by extending a valid concrete evaluation with test-only overrides and forcing `config.system.build.toplevel.drvPath`.

Each negative test must require a non-zero evaluation result and match the corresponding stable message fragment:

1. Force `mySystem.secrets.enable = false` on `hyperd-ai-dev` and require `requires mySystem.secrets.enable=true`.
2. Force `mySystem.hardware.systemRamGb = 8` on `hyperd-ai-dev` and require `minimum 12 GB RAM required`.
3. Force `mySystem.secureboot.enable = true` and `mySystem.hardware.firmwareType = "unknown"` on `hyperd-ai-dev` and require `requires hardware.firmwareType = "efi"`.

Use `extendModules` or an equivalent evaluation-only module override. A negative test passes only when evaluation fails for the expected assertion; command failure alone is insufficient. Store stderr in a temporary file, inspect it, and remove the temporary file through a shell trap.

Also retain a structural negative test that confirms a directory with `default.nix` but no source-visible `facts.nix` is absent from exported configuration names. This tests classification without weakening the missing-facts assertion.

## Positive validation

The implementation evidence must include:

```bash
nix flake show --no-write-lock-file .
nix flake check --offline --no-build .
nix eval --offline --raw .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel.drvPath
nix eval --offline --raw .#nixosConfigurations.hyperd-gaming.config.system.build.toplevel.drvPath
nix eval --offline --raw .#nixosConfigurations.hyperd-minimal.config.system.build.toplevel.drvPath
nix eval --offline --json .#nixosConfigurations --apply 'x: builtins.attrNames x'
```

Acceptance requires:

- all commands exit zero;
- all three `hyperd-*` derivation paths are produced;
- exported configuration names are non-empty and contain all three required concrete profiles;
- standard Git-backed output names exclude incomplete `nixos-*` and `sbc-minimal-*` scaffolds;
- all three assertion-negative tests fail for the expected reason;
- the unrelated CrowdSec acquisition warning may remain visible but no new warning is introduced by host classification.

No build, switch, deployment, service restart, or runtime activation is required for this configuration/CI-only closure.

## Monitoring and evidence

This slice introduces no service, endpoint, background process, or runtime metric, so the service coverage contract and dashboard-panel gate are not applicable. Its operational evidence is:

- standard Git-backed flake check status in GitHub Actions;
- the non-empty enumerated configuration list in CI logs;
- explicit per-profile `hyperd-*` evaluation results;
- expected-message evidence from the three negative assertion tests;
- the updated issue entry containing the exact commands and results.

Treat disappearance of any required `hyperd-*` output, an empty exported set, or a negative assertion unexpectedly evaluating successfully as a blocking regression.

## Explicit exclusions

This closure must not:

- track, force-add, copy, or synthesize `nix/hosts/nixos/facts.nix`;
- track or force-add the currently ignored `nix/hosts/sbc-minimal/facts.nix`;
- change `.gitignore` facts handling;
- create fallback hardware facts or generic machine defaults;
- create a synthetic `nixosConfigurations` host that can be built or switched;
- enable secrets with placeholder or nonexistent secret material merely to satisfy evaluation;
- disable the AI role, MCP servers, or Secure Boot assertions to make the check green;
- remove or relax the missing-facts or hardware-configuration assertions;
- alter deploy behavior, deployment scripts, host modules, security modules, or Nix option defaults;
- address the CrowdSec acquisition warning in this slice;
- touch Foundation A/R0.1 authority artifacts.

If an evaluable generic fixture is later required, it must be a separately reviewed, checks-only fixture under `checks.<system>`, with an explicit guarantee that it is not exported through `nixosConfigurations` and cannot be selected by `nixos-rebuild switch`.

## Rollback

Rollback is an ordinary revert of the atomic three-file implementation commit. Do not use destructive reset or checkout operations.

Before accepting rollback, rerun the pre-change evidence and document that the standard Git-backed flake check will again fail on incomplete host scaffolds. Local `path:${REPO_ROOT}` deployment semantics are expected to be unchanged both before and after the slice. If rollback is required because a valid source-complete host disappeared, restore the classification logic through a corrective commit while retaining non-empty CI enumeration and all assertion-negative tests.

## Review gate

Independent review must verify the exact implementation commit and return `PASS` only if:

- the diff is limited to the three declared implementation files;
- concurrent issue-backlog edits were preserved;
- concrete-host assertions and module defaults are unchanged;
- generated facts and synthetic switchable hosts were not added;
- standard Git-backed flake validation and positive/negative CI evidence satisfy this packet.
