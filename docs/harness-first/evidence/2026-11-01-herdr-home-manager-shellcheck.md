# aq-herdr Home Manager build regression

The Home Manager activation package could not build because writeShellApplication runs ShellCheck and the optional, repository-local usage hook was unresolved (SC1091). The hook intentionally tolerates an absent shim in installed packages.

The fix annotates only this optional source with `source=/dev/null`. ShellCheck remains enabled for the application. No Herdr daemon or mutation authority is enabled.

Scope: restore the existing H1 facade build. H2 project subcommands remain outside this slice and do not establish H2 readiness.

Validation: `nix build .#homeConfigurations.hyperd.activationPackage --no-link --print-out-paths` passed using the owner's current, uncommitted flake.lock. Output: `/nix/store/25bwgsy3b0pj081jbbyxlqlh0sq5mza3-home-manager-generation`. The lock is excluded from the fix. `home-manager switch --flake /tmp/nqd-fix-herdr-shellcheck#hyperd` completed with exit 0. Bash syntax, ShellCheck, H1 contract, and usage logging tests also passed. H1 runtime remains disabled by design.
