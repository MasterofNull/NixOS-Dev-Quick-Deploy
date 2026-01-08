# AI Model Modular System - Quick Start Guide

**Version**: 1.0
**Created**: 2025-11-20
**For**: Easy AI model experimentation and swapping

---

## TL;DR - Get Started in 30 Seconds

```bash
# 1. Set up the model manager (one-time)
ln -s ~/Documents/NixOS-Dev-Quick-Deploy/scripts/ai-model-manager.sh ~/.local/bin/amm
chmod +x ~/.local/bin/amm

# 2. List available models
amm list

# 3. Switch to a model (example)
amm switch tgi-primary coding/deepseek-coder

# 4. Check status
amm status
```

That's it! You now have a modular AI model system.

---

## What This System Does

**Problem Solved**: Switching AI models traditionally requires:
- Editing configuration files
- Rebuilding containers
- Restarting services manually
- Keeping track of model parameters

**Solution**: This modular system lets you:
- Switch models with one command
- Run multiple models simultaneously
- Track experiments
- Share configurations easily

---

## Installation

### Step 1: Create Symlink

```bash
# Create convenient alias
ln -s ~/Documents/NixOS-Dev-Quick-Deploy/scripts/ai-model-manager.sh ~/.local/bin/amm
chmod +x ~/.local/bin/amm

# Or add to PATH
export PATH="$PATH:~/Documents/NixOS-Dev-Quick-Deploy/scripts"
```

### Step 2: Verify Installation

```bash
amm version
amm list
```

You should see the available model profiles.

---

## Basic Usage

### List Available Models

```bash
# List all models
amm list

# List by category
amm list coding
amm list chat
amm list reasoning

# Search for specific models
amm list all deepseek
amm list coding llama
```

### Check Current Configuration

```bash
amm status
```

This shows:
- Which models are currently active
- Service status (running/stopped)
- Model details

### Switch Models

```bash
# Basic syntax
amm switch <service-name> <profile-path>

# Examples
amm switch tgi-primary coding/deepseek-coder
amm switch tgi-secondary coding/qwen-coder
amm switch ollama-default chat/phi4
```

**Service Names**:
- `tgi-primary` - Main TGI instance (port 8080)
- `tgi-secondary` - Secondary TGI instance (port 8085)
- `tgi-experimental` - Experimental instance (port 8090)
- `ollama-default` - Default Ollama model

### Get Model Information

```bash
# Show full profile details
amm info coding/deepseek-coder
amm info chat/phi4
```

---

## Available Models (Out of the Box)

### Coding Models

| Model | Size | Best For | Speed |
|-------|------|----------|-------|
| **deepseek-coder** | 7B | Code completion, FIM | Fast |
| **qwen-coder** | 7B | Multilingual, long context | Fast |
| **starcoder2** | 15B | Production code, 80+ languages | Medium |

### Chat Models

| Model | Size | Best For | Speed |
|-------|------|----------|-------|
| **llama3** | 3B | General chat, Q&A | Very Fast |
| **phi4** | 14B | Reasoning, technical topics | Medium |

### Reasoning Models

| Model | Size | Best For | Speed |
|-------|------|----------|-------|
| **deepseek-r1** | 7B | Complex problems, planning | Medium |

---

## Common Workflows

### Workflow 1: Quick Model Test

```bash
# Switch to a model
amm switch tgi-primary coding/deepseek-coder

# Test it (wait a moment for service to restart)
sleep 5
curl http://localhost:8080/health

# Try the model
curl http://localhost:8080/generate \
  -X POST \
  -d '{"inputs":"def fibonacci(n):", "parameters":{"max_new_tokens":100}}' \
  -H 'Content-Type: application/json'
```

### Workflow 2: Compare Two Models

```bash
# Run two models simultaneously
amm switch tgi-primary coding/deepseek-coder
amm switch tgi-secondary coding/starcoder2

# Now you have:
# - DeepSeek Coder on http://localhost:8080
# - StarCoder2 on http://localhost:8085

# Test both and compare results
```

### Workflow 3: Experiment Tracking

```bash
# Start an experiment
amm experiment start "Comparing code quality for Python tasks"

# Test Model 1
amm switch tgi-primary coding/deepseek-coder
# ... run your tests ...

# Test Model 2
amm switch tgi-primary coding/qwen-coder
# ... run your tests ...

# Results are logged in ~/.config/ai-models/experiments/
```

### Workflow 4: Create Custom Profile

```bash
# Create a custom model profile
amm create my-special-model \
  --runtime tgi \
  --model-id "myorg/my-model" \
  --description "My experimental model"

# Edit the profile
$EDITOR ~/.config/ai-models/custom/my-special-model.yaml

# Activate it
amm switch tgi-experimental custom/my-special-model
```

---

## Tips & Tricks

### Tip 1: Use Shell Aliases

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
# Quick model switching
alias amm-deepseek='amm switch tgi-primary coding/deepseek-coder'
alias amm-qwen='amm switch tgi-primary coding/qwen-coder'
alias amm-phi='amm switch ollama-default chat/phi4'

# Quick status check
alias amm-st='amm status'
```

### Tip 2: Check Service Logs

```bash
# TGI service logs
journalctl --user -u podman-tgi-primary.service -f

# Ollama logs
journalctl --user -u podman-local-ai-ollama.service -f
```

### Tip 3: Multiple Models for Different Tasks

```bash
# Coding on primary
amm switch tgi-primary coding/deepseek-coder

# Chat on secondary
amm switch tgi-secondary chat/phi4

# Reasoning on experimental
amm switch tgi-experimental reasoning/deepseek-r1

