# Git Hooks for Hyper-NixOS

This directory contains git hooks that help maintain code quality.

## Installation

To install the hooks, run from the repository root:

```bash
# Install pre-commit hook
ln -sf ../../.githooks/pre-commit .git/hooks/pre-commit

# Or use git config to set hooks directory (Git 2.9+)
git config core.hooksPath .githooks
```

## Available Hooks

### pre-commit

Runs fast commit-time governance and safety checks:

- ✅ Secret pattern scan on staged content
- ✅ Bash/Python/Nix syntax checks on staged files
- ✅ Repository structure policy (`--staged`)
- ✅ Shell color-echo lint on staged files
- ✅ Migration governance checks (allowlist/root/artifact hygiene, doc links/metadata/path migration, shim consistency, archive/deprecated guards)

**Skip if needed** (not recommended):
```bash
git commit --no-verify
```

### pre-push

Runs repository quick lint before push:

- ✅ Fetches upstream and blocks push early if your local branch is behind remote
- ✅ Executes `./scripts/governance/quick-deploy-lint.sh --mode fast`
- ✅ Blocks push on governance/runtime lint regressions
- ✅ Prints a short failing-check summary after lint errors for easier IDE push debugging

Emergency bypass (not recommended):
```bash
SKIP_PRE_PUSH_SYNC_CHECK=true git push
SKIP_PRE_PUSH_LINT=true git push
```

Recommended sync workflow when collaborating from multiple sessions/machines:

```bash
git pull --rebase --autostash
```

## Automatic Fixes

If the pre-commit hook finds issues, fix them automatically:

```bash
./scripts/governance/lint-color-echo-usage.sh --staged
```

Then stage the changes and commit again:

```bash
git add -u
git commit
```

## Manual Validation

Check all scripts without committing:

```bash
./scripts/governance/lint-color-echo-usage.sh
./scripts/governance/quick-deploy-lint.sh --mode fast
```

## Why These Checks?

Shell scripts use ANSI escape codes for colors. Without the `-e` flag, `echo` treats escape sequences as literal text:

```bash
# ❌ Wrong - shows: \033[0;32m✓\033[0m Success
echo "  ${GREEN}✓${NC} Success"

# ✓ Correct - shows: ✓ Success (with green color)
echo -e "  ${GREEN}✓${NC} Success"
```

This ensures all colored output renders correctly for users.
