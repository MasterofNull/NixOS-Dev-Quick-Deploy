# Reasoning Profiles Implementation Summary

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-07

## Overview

This document summarizes the implementation of the **Reasoning Profiles** feature for the NixOS AI Stack. Reasoning profiles allow hot-reloadable, task-specific LLM behavior customization without modifying core prompts or code.

## Implementation Date

2024 (Phase 6+ enhancements)

## Changes Made

### 1. Core Configuration (`config.py`)

#### Added Functions

**`_load_reasoning_profiles() -> Dict[str, Dict[str, Any]]`**
- Loads reasoning profiles from `~/.local/share/nixos-ai-stack/reasoning-profiles.json`
- Falls back to built-in defaults if file not found or invalid
- Provides 4 default profiles: `default`, `precise`, `creative`, `deep-reasoning`
- Returns dictionary mapping profile names to configuration objects

#### Modified Class: `Config`

**New Class Variable:**
```python
REASONING_PROFILES: Dict[str, Dict[str, Any]] = _load_reasoning_profiles()
```

**New Class Methods:**

1. **`get_reasoning_profile(profile_name: str = "default") -> Dict[str, Any]`**
   - Retrieves a reasoning profile by name
   - Raises `ValueError` if profile not found
   - Returns profile configuration with:
     - `name`: Profile identifier
     - `description`: Human-readable purpose
     - `temperature`: Sampling temperature (0.0-2.0)
     - `max_tokens`: Maximum tokens to generate
     - `top_p`: Nucleus sampling parameter
     - `stop_sequences`: List of generation stop markers
     - `system_suffix`: Optional additional system prompt text

2. **`reload_reasoning_profiles() -> None`**
   - Hot-reloads profiles from configuration file
   - Allows updating profiles without restarting server
   - Logs reload operation

### 2. Workflow Executor (`workflow_executor.py`)

#### Modified Method: `_execute_with_llm()`

Enhanced LLM execution to support reasoning profiles:

1. **Profile Loading**
   - Reads `reasoning_profile` from session metadata
   - Defaults to "default" if not specified
   - Loads profile via `Config.get_reasoning_profile()`

2. **Parameter Application**
   - Extracts `temperature` from profile
   - Extracts `max_tokens` from profile
   - Respects budget token limits (uses minimum of profile and budget)
   - Appends `system_suffix` to system prompt if present

3. **Error Handling**
   - Falls back to safe defaults if profile loading fails
   - Logs warnings for missing or invalid profiles

4. **LLM Call Enhancement**
   - Passes `temperature` parameter to `llm_client.create_message()`
   - Uses profile-specific `max_tokens`
   - Augments system prompt with profile suffix

### 3. Configuration Files

#### `ai-stack/mcp-servers/shared/config/reasoning-profiles.json`

Created example configuration with 8 pre-defined profiles:

1. **default** - General purpose, balanced (temp: 0.7, tokens: 4K)
2. **precise** - Deterministic outputs (temp: 0.1, tokens: 2K)
3. **creative** - High creativity (temp: 1.0, tokens: 8K)
4. **deep-reasoning** - Extended chain-of-thought (temp: 0.3, tokens: 16K)
5. **fast-response** - Quick iteration (temp: 0.5, tokens: 1K)
6. **code-generation** - Code writing (temp: 0.2, tokens: 4K)
7. **problem-solving** - Systematic decomposition (temp: 0.4, tokens: 8K)
8. **code-review** - Critical analysis (temp: 0.3, tokens: 4K)

Each profile includes:
- Temperature, max_tokens, top_p, stop_sequences
- Human-readable description
- Optional system_suffix for task-specific prompting

### 4. Documentation

#### `docs/features/reasoning-profiles.md`

Comprehensive documentation covering:
- Profile structure and field definitions
- Built-in profile descriptions and use cases
- Usage examples in workflow sessions
- Profile selection guidelines
- Customization instructions
- Hot-reload functionality
- Temperature range guidelines
- Best practices
- Monitoring and debugging
- Future enhancement ideas

### 5. Testing

#### `ai-stack/mcp-servers/hybrid-coordinator/test_reasoning_profiles.py`

Test suite validating:
- Default profile loading
- Profile retrieval by name
- Error handling for missing profiles
- Profile structure validation
- Temperature range validation
- Example config file validity

**Test Results:** ✓ All tests passed

## Usage Example

### Creating a Session with a Reasoning Profile

```python
session = await workflow_planner.create_session(
    objective="Refactor authentication module for improved security",
    safety_mode="plan-readonly",
    reasoning_profile="code-review",  # Use code-review profile
    budget={"token_limit": 5000}
)
```

### Profile Selection by Task Type

| Task | Profile | Rationale |
|------|---------|-----------|
| Writing code | `code-generation` | Low temp, best practices |
| Debugging | `problem-solving` | Systematic analysis |
| Code review | `code-review` | Critical evaluation |
| Design | `deep-reasoning` | Extended thinking |
| Quick queries | `fast-response` | Low latency |

## API Integration Points

### Session Creation

