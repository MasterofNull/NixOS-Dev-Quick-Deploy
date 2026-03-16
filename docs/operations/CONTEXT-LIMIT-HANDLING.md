# Context Limit Handling Guide

Status: Active
Owner: AI Harness Team
Last Updated: 2026-03-15

## Overview

This guide addresses the recurring "message exceeds context limit" issue in agent mode and provides systematic solutions.

## Problem: Context Limit Exceeded

When agent conversations grow too long, you may encounter:
```
Error: message exceeds context limit
```

This indicates the conversation history has exceeded the model's maximum context window.

## Diagnostic Path

### 1. Check Current Context Usage

```bash
# View current session size
ls -lh ~/.claude/projects/*/*.jsonl

# Count messages in current session
jq -s 'length' ~/.claude/projects/*/*.jsonl
```

### 2. Identify Context Sources

Large context typically comes from:
- Long conversation history (100+ turns)
- Large file reads (>10,000 lines total)
- Repeated searches returning many results
- Accumulated tool outputs

## Solutions

### Quick Fix: Start Fresh Session

```bash
# Start new Claude Code session
claude code

# Use /clear command to reset context
/clear
```

### Progressive Disclosure Approach

Instead of reading entire large files, use progressive disclosure:

```bash
# Bad: Read entire 5000-line file
Read file.py

# Good: Read specific sections
Read file.py offset=100 limit=50
Grep "function_name" file.py output_mode=content
```

### Use Compact Modes

For status reports and summaries:

```bash
# Compact mode for aq-report
aq-report --format=compact

# Summary-only QA
./deploy ai-stack qa --phase=0 --summary-only
```

### Leverage Local LLM for Summarization

The local LLM can summarize large outputs:

```bash
# Summarize large log files
journalctl -u service.service --since "1 hour ago" | \
  aq-query --compact "Summarize key errors and warnings"
```

### Use Task Delegation

For complex multi-step work, use the Task tool to delegate to sub-agents:
- Sub-agents start with fresh context
- Only final results returned to main session
- Prevents context accumulation

## Context Optimization Strategies

### 1. Batch Operations

```python
# Instead of 100 individual queries
for item in items:
    process(item)  # 100 context entries

# Batch process
process_batch(items)  # 1 context entry
```

### 2. Use Caching

Repeated queries can use cached results:

```bash
# Enable query caching (auto in hybrid-coordinator)
curl "http://localhost:8003/query?q=test&use_cache=true"
```

### 3. Progressive Summarization

For long-running tasks:
- Summarize intermediate results
- Store summaries in files
- Reference summaries instead of full history

### 4. Session Checkpointing

Save progress and continue in fresh session:

```bash
# Save state to file
echo "Current progress: ..." > /tmp/session-state.md

# New session: load state
Read /tmp/session-state.md
# Continue from checkpoint
```

## Autonomous System Integration

The autonomous improvement system monitors context usage:

**Metrics Tracked:**
- Average tokens per request
- Context window utilization
- Query complexity distribution

**Automatic Optimizations:**
- Suggest query reformulation when context high
- Recommend batch operations for repeated patterns
- Trigger summarization for long sessions

**Check Autonomous Status:**
```bash
# View autonomous improvement recommendations
aq-autonomous-improve hypotheses | grep -i context

# Check recent improvements
aq-autonomous-improve status
```

## Prevention Best Practices

### 1. Design for Incremental Work

Break large tasks into smaller slices:
- Each slice has clear input/output
- Minimal context carryover between slices
- Use files for inter-slice communication

### 2. Use Appropriate Tools

| Task | Tool | Why |
|------|------|-----|
| Search codebase | Grep, Glob | Returns only matches |
| Read specific code | Read with offset/limit | Controlled size |
| Get status | Compact commands | Minimal output |
| Process logs | Local LLM summary | Pre-filtered |

### 3. Implement Progressive Disclosure

Load documentation on-demand:
```bash
# Instead of loading all docs upfront
Read docs/README.md  # Table of contents only

# Load specific sections as needed
Read docs/section-1.md
```

### 4. Leverage Hybrid Coordinator

The hybrid-coordinator provides context-aware routing:
- Automatically selects appropriate model for query complexity
- Uses local LLM for simple/summarization tasks
- Escalates to remote models only when needed

## Monitoring Context Health

### Dashboard View

