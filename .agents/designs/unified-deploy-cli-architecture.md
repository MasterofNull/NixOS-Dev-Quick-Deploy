# Unified Deploy CLI Architecture

**Version:** 1.0.0
**Date:** 2026-03-15
**Status:** Implementation Ready

## Overview

The `deploy` CLI consolidates 306 scattered scripts into a single, cohesive entry point with clear subcommands, consistent patterns, and excellent UX.

## Design Principles

1. **Single Entry Point** - One command to rule them all
2. **Consistent Interface** - Same flags, patterns across all subcommands
3. **Progressive Disclosure** - Show simple by default, detail on demand
4. **Fail-Safe** - Dry-run by default for destructive operations
5. **Self-Documenting** - Excellent help text and examples
6. **Fast Feedback** - Immediate validation, clear progress indicators

## Architecture

```
deploy (main CLI)
├── lib/
│   ├── core.sh           # Core functions (logging, error handling)
│   ├── config.sh         # Configuration management
│   ├── validation.sh     # Input validation
│   └── utils.sh          # Utility functions
├── commands/
│   ├── system.sh         # System deployment
│   ├── ai-stack.sh       # AI stack management
│   ├── test.sh           # Testing
│   ├── health.sh         # Health checks
│   ├── security.sh       # Security operations
│   ├── dashboard.sh      # Dashboard management
│   ├── config.sh         # Configuration management
│   ├── search.sh         # Semantic search
│   └── recover.sh        # Recovery operations
└── deploy                # Main entry point
```

## Command Structure

### Top-Level Commands

```bash
deploy [OPTIONS] COMMAND [COMMAND_OPTIONS] [ARGS...]

Options:
  -h, --help              Show help
  -v, --verbose           Verbose output
  -q, --quiet             Quiet mode (errors only)
  --dry-run               Show what would be done
  --config FILE           Use alternative config file
  --no-color              Disable colored output
  --json                  Output in JSON format
  --version               Show version

Commands:
  system                  Deploy/manage entire system
  ai-stack                Deploy/manage AI stack
  test                    Run test suites
  health                  Health checks and diagnostics
  security                Security operations
  dashboard               Dashboard management
  config                  Configuration management
  search                  Semantic search
  recover                 Recovery operations
  help                    Show detailed help for commands
```

### Subcommand Details

#### `deploy system`
```bash
deploy system [OPTIONS]

Deploy entire NixOS system configuration.

Options:
  --dry-run               Show what would change
  --rollback              Rollback to previous generation
  --target HOST           Deploy to remote host
  --fast                  Skip expensive checks
  --force                 Override safety checks

Examples:
  deploy system                    # Full deployment with preview
  deploy system --dry-run          # Preview changes only
  deploy system --rollback         # Rollback to previous
  deploy system --target=server    # Deploy to remote server
```

#### `deploy ai-stack`
```bash
deploy ai-stack [OPTIONS] [SERVICES...]

Deploy/manage AI stack services.

Options:
  --services=LIST         Comma-separated service list
  --restart               Restart services after deploy
  --stop                  Stop services
  --start                 Start services
  --status                Show service status
  --logs                  Show service logs

Services:
  hybrid-coordinator      Main coordination service
  aidb                    AI database
  ralph-wiggum            Ralph orchestrator
  llama-cpp               Llama inference engine
  qdrant                  Vector database
  all                     All AI services (default)

Examples:
  deploy ai-stack                              # Deploy all AI services
  deploy ai-stack hybrid-coordinator aidb      # Deploy specific services
  deploy ai-stack --restart                    # Restart all services
  deploy ai-stack --logs --services=aidb       # Show aidb logs
```

#### `deploy test`
```bash
deploy test [OPTIONS] [SUITE]

Run test suites.

Options:
  --suite=NAME            Test suite to run
  --coverage              Generate coverage report
  --parallel              Run tests in parallel
  --watch                 Watch mode (re-run on changes)

Suites:
  smoke                   Quick smoke tests (default)
  unit                    Unit tests
  integration             Integration tests
  e2e                     End-to-end tests
  performance             Performance benchmarks
  security                Security tests
  all                     All test suites

Examples:
  deploy test                     # Run smoke tests
  deploy test --suite=integration # Run integration tests
  deploy test all --coverage      # All tests with coverage
```

#### `deploy health`
```bash
deploy health [OPTIONS]

Run health checks and diagnostics.

Options:
  --services=LIST         Check specific services
  --format=FORMAT         Output format (text|json|summary)
  --fix                   Attempt to fix issues
  --continuous            Continuous monitoring mode

Examples:
  deploy health                   # Quick health check
  deploy health --format=json     # JSON output
  deploy health --fix             # Check and fix issues
  deploy health --continuous      # Monitor continuously
```

