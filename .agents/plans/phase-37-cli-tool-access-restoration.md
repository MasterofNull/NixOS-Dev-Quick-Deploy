# phase-37-cli-tool-access-restoration.md

## Objective
Update agent instruction sets and VSCodium configuration to enable full access to CLI tools (`aq-prime`, `agrep`, `als`, etc.).

## Scope Lock
- **In Scope**: `AGENTS.md`, `.agent/GEMINI.md`, `.agent/WORKFLOW-CANON.md`, `nix/home/base.nix`.
- **Out of Scope**: Modifying the actual CLI tools themselves, changing MCP server logic.

## Workstreams
1. **Instruction Update**: Refactor Markdown files to remove "human-only" restrictions.
2. **Nix Config Update**: Patch `nix/home/base.nix` to update injected agent rules.
3. **Validation**: Verify that the new instructions are consistent and that `home-manager` (if possible) would accept the Nix changes.

## Step Plan
1. **[ ] Update `AGENTS.md`**:
   - Replace `## Operator Terminal CLIs (human-run, not AI tool calls)` with `## Harness Entrypoints & Diagnostic CLIs`.
   - Remove any text explicitly forbidding AI tool calls for these commands.
2. **[ ] Update `.agent/GEMINI.md`**:
   - Add a note that CLI tools are available via `run_shell_command`.
3. **[ ] Update `.agent/WORKFLOW-CANON.md`**:
   - Ensure the `ORIENT` section doesn't imply `aq-prime` is human-only.
4. **[ ] Update `nix/home/base.nix`**:
   - Search and replace "NEVER call aq-prime" with "You may call aq-prime for orientation".
   - Update `geminicodeassist.rules` string.
   - Update the `rules` list in the `CONTINUE_EOF` section.

## Validation
- Manual review of all updated files.
- Run `aq-qa 0` to ensure no regression in harness health.
- (Optional) Run `nix-instantiate` or similar on `flake.nix` if possible to check for syntax errors in Nix files.

## Rollback
- Revert changed files using `git checkout`.
