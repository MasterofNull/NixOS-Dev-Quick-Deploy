# Reasoning Profiles

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-07

## Overview

Reasoning profiles provide hot-reloadable configurations for tailoring LLM behavior to different task types. Each profile defines temperature, token limits, sampling parameters, and optional system prompt augmentations.

## Configuration

### Default Location

Profiles are loaded from:
```
~/.local/share/nixos-ai-stack/reasoning-profiles.json
```

### Built-in Profiles

The system includes these default profiles:

#### `default`
- **Description**: General purpose reasoning with balanced creativity and precision
- **Temperature**: 0.7
- **Max Tokens**: 4096
- **Use Case**: Standard queries and general tasks

#### `precise`
- **Description**: High precision deterministic outputs
- **Temperature**: 0.1
- **Max Tokens**: 2048
- **Use Case**: Code generation, structured data, technical documentation

#### `creative`
- **Description**: Creative exploration and ideation
- **Temperature**: 1.0
- **Max Tokens**: 8192
- **Use Case**: Brainstorming, creative writing, generating alternatives

#### `deep-reasoning`
- **Description**: Extended reasoning with chain-of-thought
- **Temperature**: 0.3
- **Max Tokens**: 16384
- **Use Case**: Complex problem-solving, mathematical reasoning, multi-step analysis
- **System Suffix**: Instructs model to show step-by-step reasoning

#### `fast-response`
- **Description**: Quick responses with lower token limits
- **Temperature**: 0.5
- **Max Tokens**: 1024
- **Use Case**: Rapid iteration, quick answers, status checks

#### `code-generation`
- **Description**: Optimized for code generation
- **Temperature**: 0.2
- **Max Tokens**: 4096
- **Use Case**: Writing new code, implementing features
- **System Suffix**: Emphasizes best practices and error handling

#### `problem-solving`
- **Description**: Systematic problem decomposition
- **Temperature**: 0.4
- **Max Tokens**: 8192
- **Use Case**: Debugging, system design, architecture decisions
- **System Suffix**: Encourages breaking down complex problems

#### `code-review`
- **Description**: Critical analysis for code review
- **Temperature**: 0.3
- **Max Tokens**: 4096
- **Use Case**: PR reviews, code quality assessment
- **System Suffix**: Focuses on quality dimensions and actionable feedback

## Profile Structure

Each profile is a JSON object with these fields:

```json
{
  "profile-name": {
    "name": "profile-name",
    "description": "Human-readable description",
    "temperature": 0.7,
    "max_tokens": 4096,
    "top_p": 0.9,
    "stop_sequences": [],
    "system_suffix": "Optional additional system prompt text"
  }
}
```

### Field Definitions

- **name**: Unique identifier for the profile
- **description**: Human-readable explanation of profile purpose
- **temperature**: Sampling temperature (0.0 = deterministic, 2.0 = very random)
- **max_tokens**: Maximum tokens to generate
- **top_p**: Nucleus sampling parameter (typically 0.8-0.95)
- **stop_sequences**: Array of strings that stop generation
- **system_suffix**: *(Optional)* Additional text appended to system prompt

## Usage

### In Workflow Sessions

Specify the profile when creating a workflow session:

```python
session = await workflow_planner.create_session(
    objective="Analyze and refactor authentication module",
    safety_mode="plan-readonly",
    reasoning_profile="code-review"  # Use code-review profile
)
```

### Profile Selection Guidelines

| Task Type | Recommended Profile | Rationale |
|-----------|-------------------|-----------|
| Writing new code | `code-generation` | Low temperature, best practices prompting |
| Debugging | `problem-solving` | Systematic analysis, edge case consideration |
| Code review | `code-review` | Critical analysis, quality focus |
| Architecture design | `deep-reasoning` | Extended reasoning, step-by-step thinking |
| Quick queries | `fast-response` | Fast turnaround, lower token usage |
| Brainstorming | `creative` | High temperature, exploration |
| Documentation | `precise` | Deterministic, accurate outputs |
| General tasks | `default` | Balanced approach |

## Customization

### Creating Custom Profiles

1. Copy the example file:
```bash
mkdir -p ~/.local/share/nixos-ai-stack
cp ai-stack/mcp-servers/shared/config/reasoning-profiles.json \
   ~/.local/share/nixos-ai-stack/reasoning-profiles.json
```

