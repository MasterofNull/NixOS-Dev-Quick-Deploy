# ADK Implementation Discovery Guide

**Status:** production
**Owner:** ai-harness
**Last Updated:** 2026-03-20

## Overview

The ADK Implementation Discovery system provides automated monitoring and integration of Google ADK (Agent Development Kit) features into the NixOS-Dev-Quick-Deploy harness. This guide covers architecture, workflows, configuration, and best practices.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Discovery Workflow](#discovery-workflow)
3. [Parity Tracking Methodology](#parity-tracking-methodology)
4. [Declarative Wiring Requirements](#declarative-wiring-requirements)
5. [Integration Examples](#integration-examples)
6. [Configuration Reference](#configuration-reference)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

## Architecture Overview

### Components

The ADK integration system consists of several interconnected components:

```
┌─────────────────────────────────────────────────────────────┐
│                   ADK Integration System                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐        ┌──────────────────┐          │
│  │ Implementation   │───────>│  Parity Tracker  │          │
│  │ Discovery        │        │  (Python)        │          │
│  │ (Bash)           │        └──────────────────┘          │
│  └──────────────────┘                 │                     │
│          │                            │                     │
│          │                            v                     │
│          │                 ┌──────────────────┐            │
│          │                 │  Dashboard API   │            │
│          │                 │  (FastAPI)       │            │
│          │                 └──────────────────┘            │
│          │                            │                     │
│          v                            v                     │
│  ┌──────────────────┐        ┌──────────────────┐          │
│  │ Wiring Validator │        │  Scheduling      │          │
│  │ (Bash)           │        │  (systemd/cron)  │          │
│  └──────────────────┘        └──────────────────┘          │
│          │                                                  │
│          v                                                  │
│  ┌──────────────────────────────────────────────┐          │
│  │       Declarative Wiring Spec (Nix)          │          │
│  └──────────────────────────────────────────────┘          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Discovery Phase**: Monitor ADK releases and extract new features
2. **Analysis Phase**: Compare features against current harness capabilities
3. **Gap Identification**: Identify missing or deferred capabilities
4. **Parity Calculation**: Calculate category and overall parity scores
5. **Reporting Phase**: Generate reports and dashboard updates
6. **Notification Phase**: Alert on significant discoveries or regressions

### File Structure

```
repo/
├── lib/adk/
│   ├── implementation-discovery.sh   # Discovery workflow automation
│   ├── parity-tracker.py             # Parity calculation and tracking
│   ├── wiring-validator.sh           # Declarative compliance validation
│   └── declarative-wiring-spec.nix   # Nix module templates
├── scripts/adk/
│   └── schedule-discovery.sh         # Scheduling automation
├── .agent/adk/
│   ├── discoveries/                  # Extracted features
│   ├── reports/                      # Gap and parity reports
│   ├── changelogs/                   # Cached ADK releases
│   └── parity-scorecard.json         # Current parity state
└── docs/adk/
    ├── implementation-discovery-guide.md
    └── adk-parity-scorecard.md
```

## Discovery Workflow

### Automated Discovery Process

The implementation discovery workflow runs periodically (weekly by default) to:

1. **Fetch ADK Releases**
   - Query GitHub API for latest releases
   - Cache release data (12-hour TTL)
   - Validate JSON responses

2. **Extract Features**
   - Parse release notes for new features
   - Use pattern matching to identify capabilities
   - Classify by confidence level

3. **Compare with Harness**
   - Load current parity scorecard
   - Match features against known capabilities
   - Identify new gaps

4. **Prioritize Gaps**
   - High priority: Agent protocols, tool calling
   - Medium priority: Performance, optimization
   - Low priority: UI enhancements, convenience features

5. **Generate Reports**
   - JSON reports for API consumption
   - Markdown reports for documentation
   - Roadmap update recommendations

6. **Notify Dashboard**
   - Create notification files
   - Invalidate API caches
   - Update parity history

### Manual Discovery

Run discovery manually:

```bash
# Run with default settings
lib/adk/implementation-discovery.sh

# Force fresh data fetch
lib/adk/implementation-discovery.sh --force

# Enable verbose logging
lib/adk/implementation-discovery.sh --verbose
```

### Output Files

Discovery generates several output files:

- `discoveries/features-YYYYMMDD.json` - Extracted features
- `reports/capability-gaps-YYYYMMDD.json` - Identified gaps
- `reports/roadmap-updates-YYYYMMDD.md` - Roadmap recommendations
- `latest-discovery-notification.json` - Dashboard notification

## Parity Tracking Methodology

### Parity Status Categories

Each ADK capability is classified into one of four status categories:

| Status | Description | Score Weight |
|--------|-------------|--------------|
| **Adopted** | Fully integrated into harness | 1.0 (100%) |
| **Adapted** | Modified or alternative implementation | 0.8 (80%) |
| **Deferred** | Planned but not yet implemented | 0.0 (0%) |
| **Not Applicable** | Doesn't apply to this harness | Excluded |

### Parity Score Calculation

Category parity score:
```
category_parity = sum(status_weights) / count(applicable_capabilities)
```

Overall parity score:
```
overall_parity = sum(category_scores) / count(categories)
```

### Capability Categories

1. **Agent Protocol** - A2A messaging, discovery, delegation
2. **Tool Calling** - OpenAI tools, parallel execution, streaming
3. **Context Management** - History, compression, semantic memory
4. **Model Integration** - Local/remote models, routing
5. **Observability** - Metrics, tracing, audit logs
6. **Workflow Management** - Blueprints, gates, orchestration

### Parity History Tracking

Parity scores are tracked over time to identify trends:

- History maintained for last 100 data points
- Stored in `parity-history.json`
- Enables trend analysis and regression detection

### Regression Detection

Parity regression triggers when:

- Overall parity decreases >5%
- Category parity decreases >10%
- Status changes from Adopted/Adapted to Deferred

## Declarative Wiring Requirements

### Core Principles

All ADK integrations must follow declarative-first wiring:

1. **No Hardcoded Values**
   - Ports from `config.mySystem.ports`
   - URLs from environment or config
   - Secrets from `*File` options

2. **Explicit Dependencies**
   - SystemD service dependencies
   - Port configuration dependencies
   - Module dependencies

3. **Environment Injection**
   - All configuration via environment
   - Support for `extraEnv` options
   - Proper type declarations

4. **Observability Hooks**
   - Metrics endpoints
   - Health checks
   - Audit logging

### Nix Module Template

```nix
{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.mySystem.aiStack.adk.integrations.example;
in {
  options.mySystem.aiStack.adk.integrations.example = {
    enable = mkEnableOption "Example ADK integration";

    environment = {
      baseUrl = mkOption {
        type = types.str;
        description = "Base URL (from ports module)";
      };

      apiKeyFile = mkOption {
        type = types.nullOr types.path;
        default = null;
        description = "Path to API key file";
      };
    };

    # ... more options ...
  };

  config = mkIf cfg.enable {
    # Service configuration
  };
}
```

### Validation

Validate wiring compliance:

```bash
# Validate all Nix files
lib/adk/wiring-validator.sh

# Validate staged files (pre-commit)
lib/adk/wiring-validator.sh --staged

# Validate specific directory
lib/adk/wiring-validator.sh --dir lib/adk --pattern "*.nix"
```

Validation checks:

- ✓ No hardcoded ports
- ✓ No hardcoded URLs
- ✓ No hardcoded secrets
- ✓ Proper Nix option declarations
- ✓ Environment injection patterns
- ✓ Service dependency declarations

## Integration Examples

### Example 1: Basic Agent Integration

```nix
mySystem.aiStack.adk.integrations.basic-agent = {
  enable = true;
  name = "basic-adk-agent";

  environment = {
    baseUrl = "http://127.0.0.1:${toString config.mySystem.ports.basicAgent}";
    configFile = /etc/adk/basic-agent.json;
  };

  a2a = {
    enable = true;
    agentCard = {
      name = "Basic Agent";
      version = "1.0.0";
      capabilities = [ "task_execution" ];
    };
  };
};
```

### Example 2: Tool-Calling Agent

```nix
mySystem.aiStack.adk.integrations.tool-agent = {
  enable = true;
  name = "tool-calling-agent";

  tools = {
    enable = true;
    registry = [
      {
        name = "search";
        description = "Search for information";
        schema = {
          type = "object";
          properties.query = { type = "string"; };
          required = [ "query" ];
        };
        handler = "/tools/search";
      }
    ];
  };

  observability = {
    metrics.enable = true;
    metrics.port = config.mySystem.ports.toolAgentMetrics;
  };
};
```

### Example 3: Full-Featured Agent

```nix
mySystem.aiStack.adk.integrations.full-agent = {
  enable = true;
  name = "full-featured-agent";

  environment = {
    baseUrl = "http://127.0.0.1:${toString config.mySystem.ports.fullAgent}";
    apiKeyFile = config.age.secrets.adk-api-key.path;
    extraEnv = {
      ADK_LOG_LEVEL = "debug";
      ADK_TIMEOUT = "30";
    };
  };

  dependencies = {
    services = [ "ai-hybrid-coordinator.service" "postgresql.service" ];
    ports = [ "fullAgent" "hybridCoordinator" ];
  };

  a2a = {
    enable = true;
    agentCard = {
      name = "Full Featured Agent";
      version = "2.0.0";
      capabilities = [
        "task_execution"
        "event_streaming"
        "tool_calling"
      ];
    };
  };

  tools.enable = true;

  observability = {
    metrics.enable = true;
    logging.level = "info";
    tracing.enable = false;
  };

  healthCheck = {
    enable = true;
    interval = 30;
  };
};
```

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ADK_DISCOVERY_SCHEDULE` | `weekly` | Discovery schedule frequency |
| `VERBOSE` | `0` | Enable verbose logging |
| `STRICT_MODE` | `1` | Enforce strict validation |
| `REPO_ROOT` | `/etc/nixos` | Repository root path |

### Discovery Script Options

```bash
lib/adk/implementation-discovery.sh [OPTIONS]

Options:
  --force         Force refresh of cached data
  --verbose, -v   Enable verbose logging
  --help, -h      Show help message
```

### Parity Tracker Options

```bash
lib/adk/parity-tracker.py [OPTIONS]

Options:
  --output FILE         Output file for scorecard
  --format FORMAT       Output format (json|markdown)
  --check-regression    Check for parity regressions
  --data-dir DIR        Data directory
```

### Wiring Validator Options

```bash
lib/adk/wiring-validator.sh [OPTIONS]

Options:
  --staged          Validate staged files only
  --dir DIR         Target directory
  --pattern PATTERN File pattern
  --no-strict       Disable strict mode
```

### Scheduling Options

```bash
scripts/adk/schedule-discovery.sh [COMMAND] [OPTIONS]

Commands:
  setup             Set up scheduled discovery
  remove            Remove scheduled discovery
  status            Check schedule status
  run               Run discovery now

Options:
  --schedule SCHED  Schedule frequency (daily|weekly|monthly)
```

## Troubleshooting

### Common Issues

#### Discovery Fails to Fetch Releases

**Problem**: Cannot fetch ADK releases from GitHub API

**Solutions**:
1. Check network connectivity
2. Verify GitHub API is accessible
3. Check rate limiting (60 req/hour unauthenticated)
4. Use cached data: remove `--force` flag

#### Parity Scorecard Not Generated

**Problem**: Parity tracker fails to generate scorecard

**Solutions**:
1. Check Python 3 is installed
2. Verify data directory permissions
3. Run manually: `lib/adk/parity-tracker.py --verbose`
4. Check logs in `.agent/adk/logs/`

#### Wiring Validation Fails

**Problem**: Validation reports hardcoded values

**Solutions**:
1. Review validation report in `.agent/adk/reports/`
2. Replace hardcoded ports with `config.mySystem.ports.*`
3. Replace hardcoded URLs with environment variables
4. Use `*File` options for secrets

#### Dashboard API Returns 503

**Problem**: ADK endpoints return "not available"

**Solutions**:
1. Run discovery: `lib/adk/implementation-discovery.sh`
2. Generate parity scorecard: `lib/adk/parity-tracker.py`
3. Check file permissions in `.agent/adk/`
4. Verify `REPO_ROOT` environment variable

### Debug Mode

Enable verbose logging:

```bash
VERBOSE=1 lib/adk/implementation-discovery.sh
VERBOSE=1 lib/adk/wiring-validator.sh
```

### Log Files

Check logs for detailed error information:

```bash
# Discovery logs
ls -lt .agent/adk/logs/discovery-*.log | head -5

# Systemd logs (if using timer)
journalctl --user -u adk-discovery.service

# Cron logs (if using cron)
tail -f .agent/adk/logs/discovery-cron.log
```

## Best Practices

### Discovery Workflow

1. **Schedule Appropriately**
   - Use weekly schedule for production
   - Use daily for active development
   - Avoid unnecessary API calls

2. **Monitor Notifications**
   - Review dashboard notifications weekly
   - Prioritize high-priority gaps
   - Track parity trends

3. **Validate Discoveries**
   - Don't blindly adopt all features
   - Evaluate fit for harness
   - Consider adaptation vs adoption

### Parity Tracking

1. **Regular Reviews**
   - Review parity scorecard monthly
   - Track category trends
   - Address regressions promptly

2. **Documentation**
   - Document adaptation decisions
   - Note why features are deferred
   - Track N/A rationale

3. **Goal Setting**
   - Target >80% overall parity
   - Focus on high-priority categories
   - Accept some deferrals

### Declarative Wiring

1. **Zero Hardcoded Values**
   - All ports from config
   - All URLs from environment
   - All secrets from files

2. **Explicit Dependencies**
   - Declare service dependencies
   - Document port requirements
   - Test dependency resolution

3. **Validation in CI**
   - Run wiring validator in pre-commit
   - Fail on strict violations
   - Review warnings regularly

### Integration Development

1. **Start with Template**
   - Use declarative-wiring-spec.nix examples
   - Follow established patterns
   - Validate early and often

2. **Incremental Integration**
   - Start with minimal viable integration
   - Add features incrementally
   - Test each addition

3. **Documentation**
   - Document integration decisions
   - Provide usage examples
   - Update parity scorecard

### Maintenance

1. **Keep Components Updated**
   - Update ADK version tracking
   - Refresh capability matrix
   - Review deferred items

2. **Monitor Health**
   - Check `/api/adk/status` regularly
   - Address stale data
   - Validate schedules work

3. **Continuous Improvement**
   - Refine discovery patterns
   - Improve gap prioritization
   - Enhance reporting

## Next Steps

After implementing ADK discovery:

1. Review initial parity scorecard
2. Prioritize high-impact gaps
3. Create roadmap items for integration
4. Set up weekly discovery schedule
5. Monitor dashboard for new discoveries
6. Validate integrations regularly

## References

- [ADK Parity Scorecard](./adk-parity-scorecard.md)
- [Declarative Wiring Spec](../../lib/adk/declarative-wiring-spec.nix)
- [AI Harness Implementation Roadmap](../roadmap/AI-HARNESS-IMPLEMENTATION-ROADMAP-2026-03.md)
- [Phase 4.4 Requirements](../../.agents/plans/)

---

For questions or issues, consult the troubleshooting section or review component logs.
