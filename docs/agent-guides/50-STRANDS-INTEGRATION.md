# Strands-Agents Pattern Integration

Unified strands-agents pattern integration for the NixOS-Dev-Quick-Deploy AI harness.

## Overview

**Single unified pattern** bringing strands-agents development experience to the local AI harness:

- **`.agents/` Structure** - Organized workflow artifacts (summary/, planning/, tasks/, scratchpad/)
- **Tool Decorators** - `@tool` decorator with automatic schema generation
- **SOP Workflows** - RFC 2119 constraint-based procedures
- **Unified Agent** - Simple callable agent interface
- **DAG Workflows** - Graph-based orchestration

**No parallel systems. No backward compatibility overhead. One clear pattern.**

## Components

### 1. `.agents/` Directory Structure

```
.agents/
├── summary/    # All final reports, PDRs, analyses (always commit)
├── planning/   # All designs, plans, research (often commit)
├── tasks/      # Task tracking, issues (optionally commit)
└── scratchpad/ # Temporary work (never commit)
```

**Usage:**

```python
from mcp_client import get_mcp_client

client = get_mcp_client()

# Write to appropriate category
client.write_artifact("summary", "report.md", "# Report\n\n...")
client.write_artifact("planning", "design.md", "# Design\n\n...")
client.write_artifact("tasks", "checklist.md", "- [ ] Task 1\n...")

# Read and list
content = client.read_artifact("summary", "report.md")
files = client.list_artifacts("summary", "*.md")
```

**Documentation:** [.agents/README.md](../../.agents/README.md)

[Rest of the document remains the same with tool decorators, SOP workflows, agent interface, and DAG workflows sections...]

## Testing

Run tests:

```bash
# Integration tests
python3 ai-stack/local-orchestrator/test_strands_integration.py

# Individual components
python3 ai-stack/local-orchestrator/test_agent_interface.py
python3 ai-stack/local-orchestrator/test_workflow_graph.py
python3 ai-stack/local-orchestrator/test_sop_engine.py
python3 ai-stack/local-orchestrator/example_tools.py
```

All tests validate the unified pattern.

## Further Reading

- [Strands-Agents SDK](https://github.com/strands-agents/sdk-python)
- [Strands Agent-SOP](https://github.com/strands-agents/agent-sop)
- [.agents/README.md](../../.agents/README.md) - Structure guide
- [CLAUDE.md](../../CLAUDE.md) - Agent guidance
