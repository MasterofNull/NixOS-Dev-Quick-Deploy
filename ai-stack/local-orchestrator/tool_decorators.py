#!/usr/bin/env python3
"""
Strands-style tool decorator system for simplified tool creation.

Provides @tool decorator for automatic schema generation from function
signatures and docstrings, plus tool registry with hot-reloading support.
"""

import inspect
import json
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, get_type_hints


@dataclass
class ToolDefinition:
    """Tool definition with schema and metadata."""
    name: str
    description: str
    function: Callable
    input_schema: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """
    Registry for managing decorated tools with hot-reloading support.
    
    Maintains tool definitions and enables dynamic tool discovery.
    """
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._providers: Dict[str, List[ToolDefinition]] = {}
    
    def register(
        self,
        name: str,
        func: Callable,
        description: str,
        schema: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        provider: str = "default",
    ) -> ToolDefinition:
        """
        Register a tool in the registry.
        
        Args:
            name: Tool name
            func: Tool function
            description: Tool description
            schema: JSON Schema for inputs
            metadata: Optional metadata
            provider: Provider name for grouping
            
        Returns:
            ToolDefinition instance
        """
        tool_def = ToolDefinition(
            name=name,
            description=description,
            function=func,
            input_schema=schema,
            metadata=metadata or {},
        )
        
        self._tools[name] = tool_def
        
        if provider not in self._providers:
            self._providers[provider] = []
        self._providers[provider].append(tool_def)
        
        return tool_def
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get tool by name."""
        return self._tools.get(name)
    
    def list_tools(self, provider: Optional[str] = None) -> List[ToolDefinition]:
        """List all tools, optionally filtered by provider."""
        if provider:
            return self._providers.get(provider, [])
        return list(self._tools.values())
    
    def get_tool_names(self) -> List[str]:
        """Get list of all registered tool names."""
        return list(self._tools.keys())
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a tool (useful for hot-reloading).
        
        Returns:
            True if tool was removed, False if not found
        """
        if name in self._tools:
            tool = self._tools.pop(name)
            # Remove from provider lists
            for provider_tools in self._providers.values():
                provider_tools[:] = [t for t in provider_tools if t.name != name]
            return True
        return False
    
    def reload_tool(self, name: str, func: Callable) -> Optional[ToolDefinition]:
        """
        Hot-reload a tool with updated implementation.
        
        Preserves schema but updates function reference.
        """
        if name in self._tools:
            tool_def = self._tools[name]
            tool_def.function = func
            return tool_def
        return None


# Global registry singleton
_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _registry


def _extract_docstring_description(func: Callable) -> str:
    """Extract tool description from function docstring."""
    doc = inspect.getdoc(func)
    if not doc:
        return f"Tool: {func.__name__}"
    
    # Use first line or first paragraph as description
    lines = doc.strip().split('\n\n')
    return lines[0].strip()


def _python_type_to_json_schema(py_type: type) -> Dict[str, Any]:
    """
    Convert Python type annotation to JSON Schema type.
    
    Args:
        py_type: Python type
        
    Returns:
        JSON Schema type definition
    """
    type_map = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array"},
        dict: {"type": "object"},
        List: {"type": "array"},
        Dict: {"type": "object"},
    }
    
    # Handle Optional types
    origin = getattr(py_type, '__origin__', None)
    if origin is type(None):
        return {"type": "null"}
    
    # Handle Union types (Optional is Union[T, None])
    if origin is Union:
        args = getattr(py_type, '__args__', ())
        non_none_types = [t for t in args if t is not type(None)]
        if len(non_none_types) == 1:
            return _python_type_to_json_schema(non_none_types[0])
    
    # Direct type mapping
    base_type = origin or py_type
    schema = type_map.get(base_type, {"type": "string"})
    
    return schema


def _generate_schema_from_signature(func: Callable) -> Dict[str, Any]:
    """
    Generate JSON Schema from function signature.
    
    Args:
        func: Function to analyze
        
    Returns:
        JSON Schema for function parameters
    """
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)
    
    properties = {}
    required = []
    
    for param_name, param in sig.parameters.items():
        # Skip self/cls parameters
        if param_name in ('self', 'cls'):
            continue
        
        # Get type hint
        param_type = type_hints.get(param_name, str)
        
        # Generate schema for this parameter
        param_schema = _python_type_to_json_schema(param_type)
        
        # Add description from docstring if available
        param_schema["description"] = f"Parameter: {param_name}"
        
        properties[param_name] = param_schema
        
        # Check if required (no default value)
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    
    schema = {
        "type": "object",
        "properties": properties,
    }
    
    if required:
        schema["required"] = required
    
    return schema


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    provider: str = "default",
    **metadata
):
    """
    Decorator to register a function as a tool with automatic schema generation.
    
    Converts a Python function into a tool with JSON Schema generated from
    type hints and docstring.
    
    Usage:
        @tool
        def my_tool(text: str, count: int = 5) -> str:
            '''Process text with count.'''
            return text * count
        
        @tool(name="custom_name", provider="my_provider")
        def another_tool(query: str) -> dict:
            '''Custom tool with specific name.'''
            return {"result": query}
    
    Args:
        name: Optional custom tool name (defaults to function name)
        description: Optional description (defaults to docstring)
        provider: Provider name for grouping (default: "default")
        **metadata: Additional metadata to attach to tool
        
    Returns:
        Decorated function with tool registration
    """
    def decorator(func: Callable) -> Callable:
        # Determine tool name
        tool_name = name or func.__name__
        
        # Extract description
        tool_desc = description or _extract_docstring_description(func)
        
        # Generate schema
        schema = _generate_schema_from_signature(func)
        
        # Register in global registry
        tool_def = _registry.register(
            name=tool_name,
            func=func,
            description=tool_desc,
            schema=schema,
            metadata=metadata,
            provider=provider,
        )
        
        # Attach tool definition to function for introspection
        func._tool_def = tool_def
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Preserve tool definition on wrapper
        wrapper._tool_def = tool_def
        
        return wrapper
    
    # Support both @tool and @tool(args)
    if callable(name):
        # Called as @tool without parentheses
        func = name
        name = None
        return decorator(func)
    
    return decorator


# Import Union for type handling
from typing import Union


class ToolProvider:
    """
    Base class for tool providers.
    
    Providers group related tools and enable batch registration.
    """
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self._tools: List[ToolDefinition] = []
    
    def register_tool(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        **metadata
    ) -> ToolDefinition:
        """
        Register a tool with this provider.
        
        Args:
            func: Tool function
            name: Optional tool name
            description: Optional description
            **metadata: Additional metadata
            
        Returns:
            ToolDefinition instance
        """
        tool_name = name or func.__name__
        tool_desc = description or _extract_docstring_description(func)
        schema = _generate_schema_from_signature(func)
        
        tool_def = _registry.register(
            name=tool_name,
            func=func,
            description=tool_desc,
            schema=schema,
            metadata=metadata,
            provider=self.provider_name,
        )
        
        self._tools.append(tool_def)
        return tool_def
    
    @property
    def tools(self) -> List[ToolDefinition]:
        """Get all tools from this provider."""
        return self._tools.copy()
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get MCP-compatible tool schemas.
        
        Returns:
            List of tool schemas for MCP protocol
        """
        schemas = []
        for tool_def in self._tools:
            schemas.append({
                "name": tool_def.name,
                "description": tool_def.description,
                "inputSchema": tool_def.input_schema,
            })
        return schemas
