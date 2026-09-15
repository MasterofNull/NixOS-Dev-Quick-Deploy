# Read-only FT-2/3/4 integration inventory

Explorer `ft_integration_inventory`; no code or index changes.

- Central entrypoints: `scripts/ai/aqd` project-init (~732), retrofit (~800),
  brownfield (~939), bootstrap (~1074).
- Greenfield: after git init (~785), install the bundle and test it. Replace
  legacy `install_git_secret_hooks` (~636), which overwrites .git/hooks, rather
  than blindly combining it with core.hooksPath=.githooks.
- Brownfield: preview and confirm the retrofit BEFORE calling bootstrap,
  `write_agent_command_specs` (~201), or legacy hook writers: those can clobber
  existing files. Installer must detect existing hooksPath and merge/archive
  safely, not silently redirect it or overwrite project CI/config.
- MCP bridge `mcp-bridge-hybrid.py`: project_init_workflow (~1171) and
  retrofit_workflow (~1219) resolve target/cwd; bootstrap_agent_project (~1150)
  calls workflows bootstrap and has weaker target handling. Reuse one installer
  seam rather than independently duplicating behavior in the bridge.
- No real target stack detector/command resolver currently exists in those
  workflows; --stack is a pass-through string. Internal capability marker maps
  are context hints, not an authoritative execution-command resolver.
- FT-2 detector must inspect bounded metadata only, cover Python/Node/Rust/Go/
  Nix/generic and polyglot fixtures, and return explicit unavailable/unsupported
  configuration. Detection never executes repository scripts or installs deps.

Inventory is a starting point, not authorization to overwrite any of these
surfaces. Read their current bytes before the FT-3/4 implementation slice.
