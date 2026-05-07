# AQ Switchboard - Unified AI Quality Command Router

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-07

## Overview

The AQ Switchboard (`aq` binary) is a unified entry point for all AI quality tooling commands. It replaces the need to invoke individual `aq-*` binaries directly, reducing process spawning overhead and providing intelligent routing with tiered inference profiles.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         aq (switchboard)                     │
│  - Fast bash-based routing (minimal overhead)                │
│  - Tiered inference profile selection                        │
│  - Direct exec to target binary (no nesting)                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ├─────────────────┬──────────────┐
                              │                 │              │
                    ┌─────────▼────────┐  ┌────▼─────┐  ┌────▼──────┐
                    │  Simple Profile  │  │ Standard │  │   Deep    │
                    │  (no retries)    │  │ (1 retry)│  │(3 retries)│
                    └─────────┬────────┘  └────┬─────┘  └────┬──────┘
                              │                │              │
                    ┌─────────▼────────────────▼──────────────▼──────┐
                    │         Target aq-* Tool Implementation         │
                    │   (aq-qa, aq-hints, aq-autonomous-improve, ...) │
                    └─────────────────────────────────────────────────┘
```

## Tiered Inference Profiles

The switchboard implements three reasoning profiles to optimize CPU usage and response time:

### Simple Profile (Fast Path)
- **No retries, no quality loop**
- **Use cases**: CLI help, status checks, health monitoring
- **Expected latency**: ~500ms
- **CPU usage**: ~15%
- **Examples**: `aq qa 0`, `aq health`, `aq --help`

### Standard Profile (Balanced)
- **Single retry on failure**
- **Quality improver enabled**
- **Use cases**: Code generation, context analysis, diagnostics
- **Expected latency**: ~2s
- **CPU usage**: ~40%
- **Examples**: `aq hints "task"`, `aq capability-gap`

### Deep Profile (Full Quality Loop)
- **Multiple retries (up to 3)**
- **Comprehensive validation**
- **Use cases**: Architectural changes, autonomous optimization
- **Expected latency**: ~10s
- **CPU usage**: ~80%
- **Examples**: `aq autonomous-improve`, `aq meta-optimize`

## Usage

### Basic Commands

```bash
# Show help
aq --help

# List all available commands
aq --list

# Show version
aq --version
```

### Common Operations

```bash
# Status and health checks (simple profile)
aq qa 0                    # Quick health check
aq health                  # Full health diagnostic
aq status                  # Service status

# Context and hints (standard profile)
aq hints "add new feature"  # Get task guidance
aq context-bootstrap        # Bootstrap task context
aq session-zero             # Initialize session

# Capability management (standard profile)
aq capability-gap           # Detect gaps
aq capability-remediate     # Auto-apply fixes

# Research and optimization (deep profile)
aq autonomous-improve       # Run optimization cycle
aq meta-optimize            # Parameter tuning
aq autoresearch             # Self-directed research
```

### Profile Override

You can override the default profile for any command:

```bash
# Force simple profile for quick check
AQ_REASONING_PROFILE=simple aq hints "quick question"

# Force deep profile for critical operation
AQ_REASONING_PROFILE=deep aq capability-remediate
```

## Performance Optimization

### Process Spawning Reduction

Traditional approach:
```bash
$ time aq-qa 0
# 3 processes spawned: shell → aq-qa → python
# ~200ms overhead

$ time aq-hints "task"
# 3 processes spawned: shell → aq-hints → python
# ~200ms overhead
```

Switchboard approach:
```bash
$ time aq qa 0
# 2 processes: shell → aq (exec'd to aq-qa)
# ~50ms overhead

$ time aq hints "task"
# 2 processes: shell → aq (exec'd to aq-hints)
# ~50ms overhead
```

**Benefit**: ~150ms saved per invocation × 1000s of daily invocations = significant CPU reduction

### Memory Consolidation

The switchboard uses `exec` to replace the shell process with the target binary, avoiding:
- Additional memory allocation for subprocess
- IPC overhead between parent and child
- Duplicate environment variable storage

### Intelligent Caching

Profile settings include cache TTL to avoid redundant inference:
- Simple profile: 5 minute cache
- Standard profile: 10 minute cache
- Deep profile: 30 minute cache

## Integration with Hybrid Coordinator

The switchboard sets the `AQ_REASONING_PROFILE` environment variable, which the hybrid coordinator uses to:

1. **Select inference parameters** (max_tokens, temperature, etc.)
2. **Enable/disable quality improver** based on profile
3. **Configure retry logic** for robustness
4. **Route to appropriate backend** (direct llama-cpp vs full coordinator)

Configuration: `config/reasoning-profiles.json`

## Command Mapping

All 57+ `aq-*` tools are mapped to short commands. Examples:

| Command | Maps To | Profile |
|---------|---------|---------|
| `aq qa` | `aq-qa` | simple |
| `aq hints` | `aq-hints` | standard |
| `aq autonomous-improve` | `aq-autonomous-improve` | deep |
| `aq rag-prewarm` | `aq-rag-prewarm` | standard |
| `aq llama-debug` | `aq-llama-debug` | simple |

Run `aq --list` for complete mapping.

## Monitoring

### Usage Telemetry

The switchboard logs profile usage to track optimization impact:

```bash
# View profile distribution
journalctl -u ai-hybrid-coordinator | grep AQ_REASONING_PROFILE

# Sample output:
# AQ_REASONING_PROFILE=simple count=1234 avg_latency=480ms
# AQ_REASONING_PROFILE=standard count=456 avg_latency=1950ms
# AQ_REASONING_PROFILE=deep count=23 avg_latency=9800ms
```

### Performance Metrics

```bash
# Check if optimizations are working
aq qa 1  # Run extended diagnostics

# Expected output includes:
# ✓ Switchboard routing: 45ms
# ✓ Profile selection: simple
# ✓ Cache hit rate: 78%
# ✓ Avg latency vs target: 520ms vs 500ms (104%)
```

## Development

### Adding New Commands

1. Create the `aq-<command>` script
2. Add mapping to `scripts/ai/aq`:

```bash
["mycommand"]="aq-mycommand:standard"
```

3. Document the command in `aq --help`

### Testing Profile Selection

```bash
# Test simple profile
time aq qa 0

# Test standard profile
time aq hints "test task"

# Test deep profile
time aq autonomous-improve --dry-run

# Verify profile was applied
echo $AQ_REASONING_PROFILE
```

## Troubleshooting

### Command Not Found

```bash
$ aq mycommand
Error: Unknown command: mycommand
Run aq --list to see available commands
```

**Solution**: Check command name with `aq --list` or add mapping if new command.

### Profile Not Applied

```bash
# Check environment
env | grep AQ_REASONING_PROFILE

# Force profile
AQ_REASONING_PROFILE_OVERRIDE=simple aq qa 0
```

### Slow Performance

```bash
# Check if cache is working
aq qa 1  # Should show cache hit rate

# Clear cache if corrupted
rm /var/lib/ai-stack/inference-cache.db

# Restart coordinator
systemctl restart ai-hybrid-coordinator
```

## See Also

- [Reasoning Profiles Configuration](../../config/reasoning-profiles.json)
- [Embedding Cache](./embedding-cache.md)
