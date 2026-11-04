# Enable Herdr H1 package for hyperd

## Objective

Turn on `programs.aqHerdr.enable` for the hyperd Home Manager configuration so that `aq-herdr status` reports enabled after the next home-manager switch. `programs.aqHerdr.runtimeEnable` stays `false` (asserted in `nix/home/herdr.nix`).

## Workflow/Session IDs

- Worktree: `.agents/delegation/worktrees/herdr-enable`
- Branch: `feat/enable-herdr-package`
- Workflow/session ID: none assigned for this slice.

## Delegation Decision

Bounded single-file, mechanical edit with a checkable result (a one-line option set plus eval verification). Executed directly by the delegated worker in its worktree. No further sub-agent dispatch.

## Commands Executed

- `rg -n "aqHerdr|herdr" nix flake.nix`
- `sed -n` reads of `nix/home/herdr.nix`, `flake.nix` (home section), `nix/hosts/hyperd/home.nix`, `nix/hosts/hyperd/home-deploy-options.nix`
- `fd` / `rg` to locate host home files
- `git -C <worktree> status --short` and `git -C <worktree> branch --show-current` (read-only)
- Edit: added `programs.aqHerdr.enable = true;` to `nix/hosts/hyperd/home.nix`
- `nix-instantiate --parse nix/hosts/hyperd/home.nix`
- `nix eval .#homeConfigurations.hyperd-hyperd.config.programs.aqHerdr.enable`
- `nix eval .#homeConfigurations.hyperd-hyperd.config.programs.aqHerdr.runtimeEnable`

## Validation Evidence

- Change location: `nix/hosts/hyperd/home.nix` (host-specific Home Manager file, imported by `mkHostHomeConfig` in `flake.nix`). `nix/home/herdr.nix` is already imported for every host, so only the option set is needed.
- `nix-instantiate --parse nix/hosts/hyperd/home.nix` succeeded.
- `nix eval .#homeConfigurations.hyperd-hyperd.config.programs.aqHerdr.enable` returned `true`.
- `nix eval .#homeConfigurations.hyperd-hyperd.config.programs.aqHerdr.runtimeEnable` returned `false`.
- `git diff --stat`: `nix/hosts/hyperd/home.nix | 3 +++`.
- Eval emitted a "Git tree is dirty" warning because the change is uncommitted. This is expected in the worktree.
- Not performed: home-manager switch, `aq-herdr status` on the live system (owner act; see below). No commit made.

## Rollback Plan

Revert the three added lines in `nix/hosts/hyperd/home.nix` (the comment line, `programs.aqHerdr.enable = true;`, and the blank line), then run the owner home-manager switch. The option defaults to `false`, so removing the line restores the prior state.

## Residual Risk

- The live effect (`aq-herdr status` reporting enabled) is unverified until the owner runs the home-manager switch.
- The facade and config file (`xdg.configFile."herdr/config.toml"`) and private directories will be created on switch. The raw Herdr binary is intentionally not added to the user PATH.
- Eval confirms the option value only; the built closure was not realized.

## Owner Activation

After committing and merging through the normal PR flow, run the owner's home-manager switch (for example `aq-deploy-current` or the home-manager switch command used on this host), then:

```
aq-herdr status
```

Expected: reports enabled.

## Hint Feedback

No `aq-hints` or hints tool was queried during this slice. No hint feedback to record.
