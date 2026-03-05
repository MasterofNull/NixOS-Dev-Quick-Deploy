# Safe Improvements for NixOS-Dev-Quick-Deploy

**Purpose:** Non-breaking improvements that can be safely applied
**Risk Level:** LOW - All changes preserve existing functionality
**Testing:** Changes can be applied incrementally

---

## 1. Documentation Fixes (ZERO RISK)

### Fix A: Correct "AI-Opitmizer" Typo

**Risk:** NONE (documentation only)

**Files to update:**
```bash
# Fix in nixos-quick-deploy.sh
sed -i 's/AI-Opitmizer/NixOS-Dev-Quick-Deploy/g' nixos-quick-deploy.sh

# Verify changes
grep -n "NixOS-Dev-Quick-Deploy" nixos-quick-deploy.sh
```

**Changes:**
- Line 2403: Path in recovery guide
- Line 2406: Path in re-run instructions
- Line 5258-5259: Git clone instructions

---

## 2. Clarify VSCode Version Compatibility (ZERO RISK)

**Risk:** NONE (comment update only)

**File:** `templates/home.nix`

**Current (Line 1357):**
```nix
# NixOS 25.11: Use profiles.default for extensions and settings
```

**Updated:**
```nix
# NixOS 25.11+ REQUIRED: Use profiles.default for extensions and settings
# COMPATIBILITY NOTE: profiles.default has known issues on NixOS 25.05
# If using NixOS 25.05, see: https://github.com/nix-community/home-manager/issues/7880
# For NixOS 25.05, use traditional syntax (extensions/userSettings directly under programs.vscode)
```

**How to Apply:**
```bash
# Update the comment in templates/home.nix
sed -i '1357s|.*|    # NixOS 25.11+ REQUIRED: Use profiles.default for extensions and settings\n    # COMPATIBILITY NOTE: profiles.default has known issues on NixOS 25.05\n    # If using NixOS 25.05, see: https://github.com/nix-community/home-manager/issues/7880\n    # For NixOS 25.05, use traditional syntax (extensions/userSettings directly under programs.vscode)|' templates/home.nix
```

---

## 3. Add AIDB Setup Guide (ZERO RISK)

**Risk:** NONE (new documentation file)

**Purpose:** Help users set up AIDB after running quick-deploy

**Create new file:** `AIDB_SETUP.md`

```bash
cat > AIDB_SETUP.md <<'EOF'
# AIDB Development Setup Guide

After successfully running `nixos-quick-deploy.sh`, follow these steps to set up the AIDB (NixOS-Dev-Quick-Deploy) project.

## Prerequisites Check

Verify the deployment completed successfully:

```bash
# Check that all tools are installed
which podman python3 node git

# Check Claude wrapper works
~/.npm-global/bin/claude-wrapper --version

# Check Flatpak apps
flatpak list --user
```

If any of these fail, re-run the deployment script:
```bash
cd ~/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh
```

## Step 1: Clone AIDB Repository

```bash
# Clone to standard location
git clone <your-aidb-repo-url> ~/NixOS-Dev-Quick-Deploy
cd ~/NixOS-Dev-Quick-Deploy
```

**Note:** Update `<your-aidb-repo-url>` with your actual repository URL.

## Step 2: Enter Development Environment

The quick-deploy script created a flake-based development environment:

```bash
# Enter AIDB development shell
aidb-dev

# Alternative method
aidb-shell
```

This environment includes:
- Python 3.11 with pip
- Podman and podman (legacy)
- SQLite
- All development tools

## Step 3: Verify AIDB Environment

```bash
# Show environment info
aidb-info

# Expected output:
# AIDB Development Environment
#   Flake location: ~/.dotfiles/home-manager/flake.nix
#   Enter dev env:  aidb-dev or aidb-shell
#   Update flake:   aidb-update
```

## Step 4: Initialize AIDB Database

```bash
# (Add specific AIDB initialization commands here)
# Example:
# python setup.py install
# python manage.py init-db
```

## Step 5: Start AIDB Services

```bash
# If AIDB uses Podman containers
cd ~/NixOS-Dev-Quick-Deploy/.aidb/deployment/
./scripts/start.sh

# Or if using podman (legacy)
podman (legacy) up -d
```

## Step 6: Verify AIDB is Running

```bash
# Check AIDB health (adjust URL as needed)
curl http://localhost:8000/health

# Or check Podman containers
podman ps
```

## Useful Commands

### Development Environment
```bash
aidb-dev        # Enter development shell
aidb-info       # Show environment information
aidb-update     # Update flake dependencies
```

### Container Management
```bash
podman ps                    # List running containers
podman pod ps                # List pods
podman logs <container-id>   # View logs
```

### AI Stack
```bash
podman-ai-stack up       # Start Ollama, Open WebUI, etc.
podman-ai-stack status   # Check AI services
podman-ai-stack logs     # View AI stack logs
```

### IDE Integration
```bash
codium                   # Launch VSCodium with Claude Code
code-cursor              # Launch Cursor IDE
```

## Troubleshooting

### Issue: Python packages not found

**Solution:**
```bash
# Ensure you're in the development environment
aidb-dev

