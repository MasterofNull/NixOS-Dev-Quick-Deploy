# Deployment Scripts & Entry Points Audit

**Date:** 2026-03-15
**Purpose:** Identify all deployment scripts and entry points for consolidation
**Total Scripts Found:** 306 shell scripts

## Current State: Multiple Confusing Entry Points ❌

### Primary Deployment Script
- **nixos-quick-deploy.sh** (140KB, 3,211 lines) - Main deployment script

### Problems Identified

1. **No Single Source of Truth**
   - 306 shell scripts across multiple directories
   - Unclear which script to run for what purpose
   - Overlapping functionality between scripts

2. **Scattered Entry Points**
   - Deployment scripts in root and multiple subdirectories
   - Testing scripts mixed with deployment scripts
   - Automation scripts with duplicate logic

3. **Configuration Fragmentation**
   - Multiple autonomous coordinator scripts (3+)
   - Various import/setup scripts
   - Security scripts scattered across locations

## Script Categories

### Deployment & Setup
```
nixos-quick-deploy.sh                           # Main deployment (140KB)
scripts/automation/post-deploy-converge.sh      # Post-deployment tasks
scripts/automation/prime-ai-tooling-defaults.sh # AI tooling setup
scripts/apply-tls-certificates.sh               # TLS setup
```

### AI Stack Management
```
scripts/ai/ai-stack-health.sh                   # Health checks
scripts/ai/ai-stack-e2e-test.sh                 # End-to-end testing
scripts/ai/ai-stack-resume-recovery.sh          # Recovery procedures
scripts/ai/ai-stack-troubleshoot.sh             # Troubleshooting
scripts/ai/ai-stack-feature-scenario.sh         # Feature scenarios
scripts/ai/autonomous-coordinator.sh            # Autonomous coordinator (original)
scripts/ai/autonomous-coordinator-local.sh      # Local variant
scripts/ai/autonomous-coordinator-simple.sh     # Simple variant
scripts/ai/ralph-orchestrator.sh                # Ralph orchestration
scripts/ai/complete-via-ralph.sh                # Ralph completion
```

### Testing & Validation
```
scripts/automation/run-all-checks.sh            # All checks
scripts/automation/run-acceptance-checks.sh     # Acceptance tests
scripts/automation/run-qa-suite.sh              # QA suite
scripts/automation/run-eval.sh                  # Evaluation
scripts/automation/run-advanced-parity-suite.sh # Parity tests
scripts/automation/run-harness-regression-gate.sh # Regression gate
scripts/testing/*.sh                            # 100+ test scripts
```

### Security & Maintenance
```
scripts/security/security-audit.sh              # Security audit
scripts/security/rotate-api-key.sh              # Key rotation
scripts/security/renew-tls-certificate.sh       # TLS renewal
scripts/security/firewall-audit.sh              # Firewall checks
scripts/reliability/check-runtime-reliability.sh # Reliability checks
```

### Import & Migration
```
scripts/import-agent-instructions.sh            # Agent instructions
scripts/ai/aq-knowledge-import.sh               # Knowledge import
scripts/archive-project-knowledge.sh            # Knowledge archival
scripts/cleanup-migrated-reports.sh             # Report cleanup
```

### Model & LLM Management
```
scripts/ai/ai-model-manager.sh                  # Model management
scripts/ai/ai-model-setup.sh                    # Model setup
scripts/ai/llama-model-cli.sh                   # Llama CLI
scripts/ai/update-llama-cpp.sh                  # Llama.cpp updates
```

## Consolidation Requirements

### Must Have: Single Entry Point
Create unified deployment CLI with clear subcommands:
```bash
./deploy                    # Main entry point
./deploy system             # Full system deployment
./deploy ai-stack           # AI stack only
./deploy test               # Run test suite
./deploy health             # Health check
./deploy security           # Security audit
./deploy --help             # Show all commands
```

### Integration Requirements
1. **Seamless Workflows** - No bolt-on features
2. **Single Configuration Source** - One place for all settings
3. **Clear Documentation** - Each command documented
4. **Consistent Patterns** - Same flags, same output format
5. **Error Recovery** - Built-in rollback and recovery

### Dashboard Integration Gaps
- Dashboard backend exists but not fully integrated with deployment
- Monitoring data not flowing to dashboard automatically
- No real-time deployment progress in dashboard
- Alert system not connected to dashboard visualization

## Recommendations

### Phase 1: Consolidation (Week 1-2)
1. Create unified `deploy` CLI script
2. Migrate all deployment logic from nixos-quick-deploy.sh
3. Add subcommands for test, health, security
4. Deprecated old scripts with warnings

### Phase 2: Integration (Week 3-4)
1. Connect dashboard to deployment pipeline
2. Real-time deployment progress tracking
3. Integrate monitoring data flows
4. Connect alert system to dashboard

### Phase 3: Agentic Storage (Week 5-6)
1. Implement vector storage for deployment history
2. Add semantic search for deployment logs
3. Create knowledge base from past deployments
4. Enable AI-powered troubleshooting

### Phase 4: End-to-End Validation (Week 7-8)
1. Complete workflow testing
2. Remove all optional/bolt-on features
3. Ensure every feature is seamlessly integrated
4. Performance optimization

## Success Criteria

- ✅ Single `deploy` entry point for all operations
- ✅ Dashboard fully integrated with deployment pipeline
- ✅ All monitoring data flowing to dashboard
- ✅ Agentic storage techniques implemented
- ✅ Zero bolt-on features - everything integrated
- ✅ End-to-end workflows validated
- ✅ All tests passing
- ✅ Documentation complete

## Next Steps

1. Create unified deployment CLI architecture design
2. Design dashboard integration specification
3. Plan agentic storage schema
4. Create comprehensive Q2 2026 roadmap

## References

- nixos-quick-deploy.sh: 3,211 lines, primary deployment script
- Total scripts: 306 shell scripts
- Dashboard: `dashboard/` directory (React frontend + Python backend)
- Configuration: `config/` directory (JSON/YAML files)
