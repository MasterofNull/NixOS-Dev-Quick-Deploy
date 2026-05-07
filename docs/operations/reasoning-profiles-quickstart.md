# Reasoning Profiles Quick Start Guide

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-07

## What Are Reasoning Profiles?

Reasoning profiles let you customize how the AI thinks based on your task:
- **Writing code?** Use `code-generation` (precise, follows best practices)
- **Debugging?** Use `problem-solving` (systematic, methodical)
- **Quick query?** Use `fast-response` (concise, efficient)
- **Complex design?** Use `deep-reasoning` (extended thinking, step-by-step)

## 5-Minute Setup

### 1. Copy Example Configuration

```bash
# Create config directory
mkdir -p ~/.local/share/nixos-ai-stack/

# Copy example profiles
cp ai-stack/mcp-servers/shared/config/reasoning-profiles.json \
   ~/.local/share/nixos-ai-stack/
```

### 2. Use in Your Session

```python
# Python API
session = await workflow_planner.create_session(
    objective="Refactor the authentication module",
    reasoning_profile="code-review",  # ← Add this line
    safety_mode="plan-readonly"
)
```

### 3. Done! ✅

That's it. The AI will now use the `code-review` profile, which is tuned for critical analysis and security evaluation.

## Built-in Profiles

| Profile | Best For | Temperature | Tokens |
|---------|----------|-------------|--------|
| **default** | General tasks | 0.7 | 4K |
| **precise** | Exact outputs | 0.1 | 2K |
| **creative** | Brainstorming | 1.0 | 8K |
| **deep-reasoning** | Complex problems | 0.3 | 16K |
| **fast-response** | Quick queries | 0.5 | 1K |
| **code-generation** | Writing code | 0.2 | 4K |
| **problem-solving** | Debugging | 0.4 | 8K |
| **code-review** | Security review | 0.3 | 4K |

## Common Use Cases

### Writing New Code

```python
session = await workflow_planner.create_session(
    objective="Create a new authentication service",
    reasoning_profile="code-generation"
)
```

**Why?** Low temperature (0.2) = consistent, predictable code that follows patterns.

### Debugging a Bug

```python
session = await workflow_planner.create_session(
    objective="Fix the memory leak in the cache module",
    reasoning_profile="problem-solving"
)
```

**Why?** Moderate temperature (0.4) = systematic analysis with flexibility for creative solutions.

### Reviewing Code for Security

```python
session = await workflow_planner.create_session(
    objective="Review authentication.py for security vulnerabilities",
    reasoning_profile="code-review"
)
```

**Why?** Low temperature (0.3) + critical thinking prompt = thorough, security-focused analysis.

### Brainstorming Architecture

```python
session = await workflow_planner.create_session(
    objective="Design a scalable microservices architecture",
    reasoning_profile="creative"
)
```

**Why?** High temperature (1.0) + large token budget = diverse, innovative ideas.

### Quick Status Check

```python
session = await workflow_planner.create_session(
    objective="Check if tests are passing",
    reasoning_profile="fast-response"
)
```

**Why?** Small token budget (1K) = quick, concise answer without unnecessary detail.

## Customizing Profiles

### Edit Your Configuration

```bash
nano ~/.local/share/nixos-ai-stack/reasoning-profiles.json
```

### Add a Custom Profile

```json
{
  "my-profile": {
    "name": "my-profile",
    "description": "Custom profile for my specific use case",
    "temperature": 0.5,
    "max_tokens": 6000,
    "top_p": 0.9,
    "stop_sequences": [],
    "system_suffix": "Always include performance considerations."
  }
}
```

### Hot-Reload (No Restart Required!)

```python
from config import Config
Config.reload_reasoning_profiles()
```

Your changes are live immediately.

## Temperature Guide

| Temperature | Behavior | Use When |
|-------------|----------|----------|
| **0.1 - 0.3** | Very deterministic | Code, security, factual answers |
| **0.4 - 0.6** | Balanced | Problem-solving, general tasks |
| **0.7 - 0.9** | Creative | Brainstorming, design, writing |
| **1.0+** | Very creative | Ideation, exploration |