The `reasoning_profile` parameter is now accepted in:
- `WorkflowPlanner.create_session()`
- Session metadata dictionary

### LLM Client

Enhanced `llm_client.create_message()` call:
- Added `temperature` parameter
- Respects profile `max_tokens`
- Augmented system prompt with profile suffix

### Configuration Access

External code can access profiles via:
```python
from config import Config

# Get profile
profile = Config.get_reasoning_profile("deep-reasoning")

# Hot-reload profiles
Config.reload_reasoning_profiles()
```

## File Locations

```
ai-stack/mcp-servers/
├── hybrid-coordinator/
│   ├── config.py                          # Modified: Added profile loading
│   ├── workflow_executor.py               # Modified: Profile integration
│   └── test_reasoning_profiles.py         # New: Test suite
├── shared/
│   └── config/
│       └── reasoning-profiles.json        # New: Example profiles
└── docs/
    └── features/
        ├── reasoning-profiles.md          # New: User documentation
        └── reasoning-profiles-implementation-summary.md  # This file
```

## Backwards Compatibility

✓ **Fully backwards compatible**

- If `reasoning_profile` not specified, defaults to "default" profile
- Default profile uses balanced settings (temp: 0.7, tokens: 4K)
- Existing sessions continue to work without modification
- Profile loading failures fall back to safe defaults

## Performance Considerations

### Startup Impact
- Minimal: Profile loading happens once at import time
- Falls back to built-in defaults if file I/O slow

### Runtime Impact
- Negligible: Profile lookup is O(1) dictionary access
- No additional API calls
- System suffix appending is simple string concatenation

### Token Usage Impact
- Profiles can optimize token usage via `max_tokens` settings
- `fast-response` profile reduces tokens by 75%
- Budget limits still enforced (minimum of profile and budget)

## Security Considerations

### Configuration File
- User-writable at `~/.local/share/nixos-ai-stack/`
- JSON format with schema validation
- Invalid profiles logged as warnings
- No code execution from configuration

### System Prompts
- `system_suffix` appended to existing prompts
- No prompt injection risk (user controls their own config)
- Profiles cannot disable safety mechanisms

## Future Enhancements

Potential additions:
1. **Dynamic Selection** - Auto-select profile based on task classification
2. **Profile Inheritance** - Compose profiles from base templates
3. **Per-Tool Overrides** - Different profiles for different tool types
4. **Analytics** - Track profile performance and token efficiency
5. **A/B Testing** - Compare profiles for specific task categories
6. **Recommendations** - Suggest optimal profiles based on objective
7. **Web UI** - Visual profile editor and manager

## Testing Coverage

✓ Profile loading from file
✓ Profile loading with fallback to defaults
✓ Profile retrieval by name
✓ Invalid profile error handling
✓ Profile structure validation
✓ Temperature range validation
✓ Example config file validation
✓ Hot-reload functionality (manual verification)

## Known Limitations

1. **No Validation of system_suffix** - User-provided suffixes could theoretically conflict with base prompts
2. **No Profile Versioning** - No migration path for profile format changes
3. **No Profile Dependencies** - Cannot reference other profiles
4. **Single Config File** - All profiles in one file (could be split for organization)

## Migration Guide

### For Users

No migration needed. Feature is opt-in:
- Existing sessions work unchanged
- Add `reasoning_profile` parameter to customize behavior

### For Developers

To integrate reasoning profiles in new features:

```python
# 1. Accept profile name in your API
def your_function(task: str, reasoning_profile: str = "default"):
    # 2. Load profile
    from config import Config
    profile = Config.get_reasoning_profile(reasoning_profile)
    
    # 3. Apply profile settings
    temperature = profile["temperature"]
    max_tokens = profile["max_tokens"]
    
    # 4. Augment prompts if needed
    system_suffix = profile.get("system_suffix", "")
```

## Validation

### Syntax Validation
```bash
python3 -m py_compile config.py workflow_executor.py
```
✓ No syntax errors

### Test Execution
```bash
AI_STRICT_ENV=false python3 test_reasoning_profiles.py
```
✓ All tests passed

### JSON Validation
```bash
python3 -m json.tool reasoning-profiles.json
```
✓ Valid JSON

## Rollback Plan

If issues arise:
1. Remove `reasoning_profile` parameter from session calls
2. Revert changes to `workflow_executor.py` (_execute_with_llm method)
3. Revert changes to `config.py` (remove profile methods)
4. No data migration needed (feature is stateless)

## Success Metrics

To measure feature adoption and effectiveness:
- **Adoption Rate**: % of sessions using non-default profiles
- **Token Efficiency**: Average tokens per task by profile
- **Task Success Rate**: Completion rates by profile type
- **User Satisfaction**: Survey results on profile utility

## Conclusion

The Reasoning Profiles feature provides a flexible, hot-reloadable mechanism for tailoring LLM behavior to specific task types. The implementation:
- ✓ Is fully backwards compatible
- ✓ Requires no database changes
- ✓ Is well-tested and documented
- ✓ Enables fine-grained control without code changes
- ✓ Supports hot-reloading for rapid iteration

The feature is production-ready and can be deployed immediately.
