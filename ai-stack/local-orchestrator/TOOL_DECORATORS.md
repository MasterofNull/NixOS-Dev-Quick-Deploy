# Tool Decorators - Strands-Style Tool Registration

This module provides a strands-agents-inspired `@tool` decorator system for simplified tool creation with automatic schema generation.

## Features

- **Automatic Schema Generation**: JSON Schema generated from Python type hints
- **Docstring Parsing**: Tool descriptions extracted from function docstrings
- **Hot-Reloading**: Dynamic tool registration and unregistration
- **Provider-Based Organization**: Group related tools into providers
- **Type-Safe**: Leverages Python type annotations for parameter validation

## Quick Start

### Basic Tool

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

### Custom Tool Name and Metadata

```python
@tool(name="custom_validator", provider="qa", category="validation")
def validate_file(filepath: str, strict: bool = False) -> dict:
    """Validate file structure and format."""
    # Implementation
    pass
```

### Provider-Based Registration

```python
from tool_decorators import ToolProvider

class FileToolsProvider(ToolProvider):
    def __init__(self):
        super().__init__("file_tools")
        
        self.register_tool(self.read_file, description="Read file contents")
        self.register_tool(self.write_file, description="Write to file")
    
    def read_file(self, path: str, max_bytes: int = 10000) -> str:
        """Read file with size limit."""
        from pathlib import Path
        return Path(path).read_text()[:max_bytes]
    
    def write_file(self, path: str, content: str) -> bool:
        """Write content to file."""
        from pathlib import Path
        Path(path).write_text(content)
        return True
```

## Tool Registry

Access the global tool registry:

```python
from tool_decorators import get_tool_registry

registry = get_tool_registry()

# List all tools
tools = registry.list_tools()

# Get specific tool
tool_def = registry.get_tool("text_analyzer")

# Get tool names
names = registry.get_tool_names()

# Hot-reload
registry.unregister("old_tool")
registry.reload_tool("updated_tool", new_function)
```

## Schema Generation

Type hints are automatically converted to JSON Schema:

| Python Type | JSON Schema Type |
|-------------|------------------|
| `str` | `{"type": "string"}` |
| `int` | `{"type": "integer"}` |
| `float` | `{"type": "number"}` |
| `bool` | `{"type": "boolean"}` |
| `list`, `List` | `{"type": "array"}` |
| `dict`, `Dict` | `{"type": "object"}` |
| `Optional[T]` | Schema for `T` (not required) |

Parameters without default values are marked as `required` in the schema.

## Integration with MCP Bridge

Tools registered with the decorator system can be exposed via the MCP bridge:

```python
# In mcp-bridge-hybrid.py
from tool_decorators import get_tool_registry

registry = get_tool_registry()

# Get all tool schemas for MCP
tools_list = []
for tool_def in registry.list_tools():
    tools_list.append({
        "name": tool_def.name,
        "description": tool_def.description,
        "inputSchema": tool_def.input_schema,
    })
```

## Examples

See [example_tools.py](./example_tools.py) for complete examples demonstrating:
- Basic tools with type hints
- Optional parameters and defaults
- Custom names and metadata
- Provider-based registration
- Hot-reloading patterns

## API Reference

### `@tool` Decorator

```python
def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    provider: str = "default",
    **metadata
) -> Callable
```

**Parameters:**
- `name`: Custom tool name (defaults to function name)
- `description`: Tool description (defaults to docstring first line)
- `provider`: Provider name for grouping (default: "default")
- `**metadata`: Additional metadata attached to tool definition

### `ToolRegistry` Class

**Methods:**
- `register(name, func, description, schema, metadata, provider)`: Register a tool
- `get_tool(name)`: Get tool by name
- `list_tools(provider=None)`: List all tools (optionally filtered)
- `get_tool_names()`: Get list of tool names
- `unregister(name)`: Remove a tool (returns bool)
- `reload_tool(name, func)`: Hot-reload tool with new implementation

### `ToolProvider` Class

**Methods:**
- `register_tool(func, name=None, description=None, **metadata)`: Register tool with provider
- `tools`: Property returning list of provider's tools
- `get_tool_schemas()`: Get MCP-compatible schemas for all tools

### `ToolDefinition` Dataclass

**Attributes:**
- `name`: Tool name
- `description`: Tool description
- `function`: The decorated function
- `input_schema`: JSON Schema for parameters
- `metadata`: Additional metadata dict

## Best Practices

1. **Use Type Hints**: Always provide type annotations for accurate schema generation
2. **Write Clear Docstrings**: First line becomes the tool description
3. **Group Related Tools**: Use providers to organize domain-specific tools
4. **Test Tools Independently**: Tools are just functions and can be tested directly
5. **Leverage Hot-Reloading**: Update tools without restarting the system during development

## Migration from Manual Registration

**Before:**
```python
TOOLS = [{
    "name": "my_tool",
    "description": "Does something",
    "inputSchema": {
        "type": "object",
        "properties": {
            "param1": {"type": "string"},
            "param2": {"type": "integer"},
        },
        "required": ["param1"],
    },
}]
```

**After:**
```python
@tool
def my_tool(param1: str, param2: int = 0):
    """Does something."""
    pass
```

Much simpler and type-safe!
