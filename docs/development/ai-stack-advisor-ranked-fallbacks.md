# AI Advisor Ranked Fallback Chains

Status: Implemented
Owner: AI Stack Team
Last Updated: 2026-04-17

## Overview

The AI advisor strategy now supports **ranked fallback chains** - each decision type has 3-4 ranked advisor models that are tried in order until one succeeds. This dramatically improves system resilience by preventing failures when a single advisor model is unavailable.

## Configuration

### Per-Decision-Type Ranked Chains

Each decision type can have its own ranked fallback chain optimized for that specific use case:

```bash
# Architecture decisions: Opus → GPT-4 → Sonnet → Gemini
AI_ADVISOR_ARCHITECTURE_MODELS_JSON='["claude-opus-4-5","gpt-4o","claude-sonnet","gemini-2.0-flash-thinking"]'

# Security decisions: Opus → GPT-4 → Sonnet → Gemini
AI_ADVISOR_SECURITY_MODELS_JSON='["claude-opus-4-5","gpt-4o","claude-sonnet","gemini-2.0-flash-thinking"]'

# Planning decisions: Gemini Thinking → Sonnet → GPT-4 → Qwen
AI_ADVISOR_PLANNING_MODELS_JSON='["gemini-2.0-flash-thinking","claude-sonnet","gpt-4o","qwen-max"]'

# Tradeoff analysis: GPT-4 → Sonnet → Gemini → Qwen
AI_ADVISOR_TRADEOFF_MODELS_JSON='["gpt-4o","claude-sonnet","gemini-2.0-flash-thinking","qwen-max"]'

# Ambiguity resolution: Sonnet → GPT-4 → Gemini → Qwen
AI_ADVISOR_AMBIGUITY_MODELS_JSON='["claude-sonnet","gpt-4o","gemini-2.0-flash-thinking","qwen-max"]'

# Global fallback (used after decision-specific chain exhausted)
AI_ADVISOR_GLOBAL_FALLBACKS_JSON='["claude-sonnet","gpt-4o","gemini-2.0-flash-thinking","qwen-max","deepseek-r1"]'
```

### Example: Cost-Optimized Configuration

Prioritize free/cheap models with expensive fallbacks:

```bash
# Architecture: Start with free Gemini, fallback to paid if needed
AI_ADVISOR_ARCHITECTURE_MODELS_JSON='["gemini-2.0-flash-thinking","qwen-max","claude-sonnet","claude-opus-4-5"]'

# Security: Start with paid for critical decisions
AI_ADVISOR_SECURITY_MODELS_JSON='["claude-opus-4-5","gpt-4o","claude-sonnet","gemini-2.0-flash-thinking"]'

# Planning: Free models work well for multi-step planning
AI_ADVISOR_PLANNING_MODELS_JSON='["gemini-2.0-flash-thinking","qwen-max","claude-sonnet","gpt-4o"]'
```

### Example: Quality-First Configuration

Prioritize best-in-class models with cost-effective fallbacks:

```bash
# All decision types start with highest quality
AI_ADVISOR_ARCHITECTURE_MODELS_JSON='["claude-opus-4-5","gpt-4o","claude-sonnet"]'
AI_ADVISOR_SECURITY_MODELS_JSON='["claude-opus-4-5","gpt-4o","claude-sonnet"]'
AI_ADVISOR_PLANNING_MODELS_JSON='["claude-opus-4-5","gemini-2.0-flash-thinking","claude-sonnet"]'
AI_ADVISOR_TRADEOFF_MODELS_JSON='["gpt-4o","claude-opus-4-5","claude-sonnet"]'
AI_ADVISOR_AMBIGUITY_MODELS_JSON='["claude-sonnet","gpt-4o","gemini-2.0-flash-thinking"]'
```

### Example: Fully Local with Remote Fallback

Local-first with remote safety net:

```bash
# Try local DeepSeek first, fallback to remote if needed
AI_ADVISOR_ARCHITECTURE_MODELS_JSON='["deepseek-r1","qwen-max","claude-sonnet","claude-opus-4-5"]'
AI_ADVISOR_SECURITY_MODELS_JSON='["deepseek-r1","claude-opus-4-5","gpt-4o"]'
AI_ADVISOR_PLANNING_MODELS_JSON='["deepseek-r1","gemini-2.0-flash-thinking","qwen-max"]'
```

## How Fallback Chains Work

### Chain Construction

For each advisor consultation, the system builds a fallback chain:

1. **Decision-specific ranked chain** (if configured)
2. **Legacy single model override** (prepended if set)
3. **Primary advisor model** (added if not in chain)
4. **Global fallbacks** (deduplicated)

Example for security decision:
```python
# Configured:
AI_ADVISOR_SECURITY_MODELS_JSON='["claude-opus-4-5","gpt-4o"]'
AI_ADVISOR_GLOBAL_FALLBACKS_JSON='["claude-sonnet","gemini-2.0-flash-thinking","qwen-max"]'

# Resulting chain:
["claude-opus-4-5", "gpt-4o", "claude-sonnet", "gemini-2.0-flash-thinking", "qwen-max"]
```

### Retry Logic

When consulting an advisor:

1. Try first model in chain (rank 0 = primary)
2. If fails → try second model (rank 1 = first fallback)
3. If fails → try third model (rank 2 = second fallback)
4. Continue until success or chain exhausted
5. If all fail → raise exception with details

Each attempt logs:
- Model being tried
- Fallback rank
- Success/failure
- Time taken