#### `deploy security`
```bash
deploy security [OPTIONS] OPERATION

Security operations and audits.

Operations:
  audit                   Run security audit
  scan                    Scan for vulnerabilities
  rotate-keys             Rotate API keys
  renew-certs             Renew TLS certificates
  firewall                Firewall audit

Options:
  --level=LEVEL           Audit level (basic|standard|deep)
  --fix                   Fix issues automatically
  --report=FILE           Save report to file

Examples:
  deploy security audit               # Security audit
  deploy security scan --fix          # Scan and fix issues
  deploy security rotate-keys         # Rotate API keys
```

#### `deploy dashboard`
```bash
deploy dashboard [OPTIONS] OPERATION

Dashboard management.

Operations:
  start                   Start dashboard
  stop                    Stop dashboard
  restart                 Restart dashboard
  status                  Show dashboard status
  open                    Open dashboard in browser

Options:
  --port=PORT             Dashboard port (default: 3000)
  --host=HOST             Dashboard host (default: localhost)

Examples:
  deploy dashboard start          # Start dashboard
  deploy dashboard open           # Open in browser
  deploy dashboard restart        # Restart dashboard
```

#### `deploy config`
```bash
deploy config [OPTIONS] OPERATION [KEY] [VALUE]

Configuration management.

Operations:
  show                    Show current configuration
  get KEY                 Get configuration value
  set KEY VALUE           Set configuration value
  validate                Validate configuration
  reset                   Reset to defaults

Options:
  --format=FORMAT         Output format (text|json|yaml)

Examples:
  deploy config show                              # Show all config
  deploy config get ai-stack.services             # Get specific value
  deploy config set ai-stack.replicas 3           # Set value
  deploy config validate                          # Validate config
```

#### `deploy search`
```bash
deploy search [OPTIONS] QUERY

Semantic search across deployments, logs, and code.

Options:
  --type=TYPE             Search type (all|deployments|logs|code|errors)
  --limit=N               Number of results (default: 10)
  --format=FORMAT         Output format (text|json)
  --explain               Show search explanation

Examples:
  deploy search "why did deployment fail"         # Search everything
  deploy search --type=errors "authentication"    # Search errors only
  deploy search --explain "configure mTLS"        # Search with explanation
```

#### `deploy recover`
```bash
deploy recover [OPTIONS] OPERATION

Recovery operations.

Operations:
  rollback                Rollback deployment
  restore                 Restore from backup
  diagnose                Diagnose issues
  fix                     Attempt automatic fix

Options:
  --to=GENERATION         Rollback to specific generation
  --backup=ID             Restore from specific backup

Examples:
  deploy recover rollback             # Rollback to previous
  deploy recover diagnose             # Diagnose issues
  deploy recover fix                  # Attempt automatic fix
```

## Configuration File

`config/deploy.yaml`:

```yaml
# Unified deployment configuration

system:
  target: nixos           # Deployment target hostname
  flake_ref: path:.       # Nix flake reference

ai_stack:
  enable: true
  services:
    - hybrid-coordinator
    - aidb
    - ralph-wiggum
    - llama-cpp
    - qdrant

dashboard:
  enable: true
  port: 3000
  host: localhost

testing:
  default_suite: smoke
  parallel: true
  coverage: false

security:
  audit_level: standard
  auto_fix: false

performance:
  deployment_timeout: 600      # 10 minutes
  service_start_timeout: 30    # 30 seconds

monitoring:
  enable: true
  metrics_retention: 30d

search:
  enable_vector_storage: true
  max_results: 10
```

## Error Handling

### Error Categories

1. **User Errors** - Invalid input, missing arguments
   - Exit code: 1
   - Action: Show usage help

2. **Configuration Errors** - Invalid configuration
   - Exit code: 2
   - Action: Show config validation errors

3. **System Errors** - Deployment failures, service errors
   - Exit code: 3
   - Action: Show detailed error + recovery suggestions

4. **Network Errors** - Connectivity issues
   - Exit code: 4
   - Action: Show retry suggestions

### Error Message Format

```
ERROR: Brief description of what went wrong

Details:
  - Specific detail 1
  - Specific detail 2

Suggestions:
  1. Try this first
  2. If that doesn't work, try this
  3. For more help: deploy help <command>

Logs: /path/to/detailed/logs.txt
```

## Progress Indicators

### Spinner for Quick Operations (<5s)
```
⠋ Checking service health...
```

### Progress Bar for Long Operations (>5s)
```
Deploying system [████████████░░░░░░░░] 60% (3/5 services)
  ✓ hybrid-coordinator
  ✓ aidb
  ⚙ ralph-wiggum
  - llama-cpp
  - qdrant
```

