#!/usr/bin/env python3
"""
Example tools demonstrating the @tool decorator pattern.

These tools showcase automatic schema generation, type handling,
and provider-based registration.
"""

from typing import List, Optional
from tool_decorators import tool, ToolProvider


# ── Example 1: Simple Tool with Basic Types ──────────────────────────────

@tool
def text_analyzer(text: str, case_sensitive: bool = False) -> dict:
    """
    Analyze text and return statistics.
    
    Counts words, characters, and lines in the provided text.
    Optionally performs case-sensitive analysis.
    """
    lines = text.split('\n')
    words = text.split() if case_sensitive else text.lower().split()
    
    return {
        "word_count": len(words),
        "char_count": len(text),
        "line_count": len(lines),
        "unique_words": len(set(words)),
    }


# ── Example 2: Tool with Optional Parameters ──────────────────────────────

@tool(description="Search for patterns in text with optional filtering")
def pattern_search(
    text: str,
    pattern: str,
    max_results: int = 10,
    ignore_case: bool = True,
) -> List[dict]:
    """
    Search for pattern occurrences in text.
    
    Returns list of matches with position information.
    Supports case-insensitive search and result limiting.
    """
    import re
    
    flags = re.IGNORECASE if ignore_case else 0
    matches = []
    
    for match in re.finditer(pattern, text, flags):
        matches.append({
            "text": match.group(),
            "start": match.start(),
            "end": match.end(),
        })
        
        if len(matches) >= max_results:
            break
    
    return matches


# ── Example 3: Tool with Custom Name and Provider ─────────────────────────

@tool(name="workflow_validator", provider="qa", category="validation")
def validate_workflow_structure(workflow_path: str, strict: bool = False) -> dict:
    """
    Validate workflow file structure and format.
    
    Checks for required fields, proper formatting, and optional
    strict validation of content.
    """
    from pathlib import Path
    import json
    
    path = Path(workflow_path)
    
    if not path.exists():
        return {
            "valid": False,
            "errors": [f"Workflow file not found: {workflow_path}"],
        }
    
    errors = []
    warnings = []
    
    # Read and parse
    try:
        content = path.read_text()
        
        # Check if JSON
        if workflow_path.endswith('.json'):
            data = json.loads(content)
            
            # Validate required fields
            required = ['name', 'steps']
            for field in required:
                if field not in data:
                    errors.append(f"Missing required field: {field}")
        
        # Check if markdown
        elif workflow_path.endswith('.md'):
            if not content.strip():
                errors.append("Empty workflow file")
            
            if strict and '##' not in content:
                warnings.append("No section headers found")
        
        else:
            warnings.append("Unknown workflow format")
    
    except Exception as e:
        errors.append(f"Parse error: {str(e)}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "path": workflow_path,
    }


# ── Example 4: Provider-Based Tool Registration ───────────────────────────

class FileToolsProvider(ToolProvider):
    """Provider for file-related tools."""
    
    def __init__(self):
        super().__init__("file_tools")
        
        # Register tools via provider
        self.register_tool(self.read_lines, description="Read lines from file")
        self.register_tool(self.count_files, description="Count files in directory")
    
    def read_lines(self, filepath: str, max_lines: int = 100) -> List[str]:
        """Read lines from a file with limit."""
        from pathlib import Path
        
        path = Path(filepath)
        if not path.exists():
            return []
        
        lines = path.read_text().split('\n')
        return lines[:max_lines]
    
    def count_files(self, directory: str, pattern: str = "*") -> int:
        """Count files matching pattern in directory."""
        from pathlib import Path
        
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return 0
        
        return len(list(dir_path.glob(pattern)))


# ── Usage Example ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    from tool_decorators import get_tool_registry
    
    # Get registry
    registry = get_tool_registry()
    
    print("Registered Tools:")
    print("=" * 60)
    
    for tool_def in registry.list_tools():
        print(f"\n{tool_def.name}")
        print(f"  Description: {tool_def.description}")
        print(f"  Schema: {tool_def.input_schema}")
        if tool_def.metadata:
            print(f"  Metadata: {tool_def.metadata}")
    
    # Test a tool
    print("\n" + "=" * 60)
    print("Testing text_analyzer tool:")
    print("=" * 60)
    
    result = text_analyzer("Hello World\nThis is a test\nWith multiple lines", case_sensitive=False)
    print(f"Result: {result}")
    
    # Create provider instance
    print("\n" + "=" * 60)
    print("Provider-based tools:")
    print("=" * 60)
    
    file_provider = FileToolsProvider()
    for tool_def in file_provider.tools:
        print(f"  - {tool_def.name}: {tool_def.description}")
