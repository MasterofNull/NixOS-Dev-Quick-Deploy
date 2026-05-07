# Reasoning Profiles - Quick Reference Card

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-07

> **Quick lookup for developers using the reasoning profiles feature**

---

## 📋 Profile Selection Guide

| Task Type | Best Profile | Why |
|-----------|--------------|-----|
| **Writing new code** | `code-generation` | Low temperature (0.2) for precise syntax |
| **Debugging** | `problem-solving` | Systematic analysis at 0.4 temp |
| **Code review** | `code-review` | Critical thinking, security-focused |
| **Brainstorming** | `creative` | High temperature (1.0) for ideas |
| **Math/Logic** | `deep-reasoning` | Extended context, step-by-step |
| **Quick status** | `fast-response` | Small token limit for speed |
| **Documentation** | `precise` | Factual, deterministic outputs |
| **General tasks** | `default` | Balanced parameters |

---

## 🔧 API Usage

### Basic

```python
from workflow_planner import create_session

session = await create_session(
    objective="Debug authentication issue",
    reasoning_profile="problem-solving",  # ← Add this
    safety_mode="plan-readonly"
)
```

### With Budget Limit

```python
session = await create_session(
    objective="Quick status check",
    reasoning_profile="fast-response",
    budget={"token_limit": 500}  # Overrides profile max_tokens
)
```

### Profile Lookup

```python
from config import Config

# Get profile details
profile = Config.get_reasoning_profile("creative")
# Returns: {
#   "name": "creative",
#   "temperature": 1.0,
#   "max_tokens": 8192,
#   ...
# }

# List all profiles
profiles = Config.REASONING_PROFILES.keys()
# Returns: ['default', 'precise', 'creative', ...]
```

---

## 📦 Profile Structure

```json
{
  "my-profile": {
    "name": "my-profile",               // Required: Profile identifier
    "description": "...",               // Required: Human-readable description
    "temperature": 0.7,                 // Required: 0.0-2.0 (lower=deterministic)
    "max_tokens": 4096,                 // Required: Max output tokens
    "top_p": 0.9,                       // Required: Nucleus sampling (0.0-1.0)
    "stop_sequences": [],               // Optional: Stop generation on these strings
    "system_suffix": "..."              // Optional: Append to system prompt
  }
}
```

---

## 🔄 Hot-Reload

```python
# 1. Edit config file
vim ~/.local/share/nixos-ai-stack/reasoning-profiles.json

# 2. Reload (no restart needed)
from config import Config
Config.reload_reasoning_profiles()

# 3. Verify changes
profile = Config.get_reasoning_profile("my-profile")
print(profile)
```

---

## 📊 Profile Parameters Explained

### Temperature

| Value | Behavior | Use Case |
|-------|----------|----------|
| 0.0-0.2 | Deterministic, focused | Code, math, factual |
| 0.3-0.7 | Balanced | General tasks, reasoning |
| 0.8-1.5 | Creative, diverse | Brainstorming, writing |
| 1.6-2.0 | Very random | Experimental only |

### Max Tokens

| Value | Response Length | Use Case |
|-------|----------------|----------|
| 512-1K | Very short | Quick queries |
| 2K-4K | Standard | Most tasks |
| 8K-16K | Extended | Complex analysis |
| 32K+ | Very long | Documents, large refactors |

**Note:** Budget limits always override max_tokens if lower.

### Top-P (Nucleus Sampling)

| Value | Behavior |
|-------|----------|
| 0.9-1.0 | More diverse outputs |
| 0.8-0.9 | Balanced (recommended) |
| 0.5-0.8 | More focused outputs |

---

## 🚨 Error Handling

```python
from config import Config

try:
    profile = Config.get_reasoning_profile("nonexistent")
except ValueError as e:
    print(f"Profile not found: {e}")
    # Fallback to default
    profile = Config.get_reasoning_profile("default")
```

**Automatic Fallbacks:**
- Missing config file → Uses built-in defaults
- Invalid JSON → Uses built-in defaults
- Invalid profile fields → Uses field defaults
- Budget limit exceeded → Clamps to budget

---

## 🔍 Debugging

### Check Profile Loaded

```python
from config import Config
import logging

logging.basicConfig(level=logging.DEBUG)
profile = Config.get_reasoning_profile("creative")
# Look for: "Using reasoning profile: creative - ..."
```

### Validate Config File

```bash
# Check syntax
python3 -m json.tool ~/.local/share/nixos-ai-stack/reasoning-profiles.json

# Check loaded profiles
python3 -c "from config import Config; print(list(Config.REASONING_PROFILES.keys()))"
```

### Test Profile Application

```python
# In workflow_executor.py, check logs for:
# "Using reasoning profile: {name} - {description}"
```

---

## 💡 Best Practices

### DO ✅

- Use `code-generation` for writing new code
- Use `problem-solving` for debugging
- Use `fast-response` for simple queries
- Use `deep-reasoning` for complex logic
- Hot-reload after editing config
- Test custom profiles before production use

### DON'T ❌

- Don't use high temperature for factual tasks
- Don't set max_tokens unnecessarily high
- Don't forget to hot-reload after config changes
- Don't override safety prompts in system_suffix
- Don't use `creative` profile for security reviews
- Don't ignore ValueError exceptions

---

## 🧪 Testing Custom Profiles

```python
# test_my_profile.py
from config import Config

# Load custom profile
profile = Config.get_reasoning_profile("my-profile")

# Verify structure
assert "temperature" in profile
assert "max_tokens" in profile
assert 0.0 <= profile["temperature"] <= 2.0

# Test with session
session = await create_session(
    objective="Test task",
    reasoning_profile="my-profile"
)

# Check logs for application
# Look for: "Using reasoning profile: my-profile"
```

---

## 📁 Config File Locations

### System-wide (all users)
```
/etc/nixos-ai-stack/reasoning-profiles.json
```

### User-specific (overrides system)
```
~/.local/share/nixos-ai-stack/reasoning-profiles.json
```

### Example config
```
ai-stack/mcp-servers/shared/config/reasoning-profiles.json
```

---

## 🔢 Default Profiles Cheat Sheet

```
default          → temp:0.7  tokens:4K   General
precise          → temp:0.1  tokens:2K   Factual
creative         → temp:1.0  tokens:8K   Ideation
deep-reasoning   → temp:0.3  tokens:16K  Analysis
fast-response    → temp:0.5  tokens:1K   Quick
code-generation  → temp:0.2  tokens:4K   New code
problem-solving  → temp:0.4  tokens:8K   Debugging
code-review      → temp:0.3  tokens:4K   Review
```

---

## 📖 See Also

- **Full docs:** `docs/features/reasoning-profiles.md`
- **Quick start:** `docs/features/reasoning-profiles-quickstart.md`
- **Implementation:** `docs/features/reasoning-profiles-implementation-summary.md`
- **Tests:** `ai-stack/mcp-servers/hybrid-coordinator/test_reasoning_profiles.py`

---

**Version:** 1.0.0 | **Last Updated:** 2024 | **Status:** Production Ready ✅