### Metrics

Fallback usage is tracked in the `advisor_consultations` table:

```sql
SELECT
    advisor_model,
    fallback_rank,
    COUNT(*) as uses,
    AVG(time_to_consult_ms) as avg_time_ms
FROM advisor_consultations
GROUP BY advisor_model, fallback_rank
ORDER BY fallback_rank, uses DESC;
```

Example output:
```
advisor_model              fallback_rank  uses  avg_time_ms
-------------------------  -------------  ----  -----------
claude-opus-4-5            0              850   1250
gpt-4o                     1              120   980
claude-sonnet              1              45    720
gemini-2.0-flash-thinking  2              15    640
```

Interpretation:
- 85% of consultations succeeded with primary model (rank 0)
- 12% needed first fallback (rank 1)
- 3% needed second fallback (rank 2)
- No third fallback needed (high reliability)

## Benefits

### 1. Resilience

**Before (single model)**:
```
Security decision → claude-opus-4-5 unavailable → FAIL
```

**After (ranked fallbacks)**:
```
Security decision → claude-opus-4-5 unavailable
                 → gpt-4o unavailable
                 → claude-sonnet SUCCESS
```

### 2. Cost Optimization

Configure cheaper models first for non-critical decisions:
```bash
# Planning: Try free models first, expensive as fallback
AI_ADVISOR_PLANNING_MODELS_JSON='[
    "gemini-2.0-flash-thinking",  # Free, fast
    "qwen-max",                   # Free, good
    "claude-sonnet",              # Paid, excellent
    "claude-opus-4-5"             # Expensive, best
]'
```

If Gemini succeeds 80% of the time → 80% cost savings

### 3. Model-Specific Strengths

Route to models best suited for each decision type:

| Decision Type | Primary | Why | Fallbacks |
|--------------|---------|-----|-----------|
| **Security** | claude-opus-4-5 | Best security reasoning | gpt-4o, claude-sonnet |
| **Planning** | gemini-2.0-flash-thinking | Extended thinking mode | claude-sonnet, qwen-max |
| **Code Architecture** | gpt-4o | Strong code understanding | claude-opus-4-5, claude-sonnet |
| **Tradeoffs** | gpt-4o | Balanced analysis | claude-sonnet, gemini |

## Monitoring

### Check Fallback Health

```bash
# Get advisor metrics including fallback usage
python3 << 'EOF'
from llm_router import get_router

router = get_router()
metrics = router.get_advisor_metrics()

print(f"Total consultations: {metrics['total_consultations']}")
print(f"Primary success rate: {metrics['primary_success_rate_percent']:.1f}%")
print(f"Fallback rate: {metrics['fallback_rate_percent']:.1f}%")
print(f"\nFallback usage by rank:")
for rank, count in sorted(metrics['fallback_usage'].items()):
    print(f"  {rank}: {count} consultations")
EOF
```

### Investigate Fallback Patterns

```bash
# Which models are most reliable?
sqlite3 routing_metrics.db "
  SELECT
    advisor_model,
    fallback_rank,
    COUNT(*) as successful_uses,
    AVG(time_to_consult_ms) as avg_latency_ms,
    AVG(advisor_cost) as avg_cost
  FROM advisor_consultations
  GROUP BY advisor_model, fallback_rank
  ORDER BY successful_uses DESC
  LIMIT 10;
"

# Which decision types need fallbacks most?
sqlite3 routing_metrics.db "
  SELECT
    decision_type,
    COUNT(CASE WHEN fallback_rank = 0 THEN 1 END) as primary_success,
    COUNT(CASE WHEN fallback_rank > 0 THEN 1 END) as fallback_needed,
    ROUND(100.0 * COUNT(CASE WHEN fallback_rank > 0 THEN 1 END) / COUNT(*), 1) as fallback_pct
  FROM advisor_consultations
  GROUP BY decision_type
  ORDER BY fallback_pct DESC;
"
```

## Troubleshooting

### High Fallback Rate

If fallback rate > 20%, investigate:

```bash
# Check which models are failing
sqlite3 routing_metrics.db "
  SELECT advisor_model, COUNT(*)
  FROM advisor_consultations
  WHERE fallback_rank > 0
  GROUP BY advisor_model;
"
```

Solutions:
- Move unreliable model down in chain
- Add more fallbacks
- Check model availability/quota

### All Fallbacks Exhausted

If seeing "All advisor models failed" errors:

1. Check logs for specific error messages
2. Verify switchboard/coordinator connectivity
3. Check model availability in OpenRouter/provider
4. Ensure global fallback chain has local model (deepseek-r1)

### Excessive Cost

If advisor costs too high:

1. Check primary success rate - should be >80%
2. Move expensive models later in chains
3. Add cheaper models early in chains
4. Consider local models for non-critical decisions

## Best Practices

1. **3-4 models per chain**: Balance resilience vs retry latency
2. **Quality gradient**: Order by quality/cost (best → good → cheap)
3. **Local safety net**: Include local model as final fallback
4. **Monitor metrics**: Track fallback rate and adjust chains
5. **Decision-specific tuning**: Optimize chains per decision type

## References

- Main implementation: [llm_router.py](ai-stack/mcp-servers/hybrid-coordinator/llm_router.py)
- Configuration: [config.py](ai-stack/mcp-servers/hybrid-coordinator/config.py)
- Base strategy: [ai-stack-advisor-strategy.md](ai-stack-advisor-strategy.md)
