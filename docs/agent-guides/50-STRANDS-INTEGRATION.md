# Strands-Agents Pattern Integration

This guide documents the integration of [strands-agents](https://github.com/orgs/strands-agents/repositories) patterns into the local AI harness.

## Overview

The integration brings strands-agents' model-driven agent development patterns to the NixOS-Dev-Quick-Deploy AI harness, providing:

- **`.agents/` Directory Structure** - Organized workflow artifact management
- **Tool Decorators** - Simplified tool creation with `@tool`
- **SOP Workflows** - RFC 2119 constraint-based procedures
- **Unified Agent Interface** - Simple, callable agent pattern
- **DAG Workflows** - Graph-based workflow orchestration

## Components

### 1. `.agents/` Directory Structure

Strands-style directory for workflow artifacts:

```
.agents/
├── summary/      # Final documentation (always commit)
├── planning/     # Design decisions (often commit)
├── tasks/        # Task tracking (optionally commit)
└── scratchpad/   # Temporary files (never commit - .gitignore)
```

**Usage:**

```python
from mcp_client import get_mcp_client

client = get_mcp_client()

# Write artifact
path = client.write_artifact(
    "summary",
    "analysis-report.md",
    "# Analysis Report\n\nFindings..."
)

# Read artifact
content = client.read_artifact("summary", "analysis-report.md")

# List artifacts
artifacts = client.list_artifacts("summary", "*.md")
```

**Documentation:** [.agents/README.md](../../.agents/README.md)

### 2. Tool Decorator System

Automatic schema generation from Python type hints:

**Basic Tool:**

```python
from tool_decorators import tool

@tool
def text_analyzer(text: str, case_sensitive: bool = False) -> dict:
    """
    Analyze text and return statistics.
    
    Counts words, characters, and lines in the provided text.
    """
    words = text.split() if case_sensitive else text.lower().split()
    
    return {
        "word_count": len(words),
        "char_count": len(text),
        "unique_words": len(set(words)),
    }
```

**With Custom Name:**

```python
@tool(name="validate_file", provider="qa", category="validation")
def file_validator(filepath: str, strict: bool = False) -> dict:
    """Validate file structure and format."""
    # Implementation
    pass
```

**Provider-Based:**

```python
from tool_decorators import ToolProvider

class FileToolsProvider(ToolProvider):
    def __init__(self):
        super().__init__("file_tools")
        self.register_tool(self.read_file)
        self.register_tool(self.write_file)
    
    def read_file(self, path: str) -> str:
        """Read file contents."""
        return Path(path).read_text()
```

**Documentation:** [ai-stack/local-orchestrator/TOOL_DECORATORS.md](../../ai-stack/local-orchestrator/TOOL_DECORATORS.md)

### 3. SOP (Standard Operating Procedure) Workflows

Markdown-based workflows with RFC 2119 constraints:

**SOP Example:**

```markdown
---
name: Code Review SOP
version: 1.0.0
---

# Code Review Procedure

## Prerequisites

1. MUST have read access to repository
2. SHOULD have linting tools configured
3. MAY use automated review tools

## Review Process

1. MUST check code style and formatting
2. MUST verify test coverage
3. SHOULD validate security practices
4. MAY suggest performance improvements
```

**Parsing SOP:**

```python
from sop_engine import parse_sop

sop = parse_sop(Path("sop-templates/code-review.sop.md"))

print(f"Required steps: {len(sop.get_required_steps())}")
print(f"Optional steps: {len(sop.get_optional_steps())}")
```

**Executing SOP:**

```python
from sop_engine import execute_sop

result = execute_sop(sop, context={"repo": "."})

print(f"Status: {result['status']}")
print(f"Completed: {result['completed_steps']}/{result['total_steps']}")
```

**Available via MCP:**
- `list_sops` - List available SOPs
- `parse_sop` - Parse SOP structure
- `execute_sop` - Execute SOP workflow

**Templates:** [ai-stack/sop-templates/](../../ai-stack/sop-templates/)

### 4. Unified Agent Interface

Simple, callable agent pattern:

**Basic Usage:**

```python
from agent_interface import LocalAgent

# Create agent
agent = LocalAgent()

# Simple query
response = agent("What is NixOS?")
print(response.content)

# Conversational
agent.add_message("user", "I'm working on a NixOS deployment")
response = agent("What's the best way to manage secrets?")
```

**With Tools:**

```python
from agent_interface import LocalAgent
from example_tools import text_analyzer

# Create agent with tools
agent = LocalAgent.with_tools(text_analyzer)

# Use tools implicitly through conversation
response = agent("Analyze this text: Hello World")
```

**Workflow Agent:**

```python
# Agent configured for workflow orchestration
agent = LocalAgent.for_workflow()

# Uses hybrid coordinator for planning
response = agent("Create deployment plan for staging environment")
```

**Model Providers:**

```python
from agent_interface import ModelProvider

# Local llama-cpp
agent = LocalAgent(provider=ModelProvider.LOCAL_LLAMA)

# Hybrid coordinator
agent = LocalAgent(provider=ModelProvider.HYBRID)

# Future: OpenRouter, custom providers
```

### 5. DAG Workflow Orchestration

Graph-based workflow for complex multi-step tasks:

**Creating Workflow:**

```python
from workflow_graph import create_workflow, NodeType

workflow = create_workflow("deployment-workflow")

# Add nodes with dependencies
workflow.add_node("validate", "Validate Config")
workflow.add_node("build", "Build Artifacts", dependencies=["validate"])
workflow.add_node("test", "Run Tests", dependencies=["build"])
workflow.add_node("deploy", "Deploy", dependencies=["test"])
```

**Parallel Execution:**

```python
# Diamond pattern - parallel tasks
workflow.add_node("init", "Initialize")
workflow.add_node("task1", "Task 1", dependencies=["init"])
workflow.add_node("task2", "Task 2", dependencies=["init"])  # Parallel with task1
workflow.add_node("finish", "Finish", dependencies=["task1", "task2"])

# Detect parallel groups
parallel_groups = workflow.get_parallel_groups()
# [[init], [task1, task2], [finish]]
```

**Decision Nodes:**

```python
def check_tests_passed(ctx):
    return ctx.get("test_results", {}).get("passed", 0) > 0

workflow.add_node(
    "decision",
    "Check Test Results",
    NodeType.DECISION,
    condition=check_tests_passed,
    dependencies=["test"]
)
```

**Execution:**

```python
from workflow_graph import execute_workflow

# Sequential
result = execute_workflow(workflow, parallel=False)

# Parallel (where possible)
result = execute_workflow(workflow, parallel=True)

print(f"Status: {result['status']}")
print(f"Completed: {result['completed']}/{result['total_nodes']}")
```

**Visualization:**

```python
# Export to Mermaid diagram
mermaid = workflow.to_mermaid()
print(mermaid)
# graph TD
#     validate[Validate Config]
#     build[Build Artifacts]
#     validate --> build
#     ...
```

## Integration Patterns

### Pattern 1: SOP → Agent → Artifacts

```python
from sop_engine import parse_sop, execute_sop
from agent_interface import LocalAgent
from mcp_client import get_mcp_client

# Parse SOP
sop = parse_sop(Path("sop-templates/codebase-analysis.sop.md"))

# Execute with agent
agent = LocalAgent.for_workflow()
result = execute_sop(sop, context={"target": "."})

# Store results
client = get_mcp_client()
client.write_artifact(
    "summary",
    f"analysis-{datetime.now().isoformat()}.md",
    f"# Analysis Results\n\n{result}"
)
```

### Pattern 2: Tools → Graph → Execution

```python
from tool_decorators import tool
from workflow_graph import create_workflow, execute_workflow

# Define tools
@tool
def analyze_code(filepath: str) -> dict:
    """Analyze code file."""
    return {"complexity": "low", "issues": []}

@tool
def run_tests(suite: str) -> dict:
    """Run test suite."""
    return {"passed": 10, "failed": 0}

# Build workflow
workflow = create_workflow("qa-workflow")
workflow.add_node("analyze", "Analyze", task=lambda ctx: analyze_code("main.py"))
workflow.add_node("test", "Test", task=lambda ctx: run_tests("unit"), dependencies=["analyze"])

# Execute
result = execute_workflow(workflow)
```

### Pattern 3: Complete Pipeline

```python
# 1. Parse SOP for structure
sop = parse_sop(Path("deployment-check.sop.md"))

# 2. Create agent with tools
agent = LocalAgent.with_tools(validate_config, run_tests, deploy)

# 3. Build workflow from SOP steps
workflow = create_workflow("deployment")
for section in sop.sections:
    for step in section.steps:
        workflow.add_node(
            f"step_{step.number}",
            step.title,
            task=lambda ctx: agent.chat(step.title)
        )

# 4. Execute workflow
result = execute_workflow(workflow, parallel=True)

# 5. Store artifacts
client = get_mcp_client()
client.write_artifact("summary", "deployment-report.md", str(result))
```

## Migration from Manual Patterns

### Before (Manual Tool Registration):

```python
TOOLS = [{
    "name": "my_tool",
    "description": "Does something",
    "inputSchema": {
        "type": "object",
        "properties": {
            "param1": {"type": "string"},
        },
        "required": ["param1"],
    },
}]

def my_tool(param1: str):
    return f"Processed: {param1}"
```

### After (Decorator Pattern):

```python
@tool
def my_tool(param1: str) -> str:
    """Does something."""
    return f"Processed: {param1}"
```

## Best Practices

1. **Use Type Hints**: Always provide type annotations for accurate schema generation
2. **Write Clear Docstrings**: First line becomes the tool/node description
3. **Organize with Providers**: Group related tools into providers
4. **Leverage SOPs**: Use SOPs for repeatable, structured procedures
5. **Artifact Management**: Store important results in `.agents/summary/`
6. **Workflow Graphs**: Use for complex multi-step processes with dependencies
7. **Agent Interface**: Use for conversational interactions and tool coordination

## Testing

Run integration tests:

```bash
python3 ai-stack/local-orchestrator/test_strands_integration.py
```

Individual component tests:
- `test_agent_interface.py` - Agent interface tests
- `test_workflow_graph.py` - DAG workflow tests
- `test_sop_engine.py` - SOP parsing and execution tests
- `example_tools.py` - Tool decorator examples

## Further Reading

- [Strands-Agents SDK](https://github.com/strands-agents/sdk-python) - Original inspiration
- [Strands Agent-SOP](https://github.com/strands-agents/agent-sop) - SOP workflow pattern
- [Strands Tools](https://github.com/strands-agents/tools) - Tool architecture patterns
- [CLAUDE.md](../../CLAUDE.md) - Project-specific agent guidance
- [AGENTS.md](../AGENTS.md) - Full agent policy documentation