# Install Python dependencies
pip install -r requirements.txt
```

### Issue: Podman permission denied

**Solution:**
```bash
# Ensure rootless Podman is configured
podman system migrate
podman info
```

### Issue: Database connection failed

**Solution:**
```bash
# Check if database service is running
systemctl --user status postgresql  # if using systemd user service

# Or check SQLite database file exists
ls -la ~/NixOS-Dev-Quick-Deploy/.aidb/data/
```

## Next Steps

1. Review AIDB documentation
2. Configure AI model endpoints
3. Set up Claude Code API key (if needed)
4. Configure Cursor IDE with your API keys
5. Run AIDB test suite

## Getting Help

- AIDB Issues: https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy/issues
- NixOS Deploy Issues: https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy/issues
- NixOS Wiki: https://nixos.wiki/
- Home Manager Manual: https://nix-community.github.io/home-manager/

---

**Last Updated:** 2025-10-31
EOF
```

---

## 4. Add Health Check Function (LOW RISK)

**Risk:** LOW (new optional function, doesn't change existing behavior)

**Purpose:** Verify system state after installation

**Add to `nixos-quick-deploy.sh`:**

```bash
# Add after the finalize_configuration_activation function

# ============================================================================
# System Health Checks
# ============================================================================

run_health_checks() {
    print_section "System Health Checks"

    local checks_passed=0
    local checks_failed=0
    local checks=()

    # Helper function to run a check
    check() {
        local name="$1"
        local command="$2"

        if eval "$command" >/dev/null 2>&1; then
            print_success "✓ $name"
            ((checks_passed++))
            return 0
        else
            print_error "✗ $name"
            ((checks_failed++))
            return 1
        fi
    }

    echo ""
    print_info "Verifying system components..."
    echo ""

    # Core tools
    check "Node.js installed" "command -v node"
    check "Python installed" "command -v python3"
    check "Podman installed" "command -v podman"
    check "Git installed" "command -v git"

    # Nix tools
    check "Home Manager available" "command -v home-manager"
    check "Nix flakes enabled" "nix flake --help"

    # AI tools
    check "Claude wrapper executable" "[ -x ~/.npm-global/bin/claude-wrapper ]"
    check "Claude wrapper functional" "~/.npm-global/bin/claude-wrapper --version"

    # Editors
    check "VSCodium installed" "command -v codium"
    check "Neovim installed" "command -v nvim"

    # Container tools
    check "Podman (legacy) installed" "command -v podman (legacy)"

    # Check Flatpak apps (if flatpak is available)
    if command -v flatpak >/dev/null 2>&1; then
        local flatpak_count=$(flatpak list --user --columns=application 2>/dev/null | wc -l)
        if [ "$flatpak_count" -gt 0 ]; then
            print_success "✓ Flatpak apps ($flatpak_count installed)"
            ((checks_passed++))
        else
            print_warning "⚠ Flatpak apps (none installed)"
            ((checks_failed++))
        fi
    fi

    echo ""
    print_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [ $checks_failed -eq 0 ]; then
        print_success "All checks passed! ($checks_passed/$((checks_passed + checks_failed)))"
        echo ""
        print_success "System is ready for AIDB development!"
        return 0
    else
        print_warning "Some checks failed: $checks_passed passed, $checks_failed failed"
        echo ""
        print_info "Review the failures above and re-run the script if needed."
        print_info "Most issues can be fixed by running: exec zsh"
        return 1
    fi
}
```

**Add call to health checks in main() function:**

```bash
# In the main() function, add before finalize_configuration_activation:

    # Optional: Run health checks
    if ! run_health_checks; then
        print_warning "Health checks detected issues"
        print_info "System is still functional, but some components may need attention"
        echo ""
    fi

    finalize_configuration_activation
```

**To Apply:**

This is a new function, so add it manually to avoid breaking existing functionality. Test it first by running just the function:

```bash
# Source the function
source <(sed -n '/^run_health_checks()/,/^}/p' SAFE_IMPROVEMENTS.md)

# Run the check
run_health_checks
```

---

## 5. Add Comments for Future AIDB Packages (ZERO RISK)

**Risk:** NONE (comments only)

**File:** `templates/home.nix`

**Add to home.packages section:**

```nix
# In the home.packages section, add a commented section:

          # ========================================================================
          # AIDB-Specific Tools (Uncomment as needed)
          # ========================================================================

          # Database tools for AIDB development
          # postgresql      # Full PostgreSQL database
          # pgcli           # Better PostgreSQL CLI
          # redis           # For caching/queuing
          # dbeaver         # Universal database GUI

          # Performance & profiling
          # hyperfine       # Command-line benchmarking
          # flamegraph      # Performance visualization
          # valgrind        # Memory debugging

          # Data processing
          # csvkit          # CSV manipulation
          # miller          # CSV/JSON processor
          # datasette       # Instant JSON/CSV API

          # Load testing
          # k6              # Modern load testing
          # siege           # HTTP load testing
```

**How to Apply:**

```bash
# Find the right location (after the Development Tools section)
# and add the commented packages manually
```

---

## 6. Add .gitignore for Generated Files (ZERO RISK)

**Risk:** NONE (only affects git tracking)

**Purpose:** Don't track generated or user-specific files

**Create `.gitignore`:**

```bash
cat > .gitignore <<'EOF'
# Generated files
*.log
*.backup.*
.cache/
.config-backups/

# User-specific files
.vscode/
.idea/

# Nix build artifacts
result
result-*
.direnv/

# MacOS
.DS_Store

# Temporary files
*.tmp
*.swp
*~

# Version tracking
.nixos-quick-deploy-version
.nixos-deploy-last-backup
EOF
```

---

## 7. Add VERSION File (ZERO RISK)

**Risk:** NONE (documentation file)

**Purpose:** Track version separately from script

**Create `VERSION` file:**

```bash
cat > VERSION <<'EOF'
2.2.0
EOF
```

**Update version check in script:**

```bash
# In nixos-quick-deploy.sh, add function:

get_script_version() {
    if [ -f "$SCRIPT_DIR/VERSION" ]; then
        cat "$SCRIPT_DIR/VERSION"
    else
        echo "$SCRIPT_VERSION"  # Fallback to hardcoded version
    fi
}
```

---

## 8. Add CHANGELOG.md (ZERO RISK)

**Risk:** NONE (documentation only)

**Create `CHANGELOG.md`:**

```markdown
# Changelog

All notable changes to NixOS-Dev-Quick-Deploy will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2025-10-31

### Added
- Enhanced Claude wrapper with improved Node.js detection
- Debug mode for Claude wrapper (CLAUDE_DEBUG=1)
- Comprehensive troubleshooting documentation
- One-line installer command
- World-class dev environment package suggestions

### Fixed
- Claude Code error 127 in VSCodium
- Better error messages with troubleshooting steps
- Improved PATH resolution for Node.js in NixOS

### Changed
- Complete README revamp with better organization
- Quick deploy instructions moved to top
- Added detailed command reference

## [2.1.0] - Previous versions

(Add previous changelog entries here)

## [Unreleased]

### Planned
- Health check system
- Dry-run mode
- Backup/restore functionality
- Automated testing
```

---

## Application Instructions

### Safe Order of Application

1. **Documentation fixes** (no rebuild needed)
   ```bash
   # Fix typos
   sed -i 's/AI-Opitmizer/NixOS-Dev-Quick-Deploy/g' nixos-quick-deploy.sh

   # Add .gitignore
   cat > .gitignore <<'EOF'
   # (content from section 6)
   EOF

   # Add VERSION file
   echo "2.2.0" > VERSION

   # Add CHANGELOG.md
   # (copy content from section 8)

   # Add AIDB_SETUP.md
   # (copy content from section 3)
   ```

2. **Comment updates** (no rebuild needed)
   ```bash
   # Update VSCode version comment in templates/home.nix
   # Manually edit lines 1357-1358
   ```

3. **Add health checks** (optional, test first)
   ```bash
   # Add the run_health_checks function to nixos-quick-deploy.sh
   # Test by running the function manually first
   ```

4. **Test changes**
   ```bash
   # Verify script syntax
   bash -n nixos-quick-deploy.sh

   # Check Nix syntax
   nix-instantiate --parse templates/home.nix > /dev/null
   nix-instantiate --parse templates/configuration.nix > /dev/null
   nix-instantiate --parse templates/flake.nix > /dev/null
   ```

5. **Commit changes**
   ```bash
   git add .
   git commit -m "docs: Fix typos and add AIDB setup guide

   - Fix AI-Opitmizer typo throughout
   - Clarify VSCode profiles.default version requirements
   - Add AIDB_SETUP.md for post-deployment instructions
   - Add .gitignore for generated files
   - Add VERSION and CHANGELOG.md"
   ```

---

## Testing Checklist

Before applying changes:

- [ ] Backup current working configuration
- [ ] Review each change individually
- [ ] Test Bash syntax: `bash -n nixos-quick-deploy.sh`
- [ ] Test Nix syntax: `nix-instantiate --parse templates/*.nix`
- [ ] Verify git status before committing
- [ ] Test in VM or non-production system first (if possible)

After applying changes:

- [ ] Run the script in test mode
- [ ] Verify all documentation renders correctly
- [ ] Check that existing users aren't affected
- [ ] Update any references in README if needed

---

## Rollback Plan

If any changes cause issues:

```bash
# Revert to previous commit
git log --oneline -5
git revert <commit-hash>

# Or reset to previous version
git reset --hard HEAD~1

# Re-deploy from known good state
./nixos-quick-deploy.sh
```

---

**Note:** All improvements in this document are designed to be non-breaking and can be applied incrementally. Start with documentation fixes (sections 1-3) as they have zero risk, then proceed to optional enhancements (sections 4-8) as needed.