# Now you have:
# - localhost:8080 - DeepSeek Coder (coding tasks)
# - localhost:8085 - Phi-4 (chat/QA)
# - localhost:8090 - DeepSeek-R1 (reasoning)
```

### Tip 4: Fast Model Switching

```bash
# Create a script for your favorite setup
cat > ~/setup-my-models.sh <<'EOF'
#!/bin/bash
amm switch tgi-primary coding/deepseek-coder
amm switch tgi-secondary chat/phi4
amm status
EOF

chmod +x ~/setup-my-models.sh

# Run it anytime
~/setup-my-models.sh
```

---

## Troubleshooting

### Model Switch Doesn't Take Effect

```bash
# Manually restart the service
systemctl --user restart podman-tgi-primary.service

# Check if service exists
systemctl --user list-units 'podman-tgi-*'

# View logs for errors
journalctl --user -u podman-tgi-primary.service -n 50
```

### Service Won't Start

```bash
# Check if the model ID is correct
amm info coding/deepseek-coder

# Verify HuggingFace token (if needed)
cat ~/.config/huggingface/token

# Check disk space
df -h ~/.cache/huggingface

# Try with a smaller model first
amm switch tgi-primary chat/llama3
```

### Profile Not Found

```bash
# List all available profiles
amm list

# Check if file exists
ls -la ~/.config/ai-models/profiles/coding/

# Create it if needed
amm create my-model --runtime tgi
```

---

## Advanced Usage

### Custom Model from HuggingFace

```yaml
# ~/.config/ai-models/custom/my-hf-model.yaml
name: my-custom-model
description: My custom HuggingFace model
category: coding
version: "1.0"

source:
  type: huggingface
  model_id: myusername/my-model-name
  revision: main

container:
  runtime: tgi
  image: ghcr.io/huggingface/text-generation-inference:latest

parameters:
  max_input_length: 4096
  max_total_tokens: 8192
  quantization: bitsandbytes-nf4
  dtype: float16

resources:
  gpu_memory_min: 8GB
  cpu_cores: 4
  ram: 16GB

tags:
  - custom
  - experimental
```

Then:

```bash
amm switch tgi-experimental custom/my-hf-model
```

### Local Model Files

```yaml
# For locally downloaded models
source:
  type: local
  model_id: /path/to/model/directory
  revision: null

# Mount the model directory in home.nix
volumes:
  - /path/to/model:/data/model:ro
```

### Environment Variables

Model profiles support environment variable expansion:

```yaml
source:
  model_id: ${MY_MODEL_ID}

# Set before switching
export MY_MODEL_ID="deepseek-ai/deepseek-coder-7b"
amm switch tgi-primary coding/custom-model
```

---

## Integration with AIDB

### Python Integration Example

```python
# In your AIDB code
import yaml
from pathlib import Path

def get_active_model_config(service="tgi-primary"):
    """Get currently active model configuration"""
    config_path = Path.home() / ".config/ai-models/active" / f"{service}.yaml"

    with open(config_path) as f:
        return yaml.safe_load(f)

# Use it
config = get_active_model_config("tgi-primary")
model_name = config['name']
model_id = config['source']['model_id']
api_url = f"http://localhost:8080"  # Based on service

print(f"Using model: {model_name}")
print(f"Model ID: {model_id}")
print(f"API: {api_url}")
```

### Experiment Tracking

```python
import json
from datetime import datetime
from pathlib import Path

def log_experiment_result(model, task, metrics):
    """Log results to current experiment"""
    exp_dir = Path.home() / ".config/ai-models/experiments"
    active_file = exp_dir / ".active"

    if active_file.exists():
        exp_id = active_file.read_text().strip()
        exp_file = exp_dir / f"{exp_id}.json"

        with open(exp_file) as f:
            data = json.load(f)

        # Add result
        data['results'][model] = {
            'task': task,
            'metrics': metrics,
            'timestamp': datetime.now().isoformat()
        }

        with open(exp_file, 'w') as f:
            json.dump(data, f, indent=2)

# Usage
log_experiment_result(
    model="deepseek-coder-7b",
    task="code_generation",
    metrics={"pass@1": 0.73, "time_ms": 250}
)
```

---

## Next Steps

1. **Try the basic workflow**:
   ```bash
   amm list
   amm switch tgi-primary coding/deepseek-coder
   amm status
   ```

2. **Create your first custom profile**:
   ```bash
   amm create my-experiment --runtime tgi
   $EDITOR ~/.config/ai-models/custom/my-experiment.yaml
   ```

3. **Read the full documentation**:
   - [AI-MODEL-MODULAR-SYSTEM.md](AI-MODEL-MODULAR-SYSTEM.md) - Complete architecture
   - [SYSTEM-READY-FOR-AIDB.md](SYSTEM-READY-FOR-AIDB.md) - AIDB integration guide

4. **Integrate with your workflows**:
   - Add to your development scripts
   - Create experiment tracking
   - Share profiles with your team

---

## Summary

The modular AI model system provides:

✅ **Easy model switching** - One command to change models
✅ **Multiple simultaneous models** - Run different models on different ports
✅ **Experiment tracking** - Log and compare model performance
✅ **Profile sharing** - YAML configs are portable
✅ **AIDB ready** - Integrates seamlessly with AIDB

**Command to remember**: `amm`

That's your gateway to modular AI experimentation!

---

**Questions or Issues?**

- Check [AI-MODEL-MODULAR-SYSTEM.md](AI-MODEL-MODULAR-SYSTEM.md) for detailed documentation
- Report issues: https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy/issues
- Run `amm help` for command reference
