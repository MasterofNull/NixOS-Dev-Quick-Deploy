---
Status: active
Owner: system
Updated: 2026-04-09
---

# OpenRouter Free Models Setup

**Purpose:** Configure free remote models via OpenRouter for switchboard and workflow-adjacent testing

---

## Quick Setup

### 1. Get OpenRouter API Key (Free)

```bash
# Visit: https://openrouter.ai/keys
# Sign up with GitHub (free)
# Create API key (starts with "sk-or-v1-...")
```

### 2. Configure in NixOS

**Option A: Environment Override (Quick Test)**

```bash
# Add to /var/lib/nixos-ai-stack/optimizer/overrides.env
echo 'REMOTE_LLM_URL=https://openrouter.ai/api' >> /var/lib/nixos-ai-stack/optimizer/overrides.env
echo 'REMOTE_LLM_API_KEY_FILE=/home/hyperd/.config/openrouter/api-key' >> /var/lib/nixos-ai-stack/optimizer/overrides.env
echo 'SWB_REMOTE_MODEL_ALIAS_FREE=openrouter/auto' >> /var/lib/nixos-ai-stack/optimizer/overrides.env

# Store API key securely
mkdir -p ~/.config/openrouter
echo "sk-or-v1-YOUR-KEY-HERE" > ~/.config/openrouter/api-key
chmod 600 ~/.config/openrouter/api-key

# Restart switchboard
sudo systemctl restart ai-switchboard
```

**Option B: NixOS Configuration (Production)**

Edit `nix/hosts/hyperd/configuration.nix` or `deploy-options.local.nix`:

```nix
{
  mySystem.aiStack.switchboard = {
    enable = true;
    remoteUrl = "https://openrouter.ai/api";
    remoteApiKeyFile = "/run/secrets/remote_llm_api_key";
    remoteModelAliases = {
      enable = true;
      free = "openrouter/auto";
      gemini = "google/gemini-flash-1.5-8b";
      coding = "qwen/qwq-32b-preview";
      reasoning = "deepseek/deepseek-r1-distill-qwen-32b";
    };
  };
}
```

Then add to sops secrets:

```bash
sops /etc/nixos/secrets/secrets.sops.yaml
# Add: remote_llm_api_key: sk-or-v1-YOUR-KEY-HERE

sudo nixos-rebuild switch
```

---

## Test Free Model Access

### Via Switchboard

```bash
# Test remote-free model
curl -s http://127.0.0.1:8085/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "remote-free",
    "messages": [{"role": "user", "content": "Say hello"}],
    "max_tokens": 50
  }' | jq '.choices[0].message.content'
```

Expected: a non-empty assistant response in `.choices[0].message.content`

---

## Model Selection Notes

| Model | ID | Speed | Quality |
|-------|----|----|--------|
| **Auto Router** | `openrouter/auto` | Fast | Good |
| **Gemini Flash** | `google/gemini-flash-1.5-8b` | Very Fast | Good |
| **DeepSeek R1** | `deepseek/deepseek-r1-distill-qwen-32b` | Medium | Excellent |
| **Qwen QwQ** | `qwen/qwq-32b-preview` | Medium | Excellent |
| **Llama 3.3 70B** | `meta-llama/llama-3.3-70b-instruct` | Fast | Very Good |

**Important:** OpenRouter's free model catalog changes over time. Treat the
table above as examples, not a guaranteed free list. Verify current free-tier
availability in the OpenRouter model catalog before pinning a model in Nix or
`overrides.env`.

For the most stable setup in this repo:
- use `openrouter/auto` for `remoteModelAliases.free` when you want a generic
  free/budget lane;
- pin `coding`, `reasoning`, or `gemini` aliases only after confirming the
  model is still available and acceptable for your quota.

---

## Workflow Executor Caveat

The examples above are valid for **switchboard testing**. They are **not**
currently sufficient to route `workflow_executor.py` through switchboard, for
two repo-specific reasons:

1. `ai-stack/mcp-servers/hybrid-coordinator/llm_client.py` accepts a
   `base_url` parameter but does not currently pass it to `AsyncAnthropic()`.
2. `python3 -m ai-stack.mcp-servers...` is not a valid Python module path in
   this repo because of the hyphenated top-level directory name.

If you want to run the executor directly today, use the file path:

```bash
python3 ai-stack/mcp-servers/hybrid-coordinator/workflow_executor.py
```

If you want the executor to use OpenRouter or switchboard, patch
`llm_client.py` first so the chosen client actually honors a configurable base
URL.

---

## Troubleshooting

### "No API key found"

```bash
# Check switchboard config
systemctl status ai-switchboard
curl http://127.0.0.1:8085/v1/models | jq '.data[].id' | grep remote
```

### "Connection refused"

```bash
# Restart switchboard
sudo systemctl restart ai-switchboard

# Check logs
journalctl -u ai-switchboard -f
```

### "Rate limit exceeded"

OpenRouter free tier has limits. Switch models:
```bash
# Use different free model
curl http://127.0.0.1:8085/v1/chat/completions \
  -d '{"model": "google/gemini-flash-1.5-8b", ...}'
```

---

## Next Steps

1. Get OpenRouter API key: https://openrouter.ai/keys
2. Configure via overrides.env (quick) or NixOS config (production)
3. Test with curl
4. Update workflow executor to use switchboard
5. Delegate tasks to remote-free model!