## Token Budget Guide

| Tokens | Equivalent | Use When |
|--------|------------|----------|
| **1K** | ~750 words | Quick queries, status checks |
| **2K** | ~1,500 words | Short explanations |
| **4K** | ~3,000 words | Code generation, detailed answers |
| **8K** | ~6,000 words | Complex analysis, debugging |
| **16K** | ~12,000 words | Deep reasoning, architecture design |

## Advanced: System Suffixes

System suffixes add extra instructions to the AI's system prompt:

```json
{
  "security-focused": {
    "system_suffix": "Always consider security implications. Flag potential vulnerabilities."
  }
}
```

**Pro Tip:** Use suffixes to add domain-specific guidance without changing core prompts.

## Troubleshooting

### Profile Not Found Error

```
ValueError: Reasoning profile 'typo-profile' not found
```

**Solution:** Check spelling. List available profiles:

```python
from config import Config
print(Config.REASONING_PROFILES.keys())
```

### File Not Loading

**Check location:**
```bash
ls -la ~/.local/share/nixos-ai-stack/reasoning-profiles.json
```

**Check JSON validity:**
```bash
python3 -m json.tool ~/.local/share/nixos-ai-stack/reasoning-profiles.json
```

### Profile Not Taking Effect

1. Verify you're passing `reasoning_profile` parameter
2. Check logs for warnings:
   ```bash
   tail -f /var/log/ai-stack/hybrid-coordinator.log | grep profile
   ```
3. Try hot-reloading:
   ```python
   Config.reload_reasoning_profiles()
   ```

## Best Practices

### ✅ DO

- **Match profile to task type**
  - Code = `code-generation`
  - Debug = `problem-solving`
  - Review = `code-review`

- **Start with defaults, then tune**
  - Use built-in profiles first
  - Customize only if needed

- **Set appropriate token budgets**
  - Don't waste tokens on simple tasks
  - Don't starve complex tasks

- **Use system suffixes for domain guidance**
  - Add domain-specific constraints
  - Emphasize critical requirements

### ❌ DON'T

- **Don't use creative profiles for code**
  - High temperature = inconsistent syntax
  - Stick to 0.1-0.3 for code generation

- **Don't use precise profiles for brainstorming**
  - Low temperature = limited ideas
  - Use 0.8+ for ideation

- **Don't set max_tokens too low**
  - AI needs room to think
  - Minimum 1K for most tasks

- **Don't ignore budget limits**
  - Profiles can request more than budget
  - Budget always wins (safety feature)

## Monitoring

### Check Current Profile in Logs

```bash
tail -f /var/log/ai-stack/hybrid-coordinator.log | grep "Using reasoning profile"
```

### Track Token Usage

```bash
# See which profiles use the most tokens
grep "profile.*tokens" /var/log/ai-stack/hybrid-coordinator.log | \
  awk '{print $5, $8}' | sort | uniq -c
```

### Profile Performance Analysis

```python
# Coming soon: Built-in analytics
from config import Config
stats = Config.get_profile_stats()  # Future feature
```

## Examples by Task Type

### Data Analysis
```python
reasoning_profile="problem-solving"  # Systematic approach
```

### Documentation Writing
```python
reasoning_profile="creative"  # Clear explanations
```

### Bug Triage
```python
reasoning_profile="fast-response"  # Quick assessment
```

### Performance Optimization
```python
reasoning_profile="code-review"  # Critical analysis
```

### API Design
```python
reasoning_profile="deep-reasoning"  # Thorough planning
```

### Unit Test Writing
```python
reasoning_profile="code-generation"  # Consistent patterns
```

## Getting Help

- **Documentation:** `docs/features/reasoning-profiles.md`
- **Examples:** `shared/config/reasoning-profiles.json`
- **Logs:** `/var/log/ai-stack/hybrid-coordinator.log`
- **Test:** `python3 test_reasoning_profiles.py`

## What's Next?

1. **Try each profile** to see what works for your tasks
2. **Create custom profiles** for your workflow
3. **Share your profiles** with your team
4. **Monitor usage** to optimize token efficiency

Happy reasoning! 🚀