### Status Updates for Multi-Step
```
[1/4] Validating configuration... ✓
[2/4] Building Nix derivation... ⚙ (2m15s)
[3/4] Deploying services...
[4/4] Running health checks...
```

## Logging

### Log Levels
- **ERROR**: Errors that prevent operation
- **WARN**: Warnings that don't prevent operation
- **INFO**: Important informational messages
- **DEBUG**: Detailed diagnostic information

### Log Files
- `logs/deploy.log` - Main deployment log
- `logs/deploy-<timestamp>.log` - Timestamped deployment logs
- `logs/services/<service>.log` - Per-service logs

### Log Rotation
- Keep last 30 days
- Compress logs older than 7 days
- Max log size: 100MB before rotation

## Backward Compatibility

### Deprecation Strategy

1. **Phase 1 (Weeks 1-2)**: Add warnings to old scripts
   ```bash
   # In old scripts:
   echo "WARNING: This script is deprecated. Use: deploy <command>"
   echo "This script will be removed in 4 weeks."
   ```

2. **Phase 2 (Weeks 3-6)**: Make old scripts redirect to new CLI
   ```bash
   # In old scripts:
   echo "DEPRECATED: Redirecting to new CLI..."
   exec deploy <equivalent-command> "$@"
   ```

3. **Phase 3 (Weeks 7-8)**: Remove old scripts
   - Archive old scripts to `archive/deprecated-scripts/`
   - Update all documentation

### Migration Guide

Provide clear mapping from old scripts to new commands:

```markdown
# Migration Guide

| Old Script | New Command |
|------------|-------------|
| nixos-quick-deploy.sh | deploy system |
| scripts/ai/ai-stack-health.sh | deploy health --services=ai-stack |
| scripts/automation/run-all-checks.sh | deploy test all |
| scripts/security/security-audit.sh | deploy security audit |
```

## Performance Targets

- **Startup time**: <100ms (CLI ready to accept commands)
- **Help display**: <50ms
- **Dry-run preview**: <2s
- **Full deployment**: <5 minutes
- **Service restart**: <30s
- **Health check**: <5s

## Testing Strategy

### Unit Tests
- Test each command handler independently
- Test argument parsing and validation
- Test error handling

### Integration Tests
- Test complete workflows
- Test command chaining
- Test rollback scenarios

### End-to-End Tests
- Deploy to test environment
- Verify all services healthy
- Test recovery procedures

## Documentation

### Built-in Help
```bash
deploy --help                    # Main help
deploy system --help             # Command-specific help
deploy help system               # Detailed help with examples
```

### Man Pages
Generate man pages for all commands:
```bash
man deploy
man deploy-system
man deploy-test
```

### Cheat Sheet
Quick reference card:
```bash
deploy cheatsheet                # Show cheat sheet
deploy cheatsheet --pdf          # Generate PDF
```

## Implementation Plan

1. **Week 1, Day 1-2**: Core framework
   - Main deploy script with arg parsing
   - Logging system
   - Configuration loader
   - Error handling

2. **Week 1, Day 3-4**: System command
   - Migrate from nixos-quick-deploy.sh
   - Implement dry-run
   - Implement rollback

3. **Week 1, Day 5**: AI stack command
   - Service management
   - Log viewing
   - Status checking

4. **Week 2, Day 1-2**: Test, health, security commands
   - Consolidate test scripts
   - Consolidate health checks
   - Consolidate security scripts

5. **Week 2, Day 3-4**: Dashboard, config, search commands
   - Dashboard management
   - Config operations
   - Semantic search integration

6. **Week 2, Day 5**: Polish and documentation
   - Help text
   - Examples
   - Migration guide

## Success Criteria

- ✅ All 306 old scripts have equivalent in new CLI
- ✅ Performance targets met
- ✅ All tests passing
- ✅ Documentation complete
- ✅ User acceptance (team can use it without training)
- ✅ Zero regressions from old scripts

## Open Questions

1. Should we support command aliases? (e.g., `deploy sys` for `deploy system`)
2. Should we have interactive mode for dangerous operations?
3. Should we support plugins/extensions for custom commands?

## References

- [SYSTEM-EXCELLENCE-ROADMAP-2026-Q2.md](.agents/plans/SYSTEM-EXCELLENCE-ROADMAP-2026-Q2.md)
- [deployment-scripts-audit-2026-03.md](.agents/audits/deployment-scripts-audit-2026-03.md)
- Click CLI framework: https://click.palletsprojects.com/
- Modern CLI best practices: https://clig.dev/
