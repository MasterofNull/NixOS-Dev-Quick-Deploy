#!/usr/bin/env bash
# Upstream Contribution Management
#
# Unified interface for managing upstream contributions to:
# - NixOS/nixpkgs
# - System76 COSMIC desktop
# - Linux kernel
#
# Workflow:
#   deploy upstream setup nixpkgs      # Fork and clone
#   deploy upstream branch nixpkgs fix # Create feature branch
#   [make changes locally]
#   deploy upstream test nixpkgs       # Build with overlay
#   deploy upstream validate           # Full system validation
#   deploy upstream submit nixpkgs     # Create upstream PR
#   deploy upstream status             # Show all contributions

UPSTREAM_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../scripts/upstream" && pwd)"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
FORKS_DIR="${REPO_ROOT}/.forks"

# ============================================================================
# Help
# ============================================================================

help_upstream() {
  cat <<'EOF'
UPSTREAM CONTRIBUTION MANAGEMENT

Manages the complete upstream contribution lifecycle:
  1. Fork and setup upstream repositories
  2. Create feature branches for changes
  3. Test changes with local system build
  4. Validate with full nixos-rebuild
  5. Submit PRs to upstream projects
  6. Track PR status and respond to reviews

SUBCOMMANDS:

  setup <repo>              Fork and clone upstream repository
                            Repos: nixpkgs, cosmic-comp, cosmic-applets, etc.

  branch <repo> <name>      Create feature branch from upstream/master
                            Example: deploy upstream branch nixpkgs cve-fix

  test <repo>               Build system with forked repo overlay
                            Verifies changes compile correctly

  validate                  Full system validation with all changes
                            Runs: nixos-rebuild build --flake .#<current>

  diff <repo>               Show changes vs upstream
                            Lists modified files and commit diff

  submit <repo>             Create PR to upstream repository
                            Pushes branch and opens PR via gh CLI

  sync <repo>               Sync fork with upstream/master
                            Fetches and rebases on latest upstream

  status                    Show status of all forks and PRs
                            Lists open PRs, pending changes

  track <subcommand>        Contribution discovery and tracking
                            Subcommands: search, propose, issues

EXAMPLES:

  # Complete nixpkgs contribution workflow
  deploy upstream setup nixpkgs
  deploy upstream branch nixpkgs add-lore-sync
  # [edit .forks/nixpkgs/...]
  deploy upstream test nixpkgs
  deploy upstream validate
  deploy upstream submit nixpkgs

  # Check status of all contributions
  deploy upstream status

  # Search for contribution opportunities
  deploy upstream track nixpkgs search "cosmic"

  # Sync fork with latest upstream
  deploy upstream sync nixpkgs

PROPER WORKFLOW:

  Before submitting upstream:
  1. Make changes locally in your system config
  2. Run 'deploy system' to activate and test
  3. Verify changes work on your running system
  4. Extract/adapt changes for upstream submission
  5. Test upstream version with 'deploy upstream test'
  6. Submit with 'deploy upstream submit'

  This ensures changes are validated BEFORE upstream submission.

EOF
}

# ============================================================================
# Subcommand Handlers
# ============================================================================

cmd_upstream_setup() {
  local repo="${1:-}"
  [[ -z "$repo" ]] && { echo "Usage: deploy upstream setup <repo>"; return 1; }
  "${UPSTREAM_SCRIPT_DIR}/dev" setup "$repo"
}

cmd_upstream_branch() {
  local repo="${1:-}"
  local name="${2:-}"
  [[ -z "$repo" || -z "$name" ]] && { echo "Usage: deploy upstream branch <repo> <name>"; return 1; }
  "${UPSTREAM_SCRIPT_DIR}/dev" branch "$repo" "$name"
}

cmd_upstream_test() {
  local repo="${1:-}"
  [[ -z "$repo" ]] && { echo "Usage: deploy upstream test <repo>"; return 1; }
  "${UPSTREAM_SCRIPT_DIR}/dev" test "$repo"
}

cmd_upstream_validate() {
  echo "Running full system validation..."

  # Determine current configuration
  local hostname profile config_name
  hostname="$(hostname -s 2>/dev/null || hostname)"
  profile="${PROFILE_OVERRIDE:-ai-dev}"
  config_name="${hostname}-${profile}"

  echo "Building: .#${config_name}"
  nix build --no-link ".#nixosConfigurations.${config_name}.config.system.build.toplevel"

  echo ""
  echo "Validation complete. To activate:"
  echo "  sudo nixos-rebuild switch --flake .#${config_name}"
}

cmd_upstream_diff() {
  local repo="${1:-}"
  [[ -z "$repo" ]] && { echo "Usage: deploy upstream diff <repo>"; return 1; }
  "${UPSTREAM_SCRIPT_DIR}/dev" diff "$repo"
}

cmd_upstream_submit() {
  local repo="${1:-}"
  [[ -z "$repo" ]] && { echo "Usage: deploy upstream submit <repo>"; return 1; }
  "${UPSTREAM_SCRIPT_DIR}/dev" submit "$repo"
}

cmd_upstream_sync() {
  local repo="${1:-}"
  [[ -z "$repo" ]] && { echo "Usage: deploy upstream sync <repo>"; return 1; }
  "${UPSTREAM_SCRIPT_DIR}/dev" sync "$repo"
}

cmd_upstream_status() {
  "${UPSTREAM_SCRIPT_DIR}/dev" status
  echo ""
  "${UPSTREAM_SCRIPT_DIR}/track" status 2>/dev/null || true
}

cmd_upstream_track() {
  "${UPSTREAM_SCRIPT_DIR}/track" "$@"
}

# ============================================================================
# Main Entry Point
# ============================================================================

cmd_upstream() {
  local subcmd="${1:-}"

  case "$subcmd" in
    -h|--help|help)
      help_upstream
      ;;
    setup)
      shift; cmd_upstream_setup "$@"
      ;;
    branch)
      shift; cmd_upstream_branch "$@"
      ;;
    test)
      shift; cmd_upstream_test "$@"
      ;;
    validate)
      shift; cmd_upstream_validate "$@"
      ;;
    diff)
      shift; cmd_upstream_diff "$@"
      ;;
    submit)
      shift; cmd_upstream_submit "$@"
      ;;
    sync)
      shift; cmd_upstream_sync "$@"
      ;;
    status)
      shift; cmd_upstream_status "$@"
      ;;
    track)
      shift; cmd_upstream_track "$@"
      ;;
    "")
      echo "Usage: deploy upstream <subcommand> [args...]"
      echo ""
      echo "Subcommands: setup, branch, test, validate, diff, submit, sync, status, track"
      echo ""
      echo "Run 'deploy upstream --help' for detailed usage."
      ;;
    *)
      echo "Unknown subcommand: $subcmd"
      echo "Run 'deploy upstream --help' for usage."
      return 1
      ;;
  esac
}
