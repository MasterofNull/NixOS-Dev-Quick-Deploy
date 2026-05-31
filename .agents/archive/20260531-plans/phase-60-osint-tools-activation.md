# Phase 60 OSINT Tools Activation

Status: implementation validation in progress

## Scope

- Register the repo-local `osint-tools` MCP server in the user MCP client configuration.
- Add buildable OSINT command-line backends to the AI stack profile and OSINT dev shell.
- Keep Maigret and MOSAIC out of active profiles until their derivations avoid insecure PyPDF2.
- Add a focused MCP contract check so future activation changes cannot silently reintroduce the insecure package path.

## Architecture Decision

`ai-stack/mcp-servers/osint-tools/server.py` is a stdio MCP server. It should be spawned by MCP clients rather than managed as a persistent systemd daemon. The NixOS profile installs the tool backends (`sherlock`, `holehe`, and the BBOT placeholder), while `nix/home/base.nix` registers the MCP server command for clients that speak stdio.

## Validation

- `python3 scripts/testing/test-osint-tools-mcp-contract.py`
- `python3 -m py_compile ai-stack/mcp-servers/osint-tools/server.py scripts/testing/test-osint-tools-mcp-contract.py`
- `nix eval .#devShells.x86_64-linux.osint.drvPath --accept-flake-config`
- `nix build .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel --dry-run --accept-flake-config`
- `scripts/governance/run-focused-ci-checks.sh`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`

## Follow-Up

- Replace `bbot-placeholder` with a real BBOT derivation after packaging is complete.
- Package Maigret/MOSAIC only after the PyPDF2 security exception is removed or an audited replacement is available.