2. Edit the file to add or modify profiles:
```json
{
  "my-custom-profile": {
    "name": "my-custom-profile",
    "description": "Custom profile for my specific use case",
    "temperature": 0.6,
    "max_tokens": 6000,
    "top_p": 0.88,
    "stop_sequences": ["STOP", "END"],
    "system_suffix": "Additional instructions for this profile"
  }
}
```

3. The profiles are loaded at startup and can be hot-reloaded without restart

### Hot Reloading

To reload profiles after editing the configuration file:

```python
from config import Config
Config.reload_reasoning_profiles()
```

## Implementation Details

### Profile Loading

Profiles are loaded via `_load_reasoning_profiles()` in `config.py`:
- Reads from `~/.local/share/nixos-ai-stack/reasoning-profiles.json`
- Falls back to built-in defaults if file missing or invalid
- Validates required fields and provides defaults

### Integration with Workflow Executor

The `_execute_with_llm()` method in `workflow_executor.py`:
1. Reads `reasoning_profile` from session metadata
2. Loads profile configuration via `Config.get_reasoning_profile()`
3. Applies temperature and max_tokens to LLM call
4. Appends system_suffix to system prompt if present
5. Respects budget token limits (uses minimum of profile and budget)

### Error Handling

- **Missing profile**: Falls back to "default" profile
- **Invalid file**: Uses built-in defaults
- **Missing fields**: Populated with sensible defaults

## Temperature Guidelines

| Range | Behavior | Use Cases |
|-------|----------|-----------|
| 0.0-0.2 | Highly deterministic | Code, math, structured output |
| 0.3-0.5 | Focused but flexible | Analysis, documentation |
| 0.6-0.8 | Balanced creativity | General tasks, conversation |
| 0.9-1.2 | Creative exploration | Brainstorming, alternatives |
| 1.3+ | Highly random | Experimental, artistic |

## Best Practices

1. **Profile Selection**: Choose profiles based on task requirements, not preferences
2. **Token Budgets**: Set appropriate max_tokens to balance quality and cost
3. **System Suffixes**: Use to add task-specific instructions without changing base prompts
4. **Stop Sequences**: Define clear boundaries for multi-part responses
5. **Testing**: Validate custom profiles with representative tasks
6. **Documentation**: Document custom profiles for team consistency

## Examples

### Example 1: Deep Analysis Task

```python
session = await workflow_planner.create_session(
    objective="Analyze the security implications of the new authentication flow",
    safety_mode="plan-readonly",
    reasoning_profile="deep-reasoning",
    budget={"token_limit": 20000}
)
```

The `deep-reasoning` profile will:
- Use low temperature (0.3) for focused analysis
- Allow extended output (16K tokens max)
- Add chain-of-thought prompting via system_suffix

### Example 2: Quick Code Generation

```python
session = await workflow_planner.create_session(
    objective="Generate a simple REST API endpoint for user registration",
    safety_mode="plan-execute",
    reasoning_profile="code-generation",
    budget={"token_limit": 4000}
)
```

The `code-generation` profile will:
- Use very low temperature (0.2) for deterministic code
- Include best practices prompting
- Stop at logical code boundaries

### Example 3: Brainstorming Session

```python
session = await workflow_planner.create_session(
    objective="Generate 10 alternative approaches for caching strategy",
    safety_mode="plan-readonly",
    reasoning_profile="creative",
    budget={"token_limit": 8000}
)
```

The `creative` profile will:
- Use high temperature (1.0) for diverse ideas
- Allow longer responses (8K tokens)
- Generate varied alternatives

## Monitoring and Debugging

### Logging

The system logs profile usage:
```
DEBUG: Using reasoning profile: deep-reasoning - Extended reasoning with chain-of-thought
DEBUG: Calling LLM for objective: Analyze security...
```

### Session Metadata

Profile name is stored in session trajectory:
```python
{
    "reasoning_profile": "deep-reasoning",
    "trajectory": [
        {
            "event_type": "llm_response",
            "model": "deepseek-r1:8b",
            "temperature": 0.3,
            "tokens": 1234
        }
    ]
}
```

## Future Enhancements

Potential future additions:
- Dynamic profile selection based on task classification
- Profile inheritance and composition
- Per-tool profile overrides
- Profile performance analytics
- A/B testing between profiles
- Profile recommendation engine

## Related Documentation

- [Workflow Executor Architecture](../architecture/workflow-executor-integration.md)
