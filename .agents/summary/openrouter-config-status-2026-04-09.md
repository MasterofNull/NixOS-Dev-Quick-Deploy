# OpenRouter Configuration Status

**Date:** 2026-04-09
**Status:** Partially configured - missing API key
**Priority:** Low (blocked on external API key acquisition)

---

## Current State

### ✅ What's Configured

**File:** `/var/lib/nixos-ai-stack/optimizer/overrides.env`

```bash
REMOTE_LLM_URL=https://openrouter.ai/api
SWB_REMOTE_MODEL_ALIAS_FREE=google/gemini-flash-1.5-8b:free
SWB_REMOTE_MODEL_ALIAS_GEMINI=google/gemini-flash-1.5-8b:free
```

**Switchboard Service:**
- ✅ Loads overrides.env via EnvironmentFile
- ✅ Has OpenRouter URL configured
- ✅ Has model aliases configured
- ✅ Supports `openrouter/` prefix in model names

### ❌ What's Missing

**API Key:** `REMOTE_LLM_API_KEY_FILE=` (empty)

The switchboard environment shows the key file variable is empty, preventing actual API calls to OpenRouter.

---

## Resolution Required

### Option 1: Get OpenRouter API Key (Recommended)

1. Visit https://openrouter.ai/keys
2. Sign up with GitHub (free)
3. Create API key (format: `sk-or-v1-...`)
4. Store securely:
   ```bash
   mkdir -p ~/.config/openrouter
   echo "sk-or-v1-YOUR-KEY-HERE" > ~/.config/openrouter/api-key
   chmod 600 ~/.config/openrouter/api-key
   ```
5. Update overrides.env:
   ```bash
   echo 'REMOTE_LLM_API_KEY_FILE=/home/hyperd/.config/openrouter/api-key' >> /var/lib/nixos-ai-stack/optimizer/overrides.env
   ```
6. Restart switchboard:
   ```bash
   sudo systemctl restart ai-switchboard
   ```

### Option 2: Use Different Free Provider

Alternative free remote models that don't require API keys or have simpler setup.

---

## Historical Context

**Git History:**
- OpenRouter support added March 2026 (commits 27bc564, 0316fe0)
- Infrastructure exists for remote model routing
- Switchboard has `openrouter/` prefix support
- Model aliases configured but never activated with actual API key

**User Expectation:**
User believed OpenRouter was "wired into our system a while back" with "all the information and apis already stored locally."

**Reality:**
Infrastructure was implemented but API key acquisition/configuration was never completed.

---

## Impact

**Current:**
- Cannot delegate to free remote models via OpenRouter
- Workflow executor can only use local models or Anthropic API
- Remote model testing blocked

**When Resolved:**
- Access to free Gemini Flash 1.5 8B model
- Access to other free OpenRouter models (DeepSeek R1, Qwen QwQ, Llama 3.3 70B)
- Cost-free remote delegation for workflow execution

---

## Related Documentation

- [OpenRouter Free Setup Guide](../../docs/configuration/openrouter-free-setup.md)
- [Workflow Executor Security](../../docs/architecture/workflow-executor-security.md)
- [Switchboard Configuration](../../nix/modules/services/switchboard.nix)

---

**Next Action:** User to obtain OpenRouter API key when convenient, or continue with Anthropic API for remote execution.