```bash
# Full AI stack health including context metrics
./deploy ai-stack qa --phase=0

# Hybrid coordinator health
curl http://localhost:8003/health | jq '.ai_harness'
```

### Manual Checks

```bash
# PostgreSQL routing log analysis
psql -h 127.0.0.1 -U postgres -d ai_context -c "
  SELECT
    AVG(tokens_used) as avg_tokens,
    MAX(tokens_used) as max_tokens,
    COUNT(*) as total_requests
  FROM routing_log
  WHERE timestamp > NOW() - INTERVAL '24 hours';
"

# Check query gaps for context-related issues
cat /var/log/nixos-ai-stack/query-gaps.jsonl | \
  jq -r 'select(.query_text | contains("context"))'
```

### Autonomous Monitoring

The autonomous improvement system continuously monitors:

**Trigger Conditions:**
- Spike in context-related errors (>5% of requests)
- Average token usage >50% of model limits
- Repeated context limit failures

**Automatic Actions:**
1. Generate optimization hypotheses
2. Test context reduction strategies
3. Apply validated improvements
4. Record results to improvement_cycles table

```bash
# View autonomous decisions about context optimization
PGPASSWORD=$(cat /run/secrets/postgres_password) \
psql -h 127.0.0.1 -U postgres -d ai_context -c "
  SELECT * FROM improvement_cycles
  WHERE focus_area = 'context_optimization'
  ORDER BY created_at DESC LIMIT 5;
"
```

## Advanced: Context Compression

### Enable Context Compression

Already enabled in hybrid-coordinator (`context_compression_enabled: true`)

Features:
- Automatic summarization of old conversation turns
- Semantic deduplication
- Token budget allocation by phase

### Custom Compression Rules

For specific use cases, configure compression thresholds:

```python
# ai-stack/mcp-servers/hybrid-coordinator/config.py
CONTEXT_COMPRESSION_THRESHOLD = 8000  # tokens
COMPRESSION_RATIO_TARGET = 0.3  # compress to 30% of original
```

## Troubleshooting

### Issue: Context limit still exceeded after /clear

**Cause:** Tool outputs from current turn are too large

**Solution:**
1. Use pagination for large reads
2. Filter search results more aggressively
3. Summarize outputs before returning

### Issue: Can't complete task due to context constraints

**Cause:** Task inherently requires large context

**Solutions:**
1. **Task Delegation:** Use Task tool to delegate work to sub-agents
2. **Phased Execution:** Break into phases, save intermediate results to files
3. **External Storage:** Use PostgreSQL/Qdrant for large data, query as needed
4. **Local LLM Processing:** Pre-process with local model, return summaries

### Issue: Repeated context errors in autonomous mode

**Check:**
```bash
# Review autonomous improvement logs
journalctl -u ai-autonomous-improvement.service --since "24 hours ago" | \
  grep -i context

# Check if autonomous system has identified the issue
aq-autonomous-improve hypotheses --filter=context
```

**If not auto-resolved:**
1. The autonomous system may need more data (wait 24-48 hours)
2. Manual intervention may be required
3. Report to improvement_recommendations table for tracking

## Related Documentation

- [Progressive Disclosure Guide](../agent-guides/01-QUICK-START.md#progressive-disclosure)
- [Autonomous Improvement System](../AGENTS.md#autonomous-improvement)
- [Hybrid Workflow Model](../agent-guides/40-HYBRID-WORKFLOW.md)
- [Agent Quick Start](../agent-guides/01-QUICK-START.md)

## Summary: Quick Reference

| Symptom | Quick Fix | Long-term Solution |
|---------|-----------|-------------------|
| Context limit error | `/clear` and start fresh | Implement progressive disclosure |
| Large file reads | Use `offset`/`limit` params | Add summarization layer |
| Repeated queries | Enable caching | Create reusable patterns |
| Long sessions | Checkpoint and restart | Use Task delegation |
| Log analysis | Pipe through local LLM | Configure autonomous alerts |

## Integration with Autonomous System

The autonomous improvement system will:
1. **Detect** context limit patterns in routing_log
2. **Analyze** using local LLM (Qwen3-4B)
3. **Generate** optimization hypotheses
4. **Test** solutions via experiment framework
5. **Apply** validated improvements automatically
6. **Learn** from results and refine strategies

This creates a continuous improvement loop that automatically optimizes context usage over time.
